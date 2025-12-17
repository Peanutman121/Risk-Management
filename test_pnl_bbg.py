"""Test P&L calculation with live Bloomberg prices."""
import warnings
warnings.filterwarnings('ignore')

# Suppress streamlit warnings
import os
os.environ['STREAMLIT_LOG_LEVEL'] = 'error'

from streamlit_app import enrich_with_live_prices, load_all_traders, calculate_position_pnl

print("Loading positions...")
df = load_all_traders()

print("\nOriginal positions:")
print(df[['ticker', 'direction', 'entry_level', 'current_level', 'bpv_usd']].head(5))

print("\nEnriching with live Bloomberg prices...")
df = enrich_with_live_prices(df)

print("\nAfter enrichment:")
print(df[['ticker', 'direction', 'entry_level', 'current_level', 'bpv_usd']].head(5))

print("\nCalculating P&L...")
df['pnl'] = df.apply(calculate_position_pnl, axis=1)

print("\nPositions with P&L:")
cols = ['ticker', 'direction', 'Product', 'entry_level', 'current_level', 'bpv_usd', 'pnl']
available_cols = [c for c in cols if c in df.columns]
print(df[available_cols].to_string())

print(f"\n--- TOTAL P&L: ${df['pnl'].sum():,.2f} ---")
