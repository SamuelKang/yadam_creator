# yadam/nlp/llm_extract.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from google import genai
from google.genai import types


# --------- Structured Output (Pydantic Schema) ---------
class LLMCharacter(BaseModel):
    name_canonical: str
    aliases: List[str] = Field(default_factory=list)
    species: str = Field(default="인간", description="인간/소/개/말/고양이/기타")

    # 기존
    role: str = Field(default="조연")
    traits: List[str] = Field(default_factory=list)
    visual_anchors: List[str] = Field(default_factory=list)

    # 기존(이미 추가되어 있던 것)
    gender: str = Field(default="불명", description="남/여/불명")
    age_stage: str = Field(default="불명", description="유아/아동/청소년/청년/중년/노년/불명")
    age_hint: str = Field(default="", description="예: 열 살 남짓, 스무 살 무렵 등(근거 문구)")
    variants: List[str] = Field(default_factory=list, description="성장 서사 시 예: ['아동','청년']")

    # ✅ 추가: 궁중/민간 구분 + 계급/재산 + 복장 티어/앵커
    context: str = Field(
        default="민간",
        description="인물이 주로 속하는 맥락/공간: 궁중/민간/관아/사찰/장터/기타"
    )
    court_role: str = Field(
        default="",
        description="context가 궁중일 때만: 왕/왕비/세자/후궁/궁녀/내관/문신/무관/호위 등"
    )
    social_class: str = Field(
        default="불명",
        description="민간 기준 신분: 양반/중인/상민/천민/승려/무속/불명"
    )
    wealth_level: str = Field(
        default="불명",
        description="경제력: 부유/보통/빈곤/불명"
    )
    wardrobe_tier: str = Field(
        default="T2",
        description="복장 등급: T3(상류)/T2(중류)/T1(하류)"
    )
    wardrobe_anchors: List[str] = Field(
        default_factory=list,
        description="복식/소품 앵커 3~6개(짧게). 궁중이면 궁중 관복/궁녀복 등 규격 반영."
    )


class LLMPlace(BaseModel):
    name_canonical: str = Field(..., description="대본에 근거한 대표 장소명(정규화)")
    aliases: List[str] = Field(default_factory=list, description="대본에 등장하는 장소 표기 변형")
    visual_anchors: List[str] = Field(default_factory=list, description="이미지 일관성을 위한 분위기/시간/날씨/구조 앵커(짧게)")


class LLMSceneTag(BaseModel):
    class LLMCharacterInstance(BaseModel):
        name: str
        variant: str = ""

    scene_id: int
    characters: List[str] = Field(default_factory=list, description="name_canonical 목록")
    places: List[str] = Field(default_factory=list, description="place name_canonical 목록")

    character_instances: List[LLMCharacterInstance] = Field(
        default_factory=list,
        description="예: [{'name':'서윤','variant':'아동'}]"
    )


class LLMScenePrompt(BaseModel):
    scene_id: int
    prompt: str = Field(default="", description="clip 이미지 생성을 위한 짧은 영어 프롬프트")


class LLMExtractionResult(BaseModel):
    characters: List[LLMCharacter] = Field(default_factory=list)
    places: List[LLMPlace] = Field(default_factory=list)
    scene_tags: List[LLMSceneTag] = Field(default_factory=list)
    scene_prompts: List[LLMScenePrompt] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list, description="불확실/가정/주의 사항(짧게)")


# --------- Extractor ---------
@dataclass
class LLMExtractorConfig:
    model: str = "gemini-2.5-flash"
    max_script_chars: int = 0  # 0 이하면 전체 대본 사용
    chunk_chars: int = 1000
    chunk_overlap_chars: int = 120
    max_scenes_per_chunk: int = 40
    temperature: float = 0.1


class LLMEntityExtractor:
    """
    Vertex 모드(환경변수 GOOGLE_GENAI_USE_VERTEXAI=True + ADC)에서 동작.
    Structured Output(JSON)로 캐릭터/장소/장면태깅 결과를 얻는다.
    """
    def __init__(self, cfg: Optional[LLMExtractorConfig] = None) -> None:
        self.cfg = cfg or LLMExtractorConfig()
        self.client = genai.Client()

    def _split_script_chunks(self, text: str) -> List[Tuple[int, int, str]]:
        src = text or ""
        if self.cfg.max_script_chars > 0:
            src = src[: self.cfg.max_script_chars]
        src = src.strip()
        if not src:
            return []

        chunk_target = max(300, int(self.cfg.chunk_chars))
        overlap_target = max(0, min(int(self.cfg.chunk_overlap_chars), chunk_target // 2))

        # 문장 경계 기준 분할: 마침표/물음표/느낌표/줄바꿈을 기준으로 최대한 의미 단위를 유지한다.
        spans: List[Tuple[int, int]] = []
        for m in re.finditer(r".+?(?:[.!?。！？]\s+|\n+|$)", src, flags=re.S):
            s0, s1 = m.span()
            if s1 > s0:
                spans.append((s0, s1))
        if not spans:
            return [(0, len(src), src)]

        out: List[Tuple[int, int, str]] = []
        i = 0
        n = len(spans)

        while i < n:
            c0 = spans[i][0]
            c1 = spans[i][1]
            j = i + 1

            while j < n:
                next_end = spans[j][1]
                if next_end - c0 > chunk_target and c1 > c0:
                    break
                c1 = next_end
                j += 1

            out.append((c0, c1, src[c0:c1]))
            if j >= n:
                break

            # 다음 청크 시작점: overlap_target 분량이 남도록 문장 단위로 되감기.
            back_chars = 0
            k = j - 1
            while k > i and back_chars < overlap_target:
                back_chars += spans[k][1] - spans[k][0]
                k -= 1
            i = max(i + 1, k + 1)

        return out

    def _build_scene_position_map(self, script_text: str, scenes: List[Dict[str, Any]]) -> Dict[int, Tuple[int, int]]:
        pos_map: Dict[int, Tuple[int, int]] = {}
        cursor = 0
        for s in scenes:
            sid = int(s["id"])
            stxt = str(s.get("text", ""))
            token = stxt[:40].strip()
            if not token:
                pos_map[sid] = (cursor, cursor)
                continue
            pos = script_text.find(token, cursor)
            if pos < 0:
                pos = script_text.find(token)
            if pos < 0:
                pos = cursor
            end = pos + len(stxt)
            pos_map[sid] = (pos, end)
            cursor = max(cursor, end)
        return pos_map

    def _select_chunk_scenes(
        self,
        chunk_start: int,
        chunk_end: int,
        scene_brief: List[Dict[str, Any]],
        scene_pos_map: Dict[int, Tuple[int, int]],
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        for sb in scene_brief:
            sid = int(sb["scene_id"])
            s0, s1 = scene_pos_map.get(sid, (0, 0))
            if (s0 < chunk_end and s1 > chunk_start) or (s0 == s1 and chunk_start <= s0 <= chunk_end):
                selected.append(sb)

        if not selected:
            center = (chunk_start + chunk_end) // 2
            scored: List[Tuple[int, Dict[str, Any]]] = []
            for sb in scene_brief:
                sid = int(sb["scene_id"])
                s0, s1 = scene_pos_map.get(sid, (0, 0))
                sm = (s0 + s1) // 2
                scored.append((abs(sm - center), sb))
            scored.sort(key=lambda x: x[0])
            selected = [sb for _, sb in scored[: max(1, min(5, len(scored)))]]

        return selected[: max(1, int(self.cfg.max_scenes_per_chunk))]

    def _build_system_prompt(self) -> str:
        return (
            "너는 한국어 대본에서 등장인물/장소를 추출하고 장면별로 태깅하는 분석기다. "
            "반드시 제공된 대본 내용에만 근거한다. 대본에 없는 인물/장소를 만들어내지 않는다. "
            "출력은 스키마에 맞는 JSON만 반환한다. 설명 문장, 코드블록, 여분 텍스트를 출력하지 않는다."
        )

    def _build_user_payload(
        self,
        *,
        era_profile: str,
        style_profile: str,
        script_chunk: str,
        scene_brief: List[Dict[str, Any]],
        seed_char_candidates: List[str],
        seed_place_candidates: List[str],
    ) -> Dict[str, Any]:
        return {
            "작업": "인물/장소 추출 및 정규화 + 장면별 태깅",
            "시대프로필": era_profile,
            "화풍프로필": style_profile,
            "대본(일부)": script_chunk,
            "장면목록": scene_brief,
            "규칙기반_인물후보": seed_char_candidates,
            "규칙기반_장소후보": seed_place_candidates,
            "요구사항": [
                "인물 name_canonical은 사람이 읽을 수 있는 대표 명칭(예: 설화, 강무, 도윤, 김도령). 단순 역할명(아씨, 도령, 마님, 아들, 딸, 어머니)만으로 끝내지 말고, 대본에 실명이 있으면 실명을 canonical로 삼는다.",
                "같은 인물이 실명과 역할명/호칭으로 함께 등장하면 하나의 canonical 인물로 합치고, 역할명/호칭은 aliases로 보낸다.",
                "실명이 전혀 없을 때만 역할명(예: 노승, 사또, 할멈)을 canonical로 사용한다.",
                "반복 등장하거나 서사에서 핵심 역할을 하는 동물(소/개/말 등)도 캐릭터로 추출한다.",
                "동물 캐릭터는 species를 반드시 명시한다(예: 소, 개, 말). 사람이면 species=인간.",
                "'누렁이'는 소/개 모두의 이름으로 쓰일 수 있으므로 이름만으로 종을 단정하지 않는다.",
                "누렁이의 species는 주변 문맥(황소/송아지/외양간/쟁기/발굽 vs 강아지/꼬리 흔들기/짖다/개집 등)으로 판단한다.",
                "대본이 소/황소 문맥을 지시하면 누렁이를 절대 개로 바꾸지 않는다.",
                "aliases에는 대본에서 확인된 다른 표기만 넣는다. 존칭/호칭/관계명은 가능한 alias로 흡수한다.",
                "장면 태깅(scene_tags)에서 characters/places는 반드시 name_canonical을 사용한다.",
                "scene_prompts에는 입력 장면목록의 scene_id마다 clip 이미지용 짧은 영어 프롬프트를 넣는다(한두 문장).",
                "scene_prompts는 텍스트/말풍선/자막/로고/워터마크 금지, 만화 패널 분할 금지, 장면의 감정/행동/구도를 포함한다.",
                "불확실하면 notes에 짧게 남긴다.",
                "각 인물에 대해 gender(남/여/불명)와 age_stage(유아/아동/청소년/청년/중년/노년/불명)를 가능한 범위에서 채운다.",
                "근거가 약하면 불명으로 두되, age_hint에 대본 근거 문구(있으면)를 넣는다.",
                "성장 서사가 명확한 주인공은 variants에 최소 2개(예: 아동, 청년/성인)를 넣는다.",
                "장면 태깅(scene_tags)에서 성장 단계가 구분되면 character_instances에 {'name':name_canonical,'variant':variants 중 하나}를 채운다.",
                "각 인물에 대해 context(궁중/민간/관아/사찰/장터/기타)를 추출한다. 단서가 없으면 민간으로 둔다.",
                "context가 '궁중'이면 court_role(왕/왕비/세자/후궁/궁녀/내관/문신/무관/호위 등)를 가능한 범위에서 채운다.",
                "각 인물에 대해 social_class(양반/중인/상민/천민/승려/무속/불명)와 wealth_level(부유/보통/빈곤/불명)을 추정한다(근거 없으면 불명).",
                "각 인물에 대해 wardrobe_tier를 T3(상류)/T2(중류)/T1(하류) 중 하나로 정한다. 몰락 양반 등은 양반이더라도 T1이 될 수 있다.",
                "각 인물에 대해 wardrobe_anchors를 3~6개 제시한다(복식/소품 중심, 짧게).",
                "우선순위: context가 '궁중'이면 social_class/wealth_level보다 궁중 복식 규격이 우선이다(예: 궁중 문신/무관 관복/관모, 궁녀 당의/치마 등).",
                "과장 금지: 금/보석 과다, 판타지 의상, 과도한 장식은 피한다. 시대감 유지.",
                "성장 서사가 있는 인물은 아예 다른 캐릭터로 쪼개지 말고 하나의 canonical 인물 아래 variants(예: 유아, 아동, 청년)로 유지한다.",
            ],
        }

    def _extract_one_chunk(
        self,
        *,
        era_profile: str,
        style_profile: str,
        script_chunk: str,
        scene_brief: List[Dict[str, Any]],
        seed_char_candidates: List[str],
        seed_place_candidates: List[str],
    ) -> Dict[str, Any]:
        system = self._build_system_prompt()
        user = self._build_user_payload(
            era_profile=era_profile,
            style_profile=style_profile,
            script_chunk=script_chunk,
            scene_brief=scene_brief,
            seed_char_candidates=seed_char_candidates,
            seed_place_candidates=seed_place_candidates,
        )

        resp = self.client.models.generate_content(
            model=self.cfg.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=system + "\n\n" + json.dumps(user, ensure_ascii=False))]
                ),
            ],
            config=types.GenerateContentConfig(
                temperature=self.cfg.temperature,
                response_mime_type="application/json",
                response_schema=LLMExtractionResult,
            ),
        )

        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("LLM 응답 텍스트(resp.text)가 비어 있습니다.")
        data = json.loads(text)
        validated = LLMExtractionResult.model_validate(data)
        return validated.model_dump()

    def _merge_unique_list(self, cur: List[str], new: List[str]) -> List[str]:
        out: List[str] = []
        seen: Set[str] = set()
        for x in (cur or []) + (new or []):
            s = str(x).strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def _prefer_scalar(self, cur: str, new: str, defaults: Set[str]) -> str:
        c = str(cur or "").strip()
        n = str(new or "").strip()
        if (not c) or (c in defaults):
            return n or c
        return c

    def extract(
        self,
        *,
        era_profile: str,
        style_profile: str,
        script_text: str,
        scenes: List[Dict[str, Any]],
        seed_char_candidates: List[str],
        seed_place_candidates: List[str],
    ) -> Dict[str, Any]:
        script_src = (script_text or "")
        if self.cfg.max_script_chars > 0:
            script_src = script_src[: self.cfg.max_script_chars]
        scene_brief = [{"scene_id": int(s["id"]), "text": str(s.get("text", ""))[:600]} for s in scenes]
        scene_pos_map = self._build_scene_position_map(script_src, scenes)
        chunks = self._split_script_chunks(script_src)

        merged_chars: Dict[str, Dict[str, Any]] = {}
        merged_places: Dict[str, Dict[str, Any]] = {}
        merged_scene_tags: Dict[int, Dict[str, Any]] = {}
        merged_scene_prompts: Dict[int, str] = {}
        merged_notes: List[str] = []

        for c0, c1, ctext in chunks:
            scoped_scenes = self._select_chunk_scenes(c0, c1, scene_brief, scene_pos_map)
            part = self._extract_one_chunk(
                era_profile=era_profile,
                style_profile=style_profile,
                script_chunk=ctext,
                scene_brief=scoped_scenes,
                seed_char_candidates=seed_char_candidates,
                seed_place_candidates=seed_place_candidates,
            )

            for c in part.get("characters", []) or []:
                name = str(c.get("name_canonical", "")).strip()
                if not name:
                    continue
                if name not in merged_chars:
                    merged_chars[name] = {
                        "name_canonical": name,
                        "aliases": [],
                        "species": "인간",
                        "role": "조연",
                        "traits": [],
                        "visual_anchors": [],
                        "gender": "불명",
                        "age_stage": "불명",
                        "age_hint": "",
                        "variants": [],
                        "context": "민간",
                        "court_role": "",
                        "social_class": "불명",
                        "wealth_level": "불명",
                        "wardrobe_tier": "T2",
                        "wardrobe_anchors": [],
                    }
                cur = merged_chars[name]
                cur["aliases"] = self._merge_unique_list(cur["aliases"], c.get("aliases", []))
                cur["traits"] = self._merge_unique_list(cur["traits"], c.get("traits", []))
                cur["visual_anchors"] = self._merge_unique_list(cur["visual_anchors"], c.get("visual_anchors", []))
                cur["variants"] = self._merge_unique_list(cur["variants"], c.get("variants", []))
                cur["wardrobe_anchors"] = self._merge_unique_list(cur["wardrobe_anchors"], c.get("wardrobe_anchors", []))
                cur["species"] = self._prefer_scalar(cur["species"], str(c.get("species", "")), {"", "인간"})
                cur["role"] = self._prefer_scalar(cur["role"], str(c.get("role", "")), {"", "조연"})
                cur["gender"] = self._prefer_scalar(cur["gender"], str(c.get("gender", "")), {"", "불명"})
                cur["age_stage"] = self._prefer_scalar(cur["age_stage"], str(c.get("age_stage", "")), {"", "불명"})
                cur["age_hint"] = self._prefer_scalar(cur["age_hint"], str(c.get("age_hint", "")), {""})
                cur["context"] = self._prefer_scalar(cur["context"], str(c.get("context", "")), {"", "민간"})
                cur["court_role"] = self._prefer_scalar(cur["court_role"], str(c.get("court_role", "")), {""})
                cur["social_class"] = self._prefer_scalar(cur["social_class"], str(c.get("social_class", "")), {"", "불명"})
                cur["wealth_level"] = self._prefer_scalar(cur["wealth_level"], str(c.get("wealth_level", "")), {"", "불명"})
                cur["wardrobe_tier"] = self._prefer_scalar(cur["wardrobe_tier"], str(c.get("wardrobe_tier", "")), {"", "T2"})

            for p in part.get("places", []) or []:
                name = str(p.get("name_canonical", "")).strip()
                if not name:
                    continue
                if name not in merged_places:
                    merged_places[name] = {
                        "name_canonical": name,
                        "aliases": [],
                        "visual_anchors": [],
                    }
                curp = merged_places[name]
                curp["aliases"] = self._merge_unique_list(curp["aliases"], p.get("aliases", []))
                curp["visual_anchors"] = self._merge_unique_list(curp["visual_anchors"], p.get("visual_anchors", []))

            for t in part.get("scene_tags", []) or []:
                try:
                    sid = int(t.get("scene_id"))
                except Exception:
                    continue
                if sid not in merged_scene_tags:
                    merged_scene_tags[sid] = {
                        "scene_id": sid,
                        "characters": set(),
                        "places": set(),
                        "character_instances": set(),
                    }
                curt = merged_scene_tags[sid]
                for nm in (t.get("characters", []) or []):
                    s = str(nm).strip()
                    if s:
                        curt["characters"].add(s)
                for nm in (t.get("places", []) or []):
                    s = str(nm).strip()
                    if s:
                        curt["places"].add(s)
                for it in (t.get("character_instances", []) or []):
                    nm = str(it.get("name", "")).strip()
                    var = str(it.get("variant", "")).strip()
                    if nm:
                        curt["character_instances"].add((nm, var))

            for sp in part.get("scene_prompts", []) or []:
                try:
                    sid = int(sp.get("scene_id"))
                except Exception:
                    continue
                prompt = str(sp.get("prompt", "")).strip()
                if not prompt:
                    continue
                prev = merged_scene_prompts.get(sid, "")
                # 정보량이 더 많은(긴) 프롬프트를 우선 사용
                if len(prompt) > len(prev):
                    merged_scene_prompts[sid] = prompt

            merged_notes = self._merge_unique_list(merged_notes, part.get("notes", []) or [])

        out_scene_tags: List[Dict[str, Any]] = []
        for sid in sorted(merged_scene_tags.keys()):
            item = merged_scene_tags[sid]
            inst = sorted(list(item["character_instances"]), key=lambda x: (x[0], x[1]))
            out_scene_tags.append({
                "scene_id": sid,
                "characters": sorted(list(item["characters"])),
                "places": sorted(list(item["places"])),
                "character_instances": [{"name": nm, "variant": var} for nm, var in inst],
            })

        return {
            "characters": list(merged_chars.values()),
            "places": list(merged_places.values()),
            "scene_tags": out_scene_tags,
            "scene_prompts": [
                {"scene_id": sid, "prompt": merged_scene_prompts[sid]}
                for sid in sorted(merged_scene_prompts.keys())
            ],
            "notes": merged_notes,
        }
