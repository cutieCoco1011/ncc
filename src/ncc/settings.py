from __future__ import annotations

import os
from dataclasses import dataclass

from .models import ProviderKind


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    provider: ProviderKind
    configured: bool
    credential_env: str | None = None
    disclosure: str = ""

    def public_status(self) -> dict[str, str | bool | None]:
        return {
            "name": self.name,
            "provider": self.provider.value,
            "configured": self.configured,
            "credential_env": self.credential_env,
            "disclosure": self.disclosure,
        }


@dataclass(frozen=True)
class AppSettings:
    projects_dir: str
    llm: ProviderConfig
    tag: ProviderConfig
    image: ProviderConfig
    secret_values: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "AppSettings":
        llm_provider = os.environ.get("NCC_LLM_PROVIDER", "mock").lower()
        image_provider = os.environ.get("NCC_IMAGE_PROVIDER", "mock").lower()
        tag_provider = os.environ.get("NCC_TAG_PROVIDER", "mock").lower()

        secrets: list[str] = []
        llm = _llm_config(llm_provider, secrets)
        image = _image_config(image_provider, secrets)
        tag = _tag_config(tag_provider, secrets)

        return cls(
            projects_dir=os.environ.get("NCC_PROJECTS_DIR", "ncc-projects"),
            llm=llm,
            tag=tag,
            image=image,
            secret_values=tuple(value for value in secrets if value),
        )

    def public_provider_status(self) -> dict[str, dict[str, str | bool | None]]:
        return {
            "llm": self.llm.public_status(),
            "tag": self.tag.public_status(),
            "image": self.image.public_status(),
        }


def _llm_config(provider: str, secrets: list[str]) -> ProviderConfig:
    if provider in {"", "mock"}:
        return ProviderConfig(
            name="llm",
            provider=ProviderKind.MOCK,
            configured=True,
            disclosure="Mock LLM runs locally and sends no source text to external providers.",
        )
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        secrets.append(key)
        return ProviderConfig(
            name="llm",
            provider=ProviderKind.OPENAI if key else ProviderKind.NOT_CONFIGURED,
            configured=bool(key),
            credential_env="OPENAI_API_KEY",
            disclosure="Story source text may be sent to OpenAI when this provider is selected.",
        )
    if provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY", "")
        secrets.append(key)
        return ProviderConfig(
            name="llm",
            provider=ProviderKind.OPENROUTER if key else ProviderKind.NOT_CONFIGURED,
            configured=bool(key),
            credential_env="OPENROUTER_API_KEY",
            disclosure="Story source text may be sent to OpenRouter when this provider is selected.",
        )
    return ProviderConfig(
        name="llm",
        provider=ProviderKind.NOT_CONFIGURED,
        configured=False,
        credential_env="NCC_LLM_PROVIDER",
        disclosure=f"Unknown LLM provider '{provider}' is not configured.",
    )


def _image_config(provider: str, secrets: list[str]) -> ProviderConfig:
    if provider in {"", "mock"}:
        return ProviderConfig(
            name="image",
            provider=ProviderKind.MOCK,
            configured=True,
            disclosure="Mock image generation runs locally and sends no prompts externally.",
        )
    if provider == "novelai":
        key = os.environ.get("NOVELAI_API_TOKEN", "")
        secrets.append(key)
        return ProviderConfig(
            name="image",
            provider=ProviderKind.NOVELAI if key else ProviderKind.NOT_CONFIGURED,
            configured=bool(key),
            credential_env="NOVELAI_API_TOKEN",
            disclosure="Prompts, settings, and references may be sent to NovelAI when this provider is selected.",
        )
    return ProviderConfig(
        name="image",
        provider=ProviderKind.NOT_CONFIGURED,
        configured=False,
        credential_env="NCC_IMAGE_PROVIDER",
        disclosure=f"Unknown image provider '{provider}' is not configured.",
    )


def _tag_config(provider: str, secrets: list[str]) -> ProviderConfig:
    if provider in {"", "mock"}:
        return ProviderConfig(
            name="tag",
            provider=ProviderKind.MOCK,
            configured=True,
            disclosure="Mock tag generation runs locally.",
        )
    if provider == "local":
        return ProviderConfig(
            name="tag",
            provider=ProviderKind.LOCAL,
            configured=True,
            disclosure="Local Danbooru compiler runs on this machine.",
        )
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        secrets.append(key)
        return ProviderConfig(
            name="tag",
            provider=ProviderKind.OPENAI if key else ProviderKind.NOT_CONFIGURED,
            configured=bool(key),
            credential_env="OPENAI_API_KEY",
            disclosure="openai may suggest tags, but final prompts are produced by the local Danbooru compiler.",
        )
    if provider == "deepseek":
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        secrets.append(key)
        return ProviderConfig(
            name="tag",
            provider=ProviderKind.DEEPSEEK if key else ProviderKind.NOT_CONFIGURED,
            configured=bool(key),
            credential_env="DEEPSEEK_API_KEY",
            disclosure="deepseek may suggest tags, but final prompts are produced by the local Danbooru compiler.",
        )
    if provider == "mimo":
        key = os.environ.get("MIMO_API_KEY", "")
        secrets.append(key)
        return ProviderConfig(
            name="tag",
            provider=ProviderKind.MIMO if key else ProviderKind.NOT_CONFIGURED,
            configured=bool(key),
            credential_env="MIMO_API_KEY",
            disclosure="mimo may suggest tags, but final prompts are produced by the local Danbooru compiler.",
        )
    return ProviderConfig(
        name="tag",
        provider=ProviderKind.NOT_CONFIGURED,
        configured=False,
        credential_env="NCC_TAG_PROVIDER",
        disclosure=f"Unknown tag provider '{provider}' is not configured.",
    )
