# Quick Start Guide

## Portfolio Risk Management System

This guide will get you up and running with the portfolio risk management system in minutes.

---

## For Traders: Using Excel

### 1. Open Your Excel File

Your personal position tracking file is located at:
```
excel/positions_trader<N>.xlsx
```

### 2. Enter a New Trade

1. Open the **Positions** sheet
2. Go to the first empty row
3. Fill in the required fields:
   - **Status**: Select "Open", "Closed", or "Potential"
   - **Headline**: Brief description (e.g., "Long 10y USD swap")
   - **Ticker**: Bloomberg ticker (e.g., "USSW10 Curncy")
   - **Entry Date**: When you entered the trade
   - **Entry Level**: Rate/price at entry
   - **BPV ($k)**: Position size in $k per basis point
   - **Direction**: "Long" or "Short"
   - **TP Level**: Take profit target
   - **Stop Level**: Stop loss level
   - **Rationale Type**: Choose from dropdown
   - **Rationale Notes**: Why you like this trade
   - **Scores 1-9**: Complete the trade scoring checklist

4. **Trade ID** and **Total Score** will auto-calculate
5. **P&L** will auto-calculate based on Current Level

### 3. Complete the Trade Scoring Checklist

For each trade, score these 9 factors (each worth 0 or 1 point):

1. **Directional Conviction**: Does macro view support the trade?
2. **Valuation Support**: Does your model show value here?
3. **Flow Supportive**: Are client flows/issuance supportive?
4. **Positioning Supportive**: Is market positioning favorable?
5. **Momentum/MR**: Is this momentum or mean reversion from extreme?
6. **Liquidity**: Can you get in/out cleanly?
7. **Entry Z-Score**: Auto-calculated (will be 0, 0.5, or 1)
8. **Timing/Seasonality**: Is there a catalyst or seasonal pattern?
9. **Area of Expertise**: Is this in your wheelhouse?

**Total Score** ranges from 0 to 9. Higher scores should correlate with better outcomes.

### 4. Mark Potential Trades

To analyze a trade before putting it on:

1. Enter the trade with Status = "Potential"
2. Fill in all fields as if it were live
3. Your report will show:
   - Impact on your risk budget
   - How much size you can safely add
   - Entry z-score and timing analysis

### 5. Close a Trade

When you exit a trade:

1. Change **Status** to "Closed"
2. Enter **Exit Date** and **Exit Level**
3. Add **Postmortem** notes (what worked, what didn't, lessons learned)

### 6. Generate Your Report

**Option A: From Excel**
- Click the "Generate Report" button (if configured)

**Option B: From Command Line**
```bash
cd portfolio_risk_system
python python/xlwings_report.py --trader <N>
```

Replace `<N>` with your trader number (1-5).

### 7. Review Your Report

Your report (in the **Report** sheet) includes:

- **Current Portfolio**: All open positions with P&L, vol, and risk metrics
- **Risk Metrics**: Portfolio vol, 2-sigma drawdowns (1d, 1w, 2w, 1m), risk utilization
- **SVB Stress Scenario**: How you'd do in March 2023 SVB crisis
- **Performance**: Win rate, avg win/loss, P&L statistics
- **Score Analysis**: Do higher-scored trades actually perform better?
- **Potential Trades**: Impact of adding potential positions to your book

---

## For Portfolio Manager: Using the Dashboard

### 1. Launch the Dashboard

```bash
cd portfolio_risk_system
streamlit run python/streamlit_app.py
```

The dashboard will open in your web browser at `http://localhost:8501`

### 2. Navigate the Dashboard

The dashboard has 6 pages accessible via the top navigation:

#### 📊 **Book Summary**
- Aggregate metrics across all 5 traders
- Total book vol, headroom, P&L
- 2-Sigma drawdowns for 1d, 1w, 2w, 1m horizons
- SVB stress scenario impact
- Risk breakdown by trader and product

#### 📋 **All Positions**
- View all positions across all traders
- Filter by trader, status, product, direction
- Detect overlaps (opposite positions) and concentrations

#### 👤 **Trader Drill-Down**
- Select a trader from dropdown
- See their complete book
- Open positions, potential trades, risk metrics

#### 📈 **Performance Analytics**
- P&L by trader
- Performance by score range
- Performance by rationale type
- Identify what's working and what's not

#### 📜 **Trade History**
- All closed trades
- Filter by trader, rationale, outcome
- Export to CSV for further analysis

#### 🔮 **Potential Trades**
- See all potential trades across all traders
- Impact on overall book if added
- Whether they fit within risk budget

### 3. Adjust Settings

Use the **sidebar** to:
- Set **Portfolio Vol Target** ($mm)
- Adjust **Default Correlation** assumption
- **Refresh Data** button to reload from Excel files

### 4. Interpret Key Metrics

**Portfolio Vol**: Total annual volatility in dollars
- This is your primary risk metric
- Should stay below your vol target

**Risk Utilization**: Percentage of vol budget used
- < 80%: Comfortable
- 80-95%: High utilization
- > 95%: Very tight, limited capacity

**2-Sigma Drawdowns**:
- 1-day: 2-standard-deviation move over 1 day
- 1-week: 2-std-dev move over 1 week
- 2-week, 1-month: Same concept for longer horizons
- These represent stress loss scenarios (2% probability)

**SVB Stress P&L**: How the book would have performed during March 8-15, 2023 (SVB/Credit Suisse crisis)

---

## Common Tasks

### Add a New Trader

1. Copy `excel/template.xlsx` to `excel/positions_trader<N>.xlsx`
2. Update **Settings** sheet with trader name and risk limit
3. Add trader to `TRADER_FILES` dict in `python/config.py`

### Update SVB Stress Scenario

Edit `data/svb_stress_moves.csv`:
```csv
ticker,svb_move_bp,description
USSW10 Curncy,-50,USD 10Y Swap
...
```

Add any new tickers your desk trades.

### Switch Data Providers

Edit `python/config.py`:
```python
DATA_PROVIDER = "BBG"  # or "INHOUSE"
```

If using in-house data, implement `python/inhouse_data.py` (see comments in file).

---

## Troubleshooting

### xlwings not working

- **Windows**: Should work out of the box
- **Mac**: May need to install xlwings Excel add-in:
  ```bash
  xlwings addin install
  ```

### Dashboard shows no data

- Check that Excel files exist in `excel/` directory
- Check file paths in `python/config.py`
- Run `python python/xlwings_report.py --trader 1` to test

### Bloomberg API errors

- Ensure Bloomberg Terminal is running and logged in
- Check API permissions in Bloomberg
- Test with:
  ```python
  from xbbg import blp
  blp.bdp("USSW10 Curncy", "PX_LAST")
  ```

### P&L seems wrong

- Check direction (Long vs Short)
- Verify BPV is in $thousands
- Ensure Entry Level and Current Level are in correct format
- P&L formula assumes rates convention (price inverse to yield)

---

## Next Steps

1. **Traders**: Start entering your positions and generating daily reports
2. **PM**: Review the Book Summary page daily before market open
3. **Team**: Weekly review of Performance Analytics to identify patterns
4. **Everyone**: Use the scoring system consistently and review Score Analysis monthly

---

## Support

For issues or questions:
- Check the full documentation in `docs/`
- Review `README.md`
- Check logs in console output

---

**Built with**: Python, pandas, xlwings, Streamlit, openpyxl

**Version**: 1.0
