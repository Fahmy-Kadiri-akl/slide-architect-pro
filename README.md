# Slide Architect Pro - Quick Start Guide

## Installation Steps

### 1. Install Dependencies
```bash
# Install using the provided setup.py
pip install .

# OR install packages individually
pip install python-pptx pydantic aiohttp mistune bleach fastapi uvicorn requests altair vl-convert-python cairosvg Pillow
```

### 2. Set Environment Variables (Optional)
```bash
# Work directory (defaults to temp dir if not set)
export SLIDE_WORK_DIR="/tmp/slide_architect_pro"

# API keys for LLM providers (optional - can use offline mode)
export GEMINI_API_KEY="your-gemini-key"
export OPENAI_API_KEY="your-openai-key"
```

### 3. Run the Server
```bash
python run_server.py
```

The server will start on `http://localhost:8000`

## Testing the Installation

### Test 1: Health Check
```bash
curl http://localhost:8000/health
```
Should return: `{"status": "healthy", "service": "Slide Architect Pro"}`

### Test 2: Generate Slides (Offline Mode)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Generate a pitch deck for AI cybersecurity, audience: investors",
    "llm_provider": "offline"
  }'
```

### Test 3: WebSocket Connection (JavaScript)
```javascript
const ws = new WebSocket("ws://localhost:8000/chat");
ws.onopen = () => {
    ws.send(JSON.stringify({
        message: "Create a presentation about machine learning for developers",
        llm_provider: "offline"
    }));
};
ws.onmessage = (event) => {
    console.log(JSON.parse(event.data));
};
```

## Key Fixes Applied

### 1. **Python Compatibility**
- Removed Python 3.10+ union syntax (`str | None`)
- Added proper typing imports (`Optional`, `Union`)
- Compatible with Python 3.9+

### 2. **Dependencies**
- Added missing `vl-convert-python` for Altair SVG export
- Specified exact versions for stability
- Added Pillow for image processing

### 3. **Security Improvements**
- Better input validation and sanitization
- Secure work directory setup with path validation
- File size and complexity limits
- Proper error handling

### 4. **Rendering Fixes**
- Fixed Altair chart rendering with proper SVG export
- Better error handling for chart generation
- Fallback placeholder images when rendering fails
- Cross-platform font handling

### 5. **Error Handling**
- Added comprehensive try-catch blocks
- Better logging and error messages
- Graceful degradation when components fail
- Input validation with proper error responses

## Common Issues & Solutions

### Issue: "ModuleNotFoundError: No module named 'vl_convert'"
**Solution:** Install vl-convert-python:
```bash
pip install vl-convert-python
```

### Issue: Charts not rendering
**Solution:** Ensure Altair and vl-convert are installed:
```bash
pip install altair>=5.0.0 vl-convert-python>=1.1.0
```

### Issue: Permission denied writing to work directory
**Solution:** Set a writable work directory:
```bash
export SLIDE_WORK_DIR="/tmp/slides"
mkdir -p /tmp/slides
chmod 755 /tmp/slides
```

### Issue: LLM API calls failing
**Solution:** Use offline mode or check API keys:
```bash
# Test with offline mode first
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test presentation", "llm_provider": "offline"}'
```

## File Structure After Running
```
/tmp/slide_architect_pro_[uuid]/
├── Your_Topic_Name.pptx          # PowerPoint file
├── Your_Topic_Name.md            # Markdown source
├── Your_Topic_Name.json          # JSON structure
├── vega_[uuid].png              # Generated charts
└── placeholder_[uuid].png       # Placeholder images
```

## Next Steps
1. Test basic functionality with offline mode
2. Add your LLM API keys for enhanced generation
3. Customize templates in `templates.py`
4. Integrate with your chat platform or web app

The code should now run successfully with these fixes!