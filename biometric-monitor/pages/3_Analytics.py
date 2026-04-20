import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Analytics", page_icon="📈", layout="wide")

if st.session_state.get('processed_data') is None:
    st.info("👈 Please upload Excel files and process data first")
    st.stop()

df = st.session_state.processed_data

st.title("📈 Analytics")

# Statistics
st.subheader("Statistical Summary")
stats = pd.DataFrame({
    'Metric': ['Mean Days', 'Median Days', 'Max Days', 'Min Days', 'Std Dev'],
    'Value': [
        f"{df['Days Inactive'].mean():.1f}",
        f"{df['Days Inactive'].median():.1f}",
        df['Days Inactive'].max(),
        df['Days Inactive'].min(),
        f"{df['Days Inactive'].std():.1f}"
    ]
})
st.dataframe(stats, use_container_width=True)

# Distribution
st.subheader("Days Inactive Distribution")
fig = px.box(df, y='Days Inactive', title="Distribution of Inactive Days")
st.plotly_chart(fig, use_container_width=True)

# Status by Location (if available)
if 'Location' in df.columns:
    st.subheader("Status by Location")
    location_status = pd.crosstab(df['Location'], df['Status'])
    fig = px.bar(location_status, barmode='group', title="Devices by Location and Status")
    st.plotly_chart(fig, use_container_width=True)
