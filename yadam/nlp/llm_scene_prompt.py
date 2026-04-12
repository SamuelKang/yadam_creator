# yadam/nlp/llm_scene_prompt.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from google import genai
from google.genai import types
from yadam.model_defaults import DEFAULT_TEXT_LLM_MODEL
from yadam.nlp._llm_timeout import call_with_timeout


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
    model: str = DEFAULT_TEXT_LLM_MODEL
    temperature: float = 0.2
    max_scene_chars: int = 900  # scene_text 길이 제한
    timeout_sec: float = 90.0


class LLMScenePromptBuilder:
    def __init__(self, cfg: Optional[LLMScenePromptConfig] = None) -> None:
        self.cfg = cfg or LLMScenePromptConfig()
        self.client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if self.client is None:
            self.client = genai.Client()
        return self.client

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
            "정적인 기념사진 구도는 피하고, 행동 중간 동작(moment in action), 시선 방향, 손/몸의 제스처, 표정 변화를 명확히 넣어 연출 강도를 높인다.",
            "같은 장소의 초반 연속 장면이 이어질 때는 centered full-body standing pose를 반복하지 않는다. 최소 한 컷 이상은 손 디테일, 발동작, 측면 프로필, 로우앵글, 전경 프레이밍 등으로 구도를 꺾는다.",
            "같은 인물과 같은 장소가 인접 장면에 이어지면, 최소 2개 이상을 바꿔 변주한다: shot distance, angle, blocking, gaze direction, hand action, camera side. 같은 프레이밍과 같은 포즈를 연속 반복하지 않는다.",
            "연속 장면에서 장소가 바뀌지 않았다면 배경 핵심 앵커(화로 모양, 문 배치, 길 방향, 바위와 나무 위치)를 유지하고, 대본에 없는 새 실내/실외 전환을 만들지 않는다.",
            "표정 지시는 반드시 포함한다(긴장/분노/안도/결의/불안 등). 눈빛, 눈썹, 입술, 턱선 같은 얼굴 단서를 한 줄 이상 명시한다.",
            "무뚝뚝한 주인공이라도 매 컷 무표정으로 고정하지 않는다. 결의, 경계, 주저, 분노, 안도, 연민 중 해당 감정을 얼굴과 시선으로 분명히 드러낸다.",
            "대본에 야간/새벽/황혼이 명시되지 않으면 기본 시간대는 daytime으로 둔다.",
            "색감은 칙칙하지 않게 유지한다: bright exposure, rich mid/high saturation, clear local contrast, readable details in faces and costumes.",
            "배경은 빈 화면처럼 두지 말고 문맥에 맞는 서사 디테일(장터 군중, 작업하는 사람, 이동하는 행인, 생활 소품)을 적정량 넣는다.",
            "characters 입력에 species가 있으면 해당 종을 반드시 유지한다(인간/소/개/말 등).",
            "scene에 포함된 핵심 인물만 정확히 유지한다. 입력에 없는 새 주연급 인물을 추가하지 말고, 대본에 없는 군중/수행원/도우미로 장면 핵심 관계를 흐리지 않는다.",
            "scene의 핵심 인원 수가 2명 또는 3명으로 읽히면 그 인원만 명확히 보이게 유지하고, 같은 사람의 분신처럼 보이는 duplicate figure를 절대 만들지 않는다.",
            "한 장면 안에서 한 인물을 foreground와 background에 동시에 두 번 배치하지 않는다. 시간 경과를 한 컷 안에 합성한 split-moment 구성도 금지한다.",
            "같은 인물(name/variant)은 장면 간 외형 일관성을 유지한다(성별/연령대/얼굴 인상/헤어/복식 핵심 앵커 유지). 인물 입력에 없는 새 헤어스타일/머리장식/복식 컨셉을 임의로 추가하지 않는다.",
            "같은 인물과 같은 variant가 인접 장면에 반복되면, 복장 상태와 변장 컨셉을 유지한다. 같은 ragged beggar disguise면 다음 컷에서도 같은 누더기 옷, 같은 머리/모자 계열, 같은 색 계열을 유지하고 새 의상으로 갈아입히지 않는다.",
            "variant나 wardrobe_anchors에 disguise/변복/복장 정보가 있으면 그것을 최우선 복식 고정 규칙으로 따르고, scene마다 다른 옷으로 재해석하지 않는다.",
            "대본 문장을 그대로 복사하지 말고, 장면 묘사로 재구성한다. 시대지시가 있으면 조선시대 의복/소품/건축/분위기를 유지한다.",
            "직접 대사나 인용부호(\"...\", '...')를 prompt에 쓰지 않는다. 등장인물의 말은 입 모양, 손짓, 표정, 긴장감, 권위적인 태도 같은 시각적 행동으로만 번역한다.",
            "shouting \"...\" 또는 saying \"...\" 같은 직접 발화문 대신 mouth open in a forceful shout, appears to be announcing his authority, urgent expression, lips parted as if calling out 같은 행동 묘사를 사용한다.",
            "말풍선/대화풍선/텍스트 박스/내레이션 박스/캡션 박스/효과음 문자(SFX)를 절대 그리지 않는다. 빈 풍선 형태도 금지한다.",
            "패널 분할, 검은 테두리 프레임, 상단/하단 여백(흰색/검은색 레터박스 포함), 만화 페이지 레이아웃을 절대 만들지 않는다.",
            "굶주림, 질병, 절망, 혹한 같은 비참한 상황은 과장된 신체 왜곡이나 공포물 같은 기괴한 얼굴로 표현하지 않는다. 수척함은 절제된 표정, 마른 실루엣, 해진 옷, 황량한 환경으로 전달한다.",
            "인체 해부학 일관성을 강하게 유지한다: 사람은 머리 1개, 몸통 1개, 팔 2개, 손 2개, 다리 2개, 발 2개를 기본으로 하며 추가 팔다리/중복 손가락/뒤틀린 관절/붙은 손을 만들지 않는다.",
            "손이 프레임에 크게 보일 때는 손 형태를 단순하고 명확하게 유지한다. 손가락 수는 자연스럽게 5개 기준으로 보이도록 하고, 겹침 때문에 기괴해 보이면 포즈를 단순화한다.",
            "팔과 손의 좌우 연결을 명확히 유지한다. 오른팔에 왼손이 붙은 것처럼 보이는 crossed anatomy, 팔뚝 중복, 손목 융합을 금지한다.",
            "동물도 해부학 일관성을 유지한다: 소/개/말 등은 다리 수 4개를 기본으로 하며 여분의 다리/머리/꼬리를 만들지 않는다.",
            "인물/동물/가구/소품 사이의 물리적 경계를 명확히 유지한다. 몸이 의자/상/문/벽/바구니를 관통하거나 서로 융합된 형태를 만들지 않는다.",
            "앉기/기대기/무릎꿇기 장면에서는 접촉면(contact point)을 분명히 묘사하고, 골반/등/팔 위치가 가구 구조와 자연스럽게 맞물리도록 한다.",
            "가림(occlusion)은 단순한 앞뒤 가림으로만 표현한다. 신체 일부가 가구 내부에 끼어든 것처럼 보이는 잘린 단면, 비정상 접합, 떠 있는 팔다리를 금지한다.",
            "아동으로 표시된 인물은 학령기 어린이 비율과 얼굴로 유지한다. 갓난아기, 포대기 아기, 유아 비율, 과도하게 둥근 영아 얼굴로 바꾸지 않는다. 대본이 명시하지 않으면 아기를 품에 안은 자세로 축소 해석하지 않는다.",
            "약 5세~7세 아동은 걸을 수 있고 스스로 앉거나 서는 학령기 어린이로 묘사한다. 보호자의 품에 있더라도 신생아처럼 포대기에 싸거나 한 팔로 들어 올린 아기 자세로 그리지 않는다.",
            "장면에 두 아이, 남매, sibling pair처럼 인원 수가 명시되면 정확히 그 수만 묘사하고, 여분의 아이를 추가하지 않는다.",
            "반드시 2D Korean webtoon/manhwa rendering으로 작성한다: ink lineart, full-color cel shading, bold outlines, simplified surfaces, comic-style shading.",
            "photorealistic/photo/DSLR/live-action/film still/ultra-realistic은 금지한다. 반드시 stylized illustration로 유지한다.",
            "사진/실사/필름스틸/DSLR/렌즈/보케/심도(DOF)/blur 같은 촬영 효과 표현은 피하고, 필요하면 배경 단순화, 실루엣 처리, 명암 대비, 전경 프레이밍으로 치환한다.",
            "최종 이미지는 16:9 landscape single panel로 읽혀야 하며, 가로/세로로 인물을 늘이거나 찌그러뜨리지 않는다. 얼굴과 몸 비율은 자연스럽게 유지한다.",
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

        if any(token in rule_corpus for token in ("황소", "암소", "수소", "송아지", "외양간", "쟁기", "발굽")):
            rules.extend([
                "누렁이/소가 등장하면 반드시 bovine cattle로 묘사한다. 절대 dog/canine으로 바꾸지 않는다.",
                "소 해부학 고정: cloven hooves, bovine muzzle, heavy neck-shoulder mass, cattle horn/ear proportions.",
                "동물 표정은 과도한 의인화 대신 실제 동물 제스처(귀 방향, 목의 긴장, 발굽 자세)로 표현한다.",
            ])
        elif "누렁이" in rule_corpus:
            rules.extend([
                "'누렁이' 단어만으로 소/개를 단정하지 말고 scene_text 문맥으로 종을 판단한다.",
                "소 문맥(황소/외양간/쟁기/발굽)이면 cattle, 개 문맥(짖다/강아지/개집)이면 dog로 유지한다.",
            ])

        if any(token in rule_corpus for token in ("시장", "장터", "저잣거리", "관아", "마을")):
            rules.extend([
                "공간이 시장/장터/관아/마을이면 배경 군중과 생활 동선을 넣어 장면 생동감을 높인다.",
                "군중은 주피사체를 가리지 않는 선에서 depth layer(전경/중경/후경)로 분산 배치한다.",
            ])

        if any(token in rule_corpus for token in ("아궁이", "온돌", "헛간", "오두막", "방", "부엌")):
            rules.extend([
                "조선시대 주거 실내는 온돌 구조를 우선한다. 일반 생활방 안에 노출된 벽난로/실내 화덕/현대식 fireplace를 두지 않는다.",
                "아궁이가 필요하면 부엌 쪽 또는 방 바깥쪽 난방 구조로 처리하고, 실내 생활공간에서는 식은 재, 구들 온기, 부엌 쪽 기척처럼 간접적으로 표현한다.",
                "화로가 명시되지 않은 한 방 한가운데의 노출 화구를 만들지 않는다.",
                "실내 난방/물 데우기 장면이 필요하면 서양식 벽난로 대신 작은 화로, 숯불 화로, 부엌 쪽 솥과 난방 기척처럼 조선식 소품으로 번역한다.",
                "벽면에 붙은 fireplace, 굴뚝형 벽난로, stone hearth 같은 서양식 난방 구조는 사용하지 않는다.",
                "실내 생활방에서는 장작 더미를 직접 태우는 큰 불(캠프파이어/모닥불/타오르는 통나무 화염)을 절대 만들지 않는다.",
                "실내 불빛은 등잔, 초, 작은 화로의 약한 불씨 중심으로 제한하고, 천장까지 치솟는 화염 연출은 금지한다.",
            ])

        if any(token in rule_corpus for token in ("인질", "포박", "묶여", "잡혀", "위협", "따귀", "뺨을", "협박")):
            rules.extend([
                "포박/인질 장면의 피해자는 공포, 고통, 결연함 위주 표정으로 유지한다. 위협받는 순간에 미소, 방긋 웃음, 들뜬 표정은 금지한다.",
                "포박된 손목, 밧줄, 당겨진 어깨, 움츠린 목선처럼 구속 상태가 읽히도록 하고, 느슨하게 풀린 포즈로 바꾸지 않는다.",
            ])

        if any(token in rule_corpus for token in ("자객", "살수", "습격", "매복", "암살자", "흑영대")):
            rules.extend([
                "자객/살수는 읽을 수 있는 실체 인간으로 묘사한다. 검은 덩어리 silhouette만으로 처리하지 않는다.",
                "어둠 속 매복이어도 최소 한 명 이상은 얼굴 윤곽, 무기, 자세가 식별되게 그린다.",
            ])

        if "낫" in rule_corpus:
            rules.extend([
                "낫은 조선 생활용 한국형 ㄱ자 곡날 낫으로 유지한다. 서양식 scythe나 분리된 날/손잡이 구조는 금지한다.",
                "낫을 드는 장면에서는 날이 자기 몸이나 얼굴을 향하지 않게 하고, 손잡이와 날의 결합부를 명확히 유지한다.",
            ])

        if any(token in rule_corpus for token in ("가마", "교자", "연", "팔인교", "들것")):
            rules.extend([
                "조선시대 가마는 바퀴가 없는 가마로 묘사하고, 긴 멜대에 매달려 사람이 어깨로 메는 구조를 유지한다.",
                "가마를 사람이 들어 옮기면 바퀴, 수레 차축, 리어카 같은 구조를 절대 추가하지 않는다.",
                "가마 안의 승객은 가마를 직접 메지 않는다. 어린 왕자나 양반 승객이 멜대를 어깨에 지는 연출은 금지한다.",
                "가마를 메는 인물은 성인 수행원 2명 또는 4명으로 분명히 분리하고, 아이나 주연 인물을 운반 인부로 바꾸지 않는다.",
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

        resp = call_with_timeout(
            lambda: self._get_client().models.generate_content(
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
            ),
            self.cfg.timeout_sec,
        )

        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("LLM scene prompt 응답(resp.text)이 비어 있습니다.")

        data = json.loads(text)
        validated = LLMScenePromptResult.model_validate(data)
        return validated.model_dump()
