"""
Layouts
=======
Screens described as a list of blocks (header, text, list, ...) instead of
drawing code, so the MCP tools and the agent/digest scenes can compose their
own. Blocks stack top to bottom on the 250 x 122 canvas. Rendering reports
what didn't fit instead of failing, so a caller can shorten and retry.
"""

from typing import Annotated, Literal, Optional, Union

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field, TypeAdapter

MARGIN = 6          # left/right padding, same as the header text
GAP = 4             # space between blocks
HEADER_HEIGHT = 23  # same bar as ImageGenerator.draw_header
TEXT_SIZES = {"s": 14, "m": 18, "l": 24}


# ============================================================================
# Blocks
# ============================================================================

class HeaderBlock(BaseModel):
    """Black title bar with white text. Best as the first block."""
    type: Literal["header"] = "header"
    text: str = Field(max_length=60)
    right: Optional[str] = Field(None, max_length=20, description="Short text on the right side of the bar, e.g. a time")


class TextBlock(BaseModel):
    """Word-wrapped paragraph. Newlines start a new line."""
    type: Literal["text"] = "text"
    text: str = Field(max_length=500)
    size: Literal["s", "m", "l"] = Field("m", description="s = 14 px (~32 chars per line), m = 18 px (~24), l = 24 px (~17)")
    bold: bool = False
    align: Literal["left", "center", "right"] = "left"


class BigNumberBlock(BaseModel):
    """One large value (price, temperature, count) with an optional small label under it."""
    type: Literal["big_number"] = "big_number"
    value: str = Field(max_length=16)
    label: Optional[str] = Field(None, max_length=40)
    align: Literal["left", "center", "right"] = "left"


class ListBlock(BaseModel):
    """Bulleted list, each item wrapped with a hanging indent."""
    type: Literal["list"] = "list"
    items: list[str] = Field(max_length=12)
    size: Literal["s", "m"] = "s"


class KeyValue(BaseModel):
    key: str = Field(max_length=30)
    value: str = Field(max_length=30)


class KVBlock(BaseModel):
    """Rows with a label on the left and a value on the right (14 px)."""
    type: Literal["kv"] = "kv"
    rows: list[KeyValue] = Field(max_length=8)


class ProgressBlock(BaseModel):
    """Horizontal bar filled to value (0 to 1), with an optional label above it."""
    type: Literal["progress"] = "progress"
    value: float = Field(ge=0, le=1)
    label: Optional[str] = Field(None, max_length=30)


class DividerBlock(BaseModel):
    """Thin horizontal line."""
    type: Literal["divider"] = "divider"


class SpacerBlock(BaseModel):
    """Empty vertical space."""
    type: Literal["spacer"] = "spacer"
    height: int = Field(6, ge=1, le=60)


Block = Annotated[
    Union[HeaderBlock, TextBlock, BigNumberBlock, ListBlock, KVBlock,
          ProgressBlock, DividerBlock, SpacerBlock],
    Field(discriminator="type"),
]


# ============================================================================
# Text helpers (also used by ImageGenerator and the scenes)
# ============================================================================

# Glyph coverage per font file: {(path, char): supported}
_glyph_cache: dict[tuple[str, str], bool] = {}


def _has_glyph(font: ImageFont.FreeTypeFont, ch: str) -> bool:
    """Whether the font can draw ch (missing glyphs render as the same .notdef box)"""
    if ord(ch) < 0x80 or ch.isspace():
        return True
    path = getattr(font, "path", None)
    if path is None:
        return True
    key = (path, ch)
    if key not in _glyph_cache:
        def mask(c):
            m = font.getmask(c)
            return m.size, bytes(m)
        _glyph_cache[key] = mask(ch) != mask("\U0010FFFD")  # a private-use code point no font has
    return _glyph_cache[key]


def clean_text(text: str, font: ImageFont.FreeTypeFont) -> tuple[str, str]:
    """Drop characters the font can't draw (emoji and the like).
    Returns the cleaned text and the dropped characters."""
    kept, dropped = [], []
    for ch in text:
        (kept if _has_glyph(font, ch) else dropped).append(ch)
    cleaned = "".join(kept)
    if dropped:
        # "Done ✅ now" would otherwise keep a double space
        cleaned = "\n".join(" ".join(line.split()) for line in cleaned.split("\n"))
    return cleaned, "".join(dict.fromkeys(dropped))


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to max_width pixels. Newlines start a new line; words
    longer than a line are broken by character."""
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            test = f"{current} {word}".strip()
            if font.getlength(test) <= max_width:
                current = test
                continue
            if current:
                lines.append(current)
            # Break a word that doesn't fit on a line of its own
            while font.getlength(word) > max_width and len(word) > 1:
                cut = len(word) - 1
                while cut > 1 and font.getlength(word[:cut]) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    # Keep blank lines between paragraphs, not at the ends
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    return lines


def fit_line(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Shorten a single line with an ellipsis so it fits max_width"""
    if font.getlength(text) <= max_width:
        return text
    while text and font.getlength(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def line_box(font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """(offset, height) of a text line: draw at y - offset so the cap height
    starts at y; height runs to the bottom of the descenders"""
    left, top, right, bottom = font.getbbox("Hg")
    return top, bottom - top


# ============================================================================
# Renderer
# ============================================================================

class _Canvas:
    """Draws blocks one after another and keeps track of the space left"""

    def __init__(self, generator):
        self.generator = generator
        self.img = generator.create_blank()
        self.draw = ImageDraw.Draw(self.img)
        self.width = generator.width
        self.height = generator.height
        self.y = 0
        self.warnings: list[str] = []
        self.dropped_chars = ""

    def font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        return self.generator.get_font(size, "bold" if bold else "medium")

    def clean(self, text: str, font) -> str:
        text, dropped = clean_text(text, font)
        self.dropped_chars += dropped
        return text

    def text_x(self, text: str, font, align: str, left: int = MARGIN, right: Optional[int] = None) -> int:
        right = self.width - MARGIN if right is None else right
        width = font.getlength(text)
        if align == "center":
            return round(left + (right - left - width) / 2)
        if align == "right":
            return round(right - width)
        return left

    def lines_that_fit(self, count: int, pitch: int, height: int) -> int:
        """How many lines of a block still fit below self.y"""
        if count == 0:
            return 0
        space = self.height - self.y
        if space < height:
            return 0
        return min(count, 1 + (space - height) // pitch)


def _render_header(c: _Canvas, block: HeaderBlock, n: int) -> bool:
    if c.y + HEADER_HEIGHT > c.height:
        return False
    font = c.generator.get_font(14, "bold")
    small = c.generator.get_font(12, "mono")
    c.draw.rectangle([0, c.y, c.width, c.y + HEADER_HEIGHT - 1], fill=0)

    right_width = 0
    if block.right:
        right = c.clean(block.right, small)
        right_width = small.getlength(right) + 8
        offset, h = line_box(small)
        c.draw.text((c.width - MARGIN - small.getlength(right), c.y + (HEADER_HEIGHT - h) // 2 - offset),
                    right, font=small, fill=255)
    title = fit_line(c.clean(block.text, font), font, c.width - 2 * MARGIN - right_width)
    c.draw.text((MARGIN, c.y + 3), title, font=font, fill=255)
    c.y += HEADER_HEIGHT
    return True


def _draw_lines(c: _Canvas, lines: list[str], font, align: str, n: int, label: str,
                left: int = MARGIN, bullet: bool = False) -> bool:
    """Draw wrapped lines, cutting the block (with a warning) where the canvas ends"""
    offset, height = line_box(font)
    pitch = height + 3
    fits = c.lines_that_fit(len(lines), pitch, height)
    if fits == 0:
        return False
    if fits < len(lines):
        c.warnings.append(f"Block {n} ({label}): {len(lines) - fits} of {len(lines)} lines cut off")
        lines = lines[:fits]
        lines[-1] = fit_line(lines[-1] + "…", font, c.width - MARGIN - left)
    for i, line in enumerate(lines):
        if bullet and i == 0:
            c.draw.text((MARGIN, c.y - offset), "•", font=font, fill=0)
        c.draw.text((c.text_x(line, font, align, left=left), c.y - offset), line, font=font, fill=0)
        c.y += pitch
    c.y -= 3
    return True


def _render_text(c: _Canvas, block: TextBlock, n: int) -> bool:
    font = c.font(TEXT_SIZES[block.size], block.bold)
    lines = wrap_text(c.clean(block.text, font), font, c.width - 2 * MARGIN)
    return _draw_lines(c, lines, font, block.align, n, "text") if lines else True


def _render_list(c: _Canvas, block: ListBlock, n: int) -> bool:
    font = c.font(TEXT_SIZES[block.size])
    indent = MARGIN + round(font.getlength("• "))
    items = [wrap_text(c.clean(item, font), font, c.width - MARGIN - indent) for item in block.items]
    items = [lines for lines in items if lines]
    for i, lines in enumerate(items):
        if i:
            c.y += 3
        if not _draw_lines(c, lines, font, "left", n, "list", left=indent, bullet=True):
            if i == 0:
                return False
            c.y -= 3
            c.warnings.append(f"Block {n} (list): {len(items) - i} of {len(items)} items didn't fit")
            break
    return True


def _render_big_number(c: _Canvas, block: BigNumberBlock, n: int) -> bool:
    label_font = c.font(14)
    label = c.clean(block.label, label_font) if block.label else ""
    value = c.clean(block.value, c.generator.get_font(48, "bold"))
    # Largest size that fits the width
    for size in (48, 42, 36, 32, 28, 24):
        font = c.generator.get_font(size, "bold")
        if font.getlength(value) <= c.width - 2 * MARGIN:
            break
    offset, height = line_box(font)
    total = height + (3 + line_box(label_font)[1] if label else 0)
    if c.y + total > c.height:
        return False
    c.draw.text((c.text_x(value, font, block.align), c.y - offset), value, font=font, fill=0)
    c.y += height
    if label:
        c.y += 3
        label = fit_line(label, label_font, c.width - 2 * MARGIN)
        l_offset, l_height = line_box(label_font)
        c.draw.text((c.text_x(label, label_font, block.align), c.y - l_offset), label, font=label_font, fill=0)
        c.y += l_height
    return True


def _render_kv(c: _Canvas, block: KVBlock, n: int) -> bool:
    key_font = c.font(14)
    value_font = c.font(14, bold=True)
    offset, height = line_box(key_font)
    pitch = height + 3
    fits = c.lines_that_fit(len(block.rows), pitch, height)
    if fits == 0 and block.rows:
        return False
    if fits < len(block.rows):
        c.warnings.append(f"Block {n} (kv): {len(block.rows) - fits} of {len(block.rows)} rows didn't fit")
    for row in block.rows[:fits]:
        value = fit_line(c.clean(row.value, value_font), value_font, (c.width - 2 * MARGIN) // 2)
        value_width = value_font.getlength(value)
        key = fit_line(c.clean(row.key, key_font), key_font, c.width - 2 * MARGIN - value_width - 8)
        c.draw.text((MARGIN, c.y - offset), key, font=key_font, fill=0)
        c.draw.text((c.width - MARGIN - value_width, c.y - offset), value, font=value_font, fill=0)
        c.y += pitch
    c.y -= 3
    return True


def _render_progress(c: _Canvas, block: ProgressBlock, n: int) -> bool:
    font = c.font(14)
    offset, height = line_box(font)
    bar = 10
    total = (height + 3 if block.label else 0) + bar
    if c.y + total > c.height:
        return False
    if block.label:
        label = fit_line(c.clean(block.label, font), font, c.width - 2 * MARGIN - 40)
        percent = f"{round(block.value * 100)}%"
        c.draw.text((MARGIN, c.y - offset), label, font=font, fill=0)
        c.draw.text((c.width - MARGIN - font.getlength(percent), c.y - offset), percent, font=font, fill=0)
        c.y += height + 3
    right = c.width - MARGIN
    c.draw.rectangle([MARGIN, c.y, right, c.y + bar - 1], outline=0, width=1)
    fill_to = MARGIN + round((right - MARGIN) * block.value)
    if fill_to > MARGIN:
        c.draw.rectangle([MARGIN, c.y, fill_to, c.y + bar - 1], fill=0)
    c.y += bar
    return True


def _render_divider(c: _Canvas, block: DividerBlock, n: int) -> bool:
    if c.y + 1 > c.height:
        return False
    c.draw.line([(MARGIN, c.y), (c.width - MARGIN, c.y)], fill=0, width=1)
    c.y += 1
    return True


def _render_spacer(c: _Canvas, block: SpacerBlock, n: int) -> bool:
    c.y = min(c.height, c.y + block.height)
    return True


_RENDERERS = {
    "header": _render_header,
    "text": _render_text,
    "big_number": _render_big_number,
    "list": _render_list,
    "kv": _render_kv,
    "progress": _render_progress,
    "divider": _render_divider,
    "spacer": _render_spacer,
}


def render_layout(blocks: list, generator) -> tuple[Image.Image, list[str]]:
    """Render blocks (models or plain dicts) top to bottom.
    Returns the image and warnings about anything that didn't fit."""
    blocks = [parse_block(b) for b in blocks]
    c = _Canvas(generator)

    for i, block in enumerate(blocks):
        n = i + 1
        # A header at the top sits flush with the edge, everything else gets a gap
        if c.y or block.type != "header":
            c.y += GAP
        if not _RENDERERS[block.type](c, block, n):
            rest = len(blocks) - i
            c.warnings.append(
                f"Blocks {n}-{len(blocks)} didn't fit" if rest > 1 else f"Block {n} ({block.type}) didn't fit"
            )
            break

    if c.dropped_chars:
        c.warnings.append(f"Removed characters the font can't draw: {c.dropped_chars}")
    return c.img, c.warnings


def layout_name(blocks: list) -> str:
    """A layout's title for the web UI: the text of its first header"""
    return next((b.text for b in map(parse_block, blocks) if b.type == "header"), "Layout")


_block_adapter = TypeAdapter(Block)


def parse_block(block) -> BaseModel:
    """Validate a dict (e.g. loaded from JSON) as a block"""
    if isinstance(block, BaseModel):
        return block
    return _block_adapter.validate_python(block)
