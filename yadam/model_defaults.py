DEFAULT_TEXT_LLM_MODEL = "gemini-3-flash-preview"
DEFAULT_VERTEX_IMAGE_MODEL = "imagen-4.0-generate-001"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
DEFAULT_COMFY_MODEL = "sd_xl_base_1.0.safetensors"

GEMINI_IMAGE_MODEL_FALLBACKS = {
    "gemini-3-flash-preview": DEFAULT_GEMINI_IMAGE_MODEL,
}


def resolve_gemini_image_model(model: str) -> tuple[str, str]:
    raw = (model or "").strip() or DEFAULT_GEMINI_IMAGE_MODEL
    fallback = GEMINI_IMAGE_MODEL_FALLBACKS.get(raw)
    if fallback:
        return fallback, raw
    return raw, ""
