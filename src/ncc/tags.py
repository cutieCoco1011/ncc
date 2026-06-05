from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Protocol

import yaml

from .models import TagCandidate


class TagProvider(Protocol):
    provider_name: str

    def tags_for_panel(self, panel_id: str, beat: str, emotion: str) -> list[TagCandidate]:
        ...


class CandidateExtractor(Protocol):
    provider_name: str

    def candidates_for_text(self, text: str) -> list[str]:
        ...


def normalize_danbooru_tag(value: str) -> str:
    if re.search(r"[가-힣]", value):
        return ""
    normalized = value.strip().lower().replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_()]+", "", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


@dataclass(frozen=True)
class CompiledTags:
    positive: list[TagCandidate]
    negative: list[TagCandidate]


@dataclass(frozen=True)
class AliasEntry:
    alias: str
    canonical: str


class LocalAliasCandidateExtractor:
    provider_name = "local_alias"

    def __init__(self, aliases: list[AliasEntry]) -> None:
        self.aliases = aliases

    def candidates_for_text(self, text: str) -> list[str]:
        return [
            entry.alias
            for entry in self.aliases
            if _alias_matches(entry.alias, text)
        ]

    def negated_candidates_for_text(self, text: str) -> list[str]:
        return [
            entry.alias
            for entry in self.aliases
            if _alias_has_negated_match(entry.alias, text)
        ]


class SourceTextTagPipeline:
    def __init__(
        self,
        compiler: CanonicalTagCompiler | None = None,
        extractor: LocalAliasCandidateExtractor | None = None,
        extractors: list[CandidateExtractor] | None = None,
        fail_on_extractor_error: bool = False,
    ) -> None:
        self.compiler = compiler or CanonicalTagCompiler.from_default_lexicon()
        self.extractors = extractors or [extractor or self.compiler.alias_extractor]
        self.extractor = self.extractors[0]
        self.fail_on_extractor_error = fail_on_extractor_error

    def compile_source_text(
        self,
        panel_id: str,
        provider: str,
        source_text: str,
        base_candidates: list[str] | None = None,
        evidence: dict[str, str] | None = None,
    ) -> CompiledTags:
        candidates = list(base_candidates or [])
        extractor_names: list[str] = []
        extractor_errors: list[str] = []
        for candidate_extractor in self.extractors:
            extractor_names.append(candidate_extractor.provider_name)
            try:
                candidates.extend(candidate_extractor.candidates_for_text(source_text))
            except RuntimeError as exc:
                if self.fail_on_extractor_error:
                    raise ValueError(f"tag candidate extractor failed: {candidate_extractor.provider_name}") from exc
                extractor_errors.append(f"{candidate_extractor.provider_name}:{type(exc).__name__}")
        evidence_payload: dict[str, str] = {
            "compiler": "local_canonical",
            **(evidence or {}),
            "extractor": ",".join(extractor_names),
        }
        if extractor_errors:
            evidence_payload["extractor_errors"] = ",".join(extractor_errors)
        compiled = self.compiler.compile_candidates(
            panel_id=panel_id,
            provider=provider,
            candidates=candidates,
            evidence=evidence_payload,
        )
        negated_tags = self.compiler.negated_tags_for_text(source_text)
        if not negated_tags:
            return compiled
        return CompiledTags(
            positive=[candidate for candidate in compiled.positive if candidate.tag not in negated_tags],
            negative=compiled.negative,
        )


class OpenAICompatibleTagCandidateExtractor:
    provider_name: str

    def __init__(
        self,
        provider_name: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 30,
    ) -> None:
        self.provider_name = provider_name
        self.api_key = api_key
        self.model = model
        self.endpoint = _chat_completions_endpoint(base_url)
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls, provider_name: str) -> "OpenAICompatibleTagCandidateExtractor":
        if provider_name == "deepseek":
            return cls(
                provider_name=provider_name,
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                timeout_seconds=float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "30")),
            )
        if provider_name == "openai":
            return cls(
                provider_name=provider_name,
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                model=os.environ.get("OPENAI_TAG_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")),
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                timeout_seconds=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30")),
            )
        if provider_name == "mimo":
            return cls(
                provider_name=provider_name,
                api_key=os.environ.get("MIMO_API_KEY", ""),
                model=os.environ.get("MIMO_MODEL", "mimo-tag-candidate"),
                base_url=os.environ.get("MIMO_BASE_URL", ""),
                timeout_seconds=float(os.environ.get("MIMO_TIMEOUT_SECONDS", "30")),
            )
        raise RuntimeError(f"unsupported model-assisted tag provider: {provider_name}")

    def candidates_for_text(self, text: str) -> list[str]:
        if not self.api_key or not self.endpoint:
            raise RuntimeError(f"{self.provider_name} tag suggester is not configured")
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 256,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only. Extract candidate Danbooru/NovelAI prompt tags from the user's scene. "
                        "Use the shape {\"tags\": [\"tag_one\", \"tag_two\"]}. Do not write final prompts."
                    ),
                },
                {"role": "user", "content": text},
            ],
        }
        if self.provider_name == "deepseek":
            payload["thinking"] = {"type": "disabled"}
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=_ssl_context(),
            ) as response:
                response_body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"{self.provider_name} tag suggestion failed") from exc
        try:
            data = json.loads(response_body)
            content = data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"{self.provider_name} tag suggestion returned malformed response") from exc
        return _candidate_tags_from_model_content(content)


def _chat_completions_endpoint(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return ""
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _candidate_tags_from_model_content(content: str) -> list[str]:
    try:
        payload = json.loads(_json_payload_text(content))
    except json.JSONDecodeError as exc:
        raise RuntimeError("model tag suggestion response was not JSON") from exc
    raw_tags: Any
    if isinstance(payload, list):
        raw_tags = payload
    elif isinstance(payload, dict):
        raw_tags = (
            payload.get("tags")
            or payload.get("tag_candidates")
            or payload.get("positive_tags")
            or payload.get("candidates")
            or []
        )
    else:
        raw_tags = []
    if isinstance(raw_tags, str):
        return [
            tag.strip()
            for tag in re.split(r"[,\n]", raw_tags)
            if tag.strip()
        ]
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    for item in raw_tags:
        if isinstance(item, str):
            tags.append(item)
        elif isinstance(item, dict):
            value = item.get("tag") or item.get("name") or item.get("canonical")
            if isinstance(value, str):
                tags.append(value)
    return tags


def _json_payload_text(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, count=1)
        stripped = re.sub(r"\s*```$", "", stripped, count=1)
    return stripped.strip()


class CanonicalTagCompiler:
    @classmethod
    def from_default_lexicon(cls) -> "CanonicalTagCompiler":
        lexicon_path = Path(__file__).with_name("danbooru_lexicon.yaml")
        data = yaml.safe_load(lexicon_path.read_text(encoding="utf-8"))
        return cls(data)

    def __init__(self, lexicon: dict[str, Any]) -> None:
        self.canonical_tags: dict[str, dict[str, Any]] = dict(lexicon.get("canonical_tags", {}))
        self.positive_blocklist = set(lexicon.get("positive_blocklist", []))
        self.negative_defaults = list(lexicon.get("negative_defaults", []))
        self.required_categories = list(lexicon.get("required_categories", []))
        self.alias_to_canonical: dict[str, str] = {}
        alias_entries: list[AliasEntry] = []
        seen_alias_entries: set[tuple[str, str]] = set()
        for canonical, spec in self.canonical_tags.items():
            self.alias_to_canonical[canonical] = canonical
            _append_alias_entry(alias_entries, seen_alias_entries, canonical, canonical)
            for alias in spec.get("aliases", []):
                raw_alias = str(alias)
                self.alias_to_canonical[raw_alias.lower()] = canonical
                _append_alias_entry(alias_entries, seen_alias_entries, raw_alias, canonical)
                normalized = normalize_danbooru_tag(str(alias))
                if normalized:
                    self.alias_to_canonical[normalized] = canonical
                    _append_alias_entry(alias_entries, seen_alias_entries, normalized, canonical)
        self.alias_extractor = LocalAliasCandidateExtractor(alias_entries)

    def canonicalize(self, value: str) -> str:
        raw = value.strip()
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered in self.alias_to_canonical:
            return self.alias_to_canonical[lowered]
        normalized = normalize_danbooru_tag(raw)
        if normalized in self.alias_to_canonical:
            return self.alias_to_canonical[normalized]
        return normalized if normalized in self.canonical_tags else ""

    def negated_tags_for_text(self, text: str) -> set[str]:
        positive = {
            canonical
            for alias in self.alias_extractor.candidates_for_text(text)
            if (canonical := self.canonicalize(alias))
        }
        negated: set[str] = set()
        for alias in self.alias_extractor.negated_candidates_for_text(text):
            canonical = self.canonicalize(alias)
            if canonical:
                negated.add(canonical)
                for veto in self.canonical_tags.get(canonical, {}).get("negation_vetoes", []):
                    veto_canonical = self.canonicalize(str(veto))
                    if veto_canonical and veto_canonical not in positive:
                        negated.add(veto_canonical)
        return negated

    def compile_candidates(
        self,
        panel_id: str,
        provider: str,
        candidates: list[str],
        evidence: dict[str, str],
    ) -> CompiledTags:
        positive: list[TagCandidate] = []
        negative: list[TagCandidate] = []
        seen: set[str] = set()
        for raw in candidates:
            for tag in self._tags_from_candidate(raw):
                if tag in seen:
                    continue
                seen.add(tag)
                candidate = TagCandidate(
                    tag=tag,
                    source=provider,
                    confidence=0.8,
                    provenance={"panel_id": panel_id, "provider": provider, **evidence},
                )
                if tag in self.positive_blocklist:
                    negative.append(candidate)
                else:
                    positive.append(candidate)
        return CompiledTags(positive=positive, negative=negative)

    def _tags_from_candidate(self, raw: str) -> list[str]:
        exact = self.canonicalize(raw)
        if exact:
            return [exact]
        matches: list[str] = []
        for candidate in self.alias_extractor.candidates_for_text(raw):
            canonical = self.canonicalize(candidate)
            if canonical and canonical not in matches:
                matches.append(canonical)
        return matches


def _append_alias_entry(
    entries: list[AliasEntry],
    seen: set[tuple[str, str]],
    alias: str,
    canonical: str,
) -> None:
    key = (alias.strip().lower(), canonical)
    if key[0] and key not in seen:
        seen.add(key)
        entries.append(AliasEntry(alias=alias.strip(), canonical=canonical))


def _alias_matches(alias: str, text: str) -> bool:
    if not alias.strip():
        return False
    return any(
        not _match_is_negated(text, match.span())
        for match in _alias_match_iter(alias, text)
    )


def _alias_has_negated_match(alias: str, text: str) -> bool:
    if not alias.strip():
        return False
    return any(
        _match_is_negated(text, match.span())
        for match in _alias_match_iter(alias, text)
    )


def _alias_match_iter(alias: str, text: str) -> list[re.Match[str]]:
    if _contains_hangul(alias):
        return _korean_alias_match_iter(alias, text)
    if _contains_japanese(alias):
        return _japanese_alias_match_iter(alias, text)
    if _contains_latin(alias):
        return _latin_alias_match_iter(alias, text)
    return list(re.finditer(re.escape(alias.lower()), text.lower()))


def _latin_alias_match_iter(alias: str, text: str) -> list[re.Match[str]]:
    parts = [part for part in re.split(r"[\s_]+", alias.strip().lower()) if part]
    if not parts:
        return []
    pattern = r"(?<![A-Za-z0-9_])" + r"[\s_]+".join(re.escape(part) for part in parts)
    pattern += r"(?![A-Za-z0-9_])"
    return list(re.finditer(pattern, text.lower()))


def _korean_alias_match_iter(alias: str, text: str) -> list[re.Match[str]]:
    parts = [part for part in re.split(r"\s+", alias.strip()) if part]
    if not parts:
        return []
    pattern = r"(?<![가-힣A-Za-z0-9])" + r"\s*".join(re.escape(part) for part in parts)
    pattern += r"(?=$|[^가-힣A-Za-z0-9]|[은는이가을를와과에으도만의로])"
    return list(re.finditer(pattern, text))


def _japanese_alias_match_iter(alias: str, text: str) -> list[re.Match[str]]:
    pattern = re.escape(alias.strip())
    pattern += r"(?=$|[^ぁ-ゖァ-ヺ一-龯A-Za-z0-9]|(?:では|じゃ|だけ|です|ます|は|が|を|に|で|と|へ|も|の))"
    return list(re.finditer(pattern, text))


def _match_is_negated(text: str, span: tuple[int, int]) -> bool:
    start, end = span
    before = text[max(0, start - 48):start]
    after = text[end:min(len(text), end + 48)]
    return (
        _english_negates(before)
        or _korean_negates(before, after)
        or _japanese_negates(before, after)
    )


def _english_negates(before: str) -> bool:
    return re.search(r"(?:^|[\s,(;])(?:no|not|without|never)\s+(?:[a-z0-9_-]+\s+){0,3}$", before.lower()) is not None


def _korean_negates(before: str, after: str) -> bool:
    if re.search(r"(?:없는|없이|아닌|제외한|빼고)\s*$", before):
        return True
    return (
        re.match(
            r"\s*(?:[은는이가을를와과에의로도만]\s*){0,2}"
            r"(?:아닌|아니다|아니고|아니며|아니지만|없(?:는|다|고|어|어서|지만)?|없이|말고|제외)",
            after,
        )
        is not None
    )


def _japanese_negates(before: str, after: str) -> bool:
    if re.search(r"(?:ない|なく|無し|なし)\s*$", before):
        return True
    return (
        re.match(
            r"\s*(?:(?:では|じゃ|で|は|が|を|に|と|へ|も|の|だけ)\s*)?"
            r"(?:ない|なく|ありません|なし|無し)",
            after,
        )
        is not None
    )


def _contains_hangul(value: str) -> bool:
    return re.search(r"[가-힣]", value) is not None


def _contains_japanese(value: str) -> bool:
    return re.search(r"[ぁ-ゖァ-ヺ一-龯]", value) is not None


def _contains_latin(value: str) -> bool:
    return re.search(r"[A-Za-z0-9]", value) is not None


class StaticMockTagProvider:
    provider_name = "mock"

    def tags_for_panel(self, panel_id: str, beat: str, emotion: str) -> list[TagCandidate]:
        base_tags = [
            ("vertical webtoon panel", 0.99),
            ("cinematic composition", 0.88),
            ("dramatic lighting", 0.8),
            (emotion, 0.72),
        ]
        keyword_tags = [
            (("비", "빗", "폭풍"), "rain", 0.86),
            (("괴물", "그림자", "monster"), "shadow creature", 0.82),
            (("전차", "정류장"), "tram stop", 0.85),
            (("도서관", "서가", "책"), "library", 0.84),
            (("열쇠",), "silver key", 0.82),
            (("별", "천문도"), "starlight", 0.82),
            (("지하철", "승강장", "플랫폼"), "subway station", 0.84),
            (("사탕",), "glowing candy", 0.8),
            (("바닷가", "파도", "방파제"), "winter seaside", 0.84),
            (("등대",), "lighthouse", 0.84),
            (("엽서", "우체통"), "postcard", 0.8),
            (("우산",), "umbrella", 0.8),
            (("문구점", "잉크"), "stationery shop", 0.8),
        ]
        for keywords, tag, confidence in keyword_tags:
            if any(keyword in beat for keyword in keywords):
                base_tags.append((tag, confidence))
        return [
            TagCandidate(
                tag=tag,
                source="static-mock",
                confidence=confidence,
                provenance={"panel_id": panel_id, "provider": self.provider_name},
            )
            for tag, confidence in base_tags
        ]


class LocalDanbooruTagProvider:
    provider_name = "local"

    def __init__(
        self,
        compiler: CanonicalTagCompiler | None = None,
        suggestion_provider_name: str | None = None,
        extra_extractors: list[CandidateExtractor] | None = None,
    ) -> None:
        self.compiler = compiler or CanonicalTagCompiler.from_default_lexicon()
        self.pipeline = SourceTextTagPipeline(
            self.compiler,
            extractors=[self.compiler.alias_extractor, *(extra_extractors or [])],
            fail_on_extractor_error=bool(extra_extractors),
        )
        self.provider_name = suggestion_provider_name or self.provider_name

    def tags_for_panel(self, panel_id: str, beat: str, emotion: str) -> list[TagCandidate]:
        compiled = self.pipeline.compile_source_text(
            panel_id=panel_id,
            provider=self.provider_name,
            source_text=f"{emotion}\n{beat}",
            base_candidates=[
                "vertical webtoon panel",
                "cinematic composition",
                "dramatic lighting",
            ],
            evidence={"beat": beat, "emotion": emotion},
        )
        return compiled.positive


StaticTagProvider = StaticMockTagProvider
