"""
Streamlit Dashboard for Portfolio Risk Management.

Multi-page dashboard for portfolio manager to view aggregated risk
across all 5 traders.

PERFORMANCE OPTIMIZATIONS:
- Session state for data persistence (load once per session)
- Aggressive caching with appropriate TTLs
- Tabs instead of radio buttons for instant switching
- Lazy loading with expanders for heavy calculations
- Timing instrumentation for performance monitoring

Usage:
    streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import logging
import time

# Import our modules
from config import (
    TRADER_FILES,
    DEFAULT_VOL_TARGET,
    DEFAULT_CORRELATION,
    USE_LIVE_CORRELATIONS,
    REQUIRE_LIVE_CORRELATIONS,
    CORRELATION_LOOKBACK_DAYS,
    DASHBOARD_TITLE,
    parse_product_from_ticker,
    get_data_provider,
    FETCH_LIVE_PRICES
)
from xlwings_report import (
    read_positions_openpyxl,
    read_settings_openpyxl,
    get_open_positions,
    get_closed_positions,
    get_potential_positions
)
from risk_calcs import (
    calculate_position_vol,
    calculate_portfolio_vol_uniform,
    calculate_portfolio_vol,
    calculate_2sigma_drawdowns,
    calculate_pnl
)
from svb_stress_data import load_svb_scenario as _load_svb_scenario

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Cached SVB scenario loader
@st.cache_resource
def load_svb_scenario():
    """Load SVB scenario once and cache it."""
    return _load_svb_scenario()


# Cached data provider - singleton for Bloomberg connection
@st.cache_resource
def get_cached_data_provider():
    """Get data provider instance (cached singleton to avoid reconnecting)."""
    logger.info("⏱️ Creating data provider connection...")
    return get_data_provider()


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize session state variables for data persistence."""
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'all_positions' not in st.session_state:
        st.session_state.all_positions = None
    if 'settings_dict' not in st.session_state:
        st.session_state.settings_dict = None
    if 'live_prices' not in st.session_state:
        st.session_state.live_prices = {}
    if 'metrics_cache' not in st.session_state:
        st.session_state.metrics_cache = {}
    if 'load_times' not in st.session_state:
        st.session_state.load_times = {}


def safe_style_format(df: pd.DataFrame, format_dict: dict, **kwargs):
    """
    Safely format a DataFrame for display, handling None/NaN values.
    
    Args:
        df: DataFrame to format
        format_dict: Dictionary of column: format_string
        **kwargs: Additional arguments for style.format()
    
    Returns:
        Styled DataFrame (pandas Styler object)
    """
    df_copy = df.copy()
    
    # Fill NaN values for columns being formatted (convert to numeric first)
    for col in format_dict.keys():
        if col in df_copy.columns:
            df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce').fillna(0)
    
    # Fill string columns with empty string to avoid None issues
    for col in df_copy.columns:
        if col not in format_dict and df_copy[col].dtype == 'object':
            df_copy[col] = df_copy[col].fillna('')
    
    try:
        return df_copy.style.format(format_dict, na_rep='-', **kwargs)
    except Exception as e:
        logger.warning(f"Style format failed: {e}")
        return df_copy


# Page config
st.set_page_config(
    page_title=DASHBOARD_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# DATA LOADING (with aggressive caching and timing)
# =============================================================================

@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def fetch_live_prices(tickers: tuple) -> dict:
    """
    Fetch live prices from Bloomberg for all tickers in a single bulk call.
    Uses BDP (point data) which is fast for live prices.
    
    CACHED FOR 1 HOUR - prices fetched once per session.
    
    Args:
        tickers: Tuple of ticker strings (tuple for caching)
    
    Returns:
        Dict mapping ticker to price
    """
    start_time = time.time()
    prices = {}
    
    if not tickers:
        return prices
    
    try:
        from xbbg import blp
        
        # Single bulk BDP call for all tickers at once (~1 second for any number of tickers)
        result = blp.bdp(tickers=list(tickers), flds='PX_LAST')
        
        if result is not None and not result.empty:
            # Result has tickers as index, px_last as column
            for ticker in tickers:
                try:
                    if ticker in result.index:
                        price = result.loc[ticker, 'px_last']
                        if pd.notna(price):
                            prices[ticker] = float(price)
                except Exception as e:
                    logger.warning(f"Could not extract price for {ticker}: {e}")
                    
        elapsed = time.time() - start_time
        logger.info(f"⏱️ BBG prices: {elapsed:.2f}s for {len(prices)}/{len(tickers)} tickers")
        
    except Exception as e:
        logger.error(f"Error fetching live prices: {e}")
    
    return prices


def enrich_with_live_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich positions DataFrame with live prices from Bloomberg.
    Updates current_level column with live prices.
    
    Args:
        df: Positions DataFrame
    
    Returns:
        DataFrame with updated current_level values
    """
    df = df.copy()
    
    if 'ticker' not in df.columns:
        return df
    
    # Get unique tickers
    tickers = tuple(df['ticker'].dropna().unique().tolist())
    
    if not tickers:
        return df
    
    # Fetch live prices (cached)
    live_prices = fetch_live_prices(tickers)
    
    if live_prices:
        # Update current_level with live prices
        for idx, row in df.iterrows():
            ticker = row.get('ticker')
            if ticker and ticker in live_prices:
                df.at[idx, 'current_level'] = live_prices[ticker]
        
        logger.info(f"Updated {len(live_prices)} positions with live prices")
    
    return df


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def load_all_traders():
    """
    Load positions from all trader files.
    
    CACHED FOR 1 HOUR - Excel files only re-read on manual refresh.

    Returns:
        DataFrame with all positions from all traders
    """
    start_time = time.time()
    all_positions = []

    for trader_num, filepath in TRADER_FILES.items():
        if not filepath.exists():
            logger.warning(f"Trader file not found: {filepath}")
            continue

        try:
            # Read positions
            df = read_positions_openpyxl(filepath)

            # Add trader column
            df['trader_num'] = trader_num
            df['trader_name'] = f"Trader {trader_num}"

            all_positions.append(df)

        except Exception as e:
            logger.error(f"Error loading trader {trader_num}: {e}")

    if not all_positions:
        return pd.DataFrame()

    # Combine all
    combined = pd.concat(all_positions, ignore_index=True)

    elapsed = time.time() - start_time
    logger.info(f"⏱️ Excel load: {elapsed:.2f}s for {len(combined)} positions from {len(all_positions)} traders")

    return combined


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def load_all_settings():
    """Load settings from all trader files. CACHED FOR 1 HOUR."""
    start_time = time.time()
    all_settings = {}

    for trader_num, filepath in TRADER_FILES.items():
        if not filepath.exists():
            continue

        try:
            settings = read_settings_openpyxl(filepath)
            all_settings[trader_num] = settings
        except Exception as e:
            logger.error(f"Error loading settings for trader {trader_num}: {e}")

    elapsed = time.time() - start_time
    logger.info(f"⏱️ Settings load: {elapsed:.2f}s for {len(all_settings)} traders")

    return all_settings


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_portfolio_metrics(positions_hash: str, df_json: str) -> dict:
    """
    Pre-calculate and cache portfolio metrics.
    
    Uses hash of positions to cache results - only recalculates when data changes.
    """
    start_time = time.time()
    
    # Reconstruct dataframe from JSON
    df = pd.read_json(df_json, orient='records')
    
    if df.empty:
        return {'total_bpv': 0, 'total_vol': 0, 'total_pnl': 0, 'position_count': 0}
    
    metrics = {
        'total_bpv': df['bpv'].sum() if 'bpv' in df.columns else 0,
        'total_vol': df['position_vol'].sum() if 'position_vol' in df.columns else 0,
        'total_pnl': df['pnl'].sum() if 'pnl' in df.columns else 0,
        'position_count': len(df),
        'by_trader': df.groupby('trader')['bpv'].sum().to_dict() if 'trader' in df.columns else {},
        'by_product': df.groupby('product')['bpv'].sum().to_dict() if 'product' in df.columns else {},
    }
    
    elapsed = time.time() - start_time
    logger.info(f"⏱️ Metrics calc: {elapsed:.2f}s")
    
    return metrics


def calculate_position_vols_simple(df: pd.DataFrame, default_vol_bp: float = 50) -> pd.DataFrame:
    """
    Calculate position vols for all positions.
    Uses default vol if market data not available.
    """
    df = df.copy()

    # Use default vol assumption for demonstration
    df['annual_vol_bp'] = default_vol_bp

    # Calculate position vol
    df['position_vol'] = df.apply(
        lambda row: calculate_position_vol(row.get('bpv', 0), default_vol_bp)
        if not pd.isna(row.get('bpv'))
        else 0,
        axis=1
    )

    return df


def add_product_info(df: pd.DataFrame) -> pd.DataFrame:
    """Add product classification based on ticker."""
    df = df.copy()
    df['product'] = df['ticker'].apply(lambda x: parse_product_from_ticker(x) if pd.notna(x) else 'Unknown')
    return df


def calculate_position_pnl(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate P&L for all positions based on product type and direction.
    
    Uses entry_level, current_level, bpv, direction, and product columns.
    """
    df = df.copy()
    
    def calc_row_pnl(row):
        entry = row.get('entry_level')
        current = row.get('current_level')
        bpv = row.get('bpv')
        direction = row.get('direction', '')
        product = row.get('product', 'IR Swap')
        
        # Skip if missing required fields
        if pd.isna(entry) or pd.isna(current) or pd.isna(bpv):
            return 0
        
        try:
            return calculate_pnl(entry, current, bpv, direction, product)
        except Exception as e:
            logger.warning(f"Error calculating P&L: {e}")
            return 0
    
    df['pnl'] = df.apply(calc_row_pnl, axis=1)
    return df


# =============================================================================
# RISK CALCULATIONS
# =============================================================================

@st.cache_data(ttl=3600, show_spinner=False)  # Cache correlation matrix for 1 hour
def get_cached_correlation_matrix(tickers_tuple: tuple, lookback_days: int):
    """Fetch correlation matrix with caching to avoid repeated Bloomberg calls."""
    start = time.time()
    logger.info(f"⏱️ Fetching correlation matrix for {len(tickers_tuple)} tickers...")
    try:
        data_provider = get_cached_data_provider()  # Use cached provider
        tickers = list(tickers_tuple)
        corr_matrix = data_provider.get_correlation_matrix(tickers, lookback_days)
        elapsed = time.time() - start
        if corr_matrix is not None and not corr_matrix.empty:
            logger.info(f"✓ Fetched correlation matrix for {len(tickers)} tickers in {elapsed:.2f}s")
            return corr_matrix
        else:
            logger.warning(f"⚠ No correlation matrix returned after {elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Error fetching correlation matrix after {elapsed:.2f}s: {e}")
    return None


def calculate_book_metrics(open_positions: pd.DataFrame, correlation: float, vol_target: float) -> dict:
    """Calculate aggregate book metrics."""

    # Calculate portfolio vol (with live correlations if enabled)
    corr_matrix = None
    using_live_correlations = False
    
    if not open_positions.empty and 'position_vol' in open_positions.columns:
        vols = open_positions['position_vol'].dropna()
        if len(vols) > 0:
            # Try to get live correlation matrix if enabled (CACHED)
            if USE_LIVE_CORRELATIONS and 'ticker' in open_positions.columns:
                try:
                    tickers = open_positions['ticker'].dropna().unique().tolist()
                    if len(tickers) > 1:
                        # Use cached correlation matrix
                        corr_matrix = get_cached_correlation_matrix(tuple(sorted(tickers)), CORRELATION_LOOKBACK_DAYS)
                        if corr_matrix is not None and not corr_matrix.empty:
                            using_live_correlations = True
                            logger.info(f"✓ Using live correlation matrix ({CORRELATION_LOOKBACK_DAYS} day lookback)")
                        else:
                            logger.warning(f"⚠ WARNING: Could not retrieve correlation matrix, falling back to DEFAULT_CORRELATION={DEFAULT_CORRELATION}")
                            if REQUIRE_LIVE_CORRELATIONS:
                                raise ValueError("REQUIRE_LIVE_CORRELATIONS is True but correlation matrix unavailable")
                except Exception as e:
                    logger.error(f"⚠ WARNING: Error getting correlation matrix: {e}")
                    if REQUIRE_LIVE_CORRELATIONS:
                        raise ValueError(f"REQUIRE_LIVE_CORRELATIONS is True but failed to get correlations: {e}")
                    logger.warning(f"⚠ Falling back to DEFAULT_CORRELATION={DEFAULT_CORRELATION}")
            
            # Calculate portfolio vol
            portfolio_vol = calculate_portfolio_vol(
                open_positions, 
                correlation=correlation,
                corr_matrix=corr_matrix
            )
        else:
            portfolio_vol = 0
    else:
        portfolio_vol = 0

    # Calculate P&L
    total_pnl = 0
    if 'pnl' in open_positions.columns:
        total_pnl = open_positions['pnl'].sum()

    # Calculate headroom and utilization
    headroom = vol_target - portfolio_vol
    risk_util_pct = (portfolio_vol / vol_target) * 100 if vol_target > 0 else 0

    # Calculate drawdowns
    drawdowns = calculate_2sigma_drawdowns(portfolio_vol)

    # Expected return (assume 0.5 Sharpe for now)
    expected_return = portfolio_vol * 0.5

    # Book Sharpe
    book_sharpe = expected_return / portfolio_vol if portfolio_vol > 0 else 0

    correlation_method = "Live Market Data" if using_live_correlations else f"Fixed ({correlation})"
    
    return {
        'total_book_vol': portfolio_vol,
        'vol_headroom': headroom,
        'risk_util_pct': risk_util_pct,
        'total_pnl': total_pnl,
        'expected_return': expected_return,
        'book_sharpe': book_sharpe,
        'drawdown_1d': drawdowns['1d'],
        'drawdown_1w': drawdowns['1w'],
        'drawdown_2w': drawdowns['2w'],
        'drawdown_1m': drawdowns['1m'],
        'correlation_method': correlation_method,
        'using_live_correlations': using_live_correlations,
    }


# =============================================================================
# PAGE 1: BOOK SUMMARY
# =============================================================================

def render_book_summary(all_positions: pd.DataFrame, settings_dict: dict, correlation: float, vol_target: float):
    """Render the Book Summary page."""
    st.header("📊 Book Summary")

    # Filter to open positions
    open_pos = get_open_positions(all_positions)

    if open_pos.empty:
        st.warning("No open positions found.")
        return

    # Add position vols, product info, and calculate P&L
    open_pos = calculate_position_vols_simple(open_pos)
    open_pos = add_product_info(open_pos)
    open_pos = calculate_position_pnl(open_pos)

    # Calculate book metrics
    metrics = calculate_book_metrics(open_pos, correlation, vol_target)

    # Display correlation method warning/info
    if metrics['using_live_correlations']:
        st.success(f"✓ Using Live Correlation Matrix ({CORRELATION_LOOKBACK_DAYS} day lookback)")
    else:
        st.warning(f"⚠ Using Fixed Correlation Assumption: {correlation}")

    # Display top metrics as cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Book Vol", f"${metrics['total_book_vol']:,.0f}",
                 delta=f"{metrics['risk_util_pct']:.1f}% utilized")

    with col2:
        st.metric("Vol Headroom", f"${metrics['vol_headroom']:,.0f}")

    with col3:
        st.metric("Total P&L", f"${metrics['total_pnl']:,.0f}",
                 delta=f"Sharpe: {metrics['book_sharpe']:.2f}")

    with col4:
        st.metric("Expected Return", f"${metrics['expected_return']:,.0f}")

    st.divider()

    # 2-Sigma Drawdowns
    st.subheader("📉 2-Sigma Drawdowns")

    dd_data = {
        'Horizon': ['1 Day', '1 Week', '2 Weeks', '1 Month'],
        '2σ Drawdown ($)': [
            metrics['drawdown_1d'],
            metrics['drawdown_1w'],
            metrics['drawdown_2w'],
            metrics['drawdown_1m']
        ]
    }
    dd_df = pd.DataFrame(dd_data)
    st.dataframe(dd_df.style.format({'2σ Drawdown ($)': '${:,.0f}'}), use_container_width=True)

    st.divider()

    # SVB Stress Scenario
    st.subheader("⚠️ SVB/CS Stress Scenario (March 2023)")

    scenario = load_svb_scenario()
    stress_summary = scenario.get_portfolio_stress_summary(open_pos)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Portfolio Stress P&L", f"${stress_summary['total_stress_pnl']:,.0f}")
    with col2:
        st.metric("Worst Position", f"${stress_summary['worst_position']:,.0f}",
                 delta=stress_summary['worst_position_ticker'])
    with col3:
        st.metric("Best Position", f"${stress_summary['best_position']:,.0f}",
                 delta=stress_summary['best_position_ticker'])

    # Expandable stress detail
    with st.expander("View Stress P&L by Position"):
        stress_df = scenario.calculate_portfolio_stress_pnl(open_pos)
        stress_display = stress_df[stress_df['has_data']][['ticker', 'direction', 'bpv', 'svb_move', 'stress_pnl']]
        st.dataframe(stress_display.style.format({
            'bpv': '{:.0f}',
            'svb_move': '{:.0f}',
            'stress_pnl': '${:,.0f}'
        }), use_container_width=True)

    st.divider()

    # Risk by Trader
    st.subheader("👥 Risk by Trader")

    trader_risk = open_pos.groupby('trader_name').agg({
        'trade_id': 'count',
        'position_vol': 'sum',
        'pnl': 'sum'
    }).reset_index()

    trader_risk.columns = ['Trader', '# Positions', 'Vol ($)', 'P&L ($)']
    trader_risk['% of Book'] = (trader_risk['Vol ($)'] / metrics['total_book_vol'] * 100)

    st.dataframe(trader_risk.style.format({
        '# Positions': '{:.0f}',
        'Vol ($)': '${:,.0f}',
        'P&L ($)': '${:,.0f}',
        '% of Book': '{:.1f}%'
    }), use_container_width=True)

    # Bar chart - lazy loaded in expander
    with st.expander("📊 View Vol Chart by Trader", expanded=False):
        fig = px.bar(trader_risk, x='Trader', y='Vol ($)',
                     title="Vol Contribution by Trader",
                     color='% of Book',
                     color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Risk by Product
    st.subheader("🌍 Risk by Product")

    product_risk = open_pos.groupby('product').agg({
        'position_vol': 'sum'
    }).reset_index()

    product_risk.columns = ['Product', 'Vol ($)']
    product_risk['% of Book'] = (product_risk['Vol ($)'] / metrics['total_book_vol'] * 100)
    product_risk = product_risk.sort_values('Vol ($)', ascending=False)

    st.dataframe(product_risk.style.format({
        'Vol ($)': '${:,.0f}',
        '% of Book': '{:.1f}%'
    }), use_container_width=True)

    # Pie chart - lazy loaded in expander
    with st.expander("📊 View Product Distribution Chart", expanded=False):
        fig = px.pie(product_risk, values='Vol ($)', names='Product',
                    title='Vol by Product')
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE 2: ALL POSITIONS
# =============================================================================

def render_all_positions(all_positions: pd.DataFrame):
    """Render the All Positions page."""
    st.header("📋 All Positions")

    if all_positions.empty:
        st.warning("No positions found.")
        return

    # Add enrichment and calculate P&L
    all_positions = calculate_position_vols_simple(all_positions)
    all_positions = add_product_info(all_positions)
    all_positions = calculate_position_pnl(all_positions)

    # Filters
    st.subheader("Filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        traders_list = ['All'] + sorted(all_positions['trader_name'].unique().tolist())
        selected_traders = st.multiselect("Trader", traders_list, default=['All'], key="positions_filter_traders")

    with col2:
        statuses_list = ['All'] + sorted(all_positions['status'].dropna().unique().tolist())
        selected_status = st.selectbox("Status", statuses_list, key="positions_filter_status")

    with col3:
        products_list = ['All'] + sorted(all_positions['product'].unique().tolist())
        selected_product = st.selectbox("Product", products_list, key="positions_filter_product")

    with col4:
        # Get unique directions from data (Pay, Rec, Long, Short)
        directions_list = ['All'] + sorted(all_positions['direction'].dropna().unique().tolist())
        selected_direction = st.selectbox("Direction", directions_list, key="positions_filter_direction")

    # Apply filters
    filtered = all_positions.copy()

    if 'All' not in selected_traders and selected_traders:
        filtered = filtered[filtered['trader_name'].isin(selected_traders)]

    if selected_status != 'All':
        filtered = filtered[filtered['status'] == selected_status]

    if selected_product != 'All':
        filtered = filtered[filtered['product'] == selected_product]

    if selected_direction != 'All':
        filtered = filtered[filtered['direction'] == selected_direction]

    st.write(f"Showing {len(filtered)} positions")

    # Display table
    display_cols = [
        'trader_name', 'trade_id', 'headline', 'ticker', 'product', 'direction',
        'bpv', 'entry_level', 'current_level', 'pnl', 'position_vol',
        'total_score', 'entry_date'
    ]

    # Filter to available columns
    display_cols = [col for col in display_cols if col in filtered.columns]

    if not filtered.empty:
        # Fill NaN/None values before formatting to avoid format errors
        display_df = filtered[display_cols].copy()
        
        # Fill numeric columns with 0
        numeric_cols = ['bpv', 'entry_level', 'current_level', 'pnl', 'position_vol', 'total_score']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(0)
        
        # Fill string columns with empty string
        string_cols = ['trader_name', 'trade_id', 'headline', 'ticker', 'product', 'direction', 'entry_date']
        for col in string_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].fillna('')
        
        try:
            st.dataframe(
                display_df.style.format({
                    'bpv': '{:.0f}',
                    'entry_level': '{:.4f}',
                    'current_level': '{:.4f}',
                    'pnl': '${:,.0f}',
                    'position_vol': '${:,.0f}',
                    'total_score': '{:.1f}'
                }, na_rep='-'),
                use_container_width=True,
                height=600
            )
        except Exception as e:
            # Fallback to plain dataframe if styling fails
            st.warning(f"Table styling failed: {e}")
            st.dataframe(display_df, use_container_width=True, height=600)

    # Overlap Detection
    st.divider()
    st.subheader("🔍 Overlap Detection")

    open_filtered = get_open_positions(filtered)

    if not open_filtered.empty:
        # Group by ticker
        ticker_summary = open_filtered.groupby('ticker').agg({
            'trader_name': lambda x: ', '.join(x.unique()),
            'direction': lambda x: ', '.join(x.unique()),
            'bpv': 'sum',
            'trade_id': 'count'
        }).reset_index()

        ticker_summary.columns = ['Ticker', 'Traders', 'Directions', 'Total BPV', '# Positions']

        # Flag overlaps
        ticker_summary['Warning'] = ticker_summary.apply(
            lambda row: '⚠️ Opposite positions' if len(set(row['Directions'].split(', '))) > 1
                        else ('⚠️ Concentration' if row['# Positions'] > 1 else ''),
            axis=1
        )

        # Filter to only warnings
        warnings = ticker_summary[ticker_summary['Warning'] != '']

        if not warnings.empty:
            st.warning(f"Found {len(warnings)} position overlaps/concentrations")
            st.dataframe(warnings, use_container_width=True)
        else:
            st.success("No position overlaps detected")


# =============================================================================
# PAGE 3: TRADER DRILL-DOWN
# =============================================================================

def render_single_trader(trader_name: str, trader_pos: pd.DataFrame, settings: dict):
    """Render a single trader's positions section."""
    
    # Add enrichment and calculate P&L
    trader_pos = calculate_position_vols_simple(trader_pos)
    trader_pos = add_product_info(trader_pos)
    trader_pos = calculate_position_pnl(trader_pos)

    # Get open, closed, potential
    open_pos = get_open_positions(trader_pos)
    potential_pos = get_potential_positions(trader_pos)

    # Calculate portfolio vol
    if not open_pos.empty:
        vols = open_pos['position_vol'].dropna()
        if len(vols) > 0:
            port_vol = calculate_portfolio_vol_uniform(vols.values, settings.get('default_correlation', 0.2))
        else:
            port_vol = 0
    else:
        port_vol = 0

    # Display metrics
    risk_limit = settings.get('risk_limit', 10_000_000)
    risk_util = (port_vol / risk_limit) * 100 if risk_limit > 0 else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Open Positions", len(open_pos))

    with col2:
        st.metric("Portfolio Vol", f"${port_vol:,.0f}",
                 delta=f"{risk_util:.1f}% of limit")

    with col3:
        total_pnl = open_pos['pnl'].sum() if 'pnl' in open_pos.columns and not open_pos.empty else 0
        st.metric("Unrealised P&L", f"${total_pnl:,.0f}")

    with col4:
        st.metric("Potential Trades", len(potential_pos))

    # Open positions table
    if not open_pos.empty:
        display_cols = ['trade_id', 'headline', 'ticker', 'product', 'direction', 'bpv',
                       'entry_level', 'current_level', 'pnl', 'position_vol', 'total_score']
        display_cols = [col for col in display_cols if col in open_pos.columns]

        st.dataframe(
            safe_style_format(open_pos[display_cols], {
                'bpv': '{:.0f}',
                'entry_level': '{:.4f}',
                'current_level': '{:.4f}',
                'pnl': '${:,.0f}',
                'position_vol': '${:,.0f}',
                'total_score': '{:.1f}'
            }),
            use_container_width=True,
            height=min(400, 35 * (len(open_pos) + 1))
        )
    else:
        st.info("No open positions")

    # Potential trades (collapsed by default)
    if not potential_pos.empty:
        with st.expander(f"📋 Potential Trades ({len(potential_pos)})", expanded=False):
            display_cols = ['headline', 'ticker', 'product', 'direction', 'bpv', 'entry_level', 'total_score']
            display_cols = [col for col in display_cols if col in potential_pos.columns]

            st.dataframe(
                safe_style_format(potential_pos[display_cols], {
                    'bpv': '{:.0f}',
                    'entry_level': '{:.4f}',
                    'total_score': '{:.1f}'
                }),
                use_container_width=True
            )


def render_trader_drilldown(all_positions: pd.DataFrame, settings_dict: dict):
    """Render the Trader Drill-Down page with all traders in tabs."""
    st.header("👤 Trader Drill-Down")

    # Get all traders
    available_traders = sorted(all_positions['trader_name'].unique().tolist())
    if not available_traders:
        st.warning("No traders found in data")
        return
    
    # Create tabs for each trader
    trader_tabs = st.tabs(available_traders)
    
    for idx, trader_name in enumerate(available_traders):
        with trader_tabs[idx]:
            # Filter positions for this trader
            trader_pos = all_positions[all_positions['trader_name'] == trader_name].copy()
            
            if trader_pos.empty:
                st.info(f"No positions for {trader_name}")
                continue
            
            # Extract trader number from name
            try:
                trader_num = int(trader_name.split()[-1]) if trader_name.split()[-1].isdigit() else 1
            except:
                trader_num = 1
            
            # Get settings
            settings = settings_dict.get(trader_num, {})
            
            # Render this trader's section
            render_single_trader(trader_name, trader_pos, settings)


# =============================================================================
# PAGE 4: PERFORMANCE ANALYTICS
# =============================================================================

def render_performance(all_positions: pd.DataFrame):
    """Render the Performance Analytics page."""
    st.header("📈 Performance Analytics")

    # Get closed positions
    closed_pos = get_closed_positions(all_positions)

    if closed_pos.empty:
        st.warning("No closed positions found for performance analysis.")
        return

    # Calculate P&L if not already present
    if 'pnl' not in closed_pos.columns or closed_pos['pnl'].isna().all():
        st.warning("P&L data not available for closed positions.")
        return

    # Performance by trader - show summary first (fast)
    st.subheader("Performance by Trader")

    perf_by_trader = closed_pos.groupby('trader_name').agg({
        'trade_id': 'count',
        'pnl': ['sum', 'mean', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0]
    }).reset_index()

    perf_by_trader.columns = ['Trader', '# Trades', 'Total P&L', 'Avg P&L', 'Win Rate %']

    st.dataframe(perf_by_trader.style.format({
        '# Trades': '{:.0f}',
        'Total P&L': '${:,.0f}',
        'Avg P&L': '${:,.0f}',
        'Win Rate %': '{:.1f}%'
    }), use_container_width=True)

    st.divider()

    # Score Analysis - lazy load the detailed analysis
    with st.expander("📊 Score Analysis", expanded=False):
        if 'total_score' in closed_pos.columns:
            # Create score bins
            bins = [0, 3, 5, 7, 9]
            labels = ['0-3', '3-5', '5-7', '7-9']

            closed_pos_copy = closed_pos.copy()
            closed_pos_copy['score_range'] = pd.cut(closed_pos_copy['total_score'], bins=bins, labels=labels, include_lowest=True)

            score_analysis = closed_pos_copy.groupby('score_range', observed=True).agg({
                'trade_id': 'count',
                'pnl': ['mean', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0]
            }).reset_index()

            score_analysis.columns = ['Score Range', '# Trades', 'Avg P&L', 'Win Rate %']

            st.dataframe(score_analysis.style.format({
                '# Trades': '{:.0f}',
                'Avg P&L': '${:,.0f}',
                'Win Rate %': '{:.1f}%'
            }), use_container_width=True)

            # Chart
            fig = px.bar(score_analysis, x='Score Range', y='Avg P&L',
                         title='Average P&L by Score Range',
                         color='Win Rate %',
                         color_continuous_scale='RdYlGn')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No score data available")

    # Rationale Analysis - lazy load
    with st.expander("📊 Performance by Rationale Type", expanded=False):
        if 'rationale_type' in closed_pos.columns:
            rationale_analysis = closed_pos.groupby('rationale_type').agg({
                'trade_id': 'count',
                'pnl': ['mean', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0]
            }).reset_index()

            rationale_analysis.columns = ['Rationale', '# Trades', 'Avg P&L', 'Win Rate %']

            st.dataframe(rationale_analysis.style.format({
                '# Trades': '{:.0f}',
                'Avg P&L': '${:,.0f}',
                'Win Rate %': '{:.1f}%'
            }), use_container_width=True)
        else:
            st.info("No rationale data available")


# =============================================================================
# PAGE 5: TRADE HISTORY
# =============================================================================

def render_trade_history(all_positions: pd.DataFrame):
    """Render the Trade History page."""
    st.header("📜 Trade History")

    # Get closed positions
    closed_pos = get_closed_positions(all_positions)

    if closed_pos.empty:
        st.warning("No closed trades found.")
        return

    # Filters
    st.subheader("Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        traders_list = ['All'] + sorted(closed_pos['trader_name'].unique().tolist())
        selected_traders = st.multiselect("Trader", traders_list, default=['All'], key="history_filter_traders")

    with col2:
        if 'rationale_type' in closed_pos.columns:
            rationales_list = ['All'] + sorted(closed_pos['rationale_type'].dropna().unique().tolist())
            selected_rationale = st.selectbox("Rationale", rationales_list, key="history_filter_rationale")
        else:
            selected_rationale = 'All'

    with col3:
        outcomes_list = ['All', 'Winners', 'Losers']
        selected_outcome = st.selectbox("Outcome", outcomes_list, key="history_filter_outcome")

    # Apply filters
    filtered = closed_pos.copy()

    if 'All' not in selected_traders and selected_traders:
        filtered = filtered[filtered['trader_name'].isin(selected_traders)]

    if selected_rationale != 'All':
        filtered = filtered[filtered['rationale_type'] == selected_rationale]

    if selected_outcome == 'Winners':
        filtered = filtered[filtered['pnl'] > 0]
    elif selected_outcome == 'Losers':
        filtered = filtered[filtered['pnl'] < 0]

    st.write(f"Showing {len(filtered)} closed trades")

    # Display table
    display_cols = [
        'trader_name', 'trade_id', 'headline', 'ticker', 'product', 'direction',
        'entry_date', 'exit_date', 'entry_level', 'exit_level', 'pnl', 'total_score'
    ]

    display_cols = [col for col in display_cols if col in filtered.columns]

    if not filtered.empty:
        st.dataframe(
            safe_style_format(filtered[display_cols], {
                'entry_level': '{:.4f}',
                'exit_level': '{:.4f}',
                'pnl': '${:,.0f}',
                'total_score': '{:.1f}'
            }),
            use_container_width=True,
            height=600
        )

        # Export to CSV
        st.divider()
        csv = filtered.to_csv(index=False)
        st.download_button(
            label="📥 Export to CSV",
            data=csv,
            file_name=f"trade_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="history_export_csv_btn"
        )


# =============================================================================
# PAGE 6: POTENTIAL TRADES
# =============================================================================

def render_potential_trades(all_positions: pd.DataFrame, correlation: float, vol_target: float):
    """Render the Potential Trades page."""
    st.header("🔮 Potential Trades")

    # Get potential positions
    potential_pos = get_potential_positions(all_positions)

    if potential_pos.empty:
        st.info("No potential trades under consideration.")
        return

    # Add enrichment
    potential_pos = calculate_position_vols_simple(potential_pos)

    # Calculate current book vol (cached via session state if available)
    open_pos = get_open_positions(all_positions)
    open_pos = calculate_position_vols_simple(open_pos)

    current_vol = 0
    if not open_pos.empty:
        vols = open_pos['position_vol'].dropna()
        if len(vols) > 0:
            current_vol = calculate_portfolio_vol_uniform(vols.values, correlation)

    st.metric("Current Book Vol", f"${current_vol:,.0f}")

    st.divider()

    # Quick summary first (fast)
    st.subheader(f"📋 {len(potential_pos)} Potential Trades")
    
    # Show basic info immediately (no heavy calculations)
    quick_cols = ['trader_name', 'headline', 'ticker', 'direction', 'bpv']
    quick_cols = [c for c in quick_cols if c in potential_pos.columns]
    st.dataframe(potential_pos[quick_cols], use_container_width=True)

    # Detailed impact analysis in expander (lazy loaded)
    with st.expander("📊 View Impact Analysis", expanded=False):
        st.subheader("Impact Analysis")
        
        from risk_calcs import calculate_marginal_vol
        
        # Vectorized calculation where possible
        analysis = []
        for _, row in potential_pos.iterrows():
            trade_vol = row.get('position_vol', 0)

            if trade_vol > 0:
                marginal = calculate_marginal_vol(trade_vol, current_vol, correlation)
                new_vol = current_vol + marginal
                new_util = (new_vol / vol_target) * 100 if vol_target > 0 else 0
                fits = new_vol <= vol_target

                analysis.append({
                    'Trader': row.get('trader_name'),
                    'Headline': row.get('headline'),
                    'Ticker': row.get('ticker'),
                    'Direction': row.get('direction'),
                    'BPV': row.get('bpv'),
                    'Trade Vol ($)': trade_vol,
                    'Marginal Vol ($)': marginal,
                    'New Book Vol ($)': new_vol,
                    'New Util %': new_util,
                    'Fits Budget': '✅' if fits else '❌'
                })

        analysis_df = pd.DataFrame(analysis)

        if not analysis_df.empty:
            st.dataframe(
                safe_style_format(analysis_df, {
                    'BPV': '{:.0f}',
                    'Trade Vol ($)': '${:,.0f}',
                    'Marginal Vol ($)': '${:,.0f}',
                    'New Book Vol ($)': '${:,.0f}',
                    'New Util %': '{:.1f}%'
                }),
                use_container_width=True
            )


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    """Main app entry point."""
    app_start = time.time()
    
    # Initialize session state for data persistence
    init_session_state()

    # Sidebar
    st.sidebar.title("⚙️ Settings")

    # Vol target input
    vol_target = st.sidebar.number_input(
        "Portfolio Vol Target ($mm)",
        min_value=10.0,
        max_value=200.0,
        value=DEFAULT_VOL_TARGET,
        step=5.0,
        key="sidebar_vol_target"
    ) * 1_000_000  # Convert to $

    # Correlation slider
    correlation = st.sidebar.slider(
        "Default Correlation",
        min_value=0.0,
        max_value=1.0,
        value=DEFAULT_CORRELATION,
        step=0.05,
        key="sidebar_correlation"
    )

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data", key="sidebar_refresh_btn"):
        st.cache_data.clear()
        # Clear session state cache
        st.session_state.data_loaded = False
        st.session_state.all_positions = None
        st.session_state.settings_dict = None
        st.session_state.live_prices = {}
        st.session_state.metrics_cache = {}
        st.rerun()

    # Last updated
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load data - uses session state for persistence
    if not st.session_state.data_loaded:
        load_start = time.time()
        all_positions = load_all_traders()
        settings_dict = load_all_settings()
        
        if not all_positions.empty:
            # Optionally fetch live prices from Bloomberg (disabled by default for speed)
            if FETCH_LIVE_PRICES:
                all_positions = enrich_with_live_prices(all_positions)
            
            # Store in session state
            st.session_state.all_positions = all_positions
            st.session_state.settings_dict = settings_dict
            st.session_state.data_loaded = True
            
        load_elapsed = time.time() - load_start
        logger.info(f"⏱️ Total data load: {load_elapsed:.2f}s")
    else:
        # Use cached data from session state
        all_positions = st.session_state.all_positions
        settings_dict = st.session_state.settings_dict

    if all_positions is None or all_positions.empty:
        st.error("No position data found. Please check trader Excel files.")
        return

    # Main content
    st.title(DASHBOARD_TITLE)

    # Page navigation using SIDEBAR RADIO (only renders active page - prevents ALL tabs rendering at once)
    page = st.sidebar.radio(
        "📍 Navigation",
        [
            "📊 Book Summary",
            "📋 All Positions",
            "👤 Trader Drill-Down",
            "📈 Performance",
            "📜 Trade History",
            "🔮 Potential Trades"
        ],
        key="sidebar_page_navigation"
    )

    # Render ONLY the selected page (not all 6 at once)
    try:
        if page == "📊 Book Summary":
            render_book_summary(all_positions, settings_dict, correlation, vol_target)
        elif page == "📋 All Positions":
            render_all_positions(all_positions)
        elif page == "👤 Trader Drill-Down":
            render_trader_drilldown(all_positions, settings_dict)
        elif page == "📈 Performance":
            render_performance(all_positions)
        elif page == "📜 Trade History":
            render_trade_history(all_positions)
        elif page == "🔮 Potential Trades":
            render_potential_trades(all_positions, correlation, vol_target)
    except Exception as e:
        st.error(f"Error rendering page: {e}")
        logger.exception(f"Error on page {page}")
        import traceback
        with st.expander("🐛 Debug Info"):
            st.code(traceback.format_exc())
    
    # Log total render time (only on first load)
    if 'app_loaded' not in st.session_state:
        total_elapsed = time.time() - app_start
        logger.info(f"⏱️ Total app render: {total_elapsed:.2f}s")
        st.session_state.app_loaded = True


if __name__ == "__main__":
    main()
