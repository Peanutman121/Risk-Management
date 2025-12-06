"""
Bloomberg data provider implementation.

Requires Bloomberg Terminal with API enabled.
Uses blpapi for connection to Bloomberg data services.
"""

from typing import Optional, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_provider import DataProvider
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BBGDataProvider(DataProvider):
    """
    Bloomberg data provider implementation.

    Connects to Bloomberg Terminal API to retrieve market data.
    """

    def __init__(self, host: str = "localhost", port: int = 8194, timeout: int = 5000):
        """
        Initialize Bloomberg connection.

        Args:
            host: Bloomberg API host
            port: Bloomberg API port
            timeout: Connection timeout in milliseconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self._connected = False

        try:
            # Try to import Bloomberg library
            # Using xbbg as it's easier to use than raw blpapi
            import xbbg
            from xbbg import blp
            self.blp = blp
            self._bbg_available = True
            logger.info("Bloomberg library (xbbg) loaded successfully")
        except ImportError:
            logger.warning("Bloomberg library (xbbg) not available. Install with: pip install xbbg")
            self._bbg_available = False
            self.blp = None

    def _check_connection(self):
        """Check if Bloomberg is available."""
        if not self._bbg_available:
            raise ConnectionError(
                "Bloomberg library not installed. Install xbbg: pip install xbbg\n"
                "Or use in-house data provider instead."
            )

    def get_live_price(self, ticker: str) -> Optional[float]:
        """
        Get current market price from Bloomberg.

        Args:
            ticker: Bloomberg ticker (e.g., "USSW10 Curncy")

        Returns:
            Current price, or None if unavailable
        """
        self._check_connection()

        try:
            # Use BDP (Bloomberg Data Point) for current price
            result = self.blp.bdp(tickers=ticker, flds='PX_LAST')

            if result is not None and not result.empty:
                price = result.loc[ticker, 'px_last']
                return float(price) if not pd.isna(price) else None
            else:
                logger.warning(f"No data returned for ticker: {ticker}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving live price for {ticker}: {e}")
            return None

    def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Get historical daily data from Bloomberg.

        Args:
            ticker: Bloomberg ticker
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with DatetimeIndex and 'price' column
        """
        self._check_connection()

        try:
            # Use BDH (Bloomberg Data History) for historical prices
            result = self.blp.bdh(
                tickers=ticker,
                flds='PX_LAST',
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d')
            )

            if result is not None and not result.empty:
                # BDH returns multi-index DataFrame, flatten it
                df = result.copy()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(0)  # Remove ticker level

                # Rename column to 'price'
                df = df.rename(columns={'px_last': 'price'})

                return df
            else:
                logger.warning(f"No historical data for {ticker} from {start_date} to {end_date}")
                return pd.DataFrame(columns=['price'])

        except Exception as e:
            logger.error(f"Error retrieving historical data for {ticker}: {e}")
            return pd.DataFrame(columns=['price'])

    def get_historical_data_days(self, ticker: str, days: int) -> pd.DataFrame:
        """
        Get historical data for last N trading days.

        Args:
            ticker: Bloomberg ticker
            days: Number of trading days

        Returns:
            DataFrame with DatetimeIndex and 'price' column
        """
        # Calculate approximate calendar days (trading days * 1.4 to account for weekends)
        calendar_days = int(days * 1.4) + 10  # Add buffer
        end_date = datetime.now()
        start_date = end_date - timedelta(days=calendar_days)

        df = self.get_historical_data(ticker, start_date, end_date)

        # Return last N rows (actual trading days)
        if not df.empty and len(df) > days:
            return df.tail(days)
        else:
            return df

    def calculate_daily_vol(self, ticker: str, lookback: int = 60) -> Optional[float]:
        """
        Calculate daily volatility in basis points.

        Args:
            ticker: Bloomberg ticker
            lookback: Number of trading days

        Returns:
            Daily vol in bp, or None if insufficient data
        """
        try:
            df = self.get_historical_data_days(ticker, lookback)

            if df.empty or len(df) < 2:
                logger.warning(f"Insufficient data for vol calculation: {ticker}")
                return None

            # Calculate daily changes in basis points
            prices = df['price'].values
            changes_bp = np.diff(prices) * 100  # Convert to bp (assuming prices in %)

            # Calculate standard deviation
            daily_vol = np.std(changes_bp, ddof=1)

            return float(daily_vol)

        except Exception as e:
            logger.error(f"Error calculating daily vol for {ticker}: {e}")
            return None

    def calculate_annual_vol(self, ticker: str, lookback: int = 60) -> Optional[float]:
        """
        Calculate annualized volatility in basis points.

        Args:
            ticker: Bloomberg ticker
            lookback: Number of trading days

        Returns:
            Annual vol in bp, or None if insufficient data
        """
        daily_vol = self.calculate_daily_vol(ticker, lookback)

        if daily_vol is None:
            return None

        # Annualize: daily_vol * sqrt(252)
        annual_vol = daily_vol * np.sqrt(252)

        return float(annual_vol)

    def calculate_zscore(self, ticker: str, lookback: int = 63) -> Optional[float]:
        """
        Calculate z-score of current level vs 3-month history.

        Args:
            ticker: Bloomberg ticker
            lookback: Number of trading days (default 63 = ~3 months)

        Returns:
            Z-score, or None if insufficient data
        """
        try:
            # Get current price
            current_price = self.get_live_price(ticker)
            if current_price is None:
                return None

            # Get historical data
            df = self.get_historical_data_days(ticker, lookback)

            if df.empty or len(df) < 2:
                logger.warning(f"Insufficient data for z-score calculation: {ticker}")
                return None

            # Calculate mean and std of historical prices
            mean = df['price'].mean()
            std = df['price'].std(ddof=1)

            if std == 0:
                logger.warning(f"Zero standard deviation for {ticker}")
                return None

            # Calculate z-score
            zscore = (current_price - mean) / std

            return float(zscore)

        except Exception as e:
            logger.error(f"Error calculating z-score for {ticker}: {e}")
            return None

    def get_correlation(
        self,
        ticker1: str,
        ticker2: str,
        lookback: int = 60
    ) -> Optional[float]:
        """
        Calculate correlation between two tickers.

        Args:
            ticker1: First ticker
            ticker2: Second ticker
            lookback: Number of trading days

        Returns:
            Correlation coefficient, or None if insufficient data
        """
        try:
            # Get historical data for both tickers
            df1 = self.get_historical_data_days(ticker1, lookback)
            df2 = self.get_historical_data_days(ticker2, lookback)

            if df1.empty or df2.empty:
                return None

            # Merge on date
            df = pd.merge(
                df1[['price']],
                df2[['price']],
                left_index=True,
                right_index=True,
                suffixes=('_1', '_2')
            )

            if len(df) < 2:
                return None

            # Calculate daily changes
            df['change_1'] = df['price_1'].diff()
            df['change_2'] = df['price_2'].diff()

            # Drop first row (NaN from diff)
            df = df.dropna()

            if len(df) < 2:
                return None

            # Calculate correlation
            corr = df['change_1'].corr(df['change_2'])

            return float(corr) if not pd.isna(corr) else None

        except Exception as e:
            logger.error(f"Error calculating correlation between {ticker1} and {ticker2}: {e}")
            return None

    def get_correlation_matrix(
        self,
        tickers: List[str],
        lookback: int = 60
    ) -> Optional[pd.DataFrame]:
        """
        Calculate correlation matrix for multiple tickers.

        Args:
            tickers: List of tickers
            lookback: Number of trading days

        Returns:
            Correlation matrix DataFrame, or None if insufficient data
        """
        try:
            # Get historical data for all tickers
            all_data = {}
            for ticker in tickers:
                df = self.get_historical_data_days(ticker, lookback)
                if not df.empty:
                    all_data[ticker] = df['price']

            if not all_data:
                return None

            # Create DataFrame with all tickers
            df = pd.DataFrame(all_data)

            # Calculate daily changes
            changes = df.diff().dropna()

            if changes.empty:
                return None

            # Calculate correlation matrix
            corr_matrix = changes.corr()

            return corr_matrix

        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return None

    def is_available(self) -> bool:
        """
        Check if Bloomberg is available.

        Returns:
            True if Bloomberg can be accessed
        """
        if not self._bbg_available:
            return False

        try:
            # Try a simple query
            test_ticker = "USSW10 Curncy"
            result = self.get_live_price(test_ticker)
            return result is not None
        except Exception:
            return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Bloomberg"
