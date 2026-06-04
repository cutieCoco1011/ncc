import io
from pathlib import Path
import zipfile

from ncc.fixtures import GOLD_PATH_KOREAN_SOURCE
from PIL import Image

from ncc.images import CandidateGenerationService, NovelAIImageBackend, png_dimensions
from ncc.models import NAIPrompt, NAIPromptSet
from ncc.prompts import PromptCompiler
from ncc.story_pipeline import MockLLMStoryProvider


def test_mock_image_generation_creates_eighteen_candidate_records(tmp_path: Path) -> None:
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)
    compiler = PromptCompiler()
    prompt_ir = compiler.build_prompt_ir("demo", bundle.panel_specs, bundle.characters)
    nai_prompts = compiler.compile_nai_prompts("demo", prompt_ir)

    candidates = CandidateGenerationService().generate_candidates("demo", tmp_path, nai_prompts)

    assert len(candidates.candidates) == 18
    assert len(candidates.by_panel()) == 6
    first_path = tmp_path / candidates.candidates[0].image_path
    assert first_path.exists()
    assert png_dimensions(first_path) == (1080, 1440)
    assert candidates.candidates[0].provider_metadata["provider"] == "mock-image"


def test_novelai_backend_posts_payload_and_decodes_zip_response(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout, context):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return _FakeNovelAIResponse(_zip_png_bytes())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    prompt = NAIPrompt(
        panel_id="p1",
        base_prompt="cinematic webtoon panel, rainy bus stop",
        character_prompts={"harin": "short black hair, yellow raincoat"},
        undesired_prompt="text, watermark",
        seed=100,
        settings={"width": 832, "height": 1216, "steps": 12, "scale": 5.5, "sampler": "k_euler_ancestral"},
    )
    backend = NovelAIImageBackend(
        api_token="dummy-token",
        endpoint="https://image.novelai.net/ai/generate-image",
        model="nai-diffusion-3",
        timeout_seconds=3,
    )
    output_path = tmp_path / "candidate.png"

    metadata = backend.generate(prompt, output_path, seed=101, panel_order=1, candidate_index=1)

    assert output_path.exists()
    assert png_dimensions(output_path) == (64, 96)
    assert captured["url"] == "https://image.novelai.net/ai/generate-image"
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert '"model": "nai-diffusion-3"' in captured["body"]
    assert '"seed": 101' in captured["body"]
    assert '"negative_prompt": "text, watermark"' in captured["body"]
    assert metadata["provider"] == "novelai"
    assert metadata["model"] == "nai-diffusion-3"


def test_candidate_service_preserves_novelai_provider_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _FakeNovelAIResponse(_zip_png_bytes()))
    prompt_set = NAIPromptSet(
        project_id="demo",
        prompts=[
            NAIPrompt(
                panel_id="p1",
                base_prompt="webtoon panel",
                character_prompts={"harin": "yellow raincoat"},
                undesired_prompt="text",
                seed=1,
                settings={"width": 64, "height": 96},
            )
        ],
    )
    service = CandidateGenerationService(
        NovelAIImageBackend(
            api_token="dummy-token",
            endpoint="https://image.novelai.net/ai/generate-image",
            model="nai-diffusion-3",
            timeout_seconds=3,
        )
    )

    candidates = service.generate_candidates("demo", tmp_path, prompt_set, candidates_per_panel=1)

    assert len(candidates.candidates) == 1
    candidate = candidates.candidates[0]
    assert candidate.provider_metadata["provider"] == "novelai"
    assert candidate.provider_metadata["width"] == 64
    assert (tmp_path / candidate.image_path).exists()


class _FakeNovelAIResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = {"content-type": "application/zip"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._body


def _zip_png_bytes() -> bytes:
    image = Image.new("RGB", (64, 96), (40, 80, 120))
    image_buffer = io.BytesIO()
    image.save(image_buffer, "PNG")
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("image_0.png", image_buffer.getvalue())
    return archive_buffer.getvalue()
