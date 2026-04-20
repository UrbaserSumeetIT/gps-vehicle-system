import streamlit as st
import pandas as pd

st.set_page_config(page_title="Device Data", page_icon="📋", layout="wide")

if st.session_state.get('processed_data') is None:
    st.info("👈 Please upload Excel files and process data first")
    st.stop()

df = st.session_state.processed_data

st.title("📋 Device Data")

# Filters
col1, col2 = st.columns(2)
with col1:
    status_filter = st.multiselect("Filter by Status", df['Status'].unique(), default=df['Status'].unique())
with col2:
    search = st.text_input("🔍 Search", placeholder="Serial Number...")

# Apply filters
filtered = df[df['Status'].isin(status_filter)]
if search:
    filtered = filtered[filtered['Serial Number'].astype(str).str.contains(search, case=False)]

# Color coding
def highlight_status(val):
    if '✅' in str(val):
        return 'background-color: #90EE90'
    elif '⚠️' in str(val):
        return 'background-color: #FFB6C1'
    elif '❌' in str(val):
        return 'background-color: #FF6B6B'
    return ''

styled = filtered.style.applymap(highlight_status, subset=['Status'])
st.dataframe(styled, use_container_width=True, height=500)
st.caption(f"Showing {len(filtered)} of {len(df)} devices")

# Export
if st.button("📥 Export Filtered Data"):
    csv = filtered.to_csv(index=False)
    st.download_button("Download CSV", csv, "filtered_devices.csv", "text/csv")
