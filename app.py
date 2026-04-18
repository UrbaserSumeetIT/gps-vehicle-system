import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64
from pathlib import Path
import hashlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import seaborn as sns
import requests
import json
import numpy as np
import os
from PIL import Image
import tempfile
import warnings
warnings.filterwarnings('ignore')

# Check if kaleido is available for Plotly image export
try:
    import kaleido
    KALEIDO_AVAILABLE = True
except ImportError:
    KALEIDO_AVAILABLE = False

# ==================== PERMANENT CONFIGURATION STORAGE ====================
CONFIG_FILE = "biometric_monitor_config.json"
CONFIG_DIR = Path.home() / ".biometric_monitor"
CONFIG_PATH = CONFIG_DIR / CONFIG_FILE

def ensure_config_dir():
    """Create config directory if it doesn't exist"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        st.error(f"Could not create config directory: {e}")
        return False

def load_config():
    """Load configuration from file"""
    default_config = {
        'apps_script_url': '',
        'sheet_config': {
            'sheet_name': 'Biometric_Device_Monitor',
            'worksheet_name': 'Device_Data',
            'summary_worksheet': 'Summary'
        },
        'auto_export_enabled': False,
        'export_mode': 'Replace (Overwrite)',
        'alerts_config': {
            'inactive_threshold': 30,
            'email_alerts': False,
            'email_recipient': ''
        },
        'processing_config': {
            'active_days': 2,
            'date_format': 'Auto Detect'
        },
        'display_config': {
            'theme': 'light',
            'default_view': 'Dashboard',
            'rows_per_page': 50
        },
        'column_mappings': {
            'portal_columns': {},
            'master_columns': {}
        },
        'app_version': '5.2',
        'last_updated': datetime.now().isoformat()
    }
    
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                saved_config = json.load(f)
                # Merge saved config with default to ensure all keys exist
                for key in default_config:
                    if key not in saved_config:
                        saved_config[key] = default_config[key]
                    elif isinstance(default_config[key], dict):
                        for subkey in default_config[key]:
                            if subkey not in saved_config[key]:
                                saved_config[key][subkey] = default_config[key][subkey]
                return saved_config
        else:
            # Create default config file
            ensure_config_dir()
            with open(CONFIG_PATH, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    except Exception as e:
        st.error(f"Error loading config: {e}")
        return default_config

def save_config(config_dict):
    """Save configuration to file"""
    try:
        ensure_config_dir()
        config_dict['last_updated'] = datetime.now().isoformat()
        config_dict['app_version'] = '5.2'
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config_dict, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving config: {e}")
        return False

def reset_config_to_default():
    """Reset configuration to default values"""
    default_config = {
        'apps_script_url': '',
        'sheet_config': {
            'sheet_name': 'Biometric_Device_Monitor',
            'worksheet_name': 'Device_Data',
            'summary_worksheet': 'Summary'
        },
        'auto_export_enabled': False,
        'export_mode': 'Replace (Overwrite)',
        'alerts_config': {
            'inactive_threshold': 30,
            'email_alerts': False,
            'email_recipient': ''
        },
        'processing_config': {
            'active_days': 2,
            'date_format': 'Auto Detect'
        },
        'display_config': {
            'theme': 'light',
            'default_view': 'Dashboard',
            'rows_per_page': 50
        },
        'column_mappings': {
            'portal_columns': {},
            'master_columns': {}
        },
        'app_version': '5.2',
        'last_updated': datetime.now().isoformat()
    }
    return save_config(default_config)

def export_config_to_file():
    """Export configuration to a user-selected location"""
    try:
        config = load_config()
        config_json = json.dumps(config, indent=2)
        b64 = base64.b64encode(config_json.encode()).decode()
        href = f'<a href="data:application/json;base64,{b64}" download="biometric_monitor_config.json">Download Configuration File</a>'
        return href
    except Exception as e:
        return f"Error exporting config: {e}"

def import_config_from_file(uploaded_file):
    """Import configuration from uploaded file"""
    try:
        config_data = json.load(uploaded_file)
        # Validate required keys
        required_keys = ['apps_script_url', 'sheet_config', 'alerts_config', 'processing_config']
        for key in required_keys:
            if key not in config_data:
                config_data[key] = load_config()[key]
        return save_config(config_data), config_data
    except Exception as e:
        return False, f"Error importing config: {e}"

# Load configuration at startup
PERMANENT_CONFIG = load_config()

# Initialize session state from permanent config
def init_session_state_from_config():
    """Initialize session state variables from permanent config"""
    if 'apps_script_url' not in st.session_state:
        st.session_state.apps_script_url = PERMANENT_CONFIG.get('apps_script_url', '')
    
    if 'sheet_config' not in st.session_state:
        st.session_state.sheet_config = PERMANENT_CONFIG.get('sheet_config', {
            'sheet_name': 'Biometric_Device_Monitor',
            'worksheet_name': 'Device_Data',
            'summary_worksheet': 'Summary'
        })
    
    if 'auto_export_enabled' not in st.session_state:
        st.session_state.auto_export_enabled = PERMANENT_CONFIG.get('auto_export_enabled', False)
    
    if 'export_mode' not in st.session_state:
        st.session_state.export_mode = PERMANENT_CONFIG.get('export_mode', 'Replace (Overwrite)')
    
    if 'alerts_config' not in st.session_state:
        st.session_state.alerts_config = PERMANENT_CONFIG.get('alerts_config', {
            'inactive_threshold': 30,
            'email_alerts': False,
            'email_recipient': ''
        })
    
    if 'processing_config' not in st.session_state:
        st.session_state.processing_config = PERMANENT_CONFIG.get('processing_config', {
            'active_days': 2,
            'date_format': 'Auto Detect'
        })
    
    if 'display_config' not in st.session_state:
        st.session_state.display_config = PERMANENT_CONFIG.get('display_config', {
            'theme': 'light',
            'default_view': 'Dashboard',
            'rows_per_page': 50
        })
    
    if 'column_mappings' not in st.session_state:
        st.session_state.column_mappings = PERMANENT_CONFIG.get('column_mappings', {
            'portal_columns': {},
            'master_columns': {}
        })

# Initialize other session state variables
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'summary_data' not in st.session_state:
    st.session_state.summary_data = None
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []
if 'saved_reports' not in st.session_state:
    st.session_state.saved_reports = []
if 'google_sheet_url' not in st.session_state:
    st.session_state.google_sheet_url = ''

# Initialize from permanent config
init_session_state_from_config()

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
    .config-box {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
    }
    .config-saved {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: bold;
    }
    .config-status {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background: #28a745;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# Display config status
config_status = "✅ Config Loaded" if CONFIG_PATH.exists() else "🆕 Default Config"
st.markdown(f'<div class="config-status">{config_status} | Config: {CONFIG_PATH}</div>', unsafe_allow_html=True)

# ==================== IMAGE EXPORT FUNCTIONALITY ====================

def dataframe_to_image(df, title="Data Report", col_widths=None, font_size=10, 
                       header_color='#667eea', row_colors=['#ffffff', '#f8f9fa'],
                       max_rows=100, include_index=False, sort_by=None, sort_ascending=True,
                       filters=None):
    """Convert dataframe to matplotlib figure with customizable styling"""
    
    # Apply filters if provided
    filtered_df = df.copy()
    if filters:
        for column, filter_value in filters.items():
            if filter_value and column in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(filter_value, case=False, na=False)]
    
    # Apply sorting if provided
    if sort_by and sort_by in filtered_df.columns:
        filtered_df = filtered_df.sort_values(by=sort_by, ascending=sort_ascending)
    
    # Limit rows
    if len(filtered_df) > max_rows:
        filtered_df = filtered_df.head(max_rows)
        st.warning(f"⚠️ Showing only first {max_rows} rows in image export")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, min(30, len(filtered_df) * 0.3 + 2)))
    ax.axis('tight')
    ax.axis('off')
    
    # Prepare table data
    if include_index:
        table_data = filtered_df.reset_index()
        columns = ['Index'] + list(filtered_df.columns)
    else:
        table_data = filtered_df
        columns = list(filtered_df.columns)
    
    # Create table
    table = ax.table(cellText=table_data.values, colLabels=columns, 
                     cellLoc='center', loc='center',
                     colWidths=col_widths or [0.08] * len(columns))
    
    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1.2, 1.5)
    
    # Color header row
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_facecolor(header_color)
            cell.set_text_props(weight='bold', color='white')
        else:
            # Alternate row colors
            cell.set_facecolor(row_colors[i % 2])
    
    # Add title
    ax.set_title(title, fontsize=16, weight='bold', pad=20)
    
    plt.tight_layout()
    return fig

def export_table_as_image(df, title, format='png', dpi=300, **kwargs):
    """Export dataframe as image with various formats"""
    fig = dataframe_to_image(df, title, **kwargs)
    
    # Save to bytes buffer
    buf = io.BytesIO()
    fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def create_image_download_button(df, table_name, **kwargs):
    """Create download button for table image export"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        image_format = st.selectbox(
            f"Format for {table_name}",
            ['PNG', 'JPEG', 'PDF'],
            key=f"format_{table_name}"
        )
    
    with col2:
        dpi_value = st.selectbox(
            f"DPI for {table_name}",
            [150, 300, 600],
            index=1,
            key=f"dpi_{table_name}"
        )
    
    with col3:
        max_rows_img = st.number_input(
            f"Max rows for {table_name}",
            min_value=10, max_value=500, value=100,
            key=f"rows_{table_name}"
        )
    
    with st.expander(f"⚙️ Customize {table_name} Image Export"):
        col_a, col_b = st.columns(2)
        
        with col_a:
            sort_column = st.selectbox(
                "Sort by column",
                ['None'] + list(df.columns),
                key=f"sort_col_{table_name}"
            )
            sort_ascending = st.checkbox("Ascending order", True, key=f"sort_asc_{table_name}")
            
            include_index = st.checkbox("Include index column", False, key=f"index_{table_name}")
            
            header_color = st.color_picker("Header color", '#667eea', key=f"header_{table_name}")
        
        with col_b:
            font_size = st.slider("Font size", 6, 14, 10, key=f"font_{table_name}")
            
            # Row color pickers
            row_color1 = st.color_picker("Row color 1", '#ffffff', key=f"row1_{table_name}")
            row_color2 = st.color_picker("Row color 2", '#f8f9fa', key=f"row2_{table_name}")
    
    # Filter options
    with st.expander(f"🔍 Filter {table_name} Data"):
        filters = {}
        filter_cols = st.multiselect(
            "Select columns to filter",
            df.columns.tolist(),
            key=f"filter_cols_{table_name}"
        )
        
        for col in filter_cols:
            filter_val = st.text_input(f"Filter {col} (contains)", key=f"filter_{table_name}_{col}")
            if filter_val:
                filters[col] = filter_val
    
    if st.button(f"📸 Export {table_name} as Image", key=f"export_img_{table_name}"):
        with st.spinner(f"Generating {table_name} image..."):
            sort_by = sort_column if sort_column != 'None' else None
            
            img_buf = export_table_as_image(
                df,
                title=f"{table_name} - Generated on {datetime.now().strftime('%Y-%m-%d ')}",
                format=image_format.lower(),
                dpi=dpi_value,
                font_size=font_size,
                header_color=header_color,
                row_colors=[row_color1, row_color2],
                max_rows=max_rows_img,
                include_index=include_index,
                sort_by=sort_by,
                sort_ascending=sort_ascending,
                filters=filters if filters else None
            )
            
            # Create download button
            file_ext = 'png' if image_format.lower() == 'png' else 'jpg' if image_format.lower() == 'jpeg' else 'pdf'
            b64_img = base64.b64encode(img_buf.getvalue()).decode()
            href = f'<a href="data:image/{file_ext};base64,{b64_img}" download="biometric_{table_name.lower().replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{file_ext}">📥 Download {table_name} Image</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success(f"✅ {table_name} image ready for download!")

# ==================== FIXED JSON CLEANING FOR STREAMLIT CLOUD ====================

def clean_data_for_json(df):
    """Replace NaN, NaT, and infinite values with empty strings for JSON serialization"""
    # Convert to list of dictionaries manually to handle all edge cases
    records = []
    
    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            val = row[col]
            
            # Handle different types of invalid values
            if val is None:
                record[col] = ""
            elif pd.isna(val):  # Catches NaN, NaT, None
                record[col] = ""
            elif isinstance(val, (np.datetime64, pd.Timestamp)):
                # Convert datetime to string
                record[col] = val.strftime('%Y-%m-%d ') if pd.notna(val) else ""
            elif isinstance(val, (np.floating, float)):
                # Handle float values (including inf)
                if np.isnan(val) or np.isinf(val):
                    record[col] = ""
                else:
                    record[col] = val
            elif isinstance(val, (np.integer, int)):
                record[col] = int(val) if pd.notna(val) else ""
            else:
                # Convert to string and clean up
                str_val = str(val)
                if str_val in ['nan', 'NaN', 'NaT', 'None', '<NA>', '']:
                    record[col] = ""
                else:
                    record[col] = str_val
        
        records.append(record)
    
    return records

# ==================== GOOGLE APPS SCRIPT INTEGRATION ====================

def export_to_google_sheets_apps_script(df, sheet_name="Biometric_Data", worksheet_name="Device_Data", apps_script_url=None, export_mode="Replace"):
    """Export dataframe to Google Sheets using Apps Script web app"""
    try:
        if not apps_script_url:
            return False, "Apps Script URL not configured"
        
        # Clean the data for JSON serialization
        cleaned_records = clean_data_for_json(df)
        
        # Determine action based on export mode
        action = 'append' if export_mode == "Append (Add rows)" else 'export'
        
        # Prepare data payload
        data = {
            'action': action,
            'sheetName': sheet_name,
            'worksheetName': worksheet_name,
            'data': cleaned_records,
            'columns': df.columns.tolist(),
            'timestamp': datetime.now().strftime("%Y-%m-%d ")
        }
        
        # Send to Apps Script with increased timeout for cloud environment
        response = requests.post(
            apps_script_url, 
            json=data, 
            headers={'Content-Type': 'application/json'}, 
            timeout=60
        )
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('success'):
                    return True, result.get('sheetUrl', apps_script_url)
                else:
                    return False, result.get('error', 'Unknown error')
            except json.JSONDecodeError:
                return False, f"Invalid JSON response: {response.text[:200]}"
        else:
            return False, f"HTTP Error: {response.status_code} - {response.text[:200]}"
            
    except requests.exceptions.Timeout:
        return False, "Request timeout - the Google Sheets service might be slow. Please try again."
    except requests.exceptions.ConnectionError:
        return False, "Connection error - cannot reach the Apps Script URL. Check your URL and internet connection."
    except Exception as e:
        return False, f"Export error: {str(e)}"

def test_apps_script_connection(apps_script_url):
    """Test connection to Apps Script web app"""
    try:
        data = {
            'action': 'test', 
            'timestamp': datetime.now().strftime("%Y-%m-%d")
        }
        response = requests.post(
            apps_script_url, 
            json=data, 
            headers={'Content-Type': 'application/json'}, 
            timeout=15
        )
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('success'):
                    return True, "Connection successful!"
                else:
                    return False, result.get('error', 'Connection failed')
            except json.JSONDecodeError:
                return False, f"Invalid response from server. Response: {response.text[:100]}"
        else:
            return False, f"HTTP Error: {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Connection timeout - check your URL and internet connection"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to the Apps Script URL. Please verify the URL is correct and the script is deployed."
    except Exception as e:
        return False, f"Connection error: {str(e)}"

def debug_json_serialization(df):
    """Debug function to check JSON serialization"""
    try:
        records = clean_data_for_json(df)
        # Test serialization
        test_json = json.dumps(records[:5])  # Test first 5 records
        st.success(f"✅ JSON serialization test passed! First 5 records: {len(test_json)} chars")
        return True
    except Exception as e:
        st.error(f"❌ JSON serialization failed: {e}")
        # Find problematic row
        for idx, row in df.iterrows():
            try:
                record = {}
                for col in df.columns:
                    val = row[col]
                    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                        st.write(f"Problem at row {idx}, col {col}: {val}")
                json.dumps(record)
            except:
                st.write(f"Problem row index: {idx}")
                break
        return False

# Title
st.markdown('<div class="main-header">🏢 Biometric Device Monitoring System PRO</div>', unsafe_allow_html=True)
st.markdown("---")

# ==================== PERMANENT CONFIGURATION SECTION ====================
with st.expander("⚙️ **System Configuration** (Settings are saved permanently)", expanded=False):
    st.markdown('<div class="config-box">', unsafe_allow_html=True)
    
    st.markdown("### 🔧 Permanent Configuration Settings")
    st.info(f"📁 Configuration saved at: `{CONFIG_PATH}`")
    
    config_tab1, config_tab2, config_tab3, config_tab4, config_tab5 = st.tabs([
        "📊 Google Sheets", "🔧 Processing", "📧 Alerts", "🎨 Display", "💾 Backup/Restore"
    ])
    
    # Tab 1: Google Sheets Configuration
    with config_tab1:
        st.markdown("#### 📊 Google Sheets Integration")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            apps_script_url_input = st.text_input(
                "Apps Script Web App URL",
                value=st.session_state.apps_script_url,
                placeholder="https://script.google.com/macros/s/.../exec",
                help="Paste the URL from your deployed Apps Script web app",
                key="config_apps_script_url"
            )
        
        with col2:
            if st.button("🔗 Test Connection", use_container_width=True, key="test_conn"):
                if apps_script_url_input:
                    with st.spinner("Testing connection..."):
                        success, message = test_apps_script_connection(apps_script_url_input)
                        if success:
                            st.success("✅ Connected!")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.warning("Enter URL first")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            sheet_name = st.text_input("Spreadsheet Name", 
                                       value=st.session_state.sheet_config['sheet_name'],
                                       key="config_sheet_name")
        with col2:
            worksheet_name = st.text_input("Data Worksheet", 
                                          value=st.session_state.sheet_config['worksheet_name'],
                                          key="config_worksheet_name")
        with col3:
            summary_worksheet = st.text_input("Summary Worksheet", 
                                             value=st.session_state.sheet_config['summary_worksheet'],
                                             key="config_summary_worksheet")
        
        export_mode = st.radio("Export Mode", 
                              ["Replace (Overwrite)", "Append (Add rows)"],
                              index=0 if st.session_state.export_mode == "Replace (Overwrite)" else 1,
                              horizontal=True,
                              key="config_export_mode")
        
        auto_export = st.checkbox("Auto-export after processing", 
                                  value=st.session_state.auto_export_enabled,
                                  key="config_auto_export")
        
        # Quick setup guide
        with st.expander("📋 **Quick Setup Guide**", expanded=False):
            st.markdown("""
            **3 Simple Steps:**
            
            1. **Create Apps Script:**
               - Open [Google Sheets](https://sheets.new)
               - Extensions → Apps Script
               - Paste the code below
               - Deploy as Web App
            
            2. **Get Web App URL:**
               - Click Deploy → New Deployment
               - Choose "Web app"
               - Execute as: "Me"
               - Who has access: "Anyone"
               - Copy the URL
            
            3. **Paste URL Above:**
               - Paste the URL in the field
               - Click "Test Connection"
               - Save Configuration (button at bottom)
            """)
            
            st.code('''
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(data.worksheetName) || 
                ss.insertSheet(data.worksheetName);
    
    if (data.action === "test") {
      return ContentService.createTextOutput(
        JSON.stringify({success: true})
      ).setMimeType(ContentService.MimeType.JSON);
    }
    
    if (data.action === "export") {
      sheet.clear();
      const headers = data.columns;
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      
      const rows = data.data.map(row => 
        headers.map(h => row[h] !== null && row[h] !== "" ? row[h] : ""));
      if (rows.length > 0) {
        sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
      }
      
      sheet.getRange(1, 1, 1, headers.length)
        .setFontWeight("bold").setBackground("#667eea").setFontColor("white");
      sheet.autoResizeColumns(1, headers.length);
      
      return ContentService.createTextOutput(
        JSON.stringify({success: true, sheetUrl: ss.getUrl()})
      ).setMimeType(ContentService.MimeType.JSON);
    }
    
    if (data.action === "append") {
      const lastRow = sheet.getLastRow();
      let headers;
      
      if (lastRow === 0) {
        headers = data.columns;
        sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
        sheet.getRange(1, 1, 1, headers.length)
          .setFontWeight("bold").setBackground("#667eea").setFontColor("white");
      } else {
        headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
      }
      
      const rows = data.data.map(row => 
        headers.map(h => row[h] !== null && row[h] !== "" ? row[h] : ""));
      
      if (rows.length > 0) {
        sheet.getRange(lastRow + 1, 1, rows.length, headers.length).setValues(rows);
      }
      
      return ContentService.createTextOutput(
        JSON.stringify({success: true, sheetUrl: ss.getUrl()})
      ).setMimeType(ContentService.MimeType.JSON);
    }
  } catch(error) {
    return ContentService.createTextOutput(
      JSON.stringify({success: false, error: error.toString()})
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(
    JSON.stringify({success: true, message: "Apps Script is running"})
  ).setMimeType(ContentService.MimeType.JSON);
}
            ''', language='javascript')
    
    # Tab 2: Processing Configuration
    with config_tab2:
        st.markdown("#### 🔧 Processing Settings")
        
        active_days = st.number_input("Active Days Threshold", 
                                      min_value=1, max_value=30, 
                                      value=st.session_state.processing_config.get('active_days', 2),
                                      help="Devices active within this many days are marked as 'Active'",
                                      key="config_active_days")
        
        date_format = st.selectbox("Date Format in Excel", 
                                  ["Auto Detect", "YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"],
                                  index=["Auto Detect", "YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"].index(
                                      st.session_state.processing_config.get('date_format', 'Auto Detect')
                                  ),
                                  key="config_date_format")
        
        st.markdown("#### 📋 Status Rules")
        st.info(f"""
        **Current Rules:**
        - Ward NULL → Status = Zone/Area value
        - Days ≤ {active_days} & Zone ≠ 'Not Authorized' → ✅ Active  
        - Days > {active_days} & Zone ≠ 'Not Authorized' → ⚠️ Inactive
        - Zone/Area = 'Not Authorized' → Not authorized
        """)
        
        st.markdown("#### 📁 Column Mappings (Advanced)")
        with st.expander("Customize Column Mappings", expanded=False):
            st.markdown("**Device Export File Columns:**")
            portal_cols = st.text_area("Portal columns (JSON format)", 
                                       value=json.dumps(st.session_state.column_mappings.get('portal_columns', {}), indent=2),
                                       height=100,
                                       key="config_portal_cols")
            
            st.markdown("**Master File Columns:**")
            master_cols = st.text_area("Master columns (JSON format)", 
                                       value=json.dumps(st.session_state.column_mappings.get('master_columns', {}), indent=2),
                                       height=100,
                                       key="config_master_cols")
    
    # Tab 3: Alerts Configuration
    with config_tab3:
        st.markdown("#### 📧 Alert Settings")
        
        inactive_threshold = st.slider(
            "Inactive Alert Threshold (days)", 
            min_value=7, max_value=90, 
            value=st.session_state.alerts_config.get('inactive_threshold', 30),
            key="config_inactive_threshold"
        )
        
        email_alerts = st.checkbox(
            "Enable Email Alerts", 
            value=st.session_state.alerts_config.get('email_alerts', False),
            key="config_email_alerts"
        )
        
        email_recipient = ""
        if email_alerts:
            email_recipient = st.text_input(
                "Alert Email Address",
                value=st.session_state.alerts_config.get('email_recipient', ''),
                key="config_email_recipient"
            )
        
        st.markdown("#### 🔔 Alert Conditions")
        st.markdown(f"""
        - **Inactive Alert**: Triggered when devices are inactive for more than **{inactive_threshold} days**
        - **Email Notifications**: {'✅ Enabled' if email_alerts else '❌ Disabled'}
        """)
    
    # Tab 4: Display Configuration
    with config_tab4:
        st.markdown("#### 🎨 Display Settings")
        
        theme = st.selectbox("Theme", 
                            ["Light", "Dark"],
                            index=0 if st.session_state.display_config.get('theme', 'light') == 'light' else 1,
                            key="config_theme")
        
        default_view = st.selectbox("Default View", 
                                   ["Dashboard", "Device Data", "Analytics", "History"],
                                   index=["Dashboard", "Device Data", "Analytics", "History"].index(
                                       st.session_state.display_config.get('default_view', 'Dashboard')
                                   ),
                                   key="config_default_view")
        
        rows_per_page = st.number_input("Rows per page", 
                                       min_value=10, max_value=500, 
                                       value=st.session_state.display_config.get('rows_per_page', 50),
                                       step=10,
                                       key="config_rows_per_page")
    
    # Tab 5: Backup/Restore
    with config_tab5:
        st.markdown("#### 💾 Configuration Backup & Restore")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Export Configuration**")
            if st.button("📤 Export Config to File", use_container_width=True):
                href = export_config_to_file()
                st.markdown(href, unsafe_allow_html=True)
                st.success("Click the link above to download your configuration file")
        
        with col2:
            st.markdown("**Import Configuration**")
            uploaded_config = st.file_uploader("Upload config file", type=['json'], key="config_upload")
            if uploaded_config is not None:
                if st.button("📥 Import Configuration", use_container_width=True):
                    success, result = import_config_from_file(uploaded_config)
                    if success:
                        st.success("✅ Configuration imported successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result}")
        
        st.markdown("---")
        st.markdown("**Reset Configuration**")
        if st.button("🔄 Reset to Default Settings", use_container_width=True, type="secondary"):
            if reset_config_to_default():
                st.success("✅ Configuration reset to defaults!")
                st.rerun()
    
    # Save Configuration Button
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("💾 **SAVE ALL CONFIGURATION**", type="primary", use_container_width=True):
            # Build config dictionary
            new_config = {
                'apps_script_url': apps_script_url_input,
                'sheet_config': {
                    'sheet_name': sheet_name,
                    'worksheet_name': worksheet_name,
                    'summary_worksheet': summary_worksheet
                },
                'auto_export_enabled': auto_export,
                'export_mode': export_mode,
                'alerts_config': {
                    'inactive_threshold': inactive_threshold,
                    'email_alerts': email_alerts,
                    'email_recipient': email_recipient if email_alerts else ''
                },
                'processing_config': {
                    'active_days': active_days,
                    'date_format': date_format
                },
                'display_config': {
                    'theme': theme.lower(),
                    'default_view': default_view,
                    'rows_per_page': rows_per_page
                },
                'column_mappings': {
                    'portal_columns': json.loads(portal_cols) if portal_cols else {},
                    'master_columns': json.loads(master_cols) if master_cols else {}
                }
            }
            
            # Save to file
            if save_config(new_config):
                # Update session state
                st.session_state.apps_script_url = new_config['apps_script_url']
                st.session_state.sheet_config = new_config['sheet_config']
                st.session_state.auto_export_enabled = new_config['auto_export_enabled']
                st.session_state.export_mode = new_config['export_mode']
                st.session_state.alerts_config = new_config['alerts_config']
                st.session_state.processing_config = new_config['processing_config']
                st.session_state.display_config = new_config['display_config']
                st.session_state.column_mappings = new_config['column_mappings']
                
                st.success("✅ Configuration saved permanently!")
                st.balloons()
                st.info(f"Configuration saved to: `{CONFIG_PATH}`")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("📁 Data Upload")
    
    portal_file = st.file_uploader(
        "**Device Export File** (Excel)",
        type=['xlsx', 'xls'],
        help="Columns: Serial Number, Device Name, Area, Device IP, Last Activity"
    )
    
    master_file = st.file_uploader(
        "**Biometric Master File** (Excel)",
        type=['xlsx', 'xls'],
        help="Columns: Serial Number, Bio Metric Type, Zone, Ward, Device Name, Near Facility"
    )
    
    st.markdown("---")
    
    process_button = st.button("🚀 **Process Data**", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    # Export Section
    if st.session_state.processed_data is not None:
        st.header("📥 Quick Export")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 CSV", use_container_width=True):
                csv = st.session_state.processed_data.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="biometric_report.csv">Download CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
        
        with col2:
            if st.button("📊 Excel", use_container_width=True):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    st.session_state.processed_data.to_excel(writer, sheet_name='Processed Data', index=False)
                    if st.session_state.summary_data is not None:
                        st.session_state.summary_data.to_excel(writer, sheet_name='Summary', index=False)
                excel_data = output.getvalue()
                b64 = base64.b64encode(excel_data).decode()
                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="biometric_report.xlsx">Download Excel</a>'
                st.markdown(href, unsafe_allow_html=True)
        
        # Quick Google Sheets Export
        if st.session_state.apps_script_url:
            if st.button("📤 Export to Google Sheets", use_container_width=True):
                # Debug serialization first (optional, can be removed in production)
                with st.spinner("Exporting to Google Sheets..."):
                    success, result = export_to_google_sheets_apps_script(
                        st.session_state.processed_data,
                        st.session_state.sheet_config['sheet_name'],
                        st.session_state.sheet_config['worksheet_name'],
                        st.session_state.apps_script_url,
                        st.session_state.export_mode
                    )
                    if success:
                        st.session_state.google_sheet_url = result
                        st.success("✅ Exported successfully!")
                        st.markdown(f"[📊 Open Google Sheet]({result})")
                    else:
                        st.error(f"❌ Export failed: {result}")

# ==================== DATA PROCESSING FUNCTION ====================

def process_biometric_data(portal_file, master_file, active_threshold=2):
    try:
        # Load files
        portal_df = pd.read_excel(portal_file)
        try:
            master_df = pd.read_excel(master_file, sheet_name="Master")
        except:
            master_df = pd.read_excel(master_file)
        
        # Display actual columns found
        with st.expander("🔍 Column Debug Information", expanded=False):
            st.markdown("**Device Export File Columns Found:**")
            st.write(list(portal_df.columns))
            st.markdown("**Biometric Master File Columns Found:**")
            st.write(list(master_df.columns))
        
        # Rename columns to standard names for processing
        portal_column_map = {}
        for col in portal_df.columns:
            if col == 'Serial Number':
                portal_column_map[col] = 'Serial Number'
            elif col == 'Device Name':
                portal_column_map[col] = 'Device Name'
            elif col == 'Area':
                portal_column_map[col] = 'Area'
            elif col == 'Device IP':
                portal_column_map[col] = 'Device IP'
            elif col == 'Last Activity':
                portal_column_map[col] = 'Last Activity'
        
        master_column_map = {}
        for col in master_df.columns:
            if col == 'Serial Number':
                master_column_map[col] = 'Serial Number'
            elif col == 'Bio Metric Type':
                master_column_map[col] = 'Bio Metric Type'
            elif col == 'Zone':
                master_column_map[col] = 'Zone'
            elif col == 'Ward':
                master_column_map[col] = 'Ward'
            elif col == 'Device Name':
                master_column_map[col] = 'Device Name Master'
            elif col == 'Near Facility':
                master_column_map[col] = 'Near Facility'
        
        # Apply renaming
        portal_df = portal_df.rename(columns=portal_column_map)
        master_df = master_df.rename(columns=master_column_map)
        
        # Check for required columns
        required_portal = ['Serial Number', 'Last Activity']
        required_master = ['Serial Number']
        
        missing_portal = [col for col in required_portal if col not in portal_df.columns]
        missing_master = [col for col in required_master if col not in master_df.columns]
        
        if missing_portal:
            st.error(f"❌ Missing columns in Device Export file: {missing_portal}")
            return None, None
        if missing_master:
            st.error(f"❌ Missing columns in Master file: {missing_master}")
            return None, None
        
        # Ensure Serial Number is string for proper merging
        portal_df['Serial Number'] = portal_df['Serial Number'].astype(str).str.strip()
        master_df['Serial Number'] = master_df['Serial Number'].astype(str).str.strip()
        
        # Merge dataframes
        merged = master_df.merge(portal_df, on="Serial Number", how="left")
        
        # Process dates
        merged['Last Activity Date'] = pd.to_datetime(merged['Last Activity'], errors='coerce').dt.normalize()
        
        # Calculate days inactive
        max_date = merged['Last Activity Date'].max()
        if pd.isna(max_date):
            merged['Days Inactive'] = 0
        else:
            merged['Days Inactive'] = (max_date - merged['Last Activity Date']).dt.days
            merged['Days Inactive'] = merged['Days Inactive'].fillna(0)
        
        # Fill missing values
        if 'Device Name Master' in merged.columns:
            merged['Device Name'] = merged['Device Name Master'].fillna('Not Available')
        elif 'Device Name' in merged.columns:
            merged['Device Name'] = merged['Device Name'].fillna('Not Available')
        else:
            merged['Device Name'] = 'Not Available'
        
        if 'Device IP' not in merged.columns:
            merged['Device IP'] = 'Not Available'
        else:
            merged['Device IP'] = merged['Device IP'].fillna('Not Available')
        
        if 'Bio Metric Type' not in merged.columns:
            merged['Bio Metric Type'] = 'Not Available'
        else:
            merged['Bio Metric Type'] = merged['Bio Metric Type'].fillna('Not Available')
        
        if 'Near Facility' not in merged.columns:
            merged['Near Facility'] = 'Not Available'
        else:
            merged['Near Facility'] = merged['Near Facility'].fillna('Not Available')
        
        if 'Zone' in merged.columns:
            merged['Area'] = merged['Zone'].fillna('Not Available')
        elif 'Area' in merged.columns:
            merged['Area'] = merged['Area'].fillna('Not Available')
        else:
            merged['Area'] = 'Not Available'
        
        if 'Ward' not in merged.columns:
            merged['Ward'] = 'Not Available'
        else:
            merged['Ward'] = merged['Ward'].fillna('Not Available')
        
        # Replace empty strings and NaN with 'Not Available'
        for col in ['Device Name', 'Device IP', 'Bio Metric Type', 'Near Facility', 'Area', 'Ward']:
            if col in merged.columns:
                merged[col] = merged[col].replace(['', 'nan', 'NaN', 'None', ' '], 'Not Available')
        
        # Determine status
        def determine_status(row):
            ward = str(row.get('Ward', '')).strip()
            ward_null = ward in ['', 'Not Available', 'nan', 'NaN', 'None']
            
            if ward_null:
                ward_val = row.get('Ward', 'Unknown')
                return str(ward_val) if ward_val != 'Not Available' else 'Unknown'
            
            area = str(row.get('Area', '')).strip()
            days = row.get('Days Inactive', 0)
            
            if area == 'Not Authorized':
                return 'Not authorized'
            elif days <= active_threshold:
                return '✅ Active'
            else:
                return '⚠️ Inactive'
        
        merged['Status'] = merged.apply(determine_status, axis=1)
        
        # Create summary
        summary = merged['Status'].value_counts().reset_index()
        summary.columns = ['Status', 'Count']
        summary['Percentage'] = (summary['Count'] / summary['Count'].sum() * 100).round(1)
        
        # Define display columns
        display_cols = ['Serial Number', 'Near Facility', 'Device Name', 'Device IP', 'Area', 'Ward', 'Bio Metric Type', 'Days Inactive', 'Status', 'Last Activity']
        
        for col in display_cols:
            if col not in merged.columns:
                merged[col] = 'Not Available'
        
        result_df = merged[display_cols].copy()
        
        # Sort by status
        status_order = {'✅ Active': 0, '⚠️ Inactive': 1, 'Not authorized': 2}
        result_df['Status Order'] = result_df['Status'].map(status_order).fillna(3)
        result_df = result_df.sort_values('Status Order').drop('Status Order', axis=1)
        
        # Add processed timestamp
        result_df['Processed'] = datetime.now().strftime("%Y-%m-%d ")
        
        st.success(f"✅ Processing complete! Found {len(result_df)} devices")
        
        return result_df, summary
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None, None

# Process button
if process_button:
    if portal_file is None or master_file is None:
        st.warning("⚠️ Please upload both files!")
    else:
        with st.spinner("🔄 Processing..."):
            active_days_val = st.session_state.processing_config.get('active_days', 2)
            processed_df, summary_df = process_biometric_data(portal_file, master_file, active_days_val)
            
            if processed_df is not None:
                st.session_state.processed_data = processed_df
                st.session_state.summary_data = summary_df
                
                st.session_state.processing_history.append({
                    'timestamp': datetime.now(),
                    'total_devices': len(processed_df),
                    'file_name': portal_file.name,
                    'active_count': len(processed_df[processed_df['Status'] == '✅ Active']),
                    'inactive_count': len(processed_df[processed_df['Status'] == '⚠️ Inactive']),
                    'blocked_count': len(processed_df[processed_df['Status'] == 'Not authorized'])
                })
                
                # Auto-export to Google Sheets if enabled
                if st.session_state.auto_export_enabled and st.session_state.apps_script_url:
                    with st.spinner("Auto-exporting to Google Sheets..."):
                        success, result = export_to_google_sheets_apps_script(
                            processed_df,
                            st.session_state.sheet_config['sheet_name'],
                            st.session_state.sheet_config['worksheet_name'],
                            st.session_state.apps_script_url,
                            st.session_state.export_mode
                        )
                        if success:
                            st.session_state.google_sheet_url = result
                            st.success("✅ Auto-exported to Google Sheets!")
                        else:
                            st.warning(f"⚠️ Auto-export failed: {result}")
                
                # Alert check
                inactive_devices = processed_df[processed_df['Status'] == '⚠️ Inactive']
                long_inactive = inactive_devices[inactive_devices['Days Inactive'] > st.session_state.alerts_config['inactive_threshold']]
                
                if len(long_inactive) > 0:
                    st.warning(f"⚠️ Alert: {len(long_inactive)} devices inactive > {st.session_state.alerts_config['inactive_threshold']} days!")
                
                st.success("✅ Processing complete!")
                st.balloons()

# Main content tabs
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data
    summary = st.session_state.summary_data
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "📋 Device Data", "📈 Analytics", "📜 History", "💾 Saved Reports"])
    
    # Tab 1: Dashboard
    with tab1:
        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_devices = len(df)
            st.metric("📊 Total Devices", total_devices)
        
        with col2:
            active_count = len(df[df['Status'] == '✅ Active'])
            active_pct = (active_count/total_devices*100) if total_devices > 0 else 0
            st.metric("✅ Active", f"{active_count}", delta=f"{active_pct:.1f}%")
        
        with col3:
            inactive_count = len(df[df['Status'] == '⚠️ Inactive'])
            inactive_pct = (inactive_count/total_devices*100) if total_devices > 0 else 0
            st.metric("⚠️ Inactive", f"{inactive_count}", delta=f"{inactive_pct:.1f}%", delta_color="inverse")
        
        with col4:
            not_authorized_count = len(df[df['Status'] == 'Not authorized'])
            not_authorized_pct = (not_authorized_count/total_devices*100) if total_devices > 0 else 0
            st.metric("❌ Not authorized", f"{not_authorized_count}", delta=f"{not_authorized_pct:.1f}%")
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Status Distribution")
            fig1 = px.pie(summary, values='Count', names='Status', hole=0.3, 
                          color_discrete_sequence=['#2ecc71', '#e74c3c', '#95a5a6'])
            fig1.update_traces(textposition='inside', textinfo='percent+label')
            fig1.update_layout(height=400)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.subheader("Inactive Days Distribution")
            df['Days Group'] = pd.cut(df['Days Inactive'], bins=[-1, 0, 2, 7, 30, 90, float('inf')],
                                       labels=['0', '1-2', '3-7', '8-30', '31-90', '90+'])
            days_dist = df['Days Group'].value_counts().reset_index()
            days_dist.columns = ['Days', 'Count']
            fig2 = px.bar(days_dist, x='Days', y='Count', title='Devices by Inactive Days',
                          color='Count', color_continuous_scale='Viridis')
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Additional metrics
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_inactive = df['Days Inactive'].mean()
            st.metric("📊 Avg Inactive Days", f"{avg_inactive:.1f}")
        with col2:
            max_inactive = df['Days Inactive'].max()
            st.metric("⚠️ Max Inactive Days", f"{max_inactive}")
        with col3:
            compliance_rate = (active_count / total_devices * 100) if total_devices > 0 else 0
            st.metric("✅ Compliance Rate", f"{compliance_rate:.1f}%")
        
        # Dashboard Table Export
        st.markdown("---")
        st.subheader("📸 Export Dashboard Data as Image")
        
        # Create summary table for dashboard export
        dashboard_summary = pd.DataFrame({
            'Metric': ['Total Devices', 'Active Devices', 'Inactive Devices', 'Not Authorized Devices',
                      'Compliance Rate', 'Average Inactive Days', 'Max Inactive Days'],
            'Value': [total_devices, active_count, inactive_count, not_authorized_count,
                     f"{compliance_rate:.1f}%", f"{avg_inactive:.1f}", max_inactive]
        })
        
        create_image_download_button(dashboard_summary, "Dashboard Summary", max_rows_img=50)
    
    # Tab 2: Device Data
    with tab2:
        st.subheader("Detailed Device Data")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect("Filter by Status", options=df['Status'].unique(), 
                                           default=df['Status'].unique())
        with col2:
            if 'Area' in df.columns:
                area_options = [x for x in df['Area'].unique() if x not in ['Not Available', 'Unknown']]
                if area_options:
                    area_filter = st.multiselect("Filter by Area/Zone", options=area_options, default=area_options)
                else:
                    area_filter = []
            else:
                area_filter = []
        with col3:
            search = st.text_input("🔍 Search Serial Number", placeholder="Enter serial...")
        
        # Apply filters
        filtered_df = df[df['Status'].isin(status_filter)]
        if area_filter:
            filtered_df = filtered_df[filtered_df['Area'].isin(area_filter)]
        if search:
            filtered_df = filtered_df[filtered_df['Serial Number'].astype(str).str.contains(search, case=False)]
        
        # Color coding
        def color_status(val):
            if '✅' in str(val):
                return 'background-color: #90EE90'
            elif '⚠️' in str(val):
                return 'background-color: #FFB6C1'
            elif 'Not authorized' in str(val):
                return 'background-color: #D3D3D3'
            return ''
        
        styled_df = filtered_df.style.map(color_status, subset=['Status'])
        st.dataframe(styled_df, use_container_width=True, height=500)
        st.caption(f"Showing {len(filtered_df)} of {len(df)} records")
        
        # Export filtered data as image
        st.markdown("---")
        st.subheader("📸 Export Filtered Device Data as Image")
        create_image_download_button(filtered_df, "Filtered Device Data", max_rows_img=200)
        
        # Top inactive devices
        st.markdown("---")
        st.subheader("⚠️ Top Inactive Devices")
        
        inactive_only_df = df[df['Status'] == '⚠️ Inactive']
        
        if len(inactive_only_df) > 0:
            top_inactive = inactive_only_df.nlargest(100, 'Days Inactive')[['Serial Number', 'Device Name', 'Near Facility', 'Area', 'Device IP', 'Days Inactive', 'Status']]
            st.dataframe(top_inactive, use_container_width=True)
            
            # Export top inactive as image
            st.markdown("---")
            st.subheader("📸 Export Top Inactive Devices as Image")
            create_image_download_button(top_inactive, "Top Inactive Devices", max_rows_img=100)
        else:
            st.info("No inactive devices found!")
    
    # Tab 3: Analytics
    with tab3:
        st.subheader("Advanced Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Status by Near Facility")
            if 'Near Facility' in df.columns and len(df['Near Facility'].unique()) > 1:
                plot_df = df[df['Near Facility'] != 'Not Available']
                if len(plot_df) > 0:
                    area_status = pd.crosstab(plot_df['Near Facility'], plot_df['Status'])
                    fig3 = px.imshow(area_status, text_auto=True, aspect="auto", 
                                     title="Heatmap: Status by Near Facility", color_continuous_scale='Viridis')
                    fig3.update_layout(height=500)
                    st.plotly_chart(fig3, use_container_width=True)
                    
                    # Export crosstab data as image
                    st.markdown("---")
                    st.subheader("📸 Export Status by Near Facility Table")
                    create_image_download_button(area_status.reset_index(), "Status_by_Near_Facility")
        
        with col2:
            st.markdown("#### Status by Bio Metric Type")
            if 'Bio Metric Type' in df.columns and len(df['Bio Metric Type'].unique()) > 1:
                plot_df = df[df['Bio Metric Type'] != 'Not Available']
                if len(plot_df) > 0:
                    bio_status = pd.crosstab(plot_df['Bio Metric Type'], plot_df['Status'])
                    fig4 = px.bar(bio_status, title='Status Distribution by Bio Metric Type', barmode='group')
                    fig4.update_layout(height=500)
                    st.plotly_chart(fig4, use_container_width=True)
                    
                    # Export crosstab data as image
                    st.markdown("---")
                    st.subheader("📸 Export Status by Bio Metric Type Table")
                    create_image_download_button(bio_status.reset_index(), "Status_by_Bio_Metric")
        
        # Statistics table
        st.markdown("#### Statistical Summary")
        stats_df = pd.DataFrame({
            'Metric': ['Mean Inactive Days', 'Median Inactive Days', 'Std Deviation', 'Min Days', 'Max Days', 'Total Devices'],
            'Value': [
                f"{df['Days Inactive'].mean():.1f}",
                f"{df['Days Inactive'].median():.1f}",
                f"{df['Days Inactive'].std():.1f}",
                f"{df['Days Inactive'].min()}",
                f"{df['Days Inactive'].max()}",
                f"{len(df)}"
            ]
        })
        st.dataframe(stats_df, use_container_width=True)
        
        # Export stats as image
        st.markdown("---")
        st.subheader("📸 Export Statistical Summary as Image")
        create_image_download_button(stats_df, "Statistical_Summary")
    
    # Tab 4: History
    with tab4:
        st.subheader("Processing History")
        if st.session_state.processing_history:
            history_df = pd.DataFrame(st.session_state.processing_history)
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
            history_df = history_df.sort_values('timestamp', ascending=False)
            display_history = history_df[['timestamp', 'file_name', 'total_devices', 'active_count', 'inactive_count', 'blocked_count']].copy()
            display_history.columns = ['Date & Time', 'File Name', 'Total', 'Active', 'Inactive', 'Not authorized']
            st.dataframe(display_history, use_container_width=True)
            
            # Export history as image
            st.markdown("---")
            st.subheader("📸 Export Processing History as Image")
            create_image_download_button(display_history, "Processing_History", max_rows_img=100)
        else:
            st.info("No processing history yet.")
    
    # Tab 5: Saved Reports
    with tab5:
        st.subheader("Saved Reports")
        if st.button("💾 Save Current Report", use_container_width=True):
            report_name = f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.session_state.saved_reports.append({
                'name': report_name,
                'date': datetime.now(),
                'data': st.session_state.processed_data.copy(),
                'summary': st.session_state.summary_data.copy() if st.session_state.summary_data is not None else None
            })
            st.success(f"Report '{report_name}' saved!")
            st.rerun()
        
        if st.session_state.saved_reports:
            for idx, report in enumerate(reversed(st.session_state.saved_reports)):
                with st.expander(f"📄 {report['name']} - {report['date'].strftime('%Y-%m-%d ')}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"📊 Load Report", key=f"load_{idx}"):
                            st.session_state.processed_data = report['data']
                            st.session_state.summary_data = report['summary']
                            st.success("Report loaded!")
                            st.rerun()
                    with col2:
                        if st.button(f"📸 Export as Image", key=f"export_img_{idx}"):
                            create_image_download_button(report['data'], f"Saved_Report_{report['name']}")
                    with col3:
                        if st.button(f"🗑️ Delete Report", key=f"del_{idx}"):
                            st.session_state.saved_reports.pop(len(st.session_state.saved_reports) - 1 - idx)
                            st.rerun()
        else:
            st.info("No saved reports. Click 'Save Current Report' to store the current analysis!")

else:
    # Welcome screen
    st.info(f"""
    ### 👋 Welcome to Biometric Device Monitoring System PRO!
    
    **Configuration Status:** {'✅ Loaded from ' + str(CONFIG_PATH) if CONFIG_PATH.exists() else '🆕 Using default settings'}
    
    **Quick Start:**
    1. Configure settings in the **System Configuration** expander above
    2. Upload both Excel files in the sidebar
    3. Click **Process Data** button
    4. Explore the interactive dashboard!
    
    **New Image Export Features:**
    - 📸 Export any table as PNG/JPEG/PDF
    - 🎨 Customize colors, fonts, and styling
    - 🔍 Apply filters before export
    - 📊 Sort data by any column
    - 🖼️ Export charts as high-quality images
    
    **Features:**
    - ⚙️ **Permanent Configuration**: Settings are saved to `{CONFIG_PATH}`
    - 📊 Google Sheets integration with Apps Script
    - 📈 Interactive dashboard and analytics
    - 💾 Save and load reports
    - 📥 Export to CSV/Excel/Images
    
    **Configuration is automatically saved and persists across refreshes!**
    """)

# Footer
st.markdown("---")
st.markdown(
    f"<p style='text-align: center; color: gray;'>🏢 Biometric Device Monitor PRO | v5.2 (Streamlit Cloud Compatible) | Config: {CONFIG_PATH} | {datetime.now().strftime('%Y-%m-%d ')}</p>",
    unsafe_allow_html=True
)
