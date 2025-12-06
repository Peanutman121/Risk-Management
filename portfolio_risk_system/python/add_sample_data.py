"""
Add sample data to trader Excel files for testing.

Creates realistic sample positions across 5 traders.
"""

import openpyxl
from datetime import datetime, timedelta
import random
from pathlib import Path
from config import TRADER_FILES, SHEET_POSITIONS


# Sample data templates
SAMPLE_TRADES = [
    # Trader 1
    [
        ["Open", "Long 10y USD swap", "USSW10 Curncy", "2024-11-01", 4.25, 4.20, 250, "Long", 4.00, "Fixed", None, 4.35, "Model Valuation", "Rich-cheap model shows 10y USD undervalued vs fundamentals", 1, 1, 0, 1, 1, 1, None, 1, 1],
        ["Open", "Short 5y USD swap", "USSW5 Curncy", "2024-11-15", 4.10, 4.15, 150, "Short", 4.30, "Fixed", None, 4.05, "Momentum", "Front-end rates showing strong upward momentum", 1, 0, 1, 1, 1, 1, None, 0, 1],
        ["Closed", "Long 2y EUR swap", "EUSA2 Curncy", "2024-10-01", 2.80, None, 100, "Long", 2.60, "Fixed", None, 2.95, "Flow-Seasonal", "ECB dovish, client flows supportive", 1, 1, 1, 0, 0, 1, None, 1, 1, "2024-11-20", 2.70, None, "Hit TP as ECB cut rates. Good timing."],
        ["Potential", "Long 5s30s EUR curve", "EUSA5 Curncy", None, 0.85, None, 100, "Long", 1.10, "Trailing", 15, 0.70, "Bottoms Up", "Curve too flat, expecting steepening", 1, 1, 1, 0, 0, 1, None, 1, 1],
    ],

    # Trader 2
    [
        ["Open", "Long 10y EUR swap", "EUSA10 Curncy", "2024-10-15", 2.85, 2.80, 180, "Long", 2.60, "Fixed", None, 3.00, "Model Valuation", "EUR rates look cheap vs USD on real rates basis", 1, 1, 0, 0, 1, 1, None, 0, 1],
        ["Open", "Short 2y USD swap", "USSW2 Curncy", "2024-11-20", 4.65, 4.70, 100, "Short", 4.85, "Fixed", None, 4.55, "Momentum", "Fed pivot trade, front-end should rise", 0, 0, 1, 1, 1, 1, None, 1, 1],
        ["Closed", "Long 30y USD swap", "USSW30 Curncy", "2024-09-15", 4.50, None, 200, "Long", 4.30, "Fixed", None, 4.60, "Flow-Seasonal", "Pension rebalancing flows", 1, 0, 1, 1, 0, 1, None, 1, 1, "2024-10-30", 4.45, None, "Small profit, exited early on vol spike"],
    ],

    # Trader 3
    [
        ["Open", "Long 5y GBP swap", "BPSW5 Curncy", "2024-11-10", 4.30, 4.25, 120, "Long", 4.10, "Fixed", None, 4.45, "Bottoms Up", "BoE on hold longer than priced", 1, 1, 1, 1, 0, 1, None, 1, 1],
        ["Open", "Short 10y USD swap", "USSW10 Curncy", "2024-11-25", 4.30, 4.35, 80, "Short", 4.50, "Fixed", None, 4.20, "Model Valuation", "10y overvalued after rally", 0, 1, 0, 0, 0, 1, None, 0, 1],
        ["Potential", "Long 2y GBP swap", "BPSW2 Curncy", None, 4.80, None, 150, "Long", 4.60, "Fixed", None, 4.95, "Flow-Seasonal", "Year-end positioning opportunity", 1, 0, 1, 1, 0, 1, None, 1, 1],
    ],

    # Trader 4
    [
        ["Open", "Long 7y USD swap", "USSW7 Curncy", "2024-10-20", 4.20, 4.15, 200, "Long", 4.00, "Trailing", 10, 4.30, "Momentum", "Strong technical levels", 1, 0, 0, 1, 1, 1, None, 1, 1],
        ["Closed", "Short 5y EUR swap", "EUSA5 Curncy", "2024-09-01", 2.60, None, 150, "Short", 2.80, "Fixed", None, 2.50, "Bottoms Up", "ECB still hiking", 1, 0, 1, 1, 1, 1, None, 0, 1, "2024-11-15", 2.70, None, "Took profit as ECB signaled pause"],
    ],

    # Trader 5
    [
        ["Open", "Long 10y GBP swap", "BPSW10 Curncy", "2024-11-05", 4.40, 4.35, 160, "Long", 4.20, "Fixed", None, 4.55, "Flow-Seasonal", "Gilt issuance supportive", 1, 1, 1, 0, 0, 1, None, 1, 1],
        ["Open", "Short 30y USD swap", "USSW30 Curncy", "2024-11-18", 4.55, 4.60, 90, "Short", 4.75, "Fixed", None, 4.45, "Model Valuation", "Long-end expensive", 1, 1, 0, 0, 0, 1, None, 0, 1],
        ["Potential", "Long 3y USD swap", "USSW3 Curncy", None, 4.15, None, 130, "Long", 3.95, "Fixed", None, 4.30, "Bottoms Up", "3y sector looks attractive", 1, 1, 1, 0, 1, 1, None, 1, 1],
    ],
]


def add_sample_data_to_trader(filepath: Path, trades: list, trader_num: int):
    """
    Add sample trades to a trader file.

    Args:
        filepath: Path to trader Excel file
        trades: List of trade data
        trader_num: Trader number (for logging)
    """
    wb = openpyxl.load_workbook(filepath)
    ws = wb[SHEET_POSITIONS]

    # Add each trade
    for i, trade in enumerate(trades, start=2):
        # Map fields to columns
        # [Status, Headline, Ticker, Entry Date, Entry Level, Current Level, BPV, Direction,
        #  TP Level, TP Type, Trailing Offset, Stop Level, Rationale Type, Rationale Notes,
        #  Score 1-6, Score 7, Score 8-9, Exit Date, Exit Level, unused, Postmortem]

        status, headline, ticker, entry_date, entry_level, current_level, bpv, direction = trade[0:8]
        tp_level, tp_type, trailing_offset, stop_level, rationale_type, rationale_notes = trade[8:14]
        score_1, score_2, score_3, score_4, score_5, score_6, score_7, score_8, score_9 = trade[14:23]

        # Handle closed trades
        exit_date = trade[23] if len(trade) > 23 else None
        exit_level = trade[24] if len(trade) > 24 else None
        postmortem = trade[26] if len(trade) > 26 else None

        # Convert dates
        if entry_date:
            entry_date = datetime.strptime(entry_date, "%Y-%m-%d")
        if exit_date:
            exit_date = datetime.strptime(exit_date, "%Y-%m-%d")

        # Write to row
        row = i

        # Trade ID (formula will auto-generate)
        ws[f'A{row}'] = f'=IF(B{row}<>"","TR"&TEXT(ROW()-1,"000"),"")'

        # Basic fields
        ws[f'B{row}'] = status
        ws[f'C{row}'] = headline
        ws[f'D{row}'] = ticker
        ws[f'E{row}'] = entry_date
        ws[f'F{row}'] = entry_level
        ws[f'G{row}'] = current_level
        ws[f'H{row}'] = bpv
        ws[f'I{row}'] = direction
        ws[f'J{row}'] = tp_level
        ws[f'K{row}'] = tp_type
        ws[f'L{row}'] = trailing_offset
        ws[f'M{row}'] = stop_level
        ws[f'N{row}'] = rationale_type
        ws[f'O{row}'] = rationale_notes

        # Scores
        ws[f'P{row}'] = score_1
        ws[f'Q{row}'] = score_2
        ws[f'R{row}'] = score_3
        ws[f'S{row}'] = score_4
        ws[f'T{row}'] = score_5
        ws[f'U{row}'] = score_6
        ws[f'V{row}'] = score_7 if score_7 is not None else 0.5  # Placeholder for z-score
        ws[f'W{row}'] = score_8
        ws[f'X{row}'] = score_9

        # Total Score (formula)
        ws[f'Y{row}'] = f'=IF(B{row}<>"",SUM(P{row}:X{row}),"")'

        # Exit details
        ws[f'Z{row}'] = exit_date
        ws[f'AA{row}'] = exit_level

        # P&L (formula)
        ws[f'AB{row}'] = f'=IF(AND(B{row}<>"",I{row}<>"",F{row}<>"",H{row}<>""),IF(I{row}="Long",(IFNA(AA{row},G{row})-F{row})*H{row}*100*-1,IF(I{row}="Short",(F{row}-IFNA(AA{row},G{row}))*H{row}*100*-1,"")),""))'

        # Postmortem
        ws[f'AC{row}'] = postmortem

    # Save
    wb.save(filepath)
    print(f"✓ Added {len(trades)} sample trades to Trader {trader_num}")


def main():
    """Add sample data to all trader files."""
    print("Adding sample data to trader files...\n")

    for trader_num, trades in enumerate(SAMPLE_TRADES, start=1):
        filepath = TRADER_FILES[trader_num]
        if filepath.exists():
            add_sample_data_to_trader(filepath, trades, trader_num)
        else:
            print(f"✗ File not found: {filepath}")

    print("\n✓ Sample data added to all trader files!")
    print("You can now open the Excel files to view the sample positions.")


if __name__ == "__main__":
    from config import TRADER_FILES, SHEET_POSITIONS
    main()
