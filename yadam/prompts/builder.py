# yadam/prompts/builder.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from yadam.prompts.profiles import EraProfile, StyleProfile


@dataclass
class PromptParts:
    era_prefix: str
    content: str
    style_suffix: str
    safety: str

    def build(self) -> str:
        # 항상 동일한 순서로 합성
        return f"{self.era_prefix}\n{self.content}\n{self.style_suffix}\n{self.safety}".strip()


def _is_pojol_character(
    name: str,
    hints: List[str],
    variant: str,
    context: str,
    court_role: str,
    wardrobe_anchors: List[str],
) -> bool:
    corpus = " ".join(
        [
            name or "",
            variant or "",
            context or "",
            court_role or "",
            " ".join(hints or []),
            " ".join(wardrobe_anchors or []),
        ]
    )
    return any(token in corpus for token in ("포졸", "관아 나졸", "나졸", "형방"))


def _age_stage_to_years(age_stage: str) -> Optional[int]:
    s = (age_stage or "").strip()
    table = {
        "유아": 2,
        "아동": 5,      # ✅ 아동 기준 나이: 5
        "청소년": 15,
        "청년": 25,
        "중년": 45,
        "노년": 70,
    }
    return table.get(s)


def build_scene_content(scene_text: str, character_lines: List[str], place_line: Optional[str]) -> str:
    # 장면 프롬프트는 과밀해지지 않게: 장소 1 + 인물 0~2 + 행동/분위기 중심
    parts: List[str] = []
    if place_line:
        parts.append(f"장소: {place_line}")
    if character_lines:
        parts.append("등장인물: " + ", ".join(character_lines[:2]))
    parts.append(f"장면: {scene_text}")
    parts.append("구도: 인물 감정이 읽히는 시네마틱 구도, 과장된 폭력/선정 묘사 없음")
    parts.append("형식: 단일 장면 일러스트(한 컷). 만화 패널/컷 분할/말풍선/자막/캡션/간판 글씨 없음.")
    parts.append("주의: 화면 여백에 글자가 들어갈 공간을 만들지 말 것. 텍스트/로고/워터마크 없음.")
    parts.append("추가 금지: 만화 페이지 레이아웃, 상단/하단 내레이션 박스, 패널 테두리, 말풍선 테두리, 텍스트 박스.")
    if "주먹밥" in (scene_text or ""):
        parts.append(
            "소품 고증: 주먹밥은 일본식 삼각 오니기리가 아니라 조선식 손으로 쥔 둥글고 투박한 밥덩이로 묘사, 김 띠 없음."
        )
    return "\n".join(parts)


def build_scene_prompt(
    era: EraProfile,
    style: StyleProfile,
    scene_text: str,
    character_lines: List[str],
    place_line: Optional[str],
) -> str:
    parts = PromptParts(
        era_prefix=era.prefix,
        content=build_scene_content(scene_text, character_lines, place_line),
        style_suffix=style.suffix,
        safety=era.safety,
    )
    return parts.build()


def build_character_prompt(
    era: EraProfile,
    style: StyleProfile,
    name: str,
    hints: List[str],
    gender: str = "불명",
    age_stage: str = "불명",
    variant: str = "",
    species: str = "인간",

    # ✅ 추가: 계급/재산/궁중 컨텍스트
    context: str = "민간",         # 궁중/민간/관아/사찰...
    court_role: str = "",          # 궁중일 때만
    social_class: str = "불명",     # 양반/중인/상민/천민/승려/무속
    wealth_level: str = "불명",     # 부유/보통/빈곤
    wardrobe_tier: str = "T2",      # T1/T2/T3
    wardrobe_anchors: Optional[List[str]] = None,
) -> str:
    if wardrobe_anchors is None:
        wardrobe_anchors = []

    def _solo_safe_anchor(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        # Character sheet must stay single-subject; drop anchors that imply extra people.
        blocked = (
            "업고", "업은", "업힌", "업혀", "등에 업", "안고", "안긴", "안겨", "껴안",
            "동생", "아이", "남매", "둘이", "셋이", "함께", "포대기",
            "두 사람", "세 사람", "군중", "무리", "사람들",
        )
        return not any(k in t for k in blocked)

    anchors = [
        h.strip()
        for h in (hints or [])
        if isinstance(h, str) and h.strip() and _solo_safe_anchor(h)
    ]
    # Keep character prompt concise and stable.
    if len(anchors) > 10:
        anchors = anchors[:10]
    anchor_line = ", ".join(anchors) if anchors else ""

    # 성장 서사 variant
    variant_line = (variant or "").strip()
    age_stage = (age_stage or "").strip()

    # 연령 라인(아동=7세 등은 _age_stage_to_years가 결정)
    age_years = _age_stage_to_years(age_stage)
    if age_years is not None:
        age_line = f"연령: 약 {age_years}세 ({age_stage})"
    else:
        age_line = f"연령: {age_stage}" if age_stage else ""

    # ---------------------------
    # ✅ 복식 프리셋(궁중 우선)
    # ---------------------------
    ctx = (context or "민간").strip()
    cr = (court_role or "").strip()
    sc = (social_class or "").strip()
    wl = (wealth_level or "").strip()
    tier = (wardrobe_tier or "T2").strip().upper()
    variant_norm = variant_line.strip()
    species_norm = (species or "인간").strip()
    is_pojol = _is_pojol_character(name, anchors, variant_norm, ctx, cr, wardrobe_anchors)

    # Variant should override generic class/tier presets when it implies a clear disguise/state.
    if variant_norm == "노비":
        sc = "천민"
        wl = "빈곤"
        tier = "T1"
    elif variant_norm == "무관":
        if tier == "T1":
            tier = "T2"
    elif is_pojol:
        if sc in ("", "불명"):
            sc = "중인"
        if wl in ("", "불명"):
            wl = "보통"
        if tier == "T1":
            tier = "T2"

    wardrobe_bits: List[str] = []
    # LLM이 준 wardrobe_anchors를 우선 사용
    for w in wardrobe_anchors:
        if isinstance(w, str) and w.strip():
            wardrobe_bits.append(w.strip())

    # 프리셋 추가(anchors가 부족할 때도 기본을 채우기 위함)
    if ctx == "궁중":
        # 궁중 프리셋: court_role 기반
        if not cr:
            cr = "궁중 인물"

        if cr in ("왕", "왕비", "세자", "후궁"):
            wardrobe_bits += [
                "궁중 예복/궁중 정복 계열",
                "정갈한 비단, 과장된 금장식 금지",
                "궁중 규격의 머리장식/비녀/관모(역할에 맞게)",
            ]
        elif cr in ("문신", "관료", "승정원", "홍문관"):
            wardrobe_bits += [
                "궁중 출입 문신 관복(품계 표현은 과장 없이)",
                "사모 또는 궁중 관모, 흉배/관복 디테일은 절제",
                "단정한 도포/관복 실루엣",
            ]
        elif cr in ("무관", "호위"):
            wardrobe_bits += [
                "궁중 호위/무관 복식(갑옷 과장 금지)",
                "실용적 무장 소품은 최소",
                "단정한 궁중 무관 실루엣",
            ]
        elif cr in ("궁녀",):
            wardrobe_bits += [
                "궁녀 당의/치마 계열, 단정한 색감",
                "궁중 규격 머리 모양/비녀",
                "장식 절제, 깨끗한 선",
            ]
        elif cr in ("내관", "내시"):
            wardrobe_bits += [
                "궁중 내관/내시 복식(단정하고 절제)",
                "궁중 규격 관모",
            ]
        else:
            wardrobe_bits += [
                "궁중 인물 복식: 규격화된 궁중 톤",
                "장식 절제, 과장 금지",
            ]
    else:
        # 민간/기타 프리셋: social_class + wealth/tier
        # tier 우선(몰락 양반을 표현 가능)
        if variant_norm == "노비":
            wardrobe_bits += [
                "하류 복식: 거친 무명 적삼, 해진 소매와 단순한 허리끈",
                "장식 없는 차림, 노동과 도피의 생활감",
                "갓/관모/도포/관복/갑옷 금지",
                "짚신 또는 낡은 신발, 실용적이고 초라한 소지품만 허용",
            ]
        elif is_pojol:
            wardrobe_bits += [
                "조선시대 관아 소속 포졸 복식: 전통 포졸복 또는 실용적인 관아 하급 관리 복식",
                "넓은 양반 갓이 아닌, 낮고 투박한 조선 포졸용 전통 관모",
                "행전, 짚신 또는 거친 전통 신발, 허리띠와 실용 소지품",
                "목봉, 곤장, 횃불 같은 전통 집행 도구만 허용, 칼과 검집은 금지",
                "현대 제복 셔츠, 가슴 패치, 번호표, 배지, 현대식 단추 배열 금지",
                "양반 선비의 갓과 도포 차림, 무관의 검과 장식 허리띠 금지",
            ]
        elif tier == "T3":
            wardrobe_bits += [
                "민간 상류 복식: 비단/명주 느낌(과장 금지)",
                "정갈한 갓/도포 또는 당의/치마(성별/신분에 맞게)",
            ]
        elif tier == "T1":
            wardrobe_bits += [
                "하류 복식: 검소한 무명 위주의 실용 차림",
                "짚신/헝겊 띠 등 단순 소품, 과도한 오염/찢김/해짐 강조 금지",
            ]
        else:
            wardrobe_bits += [
                "중류 복식: 무명/면포 위주, 깔끔하고 실용적",
                "과도한 장식 없음",
            ]

        # 신분 힌트(추가 보정)
        if variant_norm == "노비":
            wardrobe_bits += ["노동/도피 흔적이 남은 검소하고 거친 복식"]
        elif sc == "양반":
            wardrobe_bits += ["사대부 느낌의 단정함(화려함보다 격식)"]
        elif sc == "중인":
            wardrobe_bits += ["실용적이되 정갈한 차림, 절제된 소품"]
        elif sc == "상민":
            wardrobe_bits += ["노동/생활감 있는 실용 복식"]
        elif sc == "천민":
            wardrobe_bits += ["검소하고 거친 질감, 과장 금지"]
        elif sc in ("승려", "무속"):
            wardrobe_bits += [f"{sc} 계열 의복(시대감 유지)"]
        elif is_pojol:
            wardrobe_bits += ["관아 하급 집행 인력의 실용적이고 투박한 차림"]

        # wealth_level이 있으면 미세 보정
        if wl == "부유":
            wardrobe_bits += ["원단과 마감이 비교적 깔끔"]
        elif wl == "빈곤":
            wardrobe_bits += ["원단이 거칠고 마감이 단순"]

    if is_pojol:
        wardrobe_bits += [
            "한국 사극/조선시대 포졸 실루엣 유지, 현대 경찰이나 군인처럼 보이지 않음",
            "소매와 옷자락은 전통 복식 비례, 현대식 카고 포켓이나 셔츠 주머니 없음",
            "양반 갓 실루엣이 아니라 관아 하급 포졸의 낮고 거친 관모 실루엣",
        ]

    # 중복 제거 + 길이 제한(너무 길면 모델이 산만해짐)
    dedup: List[str] = []
    for x in wardrobe_bits:
        x = x.strip()
        if x and x not in dedup:
            dedup.append(x)
    wardrobe_line = ", ".join(dedup[:10]) if dedup else "시대감 있는 단정한 복식"

    # 외형 앵커(visual_anchors/hints에서 온 anchors)도 별도로 유지
    if not anchor_line:
        anchor_line = "대본 기반 인물, 과장 없는 표정"

    content_lines: List[str] = [
        f"캐릭터: {name}" + (f" ({variant_line})" if variant_line else ""),
        f"종(species): {species_norm}",
        f"컨텍스트: {ctx}" + (f" / 궁중역할: {cr}" if (ctx == "궁중" and cr) else ""),
        f"신분: {sc}, 재산: {wl}, 복장티어: {tier}",
        f"성별: {gender}",
    ]
    if age_line:
        content_lines.append(age_line)

    content_lines += [
        f"복식·소품(핵심): {wardrobe_line}",
        f"외형·추가 앵커: {anchor_line}",
        "구도: 세로 3:4 비율, 전신(머리~발) 표현 우선, 중앙 정렬",
        "인물 수: 반드시 해당 캐릭터 1명만 단독으로 묘사, 다른 사람/아이/실루엣/배경 인물 추가 금지",
        "행동 제한: 다른 사람을 업거나 안거나 부축하는 포즈 금지(대본 힌트에 있어도 캐릭터 시트에서는 단독 포즈로 변환)",
        "배경: 순백 단색, 배경 소품 없음, 무늬 없음, 그라데이션 없음, 여백에 글자 영역 만들지 않음",
        "조명: 얼굴 윤곽이 자연스럽게 드러나는 부드러운 조명, 과도한 하이라이트/노이즈 없음",
        "얼굴/인상: 한국인(동아시아) 얼굴 비율과 이목구비, 한국 사극 캐릭터 인상 유지(서양인/혼혈형 과장 금지)",
        "얼굴 금지: 과한 V라인 턱, 유리피부/도자기피부, 아이돌형 과미화(과도한 미소년/미소녀화), 성형풍 비율",
        "표현 톤: B군(정돈된 캐릭터 디자인풍)으로 통일하되, 표정은 자연스럽고 과장 없는 감정 묘사",
        "질감 제한: 때/먼지/상처/찢김/피폐 질감 과장 금지, 깨끗하고 정돈된 캐릭터 마감 유지",
        "요구: 텍스트 없음, 자막 없음, 로고 없음, 워터마크 없음",
    ]
    if age_stage == "아동":
        content_lines += [
            "아동 연출: 밝고 귀여운 인상, 맑은 눈빛, 건강한 혈색, 가벼운 미소 또는 호기심 표정",
            "아동 금지: 병약/수척/비참/공포 분위기, 창백한 안색, 고통스러운 표정",
        ]
    elif age_stage == "청소년":
        content_lines += [
            "청소년 연출: 건강하고 또렷한 인상, 단정하고 생기 있는 표정",
            "청소년 금지: 병색/창백/극심한 피로/비참함 과장",
        ]
    elif age_stage == "청년":
        content_lines += [
            "청년 연출: 정돈된 인상과 균형 잡힌 얼굴 비례, 자연스러운 자신감",
            "청년 금지: 누더기/흙먼지/상처 중심의 피폐 묘사 과장",
        ]
    if species_norm != "인간":
        content_lines += [
            "동물 캐릭터 규칙: 인간형(의복/손/직립/인간 얼굴 비율)으로 의인화하지 않는다.",
            "동물 전신 비율/해부학을 정확히 유지하고, 해당 종의 귀·주둥이·다리 관절·발 형태를 보존한다.",
        ]
    if species_norm == "소":
        content_lines += [
            "종 고정: 반드시 소(cattle)로 묘사한다. 개/늑대/사슴/말로 바꾸지 않는다.",
            "소 해부학: 갈라진 발굽(cloven hooves), 소의 주둥이, 목/어깨 체형, 뿔 형태를 자연스럽게 유지한다.",
        ]
    content = "\n".join(content_lines)

    return PromptParts(era.prefix, content, style.suffix, era.safety).build()

def build_place_prompt(era: EraProfile, style: StyleProfile, name: str, hints: List[str]) -> str:
    """
    장소 이미지 프롬프트 생성.
    - hints는 orchestrator에서 visual_anchors를 우선 넘기도록 구성하는 것을 권장.
    - 여기서는 hints 내용을 '분위기/시간/날씨/구조 앵커'로 취급.
    """
    anchors = [h.strip() for h in (hints or []) if isinstance(h, str) and h.strip()]
    anchor_line = ", ".join(anchors) if anchors else "대본 기반 장소, 분위기와 조명 중심, 과장 없는 연출"

    lower_corpus = f"{name} " + " ".join(anchors)
    is_indoor_living = any(k in lower_corpus for k in ["오두막", "방", "실내", "사랑채", "안채", "대청", "온돌", "부엌"])
    is_market = any(k in lower_corpus for k in ["시장", "장터", "저잣거리", "시장통"])
    is_mountain_path = any(k in lower_corpus for k in ["산길", "고갯길", "산자락", "산등성이", "산 중턱"])

    lines = [
        f"장소: {name}",
        f"분위기·시간·날씨·구조 앵커: {anchor_line}",
        "구도: 와이드샷(장소 중심), 공간감이 느껴지도록, 문맥에 맞는 생활 요소(지나가는 사람/군중/동물/장터 기척)를 과하지 않게 포함 가능",
        "밝기/색감: 노출을 충분히 올려 디테일이 읽히게, 암부 뭉침 금지, 생기 있는 색 대비와 중고채도 유지",
        "시간대: 대본에 야간 명시가 없으면 기본은 낮",
        "요구: 16:9, 텍스트 없음, 자막 없음, 로고 없음, 워터마크 없음, 레터박스(상하 검은 여백) 없음",
    ]
    if is_indoor_living:
        lines.extend([
            "실내 고증: 조선시대 생활방/온돌 구조를 유지한다(종이문, 낮은 목가구, 온돌 마루/방바닥 중심).",
            "실내 금지: 헛간/창고 같은 노출 서까래 구조, 중앙 모닥불/캠프파이어/장작 직화, 서양식 fireplace.",
            "조명: 실내는 등잔/촛불/은은한 자연광 중심으로 표현하고, 과도한 화염 연출은 금지한다.",
        ])
    if is_market:
        lines.extend([
            "시장 연출: 군중은 중간 밀도로 두고, 배경 인물은 단순화된 군중층으로 처리한다. 과밀한 얼굴 디테일과 과도한 사실 묘사는 금지한다.",
            "화풍 고정: 반실사 질감보다 한국 웹툰풍 선화와 평면적 색면을 우선한다. 복잡한 사진풍 텍스처와 과도한 미세 디테일은 줄인다.",
            "배경 요소: 장터 좌판, 천막, 항아리, 바구니, 흙바닥 골목 등은 유지하되 주 피사체를 압도할 정도의 과밀 구성은 피한다.",
        ])
    if is_mountain_path:
        lines.extend([
            "산길 연출: 외딴 산길과 고요한 능선 분위기를 유지한다. 핵심 인물 외의 행인, 구경꾼, 행렬, 군중은 넣지 않는다.",
            "배경 요소: 바위, 메마른 흙길, 경사진 비탈, 드문 나무, 밤바람, 먼 산 능선 위주로 구성하고 사람 실루엣은 금지한다.",
            "화풍 고정: 한국 웹툰풍 선화와 명확한 실루엣을 유지하되, 쓸데없는 배경 인물 서사는 만들지 않는다.",
        ])

    content = "\n".join(lines)
    return PromptParts(era.prefix, content, style.suffix, era.safety).build()
