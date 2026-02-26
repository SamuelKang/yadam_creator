# yadam/core/resume.py
from __future__ import annotations
from typing import Any, Dict, Optional


def is_ok(node: Optional[Dict[str, Any]]) -> bool:
    return bool(node) and node.get("status") == "ok"


def is_error(node: Optional[Dict[str, Any]]) -> bool:
    return bool(node) and node.get("status") == "error"


def mark_pending(node: Dict[str, Any]) -> Dict[str, Any]:
    node["status"] = "pending"
    return node