from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def model_to_plain(model: BaseModel) -> dict:
    return model.model_dump(mode="json")


def dump_model(model: BaseModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = model_to_plain(model)
    if path.suffix == ".json":
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return model_type.model_validate(data)
