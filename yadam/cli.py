# yadam/cli.py
from __future__ import annotations

import argparse
import json
import os
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

EXAMPLES_TEXT = "\n".join([
    "선호 기본 실행 예시:",
    "  python -m yadam.cli --story-id story00",
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
        help="시놉시스 생성용 입력 문구. 지정 시 prompts/make_synopsis.txt를 사용해 synopsis/storyNN.synopsis 파일을 생성",
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
    from google import genai
    from google.genai import types

    prompts_dir = root / "prompts"
    synopsis_dir = root / "synopsis"
    _ensure_dir(synopsis_dir)

    prompt_path = prompts_dir / "make_synopsis.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"시놉시스 프롬프트 파일이 없습니다: {prompt_path}")

    template = prompt_path.read_text(encoding="utf-8").strip()
    if not template:
        raise RuntimeError(f"시놉시스 프롬프트가 비어 있습니다: {prompt_path}")

    next_no = _next_synopsis_no(root, synopsis_dir)
    out_path = synopsis_dir / f"story{next_no:02d}.synopsis"

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
    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        raise RuntimeError("시놉시스 LLM 응답이 비어 있습니다.")

    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"[INFO] synopsis saved: {out_path}")


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
        for p in stories_dir.glob("story*.txt"):
            stem = p.stem
            digits = "".join(ch for ch in stem if ch.isdigit())
            if digits:
                nums.append(int(digits))

    return (max(nums) + 1) if nums else 1


if __name__ == "__main__":
    main()
