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

# Import gspread with error handling
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    st.warning("⚠️ gspread not installed. Google Sheets upload feature will be disabled.")

# Set page config
st.set_page_config(
    page_title="GPS & KPI Monitoring Dashboard",
    page_icon="logosumeet.jpeg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Debug mode - set to True for troubleshooting
DEBUG_MODE = True

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
    .debug-info {
        background-color: #f0f0f0;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #ff6b6b;
        font-family: monospace;
        font-size: 12px;
        margin: 10px 0;
        overflow-x: auto;
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
        """Load vehicle master file"""
        try:
            debug_print(f"Loading vehicle master from: {file.name}")
            df = pd.read_excel(file, engine='openpyxl', sheet_name='vehiclemaster', skiprows=4)
            df.columns = df.columns.str.strip()
            df.rename(columns={'Register Number': 'Vehicle Number'}, inplace=True)
            self.vm_df = df
            debug_print(f"✅ Loaded {len(df)} vehicles from master")
            return df
        except Exception as e:
            error_msg = f"Error loading vehicle master: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def process_kpi_file(self, file, kpi_type):
        """Process KPI files based on type"""
        try:
            debug_print(f"Processing KPI file: {file.name} ({kpi_type})")
            df = pd.read_excel(file, engine='openpyxl')
            required_cols = ['Kpi Date', 'Zone', 'Vehicle Number', 'Marching In Out Timings']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                debug_print(f"⚠️ Missing columns in {kpi_type}: {missing_cols}")
                st.warning(f"Missing columns in {kpi_type}: {missing_cols}")
                return None
            
            df = df[required_cols].copy()
            df = df[df['Zone'].notna()]
            df['Kpi Source'] = kpi_type
            debug_print(f"✅ Processed {len(df)} rows from {kpi_type}")
            return df
        except Exception as e:
            error_msg = f"Error processing {kpi_type}: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def process_kpi52(self, file):
        """Process KPI 52 with vehicle master merge"""
        try:
            debug_print(f"Processing KPI 52 from: {file.name}")
            df = pd.read_excel(file, engine='openpyxl')
            df.rename(columns={'Vehicle Number': 'V ID'}, inplace=True)
            merge = pd.merge(df, self.vm_df, how='left', on='V ID')
            kpi_data = merge[['Kpi Date', 'Zone_x', 'Vehicle Number', 'Marching In Out Timings']].copy()
            kpi_data = kpi_data.rename(columns={'Zone_x': 'Zone'})
            kpi_data = kpi_data[kpi_data['Zone'].notna()]
            kpi_data['Kpi Source'] = 'KPI 52'
            debug_print(f"✅ Processed {len(kpi_data)} rows from KPI 52")
            return kpi_data
        except Exception as e:
            error_msg = f"Error processing KPI 52: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def process_gps_status(self, file):
        """Process GPS status file"""
        try:
            debug_print(f"Processing GPS status from: {file.name}")
            df = pd.read_excel(file, engine='openpyxl')
            df.rename(columns={'Chassis No.':'V Id'} ,inplace=True)
            
            log_dates = pd.to_datetime(df['Last Log Received At'], dayfirst=True).dt.normalize()
            max_date = log_dates.max()
            df['Age'] = (max_date - log_dates).dt.days
            
            df['Status'] = np.where(df['Age'] <= 1, 'Working', 'Not Working')
            df['Date'] = max_date
            
            df.rename(columns={'Vehicle Registration No.': 'Vehicle Number'}, inplace=True)
            
            final_df = df[['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type', 
                          'Last Log Received At', 'Last Location', 'Age', 'Status']]
            
            self.gps_df = final_df
            debug_print(f"✅ Processed GPS status: {len(final_df)} vehicles, {len(final_df[final_df['Status']=='Not Working'])} not working")
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
            df = pd.read_csv(file, usecols=['Date', 'Vehicle Registration No.', 'Remarks', 'Facility','Time', 'Technician'])
            df.rename(columns={'Vehicle Registration No.': 'Vehicle Number','Facility':'Remark_Facility','Technician':'Remarks_Technician','Time':'Remarks Date'}, inplace=True)
            debug_print(f"✅ Processed {len(df)} remarks")
            return df
        except Exception as e:
            error_msg = f"Error processing GPS remarks: {str(e)}"
            debug_print(f"❌ {error_msg}")
            st.error(error_msg)
            return None
    
    def combine_all_data(self, kpi_files, gps_file, remarks_file=None):
        """Combine all data sources"""
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
            
            combined_kpi = pd.concat(kpi_dfs, ignore_index=True)
            combined_kpi = combined_kpi.drop_duplicates(subset=['Vehicle Number'], keep='first')
            debug_print(f"Combined KPI data: {len(combined_kpi)} unique vehicles")
            
            merge = pd.merge(gps_df, combined_kpi, how='left', on='Vehicle Number')
            
            not_working = merge[(merge['Vehicle Number'] != 'TEST 02')]
            
            not_working = not_working[['Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type', 
                                      'Last Log Received At', 'Age', 'Status', 'Kpi Source']]
            
            if remarks_file:
                remarks_df = self.process_gps_remarks(remarks_file)
                if remarks_df is not None:
                    not_working = pd.merge(not_working, remarks_df[['Vehicle Number', 'Remarks']], 
                                          how='left', on='Vehicle Number')
            
            if self.vm_df is not None:
                not_working = pd.merge(not_working, self.vm_df[['Vehicle Number', 'Zone', 'Facility', 'Technician']], 
                                      how='left', on='Vehicle Number')
            
            not_working = not_working.fillna('-')
            
            def get_updated_remarks(row):
                remarks = str(row.get('Remarks', '')).lower() if not pd.isna(row.get('Remarks', '')) else ''
                kpi_source = row.get('Kpi Source', '')
                age = row.get('Age', 0)
                
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
            
            if 'Date' in not_working.columns:
                not_working['Date'] = pd.to_datetime(not_working['Date'])
            
            working = not_working[not_working['Status'] == 'Working'].copy()
            not_working_only = not_working[(not_working['Status'] == 'Not Working') & (not_working['Vehicle Number'] != 'TEST 02')].copy()
            
            combined_df = pd.concat([not_working_only, working], ignore_index=True)
            
            self.final_df = not_working_only
            self.not_working_df = not_working_only
            self.working_df = working
            self.combined_df = combined_df
            
            debug_print(f"✅ Data combination complete: Not Working: {len(not_working_only)}, Working: {len(working)}")
            return (not_working_only, working)
            
        except Exception as e:
            error_msg = f"Error combining data: {str(e)}"
            debug_print(f"❌ {error_msg}")
            debug_print(traceback.format_exc())
            st.error(error_msg)
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
    debug_print("Initializing session state")
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
    
    if 'debug_logs' not in st.session_state:
        st.session_state.debug_logs = []


def upload_to_google_sheets(credentials_json, sheet_name, sheet_index, df):
    """
    Upload DataFrame to Google Sheets
    
    Args:
        credentials_json: Service account credentials JSON
        sheet_name: Name of the Google Sheet
        sheet_index: Sheet index (0-based)
        df: DataFrame to upload
    """
    if not GSPREAD_AVAILABLE:
        return False, "❌ gspread library not installed. Please install: pip install gspread oauth2client"
    
    try:
        debug_print(f"Uploading to Google Sheets: {sheet_name}, sheet {sheet_index}")
        # Define the scope
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Authenticate using service account
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json, scope)
        client = gspread.authorize(creds)
        
        # Open the spreadsheet
        spreadsheet = client.open(sheet_name)
        debug_print(f"✅ Opened spreadsheet: {sheet_name}")
        
        # Get the worksheet by index
        worksheet = spreadsheet.get_worksheet(sheet_index)
        debug_print(f"✅ Got worksheet {sheet_index + 1}")
        
        # Clear existing data (keep headers)
        worksheet.clear()
        
        # Prepare data for upload
        # Convert DataFrame to list of lists with headers
        data_to_upload = [df.columns.tolist()] + df.values.tolist()
        
        # Update the worksheet
        worksheet.update(data_to_upload)
        debug_print(f"✅ Uploaded {len(df)} rows to Google Sheets")
        
        return True, f"✅ Successfully uploaded {len(df)} rows to Google Sheet: {sheet_name} (Sheet {sheet_index + 1})"
        
    except gspread.exceptions.SpreadsheetNotFound:
        return False, f"❌ Spreadsheet '{sheet_name}' not found. Please check the name and make sure it's shared with the service account."
    except gspread.exceptions.WorksheetNotFound:
        return False, f"❌ Worksheet at index {sheet_index} not found. Please check the sheet index."
    except Exception as e:
        error_msg = f"❌ Error uploading to Google Sheets: {str(e)}"
        debug_print(error_msg)
        debug_print(traceback.format_exc())
        return False, error_msg


def create_html_email_body(analytics_data):
    """Create email body with exact Campaign Statistics style"""
    debug_print("Creating HTML email body")
    
    # Build technician table HTML
    tech_table_html = ""
    if analytics_data.get('tech_remarks_data') is not None:
        tech_df = analytics_data['tech_remarks_data']
        debug_print(f"Building table with {len(tech_df)} rows")
        
        tech_table_html = """
        <div style="overflow-x: auto; margin-top: 12px;">
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; background: #ffffff; border: 1px solid #dadce0; border-radius: 8px;">
                <thead>
                    <tr style="background: #f8f9fa; border-bottom: 2px solid #dadce0;">
                        <th style="padding: 10px 14px; text-align: left; font-weight: 600; color: #5f6368; font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px;">Technician</th>
        """
        
        # Add column headers
        for col in tech_df.columns:
            if col != 'Total':
                tech_table_html += f"""
                        <th style="padding: 10px 14px; text-align: left; font-weight: 600; color: #5f6368; font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px;">{col}</th>
                """
        tech_table_html += """
                        <th style="padding: 10px 14px; text-align: left; font-weight: 600; color: #5f6368; font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px;">Total</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Add rows
        for idx, row in tech_df.iterrows():
            if idx != 'Total':
                tech_table_html += f"""
                    <tr style="border-bottom: 1px solid #e8eaed;">
                        <td style="padding: 10px 14px; font-weight: 500; color: #202124;"><strong>{idx}</strong></td>
                """
                for col in tech_df.columns:
                    if col != 'Total':
                        value = row[col]
                        # Conditional formatting based on value
                        cell_style = "padding: 10px 14px; color: #202124;"
                        if value > 10:
                            cell_style += " background-color: #fce8e6; color: #d93025; font-weight: 600;"
                        elif value > 5:
                            cell_style += " background-color: #fef7e0; color: #e37400; font-weight: 600;"
                        elif value > 2:
                            cell_style += " background-color: #e8f0fe; color: #1a73e8;"
                        elif value > 0:
                            cell_style += " background-color: #e6f4ea; color: #1e8e3e;"
                        tech_table_html += f"""
                        <td style="{cell_style}">{value}</td>
                        """
                tech_table_html += f"""
                        <td style="padding: 10px 14px; font-weight: 600; color: #202124;">{row['Total']}</td>
                    </tr>
                """
        
        # Add total row
        if 'Total' in tech_df.index:
            tech_table_html += f"""
                    <tr style="background: #f8f9fa; border-top: 2px solid #dadce0; font-weight: 700;">
                        <td style="padding: 10px 14px; color: #202124;">TOTAL</td>
            """
            for col in tech_df.columns:
                if col != 'Total':
                    tech_table_html += f"""
                        <td style="padding: 10px 14px; color: #202124;">{tech_df.loc['Total', col]}</td>
                    """
            tech_table_html += f"""
                        <td style="padding: 10px 14px; color: #202124; font-weight: 700;">{tech_df.loc['Total', 'Total']}</td>
                    </tr>
            """
        
        tech_table_html += """
                </tbody>
            </table>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GPS & KPI Report</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f7fa;
                color: #202124;
                line-height: 1.5;
            }}
            .container {{
                max-width: 1100px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                padding: 24px 28px;
            }}
            
            /* Header */
            .header {{
                margin-bottom: 24px;
                padding-bottom: 16px;
                border-bottom: 1px solid #e8eaed;
            }}
            .header h1 {{
                margin: 0;
                font-size: 20px;
                font-weight: 500;
                color: #202124;
            }}
            .header p {{
                margin: 4px 0 0;
                color: #5f6368;
                font-size: 14px;
            }}
            
            /* Campaign Stats Grid - Exact style */
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 16px;
                margin: 20px 0 24px 0;
                padding: 16px 20px;
                background: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #e8eaed;
            }}
            .stat-item {{
                text-align: left;
            }}
            .stat-value {{
                font-size: 28px;
                font-weight: 500;
                color: #202124;
                line-height: 1.2;
            }}
            .stat-value.green {{
                color: #1e8e3e;
            }}
            .stat-value.red {{
                color: #d93025;
            }}
            .stat-value.orange {{
                color: #e37400;
            }}
            .stat-value.blue {{
                color: #1a73e8;
            }}
            .stat-label {{
                font-size: 12px;
                color: #5f6368;
                margin-top: 2px;
                font-weight: 400;
                letter-spacing: 0.2px;
            }}
            
            /* Section Header - Campaign style */
            .section-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 28px 0 12px 0;
                padding-bottom: 8px;
                border-bottom: 2px solid #e8eaed;
            }}
            .section-header h2 {{
                margin: 0;
                font-size: 15px;
                font-weight: 500;
                color: #202124;
            }}
            .section-header .badge {{
                background: #e8eaed;
                padding: 3px 12px;
                border-radius: 12px;
                font-size: 11px;
                color: #5f6368;
                font-weight: 500;
            }}
            
            /* Filter hint - Campaign style */
            .filter-hint {{
                font-size: 12px;
                color: #5f6368;
                background: #f8f9fa;
                padding: 8px 14px;
                border-radius: 4px;
                margin: 12px 0 0;
                border-left: 3px solid #1a73e8;
            }}
            
            /* Footer */
            .footer {{
                margin-top: 24px;
                padding-top: 16px;
                border-top: 1px solid #e8eaed;
                font-size: 12px;
                color: #5f6368;
                text-align: center;
            }}
            .footer .timestamp {{
                color: #1a73e8;
                font-weight: 500;
            }}
            
            /* Responsive */
            @media only screen and (max-width: 700px) {{
                .container {{
                    padding: 16px;
                }}
                .stats-grid {{
                    grid-template-columns: repeat(3, 1fr);
                    gap: 12px;
                    padding: 12px 16px;
                }}
                .stat-value {{
                    font-size: 22px;
                }}
                table {{
                    font-size: 11px;
                }}
                th, td {{
                    padding: 6px 10px !important;
                }}
            }}
            @media only screen and (max-width: 450px) {{
                .stats-grid {{
                    grid-template-columns: repeat(2, 1fr);
                    gap: 10px;
                }}
                .stat-value {{
                    font-size: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div class="header">
                <h1>🚛 GPS & KPI Monitoring Dashboard</h1>
                <p>Vehicle Status & Technician Performance Report</p>
            </div>
            
            <!-- Stats Grid - Campaign Statistics Style -->
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{analytics_data.get('total_vehicles', 0):,}</div>
                    <div class="stat-label">Total Vehicles</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value green">{analytics_data.get('working_count', 0):,}</div>
                    <div class="stat-label">✅ Working</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value red">{analytics_data.get('not_working_count', 0):,}</div>
                    <div class="stat-label">❌ Not Working</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value orange">{analytics_data.get('tech_with_issues', 0)}</div>
                    <div class="stat-label">👨‍🔧 Techs with Issues</div>
                </div>
            </div>
            
            <!-- Section: Technician Analysis -->
            <div class="section-header">
                <h2>📋 Technician-wise Updated Remarks Analysis</h2>
                <span class="badge">Most Common: {analytics_data.get('most_common_issue', 'N/A')}</span>
            </div>
            
            {tech_table_html}
            
            <div class="filter-hint">
                🔍 Detailed vehicle-level data available in the attached Excel file
            </div>
            
            <!-- Footer -->
            <div class="footer">
                📧 Report generated on <span class="timestamp">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email_with_attachment(sender_email, sender_password, recipient_email, subject, html_body, attachment_data, filename):
    """
    Send email with attachment using Gmail SMTP with HTML body
    """
    try:
        debug_print(f"Sending email to: {recipient_email}")
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Create plain text version (fallback)
        plain_text = """
        GPS & KPI Monitoring Report
        
        Please view this email in HTML format for the best experience.
        The report summary is available in the attachment.
        """
        
        # Attach both plain text and HTML versions
        part1 = MIMEText(plain_text, 'plain')
        part2 = MIMEText(html_body, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Attach file
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment_data.getvalue())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="{filename}"'
        )
        msg.attach(part)
        
        # Gmail SMTP Configuration
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        debug_print("✅ Email sent successfully")
        return True, "Email sent successfully via Gmail!"
        
    except smtplib.SMTPAuthenticationError:
        error_msg = "Gmail authentication failed. Please use an App Password instead of your regular Gmail password."
        debug_print(f"❌ {error_msg}")
        return False, error_msg
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error occurred: {str(e)}"
        debug_print(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        debug_print(f"❌ {error_msg}")
        debug_print(traceback.format_exc())
        return False, error_msg


def create_combined_report(combined_df):
    """Create Excel report with combined data"""
    try:
        debug_print("Creating combined Excel report")
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Format dates
            export_df = format_date_column(combined_df.copy(), 'Date')
            
            # Write to Excel
            export_df.to_excel(writer, index=False, sheet_name='All_Vehicles_Report')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['All_Vehicles_Report']
            for column_idx, column_name in enumerate(export_df.columns, 1):
                # Get the column letter from column index
                column_letter = get_column_letter(column_idx)
                
                # Calculate column width
                max_length = max(
                    export_df[column_name].astype(str).map(len).max() if not export_df[column_name].empty else 0,
                    len(str(column_name))
                )
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        debug_print(f"✅ Excel report created with {len(export_df)} rows")
        return output
    except Exception as e:
        debug_print(f"❌ Error creating Excel report: {str(e)}")
        debug_print(traceback.format_exc())
        return None


def main():
    # Initialize session state first
    initialize_session_state()
    
    # Display debug info if in debug mode
    if DEBUG_MODE:
        with st.expander("🔍 Debug Information", expanded=False):
            st.markdown("### System Information")
            st.code(f"""
Python Version: {sys.version}
Streamlit Version: {st.__version__}
Pandas Version: {pd.__version__}
gspread Available: {GSPREAD_AVAILABLE}
Working Directory: {os.getcwd()}
Files in directory: {os.listdir('.') if os.path.exists('.') else 'N/A'}
            """)
    
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
                        debug_print("Process Data button clicked")
                        result = st.session_state.processor.combine_all_data(
                            kpi_files=kpi_files,
                            gps_file=gps_file,
                            remarks_file=remarks_file
                        )
                        
                        if result is None:
                            st.error("❌ Processing returned None")
                            debug_print("❌ Processing returned None")
                        elif isinstance(result, tuple) and len(result) == 2:
                            not_working_df, working_df = result
                            
                            if not_working_df is not None and working_df is not None:
                                st.session_state.data_loaded = True
                                st.session_state.not_working_df = not_working_df
                                st.session_state.working_df = working_df
                                st.session_state.final_df = not_working_df
                                st.session_state.combined_df = pd.concat([not_working_df, working_df], ignore_index=True)
                                st.success(f"✅ Data processed successfully!\nNot Working: {len(not_working_df)}, Working: {len(working_df)}")
                                debug_print(f"✅ Data processed: Not Working: {len(not_working_df)}, Working: {len(working_df)}")
                            else:
                                st.error("❌ Failed to process data. Please check your input files.")
                                debug_print("❌ Failed to process data - result was None")
                        else:
                            st.error(f"❌ Unexpected return type: {type(result)}")
                            st.write("Returned value:", result)
                            debug_print(f"❌ Unexpected return type: {type(result)}")
                    except Exception as e:
                        st.error(f"❌ Error during processing: {str(e)}")
                        st.error(traceback.format_exc())
                        debug_print(f"❌ Error during processing: {str(e)}")
                        debug_print(traceback.format_exc())
            else:
                st.warning("⚠️ Please upload GPS Status and at least one KPI file")
                debug_print("⚠️ Missing GPS Status or KPI files")
        
        # Download Section
        if st.session_state.data_loaded and not st.session_state.not_working_df.empty:
            st.markdown("---")
            st.subheader("📥 Download")
            
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
        
        # Google Sheets Upload Section
        if st.session_state.data_loaded and not st.session_state.not_working_df.empty:
            st.markdown("---")
            st.subheader("📤 Upload to Google Sheets")
            
            with st.expander("📤 Google Sheets Upload Settings", expanded=False):
                if not GSPREAD_AVAILABLE:
                    st.error("❌ gspread library not installed. Please install: pip install gspread oauth2client")
                
                st.info("""
                **📌 Google Sheets Setup:**
                1. Upload your Service Account JSON credentials file
                2. Share your Google Sheet with the service account email
                3. Enter the sheet name and index
                """)
                
                # Credentials file upload
                creds_file = st.file_uploader(
                    "Upload Service Account JSON Credentials",
                    type=['json'],
                    help="Download from Google Cloud Console → Service Accounts"
                )
                
                # Sheet details
                sheet_name = st.text_input(
                    "Google Sheet Name",
                    value="GPS Not Working",
                    help="Name of the Google Sheet"
                )
                
                sheet_index = st.number_input(
                    "Sheet Index",
                    min_value=0,
                    max_value=10,
                    value=2,
                    help="Sheet index (0-based, 0 = first sheet)"
                )
                
                if st.button("📤 Upload to Google Sheets", type="primary", use_container_width=True):
                    if not GSPREAD_AVAILABLE:
                        st.error("❌ gspread library not installed. Please install: pip install gspread oauth2client")
                    elif creds_file is None:
                        st.error("❌ Please upload your Service Account JSON credentials file")
                    else:
                        with st.spinner("Uploading to Google Sheets..."):
                            try:
                                debug_print("Starting Google Sheets upload")
                                # Load credentials from uploaded file
                                credentials_json = json.load(creds_file)
                                debug_print("✅ Credentials loaded successfully")
                                
                                # Get not working data
                                not_working_df = st.session_state.not_working_df.copy()
                                debug_print(f"✅ Retrieved {len(not_working_df)} rows for upload")
                                
                                # Select only the required columns
                                required_columns = [
                                    'Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 
                                    'Vehicle Type', 'Facility', 'Last Log Received At', 
                                    'Status', 'Technician', 'Updated Remarks', 'Age'
                                ]
                                
                                # Filter columns that exist
                                existing_columns = [col for col in required_columns if col in not_working_df.columns]
                                upload_df = not_working_df[existing_columns].copy()
                                debug_print(f"✅ Selected {len(existing_columns)} columns for upload")
                                
                                # Format Date column
                                if 'Date' in upload_df.columns:
                                    upload_df['Date'] = pd.to_datetime(upload_df['Date']).dt.strftime('%d-%m-%Y')
                                
                                # Format Last Log Received At column
                                if 'Last Log Received At' in upload_df.columns:
                                    upload_df['Last Log Received At'] = pd.to_datetime(
                                        upload_df['Last Log Received At'], errors='coerce', dayfirst=True
                                    ).dt.strftime('%d-%m-%Y')
                                
                                # Rename columns to match requested format
                                column_mapping = {
                                    'Date': 'Date',
                                    'GPS IMEI No.': 'GPS IMEI No.',
                                    'Vehicle Number': 'Vehicle Number',
                                    'V Id': 'VID',
                                    'Vehicle Type': 'Vehicle Type',
                                    'Facility': 'Facility',
                                    'Last Log Received At': 'Last Log Receive at',
                                    'Status': 'Status',
                                    'Technician': 'Technician',
                                    'Updated Remarks': 'Remarks',
                                    'Age': 'Aging'
                                }
                                
                                upload_df = upload_df.rename(columns=column_mapping)
                                debug_print("✅ Columns renamed successfully")
                                
                                # Upload to Google Sheets
                                success, message = upload_to_google_sheets(
                                    credentials_json=credentials_json,
                                    sheet_name=sheet_name,
                                    sheet_index=sheet_index,
                                    df=upload_df
                                )
                                
                                if success:
                                    st.success(f"✅ {message}")
                                    st.info(f"📊 Uploaded {len(upload_df)} Not Working GPS records")
                                    debug_print(f"✅ Upload successful: {len(upload_df)} records")
                                    
                                    # Show preview of uploaded data
                                    st.subheader("📋 Preview of Uploaded Data")
                                    st.dataframe(upload_df.head(10), use_container_width=True)
                                    
                                else:
                                    st.error(f"❌ {message}")
                                    debug_print(f"❌ Upload failed: {message}")
                                    
                            except json.JSONDecodeError:
                                error_msg = "❌ Invalid JSON file. Please upload a valid Service Account credentials file."
                                st.error(error_msg)
                                debug_print(f"❌ {error_msg}")
                            except Exception as e:
                                error_msg = f"❌ Error uploading to Google Sheets: {str(e)}"
                                st.error(error_msg)
                                st.error(traceback.format_exc())
                                debug_print(f"❌ {error_msg}")
                                debug_print(traceback.format_exc())
        
        # Email Section with Gmail Support
        if st.session_state.data_loaded and not st.session_state.combined_df.empty:
            st.markdown("---")
            st.subheader("📧 Send Email Report via Gmail")
            
            with st.expander("📧 Gmail Settings", expanded=True):
                st.info("""
                **📌 Gmail Setup Instructions:**
                1. Enable 2-Factor Authentication on your Gmail account
                2. Generate an App Password:
                   - Go to Google Account → Security → 2-Step Verification
                   - Scroll to bottom → App passwords
                   - Select "Mail" and "Other (Custom name)"
                   - Generate and copy the password
                3. Use the generated App Password below (NOT your regular Gmail password)
                """)
                
                sender_email = st.text_input(
                    "Your Gmail Address", 
                    placeholder="your.email@gmail.com",
                    help="Enter your full Gmail address"
                )
                
                sender_password = st.text_input(
                    "Gmail App Password", 
                    type="password",
                    help="Use the App Password generated from your Google Account (16 characters)"
                )
                
                recipient_email = st.text_input(
                    "Recipient Email Address", 
                    placeholder="manager@company.com",
                    help="Enter the email address where you want to send the report"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    include_working = st.checkbox("Include Working Vehicles", value=True)
                with col2:
                    include_not_working = st.checkbox("Include Not Working Vehicles", value=True)
                
                if st.button("📧 Send Email Report", type="primary", use_container_width=True):
                    if not sender_email or not sender_password or not recipient_email:
                        st.error("❌ Please fill in all email fields")
                        debug_print("❌ Missing email fields")
                    elif "@gmail.com" not in sender_email:
                        st.error("❌ Please use a valid Gmail address (must end with @gmail.com)")
                        debug_print("❌ Invalid Gmail address")
                    else:
                        with st.spinner("Preparing and sending email..."):
                            try:
                                debug_print("Starting email preparation")
                                combined_df = st.session_state.combined_df.copy()
                                not_working_df = st.session_state.not_working_df.copy()
                                
                                # Get analytics data for email body
                                viz_df = st.session_state.processor.get_visualization_remarks(not_working_df)
                                
                                if not include_working and include_not_working:
                                    combined_df = combined_df[combined_df['Status'] == 'Not Working']
                                    viz_df = viz_df[viz_df['Status'] == 'Not Working']
                                    debug_print("Filtering: Only Not Working")
                                elif include_working and not include_not_working:
                                    combined_df = combined_df[combined_df['Status'] == 'Working']
                                    viz_df = viz_df[viz_df['Status'] == 'Working']
                                    debug_print("Filtering: Only Working")
                                else:
                                    debug_print("Filtering: All vehicles")
                                
                                if combined_df.empty:
                                    st.warning("No data to send based on your selection")
                                    debug_print("⚠️ No data to send based on selection")
                                else:
                                    # Prepare analytics data for email
                                    analytics_data = {}
                                    
                                    # Basic stats - get counts from combined_df
                                    analytics_data['total_vehicles'] = len(combined_df)
                                    analytics_data['working_count'] = len(combined_df[combined_df['Status'] == 'Working']) if 'Status' in combined_df.columns else 0
                                    analytics_data['not_working_count'] = len(combined_df[combined_df['Status'] == 'Not Working']) if 'Status' in combined_df.columns else 0
                                    debug_print(f"Stats: Total: {analytics_data['total_vehicles']}, Working: {analytics_data['working_count']}, Not Working: {analytics_data['not_working_count']}")
                                    
                                    # Technician remarks data
                                    tech_remarks = None
                                    tech_remarks_viz = None
                                    tech_with_issues = 0
                                    most_common_issue = 'N/A'
                                    
                                    if 'Technician' in viz_df.columns and 'Updated Remarks' in viz_df.columns:
                                        tech_remarks = pd.crosstab(
                                            viz_df['Technician'], 
                                            viz_df['Updated Remarks'],
                                            margins=True,
                                            margins_name='Total'
                                        )
                                        
                                        if tech_remarks is not None and not tech_remarks.empty:
                                            analytics_data['tech_remarks_data'] = tech_remarks
                                            debug_print(f"✅ Tech remarks table created with {len(tech_remarks)} rows")
                                            
                                            tech_remarks_viz = tech_remarks.drop('Total', errors='ignore')
                                            if 'Total' in tech_remarks_viz.columns:
                                                tech_remarks_viz = tech_remarks_viz.drop('Total', axis=1, errors='ignore')
                                            
                                            if not tech_remarks_viz.empty:
                                                remarks_cols = [col for col in tech_remarks_viz.columns if col != 'Need to check']
                                                if remarks_cols:
                                                    tech_with_issues = tech_remarks_viz[remarks_cols].sum(axis=1)
                                                    tech_with_issues = tech_with_issues[tech_with_issues > 0].count()
                                                    
                                                    most_common_remarks = tech_remarks_viz[remarks_cols].idxmax(axis=1)
                                                    most_common = most_common_remarks.value_counts()
                                                    most_common_issue = most_common.index[0] if not most_common.empty else 'N/A'
                                                    debug_print(f"Tech with issues: {tech_with_issues}, Most common: {most_common_issue}")
                                    
                                    analytics_data['tech_with_issues'] = tech_with_issues
                                    analytics_data['most_common_issue'] = most_common_issue
                                    
                                    # Create HTML email body
                                    html_body = create_html_email_body(analytics_data)
                                    
                                    # Create report file
                                    report_data = create_combined_report(combined_df)
                                    if report_data is None:
                                        st.error("❌ Failed to create Excel report")
                                        debug_print("❌ Failed to create Excel report")
                                    else:
                                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                        subject = f"GPS & KPI Monitoring Report - {timestamp}"
                                        filename = f"GPS_KPI_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                                        
                                        # Send email
                                        success, message = send_email_with_attachment(
                                            sender_email=sender_email,
                                            sender_password=sender_password,
                                            recipient_email=recipient_email,
                                            subject=subject,
                                            html_body=html_body,
                                            attachment_data=report_data,
                                            filename=filename
                                        )
                                        
                                        if success:
                                            st.success(f"✅ Email sent successfully to {recipient_email}!")
                                            st.info(f"Report includes: {analytics_data.get('working_count', 0)} Working, {analytics_data.get('not_working_count', 0)} Not Working vehicles")
                                            debug_print("✅ Email sent successfully")
                                        else:
                                            st.error(f"❌ {message}")
                                            debug_print(f"❌ Email failed: {message}")
                                        
                            except Exception as e:
                                error_msg = f"❌ Error sending email: {str(e)}"
                                st.error(error_msg)
                                st.error(traceback.format_exc())
                                debug_print(f"❌ {error_msg}")
                                debug_print(traceback.format_exc())
    
    # Main content area
    if st.session_state.data_loaded:
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
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                if stats.get('zone_summary'):
                    zone_df = pd.DataFrame({
                        'Zone': list(stats['zone_summary'].keys()),
                        'Count': list(stats['zone_summary'].values())
                    })
                    fig = px.bar(zone_df, x='Zone', y='Count', title='Vehicles by Zone', 
                                color='Count', color_continuous_scale='Blues')
                    st.plotly_chart(fig, use_container_width=True)
            
            if 'Age' in final_df.columns:
                age_df = final_df['Age'].value_counts().reset_index()
                age_df.columns = ['Days', 'Count']
                age_df = age_df.sort_values('Days')
                fig = px.line(age_df, x='Days', y='Count', title='Vehicle Age Distribution',
                             markers=True)
                st.plotly_chart(fig, use_container_width=True)
        
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
            
            col1, col2, col3 = st.columns(3)
            with col1:
                zone_options = sorted(filtered_combined['Zone'].unique()) if 'Zone' in filtered_combined.columns else []
                zone_filter = st.multiselect(
                    "Filter by Zone",
                    options=zone_options,
                    default=[]
                )
            with col2:
                status_options = sorted(filtered_combined['Updated Remarks'].unique()) if 'Updated Remarks' in filtered_combined.columns else []
                status_filter = st.multiselect(
                    "Filter by Remarks",
                    options=status_options,
                    default=[]
                )
            with col3:
                facility_options = sorted(filtered_combined['Facility'].unique()) if 'Facility' in filtered_combined.columns else []
                facility_filter = st.multiselect(
                    "Filter by Facility",
                    options=facility_options,
                    default=[]
                )
            
            if zone_filter and 'Zone' in filtered_combined.columns:
                filtered_combined = filtered_combined[filtered_combined['Zone'].isin(zone_filter)]
            if status_filter and 'Updated Remarks' in filtered_combined.columns:
                filtered_combined = filtered_combined[filtered_combined['Updated Remarks'].isin(status_filter)]
            if facility_filter and 'Facility' in filtered_combined.columns:
                filtered_combined = filtered_combined[filtered_combined['Facility'].isin(facility_filter)]
            
            if 'Last Log Received At' in filtered_combined.columns:
                filtered_combined['Last Log Received At'] = pd.to_datetime(
                    filtered_combined['Last Log Received At'], errors='coerce', dayfirst=True
                ).dt.strftime('%d-%m-%Y')
            if 'Date' in filtered_combined.columns:
                filtered_combined['Date_'] = pd.to_datetime(filtered_combined['Date'], errors='coerce')

            filtered_combined['Unique ID'] = (
                filtered_combined['Vehicle Type'].astype(str) + "_" + 
                filtered_combined['Date_'].dt.strftime('%Y%m%d').fillna('') + 
                filtered_combined['Vehicle Number'].astype(str)
            )   

            display_columns = ['Unique ID','Date', 'GPS IMEI No.', 'Vehicle Number', 'V Id', 'Vehicle Type',
                             'Facility', 'Last Log Received At', 'Status', 'Technician', 
                             'Updated Remarks', 'Age', 'Remarks','Kpi Source', 'Zone']
            if 'Age' in filtered_combined.columns:
                filtered_combined['Age'] = filtered_combined['Age'].astype(int)
            display_columns = [col for col in display_columns if col in filtered_combined.columns]
            filtered_combined = filtered_combined[display_columns]
            
            styled_df = filtered_combined.style.apply(highlight_status, axis=1)
            
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=400,
                hide_index=True,
                column_config={
                    "Date": st.column_config.TextColumn(
                        "Date",
                        help="Date in DD-MM-YYYY format"
                    )
                }
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
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                if 'Updated Remarks' in viz_df.columns and 'Zone' in viz_df.columns:
                    status_zone = pd.crosstab(viz_df['Zone'], viz_df['Updated Remarks'])
                    fig = px.imshow(status_zone, text_auto=True, 
                                   title='Status Distribution by Zone',
                                   color_continuous_scale='Blues')
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
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
                        height=400
                    )
                    
                    tech_remarks_viz = tech_remarks.drop('Total', errors='ignore')
                    
                    if 'Total' in tech_remarks_viz.columns:
                        tech_remarks_viz = tech_remarks_viz.drop('Total', axis=1, errors='ignore')
                    
                    if not tech_remarks_viz.empty:
                        fig = px.bar(
                            tech_remarks_viz,
                            title='Technician-wise Updated Remarks Distribution',
                            labels={'value': 'Count', 'variable': 'Remarks'},
                            barmode='stack',
                            color_discrete_sequence=px.colors.qualitative.Set3
                        )
                        fig.update_layout(
                            xaxis_title='Technician',
                            yaxis_title='Number of Vehicles',
                            legend_title='Updated Remarks'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.subheader("Technician Performance Metrics")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            issue_cols = [col for col in tech_remarks_viz.columns if col != 'Need to check']
                            if issue_cols:
                                tech_with_issues = tech_remarks_viz[issue_cols].sum(axis=1)
                                tech_with_issues = tech_with_issues[tech_with_issues > 0].count()
                            else:
                                tech_with_issues = 0
                            st.metric("Technicians with Issues", tech_with_issues)
                        
                        with col2:
                            if not tech_remarks_viz.empty:
                                remarks_cols = [col for col in tech_remarks_viz.columns if col != 'Need to check']
                                if remarks_cols:
                                    most_common_remarks = tech_remarks_viz[remarks_cols].idxmax(axis=1)
                                    most_frequent = most_common_remarks.value_counts().index[0] if not most_common_remarks.empty else 'N/A'
                                    st.metric("Most Common Issue", most_frequent)
                                else:
                                    st.metric("Most Common Issue", "No issues")
                        
                        with col3:
                            total_issues = 0
                            if not tech_remarks_viz.empty:
                                remarks_cols = [col for col in tech_remarks_viz.columns if col != 'Need to check']
                                if remarks_cols:
                                    total_issues = tech_remarks_viz[remarks_cols].sum().sum()
                            st.metric("Total Vehicle Issues", total_issues)
            
            st.subheader("Key Metrics")
            
            if 'Age' in final_df.columns:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Average Age", f"{final_df['Age'].mean():.1f} days")
                with col2:
                    st.metric("Max Age", f"{final_df['Age'].max()} days")
                with col3:
                    st.metric("Min Age", f"{final_df['Age'].min()} days")
    
    else:
        st.info("""
        👋 **Welcome to the GPS & KPI Monitoring Dashboard!**
        
        ### How to use:
        1. **Upload Files** in the sidebar
        2. Click **Process Data** to generate the report
        3. View **Dashboards**, **Data Tables**, and **Analytics**
        4. **Download** the Excel report
        5. **Upload to Google Sheets** with one click
        6. **Send Email** to your manager with the report via Gmail
        
        ### Required Files:
        - 📍 GPS Status File (.xlsx or .xlsm)
        - 📊 At least one KPI file (.xlsx)
        - 📋 Vehicle Master (.xlsm) - Recommended for better data matching
        
        ### Optional Files:
        - 📝 GPS Remarks (.csv) - Adds remarks and user information
        - 🔑 Service Account JSON - For Google Sheets upload
        
        ### Google Sheets Upload:
        - Upload your Service Account JSON credentials
        - Sheet name: "GPS Not Working"
        - Sheet index: 2 (third sheet)
        - Automatically uploads only Not Working GPS data
        
        ### Email Setup:
        - Uses Gmail SMTP (smtp.gmail.com:587)
        - Requires Gmail App Password (enable 2FA first)
        - App Password: Google Account → Security → App passwords
        
        ### Debug Mode:
        - Debug mode is enabled (set DEBUG_MODE = False to disable)
        - Check the debug expander for system information
        - All errors are logged with detailed stack traces
        """)


if __name__ == "__main__":
    main()
