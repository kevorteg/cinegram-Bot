import os
import requests
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from cinegram.config import settings

class ImageGenerator:
    @staticmethod
    def generate_poster(image_url: str, title: str, description: str) -> str:
        """
        Generates a 1920x1080 poster with title and description overlay.
        Returns the path to the generated image.
        """
        # 1. Download or Load Image
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGBA")
        except Exception as e:
            print(f"Error loading image: {e}")
            # Create a black placeholder if image download fails
            img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 255))

        # 2. Smart Composition: Blurred Background + Centered Poster
        target_size = settings.IMAGE_SIZE # (1920, 1080)
        
        # A. Create Background (Blurred & Darkened)
        # Resize to FILL the screen (Aspect Fill)
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            # Image is wider than screen, resize by height
            bg_height = target_size[1]
            bg_width = int(bg_height * img_ratio)
        else:
            # Image is taller/narrower, resize by width to fill width
            bg_width = target_size[0]
            bg_height = int(bg_width / img_ratio)

        background = img.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
        
        # Center Crop the background to fit 1920x1080 exactly
        left = (background.width - target_size[0]) / 2
        top = (background.height - target_size[1]) / 2
        right = (background.width + target_size[0]) / 2
        bottom = (background.height + target_size[1]) / 2
        background = background.crop((left, top, right, bottom))
        
        # Apply Heavy Blur
        background = background.filter(ImageFilter.GaussianBlur(30))
        
        # Darken Background significantly to make text pop
        dark_layer = Image.new("RGBA", target_size, (0, 0, 0, 120))
        background = Image.alpha_composite(background, dark_layer)

        # B. Create Foreground (Fitted Poster)
        # Resize to FIT inside the screen (Aspect Fit) - maximize height usually
        # Give it a slight margin so it doesn't touch edges (e.g. 95% height)
        max_h = int(target_size[1] * 0.95)
        max_w = int(target_size[0] * 0.95)
        
        scale = min(max_w / img.width, max_h / img.height)
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        
        foreground = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Paste Foreground Center
        x_pos = (target_size[0] - new_w) // 2
        y_pos = (target_size[1] - new_h) // 2
        
        # Add shadow to foreground? (Optional, implies creating a larger shadow layer)
        # For simplicity, just paste.
        background.paste(foreground, (x_pos, y_pos))
        
        # Update main img reference
        img = background

        # 3. Add Dark Overlay (Gradient or solid semi-transparent)
        overlay = Image.new("RGBA", target_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        # Gradient from bottom 60% to bottom
        for y in range(int(target_size[1] * 0.4), target_size[1]):
            alpha = int(255 * ((y - target_size[1] * 0.4) / (target_size[1] * 0.6)))
            draw.line([(0, y), (target_size[0], y)], fill=(0, 0, 0, alpha))
        
        img = Image.alpha_composite(img, overlay)

        # 4. Add Text
        draw = ImageDraw.Draw(img)
        
        # Load Font
        try:
            # Try configured font, fallback to Arial if on Windows/generic
            font_path = settings.DEFAULT_FONT_PATH
            if not os.path.exists(font_path):
                font_path = "arial.ttf" # Common on Windows
            
            title_font = ImageFont.truetype(font_path, 80)
            desc_font = ImageFont.truetype(font_path, 40)
        except IOError:
            # Fallback to default if load fails
            title_font = ImageFont.load_default()
            desc_font = ImageFont.load_default()

        # Text Positioning
        margin_x = 100
        margin_y = 100
        max_width_chars = 50 # approx for wrapping

        # Draw Title
        # split title if too long?
        title_lines = textwrap.wrap(title, width=25)
        current_y = target_size[1] - 350 # Start from bottom-ish area
        for line in title_lines:
             # Calculate text width to verify fit if needed, but simple draw is often enough
             draw.text((margin_x, current_y), line, font=title_font, fill="white")
             current_y += 90 # Line height

        # Draw Description (Synopsis)
        current_y += 20
        # Limit description lines
        clean_desc = (description[:300] + '...') if len(description) > 300 else description
        desc_lines = textwrap.wrap(clean_desc, width=70)[:6] # Max 6 lines

        for line in desc_lines:
            draw.text((margin_x, current_y), line, font=desc_font, fill=(200, 200, 200))
            current_y += 50

        # Draw Logo Watermark (Top Right)
        try:
            logo_path = os.path.join(settings.ASSETS_DIR, "logo", "logo.png")
            if os.path.exists(logo_path):
                logo = Image.open(logo_path).convert("RGBA")
                
                # Resize logo (e.g., width 300px, maintain aspect)
                target_logo_width = 300
                logo_ratio = logo.height / logo.width
                target_logo_height = int(target_logo_width * logo_ratio)
                logo = logo.resize((target_logo_width, target_logo_height), Image.Resampling.LANCZOS)
                
                # Position: Top Right with margin
                margin = 50
                logo_x = target_size[0] - target_logo_width - margin
                logo_y = margin
                
                img.paste(logo, (logo_x, logo_y), logo)
            else:
                # Fallback to Text if logo file missing
                watermark_text = "CINEGRAM 🎬"
                wm_font_size = 60
                wm_font = ImageFont.truetype(font_path, wm_font_size) if 'font_path' in locals() else ImageFont.load_default()
                wm_bbox = draw.textbbox((0, 0), watermark_text, font=wm_font)
                wm_x = target_size[0] - (wm_bbox[2] - wm_bbox[0]) - 50
                wm_y = 50
                draw.text((wm_x + 3, wm_y + 3), watermark_text, font=wm_font, fill="black")
                draw.text((wm_x, wm_y), watermark_text, font=wm_font, fill=(255, 215, 0))
                
        except Exception as e:
            print(f"Error adding watermark: {e}")

        # 5. Save
        output_path = os.path.join(settings.TEMP_DIR, f"{title[:10].replace(' ', '_')}_poster.jpg")
        img = img.convert("RGB") # Remove alpha for JPG
        img.save(output_path, quality=95)
        
        return output_path
