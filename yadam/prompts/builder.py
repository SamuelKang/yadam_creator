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

    anchors = [h.strip() for h in (hints or []) if isinstance(h, str) and h.strip()]
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
                "하류 복식: 삼베/거친 무명, 해짐/기움은 과장 없이",
                "짚신/헝겊 띠 등 실용적 소품",
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
        "배경: 순백 단색, 배경 소품 없음, 무늬 없음, 그라데이션 없음, 여백에 글자 영역 만들지 않음",
        "조명: 얼굴 윤곽이 자연스럽게 드러나는 부드러운 조명, 과도한 하이라이트/노이즈 없음",
        "요구: 텍스트 없음, 자막 없음, 로고 없음, 워터마크 없음",
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

    content = "\n".join([
        f"장소: {name}",
        f"분위기·시간·날씨·구조 앵커: {anchor_line}",
        "구도: 와이드샷(장소 중심), 공간감이 느껴지도록, 인물 없음(사람, 실루엣, 군중, 그림자 인물 포함)",
        "밝기: 노출을 충분히 올려 디테일이 읽히게, 과도한 암부 뭉침 금지",
        "시간대: 낮 또는 밝은 황혼(blue hour)",
        "요구: 16:9, 텍스트 없음, 자막 없음, 로고 없음, 워터마크 없음",
    ])
    return PromptParts(era.prefix, content, style.suffix, era.safety).build()
