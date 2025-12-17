"""
Streamlit Dashboard for Portfolio Risk Management.

Multi-page dashboard for portfolio manager to view aggregated risk
across all 5 traders.

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
# DATA LOADING
# =============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_all_traders():
    """
    Load positions from all trader files.

    Returns:
        DataFrame with all positions from all traders
    """
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

    return combined


@st.cache_data(ttl=300)
def load_all_settings():
    """Load settings from all trader files."""
    all_settings = {}

    for trader_num, filepath in TRADER_FILES.items():
        if not filepath.exists():
            continue

        try:
            settings = read_settings_openpyxl(filepath)
            all_settings[trader_num] = settings
        except Exception as e:
            logger.error(f"Error loading settings for trader {trader_num}: {e}")

    return all_settings


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


# =============================================================================
# RISK CALCULATIONS
# =============================================================================

def calculate_book_metrics(open_positions: pd.DataFrame, correlation: float, vol_target: float) -> dict:
    """Calculate aggregate book metrics."""

    # Calculate portfolio vol
    if not open_positions.empty and 'position_vol' in open_positions.columns:
        vols = open_positions['position_vol'].dropna()
        if len(vols) > 0:
            portfolio_vol = calculate_portfolio_vol_uniform(vols.values, correlation)
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

    # Add position vols
    open_pos = calculate_position_vols_simple(open_pos)
    open_pos = add_product_info(open_pos)

    # Calculate book metrics
    metrics = calculate_book_metrics(open_pos, correlation, vol_target)

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

    # Bar chart
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

    col1, col2 = st.columns([1, 1])

    with col1:
        st.dataframe(product_risk.style.format({
            'Vol ($)': '${:,.0f}',
            '% of Book': '{:.1f}%'
        }), use_container_width=True)

    with col2:
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

    # Add enrichment
    all_positions = calculate_position_vols_simple(all_positions)
    all_positions = add_product_info(all_positions)

    # Filters
    st.subheader("Filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        traders = ['All'] + sorted(all_positions['trader_name'].unique().tolist())
        selected_traders = st.multiselect("Trader", traders, default=['All'], key="positions_filter_traders")

    with col2:
        statuses = ['All'] + sorted(all_positions['status'].dropna().unique().tolist())
        selected_status = st.selectbox("Status", statuses, key="positions_filter_status")

    with col3:
        products = ['All'] + sorted(all_positions['product'].unique().tolist())
        selected_product = st.selectbox("Product", products, key="positions_filter_product")

    with col4:
        directions = ['All', 'Long', 'Short']
        selected_direction = st.selectbox("Direction", directions, key="positions_filter_direction")

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
        'trader_name', 'trade_id', 'headline', 'ticker', 'direction',
        'bpv', 'entry_level', 'current_level', 'pnl', 'position_vol',
        'total_score', 'entry_date'
    ]

    # Filter to available columns
    display_cols = [col for col in display_cols if col in filtered.columns]

    if not filtered.empty:
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
            height=600
        )

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

def render_trader_drilldown(all_positions: pd.DataFrame, settings_dict: dict):
    """Render the Trader Drill-Down page."""
    st.header("👤 Trader Drill-Down")

    # Trader selector
    traders = sorted([f"Trader {i}" for i in range(1, 6)])
    selected_trader = st.selectbox("Select Trader", traders, key="drilldown_trader_select")

    # Extract trader number
    trader_num = int(selected_trader.split()[1])

    # Filter positions
    trader_pos = all_positions[all_positions['trader_name'] == selected_trader].copy()

    if trader_pos.empty:
        st.warning(f"No positions found for {selected_trader}")
        return

    # Get settings
    settings = settings_dict.get(trader_num, {})

    # Add enrichment
    trader_pos = calculate_position_vols_simple(trader_pos)

    # Get open, closed, potential
    open_pos = get_open_positions(trader_pos)
    closed_pos = get_closed_positions(trader_pos)
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

    st.divider()

    # Open positions table
    st.subheader("Open Positions")
    if not open_pos.empty:
        display_cols = ['trade_id', 'headline', 'ticker', 'direction', 'bpv',
                       'entry_level', 'current_level', 'pnl', 'position_vol', 'total_score']
        display_cols = [col for col in display_cols if col in open_pos.columns]

        st.dataframe(
            open_pos[display_cols].style.format({
                'bpv': '{:.0f}',
                'entry_level': '{:.4f}',
                'current_level': '{:.4f}',
                'pnl': '${:,.0f}',
                'position_vol': '${:,.0f}',
                'total_score': '{:.1f}'
            }),
            use_container_width=True
        )
    else:
        st.info("No open positions")

    st.divider()

    # Potential trades
    st.subheader("Potential Trades")
    if not potential_pos.empty:
        display_cols = ['headline', 'ticker', 'direction', 'bpv', 'entry_level', 'total_score']
        display_cols = [col for col in display_cols if col in potential_pos.columns]

        st.dataframe(
            potential_pos[display_cols].style.format({
                'bpv': '{:.0f}',
                'entry_level': '{:.4f}',
                'total_score': '{:.1f}'
            }),
            use_container_width=True
        )
    else:
        st.info("No potential trades")


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

    # Performance by trader
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

    # Score Analysis
    st.subheader("Score Analysis")

    if 'total_score' in closed_pos.columns:
        # Create score bins
        bins = [0, 3, 5, 7, 9]
        labels = ['0-3', '3-5', '5-7', '7-9']

        closed_pos['score_range'] = pd.cut(closed_pos['total_score'], bins=bins, labels=labels, include_lowest=True)

        score_analysis = closed_pos.groupby('score_range', observed=True).agg({
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

    st.divider()

    # Rationale Analysis
    st.subheader("Performance by Rationale Type")

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
        traders = ['All'] + sorted(closed_pos['trader_name'].unique().tolist())
        selected_traders = st.multiselect("Trader", traders, default=['All'], key="history_filter_traders")

    with col2:
        if 'rationale_type' in closed_pos.columns:
            rationales = ['All'] + sorted(closed_pos['rationale_type'].dropna().unique().tolist())
            selected_rationale = st.selectbox("Rationale", rationales, key="history_filter_rationale")
        else:
            selected_rationale = 'All'

    with col3:
        outcomes = ['All', 'Winners', 'Losers']
        selected_outcome = st.selectbox("Outcome", outcomes, key="history_filter_outcome")

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
        'trader_name', 'trade_id', 'headline', 'entry_date', 'exit_date',
        'entry_level', 'exit_level', 'pnl', 'total_score'
    ]

    display_cols = [col for col in display_cols if col in filtered.columns]

    if not filtered.empty:
        st.dataframe(
            filtered[display_cols].style.format({
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
            mime="text/csv"
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

    # Calculate current book vol
    open_pos = get_open_positions(all_positions)
    open_pos = calculate_position_vols_simple(open_pos)

    current_vol = 0
    if not open_pos.empty:
        vols = open_pos['position_vol'].dropna()
        if len(vols) > 0:
            current_vol = calculate_portfolio_vol_uniform(vols.values, correlation)

    st.metric("Current Book Vol", f"${current_vol:,.0f}")

    st.divider()

    # Analyze each potential trade
    st.subheader("Impact Analysis")

    analysis = []
    for _, row in potential_pos.iterrows():
        trade_vol = row.get('position_vol', 0)

        if trade_vol > 0:
            from risk_calcs import calculate_marginal_vol

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
            analysis_df.style.format({
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

    # Sidebar
    st.sidebar.title("⚙️ Settings")

    # Vol target input
    vol_target = st.sidebar.number_input(
        "Portfolio Vol Target ($mm)",
        min_value=10.0,
        max_value=200.0,
        value=DEFAULT_VOL_TARGET,
        step=5.0
    ) * 1_000_000  # Convert to $

    # Correlation slider
    correlation = st.sidebar.slider(
        "Default Correlation",
        min_value=0.0,
        max_value=1.0,
        value=DEFAULT_CORRELATION,
        step=0.05
    )

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Last updated
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load data
    with st.spinner("Loading data..."):
        all_positions = load_all_traders()
        settings_dict = load_all_settings()

    if all_positions.empty:
        st.error("No position data found. Please check trader Excel files.")
        return

    # Main content
    st.title(DASHBOARD_TITLE)

    # Page navigation
    page = st.radio(
        "Navigate",
        ["📊 Book Summary", "📋 All Positions", "👤 Trader Drill-Down",
         "📈 Performance", "📜 Trade History", "🔮 Potential Trades"],
        horizontal=True,
        key="page_navigation"
    )

    st.markdown("---")

    # Render selected page
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


if __name__ == "__main__":
    main()
