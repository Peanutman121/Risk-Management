# Data Provider Implementation Guide

## Overview

The Portfolio Risk Management System uses a pluggable data provider architecture that allows you to switch between Bloomberg and in-house data systems.

This guide explains how to implement a custom in-house data provider.

---

## Architecture

### Abstract Interface

All data providers implement the `DataProvider` interface defined in `python/data_provider.py`:

```python
class DataProvider(ABC):
    def get_live_price(ticker: str) -> float
    def get_historical_data(ticker: str, start: datetime, end: datetime) -> DataFrame
    def get_historical_data_days(ticker: str, days: int) -> DataFrame
    def calculate_daily_vol(ticker: str, lookback: int) -> float
    def calculate_annual_vol(ticker: str, lookback: int) -> float
    def calculate_zscore(ticker: str, lookback: int) -> float
    def get_correlation(ticker1: str, ticker2: str, lookback: int) -> float
    def get_correlation_matrix(tickers: List[str], lookback: int) -> DataFrame
```

### Provided Implementations

1. **BBGDataProvider** (`python/bbg_data.py`): Uses Bloomberg API
2. **InHouseDataProvider** (`python/inhouse_data.py`): Stub for custom implementation

---

## Implementing In-House Data Provider

The file `python/inhouse_data.py` provides a template with clear TODOs. Follow these steps:

### Step 1: Define Connection String

Decide what information you need to connect to your data system:

```python
def __init__(self, connection_string: str = "", ticker_map_file: Path = None):
    self.connection_string = connection_string

    # TODO: Initialize connection
    # Example:
    # self.api_client = MyDataAPI(connection_string)
    # self.db_conn = psycopg2.connect(connection_string)
```

**Examples**:
- REST API: `"http://data.myorg.com:8080"`
- Database: `"postgresql://user:pass@host:5432/dbname"`
- File-based: `"/mnt/data/market_data"`

### Step 2: Implement Ticker Mapping

Bloomberg tickers must be mapped to your internal ticker format:

```python
def _translate_ticker(self, bbg_ticker: str) -> str:
    """
    Translate BBG ticker to internal ticker.

    Examples:
        "USSW10 Curncy" -> "USD_SWAP_10Y"
        "EUSA5 Curncy" -> "EUR_SWAP_5Y"
    """
    # Check mapping file first
    if bbg_ticker in self.ticker_map:
        return self.ticker_map[bbg_ticker]

    # TODO: Implement fallback logic
    # Parse ticker and convert to internal format
```

**Option A: Mapping File** (recommended)

Create `data/ticker_mapping.csv`:
```csv
bbg_ticker,internal_ticker
USSW10 Curncy,USD_SWAP_10Y
USSW5 Curncy,USD_SWAP_5Y
EUSA10 Curncy,EUR_SWAP_10Y
...
```

**Option B: Programmatic Translation**

```python
import re

def _translate_ticker(self, bbg_ticker: str) -> str:
    # Extract currency and tenor
    if "USSW" in bbg_ticker:
        tenor = re.search(r'(\d+)', bbg_ticker).group(1)
        return f"USD_SWAP_{tenor}Y"
    elif "EUSA" in bbg_ticker:
        tenor = re.search(r'(\d+)', bbg_ticker).group(1)
        return f"EUR_SWAP_{tenor}Y"
    # ... more patterns
```

### Step 3: Implement get_live_price

Retrieve current market price from your system:

```python
def get_live_price(self, ticker: str) -> Optional[float]:
    internal_ticker = self._translate_ticker(ticker)

    # TODO: Implement data retrieval
    # Example with REST API:
    response = requests.get(
        f"{self.api_url}/price/{internal_ticker}"
    )
    if response.status_code == 200:
        return response.json()['price']
    else:
        return None

    # Example with database:
    query = "SELECT price FROM live_prices WHERE ticker = %s"
    result = self.db_conn.execute(query, (internal_ticker,))
    return result.fetchone()[0] if result else None
```

### Step 4: Implement get_historical_data

Retrieve daily historical prices:

```python
def get_historical_data(
    self,
    ticker: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    internal_ticker = self._translate_ticker(ticker)

    # TODO: Implement historical data retrieval
    # Example with REST API:
    response = requests.get(
        f"{self.api_url}/history/{internal_ticker}",
        params={
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
    )
    df = pd.DataFrame(response.json())
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.rename(columns={'close': 'price'}, inplace=True)
    return df[['price']]

    # Example with database:
    query = """
        SELECT date, close_price as price
        FROM historical_prices
        WHERE ticker = %s AND date BETWEEN %s AND %s
        ORDER BY date
    """
    df = pd.read_sql(
        query,
        self.db_conn,
        params=(internal_ticker, start_date, end_date),
        index_col='date',
        parse_dates=['date']
    )
    return df
```

### Step 5: (Optional) Optimize Calculations

If your system provides pre-calculated metrics, override these methods:

```python
def calculate_annual_vol(self, ticker: str, lookback: int = 60) -> Optional[float]:
    internal_ticker = self._translate_ticker(ticker)

    # If your system calculates vol for you:
    response = requests.get(f"{self.api_url}/vol/{internal_ticker}")
    return response.json()['annual_vol_bp']

    # Otherwise, use default implementation that calculates from historical data
    # (already provided in template)
```

### Step 6: Implement Health Check

Add a health check to verify your data system is responding:

```python
def is_available(self) -> bool:
    try:
        # Ping your data system
        response = requests.get(f"{self.api_url}/health", timeout=2)
        return response.status_code == 200
    except:
        return False
```

### Step 7: Update Configuration

Edit `python/config.py`:

```python
# Switch to in-house provider
DATA_PROVIDER = "INHOUSE"

# Add your connection details
INHOUSE_CONNECTION_STRING = "http://data.myorg.com:8080"
INHOUSE_TICKER_MAP_FILE = DATA_DIR / "ticker_mapping.csv"
```

---

## Example: REST API Implementation

Here's a complete example for a REST API-based data provider:

```python
# python/inhouse_data.py

import requests
import pandas as pd
from datetime import datetime
from data_provider import DataProvider

class InHouseDataProvider(DataProvider):
    def __init__(self, connection_string: str = "", ticker_map_file = None):
        self.api_url = connection_string
        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Bearer YOUR_API_KEY'})

        # Load ticker mapping
        if ticker_map_file:
            df = pd.read_csv(ticker_map_file)
            self.ticker_map = dict(zip(df['bbg_ticker'], df['internal_ticker']))
        else:
            self.ticker_map = {}

    def _translate_ticker(self, bbg_ticker: str) -> str:
        return self.ticker_map.get(bbg_ticker, bbg_ticker)

    def get_live_price(self, ticker: str) -> Optional[float]:
        internal_ticker = self._translate_ticker(ticker)

        try:
            response = self.session.get(
                f"{self.api_url}/v1/price",
                params={'ticker': internal_ticker}
            )
            response.raise_for_status()
            return float(response.json()['price'])
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {e}")
            return None

    def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        internal_ticker = self._translate_ticker(ticker)

        try:
            response = self.session.get(
                f"{self.api_url}/v1/history",
                params={
                    'ticker': internal_ticker,
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                }
            )
            response.raise_for_status()

            data = response.json()
            df = pd.DataFrame(data['prices'])
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.rename(columns={'close': 'price'}, inplace=True)

            return df[['price']]
        except Exception as e:
            logger.error(f"Error getting history for {ticker}: {e}")
            return pd.DataFrame(columns=['price'])

    # get_historical_data_days, calculate_daily_vol, etc.
    # use default implementations from template
```

---

## Example: Database Implementation

For a PostgreSQL database:

```python
import psycopg2
import pandas as pd
from data_provider import DataProvider

class InHouseDataProvider(DataProvider):
    def __init__(self, connection_string: str = "", ticker_map_file = None):
        self.conn = psycopg2.connect(connection_string)

        # Load ticker mapping
        # ...

    def get_live_price(self, ticker: str) -> Optional[float]:
        internal_ticker = self._translate_ticker(ticker)

        query = """
            SELECT price
            FROM market_data.live_prices
            WHERE ticker = %s
            AND timestamp = (
                SELECT MAX(timestamp)
                FROM market_data.live_prices
                WHERE ticker = %s
            )
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (internal_ticker, internal_ticker))
                result = cur.fetchone()
                return float(result[0]) if result else None
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None

    def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        internal_ticker = self._translate_ticker(ticker)

        query = """
            SELECT date, close_price as price
            FROM market_data.historical_prices
            WHERE ticker = %s
            AND date BETWEEN %s AND %s
            ORDER BY date
        """

        try:
            df = pd.read_sql(
                query,
                self.conn,
                params=(internal_ticker, start_date, end_date),
                index_col='date',
                parse_dates=['date']
            )
            return df
        except Exception as e:
            logger.error(f"Database error: {e}")
            return pd.DataFrame(columns=['price'])
```

---

## Testing Your Implementation

### 1. Test Connection

```python
from config import get_data_provider

provider = get_data_provider()
print(f"Provider: {provider.get_provider_name()}")
print(f"Available: {provider.is_available()}")
```

### 2. Test Live Price

```python
ticker = "USSW10 Curncy"
price = provider.get_live_price(ticker)
print(f"{ticker}: {price}")
```

### 3. Test Historical Data

```python
from datetime import datetime, timedelta

ticker = "USSW10 Curncy"
end = datetime.now()
start = end - timedelta(days=90)

df = provider.get_historical_data(ticker, start, end)
print(f"Retrieved {len(df)} days of data")
print(df.head())
```

### 4. Test Volatility Calculation

```python
ticker = "USSW10 Curncy"
daily_vol = provider.calculate_daily_vol(ticker)
annual_vol = provider.calculate_annual_vol(ticker)

print(f"Daily vol: {daily_vol:.2f} bp")
print(f"Annual vol: {annual_vol:.2f} bp")
```

### 5. Test Z-Score

```python
ticker = "USSW10 Curncy"
zscore = provider.calculate_zscore(ticker)
print(f"Z-score: {zscore:.2f}")
```

---

## Common Issues

### Ticker Mapping Errors

**Problem**: `No mapping found for ticker`

**Solution**:
- Add ticker to `data/ticker_mapping.csv`
- Or implement fallback logic in `_translate_ticker`

### Connection Timeouts

**Problem**: `Connection timeout`

**Solution**:
- Check network connectivity
- Verify API URL / database host
- Increase timeout in connection settings

### Data Format Mismatches

**Problem**: `KeyError: 'price'`

**Solution**:
- Ensure DataFrame has 'price' column
- Check that data is returned in expected format
- Add column renaming as needed

### Missing Data

**Problem**: `Insufficient data for calculation`

**Solution**:
- Verify ticker exists in your data system
- Check date range covers requested period
- Ensure no gaps in historical data

---

## Performance Optimization

### Caching

Implement caching for frequently accessed data:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_live_price(self, ticker: str) -> Optional[float]:
    # Cache expires after 60 seconds
    # Implementation...
```

### Batch Requests

If your API supports batch requests, implement `get_multiple_prices`:

```python
def get_multiple_prices(self, tickers: List[str]) -> Dict[str, float]:
    # Batch request for multiple tickers
    response = self.session.post(
        f"{self.api_url}/v1/prices/batch",
        json={'tickers': [self._translate_ticker(t) for t in tickers]}
    )
    return response.json()
```

### Connection Pooling

For database connections, use connection pooling:

```python
from psycopg2 import pool

self.conn_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    **connection_params
)
```

---

## Support

If you encounter issues implementing your data provider:

1. Check logs for detailed error messages
2. Test each method individually
3. Verify ticker mapping is correct
4. Ensure data system is accessible
5. Review Bloomberg data provider implementation as reference

---

**Remember**: The default implementations for `calculate_daily_vol`, `calculate_annual_vol`, `calculate_zscore`, and `get_correlation` work with raw historical data. You only need to implement `get_live_price` and `get_historical_data` for a basic working provider.
