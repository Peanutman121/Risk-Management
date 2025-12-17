"""Test different fetch methods for speed."""
import time

from xbbg import blp
from datetime import datetime, timedelta

tickers = ['USOSFR10 Curncy', 'USOSFR5 Curncy', 'EUXOQQ1 Curncy']

# Method 1: BDP (live point data)
print("Method 1: BDP (live)")
start = time.time()
try:
    result = blp.bdp(tickers=tickers, flds='PX_LAST')
    elapsed = time.time() - start
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Result:\n{result}")
except Exception as e:
    print(f"  Error: {e}")

# Method 2: BDH with 1 day
print("\nMethod 2: BDH (1 day)")
start = time.time()
try:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    result = blp.bdh(
        tickers=tickers,
        flds='PX_LAST',
        start_date=start_date.strftime('%Y%m%d'),
        end_date=end_date.strftime('%Y%m%d')
    )
    elapsed = time.time() - start
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Shape: {result.shape}")
except Exception as e:
    print(f"  Error: {e}")

# Method 3: BDH with 3 days
print("\nMethod 3: BDH (3 days)")
start = time.time()
try:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    result = blp.bdh(
        tickers=tickers,
        flds='PX_LAST',
        start_date=start_date.strftime('%Y%m%d'),
        end_date=end_date.strftime('%Y%m%d')
    )
    elapsed = time.time() - start
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Shape: {result.shape}")
except Exception as e:
    print(f"  Error: {e}")
