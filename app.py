# app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import traceback
import gc
import warnings
warnings.filterwarnings('ignore')

# Set page config FIRST
st.set_page_config(
    page_title="GPS & KPI Monitoring Dashboard",
    page_icon="logosumeet.jpeg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #1f77b4;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .status-working {
        background-color: #28a745;
        color: white;
    }
    .status-not-working {
        background-color: #dc3545;
        color: white;
    }
    .status-pending {
        background-color: #ffc107;
        color: black;
    }
    </style>
""", unsafe_allow_html=True)

def load_excel_safe(file, sheet_name=None, skiprows=0):
    """Safely load Excel file with error handling"""
    try:
        # Reset file pointer
        file.seek(0)
        
        # Try to read the file
        if sheet_name:
            df = pd.read_excel(file, sheet_name=sheet_name, skiprows=skiprows, engine='openpyxl')
        else:
            df = pd.read_excel(file, engine='openpyxl')
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        return df
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return None

def process_vehicle_master(df):
    """Process vehicle master data"""
    try:
        if df is None or df.empty:
            return None
        
        # Find vehicle number column
        vehicle_col = None
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['register', 'vehicle', 'number', 'id']):
                vehicle_col = col
                break
        
        if not vehicle_col:
            st.warning("Could not find vehicle number column")
            return None
        
        # Rename columns
        df.rename(columns={vehicle_col: 'Vehicle Number'}, inplace=True)
        
        # Keep only necessary columns
        keep_cols = ['Vehicle Number']
        for col in ['Zone', 'Facility', 'Technician']:
            if col in df.columns:
                keep_cols.append(col)
        
        df = df[keep_cols].copy()
        df = df[df['Vehicle Number'].notna()]
        df['Vehicle Number'] = df['Vehicle Number'].astype(str).str.strip()
        df = df[df['Vehicle Number'] != '']
        df = df[df['Vehicle Number'] != 'nan']
        
        return df
    except Exception as e:
        st.error(f"Error processing vehicle master: {str(e)}")
        return None

def process_gps_status(df):
    """Process GPS status data"""
    try:
        if df is None or df.empty:
            return None
        
        # Find required columns
        vehicle_col = None
        imei_col = None
        log_col = None
        chassis_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'vehicle' in col_lower or 'registration' in col_lower:
                vehicle_col = col
            elif 'imei' in col_lower or 'gps' in col_lower:
                imei_col = col
            elif 'last log' in col_lower or 'log received' in col_lower:
                log_col = col
            elif 'chassis' in col_lower:
                chassis_col = col
        
        # Create result dataframe
        result = pd.DataFrame()
        
        # Add Vehicle Number
        if vehicle_col:
            result['Vehicle Number'] = df[vehicle_col].astype(str).str.strip()
            result = result[result['Vehicle Number'] != 'nan']
            result = result[result['Vehicle Number'] != '']
        
        # Add GPS IMEI
        if imei_col:
            result['GPS IMEI No.'] = df[imei_col].astype(str).str.strip()
        
        # Add Chassis/V Id
        if chassis_col:
            result['V Id'] = df[chassis_col].astype(str).str.strip()
        
        # Add Vehicle Type if available
        if 'Vehicle Type' in df.columns:
            result['Vehicle Type'] = df['Vehicle Type'].astype(str).str.strip()
        
        # Process date and status
        if log_col:
            try:
                # Convert to datetime
                result['Last Log Received At'] = pd.to_datetime(df[log_col], errors='coerce')
                
                # Calculate age and status
                max_date = result['Last Log Received At'].max()
                result['Date'] = max_date
                result['Age'] = (max_date - result['Last Log Received At']).dt.days
                result['Status'] = np.where(result['Age'] <= 1, 'Working', 'Not Working')
                
                # Fill NaN ages
                result['Age'] = result['Age'].fillna(999)
                result['Status'] = result['Status'].fillna('Unknown')
            except Exception as e:
                st.warning(f"Could not process dates: {str(e)}")
                result['Date'] = datetime.now()
                result['Age'] = 0
                result['Status'] = 'Unknown'
        
        return result
    except Exception as e:
        st.error(f"Error processing GPS status: {str(e)}")
        return None

def process_kpi_file(df, kpi_type):
    """Process KPI file"""
    try:
        if df is None or df.empty:
            return None
        
        # Required columns
        required = ['Vehicle Number']
        for col in ['Kpi Date', 'Zone', 'Marching In Out Timings']:
            if col in df.columns:
                required.append(col)
        
        # Check if we have at least vehicle number
        if 'Vehicle Number' not in df.columns:
            # Try to find vehicle column
            vehicle_col = None
            for col in df.columns:
                if 'vehicle' in col.lower() or 'number' in col.lower():
                    vehicle_col = col
                    break
            
            if vehicle_col:
                df.rename(columns={vehicle_col: 'Vehicle Number'}, inplace=True)
            else:
                st.warning(f"No vehicle column found in {kpi_type}")
                return None
        
        # Select columns
        keep_cols = [col for col in required if col in df.columns]
        result = df[keep_cols].copy()
        
        # Clean vehicle numbers
        result['Vehicle Number'] = result['Vehicle Number'].astype(str).str.strip()
        result = result[result['Vehicle Number'] != 'nan']
        result = result[result['Vehicle Number'] != '']
        
        # Add KPI source
        result['Kpi Source'] = kpi_type
        
        # Filter out rows with empty Zone if Zone column exists
        if 'Zone' in result.columns:
            result = result[result['Zone'].notna()]
            result = result[result['Zone'] != '']
            result = result[result['Zone'] != 'nan']
        
        return result
    except Exception as e:
        st.error(f"Error processing {kpi_type}: {str(e)}")
        return None

def combine_data(gps_df, vm_df=None, kpi_dfs=None, remarks_df=None):
    """Combine all data sources"""
    try:
        if gps_df is None or gps_df.empty:
            return None, None
        
        # Start with GPS data
        combined = gps_df.copy()
        
        # Add vehicle master data
        if vm_df is not None and not vm_df.empty:
            vm_cols = ['Vehicle Number', 'Zone', 'Facility', 'Technician']
            existing_vm = [col for col in vm_cols if col in vm_df.columns]
            if existing_vm:
                combined = pd.merge(combined, vm_df[existing_vm], how='left', on='Vehicle Number')
        
        # Add KPI data
        if kpi_dfs:
            all_kpi = pd.DataFrame()
            for kpi_df in kpi_dfs:
                if kpi_df is not None and not kpi_df.empty:
                    all_kpi = pd.concat([all_kpi, kpi_df], ignore_index=True)
            
            if not all_kpi.empty:
                all_kpi = all_kpi.drop_duplicates(subset=['Vehicle Number'], keep='first')
                kpi_cols = ['Vehicle Number', 'Kpi Source']
                for col in ['Kpi Date', 'Zone', 'Marching In Out Timings']:
                    if col in all_kpi.columns:
                        kpi_cols.append(col)
                combined = pd.merge(combined, all_kpi[kpi_cols], how='left', on='Vehicle Number', suffixes=('', '_kpi'))
        
        # Add remarks
        if remarks_df is not None and not remarks_df.empty:
            if 'Remarks' in remarks_df.columns and 'Vehicle Number' in remarks_df.columns:
                combined = pd.merge(combined, remarks_df[['Vehicle Number', 'Remarks']], how='left', on='Vehicle Number')
        
        # Fill NaN values
        combined = combined.fillna('-')
        
        # Process remarks to Updated Remarks
        def get_updated_remarks(row):
            remarks = str(row.get('Remarks', '')).lower()
            kpi_source = str(row.get('Kpi Source', ''))
            
            if remarks == '-':
                return '-'
            elif 'wiring' in remarks:
                return 'Wiring Kit Fault'
            elif 'converter' in remarks or 'dc' in remarks:
                return 'Converter Fault'
            elif 'line' in remarks:
                return 'Line issue'
            elif 'gps' in remarks or 'gps issue' in remarks:
                return 'GPS Fault'
            elif kpi_source != '-' and remarks not in ['-', 'working', 'b shift']:
                return 'N'
            else:
                return '-'
        
        if 'Updated Remarks' not in combined.columns:
            combined['Updated Remarks'] = combined.apply(get_updated_remarks, axis=1)
        
        # Separate working and not working
        if 'Status' in combined.columns:
            working = combined[combined['Status'] == 'Working'].copy()
            not_working = combined[(combined['Status'] == 'Not Working')].copy()
        else:
            working = pd.DataFrame()
            not_working = combined.copy()
        
        # Clean up
        gc.collect()
        
        return not_working, working
    except Exception as e:
        st.error(f"Error combining data: {str(e)}")
        return None, None

def main():
    # Initialize session state
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'not_working_df' not in st.session_state:
        st.session_state.not_working_df = pd.DataFrame()
    if 'working_df' not in st.session_state:
        st.session_state.working_df = pd.DataFrame()
    
    st.markdown('<h1 class="main-header">🚛 GPS & KPI Monitoring Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Upload Files")
        
        # File uploads
        st.subheader("Required Files")
        gps_file = st.file_uploader("📍 GPS Status File", type=['xlsx', 'xlsm', 'csv'])
        
        st.subheader("Optional Files")
        vm_file = st.file_uploader("📋 Vehicle Master", type=['xlsm', 'xlsx'])
        remarks_file = st.file_uploader("📝 GPS Remarks", type=['csv', 'xlsx'])
        
        st.subheader("KPI Files")
        kpi_files = []
        kpi_types = ['KPI 52', 'KPI 52 Current', 'KPI 56', 'KPI 63a', 'KPI 63b', 'KPI 72']
        for kpi_type in kpi_types:
            file = st.file_uploader(f"{kpi_type}", type=['xlsx'], key=kpi_type)
            if file:
                kpi_files.append((file, kpi_type))
        
        st.markdown("---")
        
        # Process button
        if st.button("🚀 Process Data", type="primary", use_container_width=True):
            if not gps_file:
                st.error("❌ Please upload GPS Status file")
            else:
                with st.spinner("Processing data..."):
                    try:
                        # Load GPS data
                        gps_df = load_excel_safe(gps_file)
                        if gps_df is None or gps_df.empty:
                            st.error("Failed to load GPS file")
                            return
                        
                        # Process GPS
                        gps_processed = process_gps_status(gps_df)
                        if gps_processed is None or gps_processed.empty:
                            st.error("No valid GPS data found")
                            return
                        
                        # Load Vehicle Master
                        vm_processed = None
                        if vm_file:
                            vm_df = load_excel_safe(vm_file, sheet_name='vehiclemaster', skiprows=4)
                            if vm_df is not None:
                                vm_processed = process_vehicle_master(vm_df)
                        
                        # Process KPI files
                        kpi_processed = []
                        if kpi_files:
                            for file, kpi_type in kpi_files:
                                kpi_df = load_excel_safe(file)
                                if kpi_df is not None:
                                    kpi_processed_df = process_kpi_file(kpi_df, kpi_type)
                                    if kpi_processed_df is not None and not kpi_processed_df.empty:
                                        kpi_processed.append(kpi_processed_df)
                        
                        # Load Remarks
                        remarks_processed = None
                        if remarks_file:
                            if remarks_file.name.endswith('.csv'):
                                remarks_processed = pd.read_csv(remarks_file, dtype=str)
                            else:
                                remarks_processed = load_excel_safe(remarks_file)
                            
                            if remarks_processed is not None:
                                # Try to find vehicle column
                                for col in remarks_processed.columns:
                                    if 'vehicle' in col.lower() or 'registration' in col.lower():
                                        remarks_processed.rename(columns={col: 'Vehicle Number'}, inplace=True)
                                        break
                        
                        # Combine all data
                        not_working, working = combine_data(
                            gps_processed, 
                            vm_processed, 
                            kpi_processed,
                            remarks_processed
                        )
                        
                        if not_working is not None and not not_working.empty:
                            st.session_state.data_loaded = True
                            st.session_state.not_working_df = not_working
                            st.session_state.working_df = working if working is not None else pd.DataFrame()
                            
                            st.success(f"✅ Data processed successfully!")
                            st.success(f"📍 Not Working: {len(not_working)}")
                            if working is not None and not working.empty:
                                st.success(f"✅ Working: {len(working)}")
                        else:
                            st.error("No data could be processed")
                            
                    except Exception as e:
                        st.error(f"Error processing data: {str(e)}")
                        st.error(traceback.format_exc())
        
        # Download section
        if st.session_state.data_loaded and not st.session_state.not_working_df.empty:
            st.markdown("---")
            st.subheader("📥 Download Report")
            
            try:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    st.session_state.not_working_df.to_excel(
                        writer, index=False, sheet_name='Not_Working'
                    )
                    if not st.session_state.working_df.empty:
                        st.session_state.working_df.to_excel(
                            writer, index=False, sheet_name='Working'
                        )
                
                excel_data = output.getvalue()
                st.download_button(
                    label="📊 Download Excel Report",
                    data=excel_data,
                    file_name=f"gps_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error creating download: {str(e)}")
    
    # Main content
    if st.session_state.data_loaded and not st.session_state.not_working_df.empty:
        df = st.session_state.not_working_df
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🚛 Not Working", len(df))
        with col2:
            working_count = len(st.session_state.working_df) if not st.session_state.working_df.empty else 0
            st.metric("✅ Working", working_count)
        with col3:
            if 'Age' in df.columns:
                avg_age = df['Age'].mean()
                st.metric("📅 Avg Age", f"{avg_age:.1f} days" if not pd.isna(avg_age) else "N/A")
        
        st.markdown("---")
        
        # Data table
        st.subheader("📋 Not Working Vehicles")
        
        # Select columns to display
        display_cols = []
        for col in ['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type', 
                   'Facility', 'Last Log Received At', 'Status', 'Technician', 
                   'Updated Remarks', 'Age', 'Zone']:
            if col in df.columns:
                display_cols.append(col)
        
        if display_cols:
            display_df = df[display_cols].copy()
            
            # Format dates
            for col in ['Date', 'Last Log Received At']:
                if col in display_df.columns:
                    try:
                        display_df[col] = pd.to_datetime(display_df[col], errors='coerce').dt.strftime('%d-%m-%Y')
                    except:
                        pass
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            st.caption(f"Total: {len(display_df)} vehicles")
    
    else:
        st.info("""
        👋 **GPS & KPI Monitoring Dashboard**
        
        ### How to use:
        1. **Upload Files** in the sidebar
        2. Click **Process Data** to generate the report
        3. View the **Not Working Vehicles** list
        4. **Download** the Excel report
        
        ### Required:
        - 📍 GPS Status File
        
        ### Optional:
        - 📋 Vehicle Master - Adds Zone, Facility, Technician
        - 📊 KPI Files - Adds KPI information
        - 📝 Remarks File - Adds remarks
        """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        st.error(traceback.format_exc())
