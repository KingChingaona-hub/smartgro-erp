# backend/core/mobile_quick_actions.py
import streamlit as st
from backend.core.responsive import is_mobile_device

def show_mobile_quick_actions():
    """Show quick action buttons for mobile users"""
    
    if not is_mobile_device():
        return
    
    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")
    
    # Row 1 - Primary actions
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🛒 New Sale", use_container_width=True, key="mobile_pos"):
            st.session_state.current_page = "POS"
            st.rerun()
    
    with col2:
        if st.button("📦 Stock", use_container_width=True, key="mobile_stock"):
            st.session_state.current_page = "Stock Dashboard"
            st.rerun()
    
    with col3:
        if st.button("👥 Customers", use_container_width=True, key="mobile_customers"):
            st.session_state.current_page = "Customer Dashboard"
            st.rerun()
    
    # Row 2 - Secondary actions
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💰 Sales", use_container_width=True, key="mobile_sales"):
            st.session_state.current_page = "Sales Dashboard"
            st.rerun()
    
    with col2:
        if st.button("📊 Reports", use_container_width=True, key="mobile_reports"):
            st.session_state.current_page = "Reports Dashboard"
            st.rerun()
    
    with col3:
        if st.button("📱 Mobile", use_container_width=True, key="mobile_dashboard"):
            st.session_state.current_page = "Mobile Dashboard"
            st.rerun()
    
    st.markdown("---")

def show_mobile_bottom_nav():
    """Show bottom navigation bar for mobile"""
    
    if not is_mobile_device():
        return
    
    # Get current page
    current_page = st.session_state.get("current_page", "Stock Dashboard")
    
    # Define navigation items
    nav_items = [
        {"icon": "🏠", "label": "Home", "page": "Stock Dashboard"},
        {"icon": "🛒", "label": "POS", "page": "POS"},
        {"icon": "📊", "label": "Sales", "page": "Sales Dashboard"},
        {"icon": "👥", "label": "Customers", "page": "Customer Dashboard"},
        {"icon": "📱", "label": "Mobile", "page": "Mobile Dashboard"}
    ]
    
    # Create bottom navigation HTML
    nav_html = """
    <style>
        .mobile-bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            display: flex;
            justify-content: space-around;
            padding: 8px 0;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            border-top: 1px solid #e0e0e0;
            background: #ffffff;
        }
        .mobile-nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-decoration: none;
            color: #666;
            font-size: 0.7rem;
            padding: 4px 8px;
            background: none;
            border: none;
            cursor: pointer;
            min-width: 50px;
        }
        .mobile-nav-item .icon {
            font-size: 1.5rem;
        }
        .mobile-nav-item .label {
            font-size: 0.6rem;
            margin-top: 2px;
        }
        .mobile-nav-item.active {
            color: #006400;
        }
        .mobile-nav-item.active .icon {
            transform: scale(1.1);
        }
        @media (prefers-color-scheme: dark) {
            .mobile-bottom-nav {
                background: #1e1e1e;
                border-top-color: #333;
            }
            .mobile-nav-item {
                color: #aaa;
            }
            .mobile-nav-item.active {
                color: #4CAF50;
            }
        }
    </style>
    <div class="mobile-bottom-nav">
    """
    
    for item in nav_items:
        active_class = "active" if current_page == item["page"] else ""
        nav_html += f"""
        <button class="mobile-nav-item {active_class}" onclick="window.location.href='?page={item["page"]}'">
            <span class="icon">{item["icon"]}</span>
            <span class="label">{item["label"]}</span>
        </button>
        """
    
    nav_html += "</div>"
    
    # Add padding to bottom of page
    st.markdown('<div style="padding-bottom: 80px;"></div>', unsafe_allow_html=True)
    st.markdown(nav_html, unsafe_allow_html=True)

def show_mobile_sidebar_toggle():
    """Show a toggle button for sidebar on mobile"""
    
    if not is_mobile_device():
        return
    
    if st.button("☰ Menu", use_container_width=True):
        st.session_state.show_sidebar = not st.session_state.get("show_sidebar", True)
        st.rerun()