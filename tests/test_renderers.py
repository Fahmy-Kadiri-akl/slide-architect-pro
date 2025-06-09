import json
import importlib.util
from pathlib import Path

# Import renderers module directly to avoid executing package __init__
module_path = Path(__file__).resolve().parents[1] / 'slide_architect_pro' / 'renderers.py'
spec = importlib.util.spec_from_file_location('renderers', module_path)
renderers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderers)
validate_vega_spec = renderers.validate_vega_spec


def test_validate_vega_spec_valid():
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {
            "values": [
                {"a": "A", "b": 28},
                {"a": "B", "b": 55}
            ]
        },
        "mark": "bar",
        "encoding": {
            "x": {"field": "a", "type": "ordinal"},
            "y": {"field": "b", "type": "quantitative"}
        }
    }
    spec_str = json.dumps(spec)
    assert validate_vega_spec(spec_str) is True


def test_validate_vega_spec_malformed_json():
    malformed = '{ "data": [ }'  # invalid JSON
    assert validate_vega_spec(malformed) is False
