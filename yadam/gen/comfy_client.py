from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from yadam.core.errors import ErrorKind, GenError
from yadam.gen.image_client import ImageClient, ImageGenRequest, ImageGenResponse


_ASPECT_TO_SIZE: Dict[str, Tuple[int, int]] = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "3:4": (960, 1280),
    "4:3": (1280, 960),
    "1:1": (1024, 1024),
}


class ComfyUIImageClient(ImageClient):
    """
    ComfyUI HTTP API 클라이언트.
    - /prompt로 workflow를 제출
    - /history/{prompt_id}를 폴링해 결과 이미지 메타를 찾은 뒤 /view로 원본 bytes를 가져온다.
    - workflow JSON에는 아래 placeholder를 문자열로 넣어 치환할 수 있다:
      __PROMPT__, __NEGATIVE_PROMPT__, __WIDTH__, __HEIGHT__, __SEED__, __MODEL__
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        workflow_path: str = "",
        model: str = "flux1-schnell",
        timeout_sec: int = 300,
        poll_interval_sec: float = 1.0,
        negative_prompt: str = (
            "text, letters, words, subtitles, speech bubble, caption, watermark, logo, signboard text"
        ),
    ) -> None:
        self.base_url = (base_url or "http://127.0.0.1:8188").rstrip("/")
        self.workflow_path = str(workflow_path or "").strip()
        self.model = str(model or "flux1-schnell").strip()
        self.timeout_sec = max(10, int(timeout_sec))
        self.poll_interval_sec = max(0.2, float(poll_interval_sec))
        self.negative_prompt = negative_prompt
        self.client_id = str(uuid.uuid4())

    def generate(self, req: ImageGenRequest) -> ImageGenResponse:
        if not self.workflow_path:
            raise GenError(
                ErrorKind.INVALID,
                "MISSING_WORKFLOW_PATH",
                "ComfyUI workflow path가 비어 있습니다. --comfy-workflow 또는 COMFYUI_WORKFLOW_PATH를 설정하세요.",
            )

        try:
            prompt_graph = self._build_prompt_graph(req)
            payload = {"prompt": prompt_graph, "client_id": self.client_id}
            resp = self._http_json("POST", "/prompt", payload)
            prompt_id = str(resp.get("prompt_id") or "").strip()
            if not prompt_id:
                raise GenError(ErrorKind.INVALID, "EMPTY_PROMPT_ID", f"/prompt 응답에 prompt_id가 없습니다: {resp}")

            image_info = self._wait_for_first_image(prompt_id)
            image_bytes, mime = self._fetch_image_bytes(image_info)
            if not image_bytes:
                raise GenError(ErrorKind.INVALID, "EMPTY_IMAGE_BYTES", "ComfyUI /view 응답 이미지가 비어 있습니다.")
            return ImageGenResponse(image_bytes=image_bytes, mime_type=mime)
        except GenError:
            raise
        except Exception as e:
            kind = self._classify_error(str(e))
            raise GenError(kind, "COMFYUI_ERROR", str(e))

    def _build_prompt_graph(self, req: ImageGenRequest) -> Dict[str, Any]:
        wf_path = Path(self.workflow_path).expanduser().resolve()
        if not wf_path.exists():
            raise GenError(
                ErrorKind.INVALID,
                "WORKFLOW_NOT_FOUND",
                f"ComfyUI workflow 파일을 찾을 수 없습니다: {wf_path}",
            )

        try:
            workflow = json.loads(wf_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise GenError(ErrorKind.INVALID, "WORKFLOW_JSON_ERROR", f"workflow JSON 파싱 실패: {e}")

        w, h = self._resolve_size(req.aspect_ratio, req.width, req.height)
        seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647
        values = {
            "__PROMPT__": req.prompt,
            "__NEGATIVE_PROMPT__": self.negative_prompt,
            "__WIDTH__": w,
            "__HEIGHT__": h,
            "__SEED__": int(seed),
            "__MODEL__": self.model,
        }
        return self._deep_replace(workflow, values)

    def _resolve_size(self, aspect_ratio: Optional[str], width: int, height: int) -> Tuple[int, int]:
        aspect = str(aspect_ratio or "").strip()
        if aspect and aspect in _ASPECT_TO_SIZE:
            return _ASPECT_TO_SIZE[aspect]
        return int(width or 1280), int(height or 720)

    def _deep_replace(self, obj: Any, values: Dict[str, Any]) -> Any:
        if isinstance(obj, dict):
            return {k: self._deep_replace(v, values) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_replace(v, values) for v in obj]
        if isinstance(obj, str):
            s = obj
            for k, v in values.items():
                if s == k:
                    return v
                s = s.replace(k, str(v))
            return s
        return obj

    def _wait_for_first_image(self, prompt_id: str) -> Dict[str, Any]:
        deadline = time.time() + self.timeout_sec
        while time.time() < deadline:
            hist = self._http_json("GET", f"/history/{prompt_id}")
            job = hist.get(prompt_id) if isinstance(hist, dict) else None
            if isinstance(job, dict):
                out = job.get("outputs")
                image_info = self._extract_first_image(out)
                if image_info:
                    return image_info
                # 명시적 오류가 보이면 바로 실패
                if job.get("status") == "error":
                    raise GenError(ErrorKind.INVALID, "COMFY_JOB_ERROR", f"ComfyUI job error: {job}")
            time.sleep(self.poll_interval_sec)
        raise GenError(
            ErrorKind.TRANSIENT,
            "COMFY_TIMEOUT",
            f"ComfyUI 결과 대기 timeout({self.timeout_sec}s): prompt_id={prompt_id}",
        )

    def _extract_first_image(self, outputs: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(outputs, dict):
            return None
        for _, node_out in outputs.items():
            if not isinstance(node_out, dict):
                continue
            images = node_out.get("images")
            if not isinstance(images, list):
                continue
            for image in images:
                if isinstance(image, dict) and image.get("filename"):
                    return image
        return None

    def _fetch_image_bytes(self, image_info: Dict[str, Any]) -> Tuple[bytes, str]:
        params = {
            "filename": str(image_info.get("filename") or ""),
            "subfolder": str(image_info.get("subfolder") or ""),
            "type": str(image_info.get("type") or "output"),
        }
        if not params["filename"]:
            raise GenError(ErrorKind.INVALID, "COMFY_IMAGE_INFO_INVALID", f"filename 누락: {image_info}")

        qs = urlparse.urlencode(params)
        raw = self._http_bytes("GET", f"/view?{qs}")
        fn = params["filename"].lower()
        if fn.endswith(".png"):
            mime = "image/png"
        elif fn.endswith(".webp"):
            mime = "image/webp"
        else:
            mime = "image/jpeg"
        return raw, mime

    def _http_json(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raw = self._http_raw(method, path, body)
        try:
            obj = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise GenError(ErrorKind.INVALID, "JSON_PARSE_ERROR", f"{path} 응답 JSON 파싱 실패: {e}")
        if not isinstance(obj, dict):
            raise GenError(ErrorKind.INVALID, "JSON_TYPE_ERROR", f"{path} 응답이 dict가 아닙니다.")
        return obj

    def _http_bytes(self, method: str, path: str) -> bytes:
        return self._http_raw(method, path, None)

    def _http_raw(self, method: str, path: str, body: Optional[Dict[str, Any]]) -> bytes:
        url = f"{self.base_url}{path}"
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urlrequest.Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlrequest.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urlerror.HTTPError as e:
            msg = e.read().decode("utf-8", errors="replace")
            kind = self._classify_error(msg)
            raise GenError(kind, f"HTTP_{e.code}", msg)
        except urlerror.URLError as e:
            raise GenError(ErrorKind.TRANSIENT, "NETWORK_ERROR", str(e))
        except TimeoutError as e:
            raise GenError(ErrorKind.TRANSIENT, "TIMEOUT", str(e))

    def _classify_error(self, msg: str) -> ErrorKind:
        s = (msg or "").lower()
        if any(x in s for x in ["timeout", "temporar", "connection", "refused", "reset", "503", "429"]):
            return ErrorKind.TRANSIENT
        if any(x in s for x in ["policy", "safety", "blocked"]):
            return ErrorKind.POLICY
        return ErrorKind.INVALID
