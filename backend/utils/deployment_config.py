import streamlit as st
import os
import socket

def get_deployment_info():
    """Get deployment environment information"""
    
    info = {
        "is_cloud": False,
        "url": "http://localhost:8501",
        "hostname": socket.gethostname(),
        "ip_address": socket.gethostbyname(socket.gethostname())
    }
    
    # Check if running on Streamlit Cloud
    if os.environ.get("STREAMLIT_SHARING") or os.environ.get("STREAMLIT_CLOUD"):
        info["is_cloud"] = True
        info["url"] = os.environ.get("STREAMLIT_APP_URL", "https://your-app.streamlit.app")
    
    # Check if running on PythonAnywhere
    if "pythonanywhere" in socket.gethostname():
        info["is_cloud"] = True
        info["url"] = f"https://{os.environ.get('USERNAME', 'yourusername')}.pythonanywhere.com"
    
    return info


def deployment_status_page():
    """Show deployment status and access information"""
    
    st.title("🌐 System Deployment Status")
    
    info = get_deployment_info()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📡 Access Information")
        st.write(f"**Hostname:** {info['hostname']}")
        st.write(f"**IP Address:** {info['ip_address']}")
        st.write(f"**Cloud Deployment:** {'Yes' if info['is_cloud'] else 'No'}")
        
        if info['is_cloud']:
            st.success(f"🌍 **Public URL:** {info['url']}")
        else:
            st.info(f"🏠 **Local URL:** http://localhost:8501")
            st.info(f"🌐 **Network URL:** http://{info['ip_address']}:8501")
    
    with col2:
        st.markdown("### 📱 Mobile Access")
        st.markdown("""
        **To access from mobile:**
        1. Ensure computer and phone are on same WiFi
        2. Open browser on phone
        3. Enter: `http://YOUR_COMPUTER_IP:8501`
        
        **For public access:**
        - Deploy to Streamlit Cloud
        - Share the public URL
        """)
    
    st.markdown("---")
    
    st.markdown("### 🔗 Shareable Links")
    
    if info['is_cloud']:
        st.code(info['url'], language="text")
        st.caption("Share this link with your team members")
    else:
        st.code(f"http://{info['ip_address']}:8501", language="text")
        st.caption("Share this link with users on the same network")