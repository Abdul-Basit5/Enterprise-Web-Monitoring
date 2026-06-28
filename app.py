import streamlit as st
import json
import os
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from generic_monitor import run_monitoring_cycle

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(page_title="Enterprise Web Monitor", layout="wide")

# Theme / CSS for dynamic status indicators
st.markdown("""
<style>
    .status-healthy { color: #28a745; font-weight: bold; }
    .status-changes { color: #fd7e14; font-weight: bold; }
    .status-error { color: #dc3545; font-weight: bold; }
    .stCard {
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 2. Sidebar Controls
st.sidebar.title("🛠️ Monitor Controls")
poll_frequency = st.sidebar.slider("Poll Timer Frequency (s)", 30, 300, 60)

# 1. Seamless Auto-Refresh (based on slider frequency)
st_autorefresh(interval=poll_frequency * 1000, key="data_refresh")

# Initialize Session State
if 'monitor_running' not in st.session_state:
    st.session_state.monitor_running = False

# Function to load/save JSON
def load_json(filepath):
    try:
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                json.dump({}, f)
                return {}
        with open(filepath, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# Load State
config = load_json("config.json")
monitored_pages = load_json("monitored_pages.json")


# Append new monitoring target
new_url = st.sidebar.text_input("Add Monitoring Target URL", placeholder="https://example.com")
if st.sidebar.button("Add Target"):
    if new_url and new_url not in monitored_pages:
        monitored_pages[new_url] = {
            "status": "Initializing",
            "baseline_hash": None,
            "last_sanitized_text": ""
        }
        save_json("monitored_pages.json", monitored_pages)
        st.sidebar.success(f"Added: {new_url}")
    elif new_url in monitored_pages:
        st.sidebar.warning("URL already monitored.")

# Poll timer slider

st.sidebar.divider()

# Global Operational Triggers
col1, col2 = st.sidebar.columns(2)
if col1.button("▶️ Start Engine", use_container_width=True):
    st.session_state.monitor_running = True
if col2.button("⏹️ Stop Engine", use_container_width=True):
    st.session_state.monitor_running = False

status_text = "Running" if st.session_state.monitor_running else "Stopped"
status_color = "green" if st.session_state.monitor_running else "red"
st.sidebar.markdown(f"Engine Status: :{status_color}[{status_text}]")

# 3. Notification Node (Settings)
with st.sidebar.expander("📧 Notification Settings (Environment)"):
    st.info("Credentials are loaded from the project's .env file for security.")
    
    # Load current values from environment
    env_sender = os.getenv("SENDER_EMAIL", "")
    env_password = os.getenv("APP_PASSWORD", "")
    env_receiver = os.getenv("RECEIVER_EMAIL", "")
    
    st.text_input("Sender Gmail", value=env_sender, disabled=True)
    st.text_input("App Password", value="********" if env_password else "", type="password", disabled=True)
    st.text_input("Receiver Email", value=env_receiver, disabled=True)
    
    st.caption("To update these, please edit your .env file directly.")

# 4. Main UI - Live Monitors Grid
st.title("🛡️ Enterprise-Grade Web Monitoring System")
st.subheader("Live Operational Grid")

if not monitored_pages:
    st.info("No monitoring targets added yet. Use the sidebar to add your first URL.")
else:
    # Display monitors in a grid
    cols = st.columns(3)
    for idx, (url, data) in enumerate(monitored_pages.items()):
        with cols[idx % 3]:
            status = data.get('status', 'Initializing')
            
            # Dynamic Styling
            status_class = "status-healthy"
            if "Error" in status or "Blocked" in status:
                status_class = "status-error"
            elif "Changes" in status:
                status_class = "status-changes"
                
            st.markdown(f"""
            <div class="stCard">
                <h4 style="margin-top:0;">Target: {url}</h4>
                <p>Status: <span class="{status_class}">{status}</span></p>
                <p><small>Baseline Fingerprint: {data.get('baseline_hash', 'N/A')[:8] if data.get('baseline_hash') else 'Pending'}</small></p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"Remove {idx}", key=f"del_{idx}"):
                del monitored_pages[url]
                save_json("monitored_pages.json", monitored_pages)
                st.rerun()

# 5. Execution Logic
if st.session_state.monitor_running:
    st.toast("Monitoring cycle initiated...")
    run_monitoring_cycle()
    # Refresh to show new statuses after cycle
    st.rerun()
