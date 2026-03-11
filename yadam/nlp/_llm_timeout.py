from __future__ import annotations

import queue
import threading
from typing import Any, Callable


def call_with_timeout(fn: Callable[[], Any], timeout_sec: float) -> Any:
    q: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def _runner() -> None:
        try:
            q.put((True, fn()))
        except Exception as exc:  # pragma: no cover
            q.put((False, exc))

    t = threading.Thread(target=_runner, daemon=True)
    t.start()

    try:
        ok, value = q.get(timeout=max(1.0, float(timeout_sec)))
    except queue.Empty as exc:
        raise TimeoutError(f"LLM call timed out after {timeout_sec:.0f}s") from exc

    if ok:
        return value
    raise value
