# yadam/gen/image_client.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

from yadam.core.errors import GenError


@dataclass(frozen=True)
class ImageGenRequest:
    prompt: str
    width: int = 1280
    height: int = 720
    seed: Optional[int] = None
    aspect_ratio: Optional[str] = None   # ✅ 추가 (예: "16:9", "3:4", "1:1")ㄴ
    reference_image_paths: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ImageGenResponse:
    image_bytes: bytes
    mime_type: str  # "image/jpeg" etc.


class ImageClient(ABC):
    @abstractmethod
    def generate(self, req: ImageGenRequest) -> ImageGenResponse:
        """
        성공 시 bytes 반환.
        실패 시 GenError(kind=TRANSIENT/POLICY/INVALID/FATAL) raise.
        """
        raise NotImplementedError
