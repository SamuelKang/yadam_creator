# yadam/prompts/rewrite.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class RewriteResult:
    level: int
    rewritten: str
    note: str


def rewrite_for_policy(prompt: str, level: int) -> RewriteResult:
    # level 0: 원본
    if level <= 0:
        return RewriteResult(level=0, rewritten=prompt, note="original")

    # 매우 단순한 예시 규칙(운영하면서 확장)
    p = prompt

    # level 1: 위험 단어 완곡/삭제
    if level == 1:
        for bad, good in [
            ("피", "불길한 흔적"),
            ("살해", "위협적인 사건"),
            ("시체", "정적이 흐르는 현장"),
            ("강간", "심각한 위기"),
            ("노출", "단정한 복식"),
        ]:
            p = p.replace(bad, good)
        return RewriteResult(level=1, rewritten=p, note="soft rewrite")

    # level 2: 직접 묘사 제거 + 분위기/실루엣 전환
    if level == 2:
        p += "\n추가 지침: 직접적인 상해/유혈/시신/성적 행위 묘사는 배제하고, 실루엣과 조명, 정적과 분위기로만 긴장감을 표현한다."
        return RewriteResult(level=2, rewritten=p, note="moderate rewrite")

    # level 3: 최후 - 장소 분위기 샷으로 치환
    p += "\n추가 지침: 인물 클로즈업 대신 장소의 분위기 중심 장면(등불, 눈발, 빈 골목, 흔들리는 창호지)으로 표현한다. 민감한 사건은 암시만 한다."
    return RewriteResult(level=3, rewritten=p, note="hard rewrite")