# yadam/nlp/sentence_split.py
from __future__ import annotations
import re
from typing import List


_SENT_END = re.compile(r"([\.!?]|다[\.!?]?|요[\.!?]?)\s+")


def normalize_script(text: str) -> str:
    # 빈줄 제거 + 양끝 공백 정리
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def split_sentences_korean(text: str) -> List[str]:
    # 매우 단순한 문장 분리기(운영 중 개선 가능)
    t = text.replace("\r\n", "\n").strip()
    if not t:
        return []

    parts = []
    start = 0
    for m in _SENT_END.finditer(t + " "):
        end = m.end()
        seg = t[start:end].strip()
        if seg:
            parts.append(seg)
        start = end
    tail = t[start:].strip()
    if tail:
        parts.append(tail)
    return parts