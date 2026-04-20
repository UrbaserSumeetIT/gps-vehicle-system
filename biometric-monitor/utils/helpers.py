"""
Helper functions
"""

import pandas as pd
import base64
import io
from datetime import datetime

def format_datetime(dt):
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def create_download_link(df, filename):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}.csv">Download CSV</a>'
    return href

def get_status_color(status):
    colors = {
        '✅ Active': '#90EE90',
        '⚠️ Inactive': '#FFB6C1',
        '❌ Critical': '#FF6B6B'
    }
    return colors.get(status, '#FFFFFF')
