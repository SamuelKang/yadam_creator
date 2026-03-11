from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from google import genai
from google.genai import types
from yadam.model_defaults import DEFAULT_TEXT_LLM_MODEL
from yadam.nlp._llm_timeout import call_with_timeout


class LLMCharBinding(BaseModel):
    character: str
    variant: str = ""


class LLMVariantOverride(BaseModel):
    character: str
    variant: str = ""
    scenes: List[int] = Field(default_factory=list)
    chapter_title: str = ""


class LLMSceneBinding(BaseModel):
    scenes: List[int] = Field(default_factory=list)
    chapter_title: str = ""
    mode: str = "replace"
    characters: List[LLMCharBinding] = Field(default_factory=list)
    places: List[str] = Field(default_factory=list)


class LLMSceneBindingResult(BaseModel):
    variant_overrides: List[LLMVariantOverride] = Field(default_factory=list)
    scene_bindings: List[LLMSceneBinding] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


@dataclass
class LLMSceneBindingConfig:
    model: str = DEFAULT_TEXT_LLM_MODEL
    temperature: float = 0.1
    max_script_chars: int = 12000
    max_scenes: int = 220
    timeout_sec: float = 90.0


class LLMSceneBindingPlanner:
    """
    scene별 character/place/variant 일관성 규칙을 LLM으로 생성한다.
    - 실행 실패 시 호출 측에서 조용히 폴백할 수 있도록 예외를 그대로 올린다.
    """

    def __init__(self, cfg: Optional[LLMSceneBindingConfig] = None) -> None:
        self.cfg = cfg or LLMSceneBindingConfig()
        self.client = genai.Client()

    def _build_prompt(
        self,
        *,
        story_id: str,
        script_text: str,
        scenes: List[Dict[str, Any]],
        characters: List[Dict[str, Any]],
        places: List[Dict[str, Any]],
    ) -> str:
        payload = {
            "story_id": story_id,
            "script_excerpt": (script_text or "")[: self.cfg.max_script_chars],
            "scenes": scenes[: self.cfg.max_scenes],
            "characters": characters,
            "places": places,
            "requirements": [
                "Generate only high-confidence consistency rules.",
                "Prefer short contiguous scene ranges when possible.",
                "Do not invent new character/place names; use provided names only.",
                "For growth stories, propose variant_overrides for clear age-phase zones.",
                "For continuity drift zones, propose scene_bindings with mode='replace' and explicit character/place locks.",
                "Keep output minimal: only rules that reduce identity/location drift.",
            ],
            "output_format": {
                "variant_overrides": [
                    {
                        "character": "name",
                        "variant": "아동|청소년|청년|중년|노년|''",
                        "scenes": [1, 2, 3],
                        "chapter_title": "",
                    }
                ],
                "scene_bindings": [
                    {
                        "scenes": [10, 11],
                        "chapter_title": "",
                        "mode": "replace",
                        "characters": [{"character": "name", "variant": ""}],
                        "places": ["place-name"],
                    }
                ],
            },
        }
        return (
            "You are a continuity rule planner for storyboard image generation. "
            "Return strict JSON only.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    def plan(
        self,
        *,
        story_id: str,
        script_text: str,
        scenes: List[Dict[str, Any]],
        characters: List[Dict[str, Any]],
        places: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(
            story_id=story_id,
            script_text=script_text,
            scenes=scenes,
            characters=characters,
            places=places,
        )
        resp = call_with_timeout(
            lambda: self.client.models.generate_content(
                model=self.cfg.model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=self.cfg.temperature,
                    response_mime_type="application/json",
                    response_schema=LLMSceneBindingResult,
                ),
            ),
            self.cfg.timeout_sec,
        )
        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("LLM scene binding response is empty")
        data = json.loads(text)
        validated = LLMSceneBindingResult.model_validate(data)
        return validated.model_dump()
