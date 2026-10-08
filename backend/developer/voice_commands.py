# backend/developer/voice_commands.py
# Voice Commands — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> not used here (voice is always a single branch)
#
# Session keys that carry a pending action across a rerun are namespaced by
# branch: `navigate_to_<branch>`, `pos_voice_action_<branch>`, `pos_product_<branch>`.
# This prevents an HO action from leaking into a NAT POS session when an owner
# switches scope.
#
# Custom command vocabulary (data/voice_commands.json) is intentionally GLOBAL:
# the same phrases work in every branch. The actions they trigger always run
# against the current branch.

import streamlit as st
import json
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

from backend.core.db_adapter import load_branches


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
VOICE_SETTINGS_FILE = DATA_DIR / "voice_settings.json"
VOICE_COMMANDS_FILE = DATA_DIR / "voice_commands.json"
VOICE_LOGS_FILE = DATA_DIR / "voice_logs.csv"

VOICE_LOG_COLUMNS = [
    "log_id", "timestamp", "branch_id", "command", "category", "action",
    "parameters", "confidence", "status", "response",
]


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _branch_label(branch_id):
    if not branch_id:
        return "HO"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


def _session_key(base, branch_id):
    """Namespace a session key by branch."""
    return f"{base}_{str(branch_id or 'HO').upper()}"


def _get_scoped_session(base, branch_id, default=None):
    key = _session_key(base, branch_id)
    return st.session_state.get(key, default)


def _set_scoped_session(base, branch_id, value):
    st.session_state[_session_key(base, branch_id)] = value


def _clear_scoped_session(base, branch_id):
    key = _session_key(base, branch_id)
    if key in st.session_state:
        del st.session_state[key]


# ==============================
# INITIALIZATION
# ==============================
def init_voice_files():
    """Initialize voice command files."""
    DATA_DIR.mkdir(exist_ok=True)

    if not VOICE_SETTINGS_FILE.exists():
        settings = {
            "enabled": True,
            "voice_enabled": True,
            "language": "en-US",
            "confidence_threshold": 0.6,
            "continuous_listening": False,
            "auto_complete": True,
            "voice_feedback": True,
        }
        with open(VOICE_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)

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
                "search_product": ["search {product}", "find {product}", "look for {product}"],
            },
            "inventory": {
                "add_stock": ["add stock to {product}", "restock {product}", "increase stock {product}"],
                "view_stock": ["check stock {product}", "how many {product}", "stock of {product}"],
                "add_product": ["add product {product}", "create product {product}", "new product {product}"],
                "delete_product": ["delete product {product}", "remove product {product}"],
            },
            "sales": {
                "today_sales": ["today's sales", "sales today", "show today sales"],
                "weekly_sales": ["this week sales", "weekly sales", "sales this week"],
                "monthly_sales": ["this month sales", "monthly sales", "sales this month"],
                "best_sellers": ["best sellers", "top products", "most sold products"],
                "view_receipt": ["show receipt {number}", "view receipt {number}", "receipt {number}"],
            },
            "customers": {
                "add_customer": ["add customer {name}", "new customer {name}", "create customer {name}"],
                "find_customer": ["find customer {name}", "search customer {name}", "customer {name}"],
                "view_loyalty": ["loyalty points {name}", "points for {name}", "customer points {name}"],
                "add_loyalty": ["add loyalty to {name}", "give points to {name}"],
            },
            "navigation": {
                "go_to_stock": ["go to stock", "stock dashboard", "show stock"],
                "go_to_sales": ["go to sales", "sales dashboard", "show sales"],
                "go_to_pos": ["go to pos", "open pos", "pos"],
                "go_to_customers": ["go to customers", "customer dashboard", "show customers"],
                "go_to_reports": ["go to reports", "reports dashboard", "show reports"],
                "go_to_settings": ["go to settings", "open settings", "settings"],
                "go_to_inventory": ["go to inventory", "open inventory", "inventory"],
                "go_to_dashboard": ["go to dashboard", "home", "main menu"],
                "go_to_purchases": ["go to purchases", "purchases", "purchase orders"],
                "go_to_expenses": ["go to expenses", "expenses", "expense management"],
                "go_to_loyalty": ["go to loyalty", "loyalty", "loyalty program"],
                "go_to_suppliers": ["go to suppliers", "suppliers", "supplier management"],
                "go_to_debtors": ["go to debtors", "debtors", "debt management"],
                "go_to_forecasting": ["go to forecasting", "forecast", "demand forecast"],
                "go_to_live": ["go to live", "live dashboard", "command center"],
            },
            "general": {
                "help": ["help", "what can I do", "commands", "show commands"],
                "cancel": ["cancel", "stop", "nevermind", "forget it"],
                "confirm": ["yes", "confirm", "ok", "sure", "approve"],
                "deny": ["no", "cancel", "deny", "reject", "decline"],
                "logout": ["logout", "sign out", "exit"],
            },
        }
        with open(VOICE_COMMANDS_FILE, "w") as f:
            json.dump(commands, f, indent=2)

    # Migrate voice_logs.csv to include branch_id (auto-migration)
    if not VOICE_LOGS_FILE.exists():
        df = pd.DataFrame(columns=VOICE_LOG_COLUMNS)
        df.to_csv(VOICE_LOGS_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(VOICE_LOGS_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing.to_csv(VOICE_LOGS_FILE, index=False)
        except Exception:
            # If the file is corrupt, start fresh
            df = pd.DataFrame(columns=VOICE_LOG_COLUMNS)
            df.to_csv(VOICE_LOGS_FILE, index=False)


# ==============================
# LOAD / SAVE
# ==============================
def load_voice_settings():
    init_voice_files()
    with open(VOICE_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_voice_settings(settings):
    with open(VOICE_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_voice_commands():
    init_voice_files()
    with open(VOICE_COMMANDS_FILE, "r") as f:
        return json.load(f)


def save_voice_commands(commands):
    with open(VOICE_COMMANDS_FILE, "w") as f:
        json.dump(commands, f, indent=2)


# ==============================
# LOGGING
# ==============================
def log_voice_action(command, category, action, parameters, confidence,
                     status, response, branch_id=None):
    """Log a voice command with its branch. Auto-migrates old files."""
    init_voice_files()

    branch_id = _resolve_branch(branch_id)

    try:
        df = pd.read_csv(VOICE_LOGS_FILE)
        if "branch_id" not in df.columns:
            df.insert(2, "branch_id", "HO")
    except Exception:
        df = pd.DataFrame(columns=VOICE_LOG_COLUMNS)

    new_log = pd.DataFrame([{
        "log_id": f"VL{len(df)+1:08d}",
        "timestamp": datetime.now().isoformat(),
        "branch_id": branch_id,
        "command": command,
        "category": category,
        "action": action,
        "parameters": json.dumps(parameters, default=str),
        "confidence": confidence,
        "status": status,
        "response": response,
    }])

    df = pd.concat([df, new_log], ignore_index=True)
    df.to_csv(VOICE_LOGS_FILE, index=False)


# ==============================
# COMMAND PARSER
# ==============================
def parse_voice_command(text):
    """Parse voice command and extract action. Vocabulary is global."""
    text = text.lower().strip()
    commands = load_voice_commands()

    for category, category_commands in commands.items():
        for action, patterns in category_commands.items():
            for pattern in patterns:
                pattern_clean = (
                    pattern
                    .replace("{product}", "")
                    .replace("{amount}", "")
                    .replace("{number}", "")
                    .replace("{name}", "")
                    .strip()
                )

                if pattern_clean and pattern_clean in text:
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
                        "confidence": 0.8,
                    }

    return None


# ==============================
# COMMAND EXECUTOR
# ==============================
def process_voice_command(parsed_command, branch_id=None):
    """
    Process a parsed voice command in the current branch context.
    Return payload is unchanged; adds 'branch_id' for callers who want it.
    """
    branch_id = _resolve_branch(branch_id)

    category = parsed_command.get("category")
    action = parsed_command.get("action")
    params = parsed_command.get("parameters", {})

    response = {
        "success": False,
        "message": "Command not implemented yet",
        "action": action,
        "params": params,
        "navigate_to": None,
        "navigate_action": None,
        "branch_id": branch_id,
    }

    if category == "pos":
        if action == "add_to_cart":
            product = params.get("product")
            if product:
                response.update({
                    "success": True,
                    "message": f"Added {product} to cart",
                    "navigate_action": "ADD_TO_CART",
                    "product": product,
                })
            else:
                response["message"] = "Which product would you like to add?"

        elif action == "checkout":
            response.update({"success": True, "message": "Proceeding to checkout",
                             "navigate_action": "CHECKOUT"})

        elif action == "clear_cart":
            response.update({"success": True, "message": "Cart cleared",
                             "navigate_action": "CLEAR_CART"})

        elif action == "view_cart":
            response.update({"success": True, "message": "Showing cart contents",
                             "navigate_action": "VIEW_CART"})

        elif action == "search_product":
            product = params.get("product")
            if product:
                response.update({
                    "success": True,
                    "message": f"Searching for {product}",
                    "navigate_action": "SEARCH_PRODUCT",
                    "product": product,
                })

    elif category == "inventory":
        if action == "view_stock":
            product = params.get("product")
            if product:
                response.update({
                    "success": True,
                    "message": f"Checking stock for {product}",
                    "navigate_action": "VIEW_STOCK",
                    "product": product,
                })
            else:
                response["message"] = "Which product would you like to check?"

        elif action == "add_stock":
            product = params.get("product")
            if product:
                response.update({
                    "success": True,
                    "message": f"Adding stock to {product}",
                    "navigate_action": "ADD_STOCK",
                    "product": product,
                })

    elif category == "sales":
        if action == "today_sales":
            response.update({"success": True, "message": "Showing today's sales",
                             "navigate_action": "TODAY_SALES"})
        elif action == "weekly_sales":
            response.update({"success": True, "message": "Showing weekly sales",
                             "navigate_action": "WEEKLY_SALES"})
        elif action == "best_sellers":
            response.update({"success": True, "message": "Showing best selling products",
                             "navigate_action": "BEST_SELLERS"})

    elif category == "customers":
        if action == "find_customer":
            name = params.get("name")
            if name:
                response.update({
                    "success": True,
                    "message": f"Searching for customer {name}",
                    "navigate_action": "FIND_CUSTOMER",
                    "customer_name": name,
                })
            else:
                response["message"] = "Which customer would you like to find?"

        elif action == "add_customer":
            name = params.get("name")
            if name:
                response.update({
                    "success": True,
                    "message": f"Adding customer {name}",
                    "navigate_action": "ADD_CUSTOMER",
                    "customer_name": name,
                })

    elif category == "navigation":
        page_map = {
            "go_to_stock": {"page": "Inventory", "display": "Stock Dashboard"},
            "go_to_sales": {"page": "Sales Dashboard", "display": "Sales Dashboard"},
            "go_to_pos": {"page": "POS", "display": "POS"},
            "go_to_customers": {"page": "Customers", "display": "Customers Dashboard"},
            "go_to_reports": {"page": "Reports", "display": "Reports Dashboard"},
            "go_to_settings": {"page": "Settings", "display": "Settings"},
            "go_to_inventory": {"page": "Inventory", "display": "Inventory"},
            "go_to_dashboard": {"page": "Stock Dashboard", "display": "Stock Dashboard"},
            "go_to_purchases": {"page": "Purchases", "display": "Purchases"},
            "go_to_expenses": {"page": "Expenses", "display": "Expenses"},
            "go_to_loyalty": {"page": "Loyalty", "display": "Loyalty Program"},
            "go_to_suppliers": {"page": "Suppliers", "display": "Supplier Management"},
            "go_to_debtors": {"page": "Debtors", "display": "Debtors Management"},
            "go_to_forecasting": {"page": "Forecasting", "display": "Demand Forecasting"},
            "go_to_live": {"page": "Live Dashboard", "display": "Live Command Center"},
        }
        if action in page_map:
            page_info = page_map[action]
            response.update({
                "success": True,
                "message": f"Navigating to {page_info['display']}",
                "navigate_to": page_info["page"],
                "navigate_action": "NAVIGATE",
            })

    elif category == "general":
        if action == "help":
            response.update({
                "success": True,
                "message": "Available commands: Add product, Checkout, View stock, "
                           "Today's sales, Go to POS, Help, and more",
            })
        elif action == "cancel":
            response.update({"success": True, "message": "Command cancelled",
                             "navigate_action": "CANCEL"})
        elif action == "logout":
            response.update({"success": True, "message": "Logging out...",
                             "navigate_action": "LOGOUT"})

    return response


# ==============================
# TOAST
# ==============================
def show_toast(message, type="info"):
    if type == "success":
        st.success(f"{message}")
    elif type == "error":
        st.error(f"{message}")
    elif type == "warning":
        st.warning(f"{message}")
    else:
        st.info(f"{message}")


# ==============================
# DASHBOARD
# ==============================
def voice_commands_dashboard(branch_id=None):
    st.title("Voice Commands")
    st.caption("Control the system using voice commands — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager", "cashier"]:
        st.error("Access Denied. Voice commands are available to all staff.")
        return

    branch_id = _resolve_branch(branch_id)
    branch_label = _branch_label(branch_id)

    st.caption(f"Voice actions will run against: **{branch_label}**")

    init_voice_files()
    settings = load_voice_settings()

    # Namespaced widget keys so HO/NAT inputs don't collide
    input_key = _session_key("voice_input", branch_id)
    if input_key not in st.session_state:
        st.session_state[input_key] = ""

    tab1, tab2, tab3, tab4 = st.tabs([
        "Voice Control",
        "Available Commands",
        "Command History",
        "Settings",
    ])

    # ==============================
    # TAB 1: VOICE CONTROL
    # ==============================
    with tab1:
        st.markdown("## Voice Control")

        if not settings.get("enabled", True):
            st.warning("Voice commands are disabled. Enable them in Settings.")

        st.markdown(f"""
        ### How to use voice commands:
        1. Click the microphone button below
        2. Speak your command clearly
        3. The system will process it against **{branch_label}**

        ### Example commands:
        - "Add bread to cart"
        - "Checkout"
        - "Today's sales"
        - "Go to POS"
        - "Search for cooking oil"
        - "Go to reports"
        """)

        col1, col2 = st.columns([3, 1])
        with col1:
            voice_text = st.text_input(
                "Type or speak your command",
                placeholder="e.g., Add bread to cart",
                key=input_key,
            )
        with col2:
            # Mic button — unchanged JS, only the "Process" lookup is per-branch
            mic_html = """
            <style>
            .mic-btn { background: linear-gradient(135deg, #6366F1, #8B5CF6); border: none; color: white;
                padding: 12px 20px; border-radius: 50px; font-size: 20px; cursor: pointer;
                margin-top: 25px; width: 100%; transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(99,102,241,0.4); font-weight: bold; }
            .mic-btn:hover { transform: scale(1.05); box-shadow: 0 6px 25px rgba(99,102,241,0.6); }
            .mic-btn.listening { background: linear-gradient(135deg, #EF4444, #DC2626); animation: pulse 1.5s infinite; }
            @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(239,68,68,0.7); }
                70% { box-shadow: 0 0 0 15px rgba(239,68,68,0); }
                100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); } }
            .mic-status { text-align: center; font-size: 12px; margin-top: 5px; min-height: 20px; color: #666; }
            .mic-status.listening { color: #EF4444; font-weight: bold; animation: pulse 1.5s infinite; }
            </style>
            <button class="mic-btn" id="micButton">🎤</button>
            <div class="mic-status" id="micStatus">Click to speak</div>
            <script>
            (function() {
                const micBtn = document.getElementById('micButton');
                const micStatus = document.getElementById('micStatus');
                const inputField = document.querySelector('input[data-testid="stTextInput"]');
                if (!micBtn) return;
                let recognition = null, isListening = false;
                micBtn.addEventListener('click', function() {
                    if (isListening) stopRecognition(); else startRecognition();
                });
                function startRecognition() {
                    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
                    if (!SR) { micStatus.textContent = 'Browser not supported'; return; }
                    recognition = new SR();
                    recognition.lang = 'en-US';
                    recognition.interimResults = true;
                    recognition.continuous = false;
                    recognition.onstart = function() {
                        isListening = true;
                        micBtn.classList.add('listening');
                        micBtn.textContent = '🔴 Stop';
                        micStatus.textContent = 'Speak now...';
                        micStatus.className = 'mic-status listening';
                    };
                    recognition.onresult = function(event) {
                        let transcript = '';
                        for (let i = event.resultIndex; i < event.results.length; i++) {
                            transcript += event.results[i][0].transcript;
                            if (event.results[i].isFinal) {
                                if (inputField) {
                                    inputField.value = transcript;
                                    inputField.dispatchEvent(new Event('input', { bubbles: true }));
                                }
                                micStatus.textContent = '✅ ' + transcript;
                                stopRecognition();
                                setTimeout(function() {
                                    const buttons = document.querySelectorAll('button');
                                    for (let btn of buttons) {
                                        if (btn.textContent.includes('Process')) { btn.click(); break; }
                                    }
                                }, 300);
                            }
                        }
                    };
                    recognition.onerror = function(event) {
                        let msg = event.error;
                        if (msg === 'not-allowed') msg = 'Microphone access denied';
                        else if (msg === 'no-speech') msg = 'No speech detected';
                        micStatus.textContent = '❌ ' + msg;
                        stopRecognition();
                    };
                    recognition.onend = function() { stopRecognition(); };
                    recognition.start();
                }
                function stopRecognition() {
                    isListening = false;
                    micBtn.classList.remove('listening');
                    micBtn.textContent = '🎤';
                    micStatus.textContent = 'Click to speak';
                    micStatus.className = 'mic-status';
                    if (recognition) { try { recognition.stop(); } catch(e) {} recognition = null; }
                }
            })();
            </script>
            """
            st.markdown(mic_html, unsafe_allow_html=True)

        process_key = _session_key("process_voice", branch_id)
        if st.button("Process Command", key=process_key):
            if voice_text:
                with st.spinner(f"Processing command for {branch_label}..."):
                    parsed = parse_voice_command(voice_text)

                    if parsed:
                        st.success(f"Command recognized: {parsed['action'].replace('_', ' ').title()}")
                        result = process_voice_command(parsed, branch_id=branch_id)

                        if result["success"]:
                            st.info(f"Response: {result['message']}")

                            # Pending navigation — branch-namespaced
                            if result.get("navigate_to"):
                                _set_scoped_session("navigate_to", branch_id, result["navigate_to"])
                                st.success(f"Navigating to: {result['navigate_to']}")

                            # Pending POS action — branch-namespaced
                            if result.get("navigate_action") in [
                                "ADD_TO_CART", "CHECKOUT", "CLEAR_CART", "VIEW_CART"
                            ]:
                                _set_scoped_session("pos_voice_action", branch_id,
                                                    result["navigate_action"])
                                if result.get("product"):
                                    _set_scoped_session("pos_product", branch_id,
                                                        result["product"])
                                st.rerun()

                        log_voice_action(
                            voice_text,
                            parsed["category"],
                            parsed["action"],
                            parsed["parameters"],
                            parsed["confidence"],
                            "SUCCESS" if result["success"] else "FAILED",
                            result.get("message", ""),
                            branch_id=branch_id,
                        )
                    else:
                        st.error("Command not recognized. Please try again.")
                        st.info("Try: 'Help' to see available commands")
            else:
                st.warning("Please enter or speak a command first")

        # Show pending navigation for this branch
        pending_nav = _get_scoped_session("navigate_to", branch_id)
        if pending_nav:
            st.info(f"Pending navigation for {branch_label}: {pending_nav}")
            _clear_scoped_session("navigate_to", branch_id)

        # Quick actions
        st.markdown("### Quick Voice Actions")

        col1, col2, col3, col4 = st.columns(4)
        quick_actions = [
            ("Add to Cart", "Add bread to cart"),
            ("Checkout", "Checkout"),
            ("Today's Sales", "Today's sales"),
            ("Go to POS", "Go to POS"),
            ("Go to Reports", "Go to reports"),
            ("Go to Stock", "Go to stock"),
            ("Go to Customers", "Go to customers"),
            ("Help", "Help"),
        ]

        for idx, (label, command) in enumerate(quick_actions):
            cols = [col1, col2, col3, col4]
            with cols[idx % 4]:
                btn_key = _session_key(f"quick_{idx}", branch_id)
                if st.button(label, use_container_width=True, key=btn_key):
                    st.session_state[input_key] = command

    # ==============================
    # TAB 2: AVAILABLE COMMANDS
    # ==============================
    with tab2:
        st.markdown("## Available Voice Commands")
        st.caption("Command vocabulary is shared across all branches.")

        commands = load_voice_commands()
        for category, category_commands in commands.items():
            st.markdown(f"### {category.upper()}")
            for action, patterns in category_commands.items():
                with st.expander(f"{action.replace('_', ' ').title()}"):
                    st.markdown("**Patterns:**")
                    for pattern in patterns:
                        st.code(f"• {pattern}")

    # ==============================
    # TAB 3: COMMAND HISTORY
    # ==============================
    with tab3:
        st.markdown("## Voice Command History")

        if Path(VOICE_LOGS_FILE).exists():
            df = pd.read_csv(VOICE_LOGS_FILE)

            if not df.empty:
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

                # Branch filter for owners
                if "branch_id" in df.columns:
                    branches_present = sorted(df["branch_id"].dropna().unique().tolist())
                    is_owner = st.session_state.get("role", "cashier") in ("owner", "admin")
                    if is_owner and branches_present:
                        filter_choice = st.selectbox(
                            "Filter by branch",
                            ["Current branch"] + branches_present + ["All branches"],
                            key=_session_key("voice_logs_branch_filter", branch_id),
                        )
                        if filter_choice == "Current branch":
                            df = df[df["branch_id"].astype(str).str.upper()
                                    == str(branch_id).upper()]
                        elif filter_choice == "All branches":
                            pass
                        else:
                            df = df[df["branch_id"] == filter_choice]
                    else:
                        # Non-owner: only their own branch
                        df = df[df["branch_id"].astype(str).str.upper()
                                == str(branch_id).upper()]

                display_cols = ["timestamp", "branch_id", "command", "category",
                                "action", "status", "response"]
                available_cols = [c for c in display_cols if c in df.columns]
                st.dataframe(df[available_cols], use_container_width=True, hide_index=True)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export Voice Logs (CSV)",
                    data=csv,
                    file_name=(
                        f"voice_logs_{str(branch_id).upper()}_"
                        f"{datetime.now().strftime('%Y%m%d')}.csv"
                    ),
                    mime="text/csv",
                )
            else:
                st.info(f"No voice command history for {branch_label}")
        else:
            st.info("No voice command history found")

    # ==============================
    # TAB 4: SETTINGS
    # ==============================
    with tab4:
        st.markdown("## Voice Settings")
        st.caption("Voice settings are shared across all branches.")

        col1, col2 = st.columns(2)

        with col1:
            enabled = st.checkbox("Enable Voice Commands", value=settings.get("enabled", True),
                                  key=_session_key("vc_enabled", branch_id))
            voice_enabled = st.checkbox("Enable Voice Feedback",
                                        value=settings.get("voice_enabled", True),
                                        key=_session_key("vc_voice_enabled", branch_id))
            continuous = st.checkbox("Continuous Listening",
                                     value=settings.get("continuous_listening", False),
                                     key=_session_key("vc_continuous", branch_id))

        with col2:
            language = st.selectbox(
                "Language",
                ["en-US", "en-GB", "en-ZA"],
                index=["en-US", "en-GB", "en-ZA"].index(settings.get("language", "en-US")),
                key=_session_key("vc_language", branch_id),
            )
            confidence = st.slider(
                "Confidence Threshold",
                min_value=0.3, max_value=0.9,
                value=float(settings.get("confidence_threshold", 0.6)),
                step=0.1,
                key=_session_key("vc_confidence", branch_id),
            )
            auto_complete = st.checkbox("Auto-complete Commands",
                                        value=settings.get("auto_complete", True),
                                        key=_session_key("vc_auto_complete", branch_id))

        if st.button("Save Voice Settings", type="primary", use_container_width=True,
                     key=_session_key("vc_save", branch_id)):
            settings.update({
                "enabled": enabled,
                "voice_enabled": voice_enabled,
                "language": language,
                "confidence_threshold": confidence,
                "continuous_listening": continuous,
                "auto_complete": auto_complete,
            })
            save_voice_settings(settings)
            st.success("Voice settings saved successfully!")
            show_toast("Voice settings updated!", "success")

        st.markdown("### Add Custom Command")
        st.caption("Custom commands are shared across all branches.")

        col1, col2 = st.columns(2)
        with col1:
            new_category = st.selectbox(
                "Category",
                ["pos", "inventory", "sales", "customers", "navigation", "general"],
                key=_session_key("vc_new_category", branch_id),
            )
            new_action = st.text_input(
                "Action Name", placeholder="my_custom_action",
                key=_session_key("vc_new_action", branch_id),
            )
        with col2:
            new_pattern = st.text_input(
                "Command Pattern", placeholder="my custom command {product}",
                key=_session_key("vc_new_pattern", branch_id),
            )

        if st.button("Add Command", use_container_width=True,
                     key=_session_key("vc_add_command", branch_id)):
            if new_action and new_pattern:
                commands = load_voice_commands()
                commands.setdefault(new_category, {}).setdefault(new_action, [])
                commands[new_category][new_action].append(new_pattern)
                save_voice_commands(commands)
                st.success(f"Command added: {new_action}")
                show_toast("New voice command added!", "success")
                st.rerun()
            else:
                st.error("Please fill all fields")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    voice_commands_dashboard()