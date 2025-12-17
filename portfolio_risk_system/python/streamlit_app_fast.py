"""
PERFORMANCE OPTIMIZED Streamlit Dashboard for Portfolio Risk Management.

Key optimizations:
- Session state for data persistence between page changes
- Pre-calculated metrics cached in session state
- Lazy loading of heavy calculations
- More aggressive caching
- Reduced dataframe operations

Usage:
    streamlit run streamlit_app_fast.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import logging

# Import our modules
from config import (
    TRADER_FILES,
    DEFAULT_VOL_TARGET,
    DEFAULT_CORRELATION,
    DASHBOARD_TITLE,
    parse_product_from_ticker
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
    calculate_2sigma_drawdowns
)
from svb_stress_data import load_svb_scenario

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title=DASHBOARD_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# OPTIMIZED DATA LOADING WITH SESSION STATE
# =============================================================================

def initialize_session_state():
    """Initialize session state variables if not already set."""
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'all_positions' not in st.session_state:
        st.session_state.all_positions = None
    if 'settings_dict' not in st.session_state:
        st.session_state.settings_dict = None
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = None


@st.cache_data(ttl=600, show_spinner=False)  # Cache for 10 minutes
def load_trader_data():
    """Load all trader positions and settings. Cached for performance."""
    all_positions = []
    all_settings = {}

    for trader_num, filepath in TRADER_FILES.items():
        if not filepath.exists():
            continue

        try:
            # Read positions
            df = read_positions_openpyxl(filepath)
            df['trader_num'] = trader_num
            df['trader_name'] = f"Trader {trader_num}"
            all_positions.append(df)

            # Read settings
            settings = read_settings_openpyxl(filepath)
            all_settings[trader_num] = settings

        except Exception as e:
            logger.error(f"Error loading trader {trader_num}: {e}")

    if not all_positions:
        return pd.DataFrame(), {}

    combined = pd.concat(all_positions, ignore_index=True)
    return combined, all_settings


def load_data():
    """Load data into session state if needed."""
    if not st.session_state.data_loaded or st.session_state.all_positions is None:
        with st.spinner("Loading trader data..."):
            positions, settings = load_trader_data()
            st.session_state.all_positions = positions
            st.session_state.settings_dict = settings
            st.session_state.data_loaded = True
            st.session_state.last_refresh = datetime.now()


def refresh_data():
    """Force refresh of data."""
    st.cache_data.clear()
    st.session_state.data_loaded = False
    st.session_state.all_positions = None
    st.session_state.settings_dict = None
    load_data()


# =============================================================================
# OPTIMIZED CALCULATIONS (CACHED)
# =============================================================================

@st.cache_data(show_spinner=False)
def enrich_positions_fast(positions_df, default_vol_bp=50):
    """
    Fast position enrichment without market data.
    Uses default volatility assumption.
    """
    df = positions_df.copy()

    # Use default vol
    df['annual_vol_bp'] = default_vol_bp

    # Calculate position vol
    df['position_vol'] = df.apply(
        lambda row: calculate_position_vol(row.get('bpv', 0), default_vol_bp)
        if not pd.isna(row.get('bpv'))
        else 0,
        axis=1
    )

    # Add product info
    df['product'] = df['ticker'].apply(
        lambda x: parse_product_from_ticker(x) if pd.notna(x) else 'Unknown'
    )

    # Calculate P&L (from Excel formula or calculate)
    # P&L should already be in the dataframe from Excel
    if 'pnl' not in df.columns or df['pnl'].isna().all():
        df['pnl'] = 0  # Placeholder

    return df


@st.cache_data(show_spinner=False)
def calculate_book_metrics_cached(open_positions_df, correlation, vol_target):
    """Calculate aggregate book metrics. Cached for performance."""

    # Calculate portfolio vol
    if not open_positions_df.empty and 'position_vol' in open_positions_df.columns:
        vols = open_positions_df['position_vol'].dropna()
        if len(vols) > 0:
            portfolio_vol = calculate_portfolio_vol_uniform(vols.values, correlation)
        else:
            portfolio_vol = 0
    else:
        portfolio_vol = 0

    # Calculate P&L
    total_pnl = open_positions_df['pnl'].sum() if 'pnl' in open_positions_df.columns else 0

    # Calculate headroom and utilization
    headroom = vol_target - portfolio_vol
    risk_util_pct = (portfolio_vol / vol_target) * 100 if vol_target > 0 else 0

    # Calculate drawdowns
    drawdowns = calculate_2sigma_drawdowns(portfolio_vol)

    # Expected return (assume 0.5 Sharpe)
    expected_return = portfolio_vol * 0.5

    # Book Sharpe
    book_sharpe = expected_return / portfolio_vol if portfolio_vol > 0 else 0

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
    }


@st.cache_data(show_spinner=False)
def calculate_svb_stress_cached(open_positions_df):
    """Calculate SVB stress. Cached for performance."""
    if open_positions_df.empty:
        return None

    scenario = load_svb_scenario()
    stress_summary = scenario.get_portfolio_stress_summary(open_positions_df)
    return stress_summary


# =============================================================================
# PAGE 1: BOOK SUMMARY (OPTIMIZED)
# =============================================================================

def render_book_summary(all_positions, correlation, vol_target):
    """Render Book Summary page - optimized version."""
    st.header("📊 Book Summary")

    # Filter to open positions
    open_pos = get_open_positions(all_positions)

    if open_pos.empty:
        st.warning("No open positions found.")
        return

    # Enrich positions (cached)
    open_pos_enriched = enrich_positions_fast(open_pos)

    # Calculate metrics (cached)
    metrics = calculate_book_metrics_cached(
        open_pos_enriched.to_json(),  # Serialize for caching
        correlation,
        vol_target
    )

    # Deserialize back
    metrics = eval(metrics) if isinstance(metrics, str) else metrics

    # Display top metrics
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

    dd_data = pd.DataFrame({
        'Horizon': ['1 Day', '1 Week', '2 Weeks', '1 Month'],
        '2σ Drawdown ($)': [
            metrics['drawdown_1d'],
            metrics['drawdown_1w'],
            metrics['drawdown_2w'],
            metrics['drawdown_1m']
        ]
    })
    st.dataframe(dd_data.style.format({'2σ Drawdown ($)': '${:,.0f}'}),
                 use_container_width=True, hide_index=True)

    st.divider()

    # SVB Stress (cached)
    st.subheader("⚠️ SVB/CS Stress Scenario (March 2023)")

    stress_summary = calculate_svb_stress_cached(open_pos_enriched.to_json())
    stress_summary = eval(stress_summary) if isinstance(stress_summary, str) else stress_summary

    if stress_summary:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Portfolio Stress P&L", f"${stress_summary['total_stress_pnl']:,.0f}")
        with col2:
            st.metric("Worst Position", f"${stress_summary['worst_position']:,.0f}",
                     delta=stress_summary['worst_position_ticker'])
        with col3:
            st.metric("Best Position", f"${stress_summary['best_position']:,.0f}",
                     delta=stress_summary['best_position_ticker'])

    st.divider()

    # Risk by Trader (optimized groupby)
    st.subheader("👥 Risk by Trader")

    trader_risk = open_pos_enriched.groupby('trader_name', as_index=False).agg({
        'trade_id': 'count',
        'position_vol': 'sum',
        'pnl': 'sum'
    })
    trader_risk.columns = ['Trader', '# Positions', 'Vol ($)', 'P&L ($)']
    trader_risk['% of Book'] = (trader_risk['Vol ($)'] / metrics['total_book_vol'] * 100) if metrics['total_book_vol'] > 0 else 0

    st.dataframe(trader_risk.style.format({
        '# Positions': '{:.0f}',
        'Vol ($)': '${:,.0f}',
        'P&L ($)': '${:,.0f}',
        '% of Book': '{:.1f}%'
    }), use_container_width=True, hide_index=True)

    # Bar chart
    fig = px.bar(trader_risk, x='Trader', y='Vol ($)',
                 title="Vol Contribution by Trader",
                 color='% of Book',
                 color_continuous_scale='Blues')
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Risk by Product (optimized groupby)
    st.subheader("🌍 Risk by Product")

    product_risk = open_pos_enriched.groupby('product', as_index=False).agg({
        'position_vol': 'sum'
    })
    product_risk.columns = ['Product', 'Vol ($)']
    product_risk['% of Book'] = (product_risk['Vol ($)'] / metrics['total_book_vol'] * 100) if metrics['total_book_vol'] > 0 else 0
    product_risk = product_risk.sort_values('Vol ($)', ascending=False)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.dataframe(product_risk.style.format({
            'Vol ($)': '${:,.0f}',
            '% of Book': '{:.1f}%'
        }), use_container_width=True, hide_index=True)

    with col2:
        fig = px.pie(product_risk, values='Vol ($)', names='Product',
                    title='Vol by Product')
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# SIMPLIFIED OTHER PAGES (keeping original logic)
# =============================================================================

def render_all_positions(all_positions):
    """Render All Positions page."""
    st.header("📋 All Positions")

    if all_positions.empty:
        st.warning("No positions found.")
        return

    # Enrich (cached)
    all_positions_enriched = enrich_positions_fast(all_positions)

    # Filters
    st.subheader("Filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        traders = ['All'] + sorted(all_positions_enriched['trader_name'].unique().tolist())
        selected_traders = st.multiselect("Trader", traders, default=['All'], key="fast_positions_filter_traders")

    with col2:
        statuses = ['All'] + sorted(all_positions_enriched['status'].dropna().unique().tolist())
        selected_status = st.selectbox("Status", statuses, key="fast_positions_filter_status")

    with col3:
        products = ['All'] + sorted(all_positions_enriched['product'].unique().tolist())
        selected_product = st.selectbox("Product", products, key="fast_positions_filter_product")

    with col4:
        directions = ['All', 'Long', 'Short']
        selected_direction = st.selectbox("Direction", directions, key="fast_positions_filter_direction")

    # Apply filters
    filtered = all_positions_enriched.copy()

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
    display_cols = [col for col in [
        'trader_name', 'trade_id', 'headline', 'ticker', 'direction',
        'bpv', 'entry_level', 'current_level', 'pnl', 'position_vol',
        'total_score', 'entry_date'
    ] if col in filtered.columns]

    if not filtered.empty and display_cols:
        st.dataframe(
            filtered[display_cols].style.format({
                'bpv': '{:.0f}',
                'entry_level': '{:.4f}',
                'current_level': '{:.4f}',
                'pnl': '${:,.0f}',
                'position_vol': '${:,.0f}',
                'total_score': '{:.1f}'
            }),
            use_container_width=True,
            height=600,
            hide_index=True
        )


def render_performance(all_positions):
    """Render Performance page."""
    st.header("📈 Performance Analytics")

    closed_pos = get_closed_positions(all_positions)

    if closed_pos.empty:
        st.warning("No closed positions for analysis.")
        return

    # Performance by trader
    st.subheader("Performance by Trader")

    perf = closed_pos.groupby('trader_name', as_index=False).agg({
        'trade_id': 'count',
        'pnl': ['sum', 'mean', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0]
    })
    perf.columns = ['Trader', '# Trades', 'Total P&L', 'Avg P&L', 'Win Rate %']

    st.dataframe(perf.style.format({
        '# Trades': '{:.0f}',
        'Total P&L': '${:,.0f}',
        'Avg P&L': '${:,.0f}',
        'Win Rate %': '{:.1f}%'
    }), use_container_width=True, hide_index=True)


# =============================================================================
# MAIN APP (OPTIMIZED)
# =============================================================================

def main():
    """Main app - optimized with session state."""

    # Initialize session state
    initialize_session_state()

    # Sidebar
    st.sidebar.title("⚙️ Settings")

    # Vol target
    vol_target = st.sidebar.number_input(
        "Portfolio Vol Target ($mm)",
        min_value=10.0,
        max_value=200.0,
        value=DEFAULT_VOL_TARGET,
        step=5.0
    ) * 1_000_000

    # Correlation
    correlation = st.sidebar.slider(
        "Default Correlation",
        min_value=0.0,
        max_value=1.0,
        value=DEFAULT_CORRELATION,
        step=0.05
    )

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        refresh_data()
        st.rerun()

    # Last updated
    st.sidebar.markdown("---")
    if st.session_state.last_refresh:
        st.sidebar.caption(f"Last Updated: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")

    # Load data into session state
    load_data()

    # Get data from session state
    all_positions = st.session_state.all_positions

    if all_positions is None or all_positions.empty:
        st.error("No position data found. Please check trader Excel files.")
        return

    # Main content
    st.title(DASHBOARD_TITLE)

    # Page navigation using tabs (faster than radio)
    tab1, tab2, tab3 = st.tabs([
        "📊 Book Summary",
        "📋 All Positions",
        "📈 Performance"
    ])

    with tab1:
        render_book_summary(all_positions, correlation, vol_target)

    with tab2:
        render_all_positions(all_positions)

    with tab3:
        render_performance(all_positions)


if __name__ == "__main__":
    main()
