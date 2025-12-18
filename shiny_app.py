"""
Shiny Dashboard for Portfolio Risk Management.

Multi-page dashboard for portfolio manager to view aggregated risk
across all 5 traders.

KEY DIFFERENCE FROM STREAMLIT:
- Data loads ONLY when "Refresh Data" button is clicked
- Dropdowns/filters operate on in-memory data (instant, no re-reading)
- Bloomberg calls happen ONLY on refresh (not on every interaction)
- No continuous re-execution

Usage:
    shiny run shiny_app.py --reload
"""

from shiny import App, ui, render, reactive
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging

# Import our modules
from config import (
    TRADER_FILES,
    DEFAULT_VOL_TARGET,
    DEFAULT_CORRELATION,
    USE_LIVE_CORRELATIONS,
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
    calculate_pnl,
    calculate_marginal_vol
)
from svb_stress_data import SVBStressScenario

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# UI DEFINITION
# =============================================================================

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h4("⚙️ Settings"),
        ui.input_action_button(
            "refresh",
            "🔄 Refresh Data",
            class_="btn-primary btn-lg",
            width="100%"
        ),
        ui.output_text_verbatim("last_updated"),
        ui.hr(),
        ui.input_numeric(
            "vol_target",
            "Portfolio Vol Target ($mm)",
            value=DEFAULT_VOL_TARGET,
            min=10,
            max=200,
            step=5
        ),
        ui.input_slider(
            "correlation",
            "Default Correlation",
            min=0.0,
            max=1.0,
            value=DEFAULT_CORRELATION,
            step=0.05
        ),
        ui.hr(),
        ui.input_radio_buttons(
            "page",
            "📍 Navigation",
            {
                "book": "📊 Book Summary",
                "positions": "📋 All Positions",
                "traders": "👤 Trader Drill-Down",
                "performance": "📈 Performance",
                "history": "📜 Trade History",
                "potential": "🔮 Potential Trades"
            }
        ),
        width=300
    ),
    ui.output_ui("page_content"),
    title=DASHBOARD_TITLE,
    fillable=True
)


# =============================================================================
# SERVER LOGIC
# =============================================================================

def server(input, output, session):
    """
    Server logic with reactive data loading.

    Key principle: Data loads ONLY when refresh button clicked.
    All filtering/interactions happen on in-memory data.
    """

    # =========================================================================
    # REACTIVE VALUES - Stores all data in memory
    # =========================================================================

    data_store = reactive.Value({
        'all_positions': None,
        'settings_dict': None,
        'live_prices': {},
        'correlation_matrix': None,
        'svb_scenario': None,
        'last_updated': None,
        'loading': False,
        'error': None
    })

    # =========================================================================
    # DATA LOADING - ONLY on refresh button click
    # =========================================================================

    @reactive.Effect
    @reactive.event(input.refresh)
    def load_data():
        """
        Load all data when refresh button is clicked.

        This is the ONLY place where:
        - Excel files are read
        - Bloomberg API is called
        - Risk calculations happen
        """
        logger.info("🔄 Refresh button clicked - loading data...")

        # Set loading state
        current = data_store.get()
        current['loading'] = True
        current['error'] = None
        data_store.set(current)

        try:
            # 1. Read Excel files
            logger.info("📁 Reading Excel files...")
            all_positions = load_all_traders()
            settings_dict = load_all_settings()

            if all_positions.empty:
                raise ValueError("No positions found in Excel files")

            logger.info(f"✓ Loaded {len(all_positions)} positions from {len(TRADER_FILES)} traders")

            # 2. Fetch live prices from Bloomberg (if enabled)
            live_prices = {}
            if FETCH_LIVE_PRICES and not all_positions.empty:
                logger.info("💰 Fetching live prices from Bloomberg...")
                tickers = tuple(all_positions['ticker'].dropna().unique().tolist())
                if tickers:
                    live_prices = fetch_live_prices_bulk(tickers)
                    logger.info(f"✓ Fetched {len(live_prices)} live prices")

                    # Update current_level with live prices
                    for idx, row in all_positions.iterrows():
                        ticker = row.get('ticker')
                        if ticker and ticker in live_prices:
                            all_positions.at[idx, 'current_level'] = live_prices[ticker]

            # 3. Fetch correlation matrix (if enabled)
            correlation_matrix = None
            if USE_LIVE_CORRELATIONS and not all_positions.empty:
                logger.info("📊 Fetching correlation matrix from Bloomberg...")
                tickers = all_positions['ticker'].dropna().unique().tolist()
                if len(tickers) > 1:
                    correlation_matrix = fetch_correlation_matrix(tickers, CORRELATION_LOOKBACK_DAYS)
                    if correlation_matrix is not None:
                        logger.info(f"✓ Fetched correlation matrix for {len(tickers)} tickers")

            # 4. Load SVB scenario
            svb_scenario = SVBStressScenario()

            # 5. Enrich positions with calculated fields
            all_positions = enrich_positions(all_positions)

            # 6. Update data store
            data_store.set({
                'all_positions': all_positions,
                'settings_dict': settings_dict,
                'live_prices': live_prices,
                'correlation_matrix': correlation_matrix,
                'svb_scenario': svb_scenario,
                'last_updated': datetime.now(),
                'loading': False,
                'error': None
            })

            logger.info("✅ Data refresh complete")

        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            current = data_store.get()
            current['loading'] = False
            current['error'] = str(e)
            data_store.set(current)

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================

    def load_all_traders():
        """Load positions from all trader files."""
        all_positions = []

        for trader_num, filepath in TRADER_FILES.items():
            if not filepath.exists():
                logger.warning(f"Trader file not found: {filepath}")
                continue

            try:
                df = read_positions_openpyxl(filepath)
                df['trader_num'] = trader_num
                df['trader_name'] = f"Trader {trader_num}"
                all_positions.append(df)
            except Exception as e:
                logger.error(f"Error loading trader {trader_num}: {e}")

        if not all_positions:
            return pd.DataFrame()

        return pd.concat(all_positions, ignore_index=True)

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

    def fetch_live_prices_bulk(tickers):
        """Fetch live prices from Bloomberg in bulk."""
        prices = {}
        try:
            from xbbg import blp
            result = blp.bdp(tickers=list(tickers), flds='PX_LAST')
            if result is not None and not result.empty:
                for ticker in tickers:
                    try:
                        if ticker in result.index:
                            price = result.loc[ticker, 'px_last']
                            if pd.notna(price):
                                prices[ticker] = float(price)
                    except Exception as e:
                        logger.warning(f"Could not extract price for {ticker}: {e}")
        except Exception as e:
            logger.error(f"Error fetching live prices: {e}")
        return prices

    def fetch_correlation_matrix(tickers, lookback_days):
        """Fetch correlation matrix from Bloomberg."""
        try:
            data_provider = get_data_provider()
            corr_matrix = data_provider.get_correlation_matrix(tickers, lookback_days)
            return corr_matrix
        except Exception as e:
            logger.error(f"Error fetching correlation matrix: {e}")
            return None

    def enrich_positions(df):
        """Add calculated fields to positions DataFrame."""
        if df.empty:
            return df

        df = df.copy()

        # Add product classification
        df['product'] = df['ticker'].apply(
            lambda x: parse_product_from_ticker(x) if pd.notna(x) else 'Unknown'
        )

        # Calculate position volatility (using default for now)
        default_vol_bp = 50
        df['annual_vol_bp'] = default_vol_bp
        df['position_vol'] = df.apply(
            lambda row: calculate_position_vol(row.get('bpv', 0), default_vol_bp)
            if not pd.isna(row.get('bpv'))
            else 0,
            axis=1
        )

        # Calculate P&L
        def calc_row_pnl(row):
            entry = row.get('entry_level')
            current = row.get('current_level')
            bpv = row.get('bpv')
            direction = row.get('direction', '')
            product = row.get('product', 'IR Swap')

            if pd.isna(entry) or pd.isna(current) or pd.isna(bpv):
                return 0

            try:
                return calculate_pnl(entry, current, bpv, direction, product)
            except Exception as e:
                logger.warning(f"Error calculating P&L: {e}")
                return 0

        df['pnl'] = df.apply(calc_row_pnl, axis=1)

        return df

    # =========================================================================
    # OUTPUTS
    # =========================================================================

    @output
    @render.text
    def last_updated():
        """Display last update time."""
        current = data_store.get()

        if current['loading']:
            return "⏳ Loading data..."
        elif current['error']:
            return f"❌ Error: {current['error']}"
        elif current['last_updated']:
            return f"Last Updated:\n{current['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            return "Click 'Refresh Data' to load"

    @output
    @render.ui
    def page_content():
        """Render the selected page content."""
        current = data_store.get()

        # Show loading or error state
        if current['loading']:
            return ui.div(
                ui.h3("⏳ Loading data..."),
                ui.p("Reading Excel files and fetching Bloomberg data...")
            )

        if current['error']:
            return ui.div(
                ui.h3("❌ Error Loading Data"),
                ui.pre(current['error']),
                ui.p("Click 'Refresh Data' to try again")
            )

        if current['all_positions'] is None:
            return ui.div(
                ui.h3("No Data Loaded"),
                ui.p("Click '🔄 Refresh Data' button in the sidebar to load positions")
            )

        # Get current page
        page = input.page()
        all_positions = current['all_positions']
        settings_dict = current['settings_dict']
        correlation_matrix = current['correlation_matrix']
        svb_scenario = current['svb_scenario']

        vol_target = input.vol_target() * 1_000_000  # Convert to $
        correlation = input.correlation()

        # Render selected page
        try:
            if page == "book":
                return render_book_summary(
                    all_positions, settings_dict, correlation, vol_target,
                    correlation_matrix, svb_scenario
                )
            elif page == "positions":
                return render_all_positions(all_positions)
            elif page == "traders":
                return render_trader_drilldown(all_positions, settings_dict)
            elif page == "performance":
                return render_performance(all_positions)
            elif page == "history":
                return render_trade_history(all_positions)
            elif page == "potential":
                return render_potential_trades(all_positions, correlation, vol_target)
            else:
                return ui.div(ui.p("Page not found"))
        except Exception as e:
            logger.exception(f"Error rendering page {page}")
            return ui.div(
                ui.h3(f"❌ Error Rendering {page}"),
                ui.pre(str(e))
            )


# =============================================================================
# PAGE RENDERING FUNCTIONS
# =============================================================================

def render_book_summary(all_positions, settings_dict, correlation, vol_target,
                       correlation_matrix, svb_scenario):
    """Render Book Summary page."""
    open_pos = get_open_positions(all_positions)

    if open_pos.empty:
        return ui.div(
            ui.h2("📊 Book Summary"),
            ui.p("No open positions found.")
        )

    # Calculate book metrics
    metrics = calculate_book_metrics(open_pos, correlation, vol_target, correlation_matrix)

    # Build UI
    return ui.div(
        ui.h2("📊 Book Summary"),

        # Correlation method indicator
        ui.div(
            ui.p(
                f"{'✓ Using Live Correlation Matrix' if metrics['using_live_correlations'] else f'⚠ Using Fixed Correlation: {correlation}'}"
            ),
            class_="alert alert-info" if metrics['using_live_correlations'] else "alert alert-warning"
        ),

        # Top metrics
        ui.row(
            ui.column(3, ui.value_box(
                "Total Book Vol",
                f"${metrics['total_book_vol']:,.0f}",
                f"{metrics['risk_util_pct']:.1f}% utilized"
            )),
            ui.column(3, ui.value_box(
                "Vol Headroom",
                f"${metrics['vol_headroom']:,.0f}"
            )),
            ui.column(3, ui.value_box(
                "Total P&L",
                f"${metrics['total_pnl']:,.0f}",
                f"Sharpe: {metrics['book_sharpe']:.2f}"
            )),
            ui.column(3, ui.value_box(
                "Expected Return",
                f"${metrics['expected_return']:,.0f}"
            ))
        ),

        ui.hr(),

        # 2-Sigma Drawdowns
        ui.h3("📉 2-Sigma Drawdowns"),
        ui.output_data_frame("drawdowns_table"),

        ui.hr(),

        # SVB Stress
        ui.h3("⚠️ SVB/CS Stress Scenario (March 2023)"),
        render_svb_stress(open_pos, svb_scenario),

        ui.hr(),

        # Risk by Trader
        ui.h3("👥 Risk by Trader"),
        ui.output_data_frame("trader_risk_table"),

        ui.hr(),

        # Risk by Product
        ui.h3("🌍 Risk by Product"),
        ui.output_data_frame("product_risk_table")
    )

def render_all_positions(all_positions):
    """Render All Positions page with filters."""
    return ui.div(
        ui.h2("📋 All Positions"),
        ui.p(f"Total: {len(all_positions)} positions"),
        ui.output_data_frame("positions_table")
    )

def render_trader_drilldown(all_positions, settings_dict):
    """Render Trader Drill-Down page."""
    traders = sorted(all_positions['trader_name'].unique().tolist())

    return ui.div(
        ui.h2("👤 Trader Drill-Down"),
        ui.p(f"Select trader from tabs below"),
        *[ui.output_ui(f"trader_{i}") for i in range(len(traders))]
    )

def render_performance(all_positions):
    """Render Performance Analytics page."""
    closed_pos = get_closed_positions(all_positions)

    if closed_pos.empty:
        return ui.div(
            ui.h2("📈 Performance Analytics"),
            ui.p("No closed positions found for performance analysis.")
        )

    return ui.div(
        ui.h2("📈 Performance Analytics"),
        ui.output_data_frame("performance_table")
    )

def render_trade_history(all_positions):
    """Render Trade History page."""
    closed_pos = get_closed_positions(all_positions)

    if closed_pos.empty:
        return ui.div(
            ui.h2("📜 Trade History"),
            ui.p("No closed trades found.")
        )

    return ui.div(
        ui.h2("📜 Trade History"),
        ui.p(f"Showing {len(closed_pos)} closed trades"),
        ui.output_data_frame("history_table")
    )

def render_potential_trades(all_positions, correlation, vol_target):
    """Render Potential Trades page."""
    potential_pos = get_potential_positions(all_positions)

    if potential_pos.empty:
        return ui.div(
            ui.h2("🔮 Potential Trades"),
            ui.p("No potential trades under consideration.")
        )

    return ui.div(
        ui.h2("🔮 Potential Trades"),
        ui.p(f"{len(potential_pos)} potential trades"),
        ui.output_data_frame("potential_table")
    )

def render_svb_stress(open_pos, svb_scenario):
    """Render SVB stress summary."""
    if svb_scenario is None:
        return ui.p("SVB scenario not loaded")

    stress_summary = svb_scenario.get_portfolio_stress_summary(open_pos)

    return ui.row(
        ui.column(4, ui.value_box(
            "Portfolio Stress P&L",
            f"${stress_summary['total_stress_pnl']:,.0f}"
        )),
        ui.column(4, ui.value_box(
            "Worst Position",
            f"${stress_summary['worst_position']:,.0f}",
            stress_summary['worst_position_ticker']
        )),
        ui.column(4, ui.value_box(
            "Best Position",
            f"${stress_summary['best_position']:,.0f}",
            stress_summary['best_position_ticker']
        ))
    )

def calculate_book_metrics(open_positions, correlation, vol_target, corr_matrix):
    """Calculate aggregate book metrics."""
    using_live_correlations = False

    if not open_positions.empty and 'position_vol' in open_positions.columns:
        vols = open_positions['position_vol'].dropna()
        if len(vols) > 0:
            # Use correlation matrix if available
            if corr_matrix is not None and not corr_matrix.empty:
                portfolio_vol = calculate_portfolio_vol(open_positions, correlation=correlation, corr_matrix=corr_matrix)
                using_live_correlations = True
            else:
                portfolio_vol = calculate_portfolio_vol_uniform(vols.values, correlation)
        else:
            portfolio_vol = 0
    else:
        portfolio_vol = 0

    total_pnl = open_positions['pnl'].sum() if 'pnl' in open_positions.columns else 0
    headroom = vol_target - portfolio_vol
    risk_util_pct = (portfolio_vol / vol_target) * 100 if vol_target > 0 else 0
    drawdowns = calculate_2sigma_drawdowns(portfolio_vol)
    expected_return = portfolio_vol * 0.5
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
        'using_live_correlations': using_live_correlations,
    }


# =============================================================================
# CREATE APP
# =============================================================================

app = App(app_ui, server)
