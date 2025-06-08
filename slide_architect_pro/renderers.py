import json
import altair as alt
from cairosvg import svg2png
from pathlib import Path
import uuid
import logging
import tempfile
import os

logger = logging.getLogger(__name__)

def render_vega_lite(vega_spec: str, work_dir: Path) -> Path:
    """Render Vega-Lite specification to PNG image"""
    try:
        spec = json.loads(vega_spec)
        if not isinstance(spec, dict) or "$schema" not in spec or "data" not in spec:
            logger.warning("Invalid Vega-Lite specification")
            raise ValueError("Invalid Vega-Lite specification")
        
        # Create Altair chart from spec
        chart = alt.Chart.from_dict(spec)
        
        # Save as SVG first
        svg_file = work_dir / f"vega_{uuid.uuid4()}.svg"
        png_file = work_dir / f"vega_{uuid.uuid4()}.png"
        
        # Save chart as SVG
        chart.save(str(svg_file))
        
        # Convert SVG to PNG
        svg2png(url=str(svg_file), write_to=str(png_file), scale=2)
        
        # Clean up SVG file
        if svg_file.exists():
            svg_file.unlink()
            
        return png_file
        
    except Exception as e:
        logger.error(f"Failed to render Vega-Lite chart: {str(e)}")
        # Create a fallback placeholder image
        placeholder_file = work_dir / f"placeholder_{uuid.uuid4()}.png"
        _create_placeholder_image(placeholder_file, "Chart could not be rendered")
        return placeholder_file

def _create_placeholder_image(file_path: Path, text: str):
    """Create a simple placeholder image with text"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple placeholder
        img = Image.new('RGB', (400, 300), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        # Try to use a font, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        # Calculate text position
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (400 - text_width) // 2
        y = (300 - text_height) // 2
        
        draw.text((x, y), text, fill='black', font=font)
        img.save(str(file_path))
        
    except Exception as e:
        logger.error(f"Failed to create placeholder image: {str(e)}")
        # If all else fails, create an empty file
        file_path.touch()