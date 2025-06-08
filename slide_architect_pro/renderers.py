import json
import vega
from cairosvg import svg2png
from pathlib import Path
import uuid
import logging

logger = logging.getLogger(__name__)

def render_vega_lite(vega_spec: str, work_dir: Path) -> Path:
    try:
        spec = json.loads(vega_spec)
        if not isinstance(spec, dict) or "$schema" not in spec or "data" not in spec:
            logger.warning("Invalid Vega-Lite specification")
            raise ValueError("Invalid Vega-Lite specification")
        vega_chart = vega.Vega(spec)
        svg_file = work_dir / f"vega_{uuid.uuid4()}.svg"
        png_file = work_dir / f"vega_{uuid.uuid4()}.png"
        vega_chart.save(str(svg_file))
        svg2png(url=str(svg_file), write_to=str(png_file), scale=2)
        svg_file.unlink()
        return png_file
    except Exception as e:
        logger.error(f"Failed to render Vega-Lite chart: {str(e)}")
        raise ValueError(f"Failed to render Vega-Lite chart: {str(e)}")