# yadam/gen/placeholder.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageDraw, ImageFont


def make_error_image_bytes(text: str, width: int = 1280, height: int = 720) -> bytes:
    img = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # 폰트는 시스템 환경마다 다르므로 기본 폰트로
    msg = text[:800]
    draw.text((40, 40), msg, fill=(240, 240, 240))

    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()