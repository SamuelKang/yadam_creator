# yadam/prompts/profiles.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


@dataclass(frozen=True)
class EraProfile:
    name: str
    prefix: str
    safety: str


@dataclass(frozen=True)
class StyleProfile:
    name: str
    suffix: str


def load_profiles_yaml(path: str) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml 미설치: pip install pyyaml")
    p = Path(path)
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def get_era(profiles: Dict[str, Any], era_name: str) -> EraProfile:
    era = profiles["era_profiles"][era_name]
    return EraProfile(name=era_name, prefix=era["prefix"], safety=era["safety"])


def get_style(profiles: Dict[str, Any], style_name: str) -> StyleProfile:
    st = profiles["style_profiles"][style_name]
    return StyleProfile(name=style_name, suffix=st["suffix"])