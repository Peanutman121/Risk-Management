"""
Configuration settings for Portfolio Risk Management System
"""

import os
from pathlib import Path

# =============================================================================
# PROJECT PATHS
# =============================================================================

# Base directory (parent of python folder)
BASE_DIR = Path(__file__).parent.parent

# Excel file locations
EXCEL_DIR = BASE_DIR / "excel"
TRADER_FILES = {
    1: EXCEL_DIR / "positions_trader1.xlsx",
    2: EXCEL_DIR / "positions_trader2.xlsx",
    3: EXCEL_DIR / "positions_trader3.xlsx",
    4: EXCEL_DIR / "positions_trader4.xlsx",
    5: EXCEL_DIR / "positions_trader5.xlsx",
}

# Data directory
DATA_DIR = BASE_DIR / "data"
SVB_STRESS_FILE = DATA_DIR / "svb_stress_moves.csv"

# Template file
TEMPLATE_FILE = EXCEL_DIR / "template.xlsx"

# =============================================================================
# DATA PROVIDER SETTINGS
# =============================================================================

# Data provider selection: "BBG" (Bloomberg) or "INHOUSE" (custom implementation)
DATA_PROVIDER = "BBG"

# Fetch live prices from Bloomberg API when Streamlit loads?
# True = Fetch from BBG API on startup (fast bulk fetch, ~1-2s)
# False = Read prices from Excel's current_level column only
# PERFORMANCE: Set to False to prevent freezing on dropdown clicks
FETCH_LIVE_PRICES = False

# Bloomberg API settings (only used if DATA_PROVIDER = "BBG")
BBG_HOST = "localhost"
BBG_PORT = 8194
BBG_TIMEOUT = 5000  # milliseconds

# In-house data provider settings (only used if DATA_PROVIDER = "INHOUSE")
INHOUSE_CONNECTION_STRING = ""  # TODO: Add your connection string
INHOUSE_TICKER_MAP_FILE = DATA_DIR / "ticker_mapping.csv"  # BBG ticker → internal ticker mapping

# =============================================================================
# RISK PARAMETERS
# =============================================================================

# Default portfolio volatility target ($mm)
DEFAULT_VOL_TARGET = 50.0

# Default correlation assumption (used when correlation matrix not available)
DEFAULT_CORRELATION = 0.2

# Use live correlation matrix from market data (True) or fixed DEFAULT_CORRELATION (False)
# PERFORMANCE: Set to False to prevent freezing on dropdown clicks (Bloomberg API call is slow)
USE_LIVE_CORRELATIONS = False

# Require live correlations - fail report generation if correlation matrix unavailable (strict mode)
# PERFORMANCE: Set to False when USE_LIVE_CORRELATIONS is False
REQUIRE_LIVE_CORRELATIONS = False

# Risk-free rate for Sharpe calculation (%)
RISK_FREE_RATE = 0.05

# =============================================================================
# CALCULATION PARAMETERS
# =============================================================================

# Historical data lookback periods (trading days)
VOL_LOOKBACK_DAYS = 60  # For volatility calculation (~3 months)
ZSCORE_LOOKBACK_DAYS = 63  # 3 months for z-score
CORRELATION_LOOKBACK_DAYS = 60  # For correlation calculation (~3 months, ~126 for 6 months, ~252 for 1 year)

# Trading days per year (for annualization)
TRADING_DAYS_PER_YEAR = 252

# Time horizons for drawdown calculations
DRAWDOWN_HORIZONS = {
    '1d': {'label': '1 Day', 'periods_per_year': 252},
    '1w': {'label': '1 Week', 'periods_per_year': 52},
    '2w': {'label': '2 Weeks', 'periods_per_year': 26},
    '1m': {'label': '1 Month', 'periods_per_year': 12},
}

# =============================================================================
# PRODUCT TYPES
# =============================================================================

# Product type definitions with conventions:
#   quote_type: "rate_pct" (e.g., 3.9%), "bp" (e.g., 15bp), "price" (e.g., 95.50)
#   direction_type: "pay_rec" (Pay/Rec) or "long_short" (Long/Short)
#   pnl_sign: +1 means higher quote = profit for "Pay"/"Long", -1 means inverse
#
# P&L Logic:
#   Swaps (Pay/Rec): Pay = profit when rates/spreads UP, Rec = profit when rates/spreads DOWN
#   Futures (Long/Short): Long = profit when price UP, Short = profit when price DOWN

PRODUCT_TYPES = {
    'IR Swap': {
        'quote_type': 'rate_pct',      # Quoted in % (e.g., 3.9 = 3.9%)
        'direction_type': 'pay_rec',    # Pay = want rates up, Rec = want rates down
        'bp_multiplier': 100,           # 1% = 100bp, so rate_change * 100 = bp change
        'description': 'Interest Rate Swap (fixed vs floating)'
    },
    'Basis': {
        'quote_type': 'bp',             # Already in bp (e.g., 15 = 15bp)
        'direction_type': 'pay_rec',    # Pay = want spread wider, Rec = want spread tighter
        'bp_multiplier': 1,             # Already in bp
        'description': 'Basis Swap (e.g., 3s6s basis)'
    },
    'XCCY': {
        'quote_type': 'bp',             # Already in bp (e.g., -30 = -30bp)
        'direction_type': 'pay_rec',    # Pay = want spread wider, Rec = want spread tighter
        'bp_multiplier': 1,             # Already in bp
        'description': 'Cross-Currency Basis Swap'
    },
    'ASW': {
        'quote_type': 'bp',             # Already in bp (e.g., 45 = 45bp)
        'direction_type': 'pay_rec',    # Pay = want spread wider, Rec = want spread tighter
        'bp_multiplier': 1,             # Already in bp
        'description': 'Asset Swap Spread'
    },
    'Futures': {
        'quote_type': 'price',          # Quoted as price (e.g., 95.50)
        'direction_type': 'long_short', # Long = want price up, Short = want price down
        'bp_multiplier': 100,           # Price change * 100 = bp equivalent
        'description': 'Interest Rate Futures (SOFR, Euribor, etc.)'
    },
}

# Default product type if not specified
DEFAULT_PRODUCT_TYPE = 'IR Swap'

# Valid directions by product type
VALID_DIRECTIONS = {
    'pay_rec': ['Pay', 'Rec'],
    'long_short': ['Long', 'Short'],
}

# =============================================================================
# EXCEL SHEET NAMES
# =============================================================================

SHEET_POSITIONS = "Positions"
SHEET_SETTINGS = "Settings"
SHEET_REPORT = "Report"

# =============================================================================
# EXCEL COLUMN MAPPINGS
# =============================================================================

# Positions sheet columns (zero-indexed for pandas)
POSITIONS_COLUMNS = {
    'trade_id': 'A',
    'status': 'B',
    'headline': 'C',
    'ticker': 'D',
    'entry_date': 'E',
    'entry_level': 'F',
    'current_level': 'G',
    'bpv': 'H',
    'direction': 'I',
    'tp_level': 'J',
    'tp_type': 'K',
    'trailing_offset': 'L',
    'stop_level': 'M',
    'rationale_type': 'N',
    'rationale_notes': 'O',
    'score_1': 'P',
    'score_2': 'Q',
    'score_3': 'R',
    'score_4': 'S',
    'score_5': 'T',
    'score_6': 'U',
    'score_7': 'V',
    'score_8': 'W',
    'score_9': 'X',
    'total_score': 'Y',
    'exit_date': 'Z',
    'exit_level': 'AA',
    'pnl': 'AB',
    'postmortem': 'AC',
}

# Settings sheet cell locations
SETTINGS_CELLS = {
    'trader_name': 'B1',
    'risk_limit': 'B2',
    'default_correlation': 'B3',
    'excel_file_path': 'B4',
}

# =============================================================================
# STREAMLIT DASHBOARD SETTINGS
# =============================================================================

# Dashboard title
DASHBOARD_TITLE = "Portfolio Risk Management Dashboard"

# Page refresh interval (seconds) - set to None for manual refresh only
AUTO_REFRESH_INTERVAL = None

# Chart color scheme
CHART_COLORS = {
    'positive': '#00CC96',  # Green
    'negative': '#EF553B',  # Red
    'neutral': '#636EFA',   # Blue
    'warning': '#FFA15A',   # Orange
}

# =============================================================================
# WARNINGS AND ALERTS
# =============================================================================

# Alert threshold: warn if position is within X% of stop level
STOP_WARNING_THRESHOLD = 0.20  # 20%

# Alert threshold: warn if risk utilization exceeds X%
RISK_UTIL_WARNING_THRESHOLD = 0.90  # 90%

# High correlation threshold (for overlap detection)
HIGH_CORRELATION_THRESHOLD = 0.50  # 50%

# =============================================================================
# DATA PROVIDER FACTORY
# =============================================================================

def get_data_provider():
    """
    Factory function to get the configured data provider.

    Returns:
        DataProvider: Instance of the configured data provider

    Raises:
        ValueError: If DATA_PROVIDER is not recognized
    """
    if DATA_PROVIDER == "BBG":
        from bbg_data import BBGDataProvider
        return BBGDataProvider(host=BBG_HOST, port=BBG_PORT, timeout=BBG_TIMEOUT)
    elif DATA_PROVIDER == "INHOUSE":
        from inhouse_data import InHouseDataProvider
        return InHouseDataProvider(
            connection_string=INHOUSE_CONNECTION_STRING,
            ticker_map_file=INHOUSE_TICKER_MAP_FILE
        )
    else:
        raise ValueError(f"Unknown data provider: {DATA_PROVIDER}. Must be 'BBG' or 'INHOUSE'")


# =============================================================================
# PRODUCT PARSING
# =============================================================================

def parse_product_from_ticker(ticker: str) -> str:
    """
    Parse product/currency from Bloomberg ticker.

    Examples:
        USSW10 Curncy -> USD Swaps
        EUSA5 Curncy -> EUR Swaps
        BPSW2 Curncy -> GBP Swaps

    Args:
        ticker: Bloomberg ticker string

    Returns:
        Product description
    """
    ticker_upper = ticker.upper()

    # USD Swaps
    if ticker_upper.startswith('USSW'):
        return 'USD Swaps'
    # EUR Swaps
    elif ticker_upper.startswith('EUSA'):
        return 'EUR Swaps'
    # GBP Swaps
    elif ticker_upper.startswith('BPSW'):
        return 'GBP Swaps'
    # CHF Swaps
    elif ticker_upper.startswith('CHSW'):
        return 'CHF Swaps'
    # JPY Swaps
    elif ticker_upper.startswith('JYSW'):
        return 'JPY Swaps'
    # CAD Swaps
    elif ticker_upper.startswith('CDSW'):
        return 'CAD Swaps'
    # AUD Swaps
    elif ticker_upper.startswith('ADSW'):
        return 'AUD Swaps'
    # Default
    else:
        return 'Other'


def parse_tenor_from_ticker(ticker: str) -> str:
    """
    Parse tenor from Bloomberg ticker.

    Examples:
        USSW10 Curncy -> 10Y
        EUSA5 Curncy -> 5Y
        BPSW30 Curncy -> 30Y

    Args:
        ticker: Bloomberg ticker string

    Returns:
        Tenor string (e.g., "2Y", "10Y", "30Y")
    """
    import re

    # Extract numeric part
    match = re.search(r'(\d+)', ticker)
    if match:
        tenor_num = match.group(1)
        return f"{tenor_num}Y"
    else:
        return "Unknown"
