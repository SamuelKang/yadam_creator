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


@dataclass(frozen=True)
class VrewExportRequest:
    project: Dict[str, Any]
    out_dir: str
    clip_text_max_chars: int = 30


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
        input_script = str(req.project.get("project", {}).get("input_script_path") or "").strip()
        story_name = Path(input_script).stem if input_script else "story"

        now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
        project_id = str(uuid4())
        speaker_id = "10"
        speaker = {
            "speakerId": speaker_id,
            "name": "unknown",
            "provider": "vrew",
            "age": "youth",
            "gender": "female",
            "lang": "ko",
        }

        files: List[Dict[str, Any]] = []

        assets: Dict[str, Any] = {}
        tts_clip_infos: Dict[str, Any] = {}
        clips: List[Dict[str, Any]] = []
        zip_media: List[Tuple[str, bytes]] = []

        for zindex, scene in enumerate(scenes):
            sid = int(scene.get("id", 0))
            text = str(scene.get("text") or "").strip()
            text_chunks = self._split_for_clips(text, clip_text_max_chars)
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

            asset_id = str(uuid4())
            assets[asset_id] = {
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
                words, duration = self._build_words(chunk_text, audio_media_id)
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
                tts_clip_infos[audio_media_id] = {
                    "text": {
                        "raw": chunk_text,
                        "processed": chunk_text,
                        "textAspectLang": "ko",
                    },
                    "speaker": {
                        "age": speaker["age"],
                        "gender": speaker["gender"],
                        "lang": speaker["lang"],
                        "name": speaker["name"],
                        "speakerId": speaker["speakerId"],
                        "provider": speaker["provider"],
                        "versions": ["v1"],
                    },
                    "duration": duration,
                    "volume": 1,
                    "speed": 0,
                    "pitch": 0,
                    "version": "v1",
                }

                clips.append({
                    "words": words,
                    "captionMode": "MANUAL",
                    "captions": [
                        {"text": [{"insert": chunk_text + "\n"}]},
                        {"text": [{"insert": "\n"}]},
                    ],
                    "assetIds": [asset_id],
                    "dirty": {"blankDeleted": False, "caption": False, "video": False},
                    "translationModified": {"result": False, "source": False},
                    "id": str(uuid4()),
                    "audioIds": [],
                })

        project_obj = {
            "version": 15,
            "projectId": project_id,
            "files": files,
            "transcript": {
                "scenes": [
                    {
                        "id": str(uuid4()),
                        "clips": clips,
                    }
                ]
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
                "globalCaptionStyle": {
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
                "markerNames": {},
                "flipSetting": {},
                "videoRatio": 1.7777777777777777,
                "videoSize": {"width": 1920, "height": 1080},
                "lastTTSSettings": {
                    "pitch": 0,
                    "speed": 0,
                    "volume": 0,
                    "speaker": {
                        "age": speaker["age"],
                        "gender": speaker["gender"],
                        "lang": speaker["lang"],
                        "name": speaker["name"],
                        "speakerId": speaker["speakerId"],
                        "provider": speaker["provider"],
                    },
                    "version": "v1",
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

    def _split_for_clips(self, text: str, max_chars: int) -> List[str]:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if not normalized:
            return [""]

        limit = max(1, int(max_chars))
        units = self._split_meaning_units(normalized)
        chunks: List[str] = []
        current = ""
        for unit in units:
            u = unit.strip()
            if not u:
                continue
            if len(u) > limit:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(self._hard_split_by_chars(u, limit))
                continue

            if not current:
                current = u
                continue

            candidate = f"{current} {u}"
            if len(candidate) <= limit:
                current = candidate
            else:
                chunks.append(current)
                current = u

        if current:
            chunks.append(current)
        return chunks or [normalized]

    def _split_meaning_units(self, text: str) -> List[str]:
        # 문장 부호/줄바꿈 경계를 우선 적용한다.
        parts = re.split(r"(?<=[\.\!\?…。！？])\s+|\n+", text)
        out: List[str] = []
        for p in parts:
            s = p.strip()
            if s:
                out.append(s)
        return out if out else [text]

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
                "playbackRate": 1,
            })
            t += d

        # 샘플 .vrew와 유사하게 clip 종료 여백 단어를 추가한다.
        words.append({
            "id": str(uuid4()),
            "text": "",
            "startTime": round(t, 3),
            "duration": 0.7,
            "aligned": True,
            "autoControl": False,
            "type": 0,
            "softDelete": False,
            "originalDuration": 0.7,
            "originalStartTime": round(t, 3),
            "truncatedWords": [],
            "mediaId": audio_media_id,
            "audioIds": [audio_media_id],
            "assetIds": [],
            "playbackRate": 1,
        })
        t += 0.7
        words.append({
            "id": str(uuid4()),
            "text": "",
            "startTime": round(t, 3),
            "duration": 0.0,
            "aligned": True,
            "autoControl": False,
            "type": 0,
            "softDelete": False,
            "originalDuration": 0.0,
            "originalStartTime": round(t, 3),
            "truncatedWords": [],
            "mediaId": audio_media_id,
            "audioIds": [audio_media_id],
            "assetIds": [],
            "playbackRate": 1,
        })
        return words, round(t, 3)
