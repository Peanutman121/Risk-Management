# Shiny Dashboard Guide

## Why Shiny Instead of Streamlit?

### The Problem with Streamlit

**Every interaction triggers a full re-run:**
```python
# Streamlit reruns ENTIRE script on every dropdown click
user clicks dropdown
  ↓
entire script reruns
  ↓
reads Excel (cached, but still checked)
  ↓
calls Bloomberg API (cached, but still checked)
  ↓
recalculates everything
  ↓
page finally responds (3-5 seconds later)
```

**Result**: Slow, crashes, freezing, poor UX

---

### The Shiny Solution

**Explicit control over when things happen:**
```python
# Shiny ONLY loads data when you click refresh
user clicks dropdown
  ↓
filters in-memory data
  ↓
instant response (<100ms)

user clicks refresh button
  ↓
reads Excel files
  ↓
calls Bloomberg API
  ↓
stores data in memory
  ↓
done (5-10 seconds, but only when YOU choose)
```

**Result**: Fast, stable, predictable

---

## Installation

### Install Shiny

```bash
pip install shiny>=0.6.0
```

Or install all requirements:

```bash
pip install -r requirements_shiny.txt
```

---

## Running the App

### Option 1: Use the run script (easiest)

```bash
./run_shiny.sh
```

### Option 2: Run directly

```bash
cd /path/to/Risk-Management
export PYTHONPATH="${PYTHONPATH}:$(pwd)/portfolio_risk_system/python"
shiny run shiny_app.py --reload --port 8000
```

### Option 3: Background/production mode

```bash
shiny run shiny_app.py --host 0.0.0.0 --port 8000 &
```

---

## How to Use

### First Time Opening

1. **Open browser**: `http://localhost:8000`
2. **See message**: "Click 'Refresh Data' to load"
3. **Click the big blue button**: "🔄 Refresh Data"
4. **Wait 5-10 seconds** while it:
   - Reads 5 Excel files
   - Fetches Bloomberg prices
   - Fetches Bloomberg correlation matrix
   - Calculates all risk metrics
5. **Done!** Now everything is instant

### Normal Workflow

```
1. Open app → Shows "Click refresh to load"
2. Click [🔄 Refresh Data] → Loads everything (5-10s)
3. Use all dropdowns/filters → INSTANT (all in-memory)
4. Change vol target/correlation → INSTANT (recalc only)
5. Navigate between pages → INSTANT (data already loaded)
6. Want fresh data? → Click [🔄 Refresh Data] again
```

### When to Click Refresh

- **Morning**: First thing, get latest data
- **After trades entered**: Someone updated their Excel file
- **Hourly**: Get latest Bloomberg prices
- **After market events**: Get fresh correlations

**You control when data refreshes** - not the app!

---

## Key Features

### 1. Refresh Button (Main Control)

Located in sidebar, big blue button.

**What happens when clicked:**
- ✅ Reads all 5 trader Excel files
- ✅ Fetches Bloomberg live prices (if enabled)
- ✅ Fetches Bloomberg correlation matrix (if enabled)
- ✅ Calculates position vols, P&L, risk metrics
- ✅ Stores everything in memory
- ✅ Updates "Last Updated" timestamp

**What does NOT trigger a refresh:**
- Changing pages
- Using dropdowns/filters
- Changing vol target/correlation sliders
- Anything else!

### 2. Last Updated Display

Shows when data was last refreshed:
```
Last Updated:
2024-01-15 14:35:22
```

If you see this is old, click refresh!

### 3. Settings (Sidebar)

**Vol Target**: Adjusts calculations in real-time (no refresh needed)
**Correlation**: Adjusts calculations in real-time (no refresh needed)

Both of these sliders just recalculate with existing data - instant!

### 4. Pages (Navigation)

All 6 pages available:
- 📊 Book Summary
- 📋 All Positions
- 👤 Trader Drill-Down
- 📈 Performance
- 📜 Trade History
- 🔮 Potential Trades

**All pages use the same in-memory data** - switching is instant!

---

## Performance Comparison

| Action | Streamlit | Shiny |
|--------|-----------|-------|
| Initial load | 10-15s | "Click refresh" message |
| Refresh data | N/A (auto) | 5-10s (when you click) |
| Change page | 1-2s | <100ms |
| Click dropdown | 3-5s freeze | <100ms |
| Filter positions | 2-3s | <100ms |
| Change vol target | 2-3s | <100ms |
| Change correlation | 2-3s | <100ms |

---

## Architecture Details

### Data Flow

```
[User Clicks Refresh]
        ↓
[Load Excel Files] → positions_trader1.xlsx
                    → positions_trader2.xlsx
                    → ... (all 5 files)
        ↓
[Fetch Bloomberg] → Live prices (BDP call)
                  → Correlation matrix (historical data)
        ↓
[Calculate Metrics] → Position vols
                    → Portfolio vol
                    → P&L
                    → Drawdowns
                    → SVB stress
        ↓
[Store in Memory] → reactive.Value() holds all data
        ↓
[User Interacts] → Filters/dropdowns just query memory
                 → INSTANT response
```

### Reactive Programming

Shiny uses **reactive programming**:

```python
# Data storage (reactive value)
data_store = reactive.Value({
    'all_positions': None,  # ← Holds DataFrame in memory
    'settings_dict': None,
    'live_prices': {},
    'correlation_matrix': None,
    ...
})

# Only runs when refresh button clicked
@reactive.Effect
@reactive.event(input.refresh)  # ← Key: explicit trigger
def load_data():
    # Read Excel
    all_positions = load_all_traders()
    # Fetch Bloomberg
    live_prices = fetch_live_prices_bulk(...)
    # Store in memory
    data_store.set({...})

# Dropdowns just filter the in-memory data
def filter_positions():
    data = data_store.get()  # ← Get from memory
    df = data['all_positions']
    # Filter based on user selection (instant!)
    return df[df['trader'] == selected_trader]
```

---

## Configuration

Same `config.py` as before:

```python
# Use Bloomberg for risk calculations
FETCH_LIVE_PRICES = True
USE_LIVE_CORRELATIONS = True

# Fallback to defaults if Bloomberg unavailable
REQUIRE_LIVE_CORRELATIONS = False
DEFAULT_CORRELATION = 0.2
```

---

## Troubleshooting

### "Page is blank / nothing shows"

**Solution**: Click "🔄 Refresh Data" button!

The app doesn't auto-load data on startup. This is by design - you control when data is fetched.

### "Refresh takes too long"

First refresh includes:
- Reading 5 Excel files (~1s)
- Bloomberg prices (~1-2s)
- Bloomberg correlation matrix (~3-5s)

**Total**: 5-10 seconds is normal.

**Workaround**: Disable Bloomberg temporarily:
```python
# config.py
FETCH_LIVE_PRICES = False
USE_LIVE_CORRELATIONS = False
```

Now refresh takes ~1-2 seconds (Excel only).

### "Error loading data"

Check the error message in the sidebar. Common issues:
- Excel files missing/corrupted
- Bloomberg terminal not running
- Python path issues

Click refresh again to retry.

### "Dropdowns still slow"

If dropdowns are slow, something is wrong - they should be <100ms.

Check:
1. Did you actually click refresh first? (Data must be loaded)
2. Is there an error showing?
3. Check browser console (F12) for JavaScript errors

---

## Comparison to Streamlit App

### Streamlit (`streamlit_app.py`)

**Pros:**
- Simpler code
- Auto-reloads

**Cons:**
- Slow interactions (3-5s per dropdown)
- Crashes/freezes
- No control over when data loads
- Continuous re-execution

### Shiny (`shiny_app.py`)

**Pros:**
- ✅ Fast interactions (<100ms)
- ✅ Stable (no crashes)
- ✅ Full control over data loading
- ✅ Explicit refresh button
- ✅ In-memory filtering

**Cons:**
- Slightly more complex code
- Must click refresh manually

---

## Migration from Streamlit

If you were using the Streamlit app:

**Same:**
- All 6 pages
- Same calculations
- Same Bloomberg integration
- Same Excel files

**Different:**
- Must click refresh to load data (not auto-load)
- Sidebar navigation instead of tabs
- Much faster interactions

**To switch:**
1. Install Shiny: `pip install shiny`
2. Run: `./run_shiny.sh`
3. Click refresh button when app opens
4. Enjoy instant dropdowns!

---

## Advanced: Development Mode

### Auto-reload on code changes

```bash
shiny run shiny_app.py --reload
```

Now when you edit `shiny_app.py`, the app auto-restarts.

**Note**: Data does NOT auto-refresh - still need to click button!

### Port customization

```bash
shiny run shiny_app.py --port 9000
```

### Host on network

```bash
shiny run shiny_app.py --host 0.0.0.0 --port 8000
```

Now accessible from other computers: `http://your-ip:8000`

---

## Future Enhancements

### Auto-refresh timer (optional)

Could add a timer to auto-click refresh every N minutes:

```python
# In sidebar
ui.input_checkbox("auto_refresh", "Auto-refresh every 5 min", False)

# In server
@reactive.Effect
def auto_refresh_timer():
    if input.auto_refresh():
        reactive.invalidate_later(300)  # 5 minutes
        # Trigger refresh
```

### Email alerts

Could add email alerts on risk threshold breach:

```python
if metrics['risk_util_pct'] > 95:
    send_email_alert("Risk utilization >95%!")
```

### Export to PDF

Could add a button to export current view to PDF.

---

## Support

### Common Questions

**Q: Do I need to keep clicking refresh?**
A: Only when you want fresh data. If nothing changed in Excel or Bloomberg, no need to refresh.

**Q: Can I auto-refresh?**
A: Yes, could add a timer (see "Future Enhancements" above). But manual control is better for development.

**Q: Why is first refresh slow?**
A: Bloomberg correlation matrix takes 3-5s to fetch. After that, it's cached in memory.

**Q: Can I use without Bloomberg?**
A: Yes! Set `FETCH_LIVE_PRICES = False` and `USE_LIVE_CORRELATIONS = False` in config.py. App will use Excel prices and default correlation.

**Q: What if Excel file is open when I refresh?**
A: Should still work (openpyxl can read open files). But close Excel for best results.

---

## Summary

**Streamlit Problem**: Continuous re-execution, slow, unstable

**Shiny Solution**: Explicit refresh button, in-memory data, instant interactions

**Key Workflow**:
1. Click refresh (once)
2. Use app (instant)
3. Click refresh again when you want fresh data

**Result**: Fast, stable, predictable dashboard that YOU control!
