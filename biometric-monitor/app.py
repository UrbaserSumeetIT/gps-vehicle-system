import streamlit as st
from modules.data_processor import BiometricDataProcessor
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Biometric Device Monitor",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem;
        font-weight: bold;
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
if 'saved_reports' not in st.session_state:
    st.session_state.saved_reports = []

# Header
st.markdown('<div class="main-header">🏢 Biometric Device Monitoring System</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("📁 Data Upload")
    
    portal_file = st.file_uploader(
        "Device Export File (Excel)",
        type=['xlsx', 'xls'],
        help="Upload device export file with Serial Numbers and Last Activity"
    )
    
    master_file = st.file_uploader(
        "Master File (Excel)",
        type=['xlsx', 'xls'],
        help="Upload master device list with Serial Numbers"
    )
    
    st.markdown("---")
    
    if st.button("🚀 Process Data", type="primary", use_container_width=True):
        if portal_file and master_file:
            with st.spinner("Processing..."):
                processor = BiometricDataProcessor(active_threshold=2)
                processed_df, summary_df = processor.process_files(portal_file, master_file)
                
                if processed_df is not None:
                    st.session_state.processed_data = processed_df
                    st.session_state.summary_data = summary_df
                    
                    # Add to history
                    st.session_state.processing_history.append({
                        'timestamp': datetime.now(),
                        'total_devices': len(processed_df),
                        'file_name': portal_file.name,
                        'active_count': len(processed_df[processed_df['Status'] == '✅ Active']),
                        'inactive_count': len(processed_df[processed_df['Status'] == '⚠️ Inactive'])
                    })
                    
                    st.success("✅ Processing complete!")
                    st.balloons()
        else:
            st.warning("⚠️ Please upload both files")
    
    st.markdown("---")
    st.caption("Navigate using the tabs above ☝️")

# Main content area - Show welcome or instructions
if st.session_state.processed_data is None:
    st.info("""
    ### 👋 Welcome to Biometric Device Monitor!
    
    **Quick Start:**
    1. 📁 Upload your Excel files in the **left sidebar**
    2. 🚀 Click **Process Data** button
    3. 📊 Explore the **Dashboard**, **Device Data**, **Analytics**, and **History** tabs
    
    **Features:**
    - ✅ Automatic data processing and merging
    - 📈 Interactive charts and metrics
    - 📤 Export to CSV
    - 💾 Save and load reports
    - 📜 Processing history
    
    **Sample Data Format:**
    - **Device Export:** Serial Number, Last Activity, Device Name
    - **Master File:** Serial Number, Device Name, Location
    """)
else:
    st.success(f"✅ Data loaded! {len(st.session_state.processed_data)} devices ready. Use the tabs above to explore.")

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>Biometric Device Monitor | Free for Streamlit Cloud</p>",
    unsafe_allow_html=True
)
