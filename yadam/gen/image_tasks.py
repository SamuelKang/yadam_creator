# yadam/gen/image_tasks.py
from __future__ import annotations
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List

from yadam.core.errors import GenError, ErrorKind
from yadam.gen.image_client import ImageClient, ImageGenRequest
from yadam.gen.placeholder import make_error_image_bytes
from yadam.prompts.rewrite import rewrite_for_policy


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    policy_rewrite_max_level: int = 3
    transient_backoff_sec: List[float] = None

    def __post_init__(self) -> None:
        if self.transient_backoff_sec is None:
            self.transient_backoff_sec = [2.0, 5.0, 12.0]


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def generate_with_fallback(
    client: ImageClient,
    out_ok_path: Path,
    out_error_path: Path,
    prompt: str,
    retry: RetryPolicy,
    meta: Dict[str, Any],
    aspect_ratio: Optional[str] = None,
) -> Dict[str, Any]:
    """
    - 성공하면 out_ok_path 저장 + out_error_path 삭제(있으면)
    - 정책 차단이면 prompt를 레벨 1..N으로 리라이트하며 재시도
    - 일시 오류면 백오프 후 재시도
    - 최종 실패면 out_error_path 생성(텍스트 포함)
    - 디버깅을 위해 프롬프트 원본/최종/이력을 meta에 남김
    meta: JSON에 들어갈 상태 정보(dict)
    """
    attempts = int(meta.get("attempts", 0))

    # 디버깅용: 최초 원본 프롬프트는 고정
    meta.setdefault("prompt_original", prompt)

    # 기존 이력 유지
    prompt_history = list(meta.get("prompt_history", []))

    last_error: Optional[str] = None

    for attempt_idx in range(retry.max_attempts):
        attempts += 1

        # 시도 기록(프롬프트 포함)
        prompt_history.append({
            "type": "attempt",
            "attempt": attempts,
            "policy_rewrite_level": int(meta.get("policy_rewrite_level", 0)),
            "prompt": prompt,
        })

        try:
            req = ImageGenRequest(prompt=prompt, aspect_ratio=aspect_ratio)
            resp = client.generate(req)

            if not resp.image_bytes:
                raise GenError(ErrorKind.INVALID, "EMPTY_IMAGE_BYTES", "ImageClient가 빈 image_bytes를 반환했습니다.")

            _atomic_write(out_ok_path, resp.image_bytes)

            # 기존 error 파일이 있으면 삭제
            if out_error_path.exists():
                out_error_path.unlink()

            meta.update({
                "status": "ok",
                "attempts": attempts,
                "last_error": None,
                "path": str(out_ok_path),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "prompt_used": prompt,                 # 최종 사용 프롬프트
                "prompt_history": prompt_history,
            })
            return meta

        except GenError as e:
            last_error = str(e)

            # 에러 기록(프롬프트 포함)
            prompt_history.append({
                "type": "error",
                "attempt": attempts,
                "policy_rewrite_level": int(meta.get("policy_rewrite_level", 0)),
                "prompt": prompt,
                "error": last_error,
                "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                "code": e.code,
            })

            # 1) 일시 오류: 백오프 후 재시도
            if e.kind == ErrorKind.TRANSIENT:
                backoff = retry.transient_backoff_sec[
                    min(attempt_idx, len(retry.transient_backoff_sec) - 1)
                ]
                time.sleep(backoff)
                continue

            # 2) 정책 차단: 프롬프트 리라이트 후 재시도
            if e.kind == ErrorKind.POLICY:
                cur_level = int(meta.get("policy_rewrite_level", 0))
                if cur_level >= retry.policy_rewrite_max_level:
                    break

                new_level = cur_level + 1
                rr = rewrite_for_policy(prompt, new_level)

                prompt_history.append({
                    "type": "rewrite",
                    "from_level": cur_level,
                    "to_level": new_level,
                    "note": rr.note,
                    "prompt_before": prompt,
                    "prompt_after": rr.rewritten,
                })

                meta["policy_rewrite_level"] = new_level
                prompt = rr.rewritten
                continue

            # 3) INVALID/FATAL 등: 재시도 가치 낮음
            break

    # 최종 실패: error 이미지 생성(텍스트 포함)
    err_text = (
        f"ERROR\n{last_error}\n"
        f"OUT={out_error_path.name}\n"
        f"ATTEMPTS={attempts}\n"
        f"TIME={time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    err_bytes = make_error_image_bytes(err_text)
    _atomic_write(out_error_path, err_bytes)

    meta.update({
        "status": "error",
        "attempts": attempts,
        "last_error": last_error,
        "path": str(out_error_path),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "prompt_used": prompt,                # 실패 시점의 마지막 프롬프트(리라이트 반영될 수 있음)
        "prompt_history": prompt_history,
    })
    return meta