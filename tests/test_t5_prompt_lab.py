from __future__ import annotations

import json
import subprocess
import sys

from ncc.prompt_lab import compile_prompt_text


def test_compile_prompt_text_returns_copyable_novelai_prompts() -> None:
    result = compile_prompt_text(
        "노란 우비를 입은 소녀가 겨울 바닷가에서 오래된 엽서를 발견한다. "
        "멀리 등대 불빛이 켜지고 비가 내린다."
    )

    assert "yellow_raincoat" in result.positive_prompt
    assert "winter_seaside" in result.positive_prompt
    assert "postcard" in result.positive_prompt
    assert "library" not in result.positive_prompt
    assert "text" in result.negative_prompt
    assert "watermark" in result.negative_prompt
    assert not any("가" <= character <= "힣" for character in result.positive_prompt)


def test_prompt_lab_preserves_current_project_motifs_and_filters_negation() -> None:
    result = compile_prompt_text(
        "비 오는 전차 정류장에서 고양이 브로치가 빛나고 푸른 전광판이 켜진다. "
        "골목 끝에는 그림자 괴물이 있지만, 바닷가는 아니다."
    )

    positive_tags = {tag.strip() for tag in result.positive_prompt.split(",")}
    assert {"rain", "tram_stop", "cat_brooch", "blue_station_display", "narrow_alley", "shadow_creature"} <= positive_tags
    assert "winter_seaside" not in positive_tags


def test_prompt_lab_cli_reads_stdin_and_outputs_json() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "ncc.prompt_lab", "--json"],
        input="노란 우비와 엽서가 있는 겨울 바닷가 장면",
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["provider"] == "local"
    positive_tags = {tag.strip() for tag in payload["positive_prompt"].split(",")}
    assert "yellow_raincoat" in payload["positive_prompt"]
    assert "winter_seaside" in payload["positive_prompt"]
    assert "library" not in positive_tags
    assert "rain" not in positive_tags
    assert payload["tags"][0]["provenance"]["provider"] == "local"
    assert payload["tags"][0]["provenance"]["extractor"] == "local_alias"
