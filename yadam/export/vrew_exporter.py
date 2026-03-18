# yadam/export/vrew_exporter.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4
import re
import zipfile
import json
import os
from copy import deepcopy


@dataclass(frozen=True)
class VrewExportRequest:
    project: Dict[str, Any]
    out_dir: str
    clip_text_max_chars: int = 30
    clip_text_soft_max_chars: int = 45
    caption_line_max_chars: int = 22
    caption_max_lines: int = 2


class VrewExporter(ABC):
    @abstractmethod
    def export(self, req: VrewExportRequest) -> None:
        raise NotImplementedError


class VrewPayloadExporter(VrewExporter):
    """
    .vrew 파일 포맷이 공식적으로 확인되기 전까지는
    '브루에 가져오기 쉽게' 장면/이미지 경로를 묶은 payload를 내보낸다.
    """
    def export(self, req: VrewExportRequest) -> None:
        out = Path(req.out_dir) / "vrew_payload.json"
        out.write_text(json.dumps(req.project, ensure_ascii=False, indent=2), encoding="utf-8")


class VrewFileExporter(VrewExporter):
    """
    project.json + clips 이미지를 기반으로 .vrew(Zip) 파일을 직접 생성한다.
    - scene.text를 자막 원문으로 사용
    - TTS 음성은 더미 speaker("unknown") 기준 메타만 기록(실제 mp3는 포함하지 않음)
    """

    def export(self, req: VrewExportRequest) -> None:
        scenes = self._collect_scenes(req.project)
        clip_text_max_chars = max(1, int(req.clip_text_max_chars))
        clip_text_soft_max_chars = max(clip_text_max_chars, int(req.clip_text_soft_max_chars))
        caption_line_max_chars = max(8, int(req.caption_line_max_chars))
        caption_max_lines = max(1, int(req.caption_max_lines))
        input_script = str(req.project.get("project", {}).get("input_script_path") or "").strip()
        story_name = Path(input_script).stem if input_script else "story"
        preset = self._resolve_export_preset(Path(req.out_dir), story_name)

        now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
        project_id = str(uuid4())
        speaker_info = dict(preset["speaker"])
        speaker_id = str(speaker_info.get("speakerId") or speaker_info.get("name") or "vos-female28")
        speaker_info["speakerId"] = speaker_id
        speaker = {
            "provider": str(speaker_info.get("provider") or "kt"),
            "gender": str(speaker_info.get("gender") or "female"),
            "lang": str(speaker_info.get("lang") or "ko-KR"),
            "name": str(speaker_info.get("name") or speaker_id),
            "speakerId": speaker_id,
            "age": str(speaker_info.get("age") or "middle"),
        }
        if isinstance(speaker_info.get("emotions"), list):
            speaker["emotions"] = list(speaker_info["emotions"])
        if isinstance(speaker_info.get("tags"), list):
            speaker["tags"] = list(speaker_info["tags"])
        voice_volume = float(preset.get("volume", 0))
        voice_speed = float(preset.get("speed", 0))
        voice_pitch = float(preset.get("pitch", -1))
        voice_emotion = str(preset.get("emotion") or "neutral")

        files: List[Dict[str, Any]] = []
        assets: Dict[str, Any] = {}
        tts_clip_infos: Dict[str, Any] = {}
        clips: List[Dict[str, Any]] = []
        zip_media: List[Tuple[str, bytes]] = []

        for zindex, scene in enumerate(scenes):
            sid = int(scene.get("id", 0))
            text = str(scene.get("text") or "").strip()
            text_chunks = self._split_for_clips(
                text,
                clip_text_max_chars,
                clip_text_soft_max_chars,
                caption_line_max_chars,
                caption_max_lines,
            )
            image_path = Path(str((scene.get("image") or {}).get("path") or "")).resolve()

            image_media_id = str(uuid4())
            image_arcname = f"media/{image_media_id}.jpeg"
            image_bytes = image_path.read_bytes()
            zip_media.append((image_arcname, image_bytes))
            files.append({
                "version": 1,
                "mediaId": image_media_id,
                "sourceOrigin": "USER",
                "fileSize": len(image_bytes),
                "name": image_arcname,
                "type": "Image",
                "isTransparent": False,
                "fileLocation": "IN_MEMORY",
            })

            image_asset_id = str(uuid4())
            assets[image_asset_id] = {
                "mediaId": image_media_id,
                "type": "image",
                "importType": "image",
                "isDeleted": False,
                "softDelete": False,
                "originalWidthHeightRatio": 16.0 / 9.0,
                "width": 1,
                "height": 1.0158730158730158,
                "xPos": 0,
                "yPos": -0.007936507936507908,
                "rotation": 0,
                "zIndex": zindex,
                "customAttributes": [],
                "stats": {
                    "fillType": "cut",
                    "fillMenu": "floating",
                    "rearrangeCount": 0,
                },
            }

            for chunk_idx, chunk_text in enumerate(text_chunks, start=1):
                audio_media_id = str(uuid4())
                audio_name = self._audio_name_from_text(chunk_text, sid, chunk_idx)
                tts_text = self._normalize_tts_text(chunk_text)
                caption_text = self._balance_caption_lines(
                    chunk_text,
                    line_max_chars=caption_line_max_chars,
                    max_lines=caption_max_lines,
                )
                if not self._should_export_tts_chunk(chunk_text, tts_text):
                    continue
                words, duration = self._build_words(tts_text, audio_media_id)
                files.append({
                    "version": 1,
                    "mediaId": audio_media_id,
                    "sourceOrigin": "VREW_RESOURCE",
                    "fileSize": max(1, int(duration * 16000)),
                    "name": f"media/{audio_name}.mp3",
                    "type": "AVMedia",
                    "videoAudioMetaInfo": {
                        "duration": duration,
                        "audioInfo": {"sampleRate": 24000, "codec": "mp3"},
                    },
                    "sourceFileType": "TTS",
                    "fileLocation": "IN_MEMORY",
                })
                tts_info = {
                    "text": {
                        "raw": tts_text,
                        "processed": tts_text,
                        "textAspectLang": speaker["lang"],
                    },
                    "speaker": dict(speaker),
                    "duration": duration,
                    "volume": voice_volume,
                    "speed": voice_speed,
                    "pitch": voice_pitch,
                    "version": "v1",
                }
                if voice_emotion:
                    tts_info["emotion"] = voice_emotion
                tts_clip_infos[audio_media_id] = tts_info

                clips.append({
                    "words": words,
                    "captionMode": "MANUAL",
                    "captions": [
                        {"text": [{"insert": caption_text + "\n"}]},
                        {"text": [{"insert": "\n"}]},
                    ],
                    "assetIds": [image_asset_id],
                    "dirty": {"blankDeleted": False, "caption": False, "video": False},
                    "translationModified": {"result": False, "source": False},
                    "id": str(uuid4()),
                    "audioIds": [],
                })

        project_obj = {
            "version": int(preset.get("project_version", 15)),
            "projectId": project_id,
            "files": files,
            "transcript": {
                "scenes": [
                    {
                        "id": str(uuid4()),
                        "clips": clips,
                    }
                ],
            },
            "props": {
                "assets": assets,
                "audios": {},
                "speakers": [speaker],
                "overdubInfos": [],
                "ttsClipInfosMap": tts_clip_infos,
                "originalClipsMap": {},
                "backgroundMap": {},
                "analyzeDate": now_iso,
                "mediaEffectMap": {},
                "globalVideoTransform": {"x": 0, "y": 0, "scale": 1, "rotation": 0},
                "initProjectVideoSize": {"width": 1920, "height": 1080},
                "pronunciationDisplay": False,
                "projectAudioLanguage": "ko",
                "audioLanguagesMap": {},
                "captionDisplayMode": {"0": True, "1": False},
                "globalCaptionStyle": deepcopy(preset["global_caption_style"]),
                "markerNames": {},
                "flipSetting": {},
                "videoRatio": 1.7777777777777777,
                "videoSize": {"width": 1920, "height": 1080},
                "lastTTSSettings": {
                    "pitch": voice_pitch,
                    "speed": voice_speed,
                    "volume": voice_volume,
                    "speaker": dict(speaker),
                    "emotion": voice_emotion,
                },
            },
            "statistics": {
                "projectStartMode": "images_to_video",
                "saveInfo": {
                    "created": {"version": "3.6.2", "date": now_iso, "stage": "release"},
                    "updated": {"version": "3.6.2", "date": now_iso, "stage": "release"},
                    "loadCount": 1,
                    "saveCount": 1,
                },
            },
        }

        out_path = Path(req.out_dir) / f"{story_name}.vrew"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("media/", b"")
            for arcname, b in zip_media:
                zf.writestr(arcname, b)
            zf.writestr("project.json", json.dumps(project_obj, ensure_ascii=False, indent=2).encode("utf-8"))

        payload_out = Path(req.out_dir) / "vrew_payload.json"
        payload_out.write_text(json.dumps(req.project, ensure_ascii=False, indent=2), encoding="utf-8")

    def _resolve_export_preset(self, out_dir: Path, story_name: str) -> Dict[str, Any]:
        base = self._default_export_preset()
        template_path = os.getenv("VREW_TEMPLATE_PATH", "").strip()
        candidates: List[Path] = []
        repo_root = Path(__file__).resolve().parents[2]
        if template_path:
            candidates.append(Path(template_path).expanduser())
        candidates.append(repo_root / "reference" / "reference.vrew")
        candidates.append(out_dir / f"{story_name}.vrew")

        for p in candidates:
            template = self._load_preset_from_vrew(p)
            if template is not None:
                base.update({k: v for k, v in template.items() if v is not None})
                break
        return base

    def _load_preset_from_vrew(self, vrew_path: Path) -> Dict[str, Any] | None:
        try:
            if not vrew_path.exists():
                return None
            with zipfile.ZipFile(vrew_path, "r") as zf:
                raw = zf.read("project.json")
            obj = json.loads(raw)
            props = obj.get("props") if isinstance(obj.get("props"), dict) else {}
            lts = props.get("lastTTSSettings") if isinstance(props.get("lastTTSSettings"), dict) else {}
            speaker = lts.get("speaker") if isinstance(lts.get("speaker"), dict) else {}
            gcs = props.get("globalCaptionStyle") if isinstance(props.get("globalCaptionStyle"), dict) else None
            return {
                "project_version": int(obj.get("version", 16)),
                "speaker": speaker if speaker else None,
                "volume": lts.get("volume"),
                "speed": lts.get("speed"),
                "pitch": lts.get("pitch"),
                "emotion": lts.get("emotion"),
                "global_caption_style": deepcopy(gcs) if gcs else None,
            }
        except Exception:
            return None

    def _default_export_preset(self) -> Dict[str, Any]:
        return {
            "project_version": 15,
            "speaker": {
                "provider": "kt",
                "gender": "female",
                "lang": "ko-KR",
                "name": "vos-female28",
                "speakerId": "vos-female28",
                "age": "middle",
                "emotions": ["neutral", "happy", "angry"],
                "tags": ["hurrying", "firm", "strong", "calm"],
            },
            "volume": 0,
            "speed": 0,
            "pitch": -1,
            "emotion": "neutral",
            "global_caption_style": {
                "captionStyleSetting": {
                    "mediaId": "uc-0010-simple-textbox",
                    "yAlign": "bottom",
                    "yOffset": 0,
                    "xOffset": 0,
                    "rotation": 0,
                    "width": 0.96,
                    "scaleFactor": 1.7777777777777777,
                    "customAttributes": [
                        {"attributeName": "--textbox-color", "type": "color-hex", "value": "rgba(0, 0, 0, 0)"},
                        {"attributeName": "--textbox-align", "type": "textbox-align", "value": "center"},
                    ],
                },
                "quillStyle": {
                    "font": "Pretendard-Vrew_700",
                    "size": "100",
                    "color": "#ffffff",
                    "outline-on": "true",
                    "outline-color": "#000000",
                    "outline-width": "6",
                },
            },
        }

    def _collect_scenes(self, project: Dict[str, Any]) -> List[Dict[str, Any]]:
        scenes = [s for s in (project.get("scenes") or []) if isinstance(s, dict)]
        scenes.sort(key=lambda x: int(x.get("id", 0)))
        if not scenes:
            raise RuntimeError("vrew export failed: scenes not found")

        out: List[Dict[str, Any]] = []
        for s in scenes:
            sid = int(s.get("id", 0))
            text = str(s.get("text") or "").strip()
            img = s.get("image") if isinstance(s.get("image"), dict) else {}
            status = str(img.get("status") or "")
            path = str(img.get("path") or "").strip()
            if status != "ok":
                raise RuntimeError(f"vrew export failed: scene {sid} image status is not ok ({status})")
            if not text:
                raise RuntimeError(f"vrew export failed: scene {sid} text is empty")
            if not path:
                raise RuntimeError(f"vrew export failed: scene {sid} image path is empty")
            p = Path(path)
            if not p.exists():
                raise RuntimeError(f"vrew export failed: scene {sid} image file not found ({p})")
            out.append(s)
        return out

    def _audio_name_from_text(self, text: str, sid: int, chunk_idx: int) -> str:
        s = re.sub(r"\s+", " ", (text or "").strip())
        if not s:
            return f"scene_{sid:03d}_{chunk_idx:03d}"
        head = s[:18].strip()
        if not head:
            return f"scene_{sid:03d}_{chunk_idx:03d}"
        head = re.sub(r"[/:*?\"<>|\\\\]+", "_", head)
        return f"scene_{sid:03d}_{chunk_idx:03d}_{head}"[:120]

    def _split_for_clips(
        self,
        text: str,
        max_chars: int,
        soft_max_chars: int,
        caption_line_max_chars: int,
        caption_max_lines: int,
    ) -> List[str]:
        normalized = self._normalize_display_text(text)
        if not normalized:
            return [""]

        limit = max(1, int(max_chars))
        soft_limit = max(limit, int(soft_max_chars))
        units = self._split_meaning_units(normalized)
        chunks: List[str] = []
        current = ""
        for unit in units:
            u = unit.strip()
            if not u:
                continue
            if self._can_keep_soft_unit(u, soft_limit):
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(u)
                continue
            if len(u) > limit:
                if "\"" in u and u.endswith("\"") and len(u) <= soft_limit:
                    if current:
                        chunks.append(current)
                    current = u
                    continue
                if current:
                    chunks.append(current)
                    current = ""
                if self._is_wrapped_dialogue(u):
                    chunks.extend(self._split_wrapped_dialogue(u, limit, soft_limit))
                else:
                    parts = self._merge_terminal_tail(self._hard_split_by_chars(u, limit), soft_limit)
                    chunks.extend(self._fix_dangling_adnominals(parts))
                continue

            if not current:
                current = u
                continue

            candidate = self._join_clip_units(current, u)
            if len(candidate) <= limit:
                current = candidate
            elif self._can_merge_inline_dialogue(current, u, candidate, soft_limit):
                current = candidate
            elif self._can_merge_terminal_unit(candidate, u, soft_limit):
                current = candidate
            elif self._can_merge_dialogue_tail(current, u, candidate, soft_limit):
                current = candidate
            else:
                chunks.append(current)
                current = u

        if current:
            chunks.append(current)
        if not chunks:
            chunks = [normalized]
        return self._rebalance_chunks_for_caption_limits(
            chunks,
            max_chars=limit,
            soft_max_chars=soft_limit,
            caption_line_max_chars=caption_line_max_chars,
            caption_max_lines=caption_max_lines,
        )

    def _can_merge_terminal_unit(self, candidate: str, next_unit: str, soft_max_chars: int) -> bool:
        s = (next_unit or "").strip()
        if not s:
            return False
        prev_len = len(candidate) - len(s) - 1
        if len(candidate) > max(1, int(soft_max_chars)):
            return False
        if prev_len >= 15 and len(s) >= 14:
            return False
        return self._ends_with_terminal_punct(s)

    def _can_keep_soft_unit(self, text: str, soft_max_chars: int) -> bool:
        s = (text or "").strip()
        if not s:
            return False
        if self._is_wrapped_dialogue(s):
            return len(s) <= max(1, int(soft_max_chars))
        if len(s) > max(1, int(soft_max_chars)):
            return False
        return s.endswith(",")

    def _merge_terminal_tail(self, chunks: List[str], soft_max_chars: int) -> List[str]:
        if len(chunks) < 2:
            return chunks
        prev = chunks[-2].strip()
        tail = chunks[-1].strip()
        if not prev or not tail:
            return chunks
        candidate = f"{prev} {tail}"
        if len(candidate) > max(1, int(soft_max_chars)):
            return chunks
        if len(prev) >= 15 and len(tail) >= 14:
            return chunks
        if not self._ends_with_terminal_punct(tail):
            return chunks
        return chunks[:-2] + [candidate]

    def _split_wrapped_dialogue(self, text: str, max_chars: int, soft_max_chars: int) -> List[str]:
        s = (text or "").strip()
        if not self._is_wrapped_dialogue(s):
            return self._merge_terminal_tail(self._hard_split_by_chars(s, max_chars), soft_max_chars)
        dialogue_keep_max = max(max(1, int(soft_max_chars)), 90)
        if len(s) <= dialogue_keep_max:
            return [s]

        inner = s[1:-1].strip()
        if not inner:
            return []

        sentence_units = self._split_sentence_units(inner)
        if len(sentence_units) > 1:
            out: List[str] = []
            for part in sentence_units:
                p = self._strip_edge_quotes(part)
                if not p:
                    continue
                out.append(f"\"{p}\"")
            return out

        parts = self._merge_terminal_tail(self._hard_split_by_chars(inner, max_chars), soft_max_chars)
        if not parts:
            return []
        if len(parts) == 1:
            return [f"\"{parts[0]}\""]

        out: List[str] = []
        for part in parts:
            p = self._strip_edge_quotes(part)
            if not p:
                continue
            out.append(f"\"{p}\"")
        return out

    def _join_clip_units(self, left: str, right: str) -> str:
        l = (left or "").strip()
        r = (right or "").strip()
        if not l:
            return r
        if not r:
            return l
        if l.endswith("\"") and re.match(r"^[가-힣A-Za-z0-9]", r):
            return f"{l}{r}"
        return f"{l} {r}"

    def _can_merge_dialogue_tail(self, current: str, next_unit: str, candidate: str, soft_max_chars: int) -> bool:
        cur = (current or "").strip()
        nxt = (next_unit or "").strip()
        if not cur or not nxt:
            return False
        if not cur.endswith("\""):
            return False
        if len(candidate) > max(1, int(soft_max_chars)):
            return False
        return bool(re.match(r"^[가-힣]", nxt))

    def _can_merge_inline_dialogue(self, current: str, next_unit: str, candidate: str, soft_max_chars: int) -> bool:
        cur = (current or "").strip()
        nxt = (next_unit or "").strip()
        if not cur or not nxt:
            return False
        if not self._is_wrapped_dialogue(nxt):
            return False
        if len(candidate) > max(1, int(soft_max_chars)):
            return False
        return not self._ends_with_terminal_punct(cur)

    def _ends_with_terminal_punct(self, text: str) -> bool:
        s = (text or "").strip()
        return bool(re.search(r"[\.\!\?…。！？][\"'”’\)\]]*$", s) or re.search(r"[\.\!\?…。！？]$", s))

    def _split_meaning_units(self, text: str) -> List[str]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return [text]

        merged_lines: List[str] = []
        buf = ""
        in_quote = False

        for line in lines:
            piece = line.strip()
            if not piece:
                continue

            buf = f"{buf} {piece}".strip() if buf else piece
            in_quote = self._quote_balance(buf) % 2 == 1
            if in_quote:
                continue

            merged_lines.append(buf)
            buf = ""

        if buf:
            merged_lines.append(buf)

        out: List[str] = []
        for line in merged_lines:
            out.extend(self._split_non_dialogue_segments(line))

        cleaned = [self._normalize_wrapped_dialogue(s.strip()) for s in out if s and s.strip()]
        cleaned = [s for s in cleaned if not re.fullmatch(r'["“”‘’]+', s)]
        cleaned = [self._strip_leading_quote_from_narration(s) for s in cleaned]
        merged: List[str] = []
        for item in cleaned:
            s = item.strip()
            if (
                merged
                and len(merged[-1]) <= 3
                and not re.search(r"[,.!?。！？\"“”‘’]", merged[-1])
                and re.match(r"^[가-힣A-Za-z]", s)
            ):
                merged[-1] = f"{merged[-1]} {s}".strip()
            else:
                merged.append(s)
        return merged if merged else [text]

    def _split_non_dialogue_segments(self, text: str) -> List[str]:
        s = (text or "").strip()
        if not s:
            return []
        if self._is_wrapped_dialogue(s):
            return [s]

        segments: List[str] = []
        start = 0
        in_quote = False
        for idx, ch in enumerate(s):
            if ch == "\"":
                if not in_quote and "\"" not in s[idx + 1:]:
                    continue
                in_quote = not in_quote
                if not in_quote:
                    seg = s[start : idx + 1].strip()
                    if seg:
                        segments.append(seg)
                    start = idx + 1
                continue

            if in_quote:
                continue

            if ch in ".!?。！？":
                seg = s[start : idx + 1].strip()
                if seg:
                    segments.append(seg)
                start = idx + 1
                continue

            if ch == ",":
                seg = s[start : idx + 1].strip()
                if seg and len(seg) >= 15:
                    segments.append(seg)
                    start = idx + 1

        tail = s[start:].strip()
        if tail:
            segments.append(tail)

        normalized_segments: List[str] = []
        for seg in segments:
            item = seg.strip()
            if (
                normalized_segments
                and normalized_segments[-1].endswith("\"")
                and (parts := item.split(None, 1))
                and len(parts) == 2
                and re.fullmatch(r"[가-힣]{1,2}", parts[0])
            ):
                normalized_segments.append(parts[0])
                normalized_segments.append(parts[1].strip())
                continue
            normalized_segments.append(item)
        refined: List[str] = []
        for seg in normalized_segments:
            refined.extend(self._split_contrast_phrases(seg))
        return refined or [s]

    def _split_contrast_phrases(self, text: str) -> List[str]:
        s = (text or "").strip()
        if len(s) < 30:
            return [s] if s else []
        # Split on explicit contrast markers.
        for marker in ("그러나", "반면", "하지만"):
            idx = s.find(marker)
            if idx > 0:
                left = s[:idx].strip()
                right = s[idx:].strip()
                if len(left) >= 8 and len(right) >= 8:
                    return [left, right]
        # Split on "-지만" connective when followed by a new clause.
        idx = s.find("지만 ")
        if idx > 0:
            left = s[: idx + len("지만")].strip()
            right = s[idx + len("지만") :].strip()
            if len(left) >= 8 and len(right) >= 8:
                return [left, right]
        for marker in ("와 달리", "과 달리"):
            idx = s.find(marker)
            if idx <= 0:
                continue
            # Prefer splitting right after a topic/subject particle before the contrast marker
            split_at = -1
            for particle in ("은 ", "는 ", "이 ", "가 "):
                pidx = s.rfind(particle, 0, idx)
                if pidx > split_at:
                    split_at = pidx + len(particle) - 1
            if split_at <= 0:
                split_at = s.rfind(" ", 0, idx)
                if split_at <= 0:
                    continue
                left = s[:split_at].strip()
                right = s[split_at + 1 :].strip()
            else:
                left = s[: split_at + 1].strip()
                right = s[split_at + 1 :].strip()
            if len(left) < 8 or len(right) < 8:
                continue
            return [left, right]
        return [s] if s else []

    def _split_sentence_units(self, text: str) -> List[str]:
        parts = re.split(r"(?<=[\.\!\?。！？])\s+", (text or "").strip())
        out: List[str] = []
        for part in parts:
            s = part.strip()
            if s:
                out.append(s)
        return out

    def _quote_balance(self, text: str) -> int:
        return (text or "").count("\"")

    def _is_wrapped_dialogue(self, text: str) -> bool:
        s = (text or "").strip()
        return len(s) >= 2 and s.startswith("\"") and s.endswith("\"")

    def _normalize_wrapped_dialogue(self, text: str) -> str:
        s = (text or "").strip()
        if not self._is_wrapped_dialogue(s):
            return s
        inner = s[1:-1].strip()
        if self._looks_like_quoted_narration(inner):
            return inner
        return f"\"{inner}\""

    def _strip_leading_quote_from_narration(self, text: str) -> str:
        s = (text or "").strip()
        if not s.startswith("\"") or s.endswith("\""):
            return s
        body = s[1:].strip()
        if self._looks_like_quoted_narration(body):
            return body
        return s

    def _strip_edge_quotes(self, text: str) -> str:
        return re.sub(r'^["“”]+|["“”]+$', "", (text or "").strip()).strip()

    def _normalize_display_text(self, text: str) -> str:
        s = str(text or "")
        s = re.sub(r"§§CHAPTER\|[^§]+§§", " ", s)
        s = re.sub(r'([.!?。！？])"', r'\1 "', s)
        s = re.sub(r'"\s+([가-힣A-Za-z])', r'"\1', s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _looks_like_quoted_narration(self, text: str) -> bool:
        s = (text or "").strip()
        if not s:
            return False
        if re.search(r"[?!！？]", s):
            return False
        if not re.search(r"(습니다|였다|했다|있었다|보였다|가리켰다|들렸다|시작했다|향했다|웃었다|떨었다|물러났다)\.$", s):
            return False
        return True

    def _hard_split_by_chars(self, text: str, max_chars: int) -> List[str]:
        s = text.strip()
        if not s:
            return []
        limit = max(1, int(max_chars))
        out: List[str] = []
        while s:
            if len(s) <= limit:
                out.append(s)
                break
            cut = s.rfind(" ", 0, limit + 1)
            if cut <= 0:
                cut = limit
            out.append(s[:cut].strip())
            s = s[cut:].strip()
        return [x for x in out if x]

    def _rebalance_chunks_for_caption_limits(
        self,
        chunks: List[str],
        *,
        max_chars: int,
        soft_max_chars: int,
        caption_line_max_chars: int,
        caption_max_lines: int,
    ) -> List[str]:
        out: List[str] = []
        readable_limit = max(max_chars, caption_line_max_chars * caption_max_lines)
        for chunk in chunks:
            s = str(chunk or "").strip()
            if not s:
                continue
            if self._estimate_caption_line_count(s, caption_line_max_chars) <= caption_max_lines:
                out.append(s)
                continue
            out.extend(
                self._split_for_caption_readability(
                    s,
                    hard_max_chars=readable_limit,
                    soft_max_chars=soft_max_chars,
                    caption_line_max_chars=caption_line_max_chars,
                    caption_max_lines=caption_max_lines,
                )
            )
        return out or chunks

    def _split_for_caption_readability(
        self,
        text: str,
        *,
        hard_max_chars: int,
        soft_max_chars: int,
        caption_line_max_chars: int,
        caption_max_lines: int,
    ) -> List[str]:
        target_chunk_chars = max(caption_line_max_chars * caption_max_lines, 1)
        units = self._split_caption_phrase_units(text)
        if len(units) <= 1:
            parts = self._hard_split_by_chars(text, min(max(hard_max_chars, 1), target_chunk_chars))
            parts = self._merge_terminal_tail(parts, soft_max_chars)
            parts = self._fix_dangling_adnominals(parts)
            return parts or [text.strip()]

        out: List[str] = []
        current = ""
        for unit in units:
            u = unit.strip()
            if not u:
                continue
            candidate = self._join_clip_units(current, u) if current else u
            if current and (
                len(candidate) > hard_max_chars
                or self._estimate_caption_line_count(candidate, caption_line_max_chars) > caption_max_lines
            ):
                out.append(current)
                current = u
                continue
            current = candidate
        if current:
            out.append(current)

        final: List[str] = []
        for item in out:
            s = item.strip()
            if not s:
                continue
            if self._estimate_caption_line_count(s, caption_line_max_chars) <= caption_max_lines:
                final.append(s)
                continue
            final.extend(
                self._hard_split_by_chars(
                    s,
                    min(max(hard_max_chars, 1), target_chunk_chars),
                )
            )
        final = self._fix_dangling_adnominals(final)
        return self._merge_terminal_tail(final, soft_max_chars) or [text.strip()]

    def _split_caption_phrase_units(self, text: str) -> List[str]:
        s = re.sub(r"\s+", " ", str(text or "")).strip()
        if not s:
            return []

        units: List[str] = []
        start = 0
        for idx, ch in enumerate(s):
            if ch in ",.!?;:。！？":
                seg = s[start : idx + 1].strip()
                if seg:
                    units.append(seg)
                start = idx + 1
                continue
        tail = s[start:].strip()
        if tail:
            units.append(tail)
        units = self._fix_dangling_adnominals(units)
        return units or [s]

    def _fix_dangling_adnominals(self, units: List[str]) -> List[str]:
        if not units or len(units) < 2:
            return units
        out = units[:]
        for i in range(len(out) - 1):
            left = out[i].strip()
            right = out[i + 1].strip()
            if not left or not right:
                continue
            # If left ends with a short Korean adnominal (e.g., 무딘/낡은) and right starts with a noun,
            # move the adnominal to the next unit to keep the phrase together.
            m = re.search(r"([가-힣]{1,4})$", left)
            if not m:
                continue
            last = m.group(1)
            if not re.fullmatch(r"[가-힣]{1,4}", last):
                continue
            if not self._ends_with_adnominal_like(last):
                continue
            if not re.match(r"^[가-힣]", right):
                continue
            new_left = left[: -len(last)].rstrip()
            if len(new_left) < 3:
                continue
            out[i] = new_left
            out[i + 1] = f"{last} {right}".strip()
        return out

    def _ends_with_adnominal_like(self, word: str) -> bool:
        if not word:
            return False
        if word.endswith(("은", "는", "운", "한", "된", "던", "할")):
            return True
        ch = word[-1]
        if not re.fullmatch(r"[가-힣]", ch):
            return False
        code = ord(ch) - 0xAC00
        if code < 0 or code > 11171:
            return False
        jong = code % 28
        # jongseong ㄴ(4) or ㄹ(8)
        return jong in (4, 8)

    def _build_words(self, text: str, audio_media_id: str) -> Tuple[List[Dict[str, Any]], float]:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        tokens = re.findall(r"\S+|\s+", normalized)
        words: List[Dict[str, Any]] = []
        t = 0.0
        per_tok = 0.24
        for tok in tokens:
            d = per_tok
            words.append({
                "id": str(uuid4()),
                "text": tok,
                "startTime": round(t, 3),
                "playbackRate": 1,
                "duration": round(d, 3),
                "aligned": True,
                "autoControl": False,
                "type": 0,
                "softDelete": False,
                "originalDuration": round(d, 3),
                "originalStartTime": round(t, 3),
                "truncatedWords": [],
                "mediaId": audio_media_id,
                "audioIds": [audio_media_id],
                "assetIds": [],
            })
            t += d

        # End pause(type=1) and clip end sentinel(type=2) match Vrew transcript pattern.
        words.append({
            "id": str(uuid4()),
            "text": "",
            "startTime": round(t, 3),
            "playbackRate": 1,
            "duration": 0.7,
            "aligned": True,
            "autoControl": False,
            "type": 1,
            "softDelete": False,
            "originalDuration": 0.7,
            "originalStartTime": round(t, 3),
            "truncatedWords": [],
            "mediaId": audio_media_id,
            "audioIds": [audio_media_id],
            "assetIds": [],
        })
        t += 0.7
        words.append({
            "id": str(uuid4()),
            "text": "",
            "startTime": round(t, 3),
            "playbackRate": 1,
            "duration": 0.0,
            "aligned": True,
            "autoControl": False,
            "type": 2,
            "softDelete": False,
            "originalDuration": 0.0,
            "originalStartTime": round(t, 3),
            "truncatedWords": [],
            "mediaId": audio_media_id,
            "audioIds": [audio_media_id],
            "assetIds": [],
        })
        return words, round(t, 3)

    def _normalize_tts_text(self, text: str) -> str:
        original = str(text or "")
        s = original
        # Keep caption text untouched, but make TTS text conservative for Vrew voice synthesis.
        # Remove glossary-style parenthetical explanations from spoken text.
        s = re.sub(r"\s*\([^()]*\)", "", s)
        replacements = {
            "\r": " ",
            "\n": " ",
            "\"": "",
            "'": "",
            "“": "",
            "”": "",
            "‘": "",
            "’": "",
            "…": ".",
            "·": " ",
            "—": " ",
            "–": " ",
            "(": " ",
            ")": " ",
            "[": " ",
            "]": " ",
            "{": " ",
            "}": " ",
            "<": " ",
            ">": " ",
        }
        for old, new in replacements.items():
            s = s.replace(old, new)
        s = self._soften_tts_sentence_breaks(s)
        s = re.sub(r"[`~^*_=/\\|#@]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            s = self._strip_tts_unsafe_chars(s)
            if self._has_tts_payload(s):
                return s

        # Fallback: recover readable Korean/ASCII text if aggressive stripping emptied the clip.
        fallback = re.sub(r"[\r\n\t]+", " ", original)
        fallback = re.sub(r"[^\w\s가-힣.,!?。！？,:;\"'%-]+", " ", fallback, flags=re.UNICODE)
        fallback = re.sub(r"\s+", " ", fallback).strip(" \"'")
        fallback = self._strip_tts_unsafe_chars(fallback)
        if self._has_tts_payload(fallback):
            return fallback
        # Last-resort: ensure TTS has a safe, speakable token to avoid export errors.
        return "잠시"

    def _strip_tts_unsafe_chars(self, text: str) -> str:
        s = str(text or "")
        s = re.sub(r"[^\w\s가-힣.,!?。！？,:;%-]+", " ", s, flags=re.UNICODE)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _has_tts_payload(self, text: str) -> bool:
        s = str(text or "").strip()
        if not s:
            return False
        return bool(re.search(r"[A-Za-z0-9가-힣]", s))

    def _balance_caption_lines(self, text: str, line_max_chars: int = 22, max_lines: int = 2) -> str:
        s = re.sub(r"\s+", " ", str(text or "")).strip()
        if not s or "\n" in s or len(s) < 18:
            return s

        words = s.split()
        if len(words) < 2:
            return s

        best_lines = [s]
        best_score = float("inf")
        target_lines = max(1, int(max_lines))
        target_len = max(8, int(line_max_chars))

        def score(lines: List[str]) -> float:
            lengths = [len(line) for line in lines]
            over = sum(max(0, line_len - target_len) for line_len in lengths)
            imbalance = max(lengths) - min(lengths)
            penalty = float(over * 100 + max(lengths) * 2 + imbalance)
            if len(lines) > target_lines:
                penalty += 1000 * (len(lines) - target_lines)
            if len(lines) == 2:
                penalty += self._caption_break_penalty(lines[0], lines[1])
            return penalty

        def join_words(parts: List[List[str]]) -> List[str]:
            return [" ".join(part).strip() for part in parts if part]

        if len(s) <= target_len:
            best_score = score([s])
            best_lines = [s]

        if target_lines >= 2:
            for i in range(1, len(words)):
                lines = join_words([words[:i], words[i:]])
                if len(lines) != 2:
                    continue
                sc = score(lines)
                if sc < best_score:
                    best_score = sc
                    best_lines = lines

        return "\n".join(best_lines)

    def _estimate_caption_line_count(self, text: str, line_max_chars: int) -> int:
        s = re.sub(r"\s+", " ", str(text or "")).strip()
        if not s:
            return 0
        if "\n" in s:
            return len([line for line in s.splitlines() if line.strip()])
        return max(1, (len(s) + max(1, int(line_max_chars)) - 1) // max(1, int(line_max_chars)))

    def _caption_break_penalty(self, left: str, right: str) -> float:
        penalty = 0.0
        if self._is_good_caption_break(left):
            penalty -= 8.0
        if self._ends_with_awkward_break_token(left):
            penalty += 12.0
        if self._starts_with_awkward_caption_token(right):
            penalty += 8.0
        return penalty

    def _is_good_caption_break(self, text: str) -> bool:
        s = (text or "").strip()
        if not s:
            return False
        if re.search(r"[,.;:!?。！？]$", s):
            return True
        return bool(
            re.search(
                r"(습니다|니다|였다|했다|있었다|없었다|보였다|들렸다|말했다|물었다|웃었다|울었다|떨었다|바랐다|원했다|느꼈다|고|며|는데|지만|면서)$",
                s,
            )
        )

    def _ends_with_awkward_break_token(self, text: str) -> bool:
        s = (text or "").strip()
        if not s:
            return False
        return bool(
            re.search(
                r"(의|이|가|을|를|은|는|도|만|와|과|에|에서|에게|한테|께|로|으로|처럼|만큼|보다|및)$",
                s,
            )
        )

    def _starts_with_awkward_caption_token(self, text: str) -> bool:
        s = (text or "").strip()
        if not s:
            return False
        head = s.split()[0]
        return bool(re.fullmatch(r"(그리고|그러나|하지만|또는|또한|그래서|다만)", head))

    def _soften_tts_sentence_breaks(self, text: str) -> str:
        s = re.sub(r"\s+", " ", str(text or "")).strip()
        if not s:
            return s
        parts = re.split(r"(?<=[.!?。！？])\s+", s)
        if len(parts) <= 1:
            return s

        softened: List[str] = []
        for idx, part in enumerate(parts):
            p = part.strip()
            if not p:
                continue
            if idx < len(parts) - 1:
                p = re.sub(r"[.!?。！？]+$", ",", p)
            softened.append(p)
        return " ".join(softened).strip()

    def _should_export_tts_chunk(self, original_text: str, tts_text: str) -> bool:
        if (tts_text or "").strip():
            return True
        s = re.sub(r"\s+", "", str(original_text or ""))
        if not s:
            return False
        # Skip quote-only or symbol-heavy chunks that have no readable TTS payload.
        if re.fullmatch(r"['\"“”‘’`.,!?。！？:;()\[\]{}<>\-_=+/*\\|~^]+", s):
            return False
        return False
