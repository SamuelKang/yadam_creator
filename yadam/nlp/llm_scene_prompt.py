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

        system = (
            "너는 한국어 대본을 기반으로 '단일 장면(한 컷) 이미지 생성 프롬프트'를 작성하는 연출가다. "
            "반드시 대본 내용에 근거하고, 대본 문장을 그대로 길게 복사하지 말고 시각적 묘사로 변환한다. "
            "출력은 JSON 스키마에 맞게만 반환한다. 여분 설명/코드블록 금지."
        )

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

            "규칙": [
                # -----------------------------
                # 1) 변주 강제
                # -----------------------------
                "shot_hint는 반드시 반영한다(와이드/미디엄/클로즈업/오버숄더/하이앵글/로우앵글/인서트 등 구도 중심).",
                "focus_hint는 반드시 반영한다(행동/상태/시각적 초점 1개를 명확히).",
                "time_hint가 있으면 조명/톤/날씨에 반영한다.",

                # -----------------------------
                # 2) 반복 방지
                # -----------------------------
                "prev_summaries가 제공되면, 같은 shot/focus/time 조합을 그대로 반복하지 말고 변주한다.",
                "같은 인물(name/variant)은 장면 간 외형 일관성을 유지한다(성별/연령대/얼굴 인상/헤어/복식 핵심 앵커 유지).",
                "인물 입력에 없는 새 헤어스타일/머리장식/복식 컨셉을 임의로 추가하지 않는다.",
                "인물/앵커에 '포졸'이 있으면 현대 경찰로 해석하지 말고, 조선시대 관아 소속 전통 포졸로 묘사한다.",
                "포졸의 영문화는 police officer가 아니라 traditional Joseon constable, magistrate's constable, government runner 같은 역사적 표현을 우선한다.",
                "포졸은 넓은 양반 갓이 아닌 낮고 투박한 조선 포졸용 관모, 포졸복, 행전, 짚신, 목봉/곤장/횃불 같은 전통 집행 도구를 사용한다.",
                "포졸에게 칼, 검집, 무관 장식 허리띠, 양반 도포 차림을 주지 않는다.",
                "포졸은 현대 제복/패치/배지/경찰모자/진압봉도 사용하지 않는다.",

                # -----------------------------
                # 3) 대본 문장 복붙 금지
                # -----------------------------
                "대본 문장을 그대로 길게 복사하지 말고, 장면 묘사로 재구성한다(요약 + 시각화).",
                "시대지시가 제공되면 반드시 반영한다(예: 조선시대면 의복/소품/건축/분위기를 조선시대 맥락으로 유지).",

                # -----------------------------
                # 4) 웹툰 렌더링 강제 (실사 방지)
                # -----------------------------
                "반드시 2D 한국 웹툰/만화 렌더링으로 작성한다: 선화(ink lineart with full-color cel shading), 굵은 외곽선, 셀채색(cel shading), 면 분할, 만화식 음영.",
                "인물 피부, 머리카락, 옷, 바위, 나무, 실내 소품은 모두 '사진 질감'이 아니라 평면적이고 단순화된 만화식 표면으로 묘사한다.",
                "광원은 영화 촬영 조명처럼 설명하지 말고, 웹툰식 명암과 톤 분리로 설명한다. 빛은 단순한 면 처리와 색 대비로 표현한다.",
                "배경 디테일은 사실적 재질 묘사보다 선화와 색면 위주로 단순화하고, 인물 얼굴과 손은 만화식 비율과 선명한 윤곽선을 유지한다.",
                "얼굴은 배우 같은 실사 인상이 아니라 한국 웹툰/사극 만화풍 얼굴로 묘사한다. 피부 모공, 카메라 노이즈, 렌즈 느낌, 사실적 텍스처를 암시하지 않는다.",
                "사진/실사/필름스틸/DSLR/렌즈/보케/심도(DOF)/out-of-focus/blur 같은 '촬영 효과' 표현은 사용하지 말고, 웹툰식으로 대체한다.",

                # -----------------------------
                # 5) 촬영 효과 표현 치환 규칙 (중요)
                # -----------------------------
                "주제 강조가 필요하면 blur/out-of-focus/softly blurred 대신 다음으로 표현한다: '배경 디테일을 낮춘다', '배경은 단순한 실루엣/톤다운', '전경 프레이밍(부분 가림/크롭)', '명암 대비로 주제 분리'.",

                # -----------------------------
                # 6) 비유(은유) 시각화 규칙 (중요)
                # -----------------------------
                "대본의 비유/은유(예: 나뭇가지처럼 위태롭다, 바람에 흔들린다)는 인물을 초현실적으로 변형하지 말고, 현실적인 연출로 번역한다.",
                "예: '나뭇가지처럼 위태' => '몹시 마른 체형 + 휘청이는 걸음 + 굽은 허리 + 얇은 손목/어깨 + 불안정한 자세'처럼 자세/행동/표정으로 표현한다.",
                "예: '바람에 흔들' => '옷자락/머리카락이 약하게 흩날림, 몸 중심이 흔들리는 순간 포즈'로 표현한다(나뭇가지/가지 묶음/가시 같은 소품 추가 금지).",

                # -----------------------------
                # 7) 출력 포맷 요구
                # -----------------------------
                "형식은 단일 장면 일러스트(한 컷), 16:9, Korean webtoon/manhwa, 텍스트/자막/말풍선/캡션/워터마크/로고 없음.",
                "장면은 과밀하게 만들지 말고, 장소 1 + 인물 0~2 + 포커스 1개 중심으로 구성한다.",
            ],
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
