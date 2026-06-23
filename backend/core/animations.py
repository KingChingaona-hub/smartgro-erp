import streamlit as st
import time
from datetime import datetime
import random

# ==============================
# LOADING SKELETONS
# ==============================

def loading_skeleton():
    """Display animated loading skeleton"""
    skeleton_html = """
    <style>
    @keyframes shimmer {
        0% { background-position: -200px 0; }
        100% { background-position: 200px 0; }
    }
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200px 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        margin: 10px 0;
    }
    .skeleton-title {
        height: 30px;
        width: 60%;
        margin-bottom: 20px;
    }
    .skeleton-text {
        height: 15px;
        width: 100%;
        margin: 8px 0;
    }
    .skeleton-card {
        height: 150px;
        width: 100%;
        border-radius: 12px;
    }
    .skeleton-chart {
        height: 300px;
        width: 100%;
        border-radius: 12px;
    }
    </style>
    <div class="skeleton skeleton-title"></div>
    <div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-text"></div>
    <div class="skeleton skeleton-text" style="width: 80%;"></div>
    <div class="skeleton skeleton-chart"></div>
    """
    return skeleton_html

def with_loading_spinner(message="Loading..."):
    """Decorator/context manager for loading states"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with st.spinner(message):
                return func(*args, **kwargs)
        return wrapper
    return decorator

# ==============================
# TOAST NOTIFICATIONS
# ==============================

def show_toast(message, type="success", duration=3000):
    """Show animated toast notification"""
    
    colors = {
        "success": "#10B981",
        "error": "#EF4444",
        "warning": "#F59E0B",
        "info": "#3B82F6"
    }
    
    toast_html = f"""
    <style>
    @keyframes slideInRight {{
        0% {{
            transform: translateX(100%);
            opacity: 0;
        }}
        100% {{
            transform: translateX(0);
            opacity: 1;
        }}
    }}
    @keyframes fadeOut {{
        0% {{
            opacity: 1;
        }}
        100% {{
            opacity: 0;
            display: none;
        }}
    }}
    .toast-notification {{
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        border-left: 4px solid {colors[type]};
        border-radius: 8px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        animation: slideInRight 0.3s ease-out;
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 300px;
    }}
    .toast-icon {{
        font-size: 24px;
    }}
    .toast-message {{
        color: #1f2937;
        font-size: 14px;
        margin: 0;
    }}
    </style>
    <div class="toast-notification" id="toast">
        <div class="toast-icon">{get_toast_icon(type)}</div>
        <p class="toast-message">{message}</p>
    </div>
    <script>
        setTimeout(function() {{
            var toast = document.getElementById('toast');
            if(toast) {{
                toast.style.animation = 'fadeOut 0.3s ease-out';
                setTimeout(function() {{
                    toast.remove();
                }}, 300);
            }}
        }}, {duration});
    </script>
    """
    st.markdown(toast_html, unsafe_allow_html=True)

def get_toast_icon(type):
    icons = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️"
    }
    return icons.get(type, "✅")

# ==============================
# CONFETTI EFFECTS
# ==============================

def show_confetti():
    """Display confetti animation for achievements"""
    confetti_html = """
    <style>
    @keyframes confetti-fall {
        0% { transform: translateY(-100px) rotate(0deg); opacity: 1; }
        100% { transform: translateY(100vh) rotate(360deg); opacity: 0; }
    }
    .confetti {
        position: fixed;
        top: -100px;
        width: 10px;
        height: 10px;
        background: #ff0000;
        animation: confetti-fall 3s linear forwards;
        z-index: 10000;
        pointer-events: none;
    }
    </style>
    <script>
        function createConfetti() {
            const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff', '#ffa500', '#ff69b4'];
            for(let i = 0; i < 150; i++) {
                const confetti = document.createElement('div');
                confetti.className = 'confetti';
                confetti.style.left = Math.random() * 100 + '%';
                confetti.style.animationDuration = (Math.random() * 2 + 2) + 's';
                confetti.style.animationDelay = Math.random() * 1 + 's';
                confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
                confetti.style.width = (Math.random() * 8 + 4) + 'px';
                confetti.style.height = (Math.random() * 8 + 4) + 'px';
                document.body.appendChild(confetti);
                setTimeout(() => confetti.remove(), 3000);
            }
        }
        createConfetti();
    </script>
    """
    st.markdown(confetti_html, unsafe_allow_html=True)

# ==============================
# PAGE TRANSITIONS
# ==============================

def page_transition():
    """Add smooth page transition effects"""
    transition_html = """
    <style>
    @keyframes fadeInUp {
        0% {
            opacity: 0;
            transform: translateY(20px);
        }
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }
    @keyframes fadeIn {
        0% { opacity: 0; }
        100% { opacity: 1; }
    }
    .main .block-container {
        animation: fadeInUp 0.5s ease-out;
    }
    [data-testid="stSidebar"] {
        animation: fadeIn 0.3s ease-out;
    }
    .stButton > button {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stButton > button:active {
        transform: scale(0.95);
    }
    </style>
    """
    st.markdown(transition_html, unsafe_allow_html=True)

# ==============================
# ANIMATED METRICS
# ==============================

def animated_metric(label, value, delta=None, animation_duration=1000):
    """Display animated counter for metrics"""
    
    # Random ID for this metric
    metric_id = f"metric_{random.randint(1000, 9999)}"
    
    animation_html = f"""
    <style>
    @keyframes countUp {{
        from {{
            opacity: 0;
            transform: translateY(20px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    .animated-metric {{
        animation: countUp 0.5s ease-out;
    }}
    </style>
    <div class="animated-metric" id="{metric_id}">
    """
    
    st.markdown(animation_html, unsafe_allow_html=True)
    
    # Display the metric
    if delta:
        st.metric(label, value, delta)
    else:
        st.metric(label, value)
    
    st.markdown("</div>", unsafe_allow_html=True)

# ==============================
# ANIMATED CHART WRAPPER
# ==============================

def animated_chart(chart_func, *args, **kwargs):
    """Wrap any plotly chart with animation"""
    chart_html = """
    <style>
    @keyframes chartFadeIn {
        0% {
            opacity: 0;
            transform: scale(0.95);
        }
        100% {
            opacity: 1;
            transform: scale(1);
        }
    }
    .chart-container {
        animation: chartFadeIn 0.6s ease-out;
    }
    </style>
    <div class="chart-container">
    """
    st.markdown(chart_html, unsafe_allow_html=True)
    
    # Call the chart function
    result = chart_func(*args, **kwargs)
    
    st.markdown("</div>", unsafe_allow_html=True)
    return result

# ==============================
# HOVER EFFECTS FOR CARDS
# ==============================

def add_hover_effects():
    """Add hover effects to cards and buttons"""
    hover_html = """
    <style>
    [data-testid="stMetric"] {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.02);
    }
    .stExpander {
        transition: all 0.3s ease;
    }
    .stExpander:hover {
        transform: translateX(5px);
    }
    div[data-testid="stExpander"]:hover {
        border-color: #6366F1;
    }
    </style>
    """
    st.markdown(hover_html, unsafe_allow_html=True)

# ==============================
# PROGRESS ANIMATION
# ==============================

def animated_progress(value, max_value=100, height="20px", color="#6366F1"):
    """Display animated progress bar"""
    percentage = (value / max_value) * 100
    
    progress_html = f"""
    <style>
    @keyframes fillProgress {{
        0% {{ width: 0%; }}
        100% {{ width: {percentage}%; }}
    }}
    .progress-container {{
        background: #e5e7eb;
        border-radius: 999px;
        height: {height};
        overflow: hidden;
        margin: 10px 0;
    }}
    .progress-fill {{
        background: {color};
        border-radius: 999px;
        height: 100%;
        width: 0%;
        animation: fillProgress 1s ease-out forwards;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 12px;
        font-weight: bold;
    }}
    </style>
    <div class="progress-container">
        <div class="progress-fill" style="width: {percentage}%;">
            {percentage:.1f}%
        </div>
    </div>
    """
    st.markdown(progress_html, unsafe_allow_html=True)

# ==============================
# PULSE ANIMATION FOR ALERTS
# ==============================

def pulse_animation():
    """Add pulse animation for alerts"""
    pulse_html = """
    <style>
    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
        }
    }
    .pulse-alert {
        animation: pulse 2s infinite;
        border-radius: 12px;
    }
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    .blink {
        animation: blink 1s infinite;
    }
    </style>
    """
    st.markdown(pulse_html, unsafe_allow_html=True)

# ==============================
# RIPPLE EFFECT FOR BUTTONS
# ==============================

def ripple_effect():
    """Add ripple effect to buttons"""
    ripple_html = """
    <style>
    .stButton > button {
        position: relative;
        overflow: hidden;
    }
    .stButton > button:after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.5);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }
    .stButton > button:active:after {
        width: 300px;
        height: 300px;
    }
    </style>
    """
    st.markdown(ripple_html, unsafe_allow_html=True)

# ==============================
# FLOATING ACTION BUTTON
# ==============================

def floating_action_button(icon="➕", label="Action", link="#"):
    """Create floating action button"""
    fab_html = f"""
    <style>
    @keyframes float {{
        0% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-10px); }}
        100% {{ transform: translateY(0px); }}
    }}
    .fab {{
        position: fixed;
        bottom: 30px;
        right: 30px;
        background: #6366F1;
        color: white;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: all 0.3s;
        z-index: 1000;
        animation: float 2s ease-in-out infinite;
    }}
    .fab:hover {{
        transform: scale(1.1);
        background: #4F46E5;
    }}
    </style>
    <a href="{link}" target="_self">
        <div class="fab" title="{label}">
            <span style="font-size: 24px;">{icon}</span>
        </div>
    </a>
    """
    st.markdown(fab_html, unsafe_allow_html=True)

# ==============================
# INITIALIZE ALL ANIMATIONS
# ==============================

def init_animations():
    """Initialize all animation effects"""
    page_transition()
    add_hover_effects()
    pulse_animation()
    ripple_effect()