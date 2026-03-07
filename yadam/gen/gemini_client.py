# yadam/gen/gemini_client.py
import base64
from pathlib import Path
from google import genai
from google.genai import types
from yadam.gen.image_client import ImageClient, ImageGenRequest, ImageGenResponse
from yadam.core.errors import GenError, ErrorKind


def _classify_genai_error(msg: str) -> ErrorKind:
    s = (msg or "").lower()
    if any(x in s for x in ["429", "503", "deadline", "timeout", "temporar", "unavailable", "rate limit"]):
        return ErrorKind.TRANSIENT
    if any(x in s for x in ["policy", "safety", "blocked", "rai", "prohibited"]):
        return ErrorKind.POLICY
    if any(x in s for x in ["permission", "unauthorized", "forbidden", "auth"]):
        return ErrorKind.FATAL
    return ErrorKind.INVALID


def _to_bytes(data: object) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, str):
        # 일부 응답은 base64 문자열일 수 있으므로 방어적으로 디코딩한다.
        return base64.b64decode(data)
    return b""


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "image/jpeg"


class VertexImagenClient(ImageClient):
    def __init__(self, model: str = "imagen-4.0-generate-001") -> None:
        self.client = genai.Client()   # Vertex 모드: 환경변수 + 서비스계정
        self.model = model

    def generate(self, req: ImageGenRequest) -> ImageGenResponse:
        img = None
        try:
            aspect = req.aspect_ratio or "16:9"

            def _make_cfg(include_negative_prompt: bool) -> types.GenerateImagesConfig:
                kwargs = dict(
                    number_of_images=1,
                    aspect_ratio=aspect,
                    include_rai_reason=True,
                    include_safety_attributes=True,
                    output_mime_type="image/jpeg",
                )
                if include_negative_prompt:
                    kwargs["negative_prompt"] = (
                        "문자, 글자, 문장, 자막, 말풍선, 대사, 캡션, 표지 글씨, 패널 텍스트, "
                        "워터마크, 로고, 간판 글씨, 영어 문장"
                    )
                return types.GenerateImagesConfig(**kwargs)

            try:
                resp = self.client.models.generate_images(
                    model=self.model,
                    prompt=req.prompt,
                    config=_make_cfg(include_negative_prompt=True),
                )
            except Exception as e:
                msg = str(e)
                if "negative_prompt parameter is not supported" not in msg.lower():
                    raise
                resp = self.client.models.generate_images(
                    model=self.model,
                    prompt=req.prompt,
                    config=_make_cfg(include_negative_prompt=False),
                )

            gen = getattr(resp, "generated_images", None) or []
            if not gen:
                raise GenError(ErrorKind.INVALID, "EMPTY_GENERATED_IMAGES", "generated_images가 비어 있습니다.")

            gi = gen[0]
            img = gi.image

            b = getattr(img, "image_bytes", None)
            if not b:
                # gcs_uri만 있고 bytes가 없는 케이스 방어
                raise GenError(ErrorKind.INVALID, "EMPTY_IMAGE_BYTES", "image_bytes가 비어 있습니다.")

            mime = getattr(img, "mime_type", None) or "image/jpeg"
            return ImageGenResponse(image_bytes=b, mime_type=mime)

        except GenError:
            raise
        except Exception as e:
            msg = str(e)
            kind = _classify_genai_error(msg)
            raise GenError(kind, "GENAI_ERROR", msg)


class GeminiFlashImageClient(ImageClient):
    def __init__(self, model: str = "gemini-2.5-flash-image") -> None:
        self.client = genai.Client()
        self.model = model

    def generate(self, req: ImageGenRequest) -> ImageGenResponse:
        try:
            prompt = req.prompt
            if req.aspect_ratio:
                prompt += f"\n\n[output constraint] aspect ratio: {req.aspect_ratio}"
            ref_paths = []
            for raw in req.reference_image_paths[:4]:
                p = Path(raw)
                if p.exists() and p.is_file():
                    ref_paths.append(p)
            if ref_paths:
                prompt += (
                    "\n\n[reference constraint] Preserve core identity anchors from attached references. "
                    "If character references are present, keep face/hairstyle/clothing silhouette consistent. "
                    "If place references are present, preserve environment mood/layout cues without copying text."
                )

            parts = []
            for p in ref_paths:
                parts.append(
                    types.Part.from_bytes(
                        data=p.read_bytes(),
                        mime_type=_guess_mime(p),
                    )
                )
            parts.append(types.Part(text=prompt))

            resp = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(
                        role="user",
                        parts=parts,
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=req.aspect_ratio or "16:9",
                    ),
                ),
            )

            cands = getattr(resp, "candidates", None) or []
            for c in cands:
                content = getattr(c, "content", None)
                parts = getattr(content, "parts", None) or []
                for p in parts:
                    inline = getattr(p, "inline_data", None)
                    if not inline:
                        continue
                    b = _to_bytes(getattr(inline, "data", None))
                    if b:
                        mime = getattr(inline, "mime_type", None) or "image/png"
                        return ImageGenResponse(image_bytes=b, mime_type=mime)

            raise GenError(ErrorKind.INVALID, "EMPTY_IMAGE_BYTES", "Gemini Flash Image 응답에 image data가 없습니다.")

        except GenError:
            raise
        except Exception as e:
            msg = str(e)
            kind = _classify_genai_error(msg)
            raise GenError(kind, "GENAI_ERROR", msg)
