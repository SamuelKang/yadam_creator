#!/usr/bin/env python3
"""Check whether Voyager extension is installed/enabled in a Chrome user-data-dir.

Usage:
  python scripts/check_voyager_extension.py
  python scripts/check_voyager_extension.py --user-data-dir /tmp/chrome-gemini-alt3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VOYAGER_ID = "iifacdnjakkhjjiengaffnegbndgingi"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _profile_name_candidates(user_data_dir: Path) -> list[str]:
    names = ["Default"]
    for p in sorted(user_data_dir.glob("Profile *")):
        if p.is_dir():
            names.append(p.name)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _check_profile(user_data_dir: Path, profile_name: str) -> dict[str, Any]:
    profile_dir = user_data_dir / profile_name
    prefs = _load_json(profile_dir / "Preferences")
    secure_prefs = _load_json(profile_dir / "Secure Preferences")

    def _get_ext_settings(blob: dict[str, Any]) -> dict[str, Any]:
        return ((blob.get("extensions") or {}).get("settings") or {})

    ext_from_secure = _get_ext_settings(secure_prefs).get(VOYAGER_ID) or {}
    ext_from_prefs = _get_ext_settings(prefs).get(VOYAGER_ID) or {}
    ext = ext_from_secure or ext_from_prefs

    enabled_state = ext.get("state") == 1
    disable_reasons = ext.get("disable_reasons")
    manifest = ext.get("manifest") if isinstance(ext.get("manifest"), dict) else {}
    version = manifest.get("version")
    name = manifest.get("name")

    ext_folder = profile_dir / "Extensions" / VOYAGER_ID
    ext_files_present = ext_folder.exists() and any(ext_folder.iterdir())

    pinned = False
    pinned_list = (
        (((prefs.get("extensions") or {}).get("pinned_extensions")) or [])
        + ((((prefs.get("account_values") or {}).get("extensions") or {}).get("pinned_extensions")) or [])
        + (((secure_prefs.get("extensions") or {}).get("pinned_extensions")) or [])
        + ((((secure_prefs.get("account_values") or {}).get("extensions") or {}).get("pinned_extensions")) or [])
    )
    pinned = VOYAGER_ID in pinned_list

    return {
        "profile": profile_name,
        "profile_exists": profile_dir.exists(),
        "voyager_entry_found": bool(ext),
        "enabled_state": enabled_state,
        "disable_reasons": disable_reasons,
        "name": name,
        "version": version,
        "ext_files_present": ext_files_present,
        "pinned": pinned,
        "ok": bool(ext) and enabled_state and ext_files_present,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--user-data-dir",
        default="/tmp/chrome-gemini-alt3",
        help="Chrome user-data-dir to inspect (default: /tmp/chrome-gemini-alt3)",
    )
    args = parser.parse_args()

    user_data_dir = Path(args.user_data_dir).expanduser()
    if not user_data_dir.exists():
        print(f"FAIL: user-data-dir not found: {user_data_dir}")
        return 2

    print(f"Check target: {user_data_dir}")
    print(f"Voyager extension id: {VOYAGER_ID}")
    print()

    any_ok = False
    for profile_name in _profile_name_candidates(user_data_dir):
        info = _check_profile(user_data_dir, profile_name)
        if not info["profile_exists"]:
            continue
        any_ok = any_ok or info["ok"]

        print(f"[{info['profile']}]")
        print(f"  voyager_entry_found: {info['voyager_entry_found']}")
        print(f"  enabled_state(state==1): {info['enabled_state']}")
        print(f"  ext_files_present: {info['ext_files_present']}")
        print(f"  pinned: {info['pinned']}")
        if info["name"] or info["version"]:
            print(f"  manifest: {info['name']} {info['version']}")
        if info["disable_reasons"] is not None:
            print(f"  disable_reasons: {info['disable_reasons']}")
        print(f"  status: {'OK' if info['ok'] else 'NOT_READY'}")
        print()

    if any_ok:
        print("FINAL: READY (Voyager is installed and enabled in at least one profile)")
        return 0

    print("FINAL: NOT_READY (Voyager not enabled for this automation user-data-dir)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
