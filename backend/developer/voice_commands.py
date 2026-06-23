import streamlit as st
import json
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
VOICE_SETTINGS_FILE = DATA_DIR / "voice_settings.json"
VOICE_COMMANDS_FILE = DATA_DIR / "voice_commands.json"
VOICE_LOGS_FILE = DATA_DIR / "voice_logs.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_voice_files():
    """Initialize voice command files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Voice settings
    if not VOICE_SETTINGS_FILE.exists():
        settings = {
            "enabled": True,
            "voice_enabled": True,
            "language": "en-US",
            "confidence_threshold": 0.6,
            "continuous_listening": False,
            "auto_complete": True,
            "voice_feedback": True
        }
        with open(VOICE_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    
    # Voice commands
    if not VOICE_COMMANDS_FILE.exists():
        commands = {
            "pos": {
                "add_to_cart": ["add {product}", "add {product} to cart", "I want {product}", "get me {product}"],
                "remove_from_cart": ["remove {product}", "delete {product}", "take off {product}"],
                "checkout": ["checkout", "pay now", "complete purchase", "finish order"],
                "clear_cart": ["clear cart", "empty cart", "remove all"],
                "view_cart": ["show cart", "view cart", "what's in cart"],
                "apply_discount": ["apply discount {amount}", "discount {amount}", "give discount {amount}"],
                "apply_tax": ["add tax {amount}", "tax {amount}"],
                "search_product": ["search {product}", "find {product}", "look for {product}"]
            },
            "inventory": {
                "add_stock": ["add stock to {product}", "restock {product}", "increase stock {product}"],
                "view_stock": ["check stock {product}", "how many {product}", "stock of {product}"],
                "add_product": ["add product {product}", "create product {product}", "new product {product}"],
                "delete_product": ["delete product {product}", "remove product {product}"]
            },
            "sales": {
                "today_sales": ["today's sales", "sales today", "show today sales"],
                "weekly_sales": ["this week sales", "weekly sales", "sales this week"],
                "monthly_sales": ["this month sales", "monthly sales", "sales this month"],
                "best_sellers": ["best sellers", "top products", "most sold products"],
                "view_receipt": ["show receipt {number}", "view receipt {number}", "receipt {number}"]
            },
            "customers": {
                "add_customer": ["add customer {name}", "new customer {name}", "create customer {name}"],
                "find_customer": ["find customer {name}", "search customer {name}", "customer {name}"],
                "view_loyalty": ["loyalty points {name}", "points for {name}", "customer points {name}"],
                "add_loyalty": ["add loyalty to {name}", "give points to {name}"]
            },
            "navigation": {
                "go_to_stock": ["go to stock", "stock dashboard", "show stock"],
                "go_to_sales": ["go to sales", "sales dashboard", "show sales"],
                "go_to_pos": ["go to pos", "open pos", "pos"],
                "go_to_customers": ["go to customers", "customer dashboard", "show customers"],
                "go_to_reports": ["go to reports", "reports dashboard", "show reports"],
                "go_to_settings": ["go to settings", "open settings", "settings"],
                "go_to_inventory": ["go to inventory", "open inventory", "inventory"],
                "go_to_dashboard": ["go to dashboard", "home", "main menu"]
            },
            "general": {
                "help": ["help", "what can I do", "commands", "show commands"],
                "cancel": ["cancel", "stop", "nevermind", "forget it"],
                "confirm": ["yes", "confirm", "ok", "sure", "approve"],
                "deny": ["no", "cancel", "deny", "reject", "decline"],
                "logout": ["logout", "sign out", "exit"]
            }
        }
        with open(VOICE_COMMANDS_FILE, "w") as f:
            json.dump(commands, f, indent=2)
    
    # Voice logs
    if not VOICE_LOGS_FILE.exists():
        df = pd.DataFrame(columns=[
            "log_id", "timestamp", "command", "category", "action",
            "parameters", "confidence", "status", "response"
        ])
        df.to_csv(VOICE_LOGS_FILE, index=False)


def load_voice_settings():
    """Load voice settings"""
    init_voice_files()
    with open(VOICE_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_voice_settings(settings):
    """Save voice settings"""
    with open(VOICE_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_voice_commands():
    """Load voice commands"""
    init_voice_files()
    with open(VOICE_COMMANDS_FILE, "r") as f:
        return json.load(f)


def save_voice_commands(commands):
    """Save voice commands"""
    with open(VOICE_COMMANDS_FILE, "w") as f:
        json.dump(commands, f, indent=2)


def log_voice_action(command, category, action, parameters, confidence, status, response):
    """Log voice action"""
    df = pd.read_csv(VOICE_LOGS_FILE)
    
    new_log = pd.DataFrame([{
        "log_id": f"VL{len(df)+1:08d}",
        "timestamp": datetime.now().isoformat(),
        "command": command,
        "category": category,
        "action": action,
        "parameters": json.dumps(parameters),
        "confidence": confidence,
        "status": status,
        "response": response
    }])
    
    df = pd.concat([df, new_log], ignore_index=True)
    df.to_csv(VOICE_LOGS_FILE, index=False)


# ==============================
# VOICE COMMAND PARSER
# ==============================
def parse_voice_command(text):
    """Parse voice command and extract action"""
    
    text = text.lower().strip()
    commands = load_voice_commands()
    
    # Try to match against all commands
    for category, category_commands in commands.items():
        for action, patterns in category_commands.items():
            for pattern in patterns:
                pattern_clean = pattern.replace("{product}", "").replace("{amount}", "").replace("{number}", "").replace("{name}", "").strip()
                
                if pattern_clean and pattern_clean in text:
                    # Extract parameters
                    params = {}
                    
                    if "{product}" in pattern:
                        if pattern_clean:
                            product = text.replace(pattern_clean, "").strip()
                            if product:
                                params["product"] = product
                        else:
                            params["product"] = text.strip()
                    
                    if "{amount}" in pattern:
                        amount_match = re.search(r'\d+', text)
                        if amount_match:
                            params["amount"] = float(amount_match.group())
                    
                    if "{number}" in pattern:
                        num_match = re.search(r'\d+', text)
                        if num_match:
                            params["number"] = num_match.group()
                    
                    if "{name}" in pattern:
                        if pattern_clean:
                            name = text.replace(pattern_clean, "").strip()
                            if name:
                                params["name"] = name
                    
                    return {
                        "category": category,
                        "action": action,
                        "parameters": params,
                        "pattern": pattern,
                        "confidence": 0.8
                    }
    
    return None


def process_voice_command(parsed_command):
    """Process the parsed voice command"""
    
    category = parsed_command.get("category")
    action = parsed_command.get("action")
    params = parsed_command.get("parameters", {})
    
    response = {
        "success": False,
        "message": "Command not implemented yet",
        "action": action,
        "params": params
    }
    
    # POS Commands
    if category == "pos":
        if action == "add_to_cart":
            product = params.get("product")
            if product:
                response["success"] = True
                response["message"] = f"Added {product} to cart"
            else:
                response["message"] = "Which product would you like to add?"
        
        elif action == "checkout":
            response["success"] = True
            response["message"] = "Proceeding to checkout"
        
        elif action == "clear_cart":
            response["success"] = True
            response["message"] = "Cart cleared"
        
        elif action == "view_cart":
            response["success"] = True
            response["message"] = "Showing cart contents"
        
        elif action == "search_product":
            product = params.get("product")
            if product:
                response["success"] = True
                response["message"] = f"Searching for {product}"
    
    # Inventory Commands
    elif category == "inventory":
        if action == "view_stock":
            product = params.get("product")
            if product:
                response["success"] = True
                response["message"] = f"Checking stock for {product}"
            else:
                response["message"] = "Which product would you like to check?"
        
        elif action == "add_stock":
            product = params.get("product")
            if product:
                response["success"] = True
                response["message"] = f"Adding stock to {product}"
    
    # Sales Commands
    elif category == "sales":
        if action == "today_sales":
            response["success"] = True
            response["message"] = "Showing today's sales"
        
        elif action == "weekly_sales":
            response["success"] = True
            response["message"] = "Showing weekly sales"
        
        elif action == "best_sellers":
            response["success"] = True
            response["message"] = "Showing best selling products"
    
    # Customers Commands
    elif category == "customers":
        if action == "find_customer":
            name = params.get("name")
            if name:
                response["success"] = True
                response["message"] = f"Searching for customer {name}"
            else:
                response["message"] = "Which customer would you like to find?"
        
        elif action == "add_customer":
            name = params.get("name")
            if name:
                response["success"] = True
                response["message"] = f"Adding customer {name}"
    
    # Navigation Commands
    elif category == "navigation":
        page_map = {
            "go_to_stock": "Stock Dashboard",
            "go_to_sales": "Sales Dashboard",
            "go_to_pos": "POS",
            "go_to_customers": "Customer Dashboard",
            "go_to_reports": "Reports Dashboard",
            "go_to_settings": "Settings",
            "go_to_inventory": "Inventory",
            "go_to_dashboard": "Stock Dashboard"
        }
        
        if action in page_map:
            response["success"] = True
            response["message"] = f"Navigating to {page_map[action]}"
            response["navigate_to"] = page_map[action]
    
    # General Commands
    elif category == "general":
        if action == "help":
            response["success"] = True
            response["message"] = "Available commands: Add product, Checkout, View stock, Today's sales, Go to POS, and more"
        
        elif action == "cancel":
            response["success"] = True
            response["message"] = "Command cancelled"
        
        elif action == "logout":
            response["success"] = True
            response["message"] = "Logging out..."
    
    return response


# ==============================
# TOAST NOTIFICATION
# ==============================
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


# ==============================
# VOICE DASHBOARD
# ==============================
def voice_commands_dashboard():
    """Voice Commands Dashboard"""
    
    st.title("🎤 Voice Commands")
    st.caption("Control the system using voice commands")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager", "cashier"]:
        st.error("❌ Access Denied. Voice commands are available to all staff.")
        return
    
    init_voice_files()
    settings = load_voice_settings()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎤 Voice Control",
        "📋 Available Commands",
        "📜 Command History",
        "⚙️ Settings"
    ])
    
    # ==============================
    # TAB 1: VOICE CONTROL
    # ==============================
    with tab1:
        st.markdown("## 🎤 Voice Control")
        
        if not settings.get("enabled", True):
            st.warning("Voice commands are disabled. Enable them in Settings.")
        
        st.markdown("""
        ### How to use voice commands:
        1. Click the microphone button below
        2. Speak your command clearly
        3. The system will process your command
        4. View the result and response
        
        ### Example commands:
        - "Add bread to cart"
        - "Checkout"
        - "Today's sales"
        - "Go to POS"
        - "Search for cooking oil"
        """)
        
        # Voice input
        col1, col2 = st.columns([3, 1])
        
        with col1:
            voice_text = st.text_input(
                "Type or speak your command",
                placeholder="e.g., Add bread to cart",
                key="voice_input"
            )
        
        with col2:
            # Improved JavaScript with better structure
            st.markdown("""
            <style>
            .mic-btn {
                background: linear-gradient(135deg, #6366F1, #8B5CF6);
                border: none;
                color: white;
                padding: 12px 20px;
                border-radius: 50px;
                font-size: 20px;
                cursor: pointer;
                margin-top: 25px;
                width: 100%;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(99,102,241,0.4);
            }
            .mic-btn:hover {
                transform: scale(1.05);
                box-shadow: 0 6px 25px rgba(99,102,241,0.6);
            }
            .mic-btn:active {
                transform: scale(0.95);
            }
            .mic-btn.listening {
                background: linear-gradient(135deg, #EF4444, #DC2626);
                animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(239,68,68,0.7); }
                70% { box-shadow: 0 0 0 15px rgba(239,68,68,0); }
                100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
            }
            </style>
            
            <button class="mic-btn" id="micButton">🎤</button>
            
            <script>
            (function() {
                const micBtn = document.getElementById('micButton');
                if (!micBtn) return;
                
                // Prevent multiple listeners
                if (micBtn.dataset.listenerAdded) return;
                micBtn.dataset.listenerAdded = 'true';
                
                micBtn.addEventListener('click', function() {
                    const btn = this;
                    
                    // Check if already listening
                    if (btn.dataset.listening === 'true') return;
                    
                    // Check browser support
                    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                    if (!SpeechRecognition) {
                        alert('Voice recognition not supported in this browser. Please type your command.');
                        return;
                    }
                    
                    // Setup recognition
                    const recognition = new SpeechRecognition();
                    recognition.lang = 'en-US';
                    recognition.interimResults = true;
                    recognition.continuous = false;
                    recognition.maxAlternatives = 1;
                    
                    // Visual feedback
                    btn.dataset.listening = 'true';
                    btn.classList.add('listening');
                    btn.textContent = '🔴 Listening...';
                    
                    // Timeout safety (15 seconds)
                    let timeoutId = setTimeout(function() {
                        recognition.stop();
                        resetButton(btn);
                    }, 15000);
                    
                    // Results handler
                    recognition.onresult = function(event) {
                        clearTimeout(timeoutId);
                        let finalTranscript = '';
                        let interimTranscript = '';
                        
                        for (let i = event.resultIndex; i < event.results.length; i++) {
                            const transcript = event.results[i][0].transcript;
                            if (event.results[i].isFinal) {
                                finalTranscript += transcript;
                            } else {
                                interimTranscript += transcript;
                            }
                        }
                        
                        // Update input with final or interim
                        const inputField = document.getElementById('voice_input');
                        if (inputField) {
                            inputField.value = finalTranscript || interimTranscript;
                        }
                        
                        // If we have final result, trigger process
                        if (finalTranscript) {
                            resetButton(btn);
                            // Find and click the process button
                            const buttons = document.querySelectorAll('.stButton button');
                            for (let b of buttons) {
                                if (b.textContent.includes('Process')) {
                                    b.click();
                                    break;
                                }
                            }
                        }
                    };
                    
                    recognition.onerror = function(event) {
                        clearTimeout(timeoutId);
                        resetButton(btn);
                        
                        // User-friendly error messages
                        let errorMsg = '';
                        switch(event.error) {
                            case 'not-allowed':
                                errorMsg = 'Microphone access denied. Please allow microphone access and try again.';
                                break;
                            case 'no-speech':
                                errorMsg = 'No speech detected. Please try again.';
                                break;
                            case 'audio-capture':
                                errorMsg = 'No microphone found. Please connect a microphone and try again.';
                                break;
                            default:
                                errorMsg = 'Error: ' + event.error + '. Please try again or type your command.';
                        }
                        alert(errorMsg);
                    };
                    
                    recognition.onend = function() {
                        clearTimeout(timeoutId);
                        resetButton(btn);
                    };
                    
                    // Start recognition
                    try {
                        recognition.start();
                    } catch (e) {
                        resetButton(btn);
                        alert('Error starting voice recognition. Please try again.');
                    }
                });
                
                function resetButton(btn) {
                    btn.dataset.listening = 'false';
                    btn.classList.remove('listening');
                    btn.textContent = '🎤';
                }
            })();
            </script>
            """, unsafe_allow_html=True)
        
        # Process button and result
        if st.button("🔍 Process Command", key="process_voice"):
            if voice_text:
                with st.spinner("Processing command..."):
                    parsed = parse_voice_command(voice_text)
                    
                    if parsed:
                        st.success(f"✅ Command recognized: {parsed['action'].replace('_', ' ').title()}")
                        
                        result = process_voice_command(parsed)
                        
                        if result["success"]:
                            st.info(f"💬 Response: {result['message']}")
                            
                            if "navigate_to" in result:
                                st.success(f"🔄 Navigating to: {result['navigate_to']}")
                        
                        log_voice_action(
                            voice_text,
                            parsed["category"],
                            parsed["action"],
                            parsed["parameters"],
                            parsed["confidence"],
                            "SUCCESS" if result["success"] else "FAILED",
                            result.get("message", "")
                        )
                    else:
                        st.error("❌ Command not recognized. Please try again.")
                        st.info("💡 Try: 'Help' to see available commands")
            else:
                st.warning("Please enter or speak a command first")
        
        # Quick action buttons
        st.markdown("### ⚡ Quick Voice Actions")
        
        col1, col2, col3, col4 = st.columns(4)
        
        quick_actions = [
            ("📦 Add to Cart", "Add bread to cart"),
            ("💰 Checkout", "Checkout"),
            ("📊 Today's Sales", "Today's sales"),
            ("📱 Go to POS", "Go to POS")
        ]
        
        for idx, (label, command) in enumerate(quick_actions):
            cols = [col1, col2, col3, col4]
            with cols[idx]:
                if st.button(label, use_container_width=True, key=f"quick_{idx}"):
                    st.session_state.voice_input = command
                    st.rerun()
    
    # ==============================
    # TAB 2: AVAILABLE COMMANDS
    # ==============================
    with tab2:
        st.markdown("## 📋 Available Voice Commands")
        
        commands = load_voice_commands()
        
        for category, category_commands in commands.items():
            st.markdown(f"### {category.upper()}")
            
            for action, patterns in category_commands.items():
                with st.expander(f"🎯 {action.replace('_', ' ').title()}"):
                    st.markdown("**Patterns:**")
                    for pattern in patterns:
                        st.code(f"• {pattern}")
    
    # ==============================
    # TAB 3: COMMAND HISTORY
    # ==============================
    with tab3:
        st.markdown("## 📜 Voice Command History")
        
        if Path(VOICE_LOGS_FILE).exists():
            df = pd.read_csv(VOICE_LOGS_FILE)
            
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
                
                st.dataframe(
                    df[["timestamp", "command", "category", "action", "status", "response"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Voice Logs (CSV)",
                    data=csv,
                    file_name=f"voice_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No voice command history found")
        else:
            st.info("No voice command history found")
    
    # ==============================
    # TAB 4: SETTINGS
    # ==============================
    with tab4:
        st.markdown("## ⚙️ Voice Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled = st.checkbox("Enable Voice Commands", value=settings.get("enabled", True))
            voice_enabled = st.checkbox("Enable Voice Feedback", value=settings.get("voice_enabled", True))
            continuous = st.checkbox("Continuous Listening", value=settings.get("continuous_listening", False))
        
        with col2:
            language = st.selectbox(
                "Language",
                ["en-US", "en-GB", "en-ZA"],
                index=["en-US", "en-GB", "en-ZA"].index(settings.get("language", "en-US"))
            )
            confidence = st.slider(
                "Confidence Threshold",
                min_value=0.3,
                max_value=0.9,
                value=float(settings.get("confidence_threshold", 0.6)),
                step=0.1
            )
            auto_complete = st.checkbox("Auto-complete Commands", value=settings.get("auto_complete", True))
        
        if st.button("💾 Save Voice Settings", type="primary", use_container_width=True):
            settings.update({
                "enabled": enabled,
                "voice_enabled": voice_enabled,
                "language": language,
                "confidence_threshold": confidence,
                "continuous_listening": continuous,
                "auto_complete": auto_complete
            })
            save_voice_settings(settings)
            st.success("✅ Voice settings saved successfully!")
            show_toast("Voice settings updated!", "success")
        
        # Add custom command
        st.markdown("### ➕ Add Custom Command")
        
        col1, col2 = st.columns(2)
        with col1:
            new_category = st.selectbox(
                "Category",
                ["pos", "inventory", "sales", "customers", "navigation", "general"]
            )
            new_action = st.text_input("Action Name", placeholder="my_custom_action")
        
        with col2:
            new_pattern = st.text_input("Command Pattern", placeholder="my custom command {product}")
        
        if st.button("➕ Add Command", use_container_width=True):
            if new_action and new_pattern:
                commands = load_voice_commands()
                if new_category not in commands:
                    commands[new_category] = {}
                if new_action not in commands[new_category]:
                    commands[new_category][new_action] = []
                commands[new_category][new_action].append(new_pattern)
                save_voice_commands(commands)
                st.success(f"✅ Command added: {new_action}")
                show_toast("New voice command added!", "success")
                st.rerun()
            else:
                st.error("Please fill all fields")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    voice_commands_dashboard()