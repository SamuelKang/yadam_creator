# yadam/nlp/llm_scene_prompt.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from google import genai
from google.genai import types


class LLMPrevSummary(BaseModel):
    scene_id: int = Field(..., description="이전 장면 scene id")
    shot: str = Field(default="", description="이전 장면 샷/카메라 힌트 요약")
    focus: str = Field(default="", description="이전 장면 행동/포커스 요약(짧게)")
    time: str = Field(default="", description="이전 장면 시간대(낮/밤/새벽/황혼/폭풍 등)")
    place: str = Field(default="", description="이전 장면 장소명")


class LLMSceneSummary(BaseModel):
    shot: str = Field(default="", description="이번 장면 shot 요약(짧게)")
    focus: str = Field(default="", description="이번 장면 focus 요약(짧게)")
    time: str = Field(default="", description="이번 장면 time 요약(짧게)")
    place: str = Field(default="", description="이번 장면 place 요약(짧게)")


class LLMScenePromptResult(BaseModel):
    prompt: str = Field(..., description="최종 이미지 생성 프롬프트(한 덩어리 문자열)")
    summary: LLMSceneSummary = Field(
        default_factory=LLMSceneSummary,
        description="다음 장면에 전달할 요약"
    )


@dataclass
class LLMScenePromptConfig:
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_scene_chars: int = 900  # scene_text 길이 제한


class LLMScenePromptBuilder:
    def __init__(self, cfg: Optional[LLMScenePromptConfig] = None) -> None:
        self.cfg = cfg or LLMScenePromptConfig()
        self.client = genai.Client()

    def build(
        self,
        *,
        era_profile: str,
        era_prefix: str,
        style_profile: str,
        scene_id: int,
        scene_text: str,
        place_name: Optional[str],
        place_anchors: List[str],
        characters: List[Dict[str, Any]],
        shot_hint: str,
        focus_hint: str,
        time_hint: str,
        prev_summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        txt = (scene_text or "").strip()
        if len(txt) > self.cfg.max_scene_chars:
            txt = txt[: self.cfg.max_scene_chars]
        rule_corpus = " ".join(
            [
                txt,
                place_name or "",
                " ".join(place_anchors or []),
                json.dumps(characters[:2], ensure_ascii=False),
            ]
        )

        system = (
            "너는 한국어 대본을 기반으로 '단일 장면(한 컷) 이미지 생성 프롬프트'를 작성하는 연출가다. "
            "반드시 대본 내용에 근거하고, 대본 문장을 그대로 길게 복사하지 말고 시각적 묘사로 변환한다. "
            "최종 프롬프트는 레퍼런스 보드에 바로 붙여 넣는 짧은 영어 연출문처럼 써라. "
            "첫 문장은 반드시 샷/카메라 연출로 시작하고, 장면 핵심 시각 정보만 남겨 shot-first로 압축하라. "
            "출력은 JSON 스키마에 맞게만 반환한다. 여분 설명/코드블록 금지."
        )

        rules = [
            "shot_hint, focus_hint, time_hint를 반드시 반영하고, prev_summaries가 있으면 같은 shot/focus/time 조합을 그대로 반복하지 말고 변주한다.",
            "최종 prompt는 짧고 직접적인 영어 문장 3~6개 정도로 작성하고, 첫 문장은 반드시 카메라/샷 지시(예: Wide shot, Over-the-shoulder shot, Extreme close-up, High angle)로 시작한다.",
            "장면 핵심 시각 정보만 남긴다: 주인공 1~2명, 핵심 행동 1개, 배경 1개, 감정/분위기 1개. 장황한 boilerplate, 설명문, 중복 수식은 줄인다.",
            "같은 인물(name/variant)은 장면 간 외형 일관성을 유지한다(성별/연령대/얼굴 인상/헤어/복식 핵심 앵커 유지). 인물 입력에 없는 새 헤어스타일/머리장식/복식 컨셉을 임의로 추가하지 않는다.",
            "대본 문장을 그대로 복사하지 말고, 장면 묘사로 재구성한다. 시대지시가 있으면 조선시대 의복/소품/건축/분위기를 유지한다.",
            "직접 대사나 인용부호(\"...\", '...')를 prompt에 쓰지 않는다. 등장인물의 말은 입 모양, 손짓, 표정, 긴장감, 권위적인 태도 같은 시각적 행동으로만 번역한다.",
            "shouting \"...\" 또는 saying \"...\" 같은 직접 발화문 대신 mouth open in a forceful shout, appears to be announcing his authority, urgent expression, lips parted as if calling out 같은 행동 묘사를 사용한다.",
            "반드시 2D Korean webtoon/manhwa rendering으로 작성한다: ink lineart, full-color cel shading, bold outlines, simplified surfaces, comic-style shading.",
            "사진/실사/필름스틸/DSLR/렌즈/보케/심도(DOF)/blur 같은 촬영 효과 표현은 피하고, 필요하면 배경 단순화, 실루엣 처리, 명암 대비, 전경 프레이밍으로 치환한다.",
            "대본의 비유/은유는 초현실 변형이 아니라 자세/행동/표정으로 번역한다. 형식은 단일 장면 일러스트(한 컷), 16:9, text/speech bubbles/captions/watermarks/logos 없음.",
        ]

        if "포졸" in rule_corpus:
            rules.extend([
                "인물/앵커에 '포졸'이 있으면 현대 경찰로 해석하지 말고, 조선시대 관아 소속 전통 포졸로 묘사한다.",
                "포졸의 영문화는 police officer가 아니라 traditional Joseon constable, magistrate's constable, government runner 같은 역사적 표현을 우선한다.",
                "포졸은 넓은 양반 갓이 아닌 낮고 투박한 조선 포졸용 관모, 포졸복, 행전, 짚신, 목봉/곤장/횃불 같은 전통 집행 도구를 사용한다.",
                "포졸에게 칼, 검집, 무관 장식 허리띠, 양반 도포 차림을 주지 않는다.",
                "포졸은 현대 제복/패치/배지/경찰모자/진압봉도 사용하지 않는다.",
            ])

        if "주먹밥" in rule_corpus:
            rules.extend([
                "대본이나 소품에 '주먹밥'이 있으면 일본식 오니기리로 해석하지 말고, 조선시대의 손으로 쥔 둥글고 투박한 밥덩이로 묘사한다.",
                "주먹밥은 삼각형이 아니며, 김 띠나 일본식 포장 없이 헝겊/소반/손 위에 놓인 소박한 형태를 우선한다.",
            ])

        if any(token in rule_corpus for token in ("아궁이", "온돌", "헛간", "오두막", "방", "부엌")):
            rules.extend([
                "조선시대 주거 실내는 온돌 구조를 우선한다. 일반 생활방 안에 노출된 벽난로/실내 화덕/현대식 fireplace를 두지 않는다.",
                "아궁이가 필요하면 부엌 쪽 또는 방 바깥쪽 난방 구조로 처리하고, 실내 생활공간에서는 식은 재, 구들 온기, 부엌 쪽 기척처럼 간접적으로 표현한다.",
                "화로가 명시되지 않은 한 방 한가운데의 노출 화구를 만들지 않는다.",
            ])

        user = {
            "작업": "장면 이미지 프롬프트 생성",
            "scene_id": scene_id,
            "시대프로필": era_profile,
            "시대지시": (era_prefix or "").strip(),
            "화풍프로필": style_profile,
            "장소": place_name or "",
            "장소_앵커": place_anchors[:6],
            "인물": characters[:2],  # 0~2명만
            "scene_text": txt,

            # 변주 입력
            "shot_hint": shot_hint,
            "focus_hint": focus_hint,
            "time_hint": time_hint,

            # 이전 요약(최근 1~2개) - 반복 방지용
            "prev_summaries": prev_summaries[-2:],

            "규칙": rules,
            "출력_형식": {
                "prompt": "이미지 생성 프롬프트 문자열(여러 줄 가능)",
                "summary": {
                    "shot": "이번 장면 shot 요약(짧게)",
                    "focus": "이번 장면 focus 요약(짧게)",
                    "time": "이번 장면 time 요약(짧게)",
                    "place": "이번 장면 place 요약(짧게)",
                },
            },
        }

        resp = self.client.models.generate_content(
            model=self.cfg.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=system + "\n\n" + json.dumps(user, ensure_ascii=False))]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=self.cfg.temperature,
                response_mime_type="application/json",
                response_schema=LLMScenePromptResult,
            ),
        )

        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("LLM scene prompt 응답(resp.text)이 비어 있습니다.")

        data = json.loads(text)
        validated = LLMScenePromptResult.model_validate(data)
        return validated.model_dump()
