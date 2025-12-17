"""
Risk calculation functions.

Implements all risk metrics:
- Position volatility
- Portfolio volatility (with correlation)
- Marginal volatility
- 2-Sigma drawdowns (1d, 1w, 2w, 1m)
- Entry z-score scoring
- Max BPV calculations
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# POSITION VOLATILITY
# =============================================================================

def calculate_position_vol(bpv: float, annual_rate_vol_bp: float) -> float:
    """
    Calculate position volatility in dollars.

    Formula:
        Position Vol ($) = BPV ($k) × Annual Rate Vol (bp) × 100

    Args:
        bpv: Basis point value in $thousands
        annual_rate_vol_bp: Annualized rate volatility in basis points

    Returns:
        Position volatility in $

    Example:
        bpv = 250 ($250k per bp)
        annual_rate_vol = 50 bp
        position_vol = 250 × 50 × 100 = $1,250,000
    """
    return bpv * annual_rate_vol_bp * 100


def calculate_position_vols(positions: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate position volatilities for a portfolio.

    Args:
        positions: DataFrame with columns 'bpv' and 'annual_vol_bp'

    Returns:
        DataFrame with additional 'position_vol' column
    """
    df = positions.copy()
    df['position_vol'] = df['bpv'] * df['annual_vol_bp'] * 100
    return df


# =============================================================================
# PORTFOLIO VOLATILITY
# =============================================================================

def calculate_portfolio_vol_uniform(
    position_vols: np.ndarray,
    correlation: float
) -> float:
    """
    Calculate portfolio volatility with uniform correlation assumption.

    Formula:
        Portfolio Variance = Σ(σᵢ²) + ρ × Σᵢ≠ⱼ(σᵢ × σⱼ)
        Portfolio Variance = Σ(σᵢ²) + ρ × [(Σσᵢ)² - Σ(σᵢ²)]
        Portfolio Vol = √(Portfolio Variance)

    Args:
        position_vols: Array of position volatilities ($)
        correlation: Uniform correlation assumption

    Returns:
        Portfolio volatility ($)

    Example:
        position_vols = [1000000, 500000, 750000]
        correlation = 0.2
        portfolio_vol = calculate_portfolio_vol_uniform(position_vols, 0.2)
    """
    vols = np.array(position_vols)

    # Sum of variances (diagonal)
    sum_var = np.sum(vols ** 2)

    # Sum of cross terms (off-diagonal)
    sum_vols = np.sum(vols)
    sum_cross = sum_vols ** 2 - sum_var

    # Total variance
    portfolio_var = sum_var + correlation * sum_cross

    # Portfolio vol
    portfolio_vol = np.sqrt(portfolio_var)

    return float(portfolio_vol)


def calculate_portfolio_vol_matrix(
    position_vols: np.ndarray,
    corr_matrix: np.ndarray
) -> float:
    """
    Calculate portfolio volatility with full correlation matrix.

    Formula:
        Portfolio Variance = Σᵢⱼ (σᵢ × σⱼ × ρᵢⱼ)
        Portfolio Vol = √(Portfolio Variance)

    Args:
        position_vols: Array of position volatilities ($)
        corr_matrix: Correlation matrix (N×N)

    Returns:
        Portfolio volatility ($)

    Example:
        position_vols = [1000000, 500000]
        corr_matrix = [[1.0, 0.3], [0.3, 1.0]]
        portfolio_vol = calculate_portfolio_vol_matrix(position_vols, corr_matrix)
    """
    vols = np.array(position_vols)
    corr = np.array(corr_matrix)

    # Portfolio variance = vols' × Corr × vols
    # This gives: Σᵢⱼ (σᵢ × σⱼ × ρᵢⱼ)
    portfolio_var = np.dot(vols, np.dot(corr, vols))

    # Portfolio vol
    portfolio_vol = np.sqrt(portfolio_var)

    return float(portfolio_vol)


def calculate_portfolio_vol(
    positions: pd.DataFrame,
    correlation: float = 0.2,
    corr_matrix: Optional[pd.DataFrame] = None
) -> float:
    """
    Calculate portfolio volatility (convenience function).

    Uses full correlation matrix if provided, otherwise uniform correlation.
    
    When corr_matrix is provided (indexed by ticker), this function expands it
    to match positions - multiple positions with the same ticker will have 
    correlation 1.0 with each other.

    Args:
        positions: DataFrame with 'position_vol' and 'ticker' columns
        correlation: Uniform correlation (used if corr_matrix is None)
        corr_matrix: Full correlation matrix indexed by ticker (optional)

    Returns:
        Portfolio volatility ($)
    """
    vols = positions['position_vol'].values
    n = len(vols)

    if corr_matrix is not None and not corr_matrix.empty and 'ticker' in positions.columns:
        # Expand ticker-based correlation matrix to position-based matrix
        # Positions with same ticker have correlation 1.0
        tickers = positions['ticker'].values
        position_corr = np.eye(n)  # Start with identity matrix
        
        for i in range(n):
            for j in range(i+1, n):
                ticker_i = tickers[i]
                ticker_j = tickers[j]
                
                if pd.isna(ticker_i) or pd.isna(ticker_j):
                    # Unknown ticker - use default correlation
                    corr_val = correlation
                elif ticker_i == ticker_j:
                    # Same ticker = perfect correlation
                    corr_val = 1.0
                elif ticker_i in corr_matrix.index and ticker_j in corr_matrix.columns:
                    # Look up correlation from matrix
                    corr_val = corr_matrix.loc[ticker_i, ticker_j]
                else:
                    # Ticker not in correlation matrix - use default
                    corr_val = correlation
                
                position_corr[i, j] = corr_val
                position_corr[j, i] = corr_val
        
        return calculate_portfolio_vol_matrix(vols, position_corr)
    else:
        return calculate_portfolio_vol_uniform(vols, correlation)


# =============================================================================
# MARGINAL VOLATILITY
# =============================================================================

def calculate_marginal_vol(
    new_position_vol: float,
    current_portfolio_vol: float,
    correlation: float
) -> float:
    """
    Calculate marginal volatility contribution of a new position.

    Assumes the new position has the same correlation to all existing positions.

    Formula:
        New Portfolio Variance = Current Var + New Var + 2 × ρ × Current Vol × New Vol
        New Portfolio Vol = √(New Portfolio Variance)
        Marginal Vol = New Portfolio Vol - Current Portfolio Vol

    Args:
        new_position_vol: Volatility of new position ($)
        current_portfolio_vol: Current portfolio volatility ($)
        correlation: Correlation between new position and existing book

    Returns:
        Marginal volatility contribution ($)

    Example:
        new_position_vol = 500000
        current_portfolio_vol = 2000000
        correlation = 0.2
        marginal_vol = calculate_marginal_vol(500000, 2000000, 0.2)
    """
    curr_var = current_portfolio_vol ** 2
    new_var = new_position_vol ** 2
    cross_term = 2 * correlation * current_portfolio_vol * new_position_vol

    new_portfolio_var = curr_var + new_var + cross_term
    new_portfolio_vol = np.sqrt(new_portfolio_var)

    marginal_vol = new_portfolio_vol - current_portfolio_vol

    return float(marginal_vol)


def calculate_new_portfolio_vol(
    new_position_vol: float,
    current_portfolio_vol: float,
    correlation: float
) -> float:
    """
    Calculate new portfolio volatility after adding a position.

    Args:
        new_position_vol: Volatility of new position ($)
        current_portfolio_vol: Current portfolio volatility ($)
        correlation: Correlation between new position and existing book

    Returns:
        New portfolio volatility ($)
    """
    curr_var = current_portfolio_vol ** 2
    new_var = new_position_vol ** 2
    cross_term = 2 * correlation * current_portfolio_vol * new_position_vol

    new_portfolio_var = curr_var + new_var + cross_term
    new_portfolio_vol = np.sqrt(new_portfolio_var)

    return float(new_portfolio_vol)


# =============================================================================
# 2-SIGMA DRAWDOWNS
# =============================================================================

def calculate_2sigma_drawdowns(annual_vol: float) -> Dict[str, float]:
    """
    Calculate 2-sigma drawdowns for multiple time horizons.

    Horizons: 1-day, 1-week, 2-week, 1-month

    Formula:
        Horizon Vol = Annual Vol / √(periods_per_year)
        2σ Drawdown = 2 × Horizon Vol

    Args:
        annual_vol: Annual volatility ($)

    Returns:
        Dictionary with drawdowns for each horizon:
            {'1d': ..., '1w': ..., '2w': ..., '1m': ...}

    Example:
        annual_vol = 10000000  # $10mm
        drawdowns = calculate_2sigma_drawdowns(annual_vol)
        # Returns: {'1d': 1,261,566, '1w': 2,773,501, ...}
    """
    drawdowns = {}

    # 1-day: annual_vol / sqrt(252)
    daily_vol = annual_vol / np.sqrt(252)
    drawdowns['1d'] = 2 * daily_vol

    # 1-week: annual_vol / sqrt(52)
    weekly_vol = annual_vol / np.sqrt(52)
    drawdowns['1w'] = 2 * weekly_vol

    # 2-week: annual_vol / sqrt(26)
    two_week_vol = annual_vol / np.sqrt(26)
    drawdowns['2w'] = 2 * two_week_vol

    # 1-month: annual_vol / sqrt(12)
    monthly_vol = annual_vol / np.sqrt(12)
    drawdowns['1m'] = 2 * monthly_vol

    return drawdowns


def calculate_horizon_vol(annual_vol: float, periods_per_year: int) -> float:
    """
    Calculate volatility for a specific time horizon.

    Args:
        annual_vol: Annual volatility
        periods_per_year: Number of periods per year

    Returns:
        Horizon volatility
    """
    return annual_vol / np.sqrt(periods_per_year)


# =============================================================================
# MAX BPV CALCULATION
# =============================================================================

def calculate_max_bpv(
    headroom: float,
    current_vol: float,
    annual_rate_vol_bp: float,
    correlation: float
) -> float:
    """
    Calculate maximum BPV that can be added while staying within risk budget.

    Solves for BPV such that new portfolio vol = current vol + headroom.

    Formula:
        Target Vol² = Current Vol² + Position Vol² + 2 × ρ × Current Vol × Position Vol
        Position Vol = BPV × Annual Rate Vol × 100

        Solving quadratic equation for Position Vol:
        Position Vol² + 2ρ × Current Vol × Position Vol + (Current Vol² - Target Vol²) = 0

        Position Vol = -ρ × Current Vol + √(ρ² × Current Vol² + Target Vol² - Current Vol²)

        Max BPV = Position Vol / (Annual Rate Vol × 100)

    Args:
        headroom: Remaining risk budget ($)
        current_vol: Current portfolio volatility ($)
        annual_rate_vol_bp: Annual rate volatility of new position (bp)
        correlation: Correlation between new position and existing book

    Returns:
        Maximum BPV ($k) that can be added

    Example:
        headroom = 5000000  # $5mm remaining budget
        current_vol = 45000000  # $45mm current vol
        annual_rate_vol_bp = 50  # 50bp annual vol
        correlation = 0.2
        max_bpv = calculate_max_bpv(5000000, 45000000, 50, 0.2)
    """
    if headroom <= 0:
        return 0

    target_vol = current_vol + headroom

    # Solve quadratic for position vol
    # a × x² + b × x + c = 0
    # where x = position_vol
    a = 1
    b = 2 * correlation * current_vol
    c = current_vol ** 2 - target_vol ** 2

    # Discriminant
    discriminant = b ** 2 - 4 * a * c

    if discriminant < 0:
        logger.warning("Negative discriminant in max BPV calculation")
        return 0

    # Solve for position vol (take positive root)
    position_vol = (-b + np.sqrt(discriminant)) / (2 * a)

    if position_vol <= 0:
        return 0

    # Convert to BPV
    # Position Vol = BPV × Annual Rate Vol × 100
    # BPV = Position Vol / (Annual Rate Vol × 100)
    max_bpv = position_vol / (annual_rate_vol_bp * 100)

    return float(max_bpv)


# =============================================================================
# ENTRY SCORE (Z-SCORE BASED)
# =============================================================================

def calculate_entry_score(zscore: float, direction: str) -> float:
    """
    Calculate entry score (0, 0.5, or 1) based on z-score and direction.

    Logic:
        - Adjust z-score for direction:
            Long: Want to buy below mean (negative z) → adjusted_z = -z
            Short: Want to sell above mean (positive z) → adjusted_z = +z
        - Score based on adjusted z:
            adjusted_z < 0: Score = 0 (wrong side of mean)
            0 ≤ adjusted_z ≤ 1: Score = 0.5 (within 1 std)
            adjusted_z > 1: Score = 1 (more than 1 std in our favor)

    Args:
        zscore: Z-score vs 3-month history
        direction: "Long" or "Short"

    Returns:
        Entry score: 0, 0.5, or 1

    Example:
        # Long position with current price below mean (z = -1.5)
        score = calculate_entry_score(-1.5, "Long")  # Returns 1.0

        # Short position with current price above mean (z = 1.2)
        score = calculate_entry_score(1.2, "Short")  # Returns 1.0

        # Long position with current price above mean (z = 0.5)
        score = calculate_entry_score(0.5, "Long")  # Returns 0.0
    """
    if direction.upper() == "LONG":
        # Long: want price below mean (negative z-score)
        adjusted_z = -zscore
    elif direction.upper() == "SHORT":
        # Short: want price above mean (positive z-score)
        adjusted_z = zscore
    else:
        logger.warning(f"Unknown direction: {direction}")
        return 0

    # Score based on adjusted z
    if adjusted_z < 0:
        return 0.0  # Wrong side of mean
    elif adjusted_z <= 1:
        return 0.5  # Within 1 std dev
    else:
        return 1.0  # More than 1 std dev


# =============================================================================
# P&L CALCULATION
# =============================================================================

# Import product type config
try:
    from config import PRODUCT_TYPES, DEFAULT_PRODUCT_TYPE
except ImportError:
    # Fallback defaults if config not available
    PRODUCT_TYPES = {
        'IR Swap': {'quote_type': 'rate_pct', 'direction_type': 'pay_rec', 'bp_multiplier': 100},
        'Basis': {'quote_type': 'bp', 'direction_type': 'pay_rec', 'bp_multiplier': 1},
        'XCCY': {'quote_type': 'bp', 'direction_type': 'pay_rec', 'bp_multiplier': 1},
        'ASW': {'quote_type': 'bp', 'direction_type': 'pay_rec', 'bp_multiplier': 1},
        'Futures': {'quote_type': 'price', 'direction_type': 'long_short', 'bp_multiplier': 100},
    }
    DEFAULT_PRODUCT_TYPE = 'IR Swap'


def calculate_pnl(
    entry_level: float,
    current_level: float,
    bpv: float,
    direction: str,
    product_type: str = None
) -> float:
    """
    Calculate P&L for a position based on product type.

    Supports different product types with different conventions:
    
    IR Swap (quote_type='rate_pct', direction_type='pay_rec'):
        - Quoted in % (e.g., 3.9 = 3.9%)
        - Pay = want rates UP (profit when rates rise)
        - Rec = want rates DOWN (profit when rates fall)
        - bp_move = (current - entry) * 100
        
    Basis/XCCY/ASW (quote_type='bp', direction_type='pay_rec'):
        - Quoted in bp (e.g., 15 = 15bp)
        - Pay = want spread WIDER (profit when spread increases)
        - Rec = want spread TIGHTER (profit when spread decreases)
        - bp_move = (current - entry) * 1
        
    Futures (quote_type='price', direction_type='long_short'):
        - Quoted as price (e.g., 95.50)
        - Long = want price UP (profit when price rises)
        - Short = want price DOWN (profit when price falls)
        - bp_move = (current - entry) * 100 (price to bp conversion)

    Args:
        entry_level: Entry level (% for IR Swap, bp for Basis/XCCY/ASW, price for Futures)
        current_level: Current level (same unit as entry)
        bpv: Basis point value ($k) - thousands of dollars per 1bp move
        direction: "Pay"/"Rec" for swaps, "Long"/"Short" for futures
        product_type: One of 'IR Swap', 'Basis', 'XCCY', 'ASW', 'Futures'

    Returns:
        P&L in $

    Examples:
        # IR Swap: Pay 10Y at 4.25%, now 4.30% (+5bp = profit)
        pnl = calculate_pnl(4.25, 4.30, 250, "Pay", "IR Swap")
        # = 5bp * $250k = +$1,250,000

        # Basis: Pay 3s6s at 15bp, now 20bp (+5bp = profit)
        pnl = calculate_pnl(15, 20, 50, "Pay", "Basis")
        # = 5bp * $50k = +$250,000

        # Futures: Long SFRM5 at 95.50, now 95.55 (+5 ticks = profit)
        pnl = calculate_pnl(95.50, 95.55, 25, "Long", "Futures")
        # = 5bp * $25k = +$125,000
    """
    # Default to IR Swap if not specified
    if product_type is None or product_type not in PRODUCT_TYPES:
        product_type = DEFAULT_PRODUCT_TYPE
    
    product_config = PRODUCT_TYPES[product_type]
    bp_multiplier = product_config['bp_multiplier']
    direction_type = product_config['direction_type']
    
    # Calculate move in basis points
    level_change = current_level - entry_level
    bp_move = level_change * bp_multiplier
    
    # Normalize direction
    direction_upper = direction.upper().strip()
    
    if direction_type == 'pay_rec':
        # Swaps: Pay = profit when rates/spreads UP, Rec = profit when DOWN
        if direction_upper == "PAY":
            pnl = bp_move * bpv * 1000  # Positive bp_move = profit
        elif direction_upper == "REC":
            pnl = -bp_move * bpv * 1000  # Negative bp_move = profit
        else:
            logger.warning(f"Unknown swap direction '{direction}' for {product_type}. Expected Pay/Rec.")
            pnl = 0
            
    elif direction_type == 'long_short':
        # Futures: Long = profit when price UP, Short = profit when DOWN
        if direction_upper == "LONG":
            pnl = bp_move * bpv * 1000  # Positive bp_move = profit
        elif direction_upper == "SHORT":
            pnl = -bp_move * bpv * 1000  # Negative bp_move = profit
        else:
            logger.warning(f"Unknown futures direction '{direction}' for {product_type}. Expected Long/Short.")
            pnl = 0
    else:
        logger.warning(f"Unknown direction_type '{direction_type}' for {product_type}")
        pnl = 0

    return float(pnl)


def calculate_pnl_with_exit(
    entry_level: float,
    exit_level: float,
    bpv: float,
    direction: str,
    product_type: str = None
) -> float:
    """
    Calculate P&L for a closed position.

    Args:
        entry_level: Entry level
        exit_level: Exit level
        bpv: Basis point value ($k)
        direction: "Pay"/"Rec" for swaps, "Long"/"Short" for futures
        product_type: One of 'IR Swap', 'Basis', 'XCCY', 'ASW', 'Futures'

    Returns:
        Realized P&L in $
    """
    return calculate_pnl(entry_level, exit_level, bpv, direction, product_type)


# =============================================================================
# DISTANCE TO TARGET/STOP
# =============================================================================

def calculate_distance_to_level(
    current_level: float,
    target_level: float,
    direction: str
) -> float:
    """
    Calculate distance from current level to target in basis points.

    Args:
        current_level: Current rate/price
        target_level: Target rate/price
        direction: "Long" or "Short"

    Returns:
        Distance in bp (positive if moving toward target)

    Example:
        # Long position: current 4.20%, target 4.00%
        # Need rates to fall 20bp
        dist = calculate_distance_to_level(4.20, 4.00, "Long")  # Returns -20
    """
    if direction.upper() == "LONG":
        # Long: profit when rates fall
        distance = (current_level - target_level) * 100
    elif direction.upper() == "SHORT":
        # Short: profit when rates rise
        distance = (target_level - current_level) * 100
    else:
        distance = 0

    return float(distance)


def calculate_distance_to_tp(
    current_level: float,
    tp_level: float,
    direction: str
) -> float:
    """Calculate distance to take profit level in bp."""
    return calculate_distance_to_level(current_level, tp_level, direction)


def calculate_distance_to_stop(
    current_level: float,
    stop_level: float,
    direction: str
) -> float:
    """Calculate distance to stop loss level in bp."""
    return calculate_distance_to_level(current_level, stop_level, direction)


# =============================================================================
# SHARPE RATIO
# =============================================================================

def calculate_sharpe_ratio(
    expected_return: float,
    volatility: float,
    risk_free_rate: float = 0.05
) -> float:
    """
    Calculate Sharpe ratio.

    Formula:
        Sharpe = (Expected Return - Risk Free Rate) / Volatility

    Args:
        expected_return: Expected annual return ($)
        volatility: Annual volatility ($)
        risk_free_rate: Risk-free rate (decimal, e.g., 0.05 for 5%)

    Returns:
        Sharpe ratio

    Example:
        expected_return = 2000000  # $2mm
        volatility = 10000000  # $10mm
        sharpe = calculate_sharpe_ratio(2000000, 10000000, 0.05)
    """
    if volatility == 0:
        return 0

    # Convert risk-free rate to dollar terms (proportion of vol)
    rf_dollars = risk_free_rate * volatility

    sharpe = (expected_return - rf_dollars) / volatility

    return float(sharpe)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=== Risk Calculation Examples ===\n")

    # Position vol
    print("1. Position Volatility:")
    bpv = 250  # $250k per bp
    annual_vol = 50  # 50 bp
    pos_vol = calculate_position_vol(bpv, annual_vol)
    print(f"   BPV: ${bpv}k, Annual Vol: {annual_vol}bp")
    print(f"   Position Vol: ${pos_vol:,.0f}\n")

    # Portfolio vol (uniform correlation)
    print("2. Portfolio Volatility (uniform correlation):")
    position_vols = [1250000, 675000, 900000]
    correlation = 0.2
    port_vol = calculate_portfolio_vol_uniform(position_vols, correlation)
    print(f"   Position Vols: ${position_vols}")
    print(f"   Correlation: {correlation}")
    print(f"   Portfolio Vol: ${port_vol:,.0f}\n")

    # Marginal vol
    print("3. Marginal Volatility:")
    new_vol = 500000
    current_vol = 2000000
    marg_vol = calculate_marginal_vol(new_vol, current_vol, 0.2)
    print(f"   New Position Vol: ${new_vol:,.0f}")
    print(f"   Current Portfolio Vol: ${current_vol:,.0f}")
    print(f"   Marginal Vol: ${marg_vol:,.0f}\n")

    # 2-sigma drawdowns
    print("4. 2-Sigma Drawdowns:")
    annual_vol_port = 10000000
    drawdowns = calculate_2sigma_drawdowns(annual_vol_port)
    print(f"   Annual Vol: ${annual_vol_port:,.0f}")
    for horizon, dd in drawdowns.items():
        print(f"   {horizon}: ${dd:,.0f}")
    print()

    # Entry score
    print("5. Entry Score:")
    score1 = calculate_entry_score(-1.5, "Long")
    score2 = calculate_entry_score(1.2, "Short")
    score3 = calculate_entry_score(0.5, "Long")
    print(f"   Long with z=-1.5: {score1}")
    print(f"   Short with z=1.2: {score2}")
    print(f"   Long with z=0.5: {score3}\n")

    # Max BPV
    print("6. Max BPV:")
    headroom = 5000000
    current_vol = 45000000
    rate_vol = 50
    max_bpv = calculate_max_bpv(headroom, current_vol, rate_vol, 0.2)
    print(f"   Headroom: ${headroom:,.0f}")
    print(f"   Current Vol: ${current_vol:,.0f}")
    print(f"   Rate Vol: {rate_vol}bp")
    print(f"   Max BPV: ${max_bpv:,.0f}k")
