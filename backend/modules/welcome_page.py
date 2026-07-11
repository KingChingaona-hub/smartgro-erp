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
    
    # Initialize footer section state
    if "footer_section" not in st.session_state:
        st.session_state.footer_section = None
    
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
        
        .footer-content {
            background: white;
            padding: 25px;
            border-radius: 16px;
            margin-top: 20px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 2px 12px rgba(0,0,0,0.05);
        }
        
        .footer-content h3 {
            color: #1a1a2e;
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 15px;
        }
        
        .footer-content p, .footer-content li {
            color: #4a5568;
            line-height: 1.8;
        }
        
        .footer-content ul {
            list-style: none;
            padding: 0;
        }
        
        .footer-content ul li {
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        
        .footer-content ul li:last-child {
            border-bottom: none;
        }
        
        .footer-content ul li strong {
            color: #1a1a2e;
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
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .welcome-footer .footer-links .footer-link {
            background: none;
            border: none;
            color: #6B7280;
            font-size: 0.85rem;
            cursor: pointer;
            padding: 5px 10px;
            transition: all 0.3s ease;
            font-family: 'Inter', sans-serif;
            text-decoration: none;
        }
        
        .welcome-footer .footer-links .footer-link:hover {
            color: #FF6B35;
            transform: translateY(-2px);
        }
        
        .welcome-footer .footer-links .footer-link.active {
            color: #FF6B35;
            font-weight: 600;
            border-bottom: 2px solid #FF6B35;
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
            .welcome-footer .footer-links {
                gap: 15px;
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
            .welcome-footer .footer-links {
                flex-direction: column;
                gap: 5px;
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
    
    # About Section (always visible)
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
    
    # Footer with clickable links
    st.markdown('<div class="welcome-footer">', unsafe_allow_html=True)
    st.markdown('<div class="footer-links">', unsafe_allow_html=True)
    
    # Define footer sections with their display names and keys
    footer_sections = [
        {"key": "about", "label": "About"},
        {"key": "features", "label": "Features"},
        {"key": "support", "label": "Support"},
        {"key": "privacy", "label": "Privacy Policy"},
        {"key": "terms", "label": "Terms"}
    ]
    
    # Create columns for footer links
    cols = st.columns(len(footer_sections))
    
    for idx, section in enumerate(footer_sections):
        with cols[idx]:
            is_active = st.session_state.footer_section == section["key"]
            
            if st.button(
                section["label"], 
                key=f"footer_{section['key']}",
                use_container_width=True
            ):
                if st.session_state.footer_section == section["key"]:
                    st.session_state.footer_section = None
                else:
                    st.session_state.footer_section = section["key"]
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show footer content BELOW the links
    if st.session_state.footer_section:
        st.markdown(f"""
        <div class="footer-content">
            {get_footer_content(st.session_state.footer_section)}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <p style="margin-top: 20px;">SmartGro ERP v2.0 • © {datetime.now().year} All Rights Reserved</p>
    <p style="font-size: 0.7rem; margin-top: 5px;">
        Logged in as: <strong>{username}</strong> • Role: <strong>{role.upper()}</strong> • Branch: <strong>{branch_name}</strong>
    </p>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)


def get_footer_content(section):
    """Return content for footer sections"""
    
    content = {
        "about": """
        <h3>📖 About SmartGro ERP</h3>
        <p><strong>SmartGro ERP</strong> is a cutting-edge Enterprise Resource Planning solution built for modern retail and distribution businesses.</p>
        <br>
        <p><strong>Our Mission:</strong> To empower businesses with intelligent, user-friendly tools that streamline operations, drive growth, and deliver actionable insights.</p>
        <br>
        <p><strong>Our Vision:</strong> To become the preferred ERP platform for retail and distribution businesses across Africa and beyond.</p>
        <br>
        <p><strong>Key Values:</strong></p>
        <ul>
            <li><strong>Innovation</strong> - Continuously evolving with modern technology</li>
            <li><strong>Reliability</strong> - Built for businesses that depend on us</li>
            <li><strong>Simplicity</strong> - Easy to use, powerful in execution</li>
            <li><strong>Growth</strong> - Helping businesses scale and succeed</li>
        </ul>
        """,
        
        "features": """
        <h3>✨ SmartGro ERP Features</h3>
        <p>SmartGro ERP comes packed with powerful features designed to simplify your business operations:</p>
        <br>
        <ul>
            <li><strong>📦 Inventory Management</strong> - Real-time stock tracking, low stock alerts, and product management</li>
            <li><strong>💳 Point of Sale (POS)</strong> - Fast checkout with barcode scanning and customer management</li>
            <li><strong>📊 Analytics & Reports</strong> - Sales dashboards, profit analysis, and business intelligence</li>
            <li><strong>👥 Customer Management</strong> - Track history, loyalty programs, and retention insights</li>
            <li><strong>💰 Cash & Finance</strong> - Income, expenses, purchases, and cash flow management</li>
            <li><strong>🔐 Multi-Branch Support</strong> - Centralized control with branch-level reporting</li>
            <li><strong>📱 Mobile Dashboard</strong> - Access your business from anywhere</li>
            <li><strong>🔔 Auto Notifications</strong> - Low stock alerts and important updates</li>
            <li><strong>📄 Document Generation</strong> - Invoices, delivery notes, credit notes, and more</li>
        </ul>
        """,
        
        "support": """
        <h3>🆘 Support Center</h3>
        <p>We're here to help you succeed with SmartGro ERP.</p>
        <br>
        <p><strong>📧 Email Support:</strong> support@smartgro.com</p>
        <p><strong>📞 Phone Support:</strong> +27 11 234 5678</p>
        <p><strong>🕐 Business Hours:</strong> Monday - Friday, 8:00 AM - 6:00 PM (SAST)</p>
        <br>
        <p><strong>📚 Resources:</strong></p>
        <ul>
            <li><strong>📖 User Guide</strong> - Comprehensive documentation</li>
            <li><strong>🎥 Video Tutorials</strong> - Step-by-step guides</li>
            <li><strong>💬 Community Forum</strong> - Connect with other users</li>
            <li><strong>🐛 Bug Report</strong> - Report issues or suggest improvements</li>
        </ul>
        <br>
        <p><em>Response time: Within 24 hours for all support requests.</em></p>
        """,
        
        "privacy": """
        <h3>🔒 Privacy Policy</h3>
        <p>At SmartGro ERP, we take your privacy seriously. Here's how we protect your data:</p>
        <br>
        <p><strong>Data Collection:</strong> We only collect data necessary for business operations - inventory, sales, customer, and financial data.</p>
        <p><strong>Data Storage:</strong> All data is encrypted and stored securely on our servers with regular backups.</p>
        <p><strong>Data Sharing:</strong> We never sell or share your data with third parties without your explicit consent.</p>
        <p><strong>Data Access:</strong> Only authorized personnel with specific roles can access data based on their permissions.</p>
        <p><strong>Data Retention:</strong> Data is retained for as long as your account is active and as required by law.</p>
        <p><strong>Your Rights:</strong> You have the right to access, modify, or delete your data at any time.</p>
        <br>
        <p><em>Last updated: """ + datetime.now().strftime('%B %d, %Y') + """</em></p>
        """,
        
        "terms": """
        <h3>📋 Terms of Service</h3>
        <p>By using SmartGro ERP, you agree to the following terms:</p>
        <br>
        <p><strong>1. Acceptance of Terms:</strong> By using SmartGro ERP, you agree to these terms. If you don't agree, please don't use the service.</p>
        <p><strong>2. Account Security:</strong> You are responsible for maintaining the security of your account and password.</p>
        <p><strong>3. Data Ownership:</strong> All data you enter into SmartGro ERP belongs to you and your organization.</p>
        <p><strong>4. Service Availability:</strong> We strive for 99.9% uptime but cannot guarantee uninterrupted service.</p>
        <p><strong>5. Updates:</strong> We may update the service and these terms from time to time.</p>
        <p><strong>6. Termination:</strong> Either party may terminate the service at any time with notice.</p>
        <p><strong>7. Liability:</strong> We are not liable for indirect, incidental, or consequential damages.</p>
        <p><strong>8. Governing Law:</strong> These terms are governed by the laws of Zimbabwe.</p>
        <br>
        <p><em>Last updated: """ + datetime.now().strftime('%B %d, %Y') + """</em></p>
        """
    }
    
    return content.get(section, "<p>Content not found.</p>")