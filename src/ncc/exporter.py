from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .images import _load_font
from .models import CandidateImage, CandidateSet, ExportRecord, LetterBalloon, LetteringLayout, Storyboard
from .storage import safe_project_path


PANEL_WIDTH = 1080
PANEL_HEIGHT = 1440


def build_default_lettering(project_id: str, storyboard: Storyboard, candidates: CandidateSet) -> LetteringLayout:
    selection_hash = selection_revision_hash(candidates)
    balloons: list[LetterBalloon] = []
    for panel in storyboard.panels:
        if panel.caption:
            balloons.append(
                LetterBalloon(
                    balloon_id=f"{panel.panel_id}-caption",
                    panel_id=panel.panel_id,
                    text=panel.caption,
                    x=64,
                    y=54,
                    width=620,
                    height=96,
                    tail_direction="none",
                    kind="caption",
                )
            )
        if panel.draft_dialogue:
            balloons.append(
                LetterBalloon(
                    balloon_id=f"{panel.panel_id}-speech",
                    panel_id=panel.panel_id,
                    text=panel.draft_dialogue,
                    x=120 if panel.order % 2 else 470,
                    y=210,
                    width=440,
                    height=150,
                    tail_direction="down",
                    kind="speech",
                )
            )
    return LetteringLayout(
        project_id=project_id,
        panel_width=PANEL_WIDTH,
        balloons=balloons,
        source_selection_hash=selection_hash,
    )


def export_vertical_png(
    project_id: str,
    project_dir: Path,
    storyboard: Storyboard,
    candidates: CandidateSet,
    lettering: LetteringLayout,
    filename: str = "webtoon_mock_gold_path.png",
) -> ExportRecord:
    current_hash = selection_revision_hash(candidates)
    if lettering.source_selection_hash != current_hash:
        raise ValueError("lettering selection hash is stale; refresh lettering before export")
    selected = _selected_by_panel(candidates)
    panels: list[Image.Image] = []
    for panel in storyboard.panels:
        candidate = selected.get(panel.panel_id)
        if candidate is None:
            raise ValueError(f"panel {panel.panel_id} has no selected candidate")
        image_path = safe_project_path(project_dir, candidate.image_path)
        with Image.open(image_path) as image:
            panel_image = image.convert("RGB").resize((PANEL_WIDTH, PANEL_HEIGHT))
        _draw_lettering(panel_image, [b for b in lettering.balloons if b.panel_id == panel.panel_id])
        panels.append(panel_image)

    strip = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT * len(panels)), (255, 255, 255))
    for index, panel_image in enumerate(panels):
        strip.paste(panel_image, (0, index * PANEL_HEIGHT))

    output_path = safe_project_path(project_dir, f"exports/{filename}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(output_path, "PNG")
    return ExportRecord(
        project_id=project_id,
        export_path=str(output_path.relative_to(project_dir.resolve())),
        width=strip.width,
        height=strip.height,
        source_selection_hash=lettering.source_selection_hash,
    )


def selection_revision_hash(candidates: CandidateSet) -> str:
    selected = sorted(
        f"{candidate.panel_id}:{candidate.candidate_id}:{candidate.seed}"
        for candidate in candidates.candidates
        if candidate.selected
    )
    import hashlib

    return hashlib.sha256("|".join(selected).encode("utf-8")).hexdigest()


def _selected_by_panel(candidates: CandidateSet) -> dict[str, CandidateImage]:
    selected: dict[str, CandidateImage] = {}
    for candidate in candidates.candidates:
        if candidate.selected:
            selected[candidate.panel_id] = candidate
    return selected


def _draw_lettering(image: Image.Image, balloons: list[LetterBalloon]) -> None:
    draw = ImageDraw.Draw(image)
    font = _load_font(42)
    caption_font = _load_font(36)
    for balloon in balloons:
        box = (balloon.x, balloon.y, balloon.x + balloon.width, balloon.y + balloon.height)
        if balloon.kind == "caption":
            draw.rounded_rectangle(box, radius=10, fill=(20, 20, 24), outline=(255, 255, 255), width=3)
            _draw_wrapped_text(draw, balloon.text, box, caption_font, fill=(255, 255, 255))
        else:
            draw.ellipse(box, fill=(255, 255, 255), outline=(25, 25, 25), width=4)
            _draw_tail(draw, balloon)
            _draw_wrapped_text(draw, balloon.text, box, font, fill=(20, 20, 20))


def _draw_tail(draw: ImageDraw.ImageDraw, balloon: LetterBalloon) -> None:
    if balloon.tail_direction == "none":
        return
    cx = balloon.x + balloon.width // 2
    bottom = balloon.y + balloon.height
    draw.polygon(
        [(cx - 24, bottom - 18), (cx + 34, bottom - 10), (cx + 8, bottom + 70)],
        fill=(255, 255, 255),
        outline=(25, 25, 25),
    )


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    max_width = x2 - x1 - 56
    lines = _wrap_korean_text(draw, text, font, max_width)
    line_height = max(42, font.size + 8 if hasattr(font, "size") else 42)
    total_height = line_height * len(lines)
    y = y1 + max(16, (y2 - y1 - total_height) // 2)
    for line in lines:
        text_box = draw.textbbox((0, 0), line, font=font)
        text_width = text_box[2] - text_box[0]
        draw.text((x1 + (x2 - x1 - text_width) // 2, y), line, fill=fill, font=font)
        y += line_height


def _wrap_korean_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) == 1 and draw.textbbox((0, 0), lines[0], font=font)[2] > max_width:
        return _wrap_by_character(draw, lines[0], font, max_width)
    return lines


def _wrap_by_character(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines
