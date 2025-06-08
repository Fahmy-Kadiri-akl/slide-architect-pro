import json
import altair as alt
from pathlib import Path
import uuid
import logging
import tempfile
import os

logger = logging.getLogger(__name__)

def render_vega_lite(vega_spec: str, work_dir: Path) -> Path:
    """Render Vega-Lite specification to PNG image"""
    try:
        # Enable Altair to render charts properly
        alt.data_transformers.enable('json')
        
        spec = json.loads(vega_spec)
        if not isinstance(spec, dict) or "$schema" not in spec:
            logger.warning("Invalid Vega-Lite specification - missing schema")
            raise ValueError("Invalid Vega-Lite specification")
        
        # Validate that data exists
        if "data" not in spec:
            logger.warning("Invalid Vega-Lite specification - missing data")
            raise ValueError("Invalid Vega-Lite specification - missing data")
        
        # Create Altair chart from spec
        chart = alt.Chart.from_dict(spec)
        
        # Create file paths
        png_file = work_dir / f"vega_{uuid.uuid4()}.png"
        
        try:
            # Try to use vl-convert-python for direct PNG conversion
            try:
                import vl_convert as vlc
                png_data = vlc.vegalite_to_png(spec)
                with open(png_file, 'wb') as f:
                    f.write(png_data)
                logger.info(f"Successfully rendered Vega-Lite chart to {png_file} using vl-convert")
                return png_file
            except ImportError:
                logger.warning("vl-convert-python not available, trying alternative methods")
            
            # Fallback: try SVG then convert to PNG
            try:
                svg_file = work_dir / f"vega_{uuid.uuid4()}.svg"
                chart.save(str(svg_file), format='svg')
                
                # Convert SVG to PNG using cairosvg if available
                try:
                    from cairosvg import svg2png
                    with open(svg_file, 'rb') as svg_input:
                        svg2png(file_obj=svg_input, write_to=str(png_file), scale=2)
                    
                    # Clean up SVG file
                    if svg_file.exists():
                        svg_file.unlink()
                        
                    logger.info(f"Successfully rendered Vega-Lite chart to {png_file} using cairosvg")
                    return png_file
                except ImportError:
                    logger.warning("cairosvg not available")
                    # Clean up SVG file if cairosvg fails
                    if svg_file.exists():
                        svg_file.unlink()
                    
            except Exception as e:
                logger.warning(f"SVG fallback failed: {e}")
            
            # Final fallback: create placeholder
            return _create_placeholder_image(work_dir, "Chart rendering unavailable")
            
        except Exception as e:
            logger.error(f"Failed to save or convert chart: {e}")
            # Clean up any partial files
            for temp_file in [png_file]:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass
            raise
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Vega-Lite spec: {e}")
        return _create_placeholder_image(work_dir, "Invalid chart JSON")
    except Exception as e:
        logger.error(f"Failed to render Vega-Lite chart: {str(e)}")
        return _create_placeholder_image(work_dir, "Chart could not be rendered")

def _create_placeholder_image(work_dir: Path, text: str) -> Path:
    """Create a simple placeholder image with text"""
    placeholder_file = work_dir / f"placeholder_{uuid.uuid4()}.png"
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple placeholder
        img = Image.new('RGB', (400, 300), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        # Try to use a font, fall back to default if not available
        try:
            # Try common system fonts
            font_paths = [
                "/System/Library/Fonts/Arial.ttf",  # macOS
                "/usr/share/fonts/truetype/arial.ttf",  # Linux
                "C:/Windows/Fonts/arial.ttf",  # Windows
            ]
            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, 16)
                    break
                except:
                    continue
            
            if font is None:
                font = ImageFont.load_default()
                
        except Exception:
            font = ImageFont.load_default()
        
        # Calculate text position for centering
        try:
            # For newer Pillow versions
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            # For older Pillow versions
            text_width, text_height = draw.textsize(text, font=font)
        
        x = max(0, (400 - text_width) // 2)
        y = max(0, (300 - text_height) // 2)
        
        # Add a border and background for better visibility
        draw.rectangle([x-10, y-10, x+text_width+10, y+text_height+10], 
                      fill='white', outline='darkgray', width=2)
        draw.text((x, y), text, fill='black', font=font)
        
        img.save(str(placeholder_file), 'PNG')
        logger.info(f"Created placeholder image: {placeholder_file}")
        
    except ImportError:
        logger.error("PIL/Pillow not available, creating empty placeholder")
        # Create an empty file if PIL is not available
        placeholder_file.touch()
    except Exception as e:
        logger.error(f"Failed to create placeholder image: {str(e)}")
        # Create an empty file as last resort
        placeholder_file.touch()
    
    return placeholder_file

def validate_vega_spec(spec_str: str) -> bool:
    """Validate a Vega-Lite specification string"""
    try:
        spec = json.loads(spec_str)
        
        # Check required fields
        required_fields = ["$schema", "data"]
        for field in required_fields:
            if field not in spec:
                return False
        
        # Check data structure
        if "data" in spec:
            data = spec["data"]
            if "values" in data:
                if not isinstance(data["values"], list):
                    return False
                # Limit data size for security
                if len(data["values"]) > 100:
                    return False
        
        return True
        
    except (json.JSONDecodeError, TypeError):
        return False