# yadam/export/vrew_exporter.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
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
        kenburns_info = self._resolve_kenburns_info()

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
        narrator_voice_profile = {
            "speaker": dict(speaker),
            "volume": voice_volume,
            "speed": voice_speed,
            "pitch": voice_pitch,
            "emotion": voice_emotion,
        }
        character_alias_map = self._build_character_alias_map(req.project)
        dialogue_target_name = str(os.getenv("VREW_DIALOGUE_TARGET_CHARACTER", "윤") or "윤").strip()
        yun_char_id = self._find_character_id_by_token(req.project, dialogue_target_name) or self._find_yun_char_id(req.project)
        dialogue_target_tokens = self._collect_character_tokens(req.project, yun_char_id)
        yun_dialogue_voice_profile = self._resolve_yun_dialogue_voice_profile(
            out_dir=Path(req.out_dir),
            story_name=story_name,
            narrator_voice_profile=narrator_voice_profile,
        )
        manual_yun_dialogue_keys = self._load_manual_dialogue_keys_for_story(
            story_name=story_name,
            target_tokens=dialogue_target_tokens,
        )
        yeonhui_char_id = self._find_character_id_by_token(req.project, "연희")
        yeonhui_tokens = self._collect_character_tokens(req.project, yeonhui_char_id)
        yeonhui_dialogue_voice_profile = self._resolve_named_dialogue_voice_profile(
            out_dir=Path(req.out_dir),
            story_name=story_name,
            narrator_voice_profile=narrator_voice_profile,
            template_env_var="VREW_YEONHUI_DIALOGUE_TEMPLATE_PATH",
            default_template_name="reference_소녀_레다_목소리.vrew",
            fallback_out_suffix="_yeonhui_dialogue.vrew",
        )
        manual_yeonhui_dialogue_keys = self._load_manual_dialogue_keys_for_story(
            story_name=story_name,
            target_tokens=yeonhui_tokens,
        )

        files: List[Dict[str, Any]] = []
        assets: Dict[str, Any] = {}
        tts_clip_infos: Dict[str, Any] = {}
        clips: List[Dict[str, Any]] = []
        zip_media: List[Tuple[str, bytes]] = []

        if kenburns_info is not None:
            project_obj = self._build_v16_project(
                scenes=scenes,
                clip_text_max_chars=clip_text_max_chars,
                clip_text_soft_max_chars=clip_text_soft_max_chars,
                caption_line_max_chars=caption_line_max_chars,
                caption_max_lines=caption_max_lines,
                speaker=speaker,
                voice_volume=voice_volume,
                voice_speed=voice_speed,
                voice_pitch=voice_pitch,
                voice_emotion=voice_emotion,
                project_id=project_id,
                now_iso=now_iso,
                preset=preset,
                kenburns_info=kenburns_info,
                files=files,
                assets=assets,
                tts_clip_infos=tts_clip_infos,
                clips=clips,
                zip_media=zip_media,
                character_alias_map=character_alias_map,
                dialogue_char_id=yun_char_id,
                dialogue_voice_profile=yun_dialogue_voice_profile,
                narrator_voice_profile=narrator_voice_profile,
                manual_dialogue_keys=manual_yun_dialogue_keys,
                secondary_dialogue_char_id=yeonhui_char_id,
                secondary_dialogue_voice_profile=yeonhui_dialogue_voice_profile,
                secondary_manual_dialogue_keys=manual_yeonhui_dialogue_keys,
            )
            out_path = Path(req.out_dir) / f"{story_name}.vrew"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr("media/", b"")
                for arcname, b in zip_media:
                    zf.writestr(arcname, b)
                zf.writestr("project.json", json.dumps(project_obj, ensure_ascii=False, indent=2).encode("utf-8"))
            payload_out = Path(req.out_dir) / "vrew_payload.json"
            payload_out.write_text(json.dumps(req.project, ensure_ascii=False, indent=2), encoding="utf-8")
            return

        for zindex, scene in enumerate(scenes):
            sid = int(scene.get("id", 0))
            text = str(scene.get("text") or "").strip()
            prev_text = str((scenes[zindex - 1].get("text") if zindex > 0 else "") or "")
            next_text = str((scenes[zindex + 1].get("text") if zindex + 1 < len(scenes) else "") or "")
            target_dialogues = self._extract_dialogue_fragments_for_char(
                text=text,
                target_char_id=yun_char_id,
                character_alias_map=character_alias_map,
                prev_text=prev_text,
                next_text=next_text,
            )
            if manual_yun_dialogue_keys:
                target_dialogues = list(dict.fromkeys(target_dialogues + manual_yun_dialogue_keys))
            secondary_target_dialogues = self._extract_dialogue_fragments_for_char(
                text=text,
                target_char_id=yeonhui_char_id,
                character_alias_map=character_alias_map,
                prev_text=prev_text,
                next_text=next_text,
            )
            if manual_yeonhui_dialogue_keys:
                secondary_target_dialogues = list(dict.fromkeys(secondary_target_dialogues + manual_yeonhui_dialogue_keys))
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

            last_clip_idx: Optional[int] = None
            last_file_idx: Optional[int] = None
            last_audio_media_id: Optional[str] = None
            last_caption_text: Optional[str] = None
            last_tts_text: Optional[str] = None
            last_raw_text: Optional[str] = None

            for chunk_idx, chunk_text in enumerate(text_chunks, start=1):
                audio_media_id = str(uuid4())
                audio_name = self._audio_name_from_text(chunk_text, sid, chunk_idx)
                tts_text = self._normalize_tts_text(chunk_text)
                voice_profile = self._resolve_voice_profile_for_chunk_multi(
                    chunk_text=chunk_text,
                    narrator_voice_profile=narrator_voice_profile,
                    rules=[
                        (target_dialogues, yun_dialogue_voice_profile),
                        (secondary_target_dialogues, yeonhui_dialogue_voice_profile),
                    ],
                )
                chunk_speaker = dict(voice_profile["speaker"])
                chunk_volume = float(voice_profile["volume"])
                chunk_speed = float(voice_profile["speed"])
                chunk_pitch = float(voice_profile["pitch"])
                chunk_emotion = str(voice_profile["emotion"] or "")
                caption_text = self._balance_caption_lines(
                    chunk_text,
                    line_max_chars=caption_line_max_chars,
                    max_lines=caption_max_lines,
                )
                if not self._should_export_tts_chunk(chunk_text, tts_text):
                    # Merge caption-only or non-TTS-safe chunks into the previous clip.
                    if last_clip_idx is not None and last_audio_media_id is not None:
                        merged_raw = f"{(last_raw_text or '').strip()} {chunk_text.strip()}".strip()
                        merged_tts = self._normalize_tts_text(merged_raw)
                        merged_caption = (last_caption_text or "").strip()
                        if caption_text:
                            merged_caption = f"{merged_caption}\n{caption_text}".strip() if merged_caption else caption_text

                        if merged_caption:
                            clips[last_clip_idx]["captions"][0]["text"][0]["insert"] = merged_caption + "\n"
                            last_caption_text = merged_caption

                        if merged_tts and merged_tts != last_tts_text and last_file_idx is not None:
                            words, duration = self._build_words(merged_tts, last_audio_media_id)
                            clips[last_clip_idx]["words"] = words
                            files[last_file_idx]["videoAudioMetaInfo"]["duration"] = duration
                            files[last_file_idx]["fileSize"] = max(1, int(duration * 16000))
                            tts_info = tts_clip_infos.get(last_audio_media_id, {})
                            if "text" in tts_info:
                                tts_info["text"]["raw"] = merged_tts
                                tts_info["text"]["processed"] = merged_tts
                            tts_info["duration"] = duration
                            tts_clip_infos[last_audio_media_id] = tts_info
                            last_tts_text = merged_tts
                            last_raw_text = merged_raw
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
                        "textAspectLang": chunk_speaker["lang"],
                    },
                    "speaker": chunk_speaker,
                    "duration": duration,
                    "volume": chunk_volume,
                    "speed": chunk_speed,
                    "pitch": chunk_pitch,
                    "version": "v1",
                }
                if chunk_emotion:
                    tts_info["emotion"] = chunk_emotion
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
                last_clip_idx = len(clips) - 1
                last_file_idx = len(files) - 1
                last_audio_media_id = audio_media_id
                last_caption_text = caption_text
                last_tts_text = tts_text
                last_raw_text = chunk_text

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

        # Narration voice-only overlay:
        # Load only voice-related fields from a dedicated narration template,
        # keeping all non-voice export settings from the main preset resolution.
        narration_template_path = os.getenv("VREW_NARRATION_TEMPLATE_PATH", "").strip()
        if narration_template_path:
            narration_candidates = [Path(narration_template_path).expanduser()]
        else:
            narration_candidates = [repo_root / "reference" / "reference_자비왕후_목소리.vrew"]

        for p in narration_candidates:
            template = self._load_preset_from_vrew(p)
            if template is None:
                continue
            for k in ("speaker", "volume", "speed", "pitch", "emotion"):
                v = template.get(k)
                if v is not None:
                    base[k] = v
            break
        return base

    def _resolve_yun_dialogue_voice_profile(
        self,
        *,
        out_dir: Path,
        story_name: str,
        narrator_voice_profile: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        return self._resolve_named_dialogue_voice_profile(
            out_dir=out_dir,
            story_name=story_name,
            narrator_voice_profile=narrator_voice_profile,
            template_env_var="VREW_YUN_DIALOGUE_TEMPLATE_PATH",
            default_template_name="reference_소년_폼비_목소리.vrew",
            fallback_out_suffix="_yun_dialogue.vrew",
        )

    def _resolve_named_dialogue_voice_profile(
        self,
        *,
        out_dir: Path,
        story_name: str,
        narrator_voice_profile: Dict[str, Any],
        template_env_var: str,
        default_template_name: str,
        fallback_out_suffix: str,
    ) -> Optional[Dict[str, Any]]:
        template_path = os.getenv(template_env_var, "").strip()
        repo_root = Path(__file__).resolve().parents[2]
        candidates: List[Path] = []
        if template_path:
            candidates.append(Path(template_path).expanduser())
        else:
            candidates.append(repo_root / "reference" / default_template_name)
            candidates.append(out_dir / f"{story_name}{fallback_out_suffix}")

        for p in candidates:
            template = self._load_preset_from_vrew(p)
            if template is None:
                continue
            profile = {
                "speaker": dict(narrator_voice_profile.get("speaker") or {}),
                "volume": float(narrator_voice_profile.get("volume", 0)),
                "speed": float(narrator_voice_profile.get("speed", 0)),
                "pitch": float(narrator_voice_profile.get("pitch", -1)),
                "emotion": str(narrator_voice_profile.get("emotion") or "neutral"),
            }
            if isinstance(template.get("speaker"), dict):
                profile["speaker"] = dict(template["speaker"])
            for k in ("volume", "speed", "pitch", "emotion"):
                if template.get(k) is not None:
                    profile[k] = template[k]
            return profile
        return None

    def _load_manual_dialogue_keys_for_story(
        self,
        *,
        story_name: str,
        target_tokens: Optional[List[str]] = None,
    ) -> List[str]:
        repo_root = Path(__file__).resolve().parents[2]
        legacy_path = repo_root / "stories" / f"{story_name}_yun_dialogues.txt"
        generic_path = repo_root / "stories" / f"{story_name}_dialogue_overrides.txt"
        target_set = {str(t).strip().lower() for t in (target_tokens or []) if str(t).strip()}
        out: List[str] = []
        if generic_path.exists():
            try:
                for raw in generic_path.read_text(encoding="utf-8").splitlines():
                    line = str(raw or "").strip()
                    if not line or line.startswith("#"):
                        continue
                    char_label = ""
                    dialogue = line
                    if "\t" in line:
                        char_label, dialogue = line.split("\t", 1)
                    elif "|" in line:
                        char_label, dialogue = line.split("|", 1)
                    char_label = str(char_label or "").strip().lower()
                    if char_label and target_set and char_label not in target_set:
                        continue
                    k = self._dialogue_key(dialogue)
                    if k:
                        out.append(k)
            except Exception:
                return []
        if legacy_path.exists():
            try:
                for raw in legacy_path.read_text(encoding="utf-8").splitlines():
                    line = str(raw or "").strip()
                    if not line or line.startswith("#"):
                        continue
                    k = self._dialogue_key(line)
                    if k:
                        out.append(k)
            except Exception:
                return []
        return list(dict.fromkeys(out))

    def _find_character_id_by_token(self, project: Dict[str, Any], token: str) -> Optional[str]:
        t = str(token or "").strip()
        if not t:
            return None
        for c in (project.get("characters") or []):
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or "").strip()
            if not cid:
                continue
            tokens = [str(c.get("name") or "").strip()]
            tokens.extend(str(a).strip() for a in (c.get("aliases") or []) if str(a).strip())
            if any(tok == t for tok in tokens):
                return cid
        return None

    def _collect_character_tokens(self, project: Dict[str, Any], char_id: Optional[str]) -> List[str]:
        cid = str(char_id or "").strip()
        if not cid:
            return []
        for c in (project.get("characters") or []):
            if not isinstance(c, dict):
                continue
            if str(c.get("id") or "").strip() != cid:
                continue
            out = [str(c.get("name") or "").strip()]
            out.extend(str(a).strip() for a in (c.get("aliases") or []) if str(a).strip())
            return [x for x in out if x]
        return []

    def _build_character_alias_map(self, project: Dict[str, Any]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for c in (project.get("characters") or []):
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or "").strip()
            if not cid:
                continue
            tokens = [str(c.get("name") or "").strip()]
            tokens.extend(str(a).strip() for a in (c.get("aliases") or []) if str(a).strip())
            for tok in tokens:
                if tok:
                    out[tok.lower()] = cid
        return out

    def _find_yun_char_id(self, project: Dict[str, Any]) -> Optional[str]:
        for c in (project.get("characters") or []):
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or "").strip()
            if not cid:
                continue
            name = str(c.get("name") or "").strip()
            aliases = [str(a).strip() for a in (c.get("aliases") or []) if str(a).strip()]
            tokens = [name] + aliases
            if any(tok == "윤" or tok == "소년 윤" or tok.startswith("윤 ") or tok.endswith(" 윤") for tok in tokens):
                return cid
        return None

    def _extract_dialogue_fragments_for_char(
        self,
        *,
        text: str,
        target_char_id: Optional[str],
        character_alias_map: Dict[str, str],
        prev_text: str = "",
        next_text: str = "",
    ) -> List[str]:
        if not target_char_id:
            return []
        src = str(text or "")
        if not src:
            return []
        out: List[str] = []
        for m in re.finditer(r'"([^"\n]+)"', src):
            quoted = str(m.group(1) or "").strip()
            if not quoted:
                continue
            # Addressing the target by name (e.g., "윤아, ...") is usually
            # another speaker talking to the target, not target speech.
            if re.match(r"^윤아(?:\s|,|!|\?|$)", quoted):
                continue
            before = src[max(0, m.start() - 100) : m.start()]
            after = src[m.end() : min(len(src), m.end() + 100)]
            # Scene splitting can cut speaker cues right before/after a quote.
            # Borrow neighboring-scene context for boundary quotes.
            if len(before.strip()) < 20 and prev_text:
                before = (str(prev_text)[-120:] + " " + before).strip()
            if len(after.strip()) < 20 and next_text:
                after = (after + " " + str(next_text)[:120]).strip()
            speaker_id = self._infer_context_speaker(before=before, after=after, character_alias_map=character_alias_map)
            if speaker_id != target_char_id:
                continue
            out.append(self._dialogue_key(quoted))
        return out

    def _infer_context_speaker(
        self,
        *,
        before: str,
        after: str,
        character_alias_map: Dict[str, str],
    ) -> Optional[str]:
        speech_re = re.compile(r"(말|외치|묻|답하|대답|속삭|덧붙|지목|호통|입을\s*떼|입을\s*뗍)", re.IGNORECASE)
        speech_noun_re = re.compile(r"(말|목소리|대답|외침|속삭임|호통|한마디)", re.IGNORECASE)
        b = str(before or "")
        a = str(after or "")
        before_clause = b
        after_clause = re.split(r"[.!?]\s*", a, maxsplit=1)[0]
        if not (
            speech_re.search(before_clause[-90:])
            or speech_re.search(after_clause[:70])
            or speech_noun_re.search(before_clause[-90:])
            or speech_noun_re.search(after_clause[:70])
        ):
            return None

        scores: Dict[str, int] = {}
        b_low = before_clause.lower()
        a_low = after_clause.lower()
        for tok, cid in character_alias_map.items():
            if not tok:
                continue
            score = 0
            tok_re = re.escape(tok)
            # Prefer subject-form cues like "윤이 ... 말하다" near the quote boundary.
            before_subject = re.search(
                rf"{tok_re}(?:이|은|는|가)\s*[^\.!?\"“”\n]{{0,72}}{speech_re.pattern}",
                b_low[-140:],
                re.IGNORECASE,
            )
            after_subject = re.search(
                rf"{tok_re}(?:이|은|는|가)\s*[^\.!?\"“”\n]{{0,72}}{speech_re.pattern}",
                a_low[:140],
                re.IGNORECASE,
            )
            before_possessive = re.search(
                rf"{tok_re}의\s*[^\.!?\"“”\n]{{0,14}}{speech_noun_re.pattern}",
                b_low[-90:],
                re.IGNORECASE,
            )
            after_possessive = re.search(
                rf"{tok_re}의\s*[^\.!?\"“”\n]{{0,14}}{speech_noun_re.pattern}",
                a_low[:90],
                re.IGNORECASE,
            )
            after_lead = re.search(
                rf"^\s*[”\"'\)\]\.,!\?…:;]*\s*{tok_re}(?:이|은|는|가|의)\b",
                a_low[:60],
                re.IGNORECASE,
            )
            before_quoted_said = re.search(
                rf"라고\s*{tok_re}(?:이|은|는|가)",
                b_low[-90:],
                re.IGNORECASE,
            )
            after_quoted_said = re.search(
                rf"라고\s*{tok_re}(?:이|은|는|가)",
                a_low[:90],
                re.IGNORECASE,
            )
            before_intro = re.search(
                rf"{tok_re}(?:이|은|는|가)\s*[^\.!?\"“”\n]{{0,72}}(다가가|다가갑|고개를\s*숙|고개를\s*끄덕|손가락[^\.!?\"“”\n]{{0,18}}가리키|목소리로|차갑게|공손히|나직이|조용히|천천히)",
                b_low[-140:],
                re.IGNORECASE,
            )
            after_intro = re.search(
                rf"{tok_re}(?:이|은|는|가)\s*[^\.!?\"“”\n]{{0,72}}(다가가|다가갑|고개를\s*숙|고개를\s*끄덕|손가락[^\.!?\"“”\n]{{0,18}}가리키|목소리로|차갑게|공손히|나직이|조용히|천천히)",
                a_low[:140],
                re.IGNORECASE,
            )
            if before_subject:
                score += 4
            if after_subject:
                score += 2
            if before_possessive:
                score += 3
            if after_possessive:
                score += 2
            if after_lead:
                score += 2
            if before_quoted_said or after_quoted_said:
                score += 3
            if before_intro:
                score += 2
            if after_intro:
                score += 1
            if score > 0:
                scores[cid] = max(scores.get(cid, 0), score)

        if not scores:
            return None
        best_score = max(scores.values())
        best = [cid for cid, s in scores.items() if s == best_score]
        if len(best) != 1:
            return None
        return best[0]

    def _dialogue_key(self, text: str) -> str:
        s = re.sub(r"\s+", " ", str(text or "").strip())
        s = re.sub(r'^[\"“”]+|[\"“”]+$', "", s)
        return s.strip().lower()

    def _resolve_voice_profile_for_chunk(
        self,
        *,
        chunk_text: str,
        target_dialogues: List[str],
        narrator_voice_profile: Dict[str, Any],
        dialogue_voice_profile: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not dialogue_voice_profile or not target_dialogues:
            return narrator_voice_profile
        s = str(chunk_text or "").strip()
        if not s:
            return narrator_voice_profile
        # Apply dialogue voice only when this chunk actually contains
        # a quoted fragment attributed to the target character.
        chunk_quotes = [self._dialogue_key(q) for q in re.findall(r'"([^"\n]+)"', s)]
        if chunk_quotes:
            for q in chunk_quotes:
                if not q:
                    continue
                for frag in target_dialogues:
                    if q == frag:
                        return dialogue_voice_profile
                    if min(len(q), len(frag)) >= 8 and (q in frag or frag in q):
                        return dialogue_voice_profile
            return narrator_voice_profile
        key = self._dialogue_key(s)
        if not key:
            return narrator_voice_profile
        for frag in target_dialogues:
            if key == frag:
                return dialogue_voice_profile
            if min(len(key), len(frag)) >= 8 and (key in frag or frag in key):
                return dialogue_voice_profile
        return narrator_voice_profile

    def _resolve_voice_profile_for_chunk_multi(
        self,
        *,
        chunk_text: str,
        narrator_voice_profile: Dict[str, Any],
        rules: List[Tuple[List[str], Optional[Dict[str, Any]]]],
    ) -> Dict[str, Any]:
        best_profile: Optional[Dict[str, Any]] = None
        best_score = -1
        for target_dialogues, voice_profile in rules:
            if not voice_profile or not target_dialogues:
                continue
            score = self._dialogue_match_score(chunk_text=chunk_text, target_dialogues=target_dialogues)
            if score > best_score:
                best_score = score
                best_profile = voice_profile
        if best_profile is None or best_score < 0:
            return narrator_voice_profile
        return best_profile

    def _dialogue_match_score(self, *, chunk_text: str, target_dialogues: List[str]) -> int:
        s = str(chunk_text or "").strip()
        if not s:
            return -1
        best = -1
        chunk_quotes = [self._dialogue_key(q) for q in re.findall(r'"([^"\n]+)"', s)]
        if chunk_quotes:
            for q in chunk_quotes:
                if not q:
                    continue
                for frag in target_dialogues:
                    if q == frag:
                        best = max(best, 100 + len(q))
                    elif min(len(q), len(frag)) >= 8 and (q in frag or frag in q):
                        best = max(best, 60 + min(len(q), len(frag)))
            if best >= 0:
                return best
        key = self._dialogue_key(s)
        if not key:
            return -1
        for frag in target_dialogues:
            if key == frag:
                best = max(best, 90 + len(key))
            elif min(len(key), len(frag)) >= 8 and (key in frag or frag in key):
                best = max(best, 50 + min(len(key), len(frag)))
        return best

    def _resolve_kenburns_info(self) -> Optional[Dict[str, Any]]:
        enable = str(os.getenv("VREW_ENABLE_KENBURNS", "1")).strip()
        tmpl = str(os.getenv("VREW_KENBURNS_TEMPLATE_PATH", "")).strip()
        if enable in ("0", "false", "False"):
            return None
        if not tmpl:
            return {
                "type": "custom",
                "from": {"scale": 1, "centerX": 0.5, "centerY": 0.5},
                "to": {"scale": 0.8658536585365854, "centerX": 0.501219512195122, "centerY": 0.5229992378048781},
            }
        p = Path(tmpl).expanduser()
        if not p.exists():
            return None
        try:
            with zipfile.ZipFile(p, "r") as zf:
                raw = zf.read("project.json")
            obj = json.loads(raw)
        except Exception:
            return None
        tracks = obj.get("props", {}).get("tracks", {})
        if isinstance(tracks, dict):
            for t in tracks.values():
                if not isinstance(t, dict):
                    continue
                if t.get("type") != "image":
                    continue
                kb = t.get("kenburnsAnimationInfo")
                if kb:
                    return kb
        return None

    def _build_v16_project(
        self,
        *,
        scenes: List[Dict[str, Any]],
        clip_text_max_chars: int,
        clip_text_soft_max_chars: int,
        caption_line_max_chars: int,
        caption_max_lines: int,
        speaker: Dict[str, Any],
        voice_volume: float,
        voice_speed: float,
        voice_pitch: float,
        voice_emotion: str,
        project_id: str,
        now_iso: str,
        preset: Dict[str, Any],
        kenburns_info: Dict[str, Any],
        files: List[Dict[str, Any]],
        assets: Dict[str, Any],
        tts_clip_infos: Dict[str, Any],
        clips: List[Dict[str, Any]],
        zip_media: List[Tuple[str, bytes]],
        character_alias_map: Dict[str, str],
        dialogue_char_id: Optional[str],
        dialogue_voice_profile: Optional[Dict[str, Any]],
        narrator_voice_profile: Dict[str, Any],
        manual_dialogue_keys: Optional[List[str]] = None,
        secondary_dialogue_char_id: Optional[str] = None,
        secondary_dialogue_voice_profile: Optional[Dict[str, Any]] = None,
        secondary_manual_dialogue_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        tracks: Dict[str, Any] = {}
        scene_names: Dict[str, str] = {}
        # Keep one logical Vrew scene for the whole timeline so global selection
        # stays available even when per-image ken-burns tracks are applied.
        unified_scene_id = str(uuid4())
        scene_names[unified_scene_id] = "scene_all"

        for zindex, scene in enumerate(scenes):
            sid = int(scene.get("id", 0))
            text = str(scene.get("text") or "").strip()
            prev_text = str((scenes[zindex - 1].get("text") if zindex > 0 else "") or "")
            next_text = str((scenes[zindex + 1].get("text") if zindex + 1 < len(scenes) else "") or "")
            target_dialogues = self._extract_dialogue_fragments_for_char(
                text=text,
                target_char_id=dialogue_char_id,
                character_alias_map=character_alias_map,
                prev_text=prev_text,
                next_text=next_text,
            )
            if manual_dialogue_keys:
                target_dialogues = list(dict.fromkeys(target_dialogues + list(manual_dialogue_keys)))
            secondary_target_dialogues = self._extract_dialogue_fragments_for_char(
                text=text,
                target_char_id=secondary_dialogue_char_id,
                character_alias_map=character_alias_map,
                prev_text=prev_text,
                next_text=next_text,
            )
            if secondary_manual_dialogue_keys:
                secondary_target_dialogues = list(dict.fromkeys(secondary_target_dialogues + list(secondary_manual_dialogue_keys)))
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

            image_track_id = str(uuid4())
            tracks[image_track_id] = {
                "trackId": image_track_id,
                "mediaId": image_media_id,
                "xPos": 0,
                "yPos": -0.007936507936507908,
                "height": 1.0158730158730158,
                "width": 1,
                "rotation": 0,
                "zIndex": zindex,
                "type": "image",
                "originalWidthHeightRatio": 16.0 / 9.0,
                "importType": "image",
                "kenburnsAnimationInfo": deepcopy(kenburns_info),
                "stats": {"fillType": "cut", "fillMenu": "floating", "rearrangeCount": 0},
            }
            image_asset_id = str(uuid4())
            assets[image_asset_id] = {"trackIds": [image_track_id], "role": "sub"}

            for chunk_idx, chunk_text in enumerate(text_chunks, start=1):
                audio_media_id = str(uuid4())
                audio_name = self._audio_name_from_text(chunk_text, sid, chunk_idx)
                tts_text = self._normalize_tts_text(chunk_text)
                voice_profile = self._resolve_voice_profile_for_chunk_multi(
                    chunk_text=chunk_text,
                    narrator_voice_profile=narrator_voice_profile,
                    rules=[
                        (target_dialogues, dialogue_voice_profile),
                        (secondary_target_dialogues, secondary_dialogue_voice_profile),
                    ],
                )
                chunk_speaker = dict(voice_profile["speaker"])
                chunk_volume = float(voice_profile["volume"])
                chunk_speed = float(voice_profile["speed"])
                chunk_pitch = float(voice_profile["pitch"])
                chunk_emotion = str(voice_profile["emotion"] or "")
                caption_text = self._balance_caption_lines(
                    chunk_text,
                    line_max_chars=caption_line_max_chars,
                    max_lines=caption_max_lines,
                )
                if not self._should_export_tts_chunk(chunk_text, tts_text):
                    continue

                words, duration = self._build_words_v16(tts_text)
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
                    "text": {"raw": tts_text, "processed": tts_text, "textAspectLang": chunk_speaker["lang"]},
                    "speaker": chunk_speaker,
                    "duration": duration,
                    "volume": chunk_volume,
                    "speed": chunk_speed,
                    "pitch": chunk_pitch,
                    "version": "v1",
                }
                if chunk_emotion:
                    tts_info["emotion"] = chunk_emotion
                tts_clip_infos[audio_media_id] = tts_info

                t = 0.0
                for w in words:
                    w_dur = float(w.get("duration") or 0)
                    tts_track_id = str(uuid4())
                    tracks[tts_track_id] = {
                        "trackId": tts_track_id,
                        "mediaId": audio_media_id,
                        "volume": 1,
                        "sourceIn": round(t, 3),
                        "sourceOut": round(t + w_dur, 3),
                        "loop": False,
                        "playbackRate": 1,
                        "type": "ttsClip",
                    }
                    asset_id = str(uuid4())
                    assets[asset_id] = {"trackIds": [tts_track_id], "role": "main"}
                    w["assetIds"] = [asset_id] if w.get("type") != 2 else []
                    t += w_dur

                clips.append({
                    "sceneId": unified_scene_id,
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
                })

        return {
            "version": 16,
            "projectId": project_id,
            "files": files,
            "transcript": {"clips": clips, "sceneNames": scene_names, "translateInfo": None},
            "props": {
                "tracks": tracks,
                "assets": assets,
                "overdubInfos": [],
                "analyzeDate": now_iso,
                "captionDisplayMode": {"0": True, "1": False},
                "mediaEffectMap": {},
                "markerNames": {},
                "flipSetting": {},
                "videoRatio": 1.7777777777777777,
                "globalVideoTransform": {"x": 0, "y": 0, "scale": 1, "rotation": 0},
                "videoSize": {"width": 1920, "height": 1080},
                "backgroundMap": {},
                "globalCaptionStyle": deepcopy(preset["global_caption_style"]),
                "lastTTSSettings": {
                    "pitch": voice_pitch,
                    "speed": voice_speed,
                    "volume": voice_volume,
                    "speaker": dict(speaker),
                    "emotion": voice_emotion,
                    "version": "v1",
                },
                "initProjectVideoSize": {"width": 1920, "height": 1080},
                "pronunciationDisplay": False,
                "projectAudioLanguage": "ko",
                "audioLanguagesMap": {},
                "originalClips": [],
                "ttsClipInfosMap": tts_clip_infos,
            },
            "comment": {},
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

    def _build_words_v16(self, text: str) -> Tuple[List[Dict[str, Any]], float]:
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
                "playbackRate": 1,
                "duration": round(d, 3),
                "aligned": True,
                "type": 0,
                "originalDuration": round(d, 3),
                "originalStartTime": round(t, 3),
                "truncatedWords": [],
                "assetIds": [],
            })
            t += d
        words.append({
            "id": str(uuid4()),
            "text": "",
            "playbackRate": 1,
            "duration": 0.7,
            "aligned": True,
            "type": 1,
            "originalDuration": 0.7,
            "originalStartTime": round(t, 3),
            "truncatedWords": [],
            "assetIds": [],
        })
        t += 0.7
        words.append({
            "id": str(uuid4()),
            "text": "",
            "playbackRate": 1,
            "duration": 0.0,
            "aligned": True,
            "type": 2,
            "originalDuration": 0.0,
            "originalStartTime": round(t, 3),
            "truncatedWords": [],
            "assetIds": [],
        })
        return words, round(t, 3)

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

            if self._should_force_quote_boundary(current, u):
                chunks.append(current)
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
        chunks = self._split_chunks_on_quote_boundaries(chunks)
        chunks = self._rebalance_chunks_for_caption_limits(
            chunks,
            max_chars=limit,
            soft_max_chars=soft_limit,
            caption_line_max_chars=caption_line_max_chars,
            caption_max_lines=caption_max_lines,
        )
        return self._repair_chunk_word_boundaries(chunks)

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

    def _split_chunks_on_quote_boundaries(self, chunks: List[str]) -> List[str]:
        out: List[str] = []
        for chunk in chunks:
            s = (chunk or "").strip()
            if not s:
                continue
            if self._is_wrapped_dialogue(s):
                out.append(s)
                continue
            if "\"" not in s:
                out.append(s)
                continue
            parts = [p.strip() for p in s.split("\"") if p and p.strip()]
            if not parts:
                continue
            for p in parts:
                refined = self._strip_edge_quotes(self._strip_leading_quote_from_narration(p))
                if refined:
                    out.append(refined)
        return out or chunks

    def _repair_chunk_word_boundaries(self, chunks: List[str]) -> List[str]:
        if len(chunks) < 2:
            return chunks
        out = [str(c or "").strip() for c in chunks if str(c or "").strip()]
        if len(out) < 2:
            return out
        i = 0
        while i < len(out) - 1:
            cur = out[i]
            nxt = out[i + 1]
            if not cur or not nxt:
                i += 1
                continue
            last_word = cur.split()[-1] if cur.split() else ""
            if not last_word:
                i += 1
                continue
            # Fix broken Korean word boundary: "... 대" + "인들께선..."
            if (
                1 <= len(last_word) <= 2
                and re.fullmatch(r"[가-힣]+", last_word)
                and re.match(r"^[가-힣]", nxt)
                and not re.search(r"[\.\!\?…。！？,:;]$", cur)
            ):
                head = cur[: -len(last_word)].rstrip()
                if head:
                    out[i] = head
                    if len(last_word) == 1:
                        out[i + 1] = f"{last_word}{nxt}"
                    else:
                        out[i + 1] = f"{last_word} {nxt}"
            i += 1
        return [c for c in out if c]

    def _should_force_quote_boundary(self, current: str, next_unit: str) -> bool:
        cur = (current or "").strip()
        nxt = (next_unit or "").strip()
        if not cur or not nxt:
            return False
        cur_dialogue = self._is_wrapped_dialogue(cur)
        nxt_dialogue = self._is_wrapped_dialogue(nxt)
        # Keep narration and direct-quote chunks in separate clips so
        # per-speaker voice assignment stays stable.
        if cur_dialogue != nxt_dialogue:
            return True
        return False

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
        return ""

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
