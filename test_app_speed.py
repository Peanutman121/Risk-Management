"""Test the updated Streamlit app price fetching."""
import time
import warnings
warnings.filterwarnings('ignore')

start_total = time.time()

# Simulate what Streamlit does
print("Loading modules...")
t1 = time.time()
from streamlit_app import load_all_traders, enrich_with_live_prices, calculate_position_pnl
print(f"  Modules loaded: {time.time()-t1:.2f}s")

print("\nLoading positions from Excel...")
t2 = time.time()
df = load_all_traders()
print(f"  Positions loaded: {time.time()-t2:.2f}s ({len(df)} rows)")

print("\nFetching live prices from Bloomberg...")
t3 = time.time()
df = enrich_with_live_prices(df)
print(f"  Prices fetched: {time.time()-t3:.2f}s")

print("\nCalculating P&L...")
t4 = time.time()
df['calc_pnl'] = df.apply(calculate_position_pnl, axis=1)
print(f"  P&L calculated: {time.time()-t4:.2f}s")

print("\n" + "=" * 50)
print(f"TOTAL TIME: {time.time()-start_total:.2f}s")
print("=" * 50)

print("\nPositions with P&L:")
print(df[['ticker', 'direction', 'entry_level', 'current_level', 'bpv', 'calc_pnl']].to_string())
print(f"\nTotal P&L: ${df['calc_pnl'].sum():,.0f}")
