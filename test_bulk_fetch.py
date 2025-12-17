"""Test bulk price fetching speed."""
import time

# Test the bulk fetch
start = time.time()

from xbbg import blp
from datetime import datetime, timedelta

tickers = ['USOSFR10 Curncy', 'USOSFR5 Curncy', 'EUXOQQ1 Curncy', 'USSW10 Curncy', 'USSW5 Curncy']

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

print(f"Fetching prices for {len(tickers)} tickers...")
print(f"Date range: {start_date.strftime('%Y%m%d')} to {end_date.strftime('%Y%m%d')}")

result = blp.bdh(
    tickers=tickers,
    flds='PX_LAST',
    start_date=start_date.strftime('%Y%m%d'),
    end_date=end_date.strftime('%Y%m%d')
)

elapsed = time.time() - start
print(f"\n✓ Bulk fetch completed in {elapsed:.2f} seconds")

# Extract prices
prices = {}
if result is not None and not result.empty:
    for ticker in tickers:
        try:
            if (ticker, 'PX_LAST') in result.columns:
                col_data = result[(ticker, 'PX_LAST')].dropna()
                if len(col_data) > 0:
                    prices[ticker] = col_data.iloc[-1]
        except Exception as e:
            print(f"Error for {ticker}: {e}")

print(f"\nPrices fetched:")
for ticker, price in prices.items():
    print(f"  {ticker}: {price}")
