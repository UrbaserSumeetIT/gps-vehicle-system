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
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

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
    .notification-badge {
        position: fixed;
        top: 20px;
        right: 20px;
        background-color: #ff4444;
        color: white;
        padding: 10px;
        border-radius: 50%;
        animation: pulse 1s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state with more features
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
    
    # File uploaders with better UI
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
            active_days = st.number_input("Active Days Threshold", min_value=1, max_value=30, value=2, help="Days ≤ this value = Active")
        with col2:
            warning_days = st.number_input("Warning Days", min_value=7, max_value=90, value=30, help="Show warning after this many days")
        
        st.subheader("Alert Configuration")
        st.session_state.alerts_config['inactive_threshold'] = st.slider(
            "Inactive Alert Threshold (days)", 
            min_value=7, 
            max_value=90, 
            value=st.session_state.alerts_config['inactive_threshold'],
            help="Send alert for devices inactive longer than this"
        )
        
        st.session_state.alerts_config['email_alerts'] = st.checkbox("Enable Email Alerts", value=st.session_state.alerts_config['email_alerts'])
        
        if st.session_state.alerts_config['email_alerts']:
            st.session_state.alerts_config['email_recipient'] = st.text_input("Recipient Email", value=st.session_state.alerts_config['email_recipient'])
        
        # Theme toggle
        st.session_state.theme = st.radio("Theme", ['light', 'dark'], horizontal=True)
    
    # Process button with loading state
    process_button = st.button("🚀 **Process Data**", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    # Status rules explanation with icons
    with st.expander("📋 **Status Rules**", expanded=False):
        st.markdown("""
        ### 🎯 Logic Applied:
        1. **If Ward is NULL/Empty** → Status = Area value
        2. **If Days ≤ {} AND Area ≠ 'Not Authorized'** → ✅ Active
        3. **If Days > {} AND Area ≠ 'Not Authorized'** → ⚠️ Inactive
        4. **If Area = 'Not Authorized'** → 🚫 Blocked
        """.format(active_days, active_days))
        
        st.info("💡 **Pro Tip:** You can customize the Active Days Threshold in Advanced Settings")
    
    # Export section with more options
    if st.session_state.processed_data is not None:
        st.markdown("---")
        st.header("📥 Export Options")
        
        export_format = st.selectbox("Select Format", ['CSV', 'Excel', 'PDF Report', 'JSON'])
        
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
                    
                    # Add statistics sheet
                    stats_df = pd.DataFrame({
                        'Metric': ['Total Devices', 'Active %', 'Inactive %', 'Blocked %', 'Avg Inactive Days'],
                        'Value': [
                            len(st.session_state.processed_data),
                            f"{len(st.session_state.processed_data[st.session_state.processed_data['Status'] == 'Active'])/len(st.session_state.processed_data)*100:.1f}%",
                            f"{len(st.session_state.processed_data[st.session_state.processed_data['Status'] == 'Inactive'])/len(st.session_state.processed_data)*100:.1f}%",
                            f"{len(st.session_state.processed_data[st.session_state.processed_data['Status'] == 'Blocked'])/len(st.session_state.processed_data)*100:.1f}%",
                            f"{st.session_state.processed_data['Days Inactive'].mean():.1f}"
                        ]
                    })
                    stats_df.to_excel(writer, sheet_name='Statistics', index=False)
                
                excel_data = output.getvalue()
                b64 = base64.b64encode(excel_data).decode()
                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="biometric_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx">Click to Download</a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("✅ Excel report ready for download!")
                
            elif export_format == 'JSON':
                json_str = st.session_state.processed_data.to_json(orient='records', date_format='iso')
                b64 = base64.b64encode(json_str.encode()).decode()
                href = f'<a href="data:file/json;base64,{b64}" download="biometric_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json">Click to Download</a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("✅ JSON ready for download!")

# Enhanced processing function with custom thresholds
def process_biometric_data(portal_file, master_file, active_threshold=2):
    try:
        # Read files with progress indicator
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("📖 Reading files...")
        progress_bar.progress(20)
        
        portal_df = pd.read_excel(portal_file)
        try:
            master_df = pd.read_excel(master_file, sheet_name="Master")
        except Exception:
            master_df = pd.read_excel(master_file)
        
        progress_bar.progress(40)
        status_text.text("🔍 Detecting columns...")
        
        # Smart column detection
        def find_serial_column(df):
            for col in df.columns:
                col_lower = col.lower()
                if 'serial' in col_lower or 's/no' in col_lower or 'device' in col_lower or 'sl no' in col_lower:
                    return col
            return None
        
        portal_serial_col = find_serial_column(portal_df)
        master_serial_col = find_serial_column(master_df)
        
        if portal_serial_col is None or master_serial_col is None:
            st.error("❌ Could not find 'Serial Number' column in one or both files!")
            return None, None
        
        # Standardize column names
        if portal_serial_col != 'Serial Number':
            portal_df = portal_df.rename(columns={portal_serial_col: 'Serial Number'})
        if master_serial_col != 'Serial Number':
            master_df = master_df.rename(columns={master_serial_col: 'Serial Number'})
        
        progress_bar.progress(60)
        status_text.text("🔄 Merging data...")
        
        # Merge data
        merged = master_df.merge(portal_df, on="Serial Number", how="left")
        
        # Find Last Activity column
        last_activity_col = None
        for col in merged.columns:
            col_lower = col.lower()
            if 'last' in col_lower and ('activity' in col_lower or 'login' in col_lower or 'used' in col_lower):
                last_activity_col = col
                break
        
        if last_activity_col is None:
            st.error(f"❌ Could not find 'Last Activity' column!")
            return None, None
        
        progress_bar.progress(80)
        status_text.text("📊 Processing dates...")
        
        # Process dates
        merged['Last Activity Date'] = pd.to_datetime(merged[last_activity_col], errors='coerce')
        
        # Calculate days inactive
        max_date = merged['Last Activity Date'].max()
        if pd.isna(max_date):
            merged['Days Inactive'] = 0
        else:
            merged['Days Inactive'] = (max_date - merged['Last Activity Date']).dt.days
            merged['Days Inactive'] = merged['Days Inactive'].fillna(0)
        
        # Apply enhanced status logic with custom threshold
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
        
        progress_bar.progress(100)
        status_text.text("✅ Processing complete!")
        status_text.empty()
        progress_bar.empty()
        
        # Calculate summary
        summary = merged['Status'].value_counts().reset_index()
        summary.columns = ['Status', 'Count']
        summary['Percentage'] = (summary['Count'] / summary['Count'].sum() * 100).round(1)
        
        # Add severity for sorting
        severity = {'✅ Active': 1, '⚠️ Inactive': 2, '🚫 Blocked': 3}
        summary['Sort Order'] = summary['Status'].map(lambda x: severity.get(x, 4))
        summary = summary.sort_values('Sort Order').drop('Sort Order', axis=1)
        
        # Prepare display columns
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
            active_threshold = st.session_state.get('active_threshold', 2)
            processed_df, summary_df = process_biometric_data(portal_file, master_file, active_threshold)
            
            if processed_df is not None:
                st.session_state.processed_data = processed_df
                st.session_state.summary_data = summary_df
                
                # Add to history with hash for tracking
                data_hash = hashlib.md5(processed_df.to_string().encode()).hexdigest()
                st.session_state.processing_history.append({
                    'timestamp': datetime.now(),
                    'total_devices': len(processed_df),
                    'file_name': portal_file.name,
                    'data_hash': data_hash,
                    'active_count': len(processed_df[processed_df['Status'] == '✅ Active']),
                    'inactive_count': len(processed_df[processed_df['Status'] == '⚠️ Inactive']),
                    'blocked_count': len(processed_df[processed_df['Status'] == '🚫 Blocked'])
                })
                
                # Check for alerts
                inactive_devices = processed_df[processed_df['Status'] == '⚠️ Inactive']
                long_inactive = inactive_devices[inactive_devices['Days Inactive'] > st.session_state.alerts_config['inactive_threshold']]
                
                if len(long_inactive) > 0:
                    st.warning(f"⚠️ **Alert:** {len(long_inactive)} devices have been inactive for more than {st.session_state.alerts_config['inactive_threshold']} days!")
                    
                    # Show detailed alert
                    with st.expander(f"🔔 View Alert Details ({len(long_inactive)} devices)"):
                        st.dataframe(long_inactive[['Serial Number', 'Days Inactive', 'Area']])
                
                st.success("✅ Data processed successfully!")
                st.balloons()
                
                # Save to saved reports
                st.session_state.saved_reports.append({
                    'name': f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'date': datetime.now(),
                    'data': processed_df.copy()
                })

# Main content area with tabs for better organization
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data
    summary = st.session_state.summary_data
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "📋 Device Data", "📈 Analytics", "📜 History", "💾 Saved Reports"])
    
    with tab1:
        # KPI Cards in a nice grid
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_devices = len(df)
            st.metric("📊 Total Devices", total_devices, delta=None)
        
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
        
        # Charts Row with better visualizations
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
            st.subheader("📊 Days Inactive Analysis")
            
            # Create bins for inactive days
            df_display = df.copy()
            df_display['Inactive Days Group'] = pd.cut(
                df_display['Days Inactive'], 
                bins=[-1, 0, 2, 7, 30, 60, 90, float('inf')],
                labels=['0 Days', '1-2 Days', '3-7 Days', '8-30 Days', '31-60 Days', '61-90 Days', '90+ Days']
            )
            
            # Count by status and group
            heatmap_data = pd.crosstab(df_display['Inactive Days Group'], df_display['Status'])
            
            fig2 = px.bar(
                heatmap_data,
                title='Devices by Inactive Days & Status',
                labels={'value': 'Count', 'Inactive Days Group': 'Days Inactive', 'variable': 'Status'},
                barmode='group',
                color_discrete_sequence=['#2ecc71', '#e74c3c', '#95a5a6']
            )
            fig2.update_layout(height=450, xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Additional metrics row
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_inactive = df['Days Inactive'].mean()
            st.metric("📊 Average Inactive Days", f"{avg_inactive:.1f}")
        
        with col2:
            max_inactive = df['Days Inactive'].max()
            st.metric("⚠️ Max Inactive Days", f"{max_inactive}")
        
        with col3:
            compliance_rate = (active_count / total_devices * 100) if total_devices > 0 else 0
            st.metric("✅ Compliance Rate", f"{compliance_rate:.1f}%")
    
    with tab2:
        st.subheader("📋 Detailed Device Data")
        
        # Enhanced filters
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            status_filter = st.multiselect(
                "Filter by Status",
                options=df['Status'].unique(),
                default=df['Status'].unique(),
                key="status_filter_main"
            )
        with col2:
            if 'Area' in df.columns:
                area_filter = st.multiselect(
                    "Filter by Area",
                    options=df['Area'].unique(),
                    default=df['Area'].unique(),
                    key="area_filter"
                )
            else:
                area_filter = []
        with col3:
            search = st.text_input("🔍 Search by Serial Number", placeholder="Enter serial number...")
        with col4:
            sort_by = st.selectbox("Sort by", ['Serial Number', 'Days Inactive', 'Status'])
        
        # Apply filters
        filtered_df = df[df['Status'].isin(status_filter)]
        if area_filter:
            filtered_df = filtered_df[filtered_df['Area'].isin(area_filter)]
        if search:
            filtered_df = filtered_df[filtered_df['Serial Number'].astype(str).str.contains(search, case=False)]
        filtered_df = filtered_df.sort_values(by=sort_by)
        
        # Display table with color coding
        def color_status(val):
            if '✅' in str(val):
                return 'background-color: #90EE90'
            elif '⚠️' in str(val):
                return 'background-color: #FFB6C1'
            elif '🚫' in str(val):
                return 'background-color: #D3D3D3'
            return ''
        
        styled_df = filtered_df.style.applymap(color_status, subset=['Status'])
        st.dataframe(styled_df, use_container_width=True, height=500)
        
        # Show record count and export filtered data
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"Showing {len(filtered_df)} of {len(df)} records")
        with col2:
            if st.button("📥 Export Filtered Data"):
                csv = filtered_df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="filtered_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv">Download Filtered CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
        
        # Top inactive devices
        st.markdown("---")
        st.subheader("⚠️ Top 10 Most Inactive Devices")
        top_inactive = df.nlargest(10, 'Days Inactive')[['Serial Number', 'Days Inactive', 'Status']]
        if 'Area' in df.columns:
            top_inactive.insert(1, 'Area', df.loc[top_inactive.index, 'Area'])
        st.dataframe(top_inactive, use_container_width=True)
    
    with tab3:
        st.subheader("📈 Advanced Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Status by Area heatmap
            if 'Area' in df.columns and 'Status' in df.columns:
                st.markdown("#### 🗺️ Status Distribution by Area")
                area_status = pd.crosstab(df['Area'], df['Status'])
                
                fig3 = px.imshow(
                    area_status,
                    text_auto=True,
                    aspect="auto",
                    title="Heatmap: Status by Area",
                    color_continuous_scale='Viridis'
                )
                fig3.update_layout(height=500)
                st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            # Trend analysis (if multiple reports in history)
            if len(st.session_state.processing_history) > 1:
                st.markdown("#### 📈 Historical Trend")
                history_df = pd.DataFrame(st.session_state.processing_history)
                history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
                history_df = history_df.sort_values('timestamp')
                
                fig4 = px.line(
                    history_df,
                    x='timestamp',
                    y=['active_count', 'inactive_count', 'blocked_count'],
                    title='Device Status Trends Over Time',
                    labels={'value': 'Count', 'timestamp': 'Date', 'variable': 'Status'},
                    color_discrete_map={'active_count': '#2ecc71', 'inactive_count': '#e74c3c', 'blocked_count': '#95a5a6'}
                )
                fig4.update_layout(height=500)
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("Process more files to see historical trends!")
        
        # Cumulative distribution
        st.markdown("#### 📊 Cumulative Distribution of Inactive Days")
        df_sorted = df.sort_values('Days Inactive')
        df_sorted['Cumulative %'] = (df_sorted.index + 1) / len(df_sorted) * 100
        
        fig5 = px.line(
            df_sorted,
            x='Days Inactive',
            y='Cumulative %',
            title='Cumulative Distribution of Inactive Days',
            labels={'Days Inactive': 'Days Inactive', 'Cumulative %': 'Cumulative Percentage (%)'}
        )
        fig5.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="80% Threshold")
        fig5.add_hline(y=95, line_dash="dash", line_color="orange", annotation_text="95% Threshold")
        fig5.update_layout(height=450)
        st.plotly_chart(fig5, use_container_width=True)
    
    with tab4:
        st.subheader("📜 Processing History")
        
        if st.session_state.processing_history:
            history_df = pd.DataFrame(st.session_state.processing_history)
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
            history_df = history_df.sort_values('timestamp', ascending=False)
            
            # Format for display
            display_history = history_df[['timestamp', 'file_name', 'total_devices', 'active_count', 'inactive_count', 'blocked_count']].copy()
            display_history.columns = ['Date & Time', 'File Name', 'Total', 'Active', 'Inactive', 'Blocked']
            
            st.dataframe(display_history, use_container_width=True)
            
            # Option to compare with previous report
            if len(st.session_state.processing_history) >= 2:
                st.markdown("---")
                st.subheader("📊 Compare with Previous Report")
                
                col1, col2 = st.columns(2)
                with col1:
                    report1_idx = st.selectbox("Select First Report", range(len(st.session_state.processing_history)), format_func=lambda x: st.session_state.processing_history[x]['timestamp'].strftime('%Y-%m-%d %H:%M'))
                with col2:
                    report2_idx = st.selectbox("Select Second Report", range(len(st.session_state.processing_history)), format_func=lambda x: st.session_state.processing_history[x]['timestamp'].strftime('%Y-%m-%d %H:%M'), index=min(1, len(st.session_state.processing_history)-1))
                
                if report1_idx != report2_idx:
                    report1 = st.session_state.processing_history[report1_idx]
                    report2 = st.session_state.processing_history[report2_idx]
                    
                    comparison = pd.DataFrame({
                        'Metric': ['Total Devices', 'Active', 'Inactive', 'Blocked'],
                        report1['timestamp'].strftime('%Y-%m-%d'): [report1['total_devices'], report1['active_count'], report1['inactive_count'], report1['blocked_count']],
                        report2['timestamp'].strftime('%Y-%m-%d'): [report2['total_devices'], report2['active_count'], report2['inactive_count'], report2['blocked_count']],
                        'Change': [
                            report2['total_devices'] - report1['total_devices'],
                            report2['active_count'] - report1['active_count'],
                            report2['inactive_count'] - report1['inactive_count'],
                            report2['blocked_count'] - report1['blocked_count']
                        ]
                    })
                    st.dataframe(comparison, use_container_width=True)
        else:
            st.info("No processing history yet. Process some data to see history here!")
    
    with tab5:
        st.subheader("💾 Saved Reports")
        
        if st.session_state.saved_reports:
            for idx, report in enumerate(st.session_state.saved_reports):
                with st.expander(f"📄 {report['name']} - {report['date'].strftime('%Y-%m-%d %H:%M:%S')}"):
                    st.write(f"**Total Devices:** {len(report['data'])}")
                    st.write(f"**Active:** {len(report['data'][report['data']['Status'] == '✅ Active'])}")
                    st.write(f"**Inactive:** {len(report['data'][report['data']['Status'] == '⚠️ Inactive'])}")
                    st.write(f"**Blocked:** {len(report['data'][report['data']['Status'] == '🚫 Blocked'])}")
                    
                    if st.button(f"Load Report {idx}", key=f"load_{idx}"):
                        st.session_state.processed_data = report['data']
                        st.rerun()
                    
                    if st.button(f"Delete Report {idx}", key=f"delete_{idx}"):
                        st.session_state.saved_reports.pop(idx)
                        st.rerun()
        else:
            st.info("No saved reports. Process data and click 'Save Report' to store them here!")
            
            # Option to save current report
            if st.session_state.processed_data is not None:
                if st.button("💾 Save Current Report"):
                    report_name = st.text_input("Report Name", value=f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    if st.button("Confirm Save"):
                        st.session_state.saved_reports.append({
                            'name': report_name,
                            'date': datetime.now(),
                            'data': st.session_state.processed_data.copy()
                        })
                        st.success("Report saved successfully!")

else:
    # Welcome message with enhanced UI
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h2>👋 Welcome to Biometric Device Monitoring System PRO</h2>
        <p style="font-size: 1.2rem;">Upload your Excel files to get started with advanced analytics</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
            <h3>📁 Step 1</h3>
            <p>Upload Device Export File</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
            <h3>📁 Step 2</h3>
            <p>Upload Biometric Master File</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
            <h3>🚀 Step 3</h3>
            <p>Click Process Data</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Features list
    st.subheader("✨ Key Features")
    features_col1, features_col2 = st.columns(2)
    
    with features_col1:
        st.markdown("""
        - ✅ **Smart Column Detection** - Automatically finds required columns
        - 📊 **Interactive Dashboards** - Real-time charts and visualizations
        - 📈 **Advanced Analytics** - Trends, heatmaps, and distributions
        - 🔔 **Alert System** - Get notified about critical devices
        """)
    
    with features_col2:
        st.markdown("""
        - 📥 **Multiple Export Formats** - CSV, Excel, JSON
        - 📜 **Processing History** - Track changes over time
        - 💾 **Save Reports** - Store and compare analyses
        - ⚙️ **Customizable Rules** - Adjust thresholds as needed
        """)

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown(
        f"<p style='text-align: center; color: gray;'>🏢 Biometric Device Monitor PRO | v3.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        unsafe_allow_html=True
    )
