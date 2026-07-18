import os
import requests
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from cinegram.config import settings


def _load_font(size: int):
    """Try configured font, fallback to arial, then default."""
    try:
        font_path = settings.DEFAULT_FONT_PATH
        if not os.path.exists(font_path):
            font_path = "arial.ttf"
        return ImageFont.truetype(font_path, size)
    except IOError:
        return ImageFont.load_default()


def _draw_shadow(base: Image.Image, x: int, y: int, w: int, h: int):
    """Draw a soft shadow behind a rectangle area on the base image."""
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    offset = settings.POSTER_SHADOW_OFFSET
    blur = settings.POSTER_SHADOW_BLUR
    # Draw shadow rectangle
    shadow_draw.rounded_rectangle(
        [x + offset, y + offset, x + w + offset, y + h + offset],
        radius=12,
        fill=(0, 0, 0, 160)
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(base, shadow_layer)


class ImageGenerator:
    @staticmethod
    def generate_poster(image_url: str, title: str, description: str) -> str:
        """
        Generates a 1920x1080 split-style poster:
        - Left: movie poster with shadow
        - Right: title, metadata, synopsis
        - Background: solid dark color
        Returns the path to the generated image.
        """
        target_w, target_h = settings.IMAGE_SIZE

        # 1. Download poster image
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            poster = Image.open(BytesIO(response.content)).convert("RGBA")
        except Exception as e:
            print(f"Error loading image: {e}")
            poster = Image.new("RGBA", (500, 750), (30, 30, 30, 255))

        # 2. Create dark background
        canvas = Image.new("RGBA", (target_w, target_h), settings.POSTER_BG_COLOR + (255,))

        # 3. Calculate poster area (left side)
        poster_area_w = int(target_w * settings.POSTER_LEFT_WIDTH)
        poster_max_w = poster_area_w - settings.POSTER_MARGIN * 2
        poster_max_h = target_h - settings.POSTER_MARGIN * 2

        # Scale poster to fit (aspect fit)
        scale = min(poster_max_w / poster.width, poster_max_h / poster.height)
        new_w = int(poster.width * scale)
        new_h = int(poster.height * scale)
        poster_resized = poster.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Center poster in left area
        poster_x = (poster_area_w - new_w) // 2
        poster_y = (target_h - new_h) // 2

        # 4. Draw shadow behind poster
        canvas = _draw_shadow(canvas, poster_x, poster_y, new_w, new_h)

        # 5. Add rounded corners to poster (optional visual polish)
        # Create a mask for rounded corners
        mask = Image.new("L", (new_w, new_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, new_w - 1, new_h - 1], radius=10, fill=255)

        # Paste poster with mask
        canvas.paste(poster_resized, (poster_x, poster_y), mask)

        # 6. Draw text on right side
        draw = ImageDraw.Draw(canvas)

        text_x = poster_area_w + settings.POSTER_TEXT_MARGIN_LEFT

        title_font = _load_font(settings.POSTER_TITLE_SIZE)
        desc_font = _load_font(settings.POSTER_DESC_SIZE)

        # --- Title ---
        title_lines = textwrap.wrap(title, width=28)
        title_line_h = settings.POSTER_TITLE_SIZE + 10

        # Start title vertically centered relative to poster
        text_start_y = max(poster_y, int(target_h * 0.15))

        current_y = text_start_y
        for line in title_lines:
            draw.text((text_x, current_y), line, font=title_font, fill="white")
            current_y += title_line_h

        # --- Synopsis ---
        current_y += 20
        clean_desc = (description[:500] + "...") if len(description) > 500 else description
        desc_lines = textwrap.wrap(clean_desc, width=55)

        # Limit to available space
        available_h = target_h - 100 - current_y  # bottom margin
        max_desc_lines = max(1, available_h // (settings.POSTER_DESC_SIZE + 8))
        desc_lines = desc_lines[:max_desc_lines]

        for line in desc_lines:
            draw.text((text_x, current_y), line, font=desc_font, fill=(180, 180, 180))
            current_y += settings.POSTER_DESC_SIZE + 8

        # 7. Logo Watermark (top right)
        try:
            logo_path = os.path.join(settings.ASSETS_DIR, "logo", "logo.png")
            if os.path.exists(logo_path):
                logo = Image.open(logo_path).convert("RGBA")
                target_logo_w = 250
                logo_ratio = logo.height / logo.width
                target_logo_h = int(target_logo_w * logo_ratio)
                logo = logo.resize((target_logo_w, target_logo_h), Image.Resampling.LANCZOS)
                logo_x = target_w - target_logo_w - 40
                logo_y = 40
                canvas.paste(logo, (logo_x, logo_y), logo)
            else:
                wm_text = "CINEGRAM"
                wm_font = _load_font(50)
                wm_bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
                wm_x = target_w - (wm_bbox[2] - wm_bbox[0]) - 40
                wm_y = 45
                draw.text((wm_x + 2, wm_y + 2), wm_text, font=wm_font, fill="black")
                draw.text((wm_x, wm_y), wm_text, font=wm_font, fill=(255, 215, 0))
        except Exception as e:
            print(f"Error adding watermark: {e}")

        # 8. Save
        output_path = os.path.join(settings.TEMP_DIR, f"{title[:10].replace(' ', '_')}_poster.jpg")
        canvas = canvas.convert("RGB")
        canvas.save(output_path, quality=95)

        return output_path
