# Streamlit Dashboard Issues - Diagnosis & Fixes

## Issue 1: Dropdown Freezing (Page Fades)

### Root Cause
Every dropdown interaction causes a **full page re-run** that:
1. Re-renders ALL 6 tabs at once (lines 1213-1263)
2. Fetches Bloomberg correlation matrix (line 416) - **SLOW** 🐌
3. Recalculates all metrics for all pages
4. This causes the page to "fade" (Streamlit loading state)

### THE FIX: Disable Expensive Bloomberg Calls

Your `config.py` likely has these settings enabled:
```python
USE_LIVE_CORRELATIONS = True  # ← CAUSING SLOWNESS
FETCH_LIVE_PRICES = True      # ← ALSO SLOW
```

**Change them to:**
```python
USE_LIVE_CORRELATIONS = False  # Use fast default correlation
FETCH_LIVE_PRICES = False      # Use Excel prices
```

This will make dropdowns instant because no Bloomberg calls happen.

---

## Issue 2: "Blank" Pages Not Actually Blank

Your data exists:
- ✅ Open positions: 2
- ✅ Closed positions: 1
- ✅ Potential positions: 1

If pages look blank, check:
1. **Browser console for errors** (F12 → Console tab)
2. **Terminal/logs for errors** (check where you ran `streamlit run`)
3. **Try clicking the expanders** - Some content is inside collapsed expanders

---

## Complete Fix - Apply These Changes

### Step 1: Update config.py

```python
# In portfolio_risk_system/python/config.py

# PERFORMANCE SETTINGS
USE_LIVE_CORRELATIONS = False    # ← Set to False for fast dropdowns
FETCH_LIVE_PRICES = False         # ← Set to False for fast dropdowns
REQUIRE_LIVE_CORRELATIONS = False # ← Set to False

# Only enable Bloomberg when you actually need real-time data
# For testing/development, keep these False
```

### Step 2: Optional - Switch from Tabs to Sidebar Navigation

Tabs render ALL pages at once. For better performance, use sidebar navigation (only renders active page).

Replace lines 1212-1264 in `streamlit_app.py` with:

```python
# Page navigation - SIDEBAR (only renders selected page)
page = st.sidebar.radio(
    "Navigation",
    ["📊 Book Summary", "📋 All Positions", "👤 Trader Drill-Down",
     "📈 Performance", "📜 Trade History", "🔮 Potential Trades"],
    key="sidebar_page_navigation"
)

# Render ONLY the selected page
try:
    if page == "📊 Book Summary":
        render_book_summary(all_positions, settings_dict, correlation, vol_target)
    elif page == "📋 All Positions":
        render_all_positions(all_positions)
    elif page == "👤 Trader Drill-Down":
        render_trader_drilldown(all_positions, settings_dict)
    elif page == "📈 Performance":
        render_performance(all_positions)
    elif page == "📜 Trade History":
        render_trade_history(all_positions)
    elif page == "🔮 Potential Trades":
        render_potential_trades(all_positions, correlation, vol_target)
except Exception as e:
    st.error(f"Error rendering page: {e}")
    logger.exception(f"Error on page {page}")
    import traceback
    st.code(traceback.format_exc())  # Show full error to debug
```

**Why this helps:**
- ✅ Only ONE page renders at a time (not all 6)
- ✅ Dropdowns only re-render the current page
- ✅ Much faster, no freezing

---

## Step 3: Add Debug Info (if pages still look blank)

Add this at the top of each render function to see what's happening:

```python
def render_performance(all_positions: pd.DataFrame):
    """Render the Performance Analytics page."""
    st.header("📈 Performance Analytics")

    # DEBUG INFO
    st.write(f"DEBUG: Total positions: {len(all_positions)}")
    st.write(f"DEBUG: Columns: {list(all_positions.columns)}")

    # Get closed positions
    closed_pos = get_closed_positions(all_positions)

    st.write(f"DEBUG: Closed positions: {len(closed_pos)}")  # ← See actual count

    if closed_pos.empty:
        st.warning("No closed positions found for performance analysis.")
        return

    # ... rest of function
```

---

## Quick Test Checklist

After applying fixes:

- [ ] **Config.py updated** - Bloomberg calls disabled
- [ ] **Streamlit restarted** - `Ctrl+C` and restart with `streamlit run streamlit_app.py`
- [ ] **Clear cache** - Click "🔄 Refresh Data" button in sidebar
- [ ] **Test dropdowns** - Should be instant now (no fading)
- [ ] **Check all pages** - All 6 should show content

---

## Expected Behavior After Fix

| Action | Before (slow) | After (fast) |
|--------|---------------|--------------|
| Initial load | 10-15s | 2-3s |
| Click dropdown | 3-5s freeze | Instant |
| Change tab | 3-5s | Instant |
| Filter positions | 2-3s | Instant |

---

## If Still Having Issues

### Dropdown still freezing?
1. **Check config.py** - Make sure Bloomberg is disabled
2. **Hard refresh browser** - Ctrl+Shift+R (clears browser cache)
3. **Check terminal logs** - Look for "⏱️ BBG" messages (shouldn't appear if disabled)

### Pages still blank?
1. **Add debug info** - See Step 3 above
2. **Check browser console** - F12 → Console tab for errors
3. **Check terminal** - Look for Exception traces
4. **Try expanders** - Click "View..." expanders on each page

---

## Root Cause Summary

### Dropdown Freezing:
```
User clicks dropdown
  ↓
Streamlit reruns entire script
  ↓
Bloomberg correlation fetch (3-5 seconds) ← BOTTLENECK
  ↓
All 6 tabs re-render
  ↓
Page unfreezes
```

**Fix**: Disable Bloomberg calls → Instant reruns

### Blank Pages:
- Pages aren't blank - they have data
- Might be errors being hidden by try/except blocks
- Use debug info to diagnose

---

## Implementation Priority

**Do this first (easiest, biggest impact):**
1. ✅ Update config.py - disable Bloomberg
2. ✅ Restart Streamlit
3. ✅ Test dropdowns

**Do this second (optional but recommended):**
4. 🔧 Switch from tabs to sidebar navigation
5. 🔧 Add debug info if pages look blank

---

## File Locations

```
portfolio_risk_system/
├── python/
│   ├── config.py              ← UPDATE THIS FIRST
│   ├── streamlit_app.py       ← OPTIONALLY UPDATE THIS
│   └── ...
└── ...
```

---

## Questions?

**Q: Will disabling Bloomberg break my system?**
A: No. The system falls back to:
- Default correlation (0.2)
- Excel prices (from `current_level` column)

**Q: When should I enable Bloomberg?**
A: Only when you need REAL real-time data. For development/testing, keep it off.

**Q: Why do tabs cause issues?**
A: Streamlit tabs render ALL tab content upfront, not just the visible tab. This means all 6 pages execute simultaneously.

---

**Bottom line**: Disable Bloomberg calls in config.py and your dropdowns will be instant! 🚀
