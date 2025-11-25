import os
import io
import logging
from typing import Tuple, Union, Literal, Optional, List, Dict
from PIL import Image, ImageDraw, ImageFont

try:
    from pilmoji import Pilmoji
    PILMOJI_AVAILABLE = True
except ImportError:
    PILMOJI_AVAILABLE = False

logger = logging.getLogger(__name__)

Align = Literal["left", "center", "right"]
VAlign = Literal["top", "middle", "bottom"]

class ImageProcessor:
    def __init__(self):
        pass

    @staticmethod
    def compress_image(image: Image.Image, max_width: int = 1200, max_height: int = 800, resize_ratio: float = 0.7) -> Image.Image:
        """Compress image size."""
        width, height = image.size
        new_width = int(width * resize_ratio)
        new_height = int(height * resize_ratio)

        if new_width > max_width:
            ratio = max_width / new_width
            new_width, new_height = max_width, int(new_height * ratio)

        if new_height > max_height:
            ratio = max_height / new_height
            new_height, new_width = max_height, int(new_width * ratio)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    @staticmethod
    def paste_image(
        image_source: Union[str, Image.Image],
        top_left: Tuple[int, int],
        bottom_right: Tuple[int, int],
        content_image: Image.Image,
        align: Align = "center",
        valign: VAlign = "middle",
        padding: int = 0,
        allow_upscale: bool = False,
        image_overlay: Union[str, Image.Image, None] = None,
        max_image_size: Tuple[Optional[int], Optional[int]] = (None, None),
        role_name: str = "unknown",
        text_configs_dict: Optional[Dict] = None,
        font_path: Optional[str] = None
    ) -> bytes:
        """
        Paste an image into a specified rectangle, scaling to fit.
        """
        if not isinstance(content_image, Image.Image):
            raise TypeError("content_image must be PIL.Image.Image")

        if isinstance(image_source, Image.Image):
            img = image_source.copy()
        else:
            img = Image.open(image_source).convert("RGBA")

        # Load overlay if provided
        img_overlay = None
        if image_overlay is not None:
            if isinstance(image_overlay, Image.Image):
                img_overlay = image_overlay.copy()
            elif isinstance(image_overlay, str) and os.path.isfile(image_overlay):
                img_overlay = Image.open(image_overlay).convert("RGBA")

        x1, y1 = top_left
        x2, y2 = bottom_right
        if not (x2 > x1 and y2 > y1):
            raise ValueError("Invalid paste area.")

        region_w = max(1, (x2 - x1) - 2 * padding)
        region_h = max(1, (y2 - y1) - 2 * padding)

        cw, ch = content_image.size
        if cw <= 0 or ch <= 0:
            raise ValueError("Invalid content_image size.")

        # Calculate scale
        scale_w = region_w / cw
        scale_h = region_h / ch
        scale = min(scale_w, scale_h)

        if not allow_upscale:
            scale = min(1.0, scale)
        
        max_width, max_height = max_image_size
        if max_width is not None:
            scale = min(scale, max_width / cw)
        if max_height is not None:
            scale = min(scale, max_height / ch)

        new_w = max(1, int(round(cw * scale)))
        new_h = max(1, int(round(ch * scale)))

        resized = content_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Calculate position
        if align == "left":
            paste_x = x1 + padding
        elif align == "right":
            paste_x = x2 - padding - new_w
        else: # center
            paste_x = x1 + padding + (region_w - new_w) // 2

        if valign == "top":
            paste_y = y1 + padding
        elif valign == "bottom":
            paste_y = y2 - padding - new_h
        else: # middle
            paste_y = y1 + padding + (region_h - new_h) // 2

        # Paste content
        if resized.mode == 'RGBA':
            img.paste(resized, (paste_x, paste_y), resized)
        else:
            img.paste(resized, (paste_x, paste_y))

        # Paste overlay
        if img_overlay:
            img.paste(img_overlay, (0, 0), img_overlay)

        # Draw character name if configured
        if text_configs_dict and role_name in text_configs_dict:
            ImageProcessor._draw_character_name(img, role_name, text_configs_dict, font_path)

        img = ImageProcessor.compress_image(img)
        
        buf = io.BytesIO()
        img.save(buf, "png")
        return buf.getvalue()

    @staticmethod
    def draw_text(
        image_source: Union[str, Image.Image],
        top_left: Tuple[int, int],
        bottom_right: Tuple[int, int],
        text: str,
        color: Tuple[int, int, int] = (0, 0, 0),
        max_font_height: Optional[int] = None,
        font_path: Optional[str] = None,
        align: Align = "center",
        valign: VAlign = "middle",
        line_spacing: float = 0.15,
        bracket_color: Tuple[int, int, int] = (137, 177, 251),
        image_overlay: Union[str, Image.Image, None] = None,
        role_name: str = "unknown",
        text_configs_dict: Optional[Dict] = None,
    ) -> bytes:
        """
        Draw text into a specified rectangle, auto-sizing font.
        """
        if isinstance(image_source, Image.Image):
            img = image_source.copy()
        else:
            img = Image.open(image_source).convert("RGBA")

        # Load overlay
        img_overlay = None
        if image_overlay is not None:
            if isinstance(image_overlay, Image.Image):
                img_overlay = image_overlay.copy()
            elif isinstance(image_overlay, str) and os.path.isfile(image_overlay):
                img_overlay = Image.open(image_overlay).convert("RGBA")

        x1, y1 = top_left
        x2, y2 = bottom_right
        region_w = x2 - x1
        region_h = y2 - y1

        if region_w <= 0 or region_h <= 0:
             raise ValueError("Invalid text area.")

        # Helper to load font
        def _load_font(size: int) -> ImageFont.FreeTypeFont:
            if font_path and os.path.exists(font_path):
                return ImageFont.truetype(font_path, size=size)
            try:
                # Try to find a default font or use a fallback
                return ImageFont.truetype("arial.ttf", size=size)
            except Exception:
                return ImageFont.load_default() # type: ignore

        # Helper to measure text
        def _get_text_size(text_segment: str, font) -> Tuple[int, int]:
            if PILMOJI_AVAILABLE:
                with Pilmoji(img) as pilmoji:
                    return pilmoji.getsize(text_segment, font=font)
            else:
                draw = ImageDraw.Draw(img)
                return (int(draw.textlength(text_segment, font=font)), int(font.size)) # Approximate height

        # Wrap lines logic
        def _wrap_lines(txt: str, font, max_w: int) -> List[str]:
            lines = []
            for para in txt.splitlines() or [""]:
                has_space = " " in para
                units = para.split(" ") if has_space else list(para)
                buf = ""
                
                def unit_join(a, b):
                    return (a + " " + b) if has_space and a else (a + b)

                for u in units:
                    trial = unit_join(buf, u)
                    w, _ = _get_text_size(trial, font)
                    if w <= max_w:
                        buf = trial
                    else:
                        if buf:
                            lines.append(buf)
                        
                        # If single unit is too long, split it char by char
                        if has_space and len(u) > 1:
                            tmp = ""
                            for ch in u:
                                tmp_w, _ = _get_text_size(tmp + ch, font)
                                if tmp_w <= max_w:
                                    tmp += ch
                                else:
                                    if tmp: lines.append(tmp)
                                    tmp = ch
                            buf = tmp
                        else:
                            # Single char too wide? Just put it (or split if we supported that)
                            w_u, _ = _get_text_size(u, font)
                            if w_u <= max_w:
                                buf = u
                            else:
                                lines.append(u)
                                buf = ""
                if buf:
                    lines.append(buf)
                if para == "" and (not lines or lines[-1] != ""):
                    lines.append("")
            return lines

        def _measure_block(lines: List[str], font):
            ascent, descent = font.getmetrics()
            line_h = int((ascent + descent) * (1 + line_spacing))
            max_w = 0
            for ln in lines:
                w, _ = _get_text_size(ln, font)
                max_w = max(max_w, w)
            total_h = max(line_h * len(lines), 1)
            return max_w, total_h, line_h

        # Binary search for font size
        hi = min(region_h, max_font_height) if max_font_height else region_h
        lo = 1
        best_size = 1
        best_lines = []
        best_line_h = 1
        best_block_h = 1

        while lo <= hi:
            mid = (lo + hi) // 2
            font_main = _load_font(mid)
            lines = _wrap_lines(text, font_main, region_w)
            w, h, lh = _measure_block(lines, font_main)
            if w <= region_w and h <= region_h:
                best_size = mid
                best_lines = lines
                best_line_h = lh
                best_block_h = h
                lo = mid + 1
            else:
                hi = mid - 1
        
        font_main = _load_font(best_size)

        # Calculate Y start
        if valign == "top":
            y_start = y1
        elif valign == "bottom":
            y_start = y2 - best_block_h
        else:
            y_start = y1 + (region_h - best_block_h) // 2

        # Draw text
        y = y_start
        in_bracket = False
        
        # Prepare drawer
        if PILMOJI_AVAILABLE:
            pilmoji = Pilmoji(img)
        else:
            draw = ImageDraw.Draw(img)

        for ln in best_lines:
            w, _ = _get_text_size(ln, font_main)
            
            if align == "left":
                x = x1
            elif align == "right":
                x = x2 - w
            else:
                x = x1 + (region_w - w) // 2
            
            segments, in_bracket = ImageProcessor._parse_color_segments(ln, in_bracket, color, bracket_color)
            
            for seg_text, seg_color in segments:
                if not seg_text: continue
                
                if PILMOJI_AVAILABLE:
                    # Shadow
                    pilmoji.text((x+4, y+4), seg_text, font=font_main, fill=(0,0,0))
                    # Main text
                    pilmoji.text((x, y), seg_text, font=font_main, fill=seg_color)
                    seg_w, _ = pilmoji.getsize(seg_text, font=font_main)
                    x += seg_w
                else:
                    draw.text((x+4, y+4), seg_text, font=font_main, fill=(0,0,0))
                    draw.text((x, y), seg_text, font=font_main, fill=seg_color)
                    x += int(draw.textlength(seg_text, font=font_main))
            
            y += best_line_h

        # Paste overlay
        if img_overlay:
            img.paste(img_overlay, (0, 0), img_overlay)

        # Draw character name
        if text_configs_dict and role_name in text_configs_dict:
            ImageProcessor._draw_character_name(img, role_name, text_configs_dict, font_path)

        img = ImageProcessor.compress_image(img)
        
        buf = io.BytesIO()
        img.save(buf, "png")
        return buf.getvalue()

    @staticmethod
    def _parse_color_segments(text: str, in_bracket: bool, default_color: Tuple[int, int, int], bracket_color: Tuple[int, int, int]) -> Tuple[List[Tuple[str, Tuple[int, int, int]]], bool]:
        segs = []
        buf = ""
        for ch in text:
            if ch in ("[", "【"):
                if buf:
                    segs.append((buf, bracket_color if in_bracket else default_color))
                    buf = ""
                segs.append((ch, bracket_color))
                in_bracket = True
            elif ch in ("]", "】"):
                if buf:
                    segs.append((buf, bracket_color))
                    buf = ""
                segs.append((ch, bracket_color))
                in_bracket = False
            else:
                buf += ch
        if buf:
            segs.append((buf, bracket_color if in_bracket else default_color))
        return segs, in_bracket

    @staticmethod
    def _draw_character_name(img: Image.Image, role_name: str, text_configs_dict: Dict, font_path: Optional[str]):
        draw = ImageDraw.Draw(img)
        shadow_offset = (2, 2)
        shadow_color = (0, 0, 0)
        
        for config in text_configs_dict[role_name]:
            char_text = config["text"]
            position = config["position"]
            font_color = config["font_color"]
            font_size = config["font_size"]
            
            # Use provided font path or fallback
            try:
                if font_path and os.path.exists(font_path):
                    char_font = ImageFont.truetype(font_path, font_size)
                else:
                    char_font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                char_font = ImageFont.load_default()

            shadow_position = (position[0] + shadow_offset[0], position[1] + shadow_offset[1])
            
            draw.text(shadow_position, char_text, fill=shadow_color, font=char_font)
            draw.text(position, char_text, fill=font_color, font=char_font)
