# yadam/nlp/tagger.py
from __future__ import annotations
from typing import Dict, List
from yadam.nlp.scene_split import Scene
from yadam.nlp.entity_extract import Character, Place


def tag_scene(scene: Scene, characters: List[Character], places: List[Place]) -> Dict[str, List[str]]:
    text = scene.text
    scene_chars: List[str] = []
    scene_places: List[str] = []

    for c in characters:
        names = [c.name] + list(getattr(c, "aliases", []) or [])
        if any(n and n in text for n in names):
            scene_chars.append(c.char_id)

    for p in places:
        names = [p.name] + list(getattr(p, "aliases", []) or [])
        if any(n and n in text for n in names):
            scene_places.append(p.place_id)

    # 직접 언급이 없으면 빈 배열(추후: 직전 장면 상속 옵션 등 추가 가능)
    return {"characters": scene_chars, "places": scene_places}
