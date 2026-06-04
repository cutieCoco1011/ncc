from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import CandidateImage, CandidateSet, NAIPrompt, NAIPromptSet, ProviderKind, QAStatus, text_hash
from .storage import safe_project_path


class NovelAIImageBackend:
    def __init__(self, api_token: str | None = None) -> None:
        self.api_token = api_token

    @property
    def status(self) -> ProviderKind:
        return ProviderKind.NOVELAI if self.api_token else ProviderKind.NOT_CONFIGURED

    def generate(self, prompt: NAIPrompt, output_path: Path, seed: int, panel_order: int, candidate_index: int) -> None:
        if not self.api_token:
            raise RuntimeError("NovelAI image provider is not_configured")
        raise NotImplementedError("Real NovelAI generation is an opt-in adapter boundary for v1.")


class MockImageBackend:
    provider_name = "mock-image"

    def generate(self, prompt: NAIPrompt, output_path: Path, seed: int, panel_order: int, candidate_index: int) -> None:
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
                self.backend.generate(prompt, output_path, seed, panel_order, candidate_index)
                candidates.append(
                    CandidateImage(
                        candidate_id=f"{prompt.panel_id}-c{candidate_index}",
                        panel_id=prompt.panel_id,
                        image_path=relative,
                        prompt=prompt,
                        seed=seed,
                        settings=prompt.settings,
                        provider_metadata={
                            "provider": getattr(self.backend, "provider_name", "novelai"),
                            "candidate_index": candidate_index,
                        },
                        qa_status=QAStatus.PENDING,
                        source_revision=text_hash(prompt.model_dump_json()),
                    )
                )
        return CandidateSet(project_id=project_id, candidates=candidates)


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
