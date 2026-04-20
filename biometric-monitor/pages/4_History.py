import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="History", page_icon="📜", layout="wide")

st.title("📜 Processing History")

if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

if st.session_state.processing_history:
    history_df = pd.DataFrame(st.session_state.processing_history)
    history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
    history_df = history_df.sort_values('timestamp', ascending=False)
    
    display = history_df[['timestamp', 'file_name', 'total_devices', 'active_count', 'inactive_count']].copy()
    display.columns = ['Date & Time', 'File Name', 'Total', 'Active', 'Inactive']
    st.dataframe(display, use_container_width=True)
else:
    st.info("No processing history yet. Upload and process some data!")

st.markdown("---")
st.subheader("💾 Saved Reports")

if 'saved_reports' not in st.session_state:
    st.session_state.saved_reports = []

if st.button("💾 Save Current Report"):
    if st.session_state.processed_data is not None:
        report_name = f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.saved_reports.append({
            'name': report_name,
            'date': datetime.now(),
            'data': st.session_state.processed_data.copy()
        })
        st.success(f"Saved: {report_name}")
        st.rerun()
    else:
        st.warning("No data to save")

for idx, report in enumerate(reversed(st.session_state.saved_reports)):
    with st.expander(f"📄 {report['name']} - {report['date'].strftime('%Y-%m-%d %H:%M')}"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"Load", key=f"load_{idx}"):
                st.session_state.processed_data = report['data']
                st.success("Report loaded!")
                st.rerun()
        with col2:
            if st.button(f"Delete", key=f"del_{idx}"):
                st.session_state.saved_reports.pop(len(st.session_state.saved_reports) - 1 - idx)
                st.rerun()
