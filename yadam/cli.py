# yadam/cli.py
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from yadam.model_defaults import (
    DEFAULT_COMFY_MODEL,
    DEFAULT_COMFY_WORKFLOW_FLUX_BASE,
    DEFAULT_COMFY_WORKFLOW_SDXL_FAST,
    DEFAULT_COMFY_WORKFLOW_ZIMAGE_TURBO,
    DEFAULT_GEMINI_IMAGE_MODEL,
    DEFAULT_TEXT_LLM_MODEL,
    DEFAULT_VERTEX_IMAGE_MODEL,
    resolve_gemini_image_model,
)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


class _TeeWriter(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase) -> None:
        self._streams = streams

    def write(self, s: str) -> int:
        for stream in self._streams:
            stream.write(s)
            stream.flush()
        return len(s)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


_RUN_LOG_STREAM: io.TextIOBase | None = None


def _enable_run_log(work_dir: Path, story_id: str) -> Path:
    global _RUN_LOG_STREAM

    if _RUN_LOG_STREAM is not None:
        return Path(getattr(_RUN_LOG_STREAM, "name", ""))

    logs_dir = work_dir / story_id / "logs"
    _ensure_dir(logs_dir)
    log_path = logs_dir / f"{story_id}.log"
    log_stream = log_path.open("a", encoding="utf-8", buffering=1)
    log_stream.write(f"[INFO] run log started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_stream.flush()

    sys.stdout = _TeeWriter(sys.__stdout__, log_stream)
    sys.stderr = _TeeWriter(sys.__stderr__, log_stream)
    _RUN_LOG_STREAM = log_stream
    print(f"[INFO] run log: {log_path}")
    return log_path


def _resolve_llm_model(raw: str = "") -> str:
    return (raw or "").strip() or DEFAULT_TEXT_LLM_MODEL


def _confirm_clean_workdir(target: Path) -> bool:
    """
    --clean-workdir 사용 시, 반드시 y/n 중 하나만 입력받는다.
    enter/기타 입력은 무효로 처리하고 재질문한다.
    """
    print("")
    print("=" * 72)
    print("[CONFIRM] workdir를 삭제하고 처음부터 시작합니다. 계속할까요? (y/n)")
    print(f"- delete: {target}")
    while True:
        ans = input("> ").strip().lower()
        if ans == "y":
            return True
        if ans == "n":
            return False
        print("y 또는 n만 입력하세요.")


def _confirm_overwrite(target: Path) -> bool:
    print("")
    print("=" * 72)
    print("[CONFIRM] 파일이 이미 존재합니다. 덮어쓸까요? (y/n)")
    print(f"- overwrite: {target}")
    while True:
        ans = input("> ").strip().lower()
        if ans == "y":
            return True
        if ans == "n":
            return False
        print("y 또는 n만 입력하세요.")


def _confirm_continue_default_yes_or_all(message: str) -> str:
    print("")
    print("=" * 72)
    print(f"[CONFIRM] {message} (Y/n/a)")
    print("- a: 이후 단계는 모두 non-interactive로 자동 진행")
    while True:
        ans = input("> ").strip().lower()
        if ans in ("", "y", "yes"):
            return "yes"
        if ans in ("n", "no"):
            return "no"
        if ans in ("a", "all"):
            return "all"
        print("Y, n, a 중 하나로 입력하세요. Enter는 Y입니다.")


def _load_prompt_template(root: Path, relative_path: str) -> str:
    path = root / relative_path
    if not path.exists():
        raise FileNotFoundError(f"프롬프트 파일이 없습니다: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"프롬프트 파일이 비어 있습니다: {path}")
    return text


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding=encoding)
    tmp_path.replace(path)


def _is_transient_llm_error(err: Exception) -> bool:
    text = f"{type(err).__name__}: {err}".lower()
    transient_markers = (
        "500",
        "502",
        "503",
        "504",
        "internal",
        "unavailable",
        "resource_exhausted",
        "rate limit",
        "quota",
        "timeout",
        "timed out",
        "connection reset",
        "temporarily unavailable",
    )
    return any(marker in text for marker in transient_markers)


def _llm_retry_delay_sec(attempt: int) -> float:
    delays = {1: 1.5, 2: 3.0, 3: 6.0}
    return delays.get(attempt, 10.0)


def _build_make_story_automation_override(
    *,
    story_id: str,
    target_chars: int,
    chapter_no: int | None = None,
    chapter_title: str = "",
) -> str:
    lines = [
        "[자동 실행 모드 override]",
        f"- story_id: {story_id}",
        f"- 목표 분량: 챕터당 약 {target_chars}자",
        "- 지금은 대화형 세션이 아니라 배치 실행이다.",
        "- 사용자에게 질문하지 말고, 분량 선택을 다시 묻지 말라.",
        "- '다음' 입력을 기다리지 말라.",
        "- 지정된 출력만 바로 생성하라.",
        "- 설명이나 운영 안내 없이 결과 본문만 출력하라.",
        "- 코드블록 마크다운을 사용하지 말라.",
    ]
    if chapter_no is not None:
        lines.extend([
            f"- 이번 호출에서 작성할 대상은 Chapter {chapter_no} 하나뿐이다.",
            "- 다른 챕터를 미리 쓰거나 요약하지 말라.",
            f"- 출력은 반드시 'Chapter {chapter_no} : (제목)' 형식으로 시작하라.",
        ])
    if chapter_title:
        lines.append(f"- 이번 챕터 제목: {chapter_title}")
    return "\n".join(lines)


def _build_make_story_prompt(
    *,
    root: Path,
    story_id: str,
    synopsis_text: str,
    target_chars: int,
    chapter_no: int | None = None,
    chapter_title: str = "",
    chapter_outline: str = "",
    previous_chapter_text: str = "",
) -> str:
    template = _load_prompt_template(root, "prompts/make_story.txt")
    override = _build_make_story_automation_override(
        story_id=story_id,
        target_chars=target_chars,
        chapter_no=chapter_no,
        chapter_title=chapter_title,
    )
    payload = {
        "story_id": story_id,
        "target_chars_per_chapter": target_chars,
        "chapter_no": chapter_no,
        "chapter_title": chapter_title,
        "chapter_outline": chapter_outline,
        "previous_chapter_text": previous_chapter_text,
        "full_synopsis": synopsis_text,
    }
    return (
        template
        + "\n\n"
        + override
        + "\n\n[입력]\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _parse_synopsis_chapters(synopsis_text: str) -> list[dict[str, str | int]]:
    lines = synopsis_text.splitlines()
    chapter_starts: list[tuple[int, int, str]] = []
    pattern = re.compile(
        r"^\s*(?:#+\s*)?(?:\*\*)?(\d+)\s*챕터\s*[:：]\s*(.+?)(?:\*\*)?\s*$"
    )
    for idx, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            chapter_starts.append((idx, int(m.group(1)), m.group(2).strip()))

    if not chapter_starts:
        raise RuntimeError("시놉시스에서 'N챕터: 제목' 형식을 찾지 못했습니다.")

    chapters: list[dict[str, str | int]] = []
    for i, (start_idx, no, title) in enumerate(chapter_starts):
        end_idx = chapter_starts[i + 1][0] if i + 1 < len(chapter_starts) else len(lines)
        body_lines = lines[start_idx + 1:end_idx]
        outline = "\n".join(body_lines).strip()
        block = "\n".join(lines[start_idx:end_idx]).strip()
        chapters.append({
            "chapter_no": no,
            "chapter_title": title,
            "chapter_outline": outline,
            "chapter_block": block,
        })
    return chapters

def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()
    return cleaned


def _sanitize_synopsis_output(text: str) -> str:
    cleaned = _strip_code_fences(text)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in cleaned.splitlines()]

    normalized: list[str] = []
    chapter_pattern = re.compile(
        r"^\s*(?:#+\s*)?(?:\*\*)?(?:Chapter\s*)?(\d+)\s*(?:챕터)?\s*[:：.\-]\s*(.+?)(?:\*\*)?\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\s*#+\s+", stripped) and not re.search(r"\d+\s*챕터", stripped):
            continue
        if stripped.startswith("**") and stripped.endswith("**") and len(stripped) >= 4:
            line = stripped[2:-2].strip()
        m = chapter_pattern.match(line)
        if m:
            normalized.append(f"{int(m.group(1))}챕터: {m.group(2).strip()}")
        else:
            normalized.append(line)

    cleaned = "\n".join(normalized)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _normalize_story_header_line(header_line: str, expected_no: int, expected_title: str) -> str:
    m = re.match(
        r"^\s*(?:Chapter\s*)?(\d+)\s*[:：.\-]\s*(.+?)\s*$",
        header_line.strip(),
        re.IGNORECASE,
    )
    if m:
        title = m.group(2).strip() or expected_title
        return f"Chapter {int(m.group(1))} : {title}"
    return f"Chapter {expected_no} : {expected_title}"


def _sanitize_story_chapter_output(text: str, expected_no: int, expected_title: str) -> str:
    cleaned = _strip_code_fences(text)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in cleaned.splitlines()]

    while lines and (
        not lines[0].strip()
        or lines[0].strip().startswith("[")
        or lines[0].strip().startswith("설명")
        or lines[0].strip().startswith("다음")
    ):
        lines.pop(0)

    header_idx = None
    header_pattern = re.compile(r"^\s*(?:Chapter\s*)?\d+\s*[:：.\-]\s*.+$", re.IGNORECASE)
    for idx, line in enumerate(lines):
        if header_pattern.match(line.strip()):
            header_idx = idx
            break

    body_lines: list[str]
    if header_idx is None:
        header = f"Chapter {expected_no} : {expected_title}"
        body_lines = lines
    else:
        header = _normalize_story_header_line(lines[header_idx], expected_no, expected_title)
        body_lines = lines[header_idx + 1:]

    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)

    body = "\n".join(body_lines).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    if not body:
        raise RuntimeError(f"Chapter {expected_no} 본문이 비어 있습니다.")
    return f"{header}\n\n{body}".strip()


def _parse_story_chapter_blocks(story_text: str) -> list[dict[str, str | int]]:
    text = story_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    header_pattern = re.compile(
        r"(?m)^\s*Chapter\s+(\d+)\s*:\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    matches = list(header_pattern.finditer(text))
    if not matches:
        return []

    blocks: list[dict[str, str | int]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        blocks.append({
            "chapter_no": int(match.group(1)),
            "chapter_title": match.group(2).strip(),
            "text": block,
        })
    return blocks


def _generate_story_chapter_with_retry(
    *,
    root: Path,
    story_id: str,
    synopsis_text: str,
    target_chars: int,
    chapter_no: int,
    chapter_title: str,
    chapter_outline: str,
    previous_chapter_text: str,
    llm_model: str,
    max_attempts: int = 3,
) -> str:
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                print(f"[INFO] make-story retry {attempt}/{max_attempts} -> Chapter {chapter_no}")
            return _generate_story_chapter(
                root=root,
                story_id=story_id,
                synopsis_text=synopsis_text,
                target_chars=target_chars,
                chapter_no=chapter_no,
                chapter_title=chapter_title,
                chapter_outline=chapter_outline,
                previous_chapter_text=previous_chapter_text,
                llm_model=llm_model,
            )
        except Exception as err:
            last_err = err
            print(f"[WARN] Chapter {chapter_no} generation failed ({attempt}/{max_attempts}): {err}")
            if attempt < max_attempts and _is_transient_llm_error(err):
                delay = _llm_retry_delay_sec(attempt)
                print(f"[INFO] transient LLM error, retrying Chapter {chapter_no} in {delay:.1f}s")
                time.sleep(delay)
    assert last_err is not None
    raise RuntimeError(
        f"Chapter {chapter_no} 생성이 {max_attempts}회 연속 실패했습니다. 다음 실행 시 이 챕터부터 재개합니다."
    ) from last_err


def _generate_synopsis_file_with_retry(
    root: Path,
    synopsis_input: str,
    out_path: Path,
    *,
    llm_model: str,
    max_attempts: int = 3,
) -> None:
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                print(f"[INFO] synopsis retry {attempt}/{max_attempts}")
            _generate_synopsis_file(root, synopsis_input, out_path, llm_model=llm_model)
            return
        except Exception as err:
            last_err = err
            print(f"[WARN] synopsis generation failed ({attempt}/{max_attempts}): {err}")
            if attempt < max_attempts and _is_transient_llm_error(err):
                delay = _llm_retry_delay_sec(attempt)
                print(f"[INFO] transient LLM error, retrying synopsis in {delay:.1f}s")
                time.sleep(delay)
    assert last_err is not None
    raise RuntimeError(
        f"시놉시스 생성이 {max_attempts}회 연속 실패했습니다."
    ) from last_err

EXAMPLES_TEXT = "\n".join([
    "선호 기본 실행 예시:",
    "  python -m yadam.cli --story-id story00",
    "  python -m yadam.cli --story-id story00 --make_synopsis",
    "  python -m yadam.cli --story-id story00 --make-story",
    "  python -m yadam.cli --story-id story00 --make-story 1000",
    "  python -m yadam.cli --title '\"그 신랑은 아니지라\" 바보 만득이 한마디에 혼담이 바뀌었다'",
    "  python -m yadam.cli --title '\"그 신랑은 아니지라\" 바보 만득이 한마디에 혼담이 바뀌었다' --non-interactive",
    "  python -m yadam.cli --story-id story00 --clean-workdir",
    "  python -m yadam.cli --story-id story00 --non-interactive",
    "  python -m yadam.cli --story-id story00 --non-interactive --clean-workdir",
    "",
    "추가 예시:",
    "  python -m yadam.cli --story-id story00 --image-api gemini_flash_image",
    "  python -m yadam.cli --story-id story00 --image-api comfyui --image-model z_image_turbo_bf16.safetensors",
    "  python -m yadam.cli --story-id story00 --image-api comfyui --comfy-workflow ~/comfy/flux_api.json",
    "  python -m yadam.cli --story-id story00 --vrew-clip-max-chars 40",
])


class FriendlyArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(
            2,
            f"{self.prog}: error: {message}\n\n"
            f"간단 예시:\n"
            f"  python -m yadam.cli --story-id story00\n"
            f"  python -m yadam.cli --story-id story00 --non-interactive\n\n"
            f"전체 도움말: python -m yadam.cli --help\n",
        )


def _default_comfy_workflow_for_model(root: Path, model: str) -> Path:
    model_l = (model or "").strip().lower()
    if ("z_image" in model_l) or ("z-image" in model_l):
        name = DEFAULT_COMFY_WORKFLOW_ZIMAGE_TURBO
    elif "flux" in model_l:
        name = DEFAULT_COMFY_WORKFLOW_FLUX_BASE
    else:
        name = DEFAULT_COMFY_WORKFLOW_SDXL_FAST
    return root / "yadam" / "config" / "comfy_workflows" / name


def main() -> None:
    ap = FriendlyArgumentParser(
        description="YADAM 파이프라인 CLI: 대본 분석, 이미지 생성, .vrew export",
        epilog=EXAMPLES_TEXT,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    ap.add_argument("--story-id", required=False, help="예: story00")
    ap.add_argument(
        "--title",
        default="",
        help="제목/훅 입력 문구. 지정 시 prompts/make_synopsis.txt를 사용해 새 stories/storyNN.title, stories/storyNN.synopsis를 생성",
    )
    ap.add_argument(
        "--synopsis",
        default="",
        help=argparse.SUPPRESS,
    )
    ap.add_argument(
        "--make_synopsis",
        action="store_true",
        help="stories/<story-id>.title을 읽어 stories/<story-id>.synopsis만 생성",
    )
    ap.add_argument(
        "--make_sysnopsis",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    ap.add_argument(
        "--make-story",
        nargs="?",
        const=500,
        default=0,
        type=int,
        choices=[500, 1000],
        help="stories/<story-id>.synopsis를 입력으로 stories/<story-id>.txt 생성. 값 생략 시 500, 허용값: 500|1000",
    )
    ap.add_argument("--project-root", default=".", help="프로젝트 루트(기본: 현재 폴더)")
    ap.add_argument("--profiles", default="yadam/config/default_profiles.yaml")
    ap.add_argument("--era", default="joseon_yadam")
    ap.add_argument("--style", default="k_webtoon")
    ap.add_argument(
        "--llm-model",
        default="",
        help=f"텍스트 LLM 모델 오버라이드. 비우면 기본값 {DEFAULT_TEXT_LLM_MODEL} 사용",
    )
    ap.add_argument(
        "--image-api",
        choices=["vertex_imagen", "gemini_flash_image", "comfyui"],
        default="vertex_imagen",
        help="이미지 생성 API 선택 (기본: vertex_imagen)",
    )
    ap.add_argument(
        "--image-model",
        default="",
        help="이미지 모델 오버라이드. 비우면 API별 기본 모델 사용",
    )
    ap.add_argument(
        "--create-empty-story",
        action="store_true",
        help="stories/<story-id>.txt 가 없으면 빈 파일로 생성(기본은 에러)",
    )
    ap.add_argument(
        "--non-interactive",
        action="store_true",
        help="대화형 확인 없이 끝까지 실행(기본은 단계별 확인)",
    )
    ap.add_argument(
        "--clean-workdir",
        action="store_true",
        help="실행 전에 work/<story-id>/ 를 삭제하고 처음부터 재생성",
    )
    ap.add_argument(
        "--through-tag-scene",
        action="store_true",
        help="대본 정규화, scene 분할, seed 추출, tag_scene까지만 수행하고 중단",
    )
    ap.add_argument(
        "--through-place-refs",
        action="store_true",
        help="캐릭터/장소 레퍼런스 이미지(7/8단계)까지만 수행하고 clip/export 전에 중단",
    )
    ap.add_argument(
        "--through-clips",
        action="store_true",
        help="clip 이미지 생성(9단계)까지만 수행하고 export 전에 중단",
    )
    ap.add_argument(
        "--vrew-clip-max-chars",
        type=int,
        default=30,
        help=".vrew clip 자막 분할 최대 글자 수 (기본: 30)",
    )
    ap.add_argument(
        "--comfy-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI 서버 URL (기본: http://127.0.0.1:8188)",
    )
    ap.add_argument(
        "--comfy-workflow",
        default="",
        help="ComfyUI API workflow JSON 경로(미지정 시 프로젝트 기본 템플릿 사용, placeholder 지원)",
    )
    ap.add_argument(
        "--comfy-api-key",
        default="",
        help="ComfyUI Cloud API 키(미지정 시 COMFYUI_API_KEY 환경변수 사용)",
    )
    ap.add_argument(
        "--comfy-api-key-header",
        default="X-API-Key",
        help="ComfyUI API 키 헤더명(기본: X-API-Key)",
    )
    ap.add_argument(
        "--comfy-timeout-sec",
        type=int,
        default=300,
        help="ComfyUI 이미지 생성 결과 대기 timeout 초(기본: 300)",
    )
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    synopsis_input = (args.title or args.synopsis or "").strip()

    stories_dir = root / "stories"
    work_dir = root / "work"
    _ensure_dir(stories_dir)
    _ensure_dir(work_dir)

    if synopsis_input:
        story_id = _run_synopsis_mode(root, synopsis_input)
        _enable_run_log(work_dir, story_id)
        print(f"[INFO] step 1/3: generating synopsis for {story_id}")
        if not _run_story_synopsis_mode(
            root,
            story_id,
            non_interactive=args.non_interactive,
            llm_model=_resolve_llm_model(args.llm_model),
        ):
            return
        if args.non_interactive:
            print(f"[INFO] step 2/3: generating story for {story_id}")
            if not _run_make_story_mode(
                root,
                story_id,
                target_chars=500,
                non_interactive=True,
                llm_model=_resolve_llm_model(args.llm_model),
            ):
                return
            print(f"[INFO] step 3/3: running image and .vrew pipeline for {story_id}")
            _run_full_pipeline_mode(root, story_id, args)
        return

    story_id = (args.story_id or "").strip()
    if not story_id:
        raise ValueError("--story-id 또는 --title 중 하나는 반드시 필요합니다.")
    if "/" in story_id or "\\" in story_id or ".." in story_id:
        raise ValueError(f"invalid story-id: {story_id}")

    _enable_run_log(work_dir, story_id)
    prefer_existing_inputs = bool(args.through_tag_scene or args.through_place_refs or args.through_clips)

    if args.make_synopsis or args.make_sysnopsis:
        print(f"[INFO] step 1/1: generating synopsis for {story_id}")
        _run_story_synopsis_mode(
            root,
            story_id,
            non_interactive=args.non_interactive,
            llm_model=_resolve_llm_model(args.llm_model),
            prefer_existing=prefer_existing_inputs,
        )
        return

    if args.make_story:
        print(f"[INFO] step 1/1: generating story for {story_id}")
        _run_make_story_mode(
            root,
            story_id,
            target_chars=int(args.make_story or 500),
            non_interactive=args.non_interactive,
            llm_model=_resolve_llm_model(args.llm_model),
            prefer_existing=prefer_existing_inputs,
        )
        return

    print(f"[INFO] step 1/3: generating synopsis for {story_id}")
    if not _run_story_synopsis_mode(
        root,
        story_id,
        non_interactive=args.non_interactive,
        llm_model=_resolve_llm_model(args.llm_model),
        prefer_existing=prefer_existing_inputs,
    ):
        return
    skip_story_generation = False
    if not args.non_interactive:
        proceed = _confirm_continue_default_yes_or_all("시놉시스 생성을 확인했습니다. story 생성으로 진행할까요?")
        if proceed == "no":
            skip_story_generation = True
            print("[INFO] skip story generation by user choice")
        if proceed == "all":
            args.non_interactive = True
            print("[INFO] switch to non-interactive mode for remaining steps")

    if not skip_story_generation:
        print(f"[INFO] step 2/3: generating story for {story_id}")
        if not _run_make_story_mode(
            root,
            story_id,
            target_chars=500,
            non_interactive=args.non_interactive,
            llm_model=_resolve_llm_model(args.llm_model),
            prefer_existing=prefer_existing_inputs,
        ):
            return
    else:
        story_path = root / "stories" / f"{story_id}.txt"
        if not story_path.exists():
            print(f"[INFO] story generation was skipped, but story file is missing: {story_path}")
            print("[INFO] stopped before image/.vrew pipeline")
            return
        print(f"[INFO] step 2/3: skipped (reuse existing story: {story_path})")

    if not args.non_interactive:
        proceed = _confirm_continue_default_yes_or_all("대본 생성을 확인했습니다. 이미지 및 .vrew 생성을 진행할까요?")
        if proceed == "no":
            print("[INFO] stopped after story generation")
            return
        if proceed == "all":
            args.non_interactive = True
            print("[INFO] switch to non-interactive mode for remaining steps")

    print(f"[INFO] step 3/3: running image and .vrew pipeline for {story_id}")
    _run_full_pipeline_mode(root, story_id, args)


def _run_synopsis_mode(root: Path, synopsis_input: str) -> str:
    synopsis_dir = root / "synopsis"
    stories_dir = root / "stories"
    _ensure_dir(stories_dir)
    next_no = _next_synopsis_no(root, synopsis_dir)
    story_id = f"story{next_no:02d}"
    title_path = stories_dir / f"story{next_no:02d}.title"
    _atomic_write_text(title_path, synopsis_input.strip() + "\n")
    print(f"[INFO] title saved: {title_path}")
    return story_id


def _run_story_synopsis_mode(
    root: Path,
    story_id: str,
    *,
    non_interactive: bool,
    llm_model: str,
    prefer_existing: bool = False,
) -> bool:
    stories_dir = root / "stories"
    title_path = stories_dir / f"{story_id}.title"
    synopsis_path = stories_dir / f"{story_id}.synopsis"
    title_hash_path = stories_dir / f".{story_id}.title.sha256"

    if not title_path.exists():
        raise FileNotFoundError(
            f"시놉시스 생성을 위한 제목 파일이 없습니다: {title_path}\n"
            f"먼저 {title_path.name} 파일을 만들고 제목 한 줄을 넣으세요."
        )

    title_text = title_path.read_text(encoding="utf-8").strip()
    if not title_text:
        raise RuntimeError(f"제목 파일이 비어 있습니다: {title_path}")
    title_hash = _text_sha256(title_text)

    if synopsis_path.exists():
        print(f"[INFO] synopsis file already exists: {synopsis_path}")
        if prefer_existing:
            print(f"[INFO] reuse existing synopsis without regeneration: {synopsis_path}")
            if not title_hash_path.exists():
                _atomic_write_text(title_hash_path, title_hash + "\n")
            return True
        if non_interactive:
            previous_hash = ""
            if title_hash_path.exists():
                previous_hash = title_hash_path.read_text(encoding="utf-8").strip()
            if previous_hash == title_hash:
                print(f"[INFO] synopsis up-to-date: {synopsis_path}")
                return True
        if (not non_interactive) and (not _confirm_overwrite(synopsis_path)):
            print(f"[INFO] keep existing synopsis and continue: {synopsis_path}")
            return True

    print(f"[INFO] generating synopsis from title: {title_path.name}")
    _generate_synopsis_file_with_retry(
        root,
        title_text,
        synopsis_path,
        llm_model=llm_model,
    )
    _atomic_write_text(title_hash_path, title_hash + "\n")
    return True


def _run_make_story_mode(
    root: Path,
    story_id: str,
    *,
    target_chars: int,
    non_interactive: bool,
    llm_model: str,
    prefer_existing: bool = False,
) -> bool:
    stories_dir = root / "stories"
    synopsis_path = stories_dir / f"{story_id}.synopsis"
    story_path = stories_dir / f"{story_id}.txt"
    story_source_hash_path = stories_dir / f".{story_id}.story_source.sha256"

    if not synopsis_path.exists():
        raise FileNotFoundError(
            f"스토리 생성을 위한 시놉시스 파일이 없습니다: {synopsis_path}\n"
            f"먼저 `python -m yadam.cli --story-id {story_id}` 로 시놉시스를 생성하세요."
        )

    synopsis_text = synopsis_path.read_text(encoding="utf-8").strip()
    if not synopsis_text:
        raise RuntimeError(f"시놉시스 파일이 비어 있습니다: {synopsis_path}")
    synopsis_hash = _text_sha256(synopsis_text)
    generated_chapters: list[str] = []
    previous_chapter_text = ""
    start_index = 0

    if story_path.exists():
        print(f"[INFO] story file already exists: {story_path}")
        existing_text = story_path.read_text(encoding="utf-8").strip()
        existing_blocks = _parse_story_chapter_blocks(existing_text)
        previous_hash = ""
        if story_source_hash_path.exists():
            previous_hash = story_source_hash_path.read_text(encoding="utf-8").strip()

        if prefer_existing and existing_blocks:
            last_no = int(existing_blocks[-1]["chapter_no"])
            print(f"[INFO] reuse existing story without regeneration through Chapter {last_no}: {story_path}")
            if not story_source_hash_path.exists():
                _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")
            return True

    chapters = _parse_synopsis_chapters(synopsis_text)

    if story_path.exists():
        existing_text = story_path.read_text(encoding="utf-8").strip()
        existing_blocks = _parse_story_chapter_blocks(existing_text)
        previous_hash = ""
        if story_source_hash_path.exists():
            previous_hash = story_source_hash_path.read_text(encoding="utf-8").strip()

        if previous_hash and previous_hash != synopsis_hash:
            print(f"[INFO] synopsis changed; story will be regenerated: {story_path}")
            if (not non_interactive) and (not _confirm_overwrite(story_path)):
                print("[INFO] story generation cancelled by user")
                return False
            story_path.write_text("", encoding="utf-8")
            _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")
            generated_chapters = []
            previous_chapter_text = ""
            start_index = 0
            existing_blocks = []

        if existing_blocks:
            if not previous_hash:
                if len(existing_blocks) >= len(chapters):
                    _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")
                    previous_hash = synopsis_hash
                else:
                    print(f"[INFO] story source hash missing; story will be regenerated: {story_path}")
                    if (not non_interactive) and (not _confirm_overwrite(story_path)):
                        print("[INFO] story generation cancelled by user")
                        return False
                    story_path.write_text("", encoding="utf-8")
                    _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")
                    generated_chapters = []
                    previous_chapter_text = ""
                    start_index = 0
                    existing_blocks = []

        if existing_blocks:
            generated_chapters = [str(block["text"]) for block in existing_blocks]
            previous_chapter_text = generated_chapters[-1]
            last_no = int(existing_blocks[-1]["chapter_no"])
            start_index = len(existing_blocks)
            if start_index >= len(chapters):
                if previous_hash == synopsis_hash:
                    print(f"[INFO] story up-to-date through Chapter {last_no}: {story_path}")
                else:
                    print(f"[INFO] story already complete through Chapter {last_no}: {story_path}")
                return True
            print(f"[INFO] resuming from Chapter {last_no + 1} (last success: Chapter {last_no})")
        else:
            if previous_hash == synopsis_hash and non_interactive:
                print(f"[INFO] story source unchanged but existing file is not resumable; regenerating: {story_path}")
                story_path.write_text("", encoding="utf-8")
                _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")
            elif (not non_interactive) and (not _confirm_overwrite(story_path)):
                print("[INFO] story generation cancelled by user")
                return False
            else:
                story_path.write_text("", encoding="utf-8")
                _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")

    if not story_path.exists():
        _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")

    for idx, chapter in enumerate(chapters[start_index:], start=start_index + 1):
        chapter_no = int(chapter["chapter_no"])
        chapter_title = str(chapter["chapter_title"])
        chapter_outline = str(chapter["chapter_outline"])
        print(f"[INFO] make-story {idx}/{len(chapters)} -> Chapter {chapter_no}: {chapter_title}")
        chapter_text = _generate_story_chapter_with_retry(
            root=root,
            story_id=story_id,
            synopsis_text=synopsis_text,
            target_chars=target_chars,
            chapter_no=chapter_no,
            chapter_title=chapter_title,
            chapter_outline=chapter_outline,
            previous_chapter_text=previous_chapter_text,
            llm_model=llm_model,
        )
        generated_chapters.append(chapter_text)
        previous_chapter_text = chapter_text
        _atomic_write_text(story_path, "\n\n".join(generated_chapters).strip() + "\n")

    print(f"[INFO] story saved: {story_path}")
    _atomic_write_text(story_source_hash_path, synopsis_hash + "\n")
    return True


def _run_full_pipeline_mode(root: Path, story_id: str, args: argparse.Namespace) -> None:
    stories_dir = root / "stories"
    work_dir = root / "work"
    script_path = stories_dir / f"{story_id}.txt"
    if not script_path.exists():
        raise FileNotFoundError(
            f"입력 대본 파일이 없습니다: {script_path}\n"
            f"먼저 --make-story 단계로 {script_path.name}를 생성하세요."
        )

    base_dir = work_dir / story_id

    if args.clean_workdir:
        work_dir_real = work_dir.resolve()
        base_dir_real = base_dir.resolve()

        try:
            base_dir_real.relative_to(work_dir_real)
        except ValueError:
            raise RuntimeError(
                f"--clean-workdir safety check failed: {base_dir_real} is not under {work_dir_real}"
            )
        if base_dir_real == work_dir_real:
            raise RuntimeError("--clean-workdir safety check failed: target is work dir itself")

        print(f"[INFO] --clean-workdir target exists={base_dir_real.exists()}: {base_dir_real}")
        if args.non_interactive:
            if base_dir_real.exists():
                shutil.rmtree(base_dir_real)
        else:
            if _confirm_clean_workdir(base_dir_real):
                if base_dir_real.exists():
                    shutil.rmtree(base_dir_real)

    _ensure_dir(base_dir)

    from yadam.pipeline.orchestrator import Orchestrator, PipelineConfig
    from yadam.export.vrew_exporter import VrewFileExporter
    from yadam.gen.gemini_client import VertexImagenClient, GeminiFlashImageClient
    from yadam.gen.comfy_client import ComfyUIImageClient

    cfg = PipelineConfig(
        base_dir=str(base_dir),
        profiles_yaml=str(root / args.profiles),
        era_profile=args.era,
        style_profile=args.style,
        input_script_path=str(script_path),
        json_name="project.json",
        interactive=(not args.non_interactive),
        llm_model=_resolve_llm_model(args.llm_model),
        stop_after_tag_scene=bool(args.through_tag_scene),
        stop_after_place_refs=bool(args.through_place_refs),
        stop_after_clips=bool(args.through_clips),
        vrew_clip_max_chars=max(1, int(args.vrew_clip_max_chars)),
    )

    if args.image_api == "vertex_imagen":
        model = args.image_model.strip() or DEFAULT_VERTEX_IMAGE_MODEL
        img_client = VertexImagenClient(model=model)
        workflow_path = ""
    elif args.image_api == "gemini_flash_image":
        requested_model = args.image_model.strip() or DEFAULT_GEMINI_IMAGE_MODEL
        model, remapped_from = resolve_gemini_image_model(requested_model)
        img_client = GeminiFlashImageClient(model=model)
        workflow_path = ""
    else:
        model = args.image_model.strip() or DEFAULT_COMFY_MODEL
        default_comfy_workflow = _default_comfy_workflow_for_model(root, model)
        workflow_path = (
            args.comfy_workflow.strip()
            or os.getenv("COMFYUI_WORKFLOW_PATH", "").strip()
            or str(default_comfy_workflow)
        )
        if not workflow_path:
            raise ValueError(
                "comfyui 사용 시 workflow가 필요합니다. "
                "--comfy-workflow <path> 또는 COMFYUI_WORKFLOW_PATH 환경변수를 설정하세요."
            )
        if not Path(workflow_path).expanduser().exists():
            raise FileNotFoundError(f"comfy workflow 파일을 찾을 수 없습니다: {workflow_path}")
        img_client = ComfyUIImageClient(
            base_url=args.comfy_url.strip(),
            workflow_path=workflow_path,
            model=model,
            timeout_sec=max(10, int(args.comfy_timeout_sec)),
            api_key=args.comfy_api_key.strip() or os.getenv("COMFYUI_API_KEY", "").strip(),
            api_key_header=args.comfy_api_key_header.strip(),
        )

    print(f"[INFO] starting image and .vrew pipeline for {story_id}")
    print(f"[INFO] llm_model={cfg.llm_model}")
    print(f"[INFO] through_tag_scene={cfg.stop_after_tag_scene}")
    print(f"[INFO] through_place_refs={cfg.stop_after_place_refs}")
    print(f"[INFO] through_clips={cfg.stop_after_clips}")
    print(f"[INFO] image_api={args.image_api}, image_model={model}, image_client={img_client.__class__.__name__}")
    if args.image_api == "gemini_flash_image" and 'remapped_from' in locals() and remapped_from:
        print(f"[WARN] requested unsupported Gemini image model '{remapped_from}', fallback to '{model}'")
    if args.image_api == "comfyui":
        print(f"[INFO] comfy_url={args.comfy_url.strip()}, comfy_workflow={workflow_path}")
    exporter = VrewFileExporter()

    orch = Orchestrator(cfg, img_client=img_client, exporter=exporter)
    orch.run()


def _generate_synopsis_file(root: Path, synopsis_input: str, out_path: Path, *, llm_model: str) -> None:
    from google import genai
    from google.genai import types

    prompts_dir = root / "prompts"

    prompt_path = prompts_dir / "make_synopsis.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"시놉시스 프롬프트 파일이 없습니다: {prompt_path}")

    template = prompt_path.read_text(encoding="utf-8").strip()
    if not template:
        raise RuntimeError(f"시놉시스 프롬프트가 비어 있습니다: {prompt_path}")

    payload = {
        "input_title_or_hook": synopsis_input,
        "output_requirements": [
            "조선시대 야담 채널용 20챕터 시놉시스를 작성할 것",
            "각 챕터에는 소제목을 붙일 것",
            "출력은 바로 파일로 저장 가능한 평문 본문만 작성할 것",
        ],
    }
    user_text = (
        template
        + "\n\n[입력]\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    client = genai.Client()
    print(f"[INFO] synopsis LLM request -> {llm_model}")
    resp = client.models.generate_content(
        model=llm_model,
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=user_text)],
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.7,
        ),
    )
    text = _sanitize_synopsis_output((getattr(resp, "text", None) or "").strip())
    if not text:
        raise RuntimeError("시놉시스 LLM 응답이 비어 있습니다.")

    _atomic_write_text(out_path, text + "\n")
    print(f"[INFO] synopsis saved: {out_path}")


def _generate_story_chapter(
    *,
    root: Path,
    story_id: str,
    synopsis_text: str,
    target_chars: int,
    chapter_no: int,
    chapter_title: str,
    chapter_outline: str,
    previous_chapter_text: str,
    llm_model: str,
) -> str:
    from google import genai
    from google.genai import types

    prompt = _build_make_story_prompt(
        root=root,
        story_id=story_id,
        synopsis_text=synopsis_text,
        target_chars=target_chars,
        chapter_no=chapter_no,
        chapter_title=chapter_title,
        chapter_outline=chapter_outline,
        previous_chapter_text=previous_chapter_text[-1500:],
    )

    client = genai.Client()
    print(f"[INFO] chapter LLM request -> {llm_model} (Chapter {chapter_no})")
    resp = client.models.generate_content(
        model=llm_model,
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.7,
        ),
    )
    text = _sanitize_story_chapter_output(
        (getattr(resp, "text", None) or "").strip(),
        chapter_no,
        chapter_title,
    )
    if not text:
        raise RuntimeError(f"Chapter {chapter_no} 대본 생성 응답이 비어 있습니다.")
    return text


def _next_synopsis_no(root: Path, synopsis_dir: Path) -> int:
    nums = []
    for pattern in ("story*.synopsis", "storyp*.synopsis"):
        for p in synopsis_dir.glob(pattern):
            stem = p.stem
            digits = "".join(ch for ch in stem if ch.isdigit())
            if digits:
                nums.append(int(digits))

    stories_dir = root / "stories"
    if stories_dir.exists():
        for p in stories_dir.glob("story*.synopsis"):
            stem = p.stem
            digits = "".join(ch for ch in stem if ch.isdigit())
            if digits:
                nums.append(int(digits))
        for p in stories_dir.glob("story*.txt"):
            stem = p.stem
            digits = "".join(ch for ch in stem if ch.isdigit())
            if digits:
                nums.append(int(digits))

    return (max(nums) + 1) if nums else 1


if __name__ == "__main__":
    main()
