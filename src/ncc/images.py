from __future__ import annotations

import base64
import json
import io
import os
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .models import CandidateImage, CandidateSet, NAIPrompt, NAIPromptSet, ProviderKind, QAStatus, text_hash
from .storage import safe_project_path


class NovelAIImageError(RuntimeError):
    pass


class NovelAIImageBackend:
    provider_name = "novelai"

    def __init__(
        self,
        api_token: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_token = api_token
        self.endpoint = endpoint or os.environ.get(
            "NOVELAI_IMAGE_ENDPOINT",
            "https://image.novelai.net/ai/generate-image",
        )
        self.model = model or os.environ.get("NOVELAI_IMAGE_MODEL", "nai-diffusion-3")
        self.timeout_seconds = timeout_seconds or float(os.environ.get("NOVELAI_TIMEOUT_SECONDS", "180"))

    @property
    def status(self) -> ProviderKind:
        return ProviderKind.NOVELAI if self.api_token else ProviderKind.NOT_CONFIGURED

    def generate(
        self,
        prompt: NAIPrompt,
        output_path: Path,
        seed: int,
        panel_order: int,
        candidate_index: int,
    ) -> dict[str, Any]:
        if not self.api_token:
            raise RuntimeError("NovelAI image provider is not_configured")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._payload(prompt, seed)
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "accept": "application/zip, image/png, application/json",
                "authorization": _authorization_header(self.api_token),
                "content-type": "application/json",
                "user-agent": "ncc/0.1 local BYOK",
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=_ssl_context(),
            ) as response:
                content_type = response.headers.get("content-type", "")
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            detail = _safe_http_error_detail(exc)
            raise NovelAIImageError(f"NovelAI image generation failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise NovelAIImageError(f"NovelAI image generation request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise NovelAIImageError("NovelAI image generation timed out") from exc

        _write_generation_response(response_body, content_type, output_path)
        width, height = png_dimensions(output_path)
        return {
            "provider": self.provider_name,
            "endpoint_host": urllib.parse.urlparse(self.endpoint).netloc,
            "model": self.model,
            "candidate_index": candidate_index,
            "panel_order": panel_order,
            "width": width,
            "height": height,
            "response_content_type": content_type,
        }

    def _payload(self, prompt: NAIPrompt, seed: int) -> dict[str, Any]:
        settings = {
            "width": int(prompt.settings.get("width", 832)),
            "height": int(prompt.settings.get("height", 1216)),
            "steps": int(prompt.settings.get("steps", 28)),
            "scale": float(prompt.settings.get("scale", 6.5)),
            "sampler": str(prompt.settings.get("sampler", "k_euler_ancestral")),
            "seed": seed,
            "n_samples": 1,
            "image_format": "png",
            "qualityToggle": True,
        }
        if prompt.undesired_prompt:
            settings["negative_prompt"] = prompt.undesired_prompt
        return {
            "action": "generate",
            "input": _combined_prompt(prompt),
            "model": self.model,
            "parameters": settings,
        }


class MockImageBackend:
    provider_name = "mock-image"

    def generate(
        self,
        prompt: NAIPrompt,
        output_path: Path,
        seed: int,
        panel_order: int,
        candidate_index: int,
    ) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1080, 1440), _panel_color(panel_order, candidate_index))
        draw = ImageDraw.Draw(image)
        font = _load_font(44)
        small = _load_font(28)
        draw.rectangle((60, 60, 1020, 1380), outline=(255, 255, 255), width=6)
        draw.rectangle((90, 100, 990, 330), fill=(255, 255, 255))
        draw.text((125, 135), f"Panel {panel_order} / Candidate {candidate_index}", fill=(20, 20, 20), font=font)
        draw.text((125, 205), f"seed {seed}", fill=(60, 60, 60), font=small)
        draw.text((125, 260), "mock visual - dialogue added in lettering", fill=(60, 60, 60), font=small)
        image.save(output_path, "PNG")
        return {
            "provider": self.provider_name,
            "candidate_index": candidate_index,
            "panel_order": panel_order,
            "width": 1080,
            "height": 1440,
        }


class CandidateGenerationService:
    def __init__(self, backend: MockImageBackend | NovelAIImageBackend | None = None) -> None:
        self.backend = backend or MockImageBackend()

    def generate_candidates(
        self,
        project_id: str,
        project_dir: Path,
        prompts: NAIPromptSet,
        candidates_per_panel: int = 3,
    ) -> CandidateSet:
        candidates: list[CandidateImage] = []
        for panel_order, prompt in enumerate(prompts.prompts, start=1):
            for candidate_index in range(1, candidates_per_panel + 1):
                seed = prompt.seed + candidate_index
                relative = f"images/{prompt.panel_id}_candidate_{candidate_index}.png"
                output_path = safe_project_path(project_dir, relative)
                provider_metadata = self.backend.generate(prompt, output_path, seed, panel_order, candidate_index)
                candidates.append(
                    CandidateImage(
                        candidate_id=f"{prompt.panel_id}-c{candidate_index}",
                        panel_id=prompt.panel_id,
                        image_path=relative,
                        prompt=prompt,
                        seed=seed,
                        settings=prompt.settings,
                        provider_metadata=provider_metadata,
                        qa_status=QAStatus.PENDING,
                        source_revision=text_hash(prompt.model_dump_json()),
                    )
                )
        return CandidateSet(project_id=project_id, candidates=candidates)


def _combined_prompt(prompt: NAIPrompt) -> str:
    parts = [prompt.base_prompt]
    parts.extend(value for _, value in sorted(prompt.character_prompts.items()) if value)
    return ", ".join(part for part in parts if part)


def _authorization_header(api_token: str) -> str:
    return api_token if api_token.lower().startswith("bearer ") else f"Bearer {api_token}"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _safe_http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", "replace")
    except Exception:
        return exc.reason
    if not raw:
        return exc.reason
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:500]
    message = data.get("message") or data.get("detail") or data.get("error")
    return str(message or data)[:500]


def _write_generation_response(response_body: bytes, content_type: str, output_path: Path) -> None:
    if "application/zip" in content_type or response_body.startswith(b"PK"):
        _write_first_image_from_zip(response_body, output_path)
        return
    if "application/json" in content_type or response_body[:1] in {b"{", b"["}:
        _write_image_from_json(response_body, output_path)
        return
    if response_body.startswith(b"\x89PNG") or "image/" in content_type:
        _write_image_bytes(response_body, output_path)
        return
    raise NovelAIImageError(f"NovelAI returned an unsupported response content type: {content_type or 'unknown'}")


def _write_first_image_from_zip(response_body: bytes, output_path: Path) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(response_body)) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.lower().endswith((".png", ".webp", ".jpg", ".jpeg"))
            ]
            if not names:
                raise NovelAIImageError("NovelAI zip response did not contain an image file")
            _write_image_bytes(archive.read(names[0]), output_path)
    except zipfile.BadZipFile as exc:
        raise NovelAIImageError("NovelAI returned an invalid zip response") from exc


def _write_image_from_json(response_body: bytes, output_path: Path) -> None:
    try:
        payload = json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise NovelAIImageError("NovelAI returned invalid JSON instead of image data") from exc
    image_value = payload.get("image")
    if not image_value:
        error = payload.get("error") or payload.get("message") or "missing image field"
        raise NovelAIImageError(f"NovelAI returned no image data: {error}")
    _write_image_bytes(base64.b64decode(image_value), output_path)


def _write_image_bytes(image_bytes: bytes, output_path: Path) -> None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.convert("RGB").save(output_path, "PNG")
    except Exception as exc:
        raise NovelAIImageError("NovelAI response could not be decoded as an image") from exc


def _panel_color(panel_order: int, candidate_index: int) -> tuple[int, int, int]:
    palette = [
        (62, 93, 118),
        (104, 83, 126),
        (132, 83, 89),
        (82, 115, 87),
        (141, 105, 66),
        (72, 104, 135),
    ]
    base = palette[(panel_order - 1) % len(palette)]
    lift = candidate_index * 18
    return tuple(min(230, channel + lift) for channel in base)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def png_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()
