# backend/core/responsive.py
import streamlit as st
from streamlit import runtime

def is_mobile_device():
    """Detect if user is on mobile device"""
    try:
        if runtime.exists():
            user_agent = st.context.headers.get("User-Agent", "")
            mobile_keywords = [
                "Mobile", "Android", "iPhone", "iPad", 
                "iPod", "BlackBerry", "Windows Phone", 
                "webOS", "Opera Mini", "Samsung", "Nokia"
            ]
            return any(keyword in user_agent for keyword in mobile_keywords)
    except:
        pass
    return False

def get_device_type():
    """Get detailed device type"""
    try:
        if runtime.exists():
            user_agent = st.context.headers.get("User-Agent", "").lower()
            if "iphone" in user_agent or "ipad" in user_agent:
                return "iOS"
            elif "android" in user_agent:
                return "Android"
            elif "windows" in user_agent:
                return "Windows"
            elif "mac" in user_agent:
                return "Mac"
            else:
                return "Other"
    except:
        pass
    return "Unknown"

def apply_mobile_css():
    """Apply mobile-optimized CSS"""
    css = """
    <style>
        /* Mobile-first responsive design */
        @media screen and (max-width: 768px) {
            /* Main container */
            .main .block-container {
                padding: 0.5rem !important;
                padding-top: 1rem !important;
            }
            
            /* Full-width buttons */
            .stButton button {
                width: 100% !important;
                padding: 0.75rem !important;
                font-size: 1rem !important;
                min-height: 48px !important;
                border-radius: 8px !important;
            }
            
            /* Touch-friendly inputs */
            .stSelectbox select,
            .stTextInput input,
            .stNumberInput input,
            .stTextArea textarea {
                font-size: 16px !important;
                min-height: 44px !important;
                padding: 8px 12px !important;
            }
            
            /* Column stacking */
            div[data-testid="column"] {
                min-width: 100% !important;
                padding: 0.25rem !important;
            }
            
            /* Cards and metrics */
            div[data-testid="metric-container"] {
                padding: 8px !important;
                margin: 4px 0 !important;
            }
            
            /* Make tables scrollable */
            div[data-testid="stTable"] {
                overflow-x: auto !important;
                -webkit-overflow-scrolling: touch !important;
            }
            
            /* Larger touch targets for tabs */
            button[data-baseweb="tab"] {
                padding: 10px 16px !important;
                font-size: 0.9rem !important;
                min-height: 44px !important;
            }
            
            /* Mobile-friendly sidebar */
            [data-testid="stSidebar"] {
                min-width: 100% !important;
                max-width: 100% !important;
                padding: 0.5rem !important;
            }
            
            /* Bottom padding for nav */
            .main-content {
                padding-bottom: 80px !important;
            }
            
            /* Fix for plotly charts on mobile */
            .js-plotly-plot {
                width: 100% !important;
            }
        }
        
        /* Tablet optimization */
        @media screen and (min-width: 769px) and (max-width: 1024px) {
            div[data-testid="column"] {
                padding: 0.5rem !important;
            }
        }
        
        /* Prevent zoom on input focus */
        input, select, textarea {
            font-size: 16px !important;
        }
        
        /* Smooth scrolling */
        * {
            -webkit-overflow-scrolling: touch;
        }
        
        /* Loading spinner fix for mobile */
        .stSpinner {
            position: fixed !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            z-index: 9999 !important;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">', unsafe_allow_html=True)

def show_mobile_banner():
    """Show a mobile banner when on mobile device"""
    if is_mobile_device():
        st.success(f"📱 Mobile Mode Active - {get_device_type()}")