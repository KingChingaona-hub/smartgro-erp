import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import base64
from PIL import Image
import io

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
BRANDING_FILE = DATA_DIR / "branding_settings.json"
LOGO_DIR = Path("static/branding")

# ==============================
# INITIALIZATION
# ==============================
def init_branding_files():
    """Initialize branding-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    
    if not BRANDING_FILE.exists():
        settings = {
            "business_name": "Aziel Investments",
            "business_tagline": "Smart Retail ERP System",
            "primary_color": "#6366F1",
            "secondary_color": "#8B5CF6",
            "accent_color": "#FF6584",
            "logo_url": "",
            "favicon_url": "",
            "footer_text": "© 2024 Aziel Investments. All rights reserved.",
            "receipt_footer": "Thank you for shopping with us!",
            "email_footer": "Aziel Investments - Smart Retail ERP System",
            "custom_css": "",
            "enable_branding": True,
            "branded_reports": True,
            "branded_receipts": True,
            "branded_emails": True
        }
        with open(BRANDING_FILE, "w") as f:
            json.dump(settings, f, indent=2)


def load_branding_settings():
    """Load branding settings"""
    init_branding_files()
    with open(BRANDING_FILE, "r") as f:
        return json.load(f)


def save_branding_settings(settings):
    """Save branding settings"""
    with open(BRANDING_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def show_toast(message, type="info"):
    """Show a toast notification using Streamlit"""
    if type == "success":
        st.success(f"✅ {message}")
    elif type == "error":
        st.error(f"❌ {message}")
    elif type == "warning":
        st.warning(f"⚠️ {message}")
    else:
        st.info(f"ℹ️ {message}")


def apply_branding():
    """Apply branding CSS to the app"""
    
    settings = load_branding_settings()
    
    if not settings.get("enable_branding", True):
        return
    
    primary = settings.get("primary_color", "#6366F1")
    secondary = settings.get("secondary_color", "#8B5CF6")
    accent = settings.get("accent_color", "#FF6584")
    business_name = settings.get("business_name", "Aziel Investments")
    
    css = f"""
    <style>
        /* Branded Theme */
        :root {{
            --brand-primary: {primary};
            --brand-secondary: {secondary};
            --brand-accent: {accent};
            --brand-name: "{business_name}";
        }}
        
        /* Sidebar Branding */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {primary}10 0%, {secondary}05 100%);
        }}
        
        [data-testid="stSidebar"] .stMarkdown {{
            color: {primary} !important;
        }}
        
        /* Header Branding */
        .stApp header {{
            background: linear-gradient(90deg, {primary} 0%, {secondary} 100%);
        }}
        
        /* Button Branding */
        .stButton > button {{
            background: linear-gradient(135deg, {primary} 0%, {secondary} 100%) !important;
            border: none !important;
        }}
        
        .stButton > button:hover {{
            background: linear-gradient(135deg, {primary}dd 0%, {secondary}dd 100%) !important;
            transform: translateY(-2px);
            box-shadow: 0 4px 20px {primary}40;
        }}
        
        /* Metrics Branding */
        [data-testid="stMetricValue"] {{
            color: {primary} !important;
        }}
        
        /* Tabs Branding */
        .stTabs [aria-selected="true"] {{
            background: {primary} !important;
            color: white !important;
        }}
        
        /* Progress Bar Branding */
        .stProgress > div > div {{
            background: linear-gradient(90deg, {primary} 0%, {secondary} 100%) !important;
        }}
        
        /* Alert Branding */
        .stSuccess {{
            border-left-color: {primary} !important;
        }}
        
        /* Sidebar Title */
        [data-testid="stSidebar"] .stTitle {{
            color: {primary} !important;
            font-weight: 700 !important;
        }}
        
        /* Footer Branding */
        .branded-footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 12px;
            border-top: 1px solid #eee;
            margin-top: 40px;
        }}
        
        .branded-footer .business-name {{
            color: {primary};
            font-weight: 600;
        }}
    </style>
    """
    
    # Add custom CSS if provided
    custom_css = settings.get("custom_css", "")
    if custom_css:
        css += f"\n<style>\n{custom_css}\n</style>"
    
    st.markdown(css, unsafe_allow_html=True)
    
    # Apply branded footer
    if settings.get("branded_receipts", True):
        footer = settings.get("footer_text", "")
        if footer:
            st.markdown(f"""
            <div class="branded-footer">
                <span class="business-name">{business_name}</span> - {footer}
            </div>
            """, unsafe_allow_html=True)


# ==============================
# BRANDED RECEIPTS
# ==============================
def get_branded_receipt_footer():
    """Get branded receipt footer"""
    settings = load_branding_settings()
    return settings.get("receipt_footer", "Thank you for shopping with us!")


def get_branded_email_footer():
    """Get branded email footer"""
    settings = load_branding_settings()
    return settings.get("email_footer", "Aziel Investments - Smart Retail ERP System")


def get_business_name():
    """Get business name"""
    settings = load_branding_settings()
    return settings.get("business_name", "Aziel Investments")


def get_branding_colors():
    """Get branding colors"""
    settings = load_branding_settings()
    return {
        "primary": settings.get("primary_color", "#6366F1"),
        "secondary": settings.get("secondary_color", "#8B5CF6"),
        "accent": settings.get("accent_color", "#FF6584")
    }


# ==============================
# BRANDED LOGO HANDLING
# ==============================
def upload_logo(logo_file):
    """Upload and save logo"""
    if logo_file:
        # Save logo
        logo_path = LOGO_DIR / "logo.png"
        logo_path.write_bytes(logo_file.getvalue())
        
        # Update settings
        settings = load_branding_settings()
        settings["logo_url"] = "/static/branding/logo.png"
        save_branding_settings(settings)
        
        return True
    return False


def get_logo_html():
    """Get logo HTML for display"""
    settings = load_branding_settings()
    logo_url = settings.get("logo_url", "")
    
    if logo_url:
        return f'<img src="{logo_url}" alt="Logo" style="max-height: 60px; margin: 10px 0;">'
    return ""


# ==============================
# WHITE LABEL DASHBOARD
# ==============================
def white_label_dashboard():
    """White Label / Branding Dashboard"""
    
    st.title("🏷️ White Label / Branding")
    st.caption("Customize your ERP system with your brand identity")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner"]:
        st.error("❌ Access Denied. Only owners can access branding settings.")
        return
    
    init_branding_files()
    settings = load_branding_settings()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎨 Branding",
        "🖼️ Logo",
        "📝 Custom CSS",
        "📋 Preview"
    ])
    
    # ==============================
    # TAB 1: BRANDING
    # ==============================
    with tab1:
        st.markdown("## 🎨 Branding Settings")
        st.caption("Customize your brand identity")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enable_branding = st.checkbox("Enable Branding", value=settings.get("enable_branding", True))
            business_name = st.text_input("Business Name", value=settings.get("business_name", "Aziel Investments"))
            business_tagline = st.text_input("Tagline", value=settings.get("business_tagline", "Smart Retail ERP System"))
            
            primary_color = st.color_picker("Primary Color", value=settings.get("primary_color", "#6366F1"))
            secondary_color = st.color_picker("Secondary Color", value=settings.get("secondary_color", "#8B5CF6"))
            accent_color = st.color_picker("Accent Color", value=settings.get("accent_color", "#FF6584"))
        
        with col2:
            footer_text = st.text_area("Footer Text", value=settings.get("footer_text", "© 2024 Aziel Investments. All rights reserved."))
            receipt_footer = st.text_area("Receipt Footer", value=settings.get("receipt_footer", "Thank you for shopping with us!"))
            email_footer = st.text_area("Email Footer", value=settings.get("email_footer", "Aziel Investments - Smart Retail ERP System"))
        
        st.markdown("### 📄 Branding Options")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            branded_reports = st.checkbox("Branded Reports", value=settings.get("branded_reports", True))
        with col2:
            branded_receipts = st.checkbox("Branded Receipts", value=settings.get("branded_receipts", True))
        with col3:
            branded_emails = st.checkbox("Branded Emails", value=settings.get("branded_emails", True))
        
        if st.button("💾 Save Branding Settings", type="primary", use_container_width=True):
            settings.update({
                "enable_branding": enable_branding,
                "business_name": business_name,
                "business_tagline": business_tagline,
                "primary_color": primary_color,
                "secondary_color": secondary_color,
                "accent_color": accent_color,
                "footer_text": footer_text,
                "receipt_footer": receipt_footer,
                "email_footer": email_footer,
                "branded_reports": branded_reports,
                "branded_receipts": branded_receipts,
                "branded_emails": branded_emails
            })
            save_branding_settings(settings)
            show_toast("Branding updated!", "success")
            st.rerun()
    
    # ==============================
    # TAB 2: LOGO
    # ==============================
    with tab2:
        st.markdown("## 🖼️ Logo Management")
        st.caption("Upload your business logo")
        
        # Current logo
        st.markdown("### Current Logo")
        logo_html = get_logo_html()
        if logo_html:
            st.markdown(logo_html, unsafe_allow_html=True)
        else:
            st.info("No logo uploaded yet")
        
        # Upload new logo
        st.markdown("### Upload New Logo")
        st.caption("Recommended: PNG format, 500x200px or larger")
        
        logo_file = st.file_uploader("Choose logo image", type=["png", "jpg", "jpeg", "svg", "gif"])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Upload Logo", type="primary", use_container_width=True):
                if logo_file:
                    if upload_logo(logo_file):
                        show_toast("Logo updated!", "success")
                        st.rerun()
                    else:
                        show_toast("Failed to upload logo", "error")
                else:
                    show_toast("Please select a logo image", "warning")
        
        with col2:
            if st.button("🗑️ Remove Logo", use_container_width=True):
                settings = load_branding_settings()
                settings["logo_url"] = ""
                save_branding_settings(settings)
                show_toast("Logo removed", "success")
                st.rerun()
    
    # ==============================
    # TAB 3: CUSTOM CSS
    # ==============================
    with tab3:
        st.markdown("## 📝 Custom CSS")
        st.caption("Add custom CSS for advanced branding customization")
        
        st.info("💡 Use custom CSS to fine-tune your brand appearance")
        
        custom_css = st.text_area(
            "Custom CSS",
            value=settings.get("custom_css", ""),
            height=300,
            placeholder="""
/* Example Custom CSS */
.stApp {
    background-color: #f8f9fa;
}
.custom-header {
    font-size: 24px;
    color: #6366F1;
}
            """
        )
        
        if st.button("💾 Save Custom CSS", type="primary", use_container_width=True):
            settings = load_branding_settings()
            settings["custom_css"] = custom_css
            save_branding_settings(settings)
            show_toast("Custom CSS updated!", "success")
            st.rerun()
        
        st.markdown("### 🎨 CSS Examples")
        with st.expander("Show CSS Examples"):
            st.code("""
/* Change sidebar background */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
}

/* Custom font for headers */
h1, h2, h3 {
    font-family: 'Georgia', serif;
    color: #2d2d2d;
}

/* Custom button style */
.stButton > button {
    border-radius: 20px !important;
    padding: 12px 30px !important;
    font-weight: 600 !important;
}

/* Custom card style */
[data-testid="stMetric"] {
    background: white;
    border-radius: 15px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

/* Branded footer */
.custom-footer {
    text-align: center;
    padding: 20px;
    color: #666;
    border-top: 2px solid #6366F1;
    margin-top: 30px;
}
            """, language="css")
    
    # ==============================
    # TAB 4: PREVIEW
    # ==============================
    with tab4:
        st.markdown("## 📋 Branding Preview")
        st.caption("Preview your branding settings")
        
        # Apply branding preview
        apply_branding()
        
        # Preview sections
        st.markdown("### 🏢 Business Identity")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Business Name:** {settings.get('business_name', 'Aziel Investments')}")
        with col2:
            st.markdown(f"**Tagline:** {settings.get('business_tagline', 'Smart Retail ERP System')}")
        with col3:
            st.markdown(f"**Branding:** {'✅ Enabled' if settings.get('enable_branding', True) else '❌ Disabled'}")
        
        st.markdown("### 🎨 Color Palette")
        colors = get_branding_colors()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div style="background: {colors['primary']}; padding: 20px; border-radius: 8px; text-align: center; color: white;">
                Primary<br>
                {colors['primary']}
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="background: {colors['secondary']}; padding: 20px; border-radius: 8px; text-align: center; color: white;">
                Secondary<br>
                {colors['secondary']}
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style="background: {colors['accent']}; padding: 20px; border-radius: 8px; text-align: center; color: white;">
                Accent<br>
                {colors['accent']}
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 📄 Document Previews")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Receipt Footer")
            st.info(settings.get("receipt_footer", "Thank you for shopping with us!"))
        
        with col2:
            st.markdown("#### Email Footer")
            st.info(settings.get("email_footer", "Aziel Investments - Smart Retail ERP System"))
        
        # Export branding settings
        st.markdown("### 📥 Export Branding Settings")
        
        if st.button("📥 Export Branding Settings (JSON)", use_container_width=True):
            json_data = json.dumps(settings, indent=2)
            st.download_button(
                label="💾 Download Settings",
                data=json_data,
                file_name="branding_settings.json",
                mime="application/json"
            )
        
        st.info("💡 Changes made in branding settings will take effect immediately after saving.")


if __name__ == "__main__":
    white_label_dashboard()