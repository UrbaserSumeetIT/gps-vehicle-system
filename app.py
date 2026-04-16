import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64
from pathlib import Path
import hashlib
import json

# Page configuration
st.set_page_config(
    page_title="Biometric Device Monitor Pro",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem;
        font-weight: bold;
    }
    .status-active {
        background-color: #00ff00;
        color: #000000;
        padding: 4px 8px;
        border-radius: 12px;
        font-weight: bold;
        text-align: center;
    }
    .status-inactive {
        background-color: #ff0000;
        color: #ffffff;
        padding: 4px 8px;
        border-radius: 12px;
        font-weight: bold;
        text-align: center;
    }
    .status-blocked {
        background-color: #808080;
        color: #ffffff;
        padding: 4px 8px;
        border-radius: 12px;
        font-weight: bold;
        text-align: center;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        transition: transform 0.3s;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'summary_data' not in st.session_state:
    st.session_state.summary_data = None
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []
if 'alerts_config' not in st.session_state:
    st.session_state.alerts_config = {
        'inactive_threshold': 30,
        'email_alerts': False,
        'email_recipient': ''
    }
if 'saved_reports' not in st.session_state:
    st.session_state.saved_reports = []
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

# Title and description
st.markdown('<div class="main-header">🏢 Biometric Device Monitoring System PRO</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar for file upload and settings
with st.sidebar:
    st.header("📁 Data Upload")
    
    portal_file = st.file_uploader(
        "**Device Export File** (Excel)",
        type=['xlsx', 'xls'],
        help="Required columns: 'Serial Number', 'Last Activity'",
        key="portal_uploader"
    )
    
    master_file = st.file_uploader(
        "**Biometric Master File** (Excel)",
        type=['xlsx', 'xls'],
        help="Required columns: 'Serial Number', 'Area', 'Ward'",
        key="master_uploader"
    )
    
    st.markdown("---")
    
    # Advanced Settings
    with st.expander("⚙️ **Advanced Settings**", expanded=False):
        st.subheader("Status Rules Configuration")
        
        col1, col2 = st.columns(2)
        with col1:
            active_days = st.number_input("Active Days Threshold", min_value=1, max_value=30, value=2)
        with col2:
            warning_days = st.number_input("Warning Days", min_value=7, max_value=90, value=30)
        
        st.subheader("Alert Configuration")
        st.session_state.alerts_config['inactive_threshold'] = st.slider(
            "Inactive Alert Threshold (days)", 
            min_value=7, 
            max_value=90, 
            value=st.session_state.alerts_config['inactive_threshold']
        )
        
        st.session_state.alerts_config['email_alerts'] = st.checkbox("Enable Email Alerts", value=st.session_state.alerts_config['email_alerts'])
        
        if st.session_state.alerts_config['email_alerts']:
            st.session_state.alerts_config['email_recipient'] = st.text_input("Recipient Email", value=st.session_state.alerts_config['email_recipient'])
    
    process_button = st.button("🚀 **Process Data**", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    with st.expander("📋 **Status Rules**", expanded=False):
        st.markdown(f"""
        ### 🎯 Logic Applied:
        1. **If Ward is NULL/Empty** → Status = Area value
        2. **If Days ≤ {active_days} AND Area ≠ 'Not Authorized'** → ✅ Active
        3. **If Days > {active_days} AND Area ≠ 'Not Authorized'** → ⚠️ Inactive
        4. **If Area = 'Not Authorized'** → 🚫 Blocked
        """)
    
    # Export section
    if st.session_state.processed_data is not None:
        st.markdown("---")
        st.header("📥 Export Options")
        
        export_format = st.selectbox("Select Format", ['CSV', 'Excel', 'JSON'])
        
        if st.button(f"Download as {export_format}", use_container_width=True):
            if export_format == 'CSV':
                csv = st.session_state.processed_data.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="biometric_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv">Click to Download</a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("✅ CSV ready for download!")
                
            elif export_format == 'Excel':
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    st.session_state.processed_data.to_excel(writer, sheet_name='Processed Data', index=False)
                    if st.session_state.summary_data is not None:
                        st.session_state.summary_data.to_excel(writer, sheet_name='Summary', index=False)
                excel_data = output.getvalue()
                b64 = base64.b64encode(excel_data).decode()
                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="biometric_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx">Click to Download</a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("✅ Excel report ready!")
                
            elif export_format == 'JSON':
                json_str = st.session_state.processed_data.to_json(orient='records', date_format='iso')
                b64 = base64.b64encode(json_str.encode()).decode()
                href = f'<a href="data:file/json;base64,{b64}" download="biometric_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json">Click to Download</a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("✅ JSON ready!")

# Processing function
def process_biometric_data(portal_file, master_file, active_threshold=2):
    try:
        portal_df = pd.read_excel(portal_file)
        try:
            master_df = pd.read_excel(master_file, sheet_name="Master")
        except Exception:
            master_df = pd.read_excel(master_file)
        
        def find_serial_column(df):
            for col in df.columns:
                col_lower = col.lower()
                if 'serial' in col_lower or 's/no' in col_lower or 'device' in col_lower or 'sl no' in col_lower:
                    return col
            return None
        
        portal_serial_col = find_serial_column(portal_df)
        master_serial_col = find_serial_column(master_df)
        
        if portal_serial_col is None or master_serial_col is None:
            st.error("❌ Could not find 'Serial Number' column!")
            return None, None
        
        if portal_serial_col != 'Serial Number':
            portal_df = portal_df.rename(columns={portal_serial_col: 'Serial Number'})
        if master_serial_col != 'Serial Number':
            master_df = master_df.rename(columns={master_serial_col: 'Serial Number'})
        
        merged = master_df.merge(portal_df, on="Serial Number", how="left")
        
        last_activity_col = None
        for col in merged.columns:
            col_lower = col.lower()
            if 'last' in col_lower and ('activity' in col_lower or 'login' in col_lower or 'used' in col_lower):
                last_activity_col = col
                break
        
        if last_activity_col is None:
            st.error(f"❌ Could not find 'Last Activity' column!")
            return None, None
        
        merged['Last Activity Date'] = pd.to_datetime(merged[last_activity_col], errors='coerce')
        
        max_date = merged['Last Activity Date'].max()
        if pd.isna(max_date):
            merged['Days Inactive'] = 0
        else:
            merged['Days Inactive'] = (max_date - merged['Last Activity Date']).dt.days
            merged['Days Inactive'] = merged['Days Inactive'].fillna(0)
        
        def determine_status(row):
            ward = row.get('Ward', '')
            ward_null = pd.isna(ward) or str(ward).strip() == '' or str(ward).strip().lower() == 'nan'
            
            if ward_null:
                area_val = row.get('Area', 'Unknown')
                return str(area_val) if not pd.isna(area_val) else 'Unknown'
            
            area = str(row.get('Area', '')).strip()
            days = row.get('Days Inactive', 0)
            
            if area == 'Not Authorized':
                return '🚫 Blocked'
            elif days <= active_threshold:
                return '✅ Active'
            else:
                return '⚠️ Inactive'
        
        merged['Status'] = merged.apply(determine_status, axis=1)
        
        summary = merged['Status'].value_counts().reset_index()
        summary.columns = ['Status', 'Count']
        summary['Percentage'] = (summary['Count'] / summary['Count'].sum() * 100).round(1)
        
        severity = {'✅ Active': 1, '⚠️ Inactive': 2, '🚫 Blocked': 3}
        summary['Sort Order'] = summary['Status'].map(lambda x: severity.get(x, 4))
        summary = summary.sort_values('Sort Order').drop('Sort Order', axis=1)
        
        display_cols = ['Serial Number', 'Days Inactive', 'Status']
        if 'Area' in merged.columns:
            display_cols.insert(1, 'Area')
        if 'Ward' in merged.columns:
            display_cols.insert(2, 'Ward')
        if last_activity_col:
            display_cols.append(last_activity_col)
        
        result_df = merged[display_cols].copy()
        result_df['Processed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return result_df, summary
        
    except Exception as e:
        st.error(f"❌ Error processing files: {str(e)}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())
        return None, None

# Process when button is clicked
if process_button:
    if portal_file is None or master_file is None:
        st.warning("⚠️ Please upload both files before processing!")
    else:
        with st.spinner("🔄 Processing data... Please wait"):
            processed_df, summary_df = process_biometric_data(portal_file, master_file, active_days)
            
            if processed_df is not None:
                st.session_state.processed_data = processed_df
                st.session_state.summary_data = summary_df
                
                st.session_state.processing_history.append({
                    'timestamp': datetime.now(),
                    'total_devices': len(processed_df),
                    'file_name': portal_file.name,
                    'active_count': len(processed_df[processed_df['Status'] == '✅ Active']),
                    'inactive_count': len(processed_df[processed_df['Status'] == '⚠️ Inactive']),
                    'blocked_count': len(processed_df[processed_df['Status'] == '🚫 Blocked'])
                })
                
                inactive_devices = processed_df[processed_df['Status'] == '⚠️ Inactive']
                long_inactive = inactive_devices[inactive_devices['Days Inactive'] > st.session_state.alerts_config['inactive_threshold']]
                
                if len(long_inactive) > 0:
                    st.warning(f"⚠️ **Alert:** {len(long_inactive)} devices have been inactive for more than {st.session_state.alerts_config['inactive_threshold']} days!")
                
                st.success("✅ Data processed successfully!")
                st.balloons()

# Main content area
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data
    summary = st.session_state.summary_data
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_devices = len(df)
        st.metric("📊 Total Devices", total_devices)
    
    with col2:
        active_count = len(df[df['Status'] == '✅ Active'])
        active_pct = (active_count/total_devices*100) if total_devices > 0 else 0
        st.metric("✅ Active Devices", active_count, delta=f"{active_pct:.1f}%")
    
    with col3:
        inactive_count = len(df[df['Status'] == '⚠️ Inactive'])
        inactive_pct = (inactive_count/total_devices*100) if total_devices > 0 else 0
        st.metric("⚠️ Inactive Devices", inactive_count, delta=f"{inactive_pct:.1f}%", delta_color="inverse")
    
    with col4:
        blocked_count = len(df[df['Status'] == '🚫 Blocked'])
        blocked_pct = (blocked_count/total_devices*100) if total_devices > 0 else 0
        st.metric("🚫 Blocked Devices", blocked_count, delta=f"{blocked_pct:.1f}%")
    
    st.markdown("---")
    
    # Charts Row
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Status Distribution")
        fig1 = px.pie(
            summary, 
            values='Count', 
            names='Status',
            title='Device Status Distribution',
            color_discrete_sequence=px.colors.qualitative.Set3,
            hole=0.3
        )
        fig1.update_traces(textposition='inside', textinfo='percent+label')
        fig1.update_layout(height=450)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("📊 Inactive Days Distribution")
        df['Inactive Days Group'] = pd.cut(
            df['Days Inactive'], 
            bins=[-1, 0, 2, 7, 30, float('inf')],
            labels=['0 Days', '1-2 Days', '3-7 Days', '8-30 Days', '30+ Days']
        )
        days_dist = df['Inactive Days Group'].value_counts().reset_index()
        days_dist.columns = ['Days Range', 'Count']
        fig2 = px.bar(
            days_dist,
            x='Days Range',
            y='Count',
            title='Devices by Inactive Days',
            color='Count',
            color_continuous_scale='Viridis'
        )
        fig2.update_layout(height=450)
        st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    
    # Data Table with filters
    st.subheader("📋 Detailed Device Data")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=df['Status'].unique(),
            default=df['Status'].unique()
        )
    with col2:
        search = st.text_input("🔍 Search by Serial Number", placeholder="Enter serial number...")
    with col3:
        sort_by = st.selectbox("Sort by", ['Serial Number', 'Days Inactive', 'Status'])
    
    filtered_df = df[df['Status'].isin(status_filter)]
    if search:
        filtered_df = filtered_df[filtered_df['Serial Number'].astype(str).str.contains(search, case=False)]
    filtered_df = filtered_df.sort_values(by=sort_by)
    
    # FIXED: Use 'map' instead of 'applymap' (applymap is deprecated)
    def color_status(val):
        if '✅' in str(val):
            return 'background-color: #90EE90'
        elif '⚠️' in str(val):
            return 'background-color: #FFB6C1'
        elif '🚫' in str(val):
            return 'background-color: #D3D3D3'
        return ''
    
    # FIXED: Use .map instead of .applymap
    styled_df = filtered_df.style.map(color_status, subset=['Status'])
    
    # FIXED: Replace use_container_width with width='stretch'
    st.dataframe(styled_df, width='stretch', height=500)
    
    st.caption(f"Showing {len(filtered_df)} of {len(df)} records")
    
    st.markdown("---")
    st.subheader("⚠️ Top 10 Most Inactive Devices")
    top_inactive = df.nlargest(10, 'Days Inactive')[['Serial Number', 'Days Inactive', 'Status']]
    if 'Area' in df.columns:
        top_inactive.insert(1, 'Area', df.loc[top_inactive.index, 'Area'])
    st.dataframe(top_inactive, width='stretch')
    
    if st.session_state.processing_history:
        st.markdown("---")
        with st.expander("📜 Processing History"):
            history_df = pd.DataFrame(st.session_state.processing_history)
            st.dataframe(history_df, width='stretch')

else:
    st.info("""
    ### 👋 Welcome to Biometric Device Monitoring System!
    
    **Get started:**
    1. Upload your **Device Export File** (Excel with Serial Number & Last Activity)
    2. Upload your **Biometric Master File** (Excel with Serial Number, Area, Ward)
    3. Click **Process Data** button
    
    The system will automatically:
    - Calculate days of inactivity
    - Apply status rules
    - Generate interactive charts
    - Allow export to CSV/Excel
    """)

st.markdown("---")
st.markdown(
    f"<p style='text-align: center; color: gray;'>Biometric Device Monitor | v3.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
    unsafe_allow_html=True
)
