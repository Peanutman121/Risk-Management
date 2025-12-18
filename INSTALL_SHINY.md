# Installing and Running the Shiny Dashboard

## Quick Start

### 1. Install Shiny

```bash
pip install shiny
```

Or install all dependencies:

```bash
pip install -r requirements_shiny.txt
```

### 2. Run the App

```bash
./run_shiny.sh
```

Or manually:

```bash
cd /home/user/Risk-Management
export PYTHONPATH="${PYTHONPATH}:$(pwd)/portfolio_risk_system/python"
shiny run shiny_app.py --reload --port 8000
```

### 3. Open Browser

Navigate to: **http://localhost:8000**

### 4. Click Refresh

Click the big blue "🔄 Refresh Data" button to load positions and Bloomberg data.

---

## First Time Setup

### Install Python 3.11+ (if needed)

```bash
python3 --version  # Should be 3.11 or higher
```

### Create Virtual Environment (recommended)

```bash
cd /home/user/Risk-Management
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install All Dependencies

```bash
pip install --upgrade pip
pip install -r requirements_shiny.txt
```

### Verify Installation

```bash
python3 -c "import shiny; print(f'Shiny version: {shiny.__version__}')"
```

Should output: `Shiny version: 0.6.x` or similar

---

## Running Options

### Development (auto-reload on code changes)

```bash
shiny run shiny_app.py --reload
```

### Production (stable)

```bash
shiny run shiny_app.py
```

### Background (keeps running)

```bash
nohup shiny run shiny_app.py --port 8000 > shiny.log 2>&1 &
```

To stop:
```bash
pkill -f "shiny run"
```

### Custom Port

```bash
shiny run shiny_app.py --port 9000
```

### Network Access (access from other computers)

```bash
shiny run shiny_app.py --host 0.0.0.0 --port 8000
```

Then access from other machines: `http://YOUR_IP:8000`

---

## Troubleshooting

### "Module not found: shiny"

**Solution**: Install Shiny
```bash
pip install shiny
```

### "No module named 'config'"

**Solution**: Set PYTHONPATH
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/portfolio_risk_system/python"
```

Or use the provided run script:
```bash
./run_shiny.sh
```

### "Port 8000 already in use"

**Solution**: Use a different port
```bash
shiny run shiny_app.py --port 9000
```

Or kill the existing process:
```bash
lsof -ti:8000 | xargs kill -9
```

### "Cannot find Excel files"

**Solution**: Check file paths in `config.py`
```python
# Should point to:
EXCEL_DIR = BASE_DIR / "excel"
TRADER_FILES = {
    1: EXCEL_DIR / "positions_trader1.xlsx",
    # ...
}
```

### "Bloomberg connection error"

**Solution**: Either:
1. Start Bloomberg terminal
2. Or disable Bloomberg in `config.py`:
```python
FETCH_LIVE_PRICES = False
USE_LIVE_CORRELATIONS = False
```

---

## Comparison to Streamlit

| Aspect | Streamlit | Shiny |
|--------|-----------|-------|
| Install | `pip install streamlit` | `pip install shiny` |
| Run | `streamlit run streamlit_app.py` | `shiny run shiny_app.py` |
| Data loading | Auto (on every interaction) | Manual (click refresh) |
| Dropdown speed | 3-5s | <100ms |
| Stability | Crashes/freezes | Stable |
| Control | Limited | Full control |

---

## Next Steps

1. ✅ Install Shiny
2. ✅ Run app
3. ✅ Click refresh to load data
4. ✅ Enjoy instant dropdowns!

See `SHINY_APP_GUIDE.md` for full usage documentation.
