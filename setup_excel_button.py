"""
Add VBA macro button to Excel template for one-click report generation.

This script adds a "Generate Report" button to the Excel template that
traders can click to generate their risk report without touching Python.
"""

import openpyxl
from openpyxl.drawing.image import Image as ExcelImage
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from config import TEMPLATE_FILE, TRADER_FILES


VBA_CODE = """
Sub GenerateReport()
    ' Generate trader risk report using xlwings

    Dim pythonPath As String
    Dim scriptPath As String
    Dim traderNum As String
    Dim excelPath As String
    Dim command As String

    ' Get current workbook path
    excelPath = ThisWorkbook.FullName

    ' Extract trader number from filename
    ' Assumes filename like "positions_trader1.xlsx"
    Dim fileName As String
    fileName = ThisWorkbook.Name
    traderNum = Mid(fileName, InStrRev(fileName, "trader") + 6, 1)

    ' Path to Python script (adjust as needed)
    scriptPath = ThisWorkbook.Path & "\\..\\python\\xlwings_report.py"

    ' Python command
    ' Option 1: Using system Python
    pythonPath = "python"

    ' Option 2: Using virtual environment (uncomment if needed)
    ' pythonPath = ThisWorkbook.Path & "\\..\\venv\\Scripts\\python.exe"

    ' Build command
    command = pythonPath & " " & scriptPath & " --trader " & traderNum & " --xlwings"

    ' Show message
    Application.StatusBar = "Generating report..."
    Application.ScreenUpdating = False

    ' Run Python script
    Dim result As Integer
    result = Shell(command, vbNormalFocus)

    ' Wait a moment for processing
    Application.Wait (Now + TimeValue("0:00:03"))

    ' Refresh the Report sheet
    Sheets("Report").Select

    Application.ScreenUpdating = True
    Application.StatusBar = False

    MsgBox "Report generated successfully!", vbInformation, "Risk Report"

End Sub
"""

# Alternative using xlwings UDF (better integration)
VBA_CODE_XLWINGS = """
Sub GenerateReport()
    ' Generate report using xlwings Python call

    Application.StatusBar = "Generating report..."
    Application.ScreenUpdating = False

    ' Call Python function via xlwings
    RunPython "import sys; sys.path.append(r'" & ThisWorkbook.Path & "\\..\\python'); " & _
             "from xlwings_report import generate_report_from_excel; " & _
             "generate_report_from_excel()"

    ' Refresh Report sheet
    Sheets("Report").Select

    Application.ScreenUpdating = True
    Application.StatusBar = False

    MsgBox "Report generated successfully!", vbInformation, "Risk Report"
End Sub
"""


def add_button_instructions():
    """
    Print instructions for manually adding a button to Excel.

    Since openpyxl can't add VBA macros or buttons programmatically,
    we provide manual instructions.
    """

    print("""
╔══════════════════════════════════════════════════════════════════╗
║  EXCEL BUTTON SETUP INSTRUCTIONS                                 ║
╚══════════════════════════════════════════════════════════════════╝

Follow these steps to add a "Generate Report" button to each trader Excel file:

STEP 1: Enable Developer Tab (One-Time Setup)
─────────────────────────────────────────────
1. Open Excel
2. File → Options → Customize Ribbon
3. Check "Developer" on the right side
4. Click OK


STEP 2: Add VBA Macro (Do for template.xlsx first)
──────────────────────────────────────────────────
1. Open: excel/template.xlsx
2. Press Alt + F11 (opens VBA editor)
3. In VBA editor: Insert → Module
4. Copy and paste this code into the module:

""")

    print("─" * 70)
    print(VBA_CODE_XLWINGS)
    print("─" * 70)

    print("""

STEP 3: Add Button to Excel Sheet
──────────────────────────────────
1. Go back to Excel (close VBA editor)
2. Go to "Report" sheet
3. Click "Developer" tab → Insert → Button (Form Control)
4. Draw the button where you want it (top of Report sheet)
5. In the popup, select "GenerateReport" macro
6. Right-click button → Edit Text → Change to "🔄 Generate Report"
7. Resize and style as needed


STEP 4: Save as Macro-Enabled Workbook
───────────────────────────────────────
1. File → Save As
2. Change file type to "Excel Macro-Enabled Workbook (*.xlsm)"
3. Save as: excel/template.xlsm


STEP 5: Update Template Script
───────────────────────────────
Edit python/create_excel_template.py:
Change: TEMPLATE_FILE = EXCEL_DIR / "template.xlsx"
To:     TEMPLATE_FILE = EXCEL_DIR / "template.xlsm"

And change file extension in TRADER_FILES:
positions_trader1.xlsx → positions_trader1.xlsm


STEP 6: Create Trader Files from New Template
──────────────────────────────────────────────
Run: python python/create_excel_template.py

This creates .xlsm files with the button for all traders.


STEP 7: Test It!
────────────────
1. Open excel/positions_trader1.xlsm
2. Go to Report sheet
3. Click "🔄 Generate Report" button
4. Report should auto-generate!


ALTERNATIVE: Simpler Version Without xlwings
─────────────────────────────────────────────
If xlwings is difficult to set up, use this simpler VBA code instead:

""")

    print("─" * 70)
    print(VBA_CODE)
    print("─" * 70)

    print("""

This version just runs the Python script via shell command.
Less integrated but easier to set up.

╔══════════════════════════════════════════════════════════════════╗
║  NOTES                                                           ║
╚══════════════════════════════════════════════════════════════════╝

• You need to do this once for the template
• All trader files created from the template will have the button
• Traders just click the button - no Python knowledge needed!
• Make sure Python is in the system PATH or update pythonPath in VBA

""")


if __name__ == "__main__":
    add_button_instructions()
