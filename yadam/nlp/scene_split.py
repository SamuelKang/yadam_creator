# yadam/nlp/scene_split.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Scene:
    id: int
    sentences: List[str]

    @property
    def text(self) -> str:
        return " ".join(self.sentences).strip()


def split_into_scenes(
    sentences: List[str],
    min_s: int = 2,
    max_s: int = 4,
    base_len: int = 40,   # ✅ 기준 길이(기본 40)
) -> List[Scene]:
    """
    새 규칙(요구사항 그대로):
    - 최소 min_s(기본 2) 문장으로 시작
    - threshold = min_s * base_len (기본 80)
    - 2문장 합이 threshold(80) 초과면: 그 2문장으로 scene 확정
    - 2문장 합이 threshold 이하(<=80)면:
        - 문장을 하나씩 추가하며(최대 max_s=4)
        - 추가 후 길이가 threshold를 "넘는 순간" 그 상태로 확정
        - 끝까지(최대 4문장) 붙여도 threshold를 못 넘으면 4문장(또는 남은 만큼)으로 확정
    - 마지막에 1문장만 남는 경우: 1문장 scene으로 처리
    """
    out: List[Scene] = []
    n = len(sentences)
    i = 0
    sid = 1
    threshold = min_s * base_len

    def joined_len(ss: List[str]) -> int:
        return len(" ".join(ss).strip())

    while i < n:
        remain = n - i

        # 마지막 1문장 남으면 그대로
        if remain == 1:
            out.append(Scene(id=sid, sentences=[sentences[i]]))
            sid += 1
            break

        # 최소 min_s 확보
        chunk = sentences[i:i + min_s]
        if len(chunk) < min_s:
            out.append(Scene(id=sid, sentences=chunk))
            sid += 1
            break

        cur_len = joined_len(chunk)

        # 2문장만으로 threshold 초과면 바로 확정
        if cur_len > threshold:
            out.append(Scene(id=sid, sentences=chunk))
            sid += 1
            i += len(chunk)
            continue

        # 2문장 길이가 threshold 이하이면, max_s까지 추가하며 threshold를 넘기려 시도
        while len(chunk) < max_s and (i + len(chunk)) < n:
            chunk.append(sentences[i + len(chunk)])
            cur_len = joined_len(chunk)

            # "넘는 순간" 확정
            if cur_len > threshold:
                break

        out.append(Scene(id=sid, sentences=chunk))
        sid += 1
        i += len(chunk)

    return out