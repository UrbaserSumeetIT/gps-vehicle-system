# app.py
import streamlit as st
import pandas as pd
import numpy as np
import openpyxl
from pathlib import Path
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import base64
import traceback
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
import sys
import json
from openpyxl.utils import get_column_letter
import warnings
warnings.filterwarnings('ignore')

# Set page config FIRST - before any other imports or operations
st.set_page_config(
    page_title="GPS & KPI Monitoring Dashboard",
    page_icon="logosumeet.jpeg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import gspread with error handling - but only if needed
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Debug mode - set to False for production
DEBUG_MODE = False

def debug_print(msg):
    """Print debug messages if DEBUG_MODE is True"""
    if DEBUG_MODE:
        print(f"🔍 DEBUG: {msg}", file=sys.stderr)

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
    /* Fix for segmentation fault - reduce memory usage */
    .stDataFrame {
        max-height: 400px !important;
    }
    .stPlotlyChart {
        max-height: 400px !important;
    }
    </style>
""", unsafe_allow_html=True)

class KPIDataProcessor:
    """Processing class for KPI data with file uploads"""
    
    def __init__(self):
        debug_print("Initializing KPIDataProcessor")
        self.vm_df = None
        self.gps_df = None
        self.kpi_df = None
        self.final_df = pd.DataFrame()
        self.working_df = pd.DataFrame()
        self.not_working_df = pd.DataFrame()
        self.combined_df = pd.DataFrame()
    
    def load_vehicle_master(self, file):
        """Load vehicle master file - optimized for memory"""
        try:
            debug_print(f"Loading vehicle master from: {file.name}")
            # Use read_excel with limited memory usage
            df = pd.read_excel(
                file, 
                engine='openpyxl', 
                sheet_name='vehiclemaster', 
                skiprows=4,
                nrows=None  # Read all rows but we'll filter
            )
            df.columns = df.columns.str.strip()
            df.rename(columns={'Register Number': 'Vehicle Number'}, inplace=True)
            # Keep only necessary columns to reduce memory
            if 'Vehicle Number' in df.columns:
                # Drop rows with NaN in Vehicle Number
                df = df[df['Vehicle Number'].notna()]
            self.vm_df = df
            debug_print(f"✅ Loaded {len(df)} vehicles from master")
            # Force garbage collection
            import gc
            gc.collect()
            return df
        except Exception as e:
            error_msg = f"Error loading vehicle master: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def process_kpi_file(self, file, kpi_type):
        """Process KPI files based on type - optimized"""
        try:
            debug_print(f"Processing KPI file: {file.name} ({kpi_type})")
            # Read only necessary columns to reduce memory
            df = pd.read_excel(file, engine='openpyxl')
            required_cols = ['Kpi Date', 'Zone', 'Vehicle Number', 'Marching In Out Timings']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                debug_print(f"⚠️ Missing columns in {kpi_type}: {missing_cols}")
                return None
            
            df = df[required_cols].copy()
            df = df[df['Zone'].notna()]
            df['Kpi Source'] = kpi_type
            debug_print(f"✅ Processed {len(df)} rows from {kpi_type}")
            import gc
            gc.collect()
            return df
        except Exception as e:
            error_msg = f"Error processing {kpi_type}: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def process_kpi52(self, file):
        """Process KPI 52 with vehicle master merge - optimized"""
        try:
            debug_print(f"Processing KPI 52 from: {file.name}")
            df = pd.read_excel(file, engine='openpyxl')
            df.rename(columns={'Vehicle Number': 'V ID'}, inplace=True)
            # Merge with vehicle master
            merge = pd.merge(df, self.vm_df, how='left', on='V ID')
            kpi_data = merge[['Kpi Date', 'Zone_x', 'Vehicle Number', 'Marching In Out Timings']].copy()
            kpi_data = kpi_data.rename(columns={'Zone_x': 'Zone'})
            kpi_data = kpi_data[kpi_data['Zone'].notna()]
            kpi_data['Kpi Source'] = 'KPI 52'
            debug_print(f"✅ Processed {len(kpi_data)} rows from KPI 52")
            import gc
            gc.collect()
            return kpi_data
        except Exception as e:
            error_msg = f"Error processing KPI 52: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def process_gps_status(self, file):
        """Process GPS status file - optimized"""
        try:
            debug_print(f"Processing GPS status from: {file.name}")
            # Read the file
            df = pd.read_excel(file, engine='openpyxl')
            
            # Rename columns if they exist
            if 'Chassis No.' in df.columns:
                df.rename(columns={'Chassis No.':'V Id'} ,inplace=True)
            
            # Convert date column
            if 'Last Log Received At' in df.columns:
                log_dates = pd.to_datetime(df['Last Log Received At'], dayfirst=True).dt.normalize()
                max_date = log_dates.max()
                df['Age'] = (max_date - log_dates).dt.days
                df['Status'] = np.where(df['Age'] <= 1, 'Working', 'Not Working')
                df['Date'] = max_date
            
            # Rename vehicle column
            if 'Vehicle Registration No.' in df.columns:
                df.rename(columns={'Vehicle Registration No.': 'Vehicle Number'}, inplace=True)
            
            # Select only necessary columns
            cols_to_keep = ['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type', 
                           'Last Log Received At', 'Last Location', 'Age', 'Status']
            existing_cols = [col for col in cols_to_keep if col in df.columns]
            final_df = df[existing_cols].copy()
            
            self.gps_df = final_df
            debug_print(f"✅ Processed GPS status: {len(final_df)} vehicles")
            import gc
            gc.collect()
            return final_df
        except Exception as e:
            error_msg = f"Error processing GPS status: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def process_gps_remarks(self, file):
        """Process GPS remarks CSV file"""
        try:
            debug_print(f"Processing GPS remarks from: {file.name}")
            df = pd.read_csv(file)
            # Check if required columns exist
            required_cols = ['Date', 'Vehicle Registration No.', 'Remarks', 'Facility','Time', 'Technician']
            existing_cols = [col for col in required_cols if col in df.columns]
            if len(existing_cols) < 4:
                debug_print(f"⚠️ Missing columns in remarks file: {existing_cols}")
                return None
            
            df = df[existing_cols].copy()
            df.rename(columns={
                'Vehicle Registration No.': 'Vehicle Number',
                'Facility':'Remark_Facility',
                'Technician':'Remarks_Technician',
                'Time':'Remarks Date'
            }, inplace=True)
            debug_print(f"✅ Processed {len(df)} remarks")
            return df
        except Exception as e:
            error_msg = f"Error processing GPS remarks: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.warning(f"Could not process remarks file: {error_msg}")
            return None
    
    def combine_all_data(self, kpi_files, gps_file, remarks_file=None):
        """Combine all data sources - optimized for memory"""
        try:
            debug_print("Starting data combination process...")
            if gps_file:
                gps_df = self.process_gps_status(gps_file)
                if gps_df is None:
                    st.error("Failed to process GPS file")
                    return (None, None)
            
            kpi_dfs = []
            for file, kpi_type in kpi_files:
                debug_print(f"Processing KPI: {kpi_type}")
                if '52' in kpi_type and self.vm_df is not None:
                    kpi_df = self.process_kpi52(file)
                else:
                    kpi_df = self.process_kpi_file(file, kpi_type)
                
                if kpi_df is not None:
                    kpi_dfs.append(kpi_df)
            
            if not kpi_dfs:
                st.warning("No valid KPI data found")
                return (None, None)
            
            # Combine KPI data
            combined_kpi = pd.concat(kpi_dfs, ignore_index=True)
            combined_kpi = combined_kpi.drop_duplicates(subset=['Vehicle Number'], keep='first')
            debug_print(f"Combined KPI data: {len(combined_kpi)} unique vehicles")
            
            # Merge with GPS data
            merge = pd.merge(gps_df, combined_kpi, how='left', on='Vehicle Number')
            
            # Filter out test vehicles
            not_working = merge[merge['Vehicle Number'] != 'TEST 02']
            
            # Select necessary columns
            base_cols = ['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type', 
                        'Last Log Received At', 'Age', 'Status', 'Kpi Source']
            existing_base = [col for col in base_cols if col in not_working.columns]
            not_working = not_working[existing_base].copy()
            
            # Process remarks
            if remarks_file:
                remarks_df = self.process_gps_remarks(remarks_file)
                if remarks_df is not None:
                    # Merge remarks
                    remark_cols = ['Vehicle Number', 'Remarks']
                    if all(col in remarks_df.columns for col in remark_cols):
                        not_working = pd.merge(not_working, remarks_df[remark_cols], 
                                              how='left', on='Vehicle Number')
            
            # Merge with vehicle master
            if self.vm_df is not None:
                vm_cols = ['Vehicle Number', 'Zone', 'Facility', 'Technician']
                existing_vm = [col for col in vm_cols if col in self.vm_df.columns]
                if existing_vm:
                    not_working = pd.merge(not_working, self.vm_df[existing_vm], 
                                          how='left', on='Vehicle Number')
            
            # Fill NaN values
            not_working = not_working.fillna('-')
            
            # Process updated remarks
            def get_updated_remarks(row):
                remarks = str(row.get('Remarks', '')).lower() if not pd.isna(row.get('Remarks', '')) else ''
                kpi_source = row.get('Kpi Source', '')
                
                if remarks.startswith('wiring kit'):
                    return 'Wiring Kit Fault'
                elif remarks.startswith('converter') or remarks.startswith('dc converter'):
                    return 'Converter Fault'
                elif remarks in ('working', 'b shift', '-'):
                    return '-'
                elif remarks.startswith('line issue'):
                    return 'Line issue'
                elif remarks in ('gps issue', 'gps missing', 'gps fault', 'gps water lock') or remarks.startswith('gps'):
                    return 'GPS Fault'
                elif remarks == '':
                    return '-'
                elif kpi_source != "-" and str(remarks) not in ['Line issue', 'Gps Issue', 'Converter Fault', 'GPS Missing', 'Working', 'GPS Fault']:
                    return 'N'
                elif kpi_source == "-" and str(remarks) not in ['Line issue', 'Gps Issue', 'Converter Fault', 'GPS Missing', 'Working', 'GPS Fault']:
                    return 'BreakDown'
                else:
                    return '-'
            
            not_working['Updated Remarks'] = not_working.apply(get_updated_remarks, axis=1)
            
            # Convert date
            if 'Date' in not_working.columns:
                not_working['Date'] = pd.to_datetime(not_working['Date'])
            
            # Separate working and not working
            working = not_working[not_working['Status'] == 'Working'].copy()
            not_working_only = not_working[(not_working['Status'] == 'Not Working') & 
                                          (not_working['Vehicle Number'] != 'TEST 02')].copy()
            
            # Combined dataframe
            combined_df = pd.concat([not_working_only, working], ignore_index=True)
            
            self.final_df = not_working_only
            self.not_working_df = not_working_only
            self.working_df = working
            self.combined_df = combined_df
            
            debug_print(f"✅ Data combination complete: Not Working: {len(not_working_only)}, Working: {len(working)}")
            import gc
            gc.collect()
            return (not_working_only, working)
            
        except Exception as e:
            error_msg = f"Error combining data: {str(e)}"
            debug_print(f"❌ {error_msg}")
            debug_print(traceback.format_exc())
            st.error(error_msg)
            if DEBUG_MODE:
                st.error(traceback.format_exc())
            return (None, None)
    
    def get_summary_stats(self, df=None):
        """Get summary statistics from data"""
        if df is None:
            df = self.final_df
            
        if df is None or df.empty:
            return {}
        
        stats = {
            'total_vehicles': len(df),
            'unique_zones': df['Zone'].nunique() if 'Zone' in df.columns else 0,
            'unique_facilities': df['Facility'].nunique() if 'Facility' in df.columns else 0,
            'total_imei': df['GPS IMEI No.'].nunique() if 'GPS IMEI No.' in df.columns else 0,
            'remarks_summary': df['Updated Remarks'].value_counts().to_dict() if 'Updated Remarks' in df.columns else {},
            'zone_summary': df['Zone'].value_counts().to_dict() if 'Zone' in df.columns else {}
        }
        
        return stats
    
    def get_technician_remarks_summary(self, df=None):
        """Get technician-wise updated remarks count"""
        if df is None:
            df = self.final_df
            
        if df is None or df.empty:
            return None
        
        tech_remarks = pd.crosstab(
            df['Technician'], 
            df['Updated Remarks'],
            margins=True,
            margins_name='Total'
        )
        
        return tech_remarks
    
    def get_visualization_remarks(self, df):
        """Replace '-' with 'Need to check' for visualization only"""
        if df is None or df.empty:
            return df
        
        viz_df = df.copy()
        
        if 'Updated Remarks' in viz_df.columns:
            viz_df['Updated Remarks'] = viz_df['Updated Remarks'].replace('-', 'Need to check')
        
        return viz_df
    
    def get_dataframe(self, df_type='final'):
        """Safely get dataframe by type"""
        if df_type == 'working':
            return self.working_df.copy() if self.working_df is not None else pd.DataFrame()
        elif df_type == 'not_working':
            return self.not_working_df.copy() if self.not_working_df is not None else pd.DataFrame()
        elif df_type == 'combined':
            return self.combined_df.copy() if self.combined_df is not None else pd.DataFrame()
        else:
            return self.final_df.copy() if self.final_df is not None else pd.DataFrame()


def format_date_column(df, column_name='Date'):
    """Helper function to safely format date column"""
    if column_name not in df.columns:
        return df
    
    df_copy = df.copy()
    
    if not pd.api.types.is_datetime64_any_dtype(df_copy[column_name]):
        try:
            df_copy[column_name] = pd.to_datetime(df_copy[column_name])
        except:
            return df_copy
    
    try:
        df_copy[column_name] = df_copy[column_name].dt.strftime('%d-%m-%Y')
    except:
        pass
    
    return df_copy


def highlight_status(row):
    """Apply color coding to Status column"""
    if row['Status'] == 'Working':
        return ['background-color: #28a745; color: white' if col == 'Status' else '' for col in row.index]
    elif row['Status'] == 'Not Working':
        return ['background-color: #dc3545; color: white' if col == 'Status' else '' for col in row.index]
    return [''] * len(row)


def initialize_session_state():
    """Initialize all session state variables"""
    if 'processor' not in st.session_state:
        st.session_state.processor = KPIDataProcessor()
    
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    
    if 'not_working_df' not in st.session_state:
        st.session_state.not_working_df = pd.DataFrame()
    
    if 'working_df' not in st.session_state:
        st.session_state.working_df = pd.DataFrame()
    
    if 'final_df' not in st.session_state:
        st.session_state.final_df = pd.DataFrame()
    
    if 'combined_df' not in st.session_state:
        st.session_state.combined_df = pd.DataFrame()


def main():
    # Initialize session state first
    initialize_session_state()
    
    st.markdown('<h1 class="main-header">🚛 GPS & KPI Monitoring Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar for file uploads
    with st.sidebar:
        st.header("📁 Upload Files")
        
        # Vehicle Master
        st.subheader("Vehicle Master")
        vm_file = st.file_uploader("Upload Vehicle Master", type=['xlsm', 'xlsx'])
        if vm_file:
            with st.spinner("Loading vehicle master..."):
                vm_df = st.session_state.processor.load_vehicle_master(vm_file)
                if vm_df is not None:
                    st.success(f"✅ Loaded {len(vm_df)} vehicles")
        
        # GPS Status File
        st.subheader("GPS Status")
        gps_file = st.file_uploader("Upload GPS Status", type=['xlsx', 'xlsm', 'csv'])
        
        # KPI Files
        st.subheader("KPI Files")
        kpi_files = []
        
        kpi_types = [
            ('KPI 52', 'kpi52'),
            ('KPI 52 Current', 'kpi52_cur'),
            ('KPI 56', 'kpi56'),
            ('KPI 63a', 'kpi63a'),
            ('KPI 63b', 'kpi63b'),
            ('KPI 72', 'kpi72')
        ]
        
        for label, key in kpi_types:
            file = st.file_uploader(f"Upload {label}", type=['xlsx'], key=key)
            if file:
                kpi_files.append((file, label))
        
        # GPS Remarks
        st.subheader("GPS Remarks")
        remarks_file = st.file_uploader("Upload Remarks", type=['csv', 'xlsx'])
        
        # Process Button
        st.markdown("---")
        if st.button("🚀 Process Data", type="primary", use_container_width=True):
            if gps_file and kpi_files:
                with st.spinner("Processing data..."):
                    try:
                        result = st.session_state.processor.combine_all_data(
                            kpi_files=kpi_files,
                            gps_file=gps_file,
                            remarks_file=remarks_file
                        )
                        
                        if result is None:
                            st.error("❌ Processing returned None")
                        elif isinstance(result, tuple) and len(result) == 2:
                            not_working_df, working_df = result
                            
                            if not_working_df is not None and working_df is not None:
                                st.session_state.data_loaded = True
                                st.session_state.not_working_df = not_working_df
                                st.session_state.working_df = working_df
                                st.session_state.final_df = not_working_df
                                st.session_state.combined_df = pd.concat([not_working_df, working_df], ignore_index=True)
                                st.success(f"✅ Data processed successfully!\nNot Working: {len(not_working_df)}, Working: {len(working_df)}")
                            else:
                                st.error("❌ Failed to process data. Please check your input files.")
                        else:
                            st.error(f"❌ Unexpected return type: {type(result)}")
                    except Exception as e:
                        st.error(f"❌ Error during processing: {str(e)}")
                        if DEBUG_MODE:
                            st.error(traceback.format_exc())
            else:
                st.warning("⚠️ Please upload GPS Status and at least one KPI file")
        
        # Download Section
        if st.session_state.data_loaded and not st.session_state.not_working_df.empty:
            st.markdown("---")
            st.subheader("📥 Download")
            
            try:
                export_df = st.session_state.not_working_df.copy()
                export_df = format_date_column(export_df, 'Date')
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Not_Working_Report')
                    if not st.session_state.working_df.empty:
                        working_export = format_date_column(st.session_state.working_df.copy(), 'Date')
                        working_export.to_excel(writer, index=False, sheet_name='Working_Report')
                
                excel_data = output.getvalue()
                st.download_button(
                    label="📊 Download Excel Report",
                    data=excel_data,
                    file_name=f"gps_kpi_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ Error creating download: {str(e)}")
    
    # Main content area - with memory optimization
    if st.session_state.data_loaded:
        try:
            not_working_df = st.session_state.not_working_df
            working_df = st.session_state.working_df
            combined_df = st.session_state.combined_df
            
            if not_working_df.empty and working_df.empty:
                st.warning("No data available to display")
                return
            
            final_df = not_working_df if not not_working_df.empty else working_df
            stats = st.session_state.processor.get_summary_stats(final_df)
            
            display_df = format_date_column(final_df, 'Date')
            viz_df = st.session_state.processor.get_visualization_remarks(final_df)
            viz_stats = st.session_state.processor.get_summary_stats(viz_df)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🚛 Not Working Vehicles", stats.get('total_vehicles', 0))
            with col2:
                working_count = len(working_df) if not working_df.empty else 0
                st.metric("✅ Working Vehicles", working_count)
            with col3:
                st.metric("📍 Zones", stats.get('unique_zones', 0))
            with col4:
                st.metric("📡 GPS Devices", stats.get('total_imei', 0))
            
            st.markdown("---")
            
            # Use tabs but limit data display
            tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📋 Data Table", "📈 Analytics"])
            
            with tab1:
                col1, col2 = st.columns(2)
                
                with col1:
                    if viz_stats.get('remarks_summary'):
                        remarks_df = pd.DataFrame({
                            'Remarks': list(viz_stats['remarks_summary'].keys()),
                            'Count': list(viz_stats['remarks_summary'].values())
                        })
                        fig = px.pie(remarks_df, values='Count', names='Remarks', title='Vehicle Status Distribution')
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                with col2:
                    if stats.get('zone_summary'):
                        zone_df = pd.DataFrame({
                            'Zone': list(stats['zone_summary'].keys()),
                            'Count': list(stats['zone_summary'].values())
                        })
                        fig = px.bar(zone_df, x='Zone', y='Count', title='Vehicles by Zone', 
                                    color='Count', color_continuous_scale='Blues')
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                if 'Age' in final_df.columns:
                    age_df = final_df['Age'].value_counts().reset_index()
                    age_df.columns = ['Days', 'Count']
                    age_df = age_df.sort_values('Days')
                    fig = px.line(age_df, x='Days', y='Count', title='Vehicle Age Distribution',
                                 markers=True)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
            with tab2:
                st.subheader("📋 Detailed Data - All Vehicles")
                
                combined_display_df = format_date_column(combined_df, 'Date')
                
                view_filter = st.radio(
                    "Show:",
                    ["All Vehicles", "Not Working Only", "Working Only"],
                    horizontal=True
                )
                
                if view_filter == "Not Working Only":
                    filtered_combined = combined_display_df[combined_display_df['Status'] == 'Not Working']
                elif view_filter == "Working Only":
                    filtered_combined = combined_display_df[combined_display_df['Status'] == 'Working']
                else:
                    filtered_combined = combined_display_df.copy()
                
                # Limit displayed data to prevent memory issues
                if len(filtered_combined) > 1000:
                    st.warning(f"Showing first 1000 of {len(filtered_combined)} records")
                    filtered_combined = filtered_combined.head(1000)
                
                # Display columns
                display_columns = ['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type',
                                 'Facility', 'Last Log Received At', 'Status', 'Technician', 
                                 'Updated Remarks', 'Age', 'Zone']
                display_columns = [col for col in display_columns if col in filtered_combined.columns]
                filtered_combined = filtered_combined[display_columns]
                
                st.dataframe(
                    filtered_combined,
                    use_container_width=True,
                    height=400,
                    hide_index=True
                )
                
                total_records = len(combined_df) if not combined_df.empty else 0
                st.caption(f"Showing {len(filtered_combined)} of {total_records} records")
            
            with tab3:
                st.subheader("📈 Advanced Analytics")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'Age' in final_df.columns and 'Zone' in final_df.columns:
                        age_zone = final_df.groupby('Zone')['Age'].mean().reset_index()
                        fig = px.bar(age_zone, x='Zone', y='Age', title='Average Age by Zone',
                                    color='Age', color_continuous_scale='RdYlGn_r')
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                with col2:
                    if 'Updated Remarks' in viz_df.columns and 'Zone' in viz_df.columns:
                        status_zone = pd.crosstab(viz_df['Zone'], viz_df['Updated Remarks'])
                        fig = px.imshow(status_zone, text_auto=True, 
                                       title='Status Distribution by Zone',
                                       color_continuous_scale='Blues')
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                st.subheader("👨‍🔧 Technician-wise Updated Remarks Analysis")
                
                if 'Technician' in viz_df.columns and 'Updated Remarks' in viz_df.columns:
                    tech_remarks = pd.crosstab(
                        viz_df['Technician'], 
                        viz_df['Updated Remarks'],
                        margins=True,
                        margins_name='Total'
                    )
                    
                    if tech_remarks is not None and not tech_remarks.empty:
                        st.dataframe(
                            tech_remarks,
                            use_container_width=True,
                            height=300
                        )
                
                st.subheader("Key Metrics")
                
                if 'Age' in final_df.columns:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Average Age", f"{final_df['Age'].mean():.1f} days")
                    with col2:
                        st.metric("Max Age", f"{final_df['Age'].max()} days")
                    with col3:
                        st.metric("Min Age", f"{final_df['Age'].min()} days")
        
        except Exception as e:
            st.error(f"❌ Error displaying data: {str(e)}")
            if DEBUG_MODE:
                st.error(traceback.format_exc())
    
    else:
        st.info("""
        👋 **Welcome to the GPS & KPI Monitoring Dashboard!**
        
        ### How to use:
        1. **Upload Files** in the sidebar
        2. Click **Process Data** to generate the report
        3. View **Dashboards**, **Data Tables**, and **Analytics**
        4. **Download** the Excel report
        
        ### Required Files:
        - 📍 GPS Status File (.xlsx or .xlsm)
        - 📊 At least one KPI file (.xlsx)
        - 📋 Vehicle Master (.xlsm) - Recommended for better data matching
        
        ### Optional Files:
        - 📝 GPS Remarks (.csv) - Adds remarks and user information
        """)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Application error: {str(e)}")
        if DEBUG_MODE:
            st.error(traceback.format_exc())
