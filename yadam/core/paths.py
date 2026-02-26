# yadam/core/paths.py
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    base_dir: Path
    characters_dir: Path
    places_dir: Path
    clips_dir: Path
    out_dir: Path
    log_dir: Path

    @staticmethod
    def from_base(base_dir: str) -> "ProjectPaths":
        b = Path(base_dir).resolve()
        return ProjectPaths(
            base_dir=b,
            characters_dir=b / "characters",
            places_dir=b / "places",
            clips_dir=b / "clips",
            out_dir=b / "out",
            log_dir=b / "logs",
        )

    def ensure(self) -> None:
        for p in [
            self.characters_dir,
            self.places_dir,
            self.clips_dir,
            self.out_dir,
            self.log_dir,
        ]:
            os.makedirs(p, exist_ok=True)