# backend/modules/welcome_page.py

import streamlit as st
from datetime import datetime

def welcome_page():
    """Welcome page shown after successful login"""
    
    # Get user info
    username = st.session_state.get("username", "User")
    role = st.session_state.get("role", "cashier")
    current_branch = st.session_state.get("current_branch", "HO")
    branch_name = st.session_state.get("branch_name", "Unknown")
    
    # Main welcome container
    st.markdown("""
    <style>
        .welcome-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        .welcome-header {
            text-align: center;
            padding: 30px 0;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 15px;
            margin-bottom: 30px;
            color: white;
        }
        .welcome-header h1 {
            font-size: 2.8rem;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .welcome-header p {
            font-size: 1.2rem;
            color: #ccc;
        }
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .feature-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s ease;
            border: 1px solid #e5e7eb;
        }
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        .feature-icon {
            font-size: 2.5rem;
            margin-bottom: 15px;
        }
        .feature-card h3 {
            color: #1a1a2e;
            margin-bottom: 10px;
            font-size: 1.1rem;
        }
        .feature-card p {
            color: #6B7280;
            font-size: 0.9rem;
            line-height: 1.5;
        }
        .get-started-btn {
            text-align: center;
            margin: 30px 0;
        }
        .stats-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
        }
        .stat-item {
            text-align: center;
        }
        .stat-number {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1a1a2e;
        }
        .stat-label {
            color: #6B7280;
            font-size: 0.85rem;
        }
        .welcome-footer {
            text-align: center;
            color: #6B7280;
            font-size: 0.85rem;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }
        @media (max-width: 640px) {
            .welcome-header h1 {
                font-size: 2rem;
            }
            .feature-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="welcome-container">', unsafe_allow_html=True)
    
    # Header
    st.markdown(f"""
    <div class="welcome-header">
        <h1>🚀 SmartGro ERP</h1>
        <p>Welcome back, <strong>{username}</strong>! 👋</p>
        <p style="font-size: 0.9rem; color: #aaa; margin-top: 5px;">
            {branch_name} • {role.upper()}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick stats (optional)
    st.markdown("""
    <div class="stats-row">
        <div class="stat-item">
            <div class="stat-number">📦</div>
            <div class="stat-label">Inventory Management</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">💰</div>
            <div class="stat-label">Sales & Cash</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">📊</div>
            <div class="stat-label">Analytics & Reports</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">👥</div>
            <div class="stat-label">Customer Management</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # About SmartGro
    st.markdown("""
    <h2 style="text-align: center; color: #1a1a2e; margin: 30px 0 20px 0;">
        About SmartGro ERP
    </h2>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: #f8f9fa; padding: 20px; border-radius: 12px; margin-bottom: 20px; line-height: 1.8;">
        <p style="color: #1a1a2e; font-size: 1rem;">
            <strong>SmartGro ERP</strong> is a comprehensive Enterprise Resource Planning system 
            designed specifically for retail and distribution businesses. It provides a unified 
            platform to manage all aspects of your business operations efficiently.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Features
    st.markdown("""
    <h3 style="text-align: center; color: #1a1a2e; margin: 30px 0 20px 0;">
        ✨ Key Features
    </h3>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="feature-grid">
        <div class="feature-card">
            <div class="feature-icon">📦</div>
            <h3>Inventory Management</h3>
            <p>Track stock levels, manage products, and get low stock alerts in real-time.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">💳</div>
            <h3>Point of Sale (POS)</h3>
            <p>Process sales quickly with barcode scanning and customer management.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3>Analytics & Reports</h3>
            <p>Get insights with sales dashboards, profit analysis, and business intelligence.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">👥</div>
            <h3>Customer Management</h3>
            <p>Track customer history, manage loyalty programs, and improve retention.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">💰</div>
            <h3>Cash & Finance</h3>
            <p>Manage income, expenses, purchases, and cash flow with ease.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🔐</div>
            <h3>Multi-Branch Support</h3>
            <p>Manage multiple branches with centralized control and reporting.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get Started Button
    st.markdown('<div class="get-started-btn">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Get Started", type="primary", use_container_width=True):
            # Set a flag to show the welcome page was seen
            st.session_state.welcome_seen = True
            # Navigate to Stock Dashboard
            st.session_state.current_page = "Stock Dashboard"
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown(f"""
    <div class="welcome-footer">
        <p>SmartGro ERP v2.0 • © {datetime.now().year} All Rights Reserved</p>
        <p style="font-size: 0.75rem;">Logged in as: {username} • Role: {role} • Branch: {branch_name}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)