# yadam/cli.py
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


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


def _load_prompt_template(root: Path, relative_path: str) -> str:
    path = root / relative_path
    if not path.exists():
        raise FileNotFoundError(f"프롬프트 파일이 없습니다: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"프롬프트 파일이 비어 있습니다: {path}")
    return text


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
    pattern = re.compile(r"^\s*(\d+)\s*챕터\s*[:：]\s*(.+?)\s*$")
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
        r"^\s*(?:Chapter\s*)?(\d+)\s*(?:챕터)?\s*[:：.\-]\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    for line in lines:
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
            )
        except Exception as err:
            last_err = err
            print(f"[WARN] Chapter {chapter_no} generation failed ({attempt}/{max_attempts}): {err}")
    assert last_err is not None
    raise RuntimeError(
        f"Chapter {chapter_no} 생성이 {max_attempts}회 연속 실패했습니다. 다음 실행 시 이 챕터부터 재개합니다."
    ) from last_err

EXAMPLES_TEXT = "\n".join([
    "선호 기본 실행 예시:",
    "  python -m yadam.cli --story-id story00",
    "  python -m yadam.cli --story-id story00 --make-story",
    "  python -m yadam.cli --story-id story00 --make-story 1000",
    "  python -m yadam.cli --synopsis '\"그 신랑은 아니지라\" 바보 만득이 한마디에 혼담이 바뀌었다'",
    "  python -m yadam.cli --story-id story00 --clean-workdir",
    "  python -m yadam.cli --story-id story00 --non-interactive",
    "  python -m yadam.cli --story-id story00 --non-interactive --clean-workdir",
    "",
    "추가 예시:",
    "  python -m yadam.cli --story-id story00 --image-api gemini_flash_image",
    "  python -m yadam.cli --story-id story00 --image-api comfyui --comfy-workflow ~/comfy/flux_api.json",
    "  python -m yadam.cli --story-id story00 --image-api comfyui --image-model sd_xl_base_1.0.safetensors",
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


def main() -> None:
    ap = FriendlyArgumentParser(
        description="YADAM 파이프라인 CLI: 대본 분석, 이미지 생성, .vrew export",
        epilog=EXAMPLES_TEXT,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    ap.add_argument("--story-id", required=False, help="예: story00")
    ap.add_argument(
        "--synopsis",
        default="",
        help="시놉시스 생성용 입력 문구. 지정 시 prompts/make_synopsis.txt를 사용해 stories/storyNN.synopsis 파일을 생성",
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
        "--comfy-timeout-sec",
        type=int,
        default=300,
        help="ComfyUI 이미지 생성 결과 대기 timeout 초(기본: 300)",
    )
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    synopsis_input = args.synopsis.strip()

    if synopsis_input:
        _run_synopsis_mode(root, synopsis_input)
        return

    story_id = (args.story_id or "").strip()
    if not story_id:
        raise ValueError("--story-id 또는 --synopsis 중 하나는 반드시 필요합니다.")
    if "/" in story_id or "\\" in story_id or ".." in story_id:
        raise ValueError(f"invalid story-id: {story_id}")

    # stories/ 와 work/ 디렉토리 자동 생성
    stories_dir = root / "stories"
    work_dir = root / "work"
    _ensure_dir(stories_dir)
    _ensure_dir(work_dir)

    if args.make_story:
        _run_make_story_mode(
            root,
            story_id,
            target_chars=int(args.make_story or 500),
            non_interactive=args.non_interactive,
        )
        return

    _run_story_synopsis_mode(root, story_id, non_interactive=args.non_interactive)
    return

    script_path = stories_dir / f"{story_id}.txt"
    if not script_path.exists():
        if args.create_empty_story:
            script_path.write_text("", encoding="utf-8")
        else:
            raise FileNotFoundError(
                f"입력 대본 파일이 없습니다: {script_path}\n"
                f"1) stories/{story_id}.txt 를 만들거나\n"
                f"2) --create-empty-story 옵션으로 빈 파일 생성 후 편집하세요."
            )

    base_dir = work_dir / story_id  # 결과물은 work/<story-id>/ 아래로

    if args.clean_workdir:
        # ✅ work/<story-id>/ 아래만 삭제 허용 (탈출 방지)
        work_dir_real = work_dir.resolve()
        base_dir_real = base_dir.resolve()

        try:
            base_dir_real.relative_to(work_dir_real)
        except ValueError:
            raise RuntimeError(
                f"--clean-workdir safety check failed: {base_dir_real} is not under {work_dir_real}"
            )

        # ✅ 추가 안전: story-id가 work 자체를 가리키거나 상위가 되는 경우 방지
        if base_dir_real == work_dir_real:
            raise RuntimeError("--clean-workdir safety check failed: target is work dir itself")

        # ✅ 사용자 확인: --clean-workdir가 켜졌으면 무조건 y/n 확인
        #    (폴더가 없어도 물어봄: y면 "있으면 삭제", 없으면 "그대로 진행")
        print(f"[INFO] --clean-workdir target exists={base_dir_real.exists()}: {base_dir_real}")

        # ✅ 사용자 확인: --clean-workdir가 켜졌으면 무조건 y/n 확인
        # y면 "있으면 삭제", 없으면 "없으니 그대로 진행"
        # n이면 삭제하지 않고 그대로 진행
        if _confirm_clean_workdir(base_dir_real):
            if base_dir_real.exists():
                shutil.rmtree(base_dir_real)

    _ensure_dir(base_dir)  # story별 디렉토리 자동 생성

    # 무거운 의존성은 실제 실행 직전에 import한다.
    # 이렇게 하면 현재 환경에서 --help 검증이 가능해진다.
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
        interactive=(not args.non_interactive),  # ✅ 기본 interactive
        vrew_clip_max_chars=max(1, int(args.vrew_clip_max_chars)),
    )

    if args.image_api == "vertex_imagen":
        model = args.image_model.strip() or "imagen-4.0-generate-001"
        img_client = VertexImagenClient(model=model)
    elif args.image_api == "gemini_flash_image":
        model = args.image_model.strip() or "gemini-2.5-flash-image"
        img_client = GeminiFlashImageClient(model=model)
    else:
        model = args.image_model.strip() or "sd_xl_base_1.0.safetensors"
        default_comfy_workflow = (
            root / "yadam" / "config" / "comfy_workflows" / "yadam_api_sdxl_base_fast_placeholders.json"
        )
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
        )

    print(f"[INFO] image_api={args.image_api}, image_model={model}")
    if args.image_api == "comfyui":
        print(f"[INFO] comfy_url={args.comfy_url.strip()}, comfy_workflow={workflow_path}")
    exporter = VrewFileExporter()

    orch = Orchestrator(cfg, img_client=img_client, exporter=exporter)
    orch.run()


def _run_synopsis_mode(root: Path, synopsis_input: str) -> None:
    synopsis_dir = root / "synopsis"
    stories_dir = root / "stories"
    _ensure_dir(stories_dir)
    next_no = _next_synopsis_no(root, synopsis_dir)
    out_path = stories_dir / f"story{next_no:02d}.synopsis"
    title_path = stories_dir / f"story{next_no:02d}.title"
    _generate_synopsis_file(root, synopsis_input, out_path)
    title_path.write_text(synopsis_input.strip() + "\n", encoding="utf-8")
    print(f"[INFO] title saved: {title_path}")


def _run_story_synopsis_mode(root: Path, story_id: str, *, non_interactive: bool) -> None:
    stories_dir = root / "stories"
    title_path = stories_dir / f"{story_id}.title"
    synopsis_path = stories_dir / f"{story_id}.synopsis"

    if not title_path.exists():
        raise FileNotFoundError(
            f"시놉시스 생성을 위한 제목 파일이 없습니다: {title_path}\n"
            f"먼저 {title_path.name} 파일을 만들고 제목 한 줄을 넣으세요."
        )

    title_text = title_path.read_text(encoding="utf-8").strip()
    if not title_text:
        raise RuntimeError(f"제목 파일이 비어 있습니다: {title_path}")

    if synopsis_path.exists():
        print(f"[INFO] synopsis file already exists: {synopsis_path}")
        if (not non_interactive) and (not _confirm_overwrite(synopsis_path)):
            print("[INFO] synopsis generation cancelled by user")
            return

    _generate_synopsis_file(root, title_text, synopsis_path)


def _run_make_story_mode(root: Path, story_id: str, *, target_chars: int, non_interactive: bool) -> None:
    stories_dir = root / "stories"
    synopsis_path = stories_dir / f"{story_id}.synopsis"
    story_path = stories_dir / f"{story_id}.txt"

    if not synopsis_path.exists():
        raise FileNotFoundError(
            f"스토리 생성을 위한 시놉시스 파일이 없습니다: {synopsis_path}\n"
            f"먼저 `python -m yadam.cli --story-id {story_id}` 로 시놉시스를 생성하세요."
        )

    synopsis_text = synopsis_path.read_text(encoding="utf-8").strip()
    if not synopsis_text:
        raise RuntimeError(f"시놉시스 파일이 비어 있습니다: {synopsis_path}")

    chapters = _parse_synopsis_chapters(synopsis_text)
    generated_chapters: list[str] = []
    previous_chapter_text = ""
    start_index = 0

    if story_path.exists():
        print(f"[INFO] story file already exists: {story_path}")
        existing_text = story_path.read_text(encoding="utf-8").strip()
        existing_blocks = _parse_story_chapter_blocks(existing_text)
        if existing_blocks:
            generated_chapters = [str(block["text"]) for block in existing_blocks]
            previous_chapter_text = generated_chapters[-1]
            last_no = int(existing_blocks[-1]["chapter_no"])
            start_index = len(existing_blocks)
            if start_index >= len(chapters):
                print(f"[INFO] story already complete through Chapter {last_no}: {story_path}")
                return
            print(f"[INFO] resuming from Chapter {last_no + 1} (last success: Chapter {last_no})")
        else:
            if (not non_interactive) and (not _confirm_overwrite(story_path)):
                print("[INFO] story generation cancelled by user")
                return
            story_path.write_text("", encoding="utf-8")

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
        )
        generated_chapters.append(chapter_text)
        previous_chapter_text = chapter_text
        story_path.write_text("\n\n".join(generated_chapters).strip() + "\n", encoding="utf-8")

    print(f"[INFO] story saved: {story_path}")


def _generate_synopsis_file(root: Path, synopsis_input: str, out_path: Path) -> None:
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
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
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

    out_path.write_text(text + "\n", encoding="utf-8")
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
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
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
