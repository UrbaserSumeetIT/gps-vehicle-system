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
import gc
import warnings
warnings.filterwarnings('ignore')

# Set page config FIRST - before any other imports or operations
st.set_page_config(
    page_title="GPS & KPI Monitoring Dashboard",
    page_icon="logosumeet.jpeg",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    /* Memory optimization */
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
            
            # Reset file pointer
            file.seek(0)
            
            # First, try to read with limited rows to check structure
            try:
                # Read only first few rows to identify columns
                sample_df = pd.read_excel(file, engine='openpyxl', nrows=5, sheet_name='vehiclemaster')
                debug_print(f"Sample columns: {sample_df.columns.tolist()}")
                file.seek(0)  # Reset file pointer
            except Exception as e:
                debug_print(f"Error reading sample: {e}")
                file.seek(0)
            
            # Read the actual data with memory optimization
            df = pd.read_excel(
                file, 
                engine='openpyxl', 
                sheet_name='vehiclemaster', 
                skiprows=4,
                dtype=str  # Read all as string to avoid type inference issues
            )
            
            # Clean column names
            df.columns = df.columns.str.strip()
            
            # Find the correct column for vehicle number
            vehicle_col = None
            for col in df.columns:
                if 'Register Number' in col or 'Vehicle Number' in col or 'Vehicle No' in col:
                    vehicle_col = col
                    break
            
            if vehicle_col:
                df.rename(columns={vehicle_col: 'Vehicle Number'}, inplace=True)
                # Remove rows with empty vehicle numbers
                df = df[df['Vehicle Number'].notna()]
                df = df[df['Vehicle Number'] != '']
                df = df[df['Vehicle Number'] != 'nan']
            
            # Keep only necessary columns
            important_cols = ['Vehicle Number', 'Zone', 'Facility', 'Technician']
            existing_cols = [col for col in important_cols if col in df.columns]
            if existing_cols:
                df = df[existing_cols].copy()
            
            self.vm_df = df
            debug_print(f"✅ Loaded {len(df)} vehicles from master")
            
            # Force garbage collection
            gc.collect()
            return df
            
        except Exception as e:
            error_msg = f"Error loading vehicle master: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(f"Error loading vehicle master: {e}")
            return None
    
    def process_kpi_file(self, file, kpi_type):
        """Process KPI files based on type - optimized"""
        try:
            debug_print(f"Processing KPI file: {file.name} ({kpi_type})")
            file.seek(0)
            
            # Read only necessary columns
            df = pd.read_excel(file, engine='openpyxl', dtype=str)
            
            required_cols = ['Kpi Date', 'Zone', 'Vehicle Number', 'Marching In Out Timings']
            # Check which required columns exist
            existing_cols = [col for col in required_cols if col in df.columns]
            
            if len(existing_cols) < 3:
                debug_print(f"⚠️ Missing columns in {kpi_type}: {required_cols}")
                return None
            
            df = df[existing_cols].copy()
            df = df[df['Zone'].notna()]
            df = df[df['Zone'] != '']
            df = df[df['Zone'] != 'nan']
            df['Kpi Source'] = kpi_type
            
            debug_print(f"✅ Processed {len(df)} rows from {kpi_type}")
            gc.collect()
            return df
            
        except Exception as e:
            error_msg = f"Error processing {kpi_type}: {str(e)}"
            debug_print(f"❌ {error_msg}")
            return None
    
    def process_kpi52(self, file):
        """Process KPI 52 with vehicle master merge - optimized"""
        try:
            debug_print(f"Processing KPI 52 from: {file.name}")
            file.seek(0)
            
            df = pd.read_excel(file, engine='openpyxl', dtype=str)
            
            # Find vehicle ID column
            vid_col = None
            for col in df.columns:
                if 'V ID' in col or 'Vehicle Number' in col:
                    vid_col = col
                    break
            
            if not vid_col:
                debug_print("⚠️ No vehicle ID column found in KPI 52")
                return None
            
            df.rename(columns={vid_col: 'V ID'}, inplace=True)
            
            # Merge with vehicle master
            if self.vm_df is not None and not self.vm_df.empty:
                merge = pd.merge(df, self.vm_df, how='left', on='V ID')
            else:
                merge = df.copy()
            
            # Extract KPI data
            kpi_data = pd.DataFrame()
            if 'Kpi Date' in merge.columns:
                kpi_data['Kpi Date'] = merge['Kpi Date']
            if 'Zone' in merge.columns:
                kpi_data['Zone'] = merge['Zone']
            elif 'Zone_x' in merge.columns:
                kpi_data['Zone'] = merge['Zone_x']
            if 'Vehicle Number' in merge.columns:
                kpi_data['Vehicle Number'] = merge['Vehicle Number']
            if 'Marching In Out Timings' in merge.columns:
                kpi_data['Marching In Out Timings'] = merge['Marching In Out Timings']
            
            if 'Zone' in kpi_data.columns:
                kpi_data = kpi_data[kpi_data['Zone'].notna()]
                kpi_data = kpi_data[kpi_data['Zone'] != '']
                kpi_data = kpi_data[kpi_data['Zone'] != 'nan']
            
            kpi_data['Kpi Source'] = 'KPI 52'
            
            debug_print(f"✅ Processed {len(kpi_data)} rows from KPI 52")
            gc.collect()
            return kpi_data
            
        except Exception as e:
            error_msg = f"Error processing KPI 52: {str(e)}"
            debug_print(f"❌ {error_msg}")
            return None
    
    def process_gps_status(self, file):
        """Process GPS status file - optimized"""
        try:
            debug_print(f"Processing GPS status from: {file.name}")
            file.seek(0)
            
            # Try to read the file
            df = pd.read_excel(file, engine='openpyxl', dtype=str)
            
            # Find and rename columns
            col_mapping = {}
            
            # Find Chassis No. / V Id
            for col in df.columns:
                if 'Chassis' in col or 'chassis' in col or 'V Id' in col or 'VID' in col:
                    col_mapping[col] = 'V Id'
                    break
            
            # Find Vehicle Registration No.
            for col in df.columns:
                if 'Registration' in col or 'Vehicle Number' in col or 'Vehicle No' in col:
                    col_mapping[col] = 'Vehicle Number'
                    break
            
            # Rename columns
            for old, new in col_mapping.items():
                if old in df.columns:
                    df.rename(columns={old: new}, inplace=True)
            
            # Process date column
            if 'Last Log Received At' in df.columns:
                try:
                    # Try to convert to datetime
                    df['Last Log Received At'] = pd.to_datetime(df['Last Log Received At'], errors='coerce')
                    max_date = df['Last Log Received At'].max()
                    df['Date'] = max_date
                    df['Age'] = (max_date - df['Last Log Received At']).dt.days
                    df['Status'] = np.where(df['Age'] <= 1, 'Working', 'Not Working')
                except Exception as e:
                    debug_print(f"Date conversion error: {e}")
                    df['Age'] = 0
                    df['Status'] = 'Unknown'
                    df['Date'] = datetime.now()
            
            # Keep only necessary columns
            cols_to_keep = ['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type', 
                           'Last Log Received At', 'Age', 'Status']
            existing_cols = [col for col in cols_to_keep if col in df.columns]
            
            if not existing_cols:
                debug_print("⚠️ No required columns found in GPS file")
                return None
            
            final_df = df[existing_cols].copy()
            
            # Clean vehicle numbers
            if 'Vehicle Number' in final_df.columns:
                final_df['Vehicle Number'] = final_df['Vehicle Number'].astype(str).str.strip()
                final_df = final_df[final_df['Vehicle Number'] != 'nan']
                final_df = final_df[final_df['Vehicle Number'] != '']
                final_df = final_df[final_df['Vehicle Number'] != 'None']
            
            self.gps_df = final_df
            debug_print(f"✅ Processed GPS status: {len(final_df)} vehicles")
            gc.collect()
            return final_df
            
        except Exception as e:
            error_msg = f"Error processing GPS status: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(f"Error processing GPS status: {e}")
            return None
    
    def process_gps_remarks(self, file):
        """Process GPS remarks CSV file"""
        try:
            debug_print(f"Processing GPS remarks from: {file.name}")
            file.seek(0)
            
            df = pd.read_csv(file, dtype=str)
            
            # Check for required columns
            required_cols = ['Date', 'Vehicle Registration No.']
            existing_cols = [col for col in required_cols if col in df.columns]
            
            if len(existing_cols) < 2:
                debug_print(f"⚠️ Missing columns in remarks file")
                return None
            
            # Rename columns
            rename_map = {}
            for col in df.columns:
                if 'Registration' in col or 'Vehicle No' in col:
                    rename_map[col] = 'Vehicle Number'
                if 'Remarks' in col:
                    rename_map[col] = 'Remarks'
                if 'Technician' in col:
                    rename_map[col] = 'Technician'
                if 'Facility' in col:
                    rename_map[col] = 'Facility'
            
            df.rename(columns=rename_map, inplace=True)
            
            debug_print(f"✅ Processed {len(df)} remarks")
            return df
            
        except Exception as e:
            error_msg = f"Error processing GPS remarks: {str(e)}"
            debug_print(f"❌ {error_msg}")
            return None
    
    def combine_all_data(self, kpi_files, gps_file, remarks_file=None):
        """Combine all data sources - optimized for memory"""
        try:
            debug_print("Starting data combination process...")
            
            if not gps_file:
                st.error("No GPS file provided")
                return (None, None)
                
            # Process GPS file
            gps_df = self.process_gps_status(gps_file)
            if gps_df is None or gps_df.empty:
                st.error("Failed to process GPS file or no data found")
                return (None, None)
            
            debug_print(f"GPS data: {len(gps_df)} rows")
            
            # Process KPI files
            kpi_dfs = []
            for file, kpi_type in kpi_files:
                debug_print(f"Processing KPI: {kpi_type}")
                if '52' in kpi_type and self.vm_df is not None:
                    kpi_df = self.process_kpi52(file)
                else:
                    kpi_df = self.process_kpi_file(file, kpi_type)
                
                if kpi_df is not None and not kpi_df.empty:
                    kpi_dfs.append(kpi_df)
            
            if not kpi_dfs:
                st.warning("No valid KPI data found - continuing with GPS data only")
                combined_kpi = pd.DataFrame()
            else:
                combined_kpi = pd.concat(kpi_dfs, ignore_index=True)
                if 'Vehicle Number' in combined_kpi.columns:
                    combined_kpi = combined_kpi.drop_duplicates(subset=['Vehicle Number'], keep='first')
                debug_print(f"Combined KPI data: {len(combined_kpi)} unique vehicles")
            
            # Merge with GPS data
            if not combined_kpi.empty and 'Vehicle Number' in combined_kpi.columns:
                merge = pd.merge(gps_df, combined_kpi, how='left', on='Vehicle Number')
            else:
                merge = gps_df.copy()
            
            # Filter out test vehicles
            merge = merge[merge['Vehicle Number'] != 'TEST 02']
            merge = merge[merge['Vehicle Number'] != 'test 02']
            
            # Add remarks if provided
            if remarks_file:
                remarks_df = self.process_gps_remarks(remarks_file)
                if remarks_df is not None and 'Vehicle Number' in remarks_df.columns:
                    merge = pd.merge(merge, remarks_df[['Vehicle Number', 'Remarks']], 
                                    how='left', on='Vehicle Number')
            
            # Add vehicle master data
            if self.vm_df is not None and not self.vm_df.empty:
                vm_cols = ['Vehicle Number', 'Zone', 'Facility', 'Technician']
                existing_vm = [col for col in vm_cols if col in self.vm_df.columns]
                if existing_vm:
                    merge = pd.merge(merge, self.vm_df[existing_vm], 
                                    how='left', on='Vehicle Number')
            
            # Fill NaN values
            merge = merge.fillna('-')
            
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
            
            if 'Updated Remarks' not in merge.columns:
                merge['Updated Remarks'] = merge.apply(get_updated_remarks, axis=1)
            
            # Format dates
            if 'Date' in merge.columns:
                try:
                    merge['Date'] = pd.to_datetime(merge['Date'])
                except:
                    pass
            
            # Separate working and not working
            if 'Status' in merge.columns:
                working = merge[merge['Status'] == 'Working'].copy()
                not_working_only = merge[(merge['Status'] == 'Not Working') & 
                                        (merge['Vehicle Number'] != 'TEST 02')].copy()
            else:
                working = pd.DataFrame()
                not_working_only = merge.copy()
            
            self.final_df = not_working_only
            self.not_working_df = not_working_only
            self.working_df = working
            self.combined_df = pd.concat([not_working_only, working], ignore_index=True)
            
            debug_print(f"✅ Data combination complete: Not Working: {len(not_working_only)}, Working: {len(working)}")
            gc.collect()
            return (not_working_only, working)
            
        except Exception as e:
            error_msg = f"Error combining data: {str(e)}"
            debug_print(f"❌ {error_msg}")
            debug_print(traceback.format_exc())
            st.error(f"Error combining data: {e}")
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
                try:
                    vm_df = st.session_state.processor.load_vehicle_master(vm_file)
                    if vm_df is not None and not vm_df.empty:
                        st.success(f"✅ Loaded {len(vm_df)} vehicles")
                    else:
                        st.warning("⚠️ No vehicles loaded from master file")
                except Exception as e:
                    st.error(f"Error loading vehicle master: {e}")
        
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
            if gps_file:
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
                            
                            if not_working_df is not None and not not_working_df.empty:
                                st.session_state.data_loaded = True
                                st.session_state.not_working_df = not_working_df
                                st.session_state.working_df = working_df if working_df is not None else pd.DataFrame()
                                st.session_state.final_df = not_working_df
                                st.session_state.combined_df = pd.concat([not_working_df, working_df if working_df is not None else pd.DataFrame()], ignore_index=True)
                                st.success(f"✅ Data processed successfully!\nNot Working: {len(not_working_df)}, Working: {len(working_df) if working_df is not None else 0}")
                            else:
                                st.error("❌ Failed to process data. Please check your input files.")
                        else:
                            st.error(f"❌ Unexpected return type: {type(result)}")
                    except Exception as e:
                        st.error(f"❌ Error during processing: {str(e)}")
                        if DEBUG_MODE:
                            st.error(traceback.format_exc())
            else:
                st.warning("⚠️ Please upload GPS Status file")
        
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
            
            if not_working_df.empty:
                st.warning("No data available to display")
                return
            
            final_df = not_working_df
            stats = st.session_state.processor.get_summary_stats(final_df)
            
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
            
            # Data Table
            st.subheader("📋 Not Working Vehicles")
            
            display_columns = ['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type',
                             'Facility', 'Last Log Received At', 'Status', 'Technician', 
                             'Updated Remarks', 'Age', 'Zone']
            
            # Get existing columns
            existing_display = [col for col in display_columns if col in not_working_df.columns]
            display_df = not_working_df[existing_display].copy()
            
            # Format dates
            if 'Date' in display_df.columns:
                display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime('%d-%m-%Y')
            
            if 'Last Log Received At' in display_df.columns:
                display_df['Last Log Received At'] = pd.to_datetime(
                    display_df['Last Log Received At'], errors='coerce'
                ).dt.strftime('%d-%m-%Y')
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            st.caption(f"Total Not Working Vehicles: {len(display_df)}")
            
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
        3. View the **Data Table** with Not Working vehicles
        4. **Download** the Excel report
        
        ### Required Files:
        - 📍 GPS Status File (.xlsx or .xlsm)
        
        ### Optional Files:
        - 📋 Vehicle Master (.xlsm) - For better data matching
        - 📊 KPI Files (.xlsx) - For KPI data integration
        - 📝 GPS Remarks (.csv) - Adds remarks and user information
        """)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Application error: {str(e)}")
        if DEBUG_MODE:
            st.error(traceback.format_exc())
