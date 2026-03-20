from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Issue:
    severity: str
    kind: str
    location: str
    detail: str
    suggestion: str = ""


MODERN_TERM_RULES = [
    (re.compile(r"잉크"), "조선시대 문맥에서는 '잉크'보다 '먹' 또는 '먹물'이 자연스럽습니다.", "표현 교체 검토: 잉크 -> 먹물/먹"),
    (re.compile(r"경찰"), "조선시대 관아 인력 문맥에서 '경찰'은 시대착오 가능성이 큽니다.", "표현 교체 검토: 경찰 -> 포졸/관아 포졸"),
    (re.compile(r"엘리베이터|승강기"), "조선시대 배경과 맞지 않는 현대 설비 표현입니다.", "배경/소품 수정 검토"),
    (re.compile(r"기차|전철|지하철|플랫폼"), "조선시대 배경과 맞지 않는 현대 교통 표현입니다.", "배경/소품 수정 검토"),
    (re.compile(r"자동차|트럭|버스|택시|엔진|브레이크"), "조선시대 배경과 맞지 않는 현대 운송/기계 표현입니다.", "배경/소품 수정 검토"),
    (re.compile(r"리볼버|권총|자동소총|샷건|권총집"), "조선시대 기본 톤과 맞지 않는 현대 화기 표현입니다.", "무기/시대 설정 수정 검토"),
    (re.compile(r"라이터|전구|형광등|전등|스위치|콘센트|배터리"), "조선시대 배경과 맞지 않는 현대 전기/점화 표현입니다.", "소품 수정 검토"),
    (re.compile(r"시멘트|아스팔트|유리창문|쇼윈도"), "조선시대 건축/거리 배경과 맞지 않는 현대 재료 표현일 수 있습니다.", "배경 표현 수정 검토"),
    (re.compile(r"샴페인|위스키|칵테일"), "시대 배경과 맞지 않는 현대/서양 주류 표현일 수 있습니다.", "음식/소품 수정 검토"),
    (re.compile(r"커피|에스프레소|카푸치노"), "조선시대 기본 배경에서는 현대 커피 음용 표현이 어색할 수 있습니다.", "음식/소품 수정 검토"),
    (re.compile(r"샌드위치|햄버거|스테이크|파스타"), "조선시대 배경과 맞지 않는 서양 음식 표현일 수 있습니다.", "음식/소품 수정 검토"),
    (re.compile(r"코트 주머니|재킷|셔츠|넥타이|부츠컷"), "조선시대 복식과 맞지 않는 현대 의복 표현일 수 있습니다.", "복식 표현 수정 검토"),
    (re.compile(r"fireplace|벽난로", re.IGNORECASE), "조선시대 생활방 문맥에서 서양식 벽난로는 부적절할 수 있습니다.", "표현 교체 검토: 화로/아궁이/온돌 기척"),
]

INJURY_TERMS = ("화상", "붕대", "상처", "피투성이", "결박", "포박", "쇠사슬", "기절", "정신을 잃", "쓰러", "의식을 잃")
RECOVERY_OR_ACTION_TERMS = ("달려", "뛰어", "걸어", "성큼", "미소", "웃", "유유히", "거침없이", "멀쩡", "당당히")
SEVERE_WEATHER_TERMS = ("빗줄기", "비바람", "폭우", "장대비", "폭풍우", "천둥", "소나기", "우박")
CLEAR_WEATHER_TERMS = ("맑은 하늘", "청명", "햇살", "봄볕", "해가 비치", "화창", "쾌청")
FIRE_CHAOS_TERMS = ("불길", "화염", "불타는", "연기", "화마", "타오르", "불길 너머", "창고가 불")
CALM_AFTERMATH_TERMS = ("고요", "잔잔", "평온", "여유", "담담", "밝은 아침", "평화로운", "미소")
TRANSITION_TERMS = ("날이 밝자", "다음날", "이튿날", "한참 뒤", "잠시 뒤", "얼마 후", "새벽이 지나", "밤새", "아침이 오자")


def _load_story_lines(story_path: Path) -> List[str]:
    return story_path.read_text(encoding="utf-8").splitlines()


def _chapter_no_for_line(lines: List[str], line_no: int) -> Optional[int]:
    chapter_no: Optional[int] = None
    pattern = re.compile(r"^\s*Chapter\s+(\d+)")
    for idx, line in enumerate(lines, start=1):
        if idx > line_no:
            break
        m = pattern.match(line)
        if m:
            chapter_no = int(m.group(1))
    return chapter_no


def _scan_story_lines(lines: List[str]) -> List[Issue]:
    issues: List[Issue] = []
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        chapter_no = _chapter_no_for_line(lines, line_no)
        prefix = f"line {line_no}"
        if chapter_no is not None:
            prefix += f" (Chapter {chapter_no})"

        if "§§" in line:
            issues.append(Issue("warn", "markup_artifact", prefix, "scene text 안에 불필요한 마커 '§§'가 있습니다.", "대본/scene 정리 검토"))

        for pattern, detail, suggestion in MODERN_TERM_RULES:
            if pattern.search(line):
                issues.append(Issue("warn", "anachronism", prefix, f"{detail} | text={line[:140]}", suggestion))
    return issues


def _load_project_scenes(project_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(project_path.read_text(encoding="utf-8"))
    scenes = data.get("scenes") or []
    return [s for s in scenes if isinstance(s, dict)]


def _scene_char_ids(scene: Dict[str, Any]) -> set[str]:
    vals = scene.get("characters")
    if not isinstance(vals, list):
        return set()
    return {str(v) for v in vals if isinstance(v, str)}


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _scan_scene_hotspots(project_path: Path) -> List[Issue]:
    if not project_path.exists():
        return []
    scenes = _load_project_scenes(project_path)
    issues: List[Issue] = []
    for prev, cur in zip(scenes, scenes[1:]):
        prev_text = str(prev.get("text") or "")
        cur_text = str(cur.get("text") or "")
        if not prev_text or not cur_text:
            continue
        if not (_contains_any(prev_text, INJURY_TERMS) and _contains_any(cur_text, RECOVERY_OR_ACTION_TERMS)):
            continue
        if _contains_any(cur_text, INJURY_TERMS):
            continue
        if not (_scene_char_ids(prev) & _scene_char_ids(cur)):
            continue
        issues.append(
            Issue(
                "review",
                "continuity_hotspot",
                f"scene {prev.get('id')} -> {cur.get('id')}",
                "직전 장면의 부상/구속 상태가 다음 장면에서 빠르게 희석될 수 있습니다. 대본 앞뒤 정황 확인이 필요합니다.",
                f"prev={prev_text[:90]} | next={cur_text[:90]}",
            )
        )
        continue

    for prev, cur in zip(scenes, scenes[1:]):
        prev_text = str(prev.get("text") or "")
        cur_text = str(cur.get("text") or "")
        if not prev_text or not cur_text:
            continue
        if _contains_any(cur_text, TRANSITION_TERMS):
            continue
        if not (_scene_char_ids(prev) & _scene_char_ids(cur)):
            continue

        same_place = bool(set(prev.get("places") or []) & set(cur.get("places") or []))

        if same_place and _contains_any(prev_text, SEVERE_WEATHER_TERMS) and _contains_any(cur_text, CLEAR_WEATHER_TERMS):
            issues.append(
                Issue(
                    "review",
                    "weather_jump",
                    f"scene {prev.get('id')} -> {cur.get('id')}",
                    "같은 흐름의 인접 장면에서 거센 날씨가 갑자기 밝은 날씨로 바뀌어 보입니다.",
                    f"prev={prev_text[:90]} | next={cur_text[:90]}",
                )
            )

        if same_place and _contains_any(prev_text, FIRE_CHAOS_TERMS) and _contains_any(cur_text, CALM_AFTERMATH_TERMS):
            issues.append(
                Issue(
                    "review",
                    "fire_state_jump",
                    f"scene {prev.get('id')} -> {cur.get('id')}",
                    "직전 장면의 화재/연기 혼란이 다음 장면에서 너무 빠르게 사라지는지 확인이 필요합니다.",
                    f"prev={prev_text[:90]} | next={cur_text[:90]}",
                )
            )
    return issues


def main() -> None:
    ap = argparse.ArgumentParser(description="Check story text for possible pre-image script issues.")
    ap.add_argument("--story-id", required=True)
    args = ap.parse_args()

    root = Path.cwd()
    story_path = root / "stories" / f"{args.story_id}.txt"
    project_path = root / "work" / args.story_id / "out" / "project.json"

    if not story_path.exists():
        raise SystemExit(f"missing story file: {story_path}")

    lines = _load_story_lines(story_path)
    issues = _scan_story_lines(lines)
    issues.extend(_scan_scene_hotspots(project_path))

    if not issues:
        print("OK: no obvious preflight story issues found")
        return

    severity_order = {"warn": 0, "review": 1}
    issues.sort(key=lambda x: (severity_order.get(x.severity, 9), x.location, x.kind))

    print(f"FOUND {len(issues)} preflight story issues")
    for it in issues:
        line = f"- [{it.severity}] {it.kind} @ {it.location}: {it.detail}"
        if it.suggestion:
            line += f" | suggestion={it.suggestion}"
        print(line)

    raise SystemExit(3)


if __name__ == "__main__":
    main()
