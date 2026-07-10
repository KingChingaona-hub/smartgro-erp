# backend/modules/welcome_page.py

import streamlit as st
from datetime import datetime
import random

def welcome_page():
    """Professional welcome page shown after successful login"""
    
    # Get user info
    username = st.session_state.get("username", "User")
    role = st.session_state.get("role", "cashier")
    current_branch = st.session_state.get("current_branch", "HO")
    branch_name = st.session_state.get("branch_name", "Unknown")
    
    # Get current time for greeting
    current_hour = datetime.now().hour
    if current_hour < 12:
        greeting = "Good Morning"
    elif current_hour < 17:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"
    
    # Random motivational quote
    quotes = [
        "Success is not final, failure is not fatal: it is the courage to continue that counts.",
        "The only way to do great work is to love what you do.",
        "Innovation distinguishes between a leader and a follower.",
        "The future belongs to those who believe in the beauty of their dreams.",
        "It does not matter how slowly you go as long as you do not stop.",
        "The best time to start was yesterday. The next best time is now.",
        "Your limitation—it's only your imagination.",
        "Push yourself, because no one else is going to do it for you."
    ]
    quote = random.choice(quotes)
    
    # Main welcome container with enhanced styling
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        .welcome-container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            font-family: 'Inter', sans-serif;
        }
        
        .welcome-header {
            text-align: center;
            padding: 40px 30px;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            border-radius: 20px;
            margin-bottom: 35px;
            color: white;
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .welcome-header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,215,0,0.1) 0%, transparent 70%);
            animation: shimmer 8s ease-in-out infinite;
        }
        
        @keyframes shimmer {
            0%, 100% { transform: translate(0, 0); }
            50% { transform: translate(10%, 10%); }
        }
        
        .welcome-header h1 {
            font-size: 3.2rem;
            font-weight: 800;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #FFD700 0%, #FF6B35 50%, #FF1493 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            position: relative;
            z-index: 1;
            letter-spacing: -1px;
        }
        
        .welcome-header .subtitle {
            font-size: 1.1rem;
            color: #a8b2d1;
            margin-top: 5px;
            position: relative;
            z-index: 1;
            letter-spacing: 2px;
            font-weight: 300;
        }
        
        .welcome-header .greeting {
            font-size: 1.4rem;
            color: #e6f1ff;
            margin-top: 15px;
            position: relative;
            z-index: 1;
            font-weight: 600;
        }
        
        .welcome-header .user-info {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
            position: relative;
            z-index: 1;
            flex-wrap: wrap;
        }
        
        .welcome-header .user-info .badge {
            background: rgba(255,255,255,0.12);
            padding: 6px 20px;
            border-radius: 20px;
            font-size: 0.85rem;
            color: #e6f1ff;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.08);
        }
        
        .welcome-header .user-info .badge strong {
            color: #FFD700;
        }
        
        .welcome-header .quote {
            margin-top: 20px;
            padding: 15px 25px;
            background: rgba(255,255,255,0.06);
            border-radius: 12px;
            border-left: 3px solid #FFD700;
            position: relative;
            z-index: 1;
            font-style: italic;
            color: #c0c8e0;
            font-size: 0.95rem;
            max-width: 80%;
            margin-left: auto;
            margin-right: auto;
        }
        
        .quick-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 20px 0 30px 0;
        }
        
        .quick-stat-item {
            background: white;
            padding: 20px;
            border-radius: 14px;
            text-align: center;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            border: 1px solid #f0f0f0;
            transition: all 0.3s ease;
        }
        
        .quick-stat-item:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        
        .quick-stat-item .stat-icon {
            font-size: 2rem;
            margin-bottom: 8px;
        }
        
        .quick-stat-item .stat-label {
            font-size: 0.8rem;
            color: #6B7280;
            font-weight: 500;
            letter-spacing: 0.5px;
        }
        
        .section-title {
            text-align: center;
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a2e;
            margin: 40px 0 20px 0;
            letter-spacing: -0.5px;
        }
        
        .section-title span {
            background: linear-gradient(135deg, #FFD700, #FF6B35);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .about-section {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            border: 1px solid #e5e7eb;
        }
        
        .about-section p {
            color: #1a1a2e;
            font-size: 1.05rem;
            line-height: 1.8;
            margin: 0;
        }
        
        .about-section .highlight {
            color: #FF6B35;
            font-weight: 600;
        }
        
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin: 25px 0 30px 0;
        }
        
        .feature-card {
            background: white;
            padding: 28px 20px;
            border-radius: 16px;
            text-align: center;
            box-shadow: 0 2px 12px rgba(0,0,0,0.05);
            border: 1px solid #f0f0f0;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .feature-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #FFD700, #FF6B35, #FF1493);
            transform: scaleX(0);
            transition: transform 0.3s ease;
        }
        
        .feature-card:hover {
            transform: translateY(-6px);
            box-shadow: 0 12px 35px rgba(0,0,0,0.1);
        }
        
        .feature-card:hover::before {
            transform: scaleX(1);
        }
        
        .feature-card .icon {
            font-size: 2.8rem;
            margin-bottom: 15px;
            display: block;
        }
        
        .feature-card h4 {
            color: #1a1a2e;
            font-size: 1.05rem;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .feature-card p {
            color: #6B7280;
            font-size: 0.85rem;
            line-height: 1.6;
            margin: 0;
        }
        
        .get-started-section {
            text-align: center;
            background: linear-gradient(135deg, #1a1a2e 0%, #302b63 100%);
            padding: 40px;
            border-radius: 20px;
            margin-top: 30px;
            position: relative;
            overflow: hidden;
        }
        
        .get-started-section::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,215,0,0.05) 0%, transparent 70%);
            animation: shimmer 10s ease-in-out infinite;
        }
        
        .get-started-section h3 {
            color: white;
            font-size: 1.6rem;
            font-weight: 700;
            position: relative;
            z-index: 1;
            margin-bottom: 10px;
        }
        
        .get-started-section p {
            color: #a8b2d1;
            position: relative;
            z-index: 1;
            margin-bottom: 25px;
            font-size: 1rem;
        }
        
        .welcome-footer {
            text-align: center;
            color: #6B7280;
            font-size: 0.8rem;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }
        
        .welcome-footer .footer-links {
            display: flex;
            justify-content: center;
            gap: 25px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }
        
        .welcome-footer .footer-links a {
            color: #6B7280;
            text-decoration: none;
            font-size: 0.8rem;
            transition: color 0.3s ease;
        }
        
        .welcome-footer .footer-links a:hover {
            color: #FF6B35;
        }
        
        @media (max-width: 768px) {
            .quick-stats {
                grid-template-columns: repeat(2, 1fr);
            }
            .feature-grid {
                grid-template-columns: 1fr 1fr;
            }
            .welcome-header h1 {
                font-size: 2.2rem;
            }
            .welcome-header .quote {
                max-width: 100%;
                font-size: 0.85rem;
            }
            .welcome-header .user-info {
                gap: 10px;
            }
            .get-started-section {
                padding: 30px 20px;
            }
        }
        
        @media (max-width: 480px) {
            .quick-stats {
                grid-template-columns: 1fr 1fr;
            }
            .feature-grid {
                grid-template-columns: 1fr;
            }
            .welcome-header h1 {
                font-size: 1.8rem;
            }
            .welcome-header .greeting {
                font-size: 1.1rem;
            }
            .section-title {
                font-size: 1.5rem;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="welcome-container">', unsafe_allow_html=True)
    
    # Header
    st.markdown(f"""
    <div class="welcome-header">
        <h1>SmartGro ERP</h1>
        <div class="subtitle">Enterprise Resource Planning</div>
        <div class="greeting">{greeting}, {username}! 👋</div>
        <div class="user-info">
            <span class="badge">🏢 <strong>{branch_name}</strong></span>
            <span class="badge">🔑 <strong>{role.upper()}</strong></span>
            <span class="badge">📅 <strong>{datetime.now().strftime('%B %d, %Y')}</strong></span>
        </div>
        <div class="quote">" {quote} "</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick Stats
    st.markdown("""
    <div class="quick-stats">
        <div class="quick-stat-item">
            <div class="stat-icon">📦</div>
            <div class="stat-label">Inventory Management</div>
        </div>
        <div class="quick-stat-item">
            <div class="stat-icon">💳</div>
            <div class="stat-label">Point of Sale</div>
        </div>
        <div class="quick-stat-item">
            <div class="stat-icon">📊</div>
            <div class="stat-label">Analytics & Reports</div>
        </div>
        <div class="quick-stat-item">
            <div class="stat-icon">👥</div>
            <div class="stat-label">Customer Management</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # About Section
    st.markdown("""
    <div class="section-title">About <span>SmartGro ERP</span></div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="about-section">
        <p>
            <strong>SmartGro ERP</strong> is a comprehensive Enterprise Resource Planning system 
            designed specifically for <span class="highlight">retail and distribution businesses</span>. 
            It provides a unified platform to manage all aspects of your business operations efficiently, 
            from inventory and sales to customer relationships and financial reporting.
        </p>
        <p style="margin-top: 10px;">
            Built with <span class="highlight">modern technology</span> and a user-centric approach, 
            SmartGro ERP empowers your team to make data-driven decisions and streamline daily operations.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Features
    st.markdown("""
    <div class="section-title">✨ Key <span>Features</span></div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="feature-grid">
        <div class="feature-card">
            <span class="icon">📦</span>
            <h4>Inventory Management</h4>
            <p>Track stock levels, manage products, and get low stock alerts in real-time.</p>
        </div>
        <div class="feature-card">
            <span class="icon">💳</span>
            <h4>Point of Sale (POS)</h4>
            <p>Process sales quickly with barcode scanning and customer management.</p>
        </div>
        <div class="feature-card">
            <span class="icon">📊</span>
            <h4>Analytics & Reports</h4>
            <p>Get insights with sales dashboards, profit analysis, and business intelligence.</p>
        </div>
        <div class="feature-card">
            <span class="icon">👥</span>
            <h4>Customer Management</h4>
            <p>Track customer history, manage loyalty programs, and improve retention.</p>
        </div>
        <div class="feature-card">
            <span class="icon">💰</span>
            <h4>Cash & Finance</h4>
            <p>Manage income, expenses, purchases, and cash flow with ease.</p>
        </div>
        <div class="feature-card">
            <span class="icon">🔐</span>
            <h4>Multi-Branch Support</h4>
            <p>Manage multiple branches with centralized control and reporting.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get Started
    st.markdown("""
    <div class="get-started-section">
        <h3>Ready to take control of your business?</h3>
        <p>Start managing your operations with SmartGro ERP today.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get Started Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Get Started", type="primary", use_container_width=True):
            st.session_state.welcome_seen = True
            st.session_state.current_page = "Stock Dashboard"
            st.rerun()
    
    # Footer
    st.markdown(f"""
    <div class="welcome-footer">
        <div class="footer-links">
            <a href="#">About</a>
            <a href="#">Features</a>
            <a href="#">Support</a>
            <a href="#">Privacy Policy</a>
            <a href="#">Terms</a>
        </div>
        <p>SmartGro ERP v2.0 • © {datetime.now().year} All Rights Reserved</p>
        <p style="font-size: 0.7rem; margin-top: 5px;">
            Logged in as: <strong>{username}</strong> • Role: <strong>{role.upper()}</strong> • Branch: <strong>{branch_name}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)