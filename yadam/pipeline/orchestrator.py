# ===== orchestrator.py (PART 1/4) =====
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable, TypeVar

from yadam.core.paths import ProjectPaths
from yadam.core.io import read_text_file
from yadam.core.jsondb import JsonDB

from yadam.nlp.sentence_split import normalize_script, split_sentences_korean
from yadam.nlp.scene_split import split_into_scenes, Scene
from yadam.nlp.entity_extract import extract_characters, extract_places
from yadam.nlp.tagger import tag_scene
from yadam.nlp.chapter_split import preprocess_chapters, attach_chapters, ChapterInfo

from yadam.nlp.llm_extract import LLMEntityExtractor, LLMExtractorConfig

from yadam.prompts.profiles import load_profiles_yaml, get_era, get_style
from yadam.prompts.builder import (
    build_character_prompt,
    build_place_prompt,
)

from yadam.gen.image_client import ImageClient
from yadam.gen.image_tasks import generate_with_fallback, RetryPolicy

from yadam.export.vrew_exporter import VrewExporter, VrewExportRequest
from yadam.nlp.llm_scene_prompt import LLMScenePromptBuilder, LLMScenePromptConfig
from yadam.nlp.llm_prompt_rewrite import LLMPromptRewriter, LLMPromptRewriteConfig
from yadam.nlp.llm_scene_binding import LLMSceneBindingPlanner, LLMSceneBindingConfig
from yadam.model_defaults import DEFAULT_TEXT_LLM_MODEL

T = TypeVar("T")

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

@dataclass
class PipelineConfig:
    base_dir: str
    profiles_yaml: str
    era_profile: str
    style_profile: str
    input_script_path: str
    json_name: str = "project.json"
    interactive: bool = True
    llm_model: str = DEFAULT_TEXT_LLM_MODEL
    stop_after_tag_scene: bool = False
    stop_after_place_refs: bool = False
    stop_after_clips: bool = False

    # ✅ scene split 파라미터(요구사항 반영)
    scene_min_s: int = 2
    scene_max_s: int = 4
    scene_base_len: int = 40  # 기본 40
    vrew_clip_max_chars: int = 30


def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-z가-힣_]+", "", s)
    if not s:
        return "unnamed"
    return s[:60]


def _default_image_meta() -> Dict[str, Any]:
    return {
        "status": "pending",
        "attempts": 0,
        "last_error": None,
        "path": None,
        "policy_rewrite_level": 0,
        "prompt_original": None,
        "prompt_used": None,
        "prompt_history": [],
    }


def _cleanup_stale_error_file(meta: Dict[str, Any], ok_path: Path, err_path: Path) -> bool:
    if (meta.get("status") == "ok") and ok_path.exists() and err_path.exists():
        try:
            err_path.unlink()
            return True
        except Exception:
            return False
    return False


class Orchestrator:
    def __init__(
        self,
        cfg: PipelineConfig,
        img_client: ImageClient,
        exporter: Optional[VrewExporter] = None,
    ):
        self.cfg = cfg
        self.paths = ProjectPaths.from_base(cfg.base_dir)
        self.paths.ensure()

        self.db = JsonDB(self.paths.out_dir / cfg.json_name)
        self.img_client = img_client
        self.exporter = exporter

        self.profiles = load_profiles_yaml(cfg.profiles_yaml)
        self.era = get_era(self.profiles, cfg.era_profile)
        self.style = get_style(self.profiles, cfg.style_profile)
        self.char_style = get_style(self.profiles, "k_webtoon_char")       # characters 전용
        self.clip_style = get_style(self.profiles, "k_webtoon_clip")

        self.scene_prompt_llm = LLMScenePromptBuilder(
            LLMScenePromptConfig(model=cfg.llm_model, temperature=0.2)
        )
        self.prompt_rewriter = LLMPromptRewriter(
            LLMPromptRewriteConfig(model=cfg.llm_model, temperature=0.2)
        )
        self.scene_binding_planner = LLMSceneBindingPlanner(
            LLMSceneBindingConfig(model=cfg.llm_model, temperature=0.1)
        )
        self.story_id = Path(cfg.input_script_path).stem
        self.variant_overrides = self._load_variant_overrides()
        self.scene_bindings = self._load_scene_bindings()

    def _load_variant_overrides(self) -> List[Dict[str, Any]]:
        if yaml is None:
            return []
        try:
            root = Path(self.cfg.input_script_path).resolve().parents[1]
        except Exception:
            return []
        candidates = [
            root / "stories" / f"{self.story_id}_variant_overrides.yaml",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                rows = raw.get("variant_overrides", [])
                return [r for r in rows if isinstance(r, dict)]
            except Exception:
                continue
        return []

    def _load_scene_bindings(self) -> List[Dict[str, Any]]:
        if yaml is None:
            return []
        try:
            root = Path(self.cfg.input_script_path).resolve().parents[1]
        except Exception:
            return []
        candidates = [
            root / "stories" / f"{self.story_id}_scene_bindings.yaml",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                rows = raw.get("scene_bindings", [])
                return [r for r in rows if isinstance(r, dict)]
            except Exception:
                continue
        return []

    def _has_story_rule_file_for_resume(self) -> bool:
        """
        non-interactive 1차 실행에서 place 단계 후 멈췄다가,
        사용자가 Codex로 규칙 파일을 만든 뒤 재실행할 때 계속 진행하기 위한 체크.
        """
        try:
            root = Path(self.cfg.input_script_path).resolve().parents[1]
        except Exception:
            return False
        candidates = [
            root / "stories" / f"{self.story_id}_variant_overrides.yaml",
            root / "stories" / f"{self.story_id}_scene_bindings.yaml",
        ]
        return any(p.exists() for p in candidates)

    def _parse_scene_selector(self, selector: Any) -> List[int]:
        out: List[int] = []
        if selector is None:
            return out
        if isinstance(selector, int):
            return [selector]
        if isinstance(selector, list):
            for x in selector:
                try:
                    out.append(int(x))
                except Exception:
                    continue
            return sorted(set(out))
        s = str(selector).strip()
        if not s:
            return out
        if "-" in s:
            a, b = s.split("-", 1)
            try:
                i0 = int(a.strip())
                i1 = int(b.strip())
            except Exception:
                return out
            if i0 > i1:
                i0, i1 = i1, i0
            return list(range(i0, i1 + 1))
        try:
            return [int(s)]
        except Exception:
            return out

    def _apply_variant_overrides(
        self,
        scenes: List[Dict[str, Any]],
        chars: List[Dict[str, Any]],
        overrides: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        rows = self.variant_overrides if overrides is None else overrides
        if not rows:
            return

        id_set = {str(c.get("id")) for c in chars if c.get("id")}
        name_to_id = {
            str(c.get("name")).strip(): str(c.get("id"))
            for c in chars
            if c.get("id") and str(c.get("name", "")).strip()
        }
        sid_map = {int(s.get("id")): s for s in scenes if s.get("id") is not None}

        for row in rows:
            story_id = str(row.get("story_id") or "").strip()
            if story_id and story_id != self.story_id:
                continue

            char_key = str(row.get("character") or "").strip()
            if not char_key:
                continue
            cid = char_key if char_key in id_set else name_to_id.get(char_key, "")
            if not cid:
                continue

            variant = str(row.get("variant") or "").strip()
            target_ids = set(self._parse_scene_selector(row.get("scenes")))
            chapter_title = str(row.get("chapter_title") or "").strip()

            for sid, s in sid_map.items():
                if target_ids and sid not in target_ids:
                    continue
                if chapter_title and str(s.get("chapter_title") or "").strip() != chapter_title:
                    continue

                chars2 = s.get("characters", [])
                if not isinstance(chars2, list):
                    chars2 = []
                if cid not in chars2:
                    chars2.append(cid)
                s["characters"] = chars2

                inst = s.get("character_instances", [])
                if not isinstance(inst, list):
                    inst = []
                replaced = False
                new_inst: List[Dict[str, str]] = []
                for it in inst:
                    if not isinstance(it, dict):
                        continue
                    if str(it.get("char_id") or "") == cid:
                        if not replaced:
                            new_inst.append({"char_id": cid, "variant": variant})
                            replaced = True
                        continue
                    new_inst.append({"char_id": str(it.get("char_id") or ""), "variant": str(it.get("variant") or "")})
                if not replaced:
                    new_inst.append({"char_id": cid, "variant": variant})
                s["character_instances"] = new_inst

    def _apply_scene_bindings(
        self,
        scenes: List[Dict[str, Any]],
        chars: List[Dict[str, Any]],
        places: List[Dict[str, Any]],
        bindings: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        rows = self.scene_bindings if bindings is None else bindings
        if not rows:
            return

        char_id_set = {str(c.get("id")) for c in chars if c.get("id")}
        char_name_to_id = {
            str(c.get("name")).strip(): str(c.get("id"))
            for c in chars
            if c.get("id") and str(c.get("name", "")).strip()
        }
        place_id_set = {str(p.get("id")) for p in places if p.get("id")}
        place_name_to_id = {
            str(p.get("name")).strip(): str(p.get("id"))
            for p in places
            if p.get("id") and str(p.get("name", "")).strip()
        }
        sid_map = {int(s.get("id")): s for s in scenes if s.get("id") is not None}

        def resolve_char_entry(entry: Any) -> Tuple[str, str]:
            if isinstance(entry, dict):
                key = str(
                    entry.get("char_id")
                    or entry.get("character")
                    or entry.get("name")
                    or ""
                ).strip()
                var = str(entry.get("variant") or "").strip()
            else:
                key = str(entry or "").strip()
                var = ""
            if not key:
                return "", var
            cid = key if key in char_id_set else char_name_to_id.get(key, "")
            return cid, var

        def resolve_place_entry(entry: Any) -> str:
            key = str(entry or "").strip()
            if not key:
                return ""
            return key if key in place_id_set else place_name_to_id.get(key, "")

        for row in rows:
            story_id = str(row.get("story_id") or "").strip()
            if story_id and story_id != self.story_id:
                continue

            target_ids = set(self._parse_scene_selector(row.get("scenes")))
            chapter_title = str(row.get("chapter_title") or "").strip()
            mode = str(row.get("mode") or "add").strip().lower()
            replace_mode = (mode == "replace")

            resolved_chars: List[Tuple[str, str]] = []
            for ent in (row.get("characters") or []):
                cid, var = resolve_char_entry(ent)
                if cid:
                    resolved_chars.append((cid, var))

            resolved_places: List[str] = []
            for ent in (row.get("places") or []):
                pid = resolve_place_entry(ent)
                if pid and pid not in resolved_places:
                    resolved_places.append(pid)

            for sid, s in sid_map.items():
                if target_ids and sid not in target_ids:
                    continue
                if chapter_title and str(s.get("chapter_title") or "").strip() != chapter_title:
                    continue

                scene_chars = s.get("characters", [])
                if not isinstance(scene_chars, list):
                    scene_chars = []
                scene_places = s.get("places", [])
                if not isinstance(scene_places, list):
                    scene_places = []
                scene_inst = s.get("character_instances", [])
                if not isinstance(scene_inst, list):
                    scene_inst = []

                if replace_mode and resolved_chars:
                    scene_chars = [cid for cid, _ in resolved_chars]
                    scene_inst = [{"char_id": cid, "variant": var} for cid, var in resolved_chars]
                else:
                    for cid, var in resolved_chars:
                        if cid not in scene_chars:
                            scene_chars.append(cid)
                        replaced = False
                        new_inst: List[Dict[str, str]] = []
                        for it in scene_inst:
                            if not isinstance(it, dict):
                                continue
                            iid = str(it.get("char_id") or "")
                            ivar = str(it.get("variant") or "")
                            if iid == cid:
                                if not replaced:
                                    new_inst.append({"char_id": cid, "variant": var})
                                    replaced = True
                                continue
                            new_inst.append({"char_id": iid, "variant": ivar})
                        if not replaced:
                            new_inst.append({"char_id": cid, "variant": var})
                        scene_inst = new_inst

                if replace_mode and resolved_places:
                    scene_places = list(resolved_places)
                else:
                    for pid in resolved_places:
                        if pid not in scene_places:
                            scene_places.append(pid)

                s["characters"] = scene_chars
                s["character_instances"] = scene_inst
                s["places"] = scene_places

    def _update_used_by_scenes(
        self,
        scenes: List[Dict[str, Any]],
        chars: List[Dict[str, Any]],
        places: List[Dict[str, Any]],
    ) -> None:
        char_usage: Dict[str, List[int]] = {}
        place_usage: Dict[str, List[int]] = {}
        for s in scenes:
            sid = int(s.get("id", 0))
            if sid <= 0:
                continue
            for cid in (s.get("characters") or []):
                if isinstance(cid, str):
                    char_usage.setdefault(cid, []).append(sid)
            for pid in (s.get("places") or []):
                if isinstance(pid, str):
                    place_usage.setdefault(pid, []).append(sid)

        for c in chars:
            cid = str(c.get("id") or "")
            used = sorted(set(char_usage.get(cid, [])))
            c["used_by_scenes"] = used

        for p in places:
            pid = str(p.get("id") or "")
            used = sorted(set(place_usage.get(pid, [])))
            p["used_by_scenes"] = used

    def _plan_auto_scene_rules(
        self,
        *,
        script_text: str,
        scenes: List[Dict[str, Any]],
        chars: List[Dict[str, Any]],
        places: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        # LLM 입력 최소화: scene/character/place 핵심 필드만 전달
        scene_payload: List[Dict[str, Any]] = []
        for s in scenes:
            scene_payload.append({
                "id": int(s.get("id", 0)),
                "chapter_title": str(s.get("chapter_title") or ""),
                "text": str(s.get("text") or "")[:280],
                "characters": list(s.get("characters") or []),
                "places": list(s.get("places") or []),
                "character_instances": list(s.get("character_instances") or []),
            })

        char_payload: List[Dict[str, Any]] = []
        for c in chars:
            char_payload.append({
                "id": str(c.get("id") or ""),
                "name": str(c.get("name") or ""),
                "variants": list(c.get("variants") or []),
                "age_stage": str(c.get("age_stage") or ""),
                "aliases": list(c.get("aliases") or [])[:8],
            })

        place_payload: List[Dict[str, Any]] = []
        for p in places:
            place_payload.append({
                "id": str(p.get("id") or ""),
                "name": str(p.get("name") or ""),
                "aliases": list(p.get("aliases") or [])[:8],
            })

        try:
            planned = self._call_with_rate_limit_retry(
                lambda: self.scene_binding_planner.plan(
                    story_id=self.story_id,
                    script_text=script_text,
                    scenes=scene_payload,
                    characters=char_payload,
                    places=place_payload,
                ),
                label="[auto-rules] scene binding planner",
                max_attempts=3,
            )
            if not isinstance(planned, dict):
                return {"variant_overrides": [], "scene_bindings": [], "notes": ["invalid planner response"]}
            return {
                "variant_overrides": list(planned.get("variant_overrides") or []),
                "scene_bindings": list(planned.get("scene_bindings") or []),
                "notes": list(planned.get("notes") or []),
            }
        except Exception as e:
            return {
                "variant_overrides": [],
                "scene_bindings": [],
                "notes": [f"planner_failed: {e}"],
            }

    def _confirm(self, title: str, hint: str = "") -> bool:
        if not getattr(self.cfg, "interactive", True):
            return True

        print("")
        print("=" * 72)
        print(f"[CONFIRM] {title} (Y/n)")
        if hint:
            print(hint)

        while True:
            ans = input("> ").strip().lower()
            if ans == "" or ans == "y" or ans == "yes":
                return True
            if ans == "n" or ans == "no":
                return False
            print("y / n 또는 엔터만 입력하세요.")

    def _is_policy_error(self, err: str) -> bool:
        s = (err or "").lower()
        return (
            "errorkind.policy" in s
            or "policy" in s
            or "blocked" in s
            or "safety" in s
            or "filter" in s
            or "rai" in s
        )

    def _is_rate_limit_error(self, err: Any) -> bool:
        s = str(err or "").lower()
        return (
            "resource_exhausted" in s
            or "429" in s
            or "rate limit" in s
            or "quota" in s
        )

    def _call_with_rate_limit_retry(
        self,
        fn: Callable[[], T],
        *,
        label: str,
        max_attempts: int = 4,
        base_delay_s: float = 1.5,
        max_delay_s: float = 20.0,
    ) -> T:
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                return fn()
            except Exception as e:
                last_error = e
                if (not self._is_rate_limit_error(e)) or attempt >= max_attempts:
                    raise
                delay = min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))
                print(
                    f"  - {label}: rate limited(429), retry in {delay:.1f}s "
                    f"(attempt {attempt}/{max_attempts})"
                )
                time.sleep(delay)
        # logical fallback (for type checker)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"{label}: unknown retry failure")

    def _load_existing_project(self) -> Dict[str, Any]:
        path = self.paths.out_dir / self.cfg.json_name
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _wipe_base_dir(self) -> None:
        """
        base_dir(work/<story-id>/) 전체 삭제 후 재생성.
        """
        base = Path(self.cfg.base_dir)
        try:
            if base.exists():
                shutil.rmtree(base)
        except Exception as e:
            raise RuntimeError(f"base_dir 삭제 실패: {base} ({e})")

        # paths 재생성
        self.paths = ProjectPaths.from_base(self.cfg.base_dir)
        self.paths.ensure()
        self.db = JsonDB(self.paths.out_dir / self.cfg.json_name)

    def _open_dir(self, path: Path) -> None:
        """
        macOS: Finder로 폴더 열기
        """
        try:
            pass #subprocess.run(["open", str(path)], check=False)
        except Exception:
            pass
    
    def _call_with_heartbeat(
        self,
        fn: Callable[[], T],
        title: str,
        interval_s: float = 1.0,
        dot: str = ".",
    ) -> T:
        """
        fn()을 별도 스레드에서 실행하고, 메인 스레드에서 주기적으로 heartbeat 출력.
        - 성공 시 fn() 반환값 리턴
        - 실패 시 예외 재-raise
        """
        done = threading.Event()
        result_box: Dict[str, Any] = {}
        err_box: Dict[str, Any] = {}

        def _runner():
            try:
                result_box["value"] = fn()
            except Exception as e:
                err_box["error"] = e
            finally:
                done.set()

        th = threading.Thread(target=_runner, daemon=True)
        th.start()

        t0 = time.time()
        print(f"  - {title} (heartbeat {interval_s:.1f}s)", end="", flush=True)

        # heartbeat loop
        last_break = 0
        while not done.wait(interval_s):
            elapsed = int(time.time() - t0)
            if elapsed >= last_break + 60:
                last_break = elapsed
                print(f"\n  - {title} still running... {elapsed}s", end="", flush=True)
            else:
                print(dot, end="", flush=True)

        dt = time.time() - t0
        print(f" done ({dt:.1f}s)")

        if "error" in err_box:
            raise err_box["error"]
        return result_box.get("value")  # 타입상 T|None 이지만 실사용은 OK

    def _fmt_eta(self, sec: float) -> str:
        if sec < 0:
            sec = 0
        s = int(sec + 0.5)
        h = s // 3600
        m = (s % 3600) // 60
        s = s % 60
        if h > 0:
            return f"{h}h {m}m {s}s"
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    def _avg_time(self, total_time: float, n: int) -> float:
        return (total_time / n) if n > 0 else 0.0

    def _norm_variants(self, c: Dict[str, Any]) -> List[str]:
        v = c.get("variants", [])
        if not isinstance(v, list):
            return [""]
        out: List[str] = []
        for x in v:
            if isinstance(x, str):
                out.append(x.strip())
        if not out:
            return [""]
        return out

    def _clean_str_list(self, values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        out: List[str] = []
        for x in values:
            if not isinstance(x, str):
                continue
            s = x.strip()
            if s and s not in out:
                out.append(s)
        return out

    def _is_child_stage(self, age_stage: str) -> bool:
        return (age_stage or "").strip() == "아동"

    def _filter_anchors_by_stage(self, anchors: List[str], age_stage: str) -> List[str]:
        out = self._clean_str_list(anchors)
        stage = (age_stage or "").strip()

        # 아동 장면: 성인화/영아화/고강도 병증 단서를 줄인다.
        if stage == "아동":
            adult_markers = (
                "청년", "성인", "아가씨", "처자", "장성", "중년", "노년", "어른",
                "청년기", "성인기", "훌쩍 자라", "성장 후", "늠름한", "듬직한",
            )
            risky_markers = (
                "피 섞인", "피가", "유혈", "토혈", "시신", "사망", "죽어",
                "불덩이 같은 이마", "신음", "창백한 얼굴", "병색", "숨이 넘어",
                "포대기에 싸인", "갓난", "신생아", "영아", "유아",
                "업힌", "업혀", "등에 업", "등에 메", "안긴", "안겨",
            )
            child_only: List[str] = []
            for s in out:
                if any(m in s for m in adult_markers):
                    continue
                if any(m in s for m in risky_markers):
                    continue
                child_only.append(s)
            return child_only

        # 청소년/청년 장면: 아동/영아/업힘 단서를 제거해 stage 충돌을 막는다.
        if stage in ("청소년", "청년"):
            child_markers = (
                "아동", "유아", "영아", "갓난", "신생아", "일곱 살", "5세", "7세",
                "작은 몸집", "통통한 볼살", "포대기", "포대기에 싸인",
                "업힌", "업혀", "등에 업",
            )
            adult_only = [s for s in out if not any(m in s for m in child_markers)]
            return adult_only

        return out

    def _normalize_age_hint(self, age_stage: str, raw_hint: str) -> str:
        if self._is_child_stage(age_stage):
            return "약 5세"
        return (raw_hint or "").strip()

    def _filter_anchors_by_variant(self, anchors: List[str], variant: str) -> List[str]:
        out = self._clean_str_list(anchors)
        v = (variant or "").strip()
        if not v:
            return out

        if v == "노비":
            blocked = ("무관", "장검", "호패", "인장", "은침통", "갑옷", "관복")
            keep = [s for s in out if not any(k in s for k in blocked)]
            preferred = [s for s in keep if any(k in s for k in ("노비", "무명", "적삼", "거친", "해진"))]
            return preferred + [s for s in keep if s not in preferred]

        if v == "무관":
            blocked = ("노비", "무명 적삼", "해진", "거친")
            keep = [s for s in out if not any(k in s for k in blocked)]
            preferred = [s for s in keep if any(k in s for k in ("무관", "도포", "장검", "호패", "인장"))]
            return preferred + [s for s in keep if s not in preferred]

        return out

    def _augment_anchors_with_variant(self, anchors: List[str], variant: str) -> List[str]:
        out = self._clean_str_list(anchors)
        v = (variant or "").strip()
        if not v:
            return out

        # story30: ensure this disguise reads as a full pink silk outfit,
        # not just a single pink sleeve patch.
        if v == "torn_pink_silk":
            forced = [
                "full pink silk hanbok silhouette, both jeogori and chima in pink tones",
                "visibly torn pink silk sleeves and ripped skirt hem",
                "frayed seams and hanging loose silk threads",
            ]
            for x in reversed(forced):
                if x not in out:
                    out.insert(0, x)

        # Scene-level variant text often carries the strongest disguise cue.
        # Promote it into stable outfit/appearance anchors so adjacent clips
        # keep the same disguise instead of inventing a fresh costume concept.
        if v not in out:
            out.insert(0, v)

        if ("변복" in v or "복장" in v or "차림" in v or "분장" in v) and "same disguise continuity" not in out:
            out.insert(1, "same disguise continuity")
        return out

    def _filter_risky_character_sheet_anchors(self, anchors: List[str]) -> List[str]:
        """
        캐릭터 단독 시트에서는 고강도 병증/유혈/사망 뉘앙스를 제거해
        EMPTY_IMAGE_BYTES/안전 차단 확률을 낮춘다.
        """
        out = self._clean_str_list(anchors)
        blocked = (
            "피 섞인", "유혈", "토혈", "시신", "사망", "죽어", "숨이 넘어",
            "불덩이 같은 이마", "신음", "고꾸라진", "피가",
            # A군(비참/피폐) 질감 유도 단서 축소
            "병색", "창백", "허연 입술", "가느다란 숨", "힘없이", "아픈 모습", "떨고 있는",
            "흙먼지", "해진", "누더기", "잿빛 안색", "후들거리는", "절박한", "오열", "애원",
            "짓무른", "상처", "피 맺힌", "초라한",
        )
        return [s for s in out if not any(k in s for k in blocked)]

    def _scene_character_score(
        self,
        scene_text: str,
        cobj: Dict[str, Any],
        order_idx: int,
    ) -> int:
        name = str(cobj.get("name") or "").strip()
        if not name:
            return -10_000

        text = str(scene_text or "")
        score = max(0, 50 - order_idx)

        if cobj.get("role") == "주인공":
            score += 10

        direct_patterns = [
            rf"{re.escape(name)}[은는이가을를의]",
            rf"{re.escape(name)}\s*대감[은는이가을를의]?",
            rf"\"{re.escape(name)}",
        ]
        if any(re.search(p, text) for p in direct_patterns):
            score += 120
        elif name in text:
            score += 60

        # Indirect mention such as "... 박종악 대감 쪽에서 사람을 보내 ..."
        indirect_patterns = [
            rf"{re.escape(name)}[^.\n]{{0,12}}쪽",
            rf"{re.escape(name)}[^.\n]{{0,18}}사람을 보내",
            rf"{re.escape(name)}[^.\n]{{0,18}}문안을",
        ]
        if any(re.search(p, text) for p in indirect_patterns):
            score -= 90

        return score

    def _select_scene_character_ids(
        self,
        scene_text: str,
        char_ids: List[str],
        char_map: Dict[str, Dict[str, Any]],
        limit: int = 2,
    ) -> List[str]:
        ranked: List[Tuple[int, str]] = []
        for idx, cid in enumerate(char_ids):
            cobj = char_map.get(cid)
            if not isinstance(cobj, dict):
                continue
            ranked.append((self._scene_character_score(scene_text, cobj, idx), cid))
        ranked.sort(key=lambda x: x[0], reverse=True)

        out: List[str] = []
        for _, cid in ranked:
            if cid not in out:
                out.append(cid)
            if len(out) >= max(1, int(limit)):
                break
        return out

    def _infer_species(
        self,
        name: str,
        aliases: List[str],
        anchors: List[str],
        script_text: str = "",
    ) -> str:
        corpus = " ".join([name or "", " ".join(aliases or []), " ".join(anchors or []), script_text or ""])
        if any(tok in corpus for tok in ("황소", "암소", "수소", "송아지", "소")):
            return "소"
        if any(tok in corpus for tok in ("강아지", "개", "진돗개")):
            return "개"
        if any(tok in corpus for tok in ("말", "망아지", "준마")):
            return "말"
        # '누렁이'는 소/개 모두에 쓰일 수 있으므로 전체 대본 문맥으로 판별을 시도한다.
        if "누렁이" in corpus:
            cattle_hits = sum(1 for t in ("황소", "암소", "수소", "송아지", "외양간", "쟁기", "발굽", "고삐") if t in corpus)
            dog_hits = sum(1 for t in ("강아지", "진돗개", "개집", "짖", "꼬리") if t in corpus)
            if cattle_hits > dog_hits:
                return "소"
            if dog_hits > cattle_hits:
                return "개"
            return "기타"
        return "인간"

    def _pick_main_characters(self, project: Dict[str, Any], max_supporting: int = 4) -> List[Dict[str, Any]]:
        chars = [c for c in project.get("characters", []) if isinstance(c, dict)]
        scenes = [s for s in project.get("scenes", []) if isinstance(s, dict)]

        counts = {c.get("id"): 0 for c in chars if c.get("id")}
        for s in scenes:
            for cid in (s.get("characters") or []):
                if cid in counts:
                    counts[cid] += 1

        protagonist = None
        for c in chars:
            if c.get("role") == "주인공":
                protagonist = c
                break
        if protagonist is None:
            protagonist = max(chars, key=lambda c: counts.get(c.get("id"), 0), default=None)

        supporting = [c for c in chars if protagonist is None or c.get("id") != protagonist.get("id")]
        supporting.sort(key=lambda c: counts.get(c.get("id"), 0), reverse=True)
        supporting = supporting[:max_supporting]

        selected: List[Dict[str, Any]] = []
        if protagonist:
            selected.append(protagonist)
        selected.extend(supporting)
        return selected
    
# ===== orchestrator.py (PART 2/4) =====
    def _chars_work_left(self, project: Dict[str, Any]) -> Tuple[bool, int, int]:
        """
        return: (work_left, total_jobs, remaining_jobs)
        - selected main chars(주인공+조연 일부)만 기준.
        """
        selected = self._pick_main_characters(project, max_supporting=8)
        total = 0
        remain = 0

        for c in selected:
            name = str(c.get("name", "unknown"))
            cid = str(c.get("id", "char_000"))

            meta_map = c.get("images")
            if not isinstance(meta_map, dict):
                meta_map = {}

            for var in self._norm_variants(c):
                total += 1
                safe = _safe_filename(name)
                var_safe = _safe_filename(var) if var else ""
                fname = f"{cid}_{safe}" + (f"_{var_safe}" if var_safe else "") + ".jpg"
                ok_path = self.paths.characters_dir / fname
                err_path = self.paths.characters_dir / (fname.replace(".jpg", "_error.jpg"))

                variant_key = var if var else "__default__"
                vmeta = meta_map.get(variant_key)
                if not isinstance(vmeta, dict):
                    vmeta = _default_image_meta()

                done_ok = (vmeta.get("status") == "ok") and ok_path.exists() and (not err_path.exists())
                if not done_ok:
                    remain += 1

        return (remain > 0, total, remain)

    def _places_work_left(self, project: Dict[str, Any]) -> Tuple[bool, int, int]:
        places = [p for p in project.get("places", []) if isinstance(p, dict)]
        total = len(places)
        remain = 0

        for p in places:
            pid = str(p.get("id", "place_000"))
            name = str(p.get("name", "unknown"))
            safe = _safe_filename(name)

            ok_path = self.paths.places_dir / f"{pid}_{safe}.jpg"
            err_path = self.paths.places_dir / f"{pid}_{safe}_error.jpg"
            meta = p.get("image") if isinstance(p.get("image"), dict) else _default_image_meta()

            done_ok = (meta.get("status") == "ok") and ok_path.exists() and (not err_path.exists())
            if not done_ok:
                remain += 1

        return (remain > 0, total, remain)

    def _clips_work_left(self, project: Dict[str, Any]) -> Tuple[bool, int, int]:
        scenes = [s for s in project.get("scenes", []) if isinstance(s, dict)]
        total = len(scenes)
        remain = 0

        for s in scenes:
            sid = int(s.get("id", 0))
            ok_path = self.paths.clips_dir / f"{sid:03d}.jpg"
            err_path = self.paths.clips_dir / f"{sid:03d}_error.jpg"
            meta = s.get("image") if isinstance(s.get("image"), dict) else _default_image_meta()
            _cleanup_stale_error_file(meta, ok_path, err_path)

            done_ok = (meta.get("status") == "ok") and ok_path.exists() and (not err_path.exists())
            if not done_ok:
                remain += 1

        return (remain > 0, total, remain)

    def run(self) -> Dict[str, Any]:
        # 1) 대본 읽기 + 전처리
        print(f"[1/7] script loaded: {self.cfg.input_script_path}")
        raw = read_text_file(self.cfg.input_script_path)
        norm = normalize_script(raw)

        marked_text, clean_text = preprocess_chapters(norm)

        # script_hash 계산(대본 동일성 판단)
        script_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

        # 기존 project.json 로드
        existing = self._load_existing_project()
        prev_hash = None
        if isinstance(existing, dict):
            prev_hash = (existing.get("project") or {}).get("script_hash")

        # ------------------------------------------------------------
        # ✅ 대본 변경 감지 -> wipe + full restart (confirm)
        # ------------------------------------------------------------
        if prev_hash and prev_hash != script_hash:
            if self._confirm(
                "대본이 변경되었습니다. 기존 산출물을 모두 삭제하고 새로 시작할까요?",
                f"- prev_hash={prev_hash[:8]}...\n- new_hash={script_hash[:8]}...\n- delete: {self.cfg.base_dir}"
            ):
                self._wipe_base_dir()
                existing = {}
                prev_hash = None
                print("[0/7] wiped base_dir, restart from scratch")
            else:
                # 사용자가 거부하면 기존 프로젝트 그대로 반환(안전)
                print("[0/7] user aborted restart; keep existing output")
                return existing if isinstance(existing, dict) else {}

        # ------------------------------------------------------------
        # ✅ 대본 동일 + 기존 scenes 존재 => split/LLM/merge 스킵
        # ------------------------------------------------------------
        reuse_scenes = False
        if prev_hash and prev_hash == script_hash:
            prev_scenes = existing.get("scenes") if isinstance(existing, dict) else None
            if isinstance(prev_scenes, list) and len(prev_scenes) > 0:
                reuse_scenes = True
                print(f"[0/7] script_hash unchanged -> reuse existing scenes ({len(prev_scenes)})")

        if reuse_scenes:
            project = existing if isinstance(existing, dict) else {}
            project.setdefault("project", {})
            project["project"].update({
                "era_profile": self.cfg.era_profile,
                "style_profile": self.cfg.style_profile,
                "input_script_path": self.cfg.input_script_path,
                "script_hash": script_hash,
                "script_hash_algo": "sha256",
                "script_hash_source": "clean_text",
                "scene_min_s": self.cfg.scene_min_s,
                "scene_max_s": self.cfg.scene_max_s,
                "scene_base_len": self.cfg.scene_base_len,
                "llm_extract": {
                    "enabled": False,
                    "ok": False,
                    "skipped": True,
                    "reason": "script_hash unchanged (reuse scenes)",
                },
                "phase": "structure_fixed",
                "phase_detail": "reuse_scenes",
            })
            self.db.save(project)
            print(f"[3/7] project reused: chars={len(project.get('characters',[]))} places={len(project.get('places',[]))} scenes={len(project.get('scenes',[]))}")
            if self.cfg.stop_after_tag_scene:
                print("[3.5/7] stop_after_tag_scene: stop before LLM extract and later stages")
                return project
        else:
            # ------------------------------------------------------------
            # ✅ 새로 split/LLM/merge 수행
            # ------------------------------------------------------------
            sentences = split_sentences_korean(marked_text)

            print("[2/7] LLM extract: start")
            seed_chars = extract_characters(clean_text)
            seed_places = extract_places(clean_text)

            # 문장에 챕터 메타 부착
            sent_with_ch = attach_chapters(sentences)

            scenes: List[Scene] = []
            scene_chapter: Dict[int, Optional[ChapterInfo]] = {}

            buf: List[str] = []
            cur_ch: Optional[ChapterInfo] = None
            next_id = 1

            def flush_chunk(chunk: List[str], ch: Optional[ChapterInfo]) -> None:
                nonlocal next_id, scenes, scene_chapter
                if not chunk:
                    return
                part = split_into_scenes(
                    chunk,
                    min_s=self.cfg.scene_min_s,
                    max_s=self.cfg.scene_max_s,
                    base_len=self.cfg.scene_base_len,
                )
                for sc in part:
                    sc.id = next_id
                    next_id += 1
                    scenes.append(sc)
                    scene_chapter[sc.id] = ch

            for sent, ch in sent_with_ch:
                if cur_ch is None:
                    cur_ch = ch
                if ch != cur_ch:
                    flush_chunk(buf, cur_ch)
                    buf = []
                    cur_ch = ch
                buf.append(sent)

            flush_chunk(buf, cur_ch)

            # 규칙 기반 장면 태깅(LLM 실패 시 폴백용)
            scene_records: List[Dict[str, Any]] = []
            for sc in scenes:
                ch = scene_chapter.get(sc.id)
                tags = tag_scene(sc, seed_chars, seed_places)
                scene_records.append({
                    "id": sc.id,
                    "chapter_no": (ch.no if ch else None),
                    "chapter_title": (ch.title if ch else None),
                    "sentences": sc.sentences,
                    "text": sc.text,
                    "characters": tags["characters"],
                    "places": tags["places"],
                    "character_instances": [],
                    "llm_clip_prompt": "",
                    "image": _default_image_meta(),
                })

            # LLM 기반 추출/정규화/태깅
            llm_debug: Dict[str, Any] = {"enabled": (not self.cfg.stop_after_tag_scene), "ok": False}
            llm_out: Optional[Dict[str, Any]] = None
            if self.cfg.stop_after_tag_scene:
                llm_debug["skipped"] = True
                llm_debug["reason"] = "stop_after_tag_scene"
                print("[2/7] LLM extract: skipped by stop_after_tag_scene")
            else:
                try:
                    extractor = LLMEntityExtractor(
                        LLMExtractorConfig(model=self.cfg.llm_model, temperature=0.1)
                    )
                    def _do_llm_call():
                        return extractor.extract(
                            era_profile=self.cfg.era_profile,
                            style_profile=self.cfg.style_profile,
                            script_text=clean_text,
                            scenes=[{"id": sc.id, "text": sc.text} for sc in scenes],
                            seed_char_candidates=[c.name for c in seed_chars],
                            seed_place_candidates=[p.name for p in seed_places],
                        )
                    llm_out = self._call_with_heartbeat(
                        _do_llm_call,
                        title="[2/7] LLM extract(remote)",
                        interval_s=1.0,
                        dot=".",
                    )
                    llm_debug["ok"] = True
                    llm_debug["result"] = llm_out
                except Exception as e:
                    llm_debug["ok"] = False
                    llm_debug["error"] = str(e)
                    llm_out = None
                print("[2/7] LLM extract: ok" if llm_debug["ok"] else f"[2/7] LLM extract: fail: {llm_debug.get('error')}")

# ===== orchestrator.py (PART 3/4) =====
            def init_or_merge(data: Dict[str, Any]) -> Dict[str, Any]:
                data.setdefault("project", {})
                data["project"].update({
                    "era_profile": self.cfg.era_profile,
                    "style_profile": self.cfg.style_profile,
                    "input_script_path": self.cfg.input_script_path,
                    "script_hash": script_hash,
                    "script_hash_algo": "sha256",
                    "script_hash_source": "clean_text",
                    "scene_min_s": self.cfg.scene_min_s,
                    "scene_max_s": self.cfg.scene_max_s,
                    "scene_base_len": self.cfg.scene_base_len,
                    "phase": "structure_fixed",
                    "phase_detail": ("through_tag_scene" if self.cfg.stop_after_tag_scene else "fresh_split_merge"),
                })
                data["project"]["llm_extract"] = llm_debug

                existing_chars_by_name = {
                    c.get("name"): c for c in data.get("characters", [])
                    if isinstance(c, dict) and c.get("name")
                }
                existing_places_by_name = {
                    p.get("name"): p for p in data.get("places", [])
                    if isinstance(p, dict) and p.get("name")
                }

                llm_chars = (llm_out or {}).get("characters", []) if llm_debug.get("ok") else []
                llm_places = (llm_out or {}).get("places", []) if llm_debug.get("ok") else []
                llm_scene_tags = (llm_out or {}).get("scene_tags", []) if llm_debug.get("ok") else []
                llm_scene_prompts = (llm_out or {}).get("scene_prompts", []) if llm_debug.get("ok") else []

                # characters
                new_chars: List[Dict[str, Any]] = []
                if llm_chars:
                    for i, c in enumerate(llm_chars, start=1):
                        name = str(c.get("name_canonical", "")).strip()
                        if not name:
                            continue
                        prev = existing_chars_by_name.get(name, {})
                        img_meta = prev.get("image") if isinstance(prev.get("image"), dict) else _default_image_meta()
                        img_meta.setdefault("prompt_history", [])
                        prev_images = prev.get("images") if isinstance(prev.get("images"), dict) else {}

                        new_chars.append({
                            "id": f"char_{i:03d}",
                            "name": name,
                            "aliases": c.get("aliases", []),
                            "species": str(
                                c.get("species")
                                or self._infer_species(
                                    name,
                                    c.get("aliases", []),
                                    c.get("visual_anchors", []),
                                    clean_text,
                                )
                            ),
                            "role": c.get("role", "조연"),
                            "traits": c.get("traits", []),
                            "visual_anchors": c.get("visual_anchors", []),
                            "gender": c.get("gender", "불명"),
                            "age_stage": c.get("age_stage", "불명"),
                            "age_hint": c.get("age_hint", ""),
                            "variants": c.get("variants", []),
                            "context": c.get("context", "민간"),
                            "court_role": c.get("court_role", ""),
                            "social_class": c.get("social_class", "불명"),
                            "wealth_level": c.get("wealth_level", "불명"),
                            "wardrobe_tier": c.get("wardrobe_tier", "T2"),
                            "wardrobe_anchors": c.get("wardrobe_anchors", []),
                            "images": prev_images,
                            "image": img_meta,
                        })
                else:
                    for i, c in enumerate(seed_chars, start=1):
                        name = c.name
                        prev = existing_chars_by_name.get(name, {})
                        img_meta = prev.get("image") if isinstance(prev.get("image"), dict) else _default_image_meta()
                        img_meta.setdefault("prompt_history", [])
                        new_chars.append({
                            "id": f"char_{i:03d}",
                            "name": name,
                            "hints": c.hints,
                            "species": self._infer_species(name, [], c.hints, clean_text),
                            "image": img_meta,
                        })

                # places
                new_places: List[Dict[str, Any]] = []
                if llm_places:
                    for i, p in enumerate(llm_places, start=1):
                        name = str(p.get("name_canonical", "")).strip()
                        if not name:
                            continue
                        prev = existing_places_by_name.get(name, {})
                        img_meta = prev.get("image") if isinstance(prev.get("image"), dict) else _default_image_meta()
                        img_meta.setdefault("prompt_history", [])
                        new_places.append({
                            "id": f"place_{i:03d}",
                            "name": name,
                            "aliases": p.get("aliases", []),
                            "visual_anchors": p.get("visual_anchors", []),
                            "image": img_meta,
                        })
                else:
                    for i, p in enumerate(seed_places, start=1):
                        name = p.name
                        prev = existing_places_by_name.get(name, {})
                        img_meta = prev.get("image") if isinstance(prev.get("image"), dict) else _default_image_meta()
                        img_meta.setdefault("prompt_history", [])
                        new_places.append({
                            "id": f"place_{i:03d}",
                            "name": name,
                            "hints": p.hints,
                            "image": img_meta,
                        })

                data["characters"] = new_chars
                data["places"] = new_places

                char_name_to_id = {c["name"]: c["id"] for c in new_chars if c.get("name") and c.get("id")}
                place_name_to_id = {p["name"]: p["id"] for p in new_places if p.get("name") and p.get("id")}

                def _names_for_match(item: Dict[str, Any]) -> List[str]:
                    names: List[str] = []
                    primary = str(item.get("name", "")).strip()
                    if primary:
                        names.append(primary)
                    for alias in item.get("aliases", []) or []:
                        alias_s = str(alias).strip()
                        if alias_s:
                            names.append(alias_s)
                    # prefer longer aliases first to avoid role-name shadowing
                    return sorted(set(names), key=len, reverse=True)

                def _backfill_scene_tags(scene_text: str) -> Dict[str, Any]:
                    scene_chars: List[str] = []
                    scene_places: List[str] = []
                    scene_instances: List[Dict[str, str]] = []

                    for c in new_chars:
                        cid = c.get("id")
                        if not cid:
                            continue
                        if any(name in scene_text for name in _names_for_match(c)):
                            scene_chars.append(cid)

                            variants = [str(v).strip() for v in c.get("variants", []) or [] if str(v).strip()]
                            if variants:
                                chosen_variant = ""
                                for variant in variants:
                                    if variant in scene_text:
                                        chosen_variant = variant
                                        break
                                if not chosen_variant and len(variants) == 1:
                                    chosen_variant = variants[0]
                                if chosen_variant:
                                    scene_instances.append({"char_id": cid, "variant": chosen_variant})

                    for p in new_places:
                        pid = p.get("id")
                        if not pid:
                            continue
                        if any(name in scene_text for name in _names_for_match(p)):
                            scene_places.append(pid)

                    return {
                        "characters": scene_chars,
                        "places": scene_places,
                        "character_instances": scene_instances,
                    }

                # LLM scene tag map
                llm_tag_map: Dict[int, Dict[str, Any]] = {}
                for t in llm_scene_tags or []:
                    try:
                        sid = int(t.get("scene_id"))
                    except Exception:
                        continue

                    ch_ids: List[str] = []
                    for nm in t.get("characters", []) or []:
                        cid = char_name_to_id.get(nm)
                        if cid:
                            ch_ids.append(cid)

                    pl_ids: List[str] = []
                    for nm in t.get("places", []) or []:
                        pid = place_name_to_id.get(nm)
                        if pid:
                            pl_ids.append(pid)

                    inst: List[Dict[str, str]] = []
                    for it in (t.get("character_instances", []) or []):
                        nm = it.get("name")
                        var = it.get("variant", "")
                        cid = char_name_to_id.get(nm)
                        if cid:
                            inst.append({"char_id": cid, "variant": var})

                    llm_tag_map[sid] = {
                        "characters": ch_ids,
                        "places": pl_ids,
                        "character_instances": inst,
                    }

                llm_prompt_map: Dict[int, str] = {}
                for sp in llm_scene_prompts or []:
                    try:
                        sid = int(sp.get("scene_id"))
                    except Exception:
                        continue
                    ptxt = str(sp.get("prompt") or "").strip()
                    if ptxt:
                        llm_prompt_map[sid] = ptxt

                existing_scenes = {
                    int(s.get("id")): s for s in data.get("scenes", [])
                    if isinstance(s, dict) and s.get("id") is not None
                }

                # merge scenes: (new id set is authoritative)
                merged: Dict[int, Dict[str, Any]] = {}
                for srec in scene_records:
                    sid = int(srec["id"])
                    prev = existing_scenes.get(sid)
                    if isinstance(prev, dict):
                        # keep previous image meta if exists
                        img_meta = prev.get("image") if isinstance(prev.get("image"), dict) else _default_image_meta()
                        prev_llm_prompt = str(prev.get("llm_clip_prompt") or "").strip()
                    else:
                        img_meta = _default_image_meta()
                        prev_llm_prompt = ""

                    # apply tags (LLM preferred)
                    if sid in llm_tag_map:
                        llm_tags = llm_tag_map[sid]
                        srec["characters"] = llm_tags["characters"]
                        srec["places"] = llm_tags["places"]
                        srec["character_instances"] = llm_tags.get("character_instances", [])

                        # LLM 태그가 비어 있거나 지나치게 약하면 이름/alias 직접 매칭으로 보강한다.
                        backfill = _backfill_scene_tags(str(srec.get("text", "")))
                        if not srec["characters"]:
                            srec["characters"] = backfill["characters"]
                        else:
                            seen = set(srec["characters"])
                            srec["characters"].extend([cid for cid in backfill["characters"] if cid not in seen])

                        if not srec["places"]:
                            srec["places"] = backfill["places"]
                        else:
                            seen = set(srec["places"])
                            srec["places"].extend([pid for pid in backfill["places"] if pid not in seen])

                        if not srec["character_instances"]:
                            srec["character_instances"] = backfill["character_instances"]
                    else:
                        # LLM 실패 시: 규칙 기반 태깅 사용(단, id 매핑이 seed와 맞는지에 따라 품질 차이 있음)
                        # 여기서는 scene_records 기본 태깅에 alias 기반 보강을 추가한다.
                        backfill = _backfill_scene_tags(str(srec.get("text", "")))
                        if not srec.get("characters"):
                            srec["characters"] = backfill["characters"]
                        if not srec.get("places"):
                            srec["places"] = backfill["places"]
                        if not srec.get("character_instances"):
                            srec["character_instances"] = backfill["character_instances"]

                    srec["image"] = img_meta
                    srec["llm_clip_prompt"] = llm_prompt_map.get(sid, prev_llm_prompt)
                    merged[sid] = srec

                data["scenes"] = [merged[i] for i in sorted(merged.keys())]
                return data

            project = self.db.upsert(init_or_merge)
            print(f"[3/7] project upserted: chars={len(project.get('characters',[]))} places={len(project.get('places',[]))} scenes={len(project.get('scenes',[]))}")
            if self.cfg.stop_after_tag_scene:
                self.db.save(project)
                print("[3.5/7] stop_after_tag_scene: saved rule-based structure and stop before LLM-dependent stages")
                return project

# ===== orchestrator.py (PART 4/4) =====
        scenes_for_rules = [s for s in project.get("scenes", []) if isinstance(s, dict)]
        chars_for_rules = [c for c in project.get("characters", []) if isinstance(c, dict)]
        places_for_rules = [p for p in project.get("places", []) if isinstance(p, dict)]

        auto_rules = self._plan_auto_scene_rules(
            script_text=clean_text,
            scenes=scenes_for_rules,
            chars=chars_for_rules,
            places=places_for_rules,
        )
        project.setdefault("project", {})
        project["project"]["auto_scene_rules"] = auto_rules

        # Optional scene-level locks from story-specific YAML
        # 1) auto rules generated by LLM from script/scenes
        self._apply_variant_overrides(
            scenes_for_rules,
            chars_for_rules,
            overrides=list(auto_rules.get("variant_overrides") or []),
        )
        self._apply_scene_bindings(
            scenes_for_rules,
            chars_for_rules,
            places_for_rules,
            bindings=list(auto_rules.get("scene_bindings") or []),
        )

        # 2) manual lock rules from stories/<story-id>_*.yaml (higher priority)
        self._apply_variant_overrides(scenes_for_rules, chars_for_rules)
        self._apply_scene_bindings(scenes_for_rules, chars_for_rules, places_for_rules)
        self._update_used_by_scenes(scenes_for_rules, chars_for_rules, places_for_rules)
        self.db.save(project)

        retry = RetryPolicy(max_attempts=3, policy_rewrite_max_level=3)

        # 최신 맵 (project 기준)
        char_map = {c["id"]: c for c in project.get("characters", []) if isinstance(c, dict) and c.get("id")}
        place_map = {p["id"]: p for p in project.get("places", []) if isinstance(p, dict) and p.get("id")}

        def resolve_char_names(char_ids: List[str]) -> List[str]:
            out: List[str] = []
            for cid in char_ids:
                c = char_map.get(cid)
                if c and c.get("name"):
                    out.append(str(c["name"]))
            return out

        def resolve_place_name(place_ids: List[str]) -> Optional[str]:
            if not place_ids:
                return None
            p = place_map.get(place_ids[0])
            return str(p["name"]) if p and p.get("name") else None

        # ------------------------------------------------------------
        # (4/7) characters generate (only if work left)
        # ------------------------------------------------------------
        ch_left, ch_total, ch_remain = self._chars_work_left(project)
        if ch_left:
            if self.cfg.interactive:
                if not self._confirm(
                    "캐릭터 이미지 생성을 시작할까요?",
                    f"- remain={ch_remain}/{ch_total}\n- dir={self.paths.characters_dir}"
                ):
                    return project

            # Keep a wider supporting set so story-critical side characters
            # (e.g., witness/hostage/court-lady roles) also receive reference images.
            selected_chars = self._pick_main_characters(project, max_supporting=8)

            total = 0
            for c in selected_chars:
                total += len(self._norm_variants(c))

            done = 0
            skip = 0
            regen = 0
            gen_ok = 0
            gen_err = 0
            gen_time_sum = 0.0
            gen_count = 0
            section_t0 = time.time()

            print(f"[4/7] characters: total_jobs={total}")

            for c in selected_chars:
                meta_map = c.setdefault("images", {})
                if not isinstance(meta_map, dict):
                    meta_map = {}
                    c["images"] = meta_map

                name = str(c.get("name", "unknown"))
                gender = str(c.get("gender", "불명"))
                age_stage = str(c.get("age_stage", "불명"))
                anchors = c.get("visual_anchors", []) or c.get("hints", []) or []
                if not isinstance(anchors, list):
                    anchors = []

                for var in self._norm_variants(c):
                    done += 1

                    safe = _safe_filename(name)
                    var_safe = _safe_filename(var) if var else ""
                    cid = str(c.get("id", "char_000"))

                    fname = f"{cid}_{safe}" + (f"_{var_safe}" if var_safe else "") + ".jpg"
                    ok_path = self.paths.characters_dir / fname
                    err_path = self.paths.characters_dir / (fname.replace(".jpg", "_error.jpg"))

                    variant_key = var if var else "__default__"
                    vmeta = meta_map.get(variant_key)
                    if not isinstance(vmeta, dict):
                        vmeta = _default_image_meta()
                    _cleanup_stale_error_file(vmeta, ok_path, err_path)

                    if vmeta.get("status") == "ok" and ok_path.exists() and (not err_path.exists()):
                        skip += 1
                        meta_map[variant_key] = vmeta
                        avg = self._avg_time(gen_time_sum, gen_count)
                        eta = self._fmt_eta(avg * max(total - done, 0))
                        print(f"[4/7] characters {done}/{total} (skip={skip}, ok={gen_ok}, err={gen_err}, regen={regen}) ETA~{eta}: {ok_path.name}  -> skip")
                        continue

                    if vmeta.get("status") == "ok" and not ok_path.exists():
                        regen += 1
                        vmeta["status"] = "pending"
                        vmeta["attempts"] = 0
                        vmeta["last_error"] = None
                        vmeta["path"] = None
                        vmeta["policy_rewrite_level"] = 0
                        vmeta["prompt_history"] = []

                    avg = self._avg_time(gen_time_sum, gen_count)
                    eta = self._fmt_eta(avg * max(total - done, 0))
                    print(f"[4/7] characters {done}/{total} (skip={skip}, ok={gen_ok}, err={gen_err}, regen={regen}) ETA~{eta}: {ok_path.name}  -> gen")

                    age_stage_for_prompt = age_stage
                    if var in ("아동", "청소년", "청년", "중년", "노년"):
                        age_stage_for_prompt = var
                    anchors2 = self._filter_anchors_by_stage(list(anchors), age_stage_for_prompt)
                    anchors2 = self._augment_anchors_with_variant(anchors2, var)
                    anchors2 = self._filter_risky_character_sheet_anchors(anchors2)
                    if self._is_child_stage(age_stage_for_prompt):
                        anchors2.append("나이: 약 5세(아동)")

                    wardrobe_anchors = c.get("wardrobe_anchors", [])
                    if not isinstance(wardrobe_anchors, list):
                        wardrobe_anchors = []
                    wardrobe_anchors = self._filter_anchors_by_stage(wardrobe_anchors, age_stage_for_prompt)
                    wardrobe_anchors = self._filter_anchors_by_variant(wardrobe_anchors, var)
                    wardrobe_anchors = self._augment_anchors_with_variant(wardrobe_anchors, var)
                    wardrobe_anchors = self._filter_risky_character_sheet_anchors(wardrobe_anchors)

                    prompt = build_character_prompt(
                        self.era, self.char_style, name, anchors2,
                        gender=gender, age_stage=age_stage_for_prompt, variant=var,
                        species=str(c.get("species", "인간") or "인간"),
                        context=str(c.get("context", "민간")),
                        court_role=str(c.get("court_role", "")),
                        social_class=str(c.get("social_class", "불명")),
                        wealth_level=str(c.get("wealth_level", "불명")),
                        wardrobe_tier=str(c.get("wardrobe_tier", "T2")),
                        wardrobe_anchors=wardrobe_anchors,
                    )

                    t0 = time.time()
                    vmeta = generate_with_fallback(
                        client=self.img_client,
                        out_ok_path=ok_path,
                        out_error_path=err_path,
                        prompt=prompt,
                        retry=retry,
                        meta=vmeta,
                        aspect_ratio="3:4",
                    )
                    dt = time.time() - t0
                    gen_time_sum += dt
                    gen_count += 1

                    if vmeta.get("status") == "ok":
                        gen_ok += 1
                    else:
                        gen_err += 1

                    meta_map[variant_key] = vmeta
                    c["images"] = meta_map
                    c["image"] = vmeta
                    self.db.save(project)

                    # non-interactive: 캐릭터 레퍼런스 실패 시 즉시 중단
                    if (not self.cfg.interactive) and vmeta.get("status") != "ok":
                        print(
                            "[4/7] STOP: non-interactive mode requires character/place references. "
                            f"character generation failed: {ok_path.name}"
                        )
                        return project

            print(f"[4/7] characters done in {self._fmt_eta(time.time()-section_t0)}: total={total} skip={skip} ok={gen_ok} err={gen_err} regen={regen}")

            # ✅ 생성 완료 후: 폴더 자동 열기 + 사용자가 눈으로 확인
            if self.cfg.interactive:
                self.paths.characters_dir.mkdir(parents=True, exist_ok=True)
                self._open_dir(self.paths.characters_dir)
                if not self._confirm(
                    "캐릭터 이미지를 확인한 뒤 다음(장소)으로 진행할까요?",
                    f"- dir={self.paths.characters_dir}"
                ):
                    return project
        else:
            print("[4/7] characters: SKIP (already complete)")

        # ------------------------------------------------------------
        # (5/7) places generate (only if work left)
        # ------------------------------------------------------------
        pl_left, pl_total, pl_remain = self._places_work_left(project)
        if pl_left:
            if self.cfg.interactive:
                if not self._confirm(
                    "장소 이미지 생성을 시작할까요?",
                    f"- remain={pl_remain}/{pl_total}\n- dir={self.paths.places_dir}"
                ):
                    return project

            places = [p for p in project.get("places", []) if isinstance(p, dict)]
            p_total = len(places)
            p_done = 0
            p_skip = 0
            p_regen = 0
            p_ok = 0
            p_err = 0
            p_gen_time_sum = 0.0
            p_gen_count = 0
            p_t0 = time.time()

            print(f"[5/7] places: total={p_total}")
            for p in places:
                p_done += 1
                img_meta = p.get("image") if isinstance(p.get("image"), dict) else _default_image_meta()

                pid = str(p.get("id", "place_000"))
                name = str(p.get("name", "unknown"))
                anchors = p.get("visual_anchors", [])
                hints = p.get("hints", [])
                use = anchors if isinstance(anchors, list) and anchors else (hints if isinstance(hints, list) else [])
                safe = _safe_filename(name)

                ok_path = self.paths.places_dir / f"{pid}_{safe}.jpg"
                err_path = self.paths.places_dir / f"{pid}_{safe}_error.jpg"
                _cleanup_stale_error_file(img_meta, ok_path, err_path)

                if img_meta.get("status") == "ok" and ok_path.exists() and (not err_path.exists()):
                    p_skip += 1
                    avg = self._avg_time(p_gen_time_sum, p_gen_count)
                    eta = self._fmt_eta(avg * max(p_total - p_done, 0))
                    print(f"[5/7] places {p_done}/{p_total} (skip={p_skip}, ok={p_ok}, err={p_err}, regen={p_regen}) ETA~{eta}: {ok_path.name}  -> skip")
                    continue

                if img_meta.get("status") == "ok" and not ok_path.exists():
                    p_regen += 1
                    img_meta["status"] = "pending"
                    img_meta["attempts"] = 0
                    img_meta["last_error"] = None
                    img_meta["path"] = None
                    img_meta["policy_rewrite_level"] = 0
                    img_meta["prompt_history"] = []

                avg = self._avg_time(p_gen_time_sum, p_gen_count)
                eta = self._fmt_eta(avg * max(p_total - p_done, 0))
                print(f"[5/7] places {p_done}/{p_total} (skip={p_skip}, ok={p_ok}, err={p_err}, regen={p_regen}) ETA~{eta}: {ok_path.name}  -> gen")

                prompt = build_place_prompt(self.era, self.style, name, use)

                t0 = time.time()
                p["image"] = generate_with_fallback(
                    client=self.img_client,
                    out_ok_path=ok_path,
                    out_error_path=err_path,
                    prompt=prompt,
                    retry=retry,
                    meta=img_meta,
                    aspect_ratio="16:9",
                )
                dt = time.time() - t0
                p_gen_time_sum += dt
                p_gen_count += 1

                if (p["image"] or {}).get("status") == "ok":
                    p_ok += 1
                else:
                    p_err += 1

                self.db.save(project)

                # non-interactive: 장소 레퍼런스 실패 시 즉시 중단
                if (not self.cfg.interactive) and (p["image"] or {}).get("status") != "ok":
                    print(
                        "[5/7] STOP: non-interactive mode requires character/place references. "
                        f"place generation failed: {ok_path.name}"
                    )
                    return project

            print(f"[5/7] places done in {self._fmt_eta(time.time()-p_t0)}: total={p_total} skip={p_skip} ok={p_ok} err={p_err} regen={p_regen}")

            # ✅ 생성 완료 후: 폴더 자동 열기 + 사용자가 눈으로 확인
            if self.cfg.interactive:
                self.paths.places_dir.mkdir(parents=True, exist_ok=True)
                self._open_dir(self.paths.places_dir)
                if not self._confirm(
                    "장소 이미지를 확인한 뒤 다음(클립)으로 진행할까요?",
                    f"- dir={self.paths.places_dir}"
                ):
                    return project
        else:
            print("[5/7] places: SKIP (already complete)")

        if self.cfg.stop_after_place_refs:
            project.setdefault("project", {})
            project["project"]["phase"] = "refs_ready"
            project["project"]["phase_detail"] = "through_place_refs"
            self.db.save(project)
            print("[5.5/7] stop_after_place_refs: stop after character/place reference generation")
            return project

        # non-interactive 모드: character/place 생성 후 규칙 파일이 없으면 clip 단계 전에 중단
        if (not self.cfg.interactive) and (not self._has_story_rule_file_for_resume()):
            print(
                f"[5.5/7] STOP: non-interactive mode paused after character/place generation. "
                f"Please request Codex to create story rule files."
            )
            print(f"{self.story_id} 인물 규칙 파일 생성을 codex에게 요청 해주세요")
            return project

        # ------------------------------------------------------------
        # (6/7) clips generate (only if work left)
        # ------------------------------------------------------------
        cl_left, cl_total, cl_remain = self._clips_work_left(project)
        if cl_left:
            if self.cfg.interactive:
                if not self._confirm(
                    "클립(장면) 이미지 생성을 시작할까요?",
                    f"- remain={cl_remain}/{cl_total}\n- dir={self.paths.clips_dir}"
                ):
                    return project

            # 이하 기존 clips 생성 루프...
            scenes_list = [s for s in project.get("scenes", []) if isinstance(s, dict)]
            s_total = len(scenes_list)
            s_done = 0
            s_skip = 0
            s_regen = 0
            s_ok = 0
            s_err = 0
            s_prompt_err = 0
            s_consecutive_err = 0
            s_gen_time_sum = 0.0
            s_gen_count = 0
            s_t0 = time.time()
            max_consecutive_err = int(os.environ.get("MAX_CONSECUTIVE_CLIP_ERRORS", "10") or "10")

            prev_ctx: List[Dict[str, Any]] = []

            def _shot_hint(scene_id: int) -> str:
                cycle = [
                    "와이드 establishing 샷(공간 전체)",
                    "미디엄 샷(인물 상반신/상황 중심)",
                    "투샷(두 인물 관계 강조)",
                    "오버숄더 샷(대화/심리)",
                    "클로즈업(표정/감정 강조)",
                    "로우앵글(압박/긴장/위엄)",
                    "하이앵글(고독/무력감)",
                    "인서트 디테일(손/소품/발자국/파도 거품 등)",
                ]
                return cycle[(scene_id - 1) % len(cycle)]

            def _time_hint(text: str) -> str:
                t = text or ""
                if "새벽" in t or "어둠이 채 가시지" in t:
                    return "새벽"
                if "한낮" in t or "낮" in t:
                    return "낮"
                if "황혼" in t or "해가 서산" in t or "붉은 기운" in t:
                    return "황혼"
                if "밤" in t or "깊은 밤" in t or "칠흑" in t:
                    return "밤"
                if "폭풍" in t or "폭풍우" in t or "비바람" in t:
                    return "폭풍"
                return "낮(명시 없으면 기본)"

            def _focus_hint(text: str) -> str:
                s2 = (text or "").strip()
                if not s2:
                    return ""
                parts = [x.strip() for x in s2.replace("\n", " ").split(".") if x.strip()]
                if not parts:
                    return s2[:60]
                for p in parts:
                    if "“" in p or "”" in p or "\"" in p:
                        return p[:80]
                verbs = ["응시", "바라", "달려", "안아", "흔들", "울", "결심", "버텨", "웅크", "쥐", "떨", "쓰러",
                         "노를", "포효", "사라", "찾", "무릎", "손을", "뒤돌", "닫", "열"]
                for p in parts:
                    for v in verbs:
                        if v in p:
                            return p[:80]
                return parts[0][:80]

            def _build_llm_scene_prompt(
                sid: int,
                s_obj: Dict[str, Any],
                place_name: Optional[str],
            ) -> str:
                def _strip_direct_speech(text: str) -> str:
                    s = str(text or "")
                    # 따옴표 기반 직접 대사를 제거해 말풍선 유도를 줄인다.
                    s = re.sub(r"[\"“][^\"”\n]{1,220}[\"”]", " ", s)
                    # 대사형 접두(예: 김도령: ...) 제거
                    s = re.sub(r"(?:^|\s)[가-힣A-Za-z]{1,10}\s*[:：]\s*[^.\n]{1,140}", " ", s)
                    s = re.sub(r"\s+", " ", s).strip()
                    return s

                def _continuity_block(chars: List[Dict[str, Any]]) -> str:
                    lines: List[str] = []
                    for ch in chars[:2]:
                        name = str(ch.get("name", "")).strip()
                        if not name:
                            continue
                        variant = str(ch.get("variant", "")).strip()
                        age_stage = str(ch.get("age_stage", "")).strip()
                        age_hint = self._normalize_age_hint(age_stage, str(ch.get("age_hint", "")))

                        va = [str(x).strip() for x in (ch.get("visual_anchors") or []) if isinstance(x, str) and str(x).strip()]
                        wa = [str(x).strip() for x in (ch.get("wardrobe_anchors") or []) if isinstance(x, str) and str(x).strip()]
                        va_line = ", ".join(va[:3]) if va else "대본 기반 외형 유지"
                        wa_line = ", ".join(wa[:3]) if wa else "대본 기반 복식 유지"
                        tag = f"{name}({variant})" if variant else name
                        lines.append(
                            f"- {tag}: 성별={ch.get('gender','불명')}, 연령대={age_stage or '불명'}"
                            + (f", 나이힌트={age_hint}" if age_hint else "")
                            + f", 외형앵커={va_line}, 복식앵커={wa_line}"
                        )
                    if not lines:
                        return ""
                    return "\n".join([
                        "Character continuity lock:",
                        "Keep each character identity consistent across scenes; do not change age/gender/face/hair/outfit core anchors.",
                        "If the same character and variant continue across adjacent scenes, keep the exact same disguise, headwear, silhouette, and outfit color family unless the scene text explicitly signals a change.",
                        *lines,
                    ])

                place_anchors: List[str] = []
                place_ids = s_obj.get("places", []) if isinstance(s_obj.get("places"), list) else []
                if place_ids:
                    pobj = place_map.get(place_ids[0])
                    if isinstance(pobj, dict):
                        va = pobj.get("visual_anchors", [])
                        if isinstance(va, list):
                            place_anchors = [str(x) for x in va if isinstance(x, str)]

                char_objs: List[Dict[str, Any]] = []
                char_ids = s_obj.get("characters", []) if isinstance(s_obj.get("characters"), list) else []
                scene_text_raw = str(s_obj.get("text", ""))
                scene_text = _strip_direct_speech(scene_text_raw) or scene_text_raw
                selected_char_ids = self._select_scene_character_ids(scene_text, char_ids, char_map, limit=2)

                inst_map: Dict[str, str] = {}
                ci = s_obj.get("character_instances", [])
                if isinstance(ci, list):
                    for it in ci:
                        if isinstance(it, dict):
                            cid2 = it.get("char_id")
                            var = it.get("variant") or ""
                            if isinstance(cid2, str):
                                inst_map[cid2] = str(var)

                for cid2 in selected_char_ids:
                    cobj = char_map.get(cid2)
                    if not isinstance(cobj, dict):
                        continue

                    variant = inst_map.get(cid2, "")  # 이 장면에서의 변형(예: 아동/청년 등)
                    age_stage2 = (variant or cobj.get("age_stage") or "불명")
                    age_hint2 = self._normalize_age_hint(age_stage2, str(cobj.get("age_hint") or ""))
                    visual_anchors2 = self._filter_anchors_by_stage(
                        self._clean_str_list(cobj.get("visual_anchors") or []),
                        age_stage2,
                    )
                    visual_anchors2 = self._augment_anchors_with_variant(
                        visual_anchors2,
                        variant,
                    )
                    wardrobe_anchors2 = self._filter_anchors_by_stage(
                        self._clean_str_list(cobj.get("wardrobe_anchors") or []),
                        age_stage2,
                    )
                    wardrobe_anchors2 = self._filter_anchors_by_variant(
                        wardrobe_anchors2,
                        variant,
                    )
                    wardrobe_anchors2 = self._augment_anchors_with_variant(
                        wardrobe_anchors2,
                        variant,
                    )

                    char_objs.append({
                        "name": cobj.get("name", ""),
                        "species": cobj.get("species", "인간") or "인간",
                        "variant": variant,
                        "gender": cobj.get("gender", "") or "불명",
                        "age_stage": age_stage2,
                        "age_hint": age_hint2,
                        "social_class": cobj.get("social_class", "불명") or "불명",
                        "wealth_level": cobj.get("wealth_level", "불명") or "불명",
                        "context": cobj.get("context", "민간") or "민간",
                        "court_role": cobj.get("court_role", "") or "",
                        "wardrobe_tier": cobj.get("wardrobe_tier", "T2") or "T2",
                        "wardrobe_anchors": wardrobe_anchors2,
                        "visual_anchors": visual_anchors2,
                    })

                shot = _shot_hint(sid)
                t_hint = _time_hint(scene_text)
                focus = _focus_hint(scene_text)

                llm_res = self._call_with_rate_limit_retry(
                    lambda: self.scene_prompt_llm.build(
                        era_profile=self.cfg.era_profile,
                        era_prefix=self.era.prefix,
                        style_profile="k_webtoon_clip",
                        scene_id=sid,
                        scene_text=scene_text,
                        place_name=place_name,
                        place_anchors=place_anchors,
                        characters=char_objs,
                        shot_hint=shot,
                        focus_hint=focus,
                        time_hint=t_hint,
                        prev_summaries=prev_ctx[-2:],
                    ),
                    label=f"[6/7] clip {sid:03d} scene prompt",
                )

                prompt = str(llm_res.get("prompt") or "").strip()
                if not prompt:
                    raise RuntimeError("empty prompt")

                continuity = _continuity_block(char_objs)
                if continuity:
                    prompt = f"{prompt}\n\n{continuity}"

                summary = llm_res.get("summary") if isinstance(llm_res, dict) else None
                if isinstance(summary, dict):
                    prev_ctx.append({
                        "scene_id": sid,
                        "shot": str(summary.get("shot", "")).strip(),
                        "focus": str(summary.get("focus", "")).strip(),
                        "time": str(summary.get("time", "")).strip(),
                        "place": str(summary.get("place", "")).strip() or (place_name or ""),
                    })
                else:
                    prev_ctx.append({
                        "scene_id": sid,
                        "shot": shot,
                        "focus": focus,
                        "time": t_hint,
                        "place": place_name or "",
                    })

                if len(prev_ctx) > 2:
                    del prev_ctx[:-2]

                return prompt

            print(f"[6/7] clips: total={s_total}")

            def _normalize_problematic_clip_terms(prompt_text: str) -> str:
                ptxt = str(prompt_text or "").strip()
                if not ptxt:
                    return ptxt
                # "hut" 계열 표현이 실내 장작불/모닥불로 과도 해석되는 경향을 줄인다.
                replacements = [
                    ("dark hut", "dim Joseon room with ondol floor, lit by an oil lamp"),
                    ("rustic hut", "small Joseon room with ondol floor and paper sliding doors"),
                    ("humble hut", "modest Joseon room with ondol floor"),
                    ("forest hut", "rural Joseon dwelling with ondol-heated room"),
                    ("small hut", "small Joseon room with ondol floor"),
                    ("secluded hut", "secluded Joseon room with ondol floor"),
                    ("inside the hut", "inside a Joseon room with ondol floor and oil-lamp lighting"),
                    ("Inside the hut", "Inside a Joseon room with ondol floor and oil-lamp lighting"),
                    ("hut door", "wooden sliding door of a Joseon room"),
                    ("hut", "Joseon room with ondol floor"),
                ]
                out = ptxt
                for src, dst in replacements:
                    out = out.replace(src, dst)
                return out

            def _sanitize_clip_prompt_text(prompt_text: str) -> str:
                ptxt = str(prompt_text or "").strip()
                if not ptxt:
                    return ptxt
                # Remove direct quoted speech to reduce speech-bubble/text rendering.
                ptxt = re.sub(r"[\"“][^\"”\n]{1,260}[\"”]", " ", ptxt)
                # Remove "Name: ..." style dialogue fragments (avoid stripping lowercase scene phrases like "entrance:")
                ptxt = re.sub(
                    r"(?:^|[\n\r]\s*|\s)(?:[A-Z][a-z]{1,15}|[가-힣]{2,8})\s*[:：]\s*[^.\n]{1,180}",
                    " ",
                    ptxt,
                )
                # Remove explicit speaking verbs followed by quoted payload patterns.
                ptxt = re.sub(r"\b(?:saying|says|said|shouting|shouts|yelling|yells)\b[^.\n]{0,120}", " ", ptxt, flags=re.IGNORECASE)
                ptxt = re.sub(r"\s+", " ", ptxt).strip()
                return ptxt

            def _character_role_hint(names: List[str]) -> str:
                joined = " ".join([n or "" for n in names]).lower()
                if any(k in joined for k in ("의원", "physician", "doctor")):
                    return "village physician"
                if any(k in joined for k in ("약초꾼", "herbalist")):
                    return "mountain herbalist"
                if any(k in joined for k in ("주모", "innkeeper", "tavern")):
                    return "tavern innkeeper"
                if any(k in joined for k in ("향리", "clerk")):
                    return "local clerk"
                if any(k in joined for k in ("내금위", "guard")):
                    return "former palace guard"
                if any(k in joined for k in ("손자", "소년", "boy")):
                    return "young boy"
                if any(k in joined for k in ("소녀", "girl")):
                    return "young girl"
                if any(k in joined for k in ("할머니", "노파", "elderly")):
                    return "elderly woman"
                if any(k in joined for k in ("아이", "child")):
                    return "child"
                return ""

            def _character_descriptor(cobj: Dict[str, Any]) -> str:
                name = str(cobj.get("name") or "")
                aliases = cobj.get("aliases") if isinstance(cobj.get("aliases"), list) else []
                names = [name] + [str(a) for a in aliases if a]
                role_hint = _character_role_hint(names)
                gender = str(cobj.get("gender") or "").lower()
                age_stage = str(cobj.get("age_stage") or "").lower()

                if role_hint:
                    return f"the {role_hint} in Joseon-era hanbok"

                age_map = {
                    "아동": "young",
                    "청년": "young",
                    "중년": "middle-aged",
                    "노년": "elderly",
                }
                gender_map = {"남": "man", "여": "woman"}
                age = age_map.get(age_stage, "")
                g = gender_map.get(gender, "")
                if age and g:
                    return f"the {age} Korean {g} in Joseon-era hanbok"
                if g:
                    return f"the Korean {g} in Joseon-era hanbok"
                return "the Joseon-era villager in hanbok"

            def _strip_character_names(prompt_text: str) -> str:
                ptxt = str(prompt_text or "")
                if not ptxt:
                    return ptxt
                generic_aliases = {
                    "child", "boy", "girl", "man", "woman", "doctor", "physician",
                    "아이", "소년", "소녀", "남자", "여자", "의원",
                }
                replacements: List[Tuple[str, str, bool]] = []
                for cobj in char_map.values():
                    if not isinstance(cobj, dict):
                        continue
                    desc = _character_descriptor(cobj)
                    name = str(cobj.get("name") or "").strip()
                    aliases = cobj.get("aliases") if isinstance(cobj.get("aliases"), list) else []
                    cand = [name] + [str(a) for a in aliases if a]
                    for n in cand:
                        if not n or n in generic_aliases:
                            continue
                        is_ascii = all(ord(ch) < 128 for ch in n)
                        replacements.append((n, desc, is_ascii))
                # Replace longer names first to avoid partial overlaps.
                replacements.sort(key=lambda x: len(x[0]), reverse=True)
                for n, desc, is_ascii in replacements:
                    if is_ascii:
                        ptxt = re.sub(rf"\\b{re.escape(n)}\\b", desc, ptxt, flags=re.IGNORECASE)
                    else:
                        ptxt = ptxt.replace(n, desc)
                ptxt = re.sub(r"\s+", " ", ptxt).strip()
                return ptxt

            def _strip_scene_romanized_names(prompt_text: str, s_obj: Dict[str, Any]) -> str:
                ptxt = str(prompt_text or "")
                if not ptxt:
                    return ptxt
                # Build descriptors for scene characters in order.
                descs: List[str] = []
                char_ids = s_obj.get("characters", []) if isinstance(s_obj.get("characters"), list) else []
                for cid in char_ids:
                    cobj = char_map.get(str(cid))
                    if isinstance(cobj, dict):
                        descs.append(_character_descriptor(cobj))
                if not descs:
                    return ptxt

                # Allow common scene/opening words and place/style terms.
                allow = {
                    "Medium", "Wide", "Close", "Long", "Establishing",
                    "Joseon", "Korea", "Jirisan", "Hanyang", "Pyeongyang",
                    "Hanok", "Hanbok", "Yangban", "Gisaeng",
                }
                idx = 0
                pat = re.compile(r"(^|[:.?!]\\s+)([A-Z][a-z]{2,})\\b")

                def _repl(m: "re.Match") -> str:
                    nonlocal idx
                    prefix = m.group(1)
                    word = m.group(2)
                    if word in allow:
                        return m.group(0)
                    desc = descs[idx] if idx < len(descs) else "the Joseon-era villager in hanbok"
                    idx += 1
                    return f"{prefix}{desc}"

                ptxt = pat.sub(_repl, ptxt)
                ptxt = re.sub(r"\s+", " ", ptxt).strip()
                return ptxt

            def _character_ab_descriptor(cobj: Dict[str, Any], variant: str) -> str:
                gender = str(cobj.get("gender") or "")
                age_stage = str(variant or cobj.get("age_stage") or "")
                g = "woman" if gender == "여" else ("man" if gender == "남" else "person")
                age = "young" if age_stage in ("아동", "청년") else ("middle-aged" if age_stage == "중년" else ("elderly" if age_stage == "노년" else ""))
                if age:
                    return f"{age} Korean {g} in Joseon-era hanbok"
                return f"Korean {g} in Joseon-era hanbok"

            def _build_scene_identity_lock(prompt_text: str, s_obj: Dict[str, Any]) -> str:
                ptxt = str(prompt_text or "").strip()
                if not ptxt:
                    return ptxt
                if re.search(r"\bcharacter\s*a\b", ptxt, flags=re.IGNORECASE) and re.search(r"\bcharacter\s*b\b", ptxt, flags=re.IGNORECASE):
                    return ptxt

                role_term_re = re.compile(
                    r"(adopted daughter|true daughter|biological daughter|foster daughter|real daughter|adoptive daughter|"
                    r"adopted son|true son|biological son|foster son|real son|adoptive son|양녀|친딸|양자|친아들)",
                    re.IGNORECASE,
                )
                pair_lock_re = re.compile(
                    r"(two women only|two men only|two people only|no identity swap|no swap|identity swap)",
                    re.IGNORECASE,
                )
                if not (role_term_re.search(ptxt) or pair_lock_re.search(ptxt)):
                    return ptxt

                char_ids = s_obj.get("characters", []) if isinstance(s_obj.get("characters"), list) else []
                selected = self._select_scene_character_ids(
                    str(s_obj.get("text", "")),
                    char_ids,
                    char_map,
                    limit=2,
                )
                if len(selected) < 2:
                    return ptxt

                inst_map: Dict[str, str] = {}
                ci_rows = s_obj.get("character_instances", [])
                if isinstance(ci_rows, list):
                    for row in ci_rows:
                        if isinstance(row, dict) and isinstance(row.get("char_id"), str):
                            inst_map[str(row.get("char_id"))] = str(row.get("variant") or "")

                lines: List[str] = []
                for idx, cid in enumerate(selected[:2]):
                    cobj = char_map.get(str(cid))
                    if not isinstance(cobj, dict):
                        continue
                    variant = inst_map.get(str(cid), "")
                    age_stage = variant or str(cobj.get("age_stage") or "")
                    visual = self._filter_anchors_by_stage(
                        self._clean_str_list(cobj.get("visual_anchors") or []),
                        age_stage,
                    )
                    visual = self._augment_anchors_with_variant(visual, variant)
                    wardrobe = self._filter_anchors_by_stage(
                        self._clean_str_list(cobj.get("wardrobe_anchors") or []),
                        age_stage,
                    )
                    wardrobe = self._filter_anchors_by_variant(wardrobe, variant)
                    wardrobe = self._augment_anchors_with_variant(wardrobe, variant)

                    visual_txt = ", ".join(visual[:2]) if visual else "keep distinct facial structure"
                    wardrobe_txt = ", ".join(wardrobe[:2]) if wardrobe else "keep distinct outfit silhouette"
                    tag = "A" if idx == 0 else "B"
                    desc = _character_ab_descriptor(cobj, variant)
                    lines.append(
                        f"Character {tag}: {desc}; visual anchors={visual_txt}; wardrobe anchors={wardrobe_txt}."
                    )

                if len(lines) < 2:
                    return ptxt

                identity_block = (
                    "Identity lock: Keep exactly one Character A and exactly one Character B in frame. "
                    "Never swap Character A/B face, body type, or outfit."
                )
                return f"{ptxt}\n\n{identity_block}\n" + "\n".join(lines)

            def _is_dns_error(msg: str) -> bool:
                s = (msg or "").lower()
                return any(x in s for x in (
                    "nodename nor servname provided",
                    "name or service not known",
                    "temporary failure in name resolution",
                    "getaddrinfo failed",
                ))

            def _apply_clip_safety_constraints(prompt_text: str, s_obj: Dict[str, Any]) -> str:
                ptxt = _sanitize_clip_prompt_text(_normalize_problematic_clip_terms(prompt_text))
                ptxt = _strip_character_names(ptxt)
                ptxt = _strip_scene_romanized_names(ptxt, s_obj)
                ptxt = _build_scene_identity_lock(ptxt, s_obj)
                if not ptxt:
                    return ptxt
                if "[Safety constraints]" in ptxt:
                    return ptxt
                indoor_tail = ""
                ltxt = ptxt.lower()
                if ("ondol floor" in ltxt) or ("joseon room" in ltxt):
                    indoor_tail = (
                        "\n- Keep this as a Joseon indoor living room (ondol-style), not a barn/shed interior.\n"
                        "- No exposed-barn rafters, no central campfire, no burning firewood pile inside the room."
                    )
                safety_tail = (
                    "[Safety constraints]\n"
                    "- Keep anatomy coherent: one head, one torso, two arms, two hands, two legs per person.\n"
                    "- No extra limbs, fused fingers, broken joints, or duplicated body parts.\n"
                    "- Keep physical boundaries clear: no body-object intersection or merged geometry.\n"
                    "- Humans must remain outside wardrobes/drawers/cabinets/chests; only objects can be inside."
                    "\n- Keep a stylized 2D Korean manhwa/webtoon look; do not render photorealistic, DSLR, or live-action style."
                    "\n- No visible text, letters, subtitles, captions, narration boxes, speech bubbles, or quote marks in the image."
                    "\n- Convey dialogue only through facial expression, gaze, posture, and hand gesture."
                    "\n- Keep character faces Korean/East-Asian in proportion and styling; avoid Western facial morphology."
                    f"{indoor_tail}"
                )
                return f"{ptxt}\n\n{safety_tail}"

            def _scene_reference_image_paths(s_obj: Dict[str, Any]) -> List[str]:
                char_refs: List[str] = []
                char_ids2 = s_obj.get("characters", []) if isinstance(s_obj.get("characters"), list) else []
                selected = self._select_scene_character_ids(
                    str(s_obj.get("text", "")),
                    char_ids2,
                    char_map,
                    limit=3,
                )
                ci2 = s_obj.get("character_instances", [])
                inst_map2: Dict[str, str] = {}
                if isinstance(ci2, list):
                    for it in ci2:
                        if isinstance(it, dict) and isinstance(it.get("char_id"), str):
                            inst_map2[str(it["char_id"])] = str(it.get("variant") or "")

                for cid3 in selected:
                    cobj2 = char_map.get(cid3)
                    if not isinstance(cobj2, dict):
                        continue
                    variant2 = inst_map2.get(cid3, "")
                    img_path = ""
                    images = cobj2.get("images")
                    if variant2 and isinstance(images, dict):
                        vmeta = images.get(variant2)
                        if isinstance(vmeta, dict):
                            img_path = str(vmeta.get("path") or "")
                    if not img_path:
                        img_meta2 = cobj2.get("image")
                        if isinstance(img_meta2, dict):
                            img_path = str(img_meta2.get("path") or "")
                    if img_path and Path(img_path).exists():
                        char_refs.append(img_path)

                place_ref: Optional[str] = None
                place_ids2 = s_obj.get("places", []) if isinstance(s_obj.get("places"), list) else []
                if place_ids2:
                    p_obj = place_map.get(str(place_ids2[0]))
                    if isinstance(p_obj, dict):
                        p_img = p_obj.get("image")
                        if isinstance(p_img, dict):
                            p_path = str(p_img.get("path") or "")
                            if p_path and Path(p_path).exists():
                                place_ref = p_path

                refs: List[str] = []
                for p in char_refs[:3]:
                    if p not in refs:
                        refs.append(p)
                if place_ref and place_ref not in refs:
                    refs.append(place_ref)

                return refs[:4]

            for s in scenes_list:
                s_done += 1
                img_meta = s.get("image") if isinstance(s.get("image"), dict) else _default_image_meta()

                sid = int(s.get("id", 0))
                ok_path = self.paths.clips_dir / f"{sid:03d}.jpg"
                err_path = self.paths.clips_dir / f"{sid:03d}_error.jpg"
                _cleanup_stale_error_file(img_meta, ok_path, err_path)

                if img_meta.get("status") == "ok" and ok_path.exists() and (not err_path.exists()):
                    s_skip += 1
                    avg = self._avg_time(s_gen_time_sum, s_gen_count)
                    eta = self._fmt_eta(avg * max(s_total - s_done, 0))
                    elapsed = self._fmt_eta(time.time() - s_t0)
                    print(f"[6/7] clips {s_done}/{s_total} (skip={s_skip}, ok={s_ok}, err={s_err}, regen={s_regen}, prompt_err={s_prompt_err}) elapsed~{elapsed} ETA~{eta}: {ok_path.name}  -> skip")
                    continue

                if img_meta.get("status") == "ok" and not ok_path.exists():
                    s_regen += 1
                    img_meta["status"] = "pending"
                    img_meta["attempts"] = 0
                    img_meta["last_error"] = None
                    img_meta["path"] = None
                    img_meta["policy_rewrite_level"] = 0
                    img_meta["prompt_history"] = []

                avg = self._avg_time(s_gen_time_sum, s_gen_count)
                eta = self._fmt_eta(avg * max(s_total - s_done, 0))
                elapsed = self._fmt_eta(time.time() - s_t0)
                print(f"[6/7] clips {s_done}/{s_total} (skip={s_skip}, ok={s_ok}, err={s_err}, regen={s_regen}, prompt_err={s_prompt_err}) elapsed~{elapsed} ETA~{eta}: {ok_path.name}  -> gen")

                char_names = resolve_char_names(s.get("characters", []) if isinstance(s.get("characters"), list) else [])
                place_name = resolve_place_name(s.get("places", []) if isinstance(s.get("places"), list) else [])

                had_err_file = err_path.exists()
                last_err = str(img_meta.get("last_error") or "")
                policy_suspect = self._is_policy_error(last_err)

                # prompt selection
                prompt: Optional[str] = None
                prebuilt = str(s.get("llm_clip_prompt") or "").strip()
                status_now = str(img_meta.get("status") or "").strip()

                # When a scene is reset to pending for regeneration, prefer the
                # current structure-stage prompt over stale prompt_used metadata.
                # This lets manual prompt repairs in project.json actually take effect.
                if status_now != "ok" and prebuilt and not (had_err_file and policy_suspect):
                    prompt = prebuilt
                    ph = img_meta.get("prompt_history")
                    if not isinstance(ph, list):
                        ph = []
                    ph.append({"phase": "llm_extract_scene_prompt", "source": "structure_stage_pending_override"})
                    img_meta["prompt_history"] = ph

                if prompt is None:
                    if had_err_file and policy_suspect:
                        prompt = None
                    else:
                        pu = img_meta.get("prompt_used")
                        if isinstance(pu, str) and pu.strip():
                            prompt = pu.strip()

                if prompt is None and prebuilt:
                    prompt = prebuilt
                    ph = img_meta.get("prompt_history")
                    if not isinstance(ph, list):
                        ph = []
                    ph.append({"phase": "llm_extract_scene_prompt", "source": "structure_stage"})
                    img_meta["prompt_history"] = ph

                if prompt is None:
                    try:
                        prompt = _build_llm_scene_prompt(sid, s, place_name)
                    except Exception as e:
                        s_prompt_err += 1
                        err_msg = f"LLM_SCENE_PROMPT_ERROR: {e}"
                        img_meta["status"] = "error"
                        img_meta["last_error"] = err_msg
                        img_meta["attempts"] = int(img_meta.get("attempts") or 0) + 1

                        ph = img_meta.get("prompt_history")
                        if not isinstance(ph, list):
                            ph = []
                        ph.append({"phase": "llm_scene_prompt", "error": err_msg})
                        img_meta["prompt_history"] = ph

                        try:
                            err_path.parent.mkdir(parents=True, exist_ok=True)
                            if not err_path.exists():
                                err_path.write_bytes(b"")
                        except Exception:
                            pass

                        s["image"] = img_meta
                        self.db.save(project)
                        print(f"  - prompt: FAIL -> {err_path.name} ({err_msg})")
                        continue

                prompt = str(prompt).strip()
                if not prompt:
                    s_prompt_err += 1
                    err_msg = "LLM_SCENE_PROMPT_ERROR: empty prompt"
                    img_meta["status"] = "error"
                    img_meta["last_error"] = err_msg
                    img_meta["attempts"] = int(img_meta.get("attempts") or 0) + 1
                    s["image"] = img_meta
                    self.db.save(project)
                    print(f"  - prompt: FAIL -> {err_path.name} ({err_msg})")
                    continue

                prompt = _apply_clip_safety_constraints(prompt, s)
                img_meta["prompt_original"] = img_meta.get("prompt_original") or prompt[:500]
                img_meta["prompt_used"] = prompt
                ref_paths = _scene_reference_image_paths(s)

                t0 = time.time()
                s["image"] = generate_with_fallback(
                    client=self.img_client,
                    out_ok_path=ok_path,
                    out_error_path=err_path,
                    prompt=prompt,
                    retry=retry,
                    meta=img_meta,
                    aspect_ratio="16:9",
                    reference_image_paths=ref_paths,
                )
                dt = time.time() - t0
                s_gen_time_sum += dt
                s_gen_count += 1

                meta_after = s.get("image") if isinstance(s.get("image"), dict) else img_meta
                status = str(meta_after.get("status") or "")
                last_err2 = str(meta_after.get("last_error") or "")

                if status == "ok":
                    s_ok += 1
                    s_consecutive_err = 0
                else:
                    s_err += 1
                    s_consecutive_err += 1
                    if s_consecutive_err >= max_consecutive_err:
                        print(f"[6/7] STOP: consecutive clip errors reached {s_consecutive_err} (threshold={max_consecutive_err})")
                        s["image"] = meta_after
                        self.db.save(project)
                        break

                # policy rewrite flow (interactive)
                if status != "ok" and self._is_policy_error(last_err2):
                    if self._confirm(
                        "정책 위반으로 막힌 것 같습니다. 우회 프롬프트를 LLM으로 재작성 후 재시도할까요?",
                        f"- scene={sid}\n- place={place_name}\n- chars={', '.join(char_names)}\n- error={last_err2}\n- file={err_path.name}"
                    ):
                        try:
                            base_prompt = str(meta_after.get("prompt_used") or prompt).strip()
                            rw = self.prompt_rewriter.rewrite(base_prompt, last_err2)
                            new_prompt = str(rw.get("prompt") or "").strip()
                            if not new_prompt:
                                raise RuntimeError("empty rewritten prompt")

                            ph = meta_after.get("prompt_history")
                            if not isinstance(ph, list):
                                ph = []
                            ph.append({
                                "phase": "policy_rewrite_llm",
                                "error": last_err2,
                                "prompt_before_head": base_prompt[:200],
                                "prompt_after_head": new_prompt[:200],
                            })
                            meta_after["prompt_history"] = ph

                            meta_after["status"] = "pending"
                            meta_after["last_error"] = None
                            meta_after["prompt_used"] = new_prompt

                            print("  - policy rewrite: retry with LLM rewritten prompt")

                            t1 = time.time()
                            s["image"] = generate_with_fallback(
                                client=self.img_client,
                                out_ok_path=ok_path,
                                out_error_path=err_path,
                                prompt=new_prompt,
                                retry=retry,
                                meta=meta_after,
                                aspect_ratio="16:9",
                                reference_image_paths=ref_paths,
                            )
                            dt2 = time.time() - t1
                            s_gen_time_sum += dt2
                            s_gen_count += 1

                            print(f"  - policy retry result: {(s['image'] or {}).get('status')}")
                        except Exception as e:
                            msg = f"POLICY_REWRITE_FLOW_ERROR: {e}"
                            meta_after["last_error"] = msg
                            ph = meta_after.get("prompt_history")
                            if not isinstance(ph, list):
                                ph = []
                            ph.append({"phase": "policy_rewrite_llm", "error": msg})
                            meta_after["prompt_history"] = ph
                            s["image"] = meta_after
                            print(f"  - policy rewrite: FAIL ({msg})")

                # non-policy + had old error file + still failing => ask regenerate prompt
                meta_after2 = s.get("image") if isinstance(s.get("image"), dict) else meta_after
                status2 = str(meta_after2.get("status") or "")
                last_err3 = str(meta_after2.get("last_error") or "")

                if (
                    status2 != "ok"
                    and (not self._is_policy_error(last_err3))
                    and (not _is_dns_error(last_err3))
                    and had_err_file
                    and err_path.exists()
                ):
                    if self._confirm(
                        "이미지 생성이 계속 실패합니다. LLM으로 clip 프롬프트를 재생성해서 다시 시도할까요?",
                        f"- scene={sid}\n- place={place_name}\n- chars={', '.join(char_names)}\n- error={last_err3}\n- file={err_path.name}"
                    ):
                        try:
                            new_prompt2 = _build_llm_scene_prompt(sid, s, place_name)

                            ph = meta_after2.get("prompt_history")
                            if not isinstance(ph, list):
                                ph = []
                            ph.append({
                                "phase": "regen_prompt_llm",
                                "error": last_err3,
                                "prompt_before_head": (str(meta_after2.get("prompt_used") or "")[:200]),
                                "prompt_after_head": new_prompt2[:200],
                            })
                            meta_after2["prompt_history"] = ph

                            meta_after2["status"] = "pending"
                            meta_after2["last_error"] = None
                            meta_after2["prompt_used"] = new_prompt2

                            print("  - regen prompt: retry with new LLM prompt")

                            t2 = time.time()
                            s["image"] = generate_with_fallback(
                                client=self.img_client,
                                out_ok_path=ok_path,
                                out_error_path=err_path,
                                prompt=new_prompt2,
                                retry=retry,
                                meta=meta_after2,
                                aspect_ratio="16:9",
                                reference_image_paths=ref_paths,
                            )
                            dt3 = time.time() - t2
                            s_gen_time_sum += dt3
                            s_gen_count += 1

                            print(f"  - regen retry result: {(s['image'] or {}).get('status')}")
                        except Exception as e:
                            msg = f"REGEN_PROMPT_FLOW_ERROR: {e}"
                            meta_after2["last_error"] = msg
                            ph = meta_after2.get("prompt_history")
                            if not isinstance(ph, list):
                                ph = []
                            ph.append({"phase": "regen_prompt_llm", "error": msg})
                            meta_after2["prompt_history"] = ph
                            s["image"] = meta_after2
                            print(f"  - regen prompt: FAIL ({msg})")

                self.db.save(project)

            print(
                f"[6/7] clips done in {self._fmt_eta(time.time()-s_t0)}: total={s_total} "
                f"skip={s_skip} ok={s_ok} err={s_err} regen={s_regen} prompt_err={s_prompt_err}"
            )
        else:
            print("[6/7] clips: SKIP (already complete)")

        if self.cfg.stop_after_clips:
            project.setdefault("project", {})
            project["project"]["phase"] = "clips_ready"
            project["project"]["phase_detail"] = "through_clips"
            self.db.save(project)
            print("[6.5/7] stop_after_clips: stop after clip generation before export")
            return project

        # ------------------------------------------------------------
        # (7/7) exporter
        # ------------------------------------------------------------
        if self.exporter is not None:
            cl_left2, cl_total2, cl_remain2 = self._clips_work_left(project)
            if cl_left2:
                print(
                    "[7/7] export: SKIP "
                    f"(clips not complete: remain={cl_remain2}/{cl_total2}, "
                    "status!=ok or missing/error file exists)"
                )
                return project

            # export도 “할 때만” confirm(기존과 동일)
            if self._confirm("export를 진행할까요?", f"- out: {self.paths.out_dir}"):
                print("[7/7] export: start")
                req = VrewExportRequest(
                    project=project,
                    out_dir=str(self.paths.out_dir),
                    clip_text_max_chars=max(1, int(self.cfg.vrew_clip_max_chars)),
                )
                self.exporter.export(req)
                print("[7/7] export: done")

        return project        
