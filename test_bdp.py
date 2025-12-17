"""Quick test of bulk BDP speed."""
import time

start = time.time()

from xbbg import blp
import pandas as pd

# Test with your actual tickers
tickers = ['USOSFR10 Curncy', 'USOSFR5 Curncy', 'EUXOQQ1 Curncy']

print(f"Fetching {len(tickers)} tickers with bulk BDP...")
result = blp.bdp(tickers=tickers, flds='PX_LAST')

elapsed = time.time() - start
print(f"\n✓ Completed in {elapsed:.2f} seconds")
print(f"\nResult:\n{result}")

# Extract prices
prices = {}
for ticker in tickers:
    if ticker in result.index:
        price = result.loc[ticker, 'px_last']
        if pd.notna(price):
            prices[ticker] = float(price)

print(f"\nPrices dict: {prices}")
