DEFAULT_TEXT_LLM_MODEL = "gemini-3-flash-preview"
DEFAULT_VERTEX_IMAGE_MODEL = "imagen-4.0-generate-001"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
DEFAULT_COMFY_MODEL = "z_image_turbo_bf16.safetensors"
DEFAULT_COMFY_WORKFLOW_ZIMAGE_TURBO = "yadam_api_z_image_turbo_placeholders.json"
DEFAULT_COMFY_WORKFLOW_SDXL_FAST = "yadam_api_sdxl_base_fast_placeholders.json"
DEFAULT_COMFY_WORKFLOW_FLUX_BASE = "yadam_api_flux_schnell_base_placeholders.json"

GEMINI_IMAGE_MODEL_FALLBACKS = {
    "gemini-3-flash-preview": DEFAULT_GEMINI_IMAGE_MODEL,
}


def resolve_gemini_image_model(model: str) -> tuple[str, str]:
    raw = (model or "").strip() or DEFAULT_GEMINI_IMAGE_MODEL
    fallback = GEMINI_IMAGE_MODEL_FALLBACKS.get(raw)
    if fallback:
        return fallback, raw
    return raw, ""
