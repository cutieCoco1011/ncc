import json
import os

from ncc import real_smoke


def test_real_smoke_skips_without_explicit_novelai_provider(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("NCC_IMAGE_PROVIDER", raising=False)
    monkeypatch.delenv("NOVELAI_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["ncc-novelai-smoke", "--env-file", str(tmp_path / "missing.env")],
    )

    real_smoke.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "skipped"
    assert payload["reason"] == "NCC_IMAGE_PROVIDER is not novelai"


def test_env_loader_does_not_override_process_env(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / "local.env"
    env_file.write_text("NCC_IMAGE_PROVIDER=novelai\n" + "NOVELAI_API_TOKEN" + "=file-token\n")
    monkeypatch.setenv("NOVELAI_API_TOKEN", "process-token")

    real_smoke._load_env_file(env_file)

    assert os.environ["NCC_IMAGE_PROVIDER"] == "novelai"
    assert os.environ["NOVELAI_API_TOKEN"] == "process-token"
