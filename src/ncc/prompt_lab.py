from __future__ import annotations

import argparse
import json
import sys
from pydantic import BaseModel, Field

from .models import TagCandidate
from .prompts import LOCAL_BASE_PROMPT_TOKENS, _dedupe
from .tags import CanonicalTagCompiler, SourceTextTagPipeline


class PromptLabResult(BaseModel):
    provider: str = "local"
    positive_prompt: str
    negative_prompt: str
    tags: list[TagCandidate] = Field(default_factory=list)
    negative_tags: list[TagCandidate] = Field(default_factory=list)


def compile_prompt_text(source_text: str, panel_id: str = "preview") -> PromptLabResult:
    compiler = CanonicalTagCompiler.from_default_lexicon()
    pipeline = SourceTextTagPipeline(compiler)
    compiled = pipeline.compile_source_text(
        panel_id=panel_id,
        provider="local",
        source_text=source_text,
        base_candidates=[
            "vertical webtoon panel",
            "cinematic composition",
            "dramatic lighting",
        ],
        evidence={"source": "prompt_lab"},
    )
    positive = _dedupe(LOCAL_BASE_PROMPT_TOKENS + [tag.tag for tag in compiled.positive])
    negative = _dedupe(compiler.negative_defaults + [tag.tag for tag in compiled.negative])
    return PromptLabResult(
        positive_prompt=", ".join(positive),
        negative_prompt=", ".join(negative),
        tags=compiled.positive,
        negative_tags=compiled.negative,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile Korean source text into a local Danbooru-style NovelAI prompt.")
    parser.add_argument("text", nargs="*", help="Prompt source text. If omitted, stdin is used.")
    parser.add_argument("--json", action="store_true", help="Print JSON with tags and provenance.")
    args = parser.parse_args(argv)

    source_text = " ".join(args.text).strip() if args.text else sys.stdin.read().strip()
    if not source_text:
        parser.error("provide source text as arguments or stdin")

    result = compile_prompt_text(source_text)
    if args.json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    _print_text_result(result)
    return 0


def _print_text_result(result: PromptLabResult) -> None:
    print("POSITIVE:")
    print(result.positive_prompt)
    print()
    print("NEGATIVE:")
    print(result.negative_prompt)


if __name__ == "__main__":
    raise SystemExit(main())
