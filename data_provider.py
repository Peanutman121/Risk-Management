"""
Abstract data provider interface for market data.

This module defines the interface that all data providers must implement.
Supports pluggable data sources (Bloomberg, in-house systems, etc.).
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List
import pandas as pd
from datetime import datetime, timedelta


class DataProvider(ABC):
    """
    Abstract base class for market data providers.

    All data providers (Bloomberg, in-house, etc.) must implement these methods.
    """

    @abstractmethod
    def get_live_price(self, ticker: str) -> Optional[float]:
        """
        Get current market price/level for a ticker.

        Args:
            ticker: Market ticker (e.g., "USSW10 Curncy")

        Returns:
            Current price/level, or None if unavailable

        Raises:
            ConnectionError: If data provider is unavailable
        """
        pass

    @abstractmethod
    def get_historical_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Get historical daily data for a ticker.

        Args:
            ticker: Market ticker
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with DatetimeIndex and 'price' column

        Raises:
            ConnectionError: If data provider is unavailable
            ValueError: If ticker is invalid
        """
        pass

    @abstractmethod
    def get_historical_data_days(
        self,
        ticker: str,
        days: int
    ) -> pd.DataFrame:
        """
        Get historical data for the last N trading days.

        Args:
            ticker: Market ticker
            days: Number of trading days to retrieve

        Returns:
            DataFrame with DatetimeIndex and 'price' column

        Raises:
            ConnectionError: If data provider is unavailable
            ValueError: If ticker is invalid
        """
        pass

    @abstractmethod
    def calculate_daily_vol(
        self,
        ticker: str,
        lookback: int = 60
    ) -> Optional[float]:
        """
        Calculate daily volatility in basis points.

        Args:
            ticker: Market ticker
            lookback: Number of trading days for calculation

        Returns:
            Daily volatility in bp, or None if insufficient data

        Raises:
            ConnectionError: If data provider is unavailable
        """
        pass

    @abstractmethod
    def calculate_annual_vol(
        self,
        ticker: str,
        lookback: int = 60
    ) -> Optional[float]:
        """
        Calculate annualized volatility in basis points.

        Args:
            ticker: Market ticker
            lookback: Number of trading days for calculation

        Returns:
            Annualized volatility in bp, or None if insufficient data

        Raises:
            ConnectionError: If data provider is unavailable
        """
        pass

    @abstractmethod
    def calculate_zscore(
        self,
        ticker: str,
        lookback: int = 63
    ) -> Optional[float]:
        """
        Calculate z-score of current level vs historical mean.

        Z-score = (current_level - mean) / std_dev
        Typically uses 3-month (63 trading days) lookback.

        Args:
            ticker: Market ticker
            lookback: Number of trading days for calculation

        Returns:
            Z-score, or None if insufficient data

        Raises:
            ConnectionError: If data provider is unavailable
        """
        pass

    @abstractmethod
    def get_correlation(
        self,
        ticker1: str,
        ticker2: str,
        lookback: int = 60
    ) -> Optional[float]:
        """
        Calculate correlation between two tickers.

        Based on correlation of daily price changes.

        Args:
            ticker1: First ticker
            ticker2: Second ticker
            lookback: Number of trading days for calculation

        Returns:
            Correlation coefficient [-1, 1], or None if insufficient data

        Raises:
            ConnectionError: If data provider is unavailable
        """
        pass

    @abstractmethod
    def get_correlation_matrix(
        self,
        tickers: List[str],
        lookback: int = 60
    ) -> Optional[pd.DataFrame]:
        """
        Calculate correlation matrix for multiple tickers.

        Args:
            tickers: List of tickers
            lookback: Number of trading days for calculation

        Returns:
            DataFrame with tickers as index and columns, or None if insufficient data

        Raises:
            ConnectionError: If data provider is unavailable
        """
        pass

    def is_available(self) -> bool:
        """
        Check if data provider is available and responding.

        Returns:
            True if provider is available, False otherwise
        """
        try:
            # Try to get a test price (override in subclass if needed)
            return True
        except Exception:
            return False

    def get_provider_name(self) -> str:
        """
        Get the name of this data provider.

        Returns:
            Provider name (e.g., "Bloomberg", "In-House")
        """
        return self.__class__.__name__
