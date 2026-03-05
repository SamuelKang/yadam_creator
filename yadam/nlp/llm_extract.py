# yadam/nlp/llm_extract.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from google import genai
from google.genai import types


# --------- Structured Output (Pydantic Schema) ---------
class LLMCharacter(BaseModel):
    name_canonical: str
    aliases: List[str] = Field(default_factory=list)

    # 기존
    role: str = Field(default="조연")
    traits: List[str] = Field(default_factory=list)
    visual_anchors: List[str] = Field(default_factory=list)

    # 기존(이미 추가되어 있던 것)
    gender: str = Field(default="불명", description="남/여/불명")
    age_stage: str = Field(default="불명", description="유아/아동/청소년/청년/중년/노년/불명")
    age_hint: str = Field(default="", description="예: 열 살 남짓, 스무 살 무렵 등(근거 문구)")
    variants: List[str] = Field(default_factory=list, description="성장 서사 시 예: ['아동','청년']")

    # ✅ 추가: 궁중/민간 구분 + 계급/재산 + 복장 티어/앵커
    context: str = Field(
        default="민간",
        description="인물이 주로 속하는 맥락/공간: 궁중/민간/관아/사찰/장터/기타"
    )
    court_role: str = Field(
        default="",
        description="context가 궁중일 때만: 왕/왕비/세자/후궁/궁녀/내관/문신/무관/호위 등"
    )
    social_class: str = Field(
        default="불명",
        description="민간 기준 신분: 양반/중인/상민/천민/승려/무속/불명"
    )
    wealth_level: str = Field(
        default="불명",
        description="경제력: 부유/보통/빈곤/불명"
    )
    wardrobe_tier: str = Field(
        default="T2",
        description="복장 등급: T3(상류)/T2(중류)/T1(하류)"
    )
    wardrobe_anchors: List[str] = Field(
        default_factory=list,
        description="복식/소품 앵커 3~6개(짧게). 궁중이면 궁중 관복/궁녀복 등 규격 반영."
    )


class LLMPlace(BaseModel):
    name_canonical: str = Field(..., description="대본에 근거한 대표 장소명(정규화)")
    aliases: List[str] = Field(default_factory=list, description="대본에 등장하는 장소 표기 변형")
    visual_anchors: List[str] = Field(default_factory=list, description="이미지 일관성을 위한 분위기/시간/날씨/구조 앵커(짧게)")


class LLMSceneTag(BaseModel):
    scene_id: int
    characters: List[str] = Field(default_factory=list, description="name_canonical 목록")
    places: List[str] = Field(default_factory=list, description="place name_canonical 목록")

    character_instances: List[Dict[str, str]] = Field(
        default_factory=list,
        description="예: [{'name':'서윤','variant':'아동'}]"
    )


class LLMExtractionResult(BaseModel):
    characters: List[LLMCharacter] = Field(default_factory=list)
    places: List[LLMPlace] = Field(default_factory=list)
    scene_tags: List[LLMSceneTag] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list, description="불확실/가정/주의 사항(짧게)")


# --------- Extractor ---------
@dataclass
class LLMExtractorConfig:
    model: str = "gemini-2.5-flash"
    max_script_chars: int = 12000
    temperature: float = 0.1


class LLMEntityExtractor:
    """
    Vertex 모드(환경변수 GOOGLE_GENAI_USE_VERTEXAI=True + ADC)에서 동작.
    Structured Output(JSON)로 캐릭터/장소/장면태깅 결과를 얻는다.
    """
    def __init__(self, cfg: Optional[LLMExtractorConfig] = None) -> None:
        self.cfg = cfg or LLMExtractorConfig()
        self.client = genai.Client()

    def extract(
        self,
        *,
        era_profile: str,
        style_profile: str,
        script_text: str,
        scenes: List[Dict[str, Any]],
        seed_char_candidates: List[str],
        seed_place_candidates: List[str],
    ) -> Dict[str, Any]:
        script_trim = script_text[: self.cfg.max_script_chars]

        scene_brief = [
            {"scene_id": int(s["id"]), "text": str(s.get("text", ""))[:600]}
            for s in scenes
        ]

        system = (
            "너는 한국어 대본에서 등장인물/장소를 추출하고 장면별로 태깅하는 분석기다. "
            "반드시 제공된 대본 내용에만 근거한다. 대본에 없는 인물/장소를 만들어내지 않는다. "
            "출력은 스키마에 맞는 JSON만 반환한다. 설명 문장, 코드블록, 여분 텍스트를 출력하지 않는다."
        )

        user = {
            "작업": "인물/장소 추출 및 정규화 + 장면별 태깅",
            "시대프로필": era_profile,
            "화풍프로필": style_profile,
            "대본(일부)": script_trim,
            "장면목록": scene_brief,
            "규칙기반_인물후보": seed_char_candidates,
            "규칙기반_장소후보": seed_place_candidates,
            "요구사항": [
                "인물 name_canonical은 사람이 읽을 수 있는 대표 명칭(예: 설화, 강무, 도윤, 김도령). 단순 역할명(아씨, 도령, 마님, 아들, 딸, 어머니)만으로 끝내지 말고, 대본에 실명이 있으면 실명을 canonical로 삼는다.",
                "같은 인물이 실명과 역할명/호칭으로 함께 등장하면 하나의 canonical 인물로 합치고, 역할명/호칭은 aliases로 보낸다.",
                "실명이 전혀 없을 때만 역할명(예: 노승, 사또, 할멈)을 canonical로 사용한다.",
                "aliases에는 대본에서 확인된 다른 표기만 넣는다. 존칭/호칭/관계명은 가능한 alias로 흡수한다.",
                "장면 태깅(scene_tags)에서 characters/places는 반드시 name_canonical을 사용한다.",
                "불확실하면 notes에 짧게 남긴다.",

                "각 인물에 대해 gender(남/여/불명)와 age_stage(유아/아동/청소년/청년/중년/노년/불명)를 가능한 범위에서 채운다.",
                "근거가 약하면 불명으로 두되, age_hint에 대본 근거 문구(있으면)를 넣는다.",
                "성장 서사가 명확한 주인공은 variants에 최소 2개(예: 아동, 청년/성인)를 넣는다.",
                "장면 태깅(scene_tags)에서 성장 단계가 구분되면 character_instances에 {'name':name_canonical,'variant':variants 중 하나}를 채운다.",

                # ✅ 궁중/민간 + 복식 규칙
                "각 인물에 대해 context(궁중/민간/관아/사찰/장터/기타)를 추출한다. 단서가 없으면 민간으로 둔다.",
                "context가 '궁중'이면 court_role(왕/왕비/세자/후궁/궁녀/내관/문신/무관/호위 등)를 가능한 범위에서 채운다.",
                "각 인물에 대해 social_class(양반/중인/상민/천민/승려/무속/불명)와 wealth_level(부유/보통/빈곤/불명)을 추정한다(근거 없으면 불명).",
                "각 인물에 대해 wardrobe_tier를 T3(상류)/T2(중류)/T1(하류) 중 하나로 정한다. 몰락 양반 등은 양반이더라도 T1이 될 수 있다.",
                "각 인물에 대해 wardrobe_anchors를 3~6개 제시한다(복식/소품 중심, 짧게).",
                "우선순위: context가 '궁중'이면 social_class/wealth_level보다 궁중 복식 규격이 우선이다(예: 궁중 문신/무관 관복/관모, 궁녀 당의/치마 등).",
                "과장 금지: 금/보석 과다, 판타지 의상, 과도한 장식은 피한다. 시대감 유지.",
                "성장 서사가 있는 인물은 아예 다른 캐릭터로 쪼개지 말고 하나의 canonical 인물 아래 variants(예: 유아, 아동, 청년)로 유지한다.",
            ],
        }

        resp = self.client.models.generate_content(
            model=self.cfg.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=system + "\n\n" + json.dumps(user, ensure_ascii=False))]
                ),
            ],
            config=types.GenerateContentConfig(
                temperature=self.cfg.temperature,
                response_mime_type="application/json",
                response_schema=LLMExtractionResult,
            ),
        )

        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("LLM 응답 텍스트(resp.text)가 비어 있습니다.")

        data = json.loads(text)
        validated = LLMExtractionResult.model_validate(data)
        return validated.model_dump()
