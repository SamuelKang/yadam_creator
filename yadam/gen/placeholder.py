# yadam/gen/placeholder.py
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from pathlib import Path
from typing import Optional, List
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter


def make_error_image_bytes(text: str, width: int = 1280, height: int = 720) -> bytes:
    img = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # 폰트는 시스템 환경마다 다르므로 기본 폰트로
    msg = text[:800]
    draw.text((40, 40), msg, fill=(240, 240, 240))

    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def compose_clip_from_reference_images(
    reference_image_paths: List[str],
    width: int = 1280,
    height: int = 720,
    one_subject_side: str = "center",
    focus_char_index: int = -1,
    fallback_place_path: Optional[str] = None,
) -> bytes:
    """
    저비용 대체 모드:
    - place 이미지를 배경으로 사용하고,
    - character 이미지를 카드 형태로 오버레이해 clip 이미지를 합성한다.
    - 생성 API 호출 없이 로컬 합성만 수행한다.
    """
    valid_paths: List[Path] = []
    for raw in reference_image_paths or []:
        p = Path(str(raw))
        if p.exists() and p.is_file():
            valid_paths.append(p)
    if (not valid_paths) and fallback_place_path:
        fp = Path(str(fallback_place_path))
        if fp.exists() and fp.is_file():
            valid_paths.append(fp)

    canvas = Image.new("RGB", (width, height), color=(64, 68, 74))

    if not valid_paths:
        import io
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=88)
        return buf.getvalue()

    def _is_place_path(p: Path) -> bool:
        s = str(p).lower()
        return ("/places/" in s) or ("place_" in s)

    place_path: Optional[Path] = None
    for p in valid_paths:
        if _is_place_path(p):
            place_path = p
            break
    if place_path is None:
        place_path = _fallback_place_from_story(valid_paths)

    char_paths = [p for p in valid_paths if p != place_path][:3]

    if place_path is not None:
        try:
            bg = Image.open(place_path).convert("RGB")
        except Exception:
            bg = Image.new("RGB", (width, height), color=(96, 96, 96))
        bg = ImageOps.fit(bg, (width, height), method=Image.Resampling.LANCZOS)
        bg = ImageEnhance.Color(bg).enhance(0.92)
        bg = ImageEnhance.Brightness(bg).enhance(0.94)
    else:
        # place reference가 없으면 캐릭터를 배경으로 쓰지 않고
        # 중립 그라데이션 배경을 사용한다.
        bg = Image.new("RGB", (width, height), color=(112, 114, 118))
        g = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        for y in range(height):
            a = int(90 * (y / max(1, height - 1)))
            gd.line([(0, y), (width, y)], fill=(38, 42, 48, a))
        bg = bg.convert("RGBA")
        bg.alpha_composite(g, (0, 0))
        bg = bg.convert("RGB")
    canvas.paste(bg, (0, 0))

    # 카드가 잘 읽히도록 하단에 얕은 비네팅을 깐다.
    grad_h = int(height * 0.34)
    shade = Image.new("RGBA", (width, grad_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shade)
    for y in range(grad_h):
        alpha = int(170 * (y / max(1, grad_h - 1)))
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(shade, (0, height - grad_h))

    if char_paths:
        one_subject = (len(char_paths) == 1)
        many = len(char_paths)
        if one_subject:
            # 단일 화자: 상반신 중심으로 크게 보여주되 전신 합성은 피한다.
            card_w = width
            card_h = height
            gap = 0
            left = 0
            top = 0
        elif many == 2:
            card_w = int(width * 0.38)
            card_h = height
            gap = int(width * 0.02)
            left = int(width * 0.03)
            top = 0
        else:
            # 3인 구도: 좌/중/우 배치로 모두 등장시킨다.
            card_w = int(width * 0.28)
            card_h = height
            gap = int(width * 0.01)
            total_w = card_w * many + gap * (many - 1)
            left = max(0, (width - total_w) // 2)
            top = 0

        for idx, cp in enumerate(char_paths):
            try:
                cimg_raw = Image.open(cp)
            except Exception:
                continue
            has_alpha = "A" in (cimg_raw.getbands() or ())
            if has_alpha:
                cimg = cimg_raw.convert("RGBA")
                cimg = _crop_to_upper_body(cimg)
                base_scale = min(card_w / max(1, cimg.width), card_h / max(1, cimg.height))
                is_focused = (not one_subject) and (int(focus_char_index) == idx)
                scale = (base_scale * 1.55) if one_subject else (base_scale * 1.22)
                if is_focused:
                    scale *= 1.22
                nw = max(1, int(cimg.width * scale))
                nh = max(1, int(cimg.height * scale))
                resized = cimg.resize((nw, nh), Image.Resampling.LANCZOS)
                resized = _limit_subject_height(resized, card_h, one_subject=one_subject, focused=is_focused)
                nw, nh = resized.size
                card_rgba = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
                ox = (card_w - nw) // 2
                oy = card_h - nh + int(card_h * (0.18 if one_subject else 0.10))
                if one_subject:
                    abox = resized.split()[-1].getbbox()
                    desired_cx = int(width * 0.50)
                    side = str(one_subject_side or "center").lower()
                    if side == "left":
                        desired_cx = int(width * 0.34)
                    elif side == "right":
                        desired_cx = int(width * 0.66)
                    if abox is not None:
                        obj_cx = int((abox[0] + abox[2]) / 2)
                        ox = desired_cx - obj_cx
                        desired_head_y = int(height * 0.30)
                        oy = desired_head_y - int(abox[1])
                    else:
                        ox = desired_cx - (nw // 2)
                card_rgba.alpha_composite(resized, (ox, oy))
                rgb = card_rgba.convert("RGB")
                rgb = ImageEnhance.Color(rgb).enhance(0.96)
                rgb = ImageEnhance.Brightness(rgb).enhance(0.98)
                r, g, b = rgb.split()
                a = card_rgba.split()[-1]
                a = a.point(lambda v: 0 if v < 18 else v)
                card_rgba = Image.merge("RGBA", (r, g, b, a))
            else:
                cimg = cimg_raw.convert("RGB")
                cimg = _crop_to_upper_body(_white_to_alpha(cimg)).convert("RGB")
                base_scale = min(card_w / max(1, cimg.width), card_h / max(1, cimg.height))
                is_focused = (not one_subject) and (int(focus_char_index) == idx)
                scale = (base_scale * 1.55) if one_subject else (base_scale * 1.22)
                if is_focused:
                    scale *= 1.22
                nw = max(1, int(cimg.width * scale))
                nh = max(1, int(cimg.height * scale))
                resized = cimg.resize((nw, nh), Image.Resampling.LANCZOS)
                resized = _limit_subject_height(
                    resized.convert("RGBA"), card_h, one_subject=one_subject, focused=is_focused
                ).convert("RGB")
                nw, nh = resized.size
                card = Image.new("RGB", (card_w, card_h), (255, 255, 255))
                ox = (card_w - nw) // 2
                oy = card_h - nh + int(card_h * (0.18 if one_subject else 0.10))
                if one_subject:
                    side = str(one_subject_side or "center").lower()
                    if side == "left":
                        ox = int(width * 0.34) - (nw // 2)
                    elif side == "right":
                        ox = int(width * 0.66) - (nw // 2)
                card.paste(resized, (ox, oy))
                card = ImageEnhance.Color(card).enhance(0.96)
                card = ImageEnhance.Brightness(card).enhance(0.98)
                card_rgba = _white_to_alpha(card)

            x = left + idx * (card_w + gap)
            y = top

            # 요청사항: 흰 배경 투명 처리만 적용한 컷아웃을 그대로 합성
            canvas.alpha_composite(card_rgba, (x, y))

    out = canvas.convert("RGB")
    import io
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _white_to_alpha(src: Image.Image) -> Image.Image:
    """
    흰 배경 제거(near-white keying):
    - 밝고 채도가 낮은 픽셀은 투명화
    - 가장자리는 blur로 부드럽게
    """
    rgba = src.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    # 1) 후보 배경 픽셀(near-white, low-chroma) 판정
    # 2) 이미지 외곽에서 flood fill로 연결된 후보만 "배경"으로 확정
    #    => 인물 내부의 밝은 옷/하이라이트가 투명해지는 문제를 줄인다.
    cand = [[False] * w for _ in range(h)]
    for y in range(h):
        row = cand[y]
        for x in range(w):
            r, g, b, _a = px[x, y]
            vmax = max(r, g, b)
            vmin = min(r, g, b)
            chroma = vmax - vmin
            bright = (r + g + b) / 3.0
            row[x] = bool((bright >= 236 and chroma <= 18) or (bright >= 246 and chroma <= 26))

    bg = [[False] * w for _ in range(h)]
    q = deque()

    def _push_if_candidate(xx: int, yy: int) -> None:
        if 0 <= xx < w and 0 <= yy < h and cand[yy][xx] and not bg[yy][xx]:
            bg[yy][xx] = True
            q.append((xx, yy))

    for x in range(w):
        _push_if_candidate(x, 0)
        _push_if_candidate(x, h - 1)
    for y in range(h):
        _push_if_candidate(0, y)
        _push_if_candidate(w - 1, y)

    while q:
        x, y = q.popleft()
        _push_if_candidate(x - 1, y)
        _push_if_candidate(x + 1, y)
        _push_if_candidate(x, y - 1)
        _push_if_candidate(x, y + 1)

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            vmax = max(r, g, b)
            vmin = min(r, g, b)
            chroma = vmax - vmin
            bright = (r + g + b) / 3.0

            if bg[y][x]:
                alpha = 0
            else:
                # 배경으로 확정되지 않은 밝은 의복/두건/피부는 불투명 유지
                alpha = 255
            px[x, y] = (r, g, b, min(a, alpha))

    # 내부에 고립된 아주 작은 투명 홀(옷/피부 관통)을 메운다.
    seen = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if seen[y][x]:
                continue
            _r, _g, _b, a0 = px[x, y]
            if a0 > 10:
                seen[y][x] = True
                continue
            q = deque([(x, y)])
            seen[y][x] = True
            comp = []
            touches_border = False
            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                if cx == 0 or cy == 0 or cx == w - 1 or cy == h - 1:
                    touches_border = True
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if not (0 <= nx < w and 0 <= ny < h):
                        continue
                    if seen[ny][nx]:
                        continue
                    _r2, _g2, _b2, a2 = px[nx, ny]
                    if a2 <= 10:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if (not touches_border) and (len(comp) <= 96):
                for cx, cy in comp:
                    r2, g2, b2, _a2 = px[cx, cy]
                    px[cx, cy] = (r2, g2, b2, 255)

    # 가장자리 톱니 완화
    r, g, b, a = rgba.split()
    a = a.filter(ImageFilter.GaussianBlur(radius=0.9))
    return Image.merge("RGBA", (r, g, b, a))


def _fallback_place_from_story(valid_paths: List[Path]) -> Optional[Path]:
    """
    scene refs에 place가 없을 때, 같은 story 폴더의 places/place_001* 를 우선 배경으로 사용.
    """
    if not valid_paths:
        return None
    anchor = valid_paths[0]
    parts = list(anchor.parts)
    if "work" not in parts:
        return None
    try:
        i = parts.index("work")
        work_story_dir = Path(*parts[: i + 2])
    except Exception:
        return None
    places_dir = work_story_dir / "places"
    if not places_dir.exists():
        return None
    cands = sorted(places_dir.glob("place_001*.jpg"))
    if not cands:
        cands = sorted(places_dir.glob("*.jpg"))
    return cands[0] if cands else None


def _crop_to_upper_body(src_rgba: Image.Image) -> Image.Image:
    """
    전신 합성으로 인한 부자연스러운 바닥/소품 관통을 줄이기 위해
    인물의 상반신 위주(머리~허벅지 상단)로 컷한다.
    """
    rgba = src_rgba.convert("RGBA")
    abox = rgba.split()[-1].getbbox()
    if abox is None:
        return rgba
    x0, y0, x1, y1 = abox
    h = max(1, y1 - y0)
    cut_bottom = y0 + int(h * 0.62)
    cut_bottom = max(y0 + 1, min(y1, cut_bottom))
    pad_x = int((x1 - x0) * 0.08)
    nx0 = max(0, x0 - pad_x)
    nx1 = min(rgba.width, x1 + pad_x)
    return rgba.crop((nx0, y0, nx1, cut_bottom))


def _limit_subject_height(
    src_rgba: Image.Image, card_h: int, one_subject: bool, focused: bool = False
) -> Image.Image:
    """
    인물 과대 확대를 방지:
    - 단일 화자: 객체 높이(card_h 대비) 최대 0.78
    - 다인 장면: 객체 높이(card_h 대비) 최대 0.64
    """
    rgba = src_rgba.convert("RGBA")
    abox = rgba.split()[-1].getbbox()
    if not abox:
        return rgba
    obj_h = max(1, abox[3] - abox[1])
    ratio = obj_h / max(1, card_h)
    if one_subject:
        max_ratio = 0.78
    else:
        # 다인 장면에서도 화자는 체감 확대가 보이도록 상한을 별도로 높인다.
        max_ratio = 0.82 if focused else 0.58
    if ratio <= max_ratio:
        return rgba
    scale = max_ratio / ratio
    nw = max(1, int(rgba.width * scale))
    nh = max(1, int(rgba.height * scale))
    return rgba.resize((nw, nh), Image.Resampling.LANCZOS)


def _prune_isolated_alpha_fragments(src_rgba: Image.Image, alpha_thr: int = 18) -> Image.Image:
    """
    컷아웃 후 남는 분리된 미세 조각(흰 점/삼각형)을 제거한다.
    - alpha_thr 초과 픽셀의 연결요소를 계산
    - 가장 큰 요소(주 피사체)와 충분히 큰 보조 요소만 유지
    """
    rgba = src_rgba.convert("RGBA")
    w, h = rgba.size
    a = rgba.split()[-1]
    apx = a.load()
    seen = [[False] * w for _ in range(h)]
    comps = []

    for y in range(h):
        for x in range(w):
            if seen[y][x]:
                continue
            if apx[x, y] <= alpha_thr:
                seen[y][x] = True
                continue
            q = deque([(x, y)])
            seen[y][x] = True
            comp = []
            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if not (0 <= nx < w and 0 <= ny < h):
                        continue
                    if seen[ny][nx]:
                        continue
                    if apx[nx, ny] > alpha_thr:
                        seen[ny][nx] = True
                        q.append((nx, ny))
                    else:
                        seen[ny][nx] = True
            comps.append(comp)

    if not comps:
        return rgba

    comps.sort(key=len, reverse=True)
    largest = len(comps[0])
    keep = [comps[0]]
    for comp in comps[1:]:
        # 주 피사체 대비 충분히 큰 보조 파츠만 유지
        if len(comp) >= max(1800, int(largest * 0.08)):
            keep.append(comp)

    keep_mask = [[False] * w for _ in range(h)]
    for comp in keep:
        for x, y in comp:
            keep_mask[y][x] = True

    px = rgba.load()
    for y in range(h):
        for x in range(w):
            r, g, b, av = px[x, y]
            if av > alpha_thr and (not keep_mask[y][x]):
                px[x, y] = (r, g, b, 0)
    return rgba


def export_character_cutout_png(src_path: str, out_path: str) -> str:
    """
    캐릭터 JPG/PNG에서 흰 배경을 제거한 알파 PNG를 생성한다.
    반환값은 생성된 out_path 문자열.
    """
    src = Path(src_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(src).convert("RGB")
    rgba = _white_to_alpha(img)
    rgba = _prune_isolated_alpha_fragments(rgba, alpha_thr=18)
    r, g, b, a = rgba.split()
    a = a.point(lambda v: 0 if v < 22 else v)
    rgba = Image.merge("RGBA", (r, g, b, a))

    tmp = out.with_suffix(out.suffix + ".tmp")
    rgba.save(tmp, format="PNG", optimize=True)
    tmp.replace(out)
    return str(out)
