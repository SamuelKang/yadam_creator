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
    # 대사 블록을 보존하는 문장 분리기.
    t = text.replace("\r\n", "\n").strip()
    if not t:
        return []

    parts: List[str] = []
    buf: List[str] = []
    in_quote = False
    i = 0
    n = len(t)

    while i < n:
        ch = t[i]
        buf.append(ch)

        if ch == "\"":
            in_quote = not in_quote
            i += 1
            continue

        if in_quote:
            i += 1
            continue

        if ch == "\n":
            seg = "".join(buf).strip()
            if seg:
                parts.append(seg)
            buf = []
            i += 1
            while i < n and t[i] == "\n":
                i += 1
            continue

        if _is_sentence_boundary(t, i):
            j = i + 1
            while j < n and t[j] in "\"'”’)]}":
                buf.append(t[j])
                j += 1
            seg = "".join(buf).strip()
            if seg:
                parts.append(seg)
            buf = []
            while j < n and t[j].isspace():
                if t[j] == "\n":
                    break
                j += 1
            i = j
            continue

        i += 1

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)

    return _merge_quote_runs(parts)


def _is_sentence_boundary(text: str, idx: int) -> bool:
    ch = text[idx]
    if ch in ".!?":
        return True

    remain = text[idx:]
    if ch in ("다", "요"):
        after = idx + 1
        if after >= len(text) or text[after].isspace() or text[after] in "\"'”’)]}":
            return True
    return False


def _merge_quote_runs(parts: List[str]) -> List[str]:
    if not parts:
        return []

    out: List[str] = []
    buf = ""
    in_quote = False
    for part in parts:
        s = part.strip()
        if not s:
            continue
        if not buf:
            buf = s
        else:
            buf = f"{buf}\n{s}"
        in_quote = (buf.count("\"") % 2) == 1
        if in_quote:
            continue
        out.append(buf.strip())
        buf = ""
    if buf:
        out.append(buf.strip())
    return out
