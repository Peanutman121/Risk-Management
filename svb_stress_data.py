"""
SVB/Credit Suisse stress scenario module.

Applies actual rate moves from March 8-15, 2023 during the
SVB/Credit Suisse crisis to assess portfolio stress impact.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SVBStressScenario:
    """
    SVB/Credit Suisse stress scenario calculator.

    Uses actual market moves from March 8-15, 2023.
    """

    def __init__(self, stress_file: Path):
        """
        Initialize SVB stress scenario.

        Args:
            stress_file: Path to CSV file with stress moves
                Expected columns: ticker, svb_move_bp, description
        """
        self.stress_file = stress_file
        self.stress_moves = {}

        # Load stress moves
        self._load_stress_moves()

    def _load_stress_moves(self):
        """Load SVB stress moves from CSV file."""
        try:
            df = pd.read_csv(self.stress_file)

            # Create dictionary: ticker -> move in bp
            self.stress_moves = dict(zip(df['ticker'], df['svb_move_bp']))

            logger.info(f"Loaded {len(self.stress_moves)} SVB stress moves")

        except FileNotFoundError:
            logger.error(f"SVB stress file not found: {self.stress_file}")
            self.stress_moves = {}
        except Exception as e:
            logger.error(f"Error loading SVB stress moves: {e}")
            self.stress_moves = {}

    def get_svb_move(self, ticker: str) -> Optional[float]:
        """
        Get SVB stress move for a ticker.

        Args:
            ticker: Market ticker (e.g., "USSW10 Curncy")

        Returns:
            SVB move in basis points, or None if not available
        """
        return self.stress_moves.get(ticker)

    def calculate_position_stress_pnl(
        self,
        ticker: str,
        direction: str,
        bpv: float
    ) -> Dict:
        """
        Calculate stress P&L for a single position.

        Args:
            ticker: Market ticker
            direction: "Long" or "Short"
            bpv: Basis point value in $thousands

        Returns:
            Dictionary with:
                - svb_move: Move in bp
                - stress_pnl: P&L in $
                - has_data: Whether stress data available
        """
        # Get SVB move
        svb_move = self.get_svb_move(ticker)

        if svb_move is None:
            return {
                'svb_move': None,
                'stress_pnl': None,
                'has_data': False
            }

        # Calculate P&L
        # For rates: Long positions lose when rates fall (negative move)
        #            Short positions gain when rates fall (negative move)
        if direction.upper() == "LONG":
            # Long: P&L = BPV × move × 100
            # Negative move = negative P&L (loss)
            stress_pnl = bpv * svb_move * 100
        elif direction.upper() == "SHORT":
            # Short: P&L = -BPV × move × 100
            # Negative move = positive P&L (gain)
            stress_pnl = -bpv * svb_move * 100
        else:
            logger.warning(f"Unknown direction: {direction}")
            stress_pnl = 0

        return {
            'svb_move': svb_move,
            'stress_pnl': stress_pnl,
            'has_data': True
        }

    def calculate_portfolio_stress_pnl(self, positions: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate stress P&L for entire portfolio.

        Args:
            positions: DataFrame with columns:
                - ticker
                - direction
                - bpv (basis point value in $k)

        Returns:
            DataFrame with columns:
                - ticker
                - direction
                - bpv
                - svb_move (bp)
                - stress_pnl ($)
                - has_data
        """
        results = []

        for _, row in positions.iterrows():
            ticker = row.get('ticker', '')
            direction = row.get('direction', '')
            bpv = row.get('bpv', 0)

            # Calculate stress for this position
            stress = self.calculate_position_stress_pnl(ticker, direction, bpv)

            results.append({
                'ticker': ticker,
                'direction': direction,
                'bpv': bpv,
                'svb_move': stress['svb_move'],
                'stress_pnl': stress['stress_pnl'],
                'has_data': stress['has_data']
            })

        # Create DataFrame
        df = pd.DataFrame(results)

        return df

    def get_portfolio_stress_summary(self, positions: pd.DataFrame) -> Dict:
        """
        Get summary statistics for portfolio stress scenario.

        Args:
            positions: DataFrame with position data

        Returns:
            Dictionary with summary statistics:
                - total_stress_pnl: Total portfolio P&L
                - worst_position: Worst single position P&L
                - best_position: Best single position P&L
                - num_positions: Number of positions
                - num_missing_data: Number of positions without stress data
        """
        stress_df = self.calculate_portfolio_stress_pnl(positions)

        # Filter to positions with data
        with_data = stress_df[stress_df['has_data'] == True]

        if with_data.empty:
            return {
                'total_stress_pnl': 0,
                'worst_position': 0,
                'worst_position_ticker': None,
                'best_position': 0,
                'best_position_ticker': None,
                'num_positions': len(stress_df),
                'num_missing_data': len(stress_df)
            }

        total_pnl = with_data['stress_pnl'].sum()

        # Find worst and best positions
        worst_idx = with_data['stress_pnl'].idxmin()
        best_idx = with_data['stress_pnl'].idxmax()

        return {
            'total_stress_pnl': total_pnl,
            'worst_position': with_data.loc[worst_idx, 'stress_pnl'],
            'worst_position_ticker': with_data.loc[worst_idx, 'ticker'],
            'best_position': with_data.loc[best_idx, 'stress_pnl'],
            'best_position_ticker': with_data.loc[best_idx, 'ticker'],
            'num_positions': len(stress_df),
            'num_missing_data': len(stress_df[stress_df['has_data'] == False])
        }

    def get_available_tickers(self) -> list:
        """
        Get list of tickers with stress data available.

        Returns:
            List of tickers
        """
        return list(self.stress_moves.keys())

    def add_stress_move(self, ticker: str, move_bp: float):
        """
        Add or update stress move for a ticker.

        Args:
            ticker: Market ticker
            move_bp: Move in basis points
        """
        self.stress_moves[ticker] = move_bp
        logger.info(f"Added/updated stress move for {ticker}: {move_bp} bp")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def load_svb_scenario(stress_file: Path = None) -> SVBStressScenario:
    """
    Load SVB stress scenario from default or specified file.

    Args:
        stress_file: Path to stress moves CSV (optional)

    Returns:
        SVBStressScenario instance
    """
    if stress_file is None:
        # Use default path
        from config import SVB_STRESS_FILE
        stress_file = SVB_STRESS_FILE

    return SVBStressScenario(stress_file)


def calculate_position_svb_pnl(ticker: str, direction: str, bpv: float) -> float:
    """
    Calculate SVB stress P&L for a single position (convenience function).

    Args:
        ticker: Market ticker
        direction: "Long" or "Short"
        bpv: Basis point value in $k

    Returns:
        Stress P&L in $, or 0 if no data available
    """
    scenario = load_svb_scenario()
    result = scenario.calculate_position_stress_pnl(ticker, direction, bpv)
    return result['stress_pnl'] if result['stress_pnl'] is not None else 0


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example usage
    from config import SVB_STRESS_FILE

    # Load scenario
    scenario = SVBStressScenario(SVB_STRESS_FILE)

    print(f"Loaded stress data for {len(scenario.stress_moves)} tickers")
    print("\nSample stress moves:")
    for ticker in list(scenario.stress_moves.keys())[:5]:
        move = scenario.get_svb_move(ticker)
        print(f"  {ticker}: {move} bp")

    # Example: Calculate stress for a position
    print("\nExample: Long 250k BPV USSW10")
    result = scenario.calculate_position_stress_pnl("USSW10 Curncy", "Long", 250)
    print(f"  SVB Move: {result['svb_move']} bp")
    print(f"  Stress P&L: ${result['stress_pnl']:,.0f}")

    print("\nExample: Short 150k BPV USSW5")
    result = scenario.calculate_position_stress_pnl("USSW5 Curncy", "Short", 150)
    print(f"  SVB Move: {result['svb_move']} bp")
    print(f"  Stress P&L: ${result['stress_pnl']:,.0f}")

    # Example: Portfolio
    print("\nExample: Portfolio stress")
    positions = pd.DataFrame([
        {'ticker': 'USSW10 Curncy', 'direction': 'Long', 'bpv': 250},
        {'ticker': 'USSW5 Curncy', 'direction': 'Short', 'bpv': 150},
        {'ticker': 'EUSA10 Curncy', 'direction': 'Long', 'bpv': 180},
    ])

    summary = scenario.get_portfolio_stress_summary(positions)
    print(f"  Total Stress P&L: ${summary['total_stress_pnl']:,.0f}")
    print(f"  Worst Position: {summary['worst_position_ticker']} (${summary['worst_position']:,.0f})")
    print(f"  Best Position: {summary['best_position_ticker']} (${summary['best_position']:,.0f})")
