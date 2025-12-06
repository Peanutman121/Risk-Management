"""
Script to create the Excel template for trader position tracking.

Generates template.xlsx with:
- Positions sheet (trade blotter with all fields)
- Settings sheet (trader configuration)
- Report sheet (placeholder for xlwings output)

Run this script to create or recreate the template.
"""

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))


def create_positions_sheet(wb):
    """Create the Positions sheet with all columns and formatting."""
    ws = wb.create_sheet("Positions", 0)

    # Column headers
    headers = [
        ("A", "Trade ID"),
        ("B", "Status"),
        ("C", "Headline"),
        ("D", "Ticker"),
        ("E", "Entry Date"),
        ("F", "Entry Level"),
        ("G", "Current Level"),
        ("H", "BPV ($k)"),
        ("I", "Direction"),
        ("J", "TP Level"),
        ("K", "TP Type"),
        ("L", "Trailing Offset (bp)"),
        ("M", "Stop Level"),
        ("N", "Rationale Type"),
        ("O", "Rationale Notes"),
        ("P", "Score 1: Directional"),
        ("Q", "Score 2: Valuation"),
        ("R", "Score 3: Flow"),
        ("S", "Score 4: Positioning"),
        ("T", "Score 5: Momentum/MR"),
        ("U", "Score 6: Liquidity"),
        ("V", "Score 7: Entry Z-Score"),
        ("W", "Score 8: Timing/Seasonal"),
        ("X", "Score 9: Expertise"),
        ("Y", "Total Score"),
        ("Z", "Exit Date"),
        ("AA", "Exit Level"),
        ("AB", "P&L ($)"),
        ("AC", "Postmortem"),
    ]

    # Write headers
    for col, header in headers:
        cell = ws[f"{col}1"]
        cell.value = header
        cell.font = Font(bold=True, size=11)
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Set column widths
    column_widths = {
        'A': 10, 'B': 10, 'C': 25, 'D': 18, 'E': 12, 'F': 12, 'G': 12, 'H': 10,
        'I': 10, 'J': 12, 'K': 10, 'L': 12, 'M': 12, 'N': 15, 'O': 30,
        'P': 10, 'Q': 10, 'R': 10, 'S': 10, 'T': 10, 'U': 10, 'V': 10,
        'W': 10, 'X': 10, 'Y': 12, 'Z': 12, 'AA': 12, 'AB': 15, 'AC': 30
    }

    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width

    # Freeze top row
    ws.freeze_panes = "A2"

    # Add data validation dropdowns
    # Status dropdown (column B)
    dv_status = DataValidation(type="list", formula1='"Open,Closed,Potential"', allow_blank=True)
    ws.add_data_validation(dv_status)
    dv_status.add(f"B2:B1000")

    # Direction dropdown (column I)
    dv_direction = DataValidation(type="list", formula1='"Long,Short"', allow_blank=True)
    ws.add_data_validation(dv_direction)
    dv_direction.add(f"I2:I1000")

    # TP Type dropdown (column K)
    dv_tp_type = DataValidation(type="list", formula1='"Fixed,Trailing"', allow_blank=True)
    ws.add_data_validation(dv_tp_type)
    dv_tp_type.add(f"K2:K1000")

    # Rationale Type dropdown (column N)
    dv_rationale = DataValidation(type="list", formula1='"Bottoms Up,Flow-Seasonal,Momentum,Model Valuation"', allow_blank=True)
    ws.add_data_validation(dv_rationale)
    dv_rationale.add(f"N2:N1000")

    # Score dropdowns (0 or 1) - columns P, Q, R, S, T, U, W, X
    dv_score_01 = DataValidation(type="list", formula1='"0,1"', allow_blank=True)
    ws.add_data_validation(dv_score_01)
    for col in ['P', 'Q', 'R', 'S', 'T', 'U', 'W', 'X']:
        dv_score_01.add(f"{col}2:{col}1000")

    # Score 7 dropdown (0, 0.5, 1) - column V
    dv_score_7 = DataValidation(type="list", formula1='"0,0.5,1"', allow_blank=True)
    ws.add_data_validation(dv_score_7)
    dv_score_7.add(f"V2:V1000")

    # Add formulas to row 2 (will be copied down by users)
    # Trade ID formula (column A)
    ws['A2'] = '=IF(B2<>"","TR"&TEXT(ROW()-1,"000"),"")'

    # Total Score formula (column Y)
    ws['Y2'] = '=IF(B2<>"",SUM(P2:X2),"")'

    # P&L formula (column AB)
    # =IF(I2="Long", (IFNA(AA2,G2)-F2)*H2*100*-1, IF(I2="Short", (F2-IFNA(AA2,G2))*H2*100*-1, ""))
    ws['AB2'] = '=IF(AND(B2<>"",I2<>"",F2<>"",H2<>""),IF(I2="Long",(IFNA(AA2,G2)-F2)*H2*100*-1,IF(I2="Short",(F2-IFNA(AA2,G2))*H2*100*-1,"")),""))'

    # Format number columns
    for row in range(2, 1001):
        # Date columns
        for col in ['E', 'Z']:
            ws[f"{col}{row}"].number_format = 'mm/dd/yyyy'

        # Number columns (4 decimal places)
        for col in ['F', 'G', 'J', 'M', 'AA']:
            ws[f"{col}{row}"].number_format = '0.0000'

        # Number columns (1 decimal place)
        for col in ['H', 'L']:
            ws[f"{col}{row}"].number_format = '0.0'

        # Score columns (1 decimal place)
        for col in ['P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y']:
            ws[f"{col}{row}"].number_format = '0.0'

        # Currency column (P&L)
        ws[f"AB{row}"].number_format = '$#,##0'

    # Add conditional formatting for P&L column
    # Note: openpyxl conditional formatting is complex, skipping for now
    # Users can add manually: Green if positive, Red if negative

    return ws


def create_settings_sheet(wb):
    """Create the Settings sheet."""
    ws = wb.create_sheet("Settings", 1)

    # Headers and fields
    settings = [
        ("Trader Name", ""),
        ("Risk Limit ($mm)", "10"),
        ("Default Correlation", "0.2"),
        ("Excel File Path", ""),
    ]

    for i, (label, default_value) in enumerate(settings, start=1):
        # Label in column A
        ws[f"A{i}"] = label
        ws[f"A{i}"].font = Font(bold=True)

        # Value in column B
        ws[f"B{i}"] = default_value

    # Set column widths
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 40

    return ws


def create_report_sheet(wb):
    """Create the Report sheet (placeholder)."""
    ws = wb.create_sheet("Report", 2)

    # Add header
    ws['A1'] = "Trader Report"
    ws['A1'].font = Font(bold=True, size=14)

    ws['A3'] = "This sheet is auto-generated by the xlwings report."
    ws['A4'] = "Click the 'Generate Report' button in Excel to populate this sheet."

    ws.column_dimensions['A'].width = 60

    return ws


def create_template(output_path):
    """
    Create the Excel template.

    Args:
        output_path: Path where template should be saved
    """
    # Create workbook
    wb = Workbook()

    # Remove default sheet
    if 'Sheet' in wb.sheetnames:
        del wb['Sheet']

    # Create sheets
    print("Creating Positions sheet...")
    create_positions_sheet(wb)

    print("Creating Settings sheet...")
    create_settings_sheet(wb)

    print("Creating Report sheet...")
    create_report_sheet(wb)

    # Save
    print(f"Saving template to: {output_path}")
    wb.save(output_path)

    print("✓ Template created successfully!")


def create_trader_files(template_path, excel_dir):
    """
    Create individual trader files from template.

    Args:
        template_path: Path to template file
        excel_dir: Directory to save trader files
    """
    import shutil

    trader_names = [
        "Trader 1",
        "Trader 2",
        "Trader 3",
        "Trader 4",
        "Trader 5",
    ]

    for i, name in enumerate(trader_names, start=1):
        output_file = excel_dir / f"positions_trader{i}.xlsx"

        # Copy template
        shutil.copy(template_path, output_file)

        # Open and update trader name
        wb = openpyxl.load_workbook(output_file)
        ws = wb["Settings"]
        ws['B1'] = name
        wb.save(output_file)

        print(f"✓ Created {output_file.name}")


if __name__ == "__main__":
    from config import EXCEL_DIR, TEMPLATE_FILE

    # Create excel directory if it doesn't exist
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)

    # Create template
    create_template(TEMPLATE_FILE)

    # Create trader files
    print("\nCreating trader files...")
    create_trader_files(TEMPLATE_FILE, EXCEL_DIR)

    print("\n✓ All files created successfully!")
    print(f"\nTemplate: {TEMPLATE_FILE}")
    print(f"Trader files: {EXCEL_DIR}/positions_trader*.xlsx")
