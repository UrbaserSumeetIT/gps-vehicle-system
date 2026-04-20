"""
Data Processing Module
"""

import pandas as pd
import streamlit as st
from datetime import datetime

class BiometricDataProcessor:
    def __init__(self, active_threshold=2):
        self.active_threshold = active_threshold
    
    def process_files(self, portal_file, master_file):
        try:
            # Read files
            portal_df = pd.read_excel(portal_file)
            master_df = pd.read_excel(master_file)
            
            # Find serial number columns
            portal_serial = None
            for col in portal_df.columns:
                if 'serial' in str(col).lower() or 's/n' in str(col).lower():
                    portal_serial = col
                    break
            
            master_serial = None
            for col in master_df.columns:
                if 'serial' in str(col).lower() or 's/n' in str(col).lower():
                    master_serial = col
                    break
            
            if portal_serial is None or master_serial is None:
                st.error("Could not find Serial Number columns")
                return None, None
            
            # Find activity column
            activity_col = None
            for col in portal_df.columns:
                if 'activity' in str(col).lower() or 'last' in str(col).lower():
                    activity_col = col
                    break
            
            # Rename columns
            portal_df = portal_df.rename(columns={portal_serial: 'Serial Number'})
            master_df = master_df.rename(columns={master_serial: 'Serial Number'})
            
            if activity_col:
                portal_df = portal_df.rename(columns={activity_col: 'Last Activity'})
            
            # Merge
            portal_df['Serial Number'] = portal_df['Serial Number'].astype(str).str.strip()
            master_df['Serial Number'] = master_df['Serial Number'].astype(str).str.strip()
            merged = master_df.merge(portal_df, on='Serial Number', how='left')
            
            # Calculate days inactive
            if 'Last Activity' in merged.columns:
                merged['Last Date'] = pd.to_datetime(merged['Last Activity'], errors='coerce')
                today = datetime.now()
                merged['Days Inactive'] = (today - merged['Last Date']).dt.days.fillna(0)
            else:
                merged['Days Inactive'] = 0
            
            # Determine status
            def get_status(row):
                days = row.get('Days Inactive', 0)
                if days <= self.active_threshold:
                    return '✅ Active'
                elif days <= 30:
                    return '⚠️ Inactive'
                else:
                    return '❌ Critical'
            
            merged['Status'] = merged.apply(get_status, axis=1)
            
            # Create summary
            summary = merged['Status'].value_counts().reset_index()
            summary.columns = ['Status', 'Count']
            summary['Percentage'] = (summary['Count'] / summary['Count'].sum() * 100).round(1)
            
            # Display columns
            display_cols = ['Serial Number', 'Status', 'Days Inactive']
            if 'Last Activity' in merged.columns:
                display_cols.append('Last Activity')
            if 'Device Name' in merged.columns:
                display_cols.append('Device Name')
            if 'Location' in merged.columns:
                display_cols.append('Location')
            
            result_df = merged[display_cols].copy()
            
            return result_df, summary
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None, None
