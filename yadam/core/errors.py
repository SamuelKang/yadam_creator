# yadam/core/errors.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class ErrorKind(str, Enum):
    TRANSIENT = "transient"      # 429/503/timeout 등 재시도 가치 있음
    POLICY = "policy"            # safety/blocked 등 프롬프트 리라이트 대상
    INVALID = "invalid"          # 입력/파라미터 문제
    FATAL = "fatal"              # 파일시스템/권한/필수 리소스 없음 등


@dataclass
class GenError(Exception):
    kind: ErrorKind
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.code}: {self.message}"