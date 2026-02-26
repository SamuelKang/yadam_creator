# yadam/nlp/llm_prompt_rewrite.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class PromptRewriteResult(BaseModel):
    prompt: str = Field(..., description="정책 위반 가능성을 줄인 수정된 프롬프트")


@dataclass
class LLMPromptRewriteConfig:
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_prompt_chars: int = 3500


class LLMPromptRewriter:
    """
    정책 위반 가능성이 있는 이미지 프롬프트를 LLM으로 완화/우회 재작성.
    - 입력: original_prompt, error_message
    - 출력: {"prompt": "..."} JSON
    """

    def __init__(self, cfg: LLMPromptRewriteConfig | None = None) -> None:
        self.cfg = cfg or LLMPromptRewriteConfig()
        self.client = genai.Client()

    def rewrite(self, original_prompt: str, error_message: str) -> Dict[str, Any]:
        op = (original_prompt or "").strip()
        if len(op) > self.cfg.max_prompt_chars:
            op = op[: self.cfg.max_prompt_chars].rstrip() + "..."

        payload = {
            "original_prompt": op,
            "error_message": (error_message or "").strip(),
            "goal": "정책 위반 소지(안전/금지 카테고리/민감 요소 등)를 낮추면서도 장면 의도를 유지",
            "rules": [
                "출력은 JSON으로만: {\"prompt\": \"...\"}",
                "원문 의도를 유지하되, 폭력/유혈/성적/아동 관련 민감 묘사/자해/혐오/불법행위 등 의심 요소를 완화",
                "구체적 신체 손상/위협 묘사는 분위기/표정/조명으로 대체",
                "인물은 가상 인물임을 유지",
            ],
        }

        instruction = (
            "너는 이미지 생성 프롬프트의 정책 리라이터다.\n"
            "아래 INPUT_JSON의 original_prompt가 이미지 생성 정책에 걸린 것으로 보인다.\n"
            "error_message를 참고해, 정책 위반 소지를 낮추도록 프롬프트를 수정하라.\n"
            "출력은 반드시 JSON {\"prompt\":\"...\"} 하나만 반환하라.\n"
        )

        user_text = instruction + "\n[INPUT_JSON]\n" + json.dumps(payload, ensure_ascii=False)

        resp = self.client.models.generate_content(
            model=self.cfg.model,
            contents=[user_text],
            config=types.GenerateContentConfig(
                temperature=self.cfg.temperature,
                response_mime_type="application/json",
                response_schema=PromptRewriteResult,
            ),
        )

        parsed = getattr(resp, "parsed", None)
        if parsed and getattr(parsed, "prompt", None):
            prompt = str(parsed.prompt).strip()
        else:
            text = getattr(resp, "text", None)
            if not text:
                raise RuntimeError("LLM rewriter returned empty response")
            obj = json.loads(text)
            prompt = str(obj.get("prompt", "")).strip()

        if not prompt:
            raise RuntimeError("LLM rewriter produced empty prompt")

        return {"prompt": prompt, "debug": {"model": self.cfg.model}}