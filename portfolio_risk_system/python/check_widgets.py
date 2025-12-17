"""
Diagnostic script to check for missing widget keys in Streamlit apps.
This will identify widgets that need keys to prevent freezing.
"""

import re
from pathlib import Path

def find_widgets_without_keys(file_path):
    """Find Streamlit widgets that don't have key parameters."""

    with open(file_path, 'r') as f:
        content = f.read()

    # Widget patterns to search for
    widget_patterns = [
        r'st\.selectbox\([^)]+\)',
        r'st\.multiselect\([^)]+\)',
        r'st\.slider\([^)]+\)',
        r'st\.number_input\([^)]+\)',
        r'st\.text_input\([^)]+\)',
        r'st\.radio\([^)]+\)',
    ]

    issues = []

    for pattern in widget_patterns:
        matches = re.finditer(pattern, content, re.MULTILINE)
        for match in matches:
            widget_call = match.group(0)
            # Check if it has a key parameter
            if 'key=' not in widget_call:
                # Find line number
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    'line': line_num,
                    'code': widget_call,
                    'type': widget_call.split('(')[0]
                })

    return issues


if __name__ == "__main__":
    # Check both Streamlit apps
    apps = [
        Path('python/streamlit_app.py'),
        Path('python/streamlit_app_fast.py')
    ]

    for app_path in apps:
        if app_path.exists():
            print(f"\n{'='*70}")
            print(f"Checking: {app_path}")
            print(f"{'='*70}")

            issues = find_widgets_without_keys(app_path)

            if issues:
                print(f"\n❌ Found {len(issues)} widgets WITHOUT keys (causes freezing):\n")
                for issue in issues[:10]:  # Show first 10
                    print(f"Line {issue['line']}: {issue['type']}")
                    print(f"  {issue['code'][:80]}...")
                    print()

                if len(issues) > 10:
                    print(f"... and {len(issues) - 10} more")
            else:
                print("\n✅ All widgets have keys!")
        else:
            print(f"\n⚠️  Not found: {app_path}")

    print(f"\n{'='*70}")
    print("RECOMMENDATION:")
    print("Every widget needs a unique key parameter to prevent freezing.")
    print("Example: st.selectbox('Label', options, key='unique_name')")
    print(f"{'='*70}\n")
