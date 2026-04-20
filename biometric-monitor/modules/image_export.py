"""
Image Export Module
"""

import matplotlib.pyplot as plt
import pandas as pd
import io
import base64
import streamlit as st
from datetime import datetime

def dataframe_to_image(df, title, max_rows=100):
    filtered_df = df.head(max_rows)
    
    fig, ax = plt.subplots(figsize=(14, min(20, len(filtered_df) * 0.3 + 2)))
    ax.axis('tight')
    ax.axis('off')
    
    table = ax.table(cellText=filtered_df.values, colLabels=filtered_df.columns,
                     cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.2, 1.5)
    
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_facecolor('#667eea')
            cell.set_text_props(weight='bold', color='white')
    
    ax.set_title(title, fontsize=14, weight='bold', pad=20)
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def create_image_export_ui(df, table_name):
    max_rows = st.number_input(f"Max rows for {table_name}", 10, 200, 50, key=f"rows_{table_name}")
    
    if st.button(f"📸 Export {table_name} as Image", key=f"export_{table_name}"):
        img_buf = dataframe_to_image(df, f"{table_name} - {datetime.now().strftime('%Y-%m-%d')}", max_rows)
        b64 = base64.b64encode(img_buf.getvalue()).decode()
        href = f'<a href="data:image/png;base64,{b64}" download="{table_name.lower().replace(" ", "_")}.png">Download Image</a>'
        st.markdown(href, unsafe_allow_html=True)
        st.success("Image ready!")
