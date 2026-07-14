import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
LANGUAGE_FILE = DATA_DIR / "language_settings.json"
TRANSLATIONS_FILE = DATA_DIR / "translations.json"

# ==============================
# LANGUAGE CONSTANTS
# ==============================
LANGUAGES = {
    "en": {
        "name": "English",
        "icon": "🇬🇧",
        "code": "en",
        "direction": "ltr",
        "native_name": "English"
    },
    "sn": {
        "name": "Shona",
        "icon": "🇿🇼",
        "code": "sn",
        "direction": "ltr",
        "native_name": "chiShona"
    },
    "nd": {
        "name": "Ndebele",
        "icon": "🇿🇼",
        "code": "nd",
        "direction": "ltr",
        "native_name": "isiNdebele"
    }
}

# ==============================
# DEFAULT TRANSLATIONS
# ==============================
DEFAULT_TRANSLATIONS = {
    # Navigation
    "nav_dashboard": {"en": "Dashboard", "sn": "Dashboard", "nd": "Dashboard"},
    "nav_stock": {"en": "Stock", "sn": "Zvitoro", "nd": "Isitoko"},
    "nav_inventory": {"en": "Inventory", "sn": "Zvitoro", "nd": "Isitoko"},
    "nav_pos": {"en": "Point of Sale", "sn": "Nzvimbo Yekutengesa", "nd": "Indawo Yokuthengisa"},
    "nav_sales": {"en": "Sales", "sn": "Kutengesa", "nd": "Ukuthengisa"},
    "nav_purchases": {"en": "Purchases", "sn": "Kutenga", "nd": "Ukuthenga"},
    "nav_expenses": {"en": "Expenses", "sn": "Mari Inobuda", "nd": "Izindleko"},
    "nav_customers": {"en": "Customers", "sn": "Vatengi", "nd": "Abathengi"},
    "nav_reports": {"en": "Reports", "sn": "Mishumo", "nd": "Imibiko"},
    "nav_settings": {"en": "Settings", "sn": "Zvirongwa", "nd": "Izilungiselelo"},
    "nav_language": {"en": "🌐 Language", "sn": "🌐 Mutauro", "nd": "🌐 Ulimi"},
    "nav_analytics": {"en": "Analytics", "sn": "Ongororo", "nd": "Ukuhlaziya"},
    "nav_security": {"en": "Security", "sn": "Chengetedzo", "nd": "Ezokuphepha"},
    "nav_bidding": {"en": "Supplier Bidding", "sn": "Kukwikwidza Kwevatengesi", "nd": "Ukubhidana Kwabathengisi"},
    "nav_debtors": {"en": "Debtors", "sn": "Vane Zvikwereti", "nd": "Abakweletayo"},
    "nav_forecasting": {"en": "Forecasting", "sn": "Kufembera", "nd": "Ukubikezela"},
    "nav_live": {"en": "Live Dashboard", "sn": "Live Dashboard", "nd": "Live Dashboard"},
    "nav_suppliers": {"en": "Suppliers", "sn": "Vatengesi", "nd": "Abathengisi"},
    
    # Common Actions
    "action_add": {"en": "Add", "sn": "Wedzera", "nd": "Faka"},
    "action_edit": {"en": "Edit", "sn": "Chinja", "nd": "Hlela"},
    "action_delete": {"en": "Delete", "sn": "Bvisa", "nd": "Susa"},
    "action_save": {"en": "Save", "sn": "Chengeta", "nd": "Gcina"},
    "action_cancel": {"en": "Cancel", "sn": "Ramba", "nd": "Khansela"},
    "action_search": {"en": "Search", "sn": "Tsvaga", "nd": "Sesha"},
    "action_clear": {"en": "Clear", "sn": "Bvisa", "nd": "Sula"},
    "action_confirm": {"en": "Confirm", "sn": "Simbisa", "nd": "Qinisekisa"},
    "action_view": {"en": "View", "sn": "Ona", "nd": "Buka"},
    "action_export": {"en": "Export", "sn": "Tumira", "nd": "Thela"},
    "action_import": {"en": "Import", "sn": "Pinza", "nd": "Ngenisa"},
    "action_print": {"en": "Print", "sn": "Dhindha", "nd": "Phrinta"},
    "action_refresh": {"en": "Refresh", "sn": "Mutsiridza", "nd": "Vuselela"},
    "action_back": {"en": "Back", "sn": "Dzoka", "nd": "Buyela"},
    "action_next": {"en": "Next", "sn": "Inotevera", "nd": "Okulandelayo"},
    
    # POS
    "pos_title": {"en": "Point of Sale", "sn": "Nzvimbo Yekutengesa", "nd": "Indawo Yokuthengisa"},
    "pos_cart": {"en": "Current Cart", "sn": "Tenga Zviri Mutokari", "nd": "Izinga Lokuthenga"},
    "pos_subtotal": {"en": "Subtotal", "sn": "Mutengo Wese", "nd": "Inani Ese"},
    "pos_final_total": {"en": "Final Total", "sn": "Mutengo Wese", "nd": "Isamba Sokugcina"},
    "pos_payment": {"en": "Payment", "sn": "Kubhadhara", "nd": "Inkokhelo"},
    "pos_cash": {"en": "Cash", "sn": "Mari", "nd": "Imali"},
    "pos_credit": {"en": "Credit", "sn": "Chikwereti", "nd": "Isikweleti"},
    "pos_checkout": {"en": "Checkout", "sn": "Bhadhara", "nd": "Khokha"},
    "pos_scan": {"en": "Scan Barcode", "sn": "Skena Bhakodhi", "nd": "Skena Ibhakhodi"},
    "pos_quantity": {"en": "Quantity", "sn": "Huwandu", "nd": "Inani"},
    "pos_price": {"en": "Price", "sn": "Mutengo", "nd": "Inani"},
    "pos_total": {"en": "Total", "sn": "Zvose", "nd": "Isamba"},
    "pos_change": {"en": "Change", "sn": "Kumukira", "nd": "Ukushintsha"},
    "pos_receipt": {"en": "Receipt", "sn": "Risiti", "nd": "Irisiti"},
    "pos_clear_cart": {"en": "Clear Cart", "sn": "Bvisa Mutokari", "nd": "Sula Izinga"},
    
    # Stock
    "stock_dashboard": {"en": "Stock Dashboard", "sn": "Zvitoro", "nd": "Isitoko"},
    "stock_low": {"en": "Low Stock", "sn": "Zvitoro Zvishoma", "nd": "Isitoko Esincane"},
    "stock_out": {"en": "Out of Stock", "sn": "Zvatorwa", "nd": "Akuphelile"},
    "stock_value": {"en": "Stock Value", "sn": "Mutengo Wezvitoro", "nd": "Inani Lesitoko"},
    "stock_add": {"en": "Add Product", "sn": "Wedzera Chigadzirwa", "nd": "Faka Umkhiqizo"},
    "stock_edit": {"en": "Edit Product", "sn": "Chinja Chigadzirwa", "nd": "Hlela Umkhiqizo"},
    "stock_delete": {"en": "Delete Product", "sn": "Bvisa Chigadzirwa", "nd": "Susa Umkhiqizo"},
    "stock_barcode": {"en": "Barcode", "sn": "Bhakodhi", "nd": "Ibhakhodi"},
    "stock_reorder": {"en": "Reorder Level", "sn": "Chiyero Chekudzokorodha", "nd": "Izinga Lokuhlela Kabusha"},
    
    # Customers
    "customer_name": {"en": "Customer Name", "sn": "Zita Remutengi", "nd": "Igama Lomthengi"},
    "customer_phone": {"en": "Phone Number", "sn": "Nhamba Yefoni", "nd": "Inombolo Yocingo"},
    "customer_points": {"en": "Loyalty Points", "sn": "Mapoinzi", "nd": "Amaphoyinti"},
    "customer_tier": {"en": "Tier", "sn": "Chikamu", "nd": "Isigaba"},
    "customer_add": {"en": "Add Customer", "sn": "Wedzera Mutengi", "nd": "Faka Umthengi"},
    "customer_search": {"en": "Search Customer", "sn": "Tsvaga Mutengi", "nd": "Sesha Umthengi"},
    
    # Messages
    "msg_success": {"en": "Success", "sn": "Zvabudirira", "nd": "Kuphumelele"},
    "msg_error": {"en": "Error", "sn": "Kanganiso", "nd": "Iphutha"},
    "msg_warning": {"en": "Warning", "sn": "Yambiro", "nd": "Isixwayiso"},
    "msg_info": {"en": "Information", "sn": "Ruzivo", "nd": "Ulwazi"},
    "msg_loading": {"en": "Loading...", "sn": "Kurodha...", "nd": "Iyalayisha..."},
    "msg_no_data": {"en": "No data available", "sn": "Hapana data", "nd": "Ayikho idatha"},
    "msg_confirm_delete": {"en": "Are you sure you want to delete this?", "sn": "Une chokwadi chekubvisa?", "nd": "Uqinisekile ukuthi uyasusa?"},
    "msg_saved": {"en": "Saved successfully", "sn": "Zvachengetwa zvakanaka", "nd": "Kugcinwe ngempumelelo"},
    "msg_deleted": {"en": "Deleted successfully", "sn": "Zvabviswa zvakanaka", "nd": "Kususiwe ngempumelelo"},
    "msg_error_occurred": {"en": "An error occurred", "sn": "Kanganiso yaitika", "nd": "Kwenzeke iphutha"},
    
    # Buttons
    "btn_login": {"en": "Login", "sn": "Pinda", "nd": "Ngena"},
    "btn_logout": {"en": "Logout", "sn": "Buda", "nd": "Phuma"},
    "btn_register": {"en": "Register", "sn": "Nyorera", "nd": "Bhalisa"},
    "btn_submit": {"en": "Submit", "sn": "Tuma", "nd": "Thumela"},
    "btn_print": {"en": "Print", "sn": "Dhindha", "nd": "Phrinta"},
    "btn_download": {"en": "Download", "sn": "Dhawunirodha", "nd": "Landa"},
    "btn_upload": {"en": "Upload", "sn": "Rodha", "nd": "Layisha"},
    "btn_close": {"en": "Close", "sn": "Vhara", "nd": "Vala"},
    "btn_yes": {"en": "Yes", "sn": "Hongu", "nd": "Yebo"},
    "btn_no": {"en": "No", "sn": "Kwete", "nd": "Cha"},
    "btn_continue": {"en": "Continue", "sn": "Enderera", "nd": "Qhubeka"},
    
    # Time
    "today": {"en": "Today", "sn": "Nhasi", "nd": "Namuhla"},
    "yesterday": {"en": "Yesterday", "sn": "Nezuro", "nd": "Izolo"},
    "this_week": {"en": "This Week", "sn": "Svondo Ino", "nd": "Kuleli Viki"},
    "this_month": {"en": "This Month", "sn": "Mwedzi Uno", "nd": "Kuleli Nyanga"},
    "this_year": {"en": "This Year", "sn": "Gore Rino", "nd": "Kulo Nyaka"},
    "last_week": {"en": "Last Week", "sn": "Svondo Yapfuura", "nd": "Iviki Elidluwe"},
    "last_month": {"en": "Last Month", "sn": "Mwedzi Wapfuura", "nd": "Inyanga Edlule"},
    "last_year": {"en": "Last Year", "sn": "Gore Rapfuura", "nd": "Unyaka Odlule"},
    "custom_range": {"en": "Custom Range", "sn": "Nguva Yako", "nd": "Isikhathi Sakho"},
    
    # Footer
    "footer_copyright": {"en": "All Rights Reserved", "sn": "Kodzero Dzose Dzachengetedzwa", "nd": "Wonke Amalungelo Agodliwe"},
    "footer_version": {"en": "Version", "sn": "Shanduro", "nd": "Inguqulo"},
    "footer_powered": {"en": "Powered by Aziel Investments", "sn": "Inoshandiswa neAziel Investments", "nd": "Iqhutshwa yi-Aziel Investments"},
    
    # Receipt
    "receipt_header": {"en": "AZIEL INVESTMENTS", "sn": "AZIEL INVESTMENTS", "nd": "AZIEL INVESTMENTS"},
    "receipt_thanks": {"en": "THANK YOU FOR SHOPPING!", "sn": "TINOKUTENDA NEKUTENGA!", "nd": "SIYABONGA NGOKUTHENGA!"},
    "receipt_change": {"en": "Change", "sn": "Kumukira", "nd": "Ukushintsha"},
    "receipt_date": {"en": "Date", "sn": "Zuva", "nd": "Usuku"},
    "receipt_time": {"en": "Time", "sn": "Nguva", "nd": "Isikhathi"},
    "receipt_cashier": {"en": "Cashier", "sn": "Mubhadhari", "nd": "Umkhokhi"},
    "receipt_amount": {"en": "Amount", "sn": "Mari", "nd": "Imali"},
    "receipt_balance": {"en": "Balance", "sn": "Chasara", "nd": "Isalela"},
    
    # Debtors
    "debtor_title": {"en": "Debtors Management", "sn": "Manejimendi Yezvikwereti", "nd": "Ukuphathwa Kwezikweleti"},
    "debtor_create": {"en": "Create Debt", "sn": "Gadzira Chikwereti", "nd": "Dala Isikweleti"},
    "debtor_payment": {"en": "Record Payment", "sn": "Rekodha Kubhadhara", "nd": "Rekhoda Inkokhelo"},
    "debtor_overdue": {"en": "Overdue Debts", "sn": "Zvikwereti Zvakanonoka", "nd": "Izikweleti Ezingamangezwa"},
    "debtor_balance": {"en": "Balance", "sn": "Chasara", "nd": "Isalela"},
    "debtor_amount": {"en": "Amount", "sn": "Mari", "nd": "Imali"},
    
    # Forecasting
    "forecast_title": {"en": "Demand Forecasting", "sn": "Kufembera Kwezvinodiwa", "nd": "Ukubikezela Izidingo"},
    "forecast_sales": {"en": "Sales Forecast", "sn": "Kufembera Kutengesa", "nd": "Ukubikezela Ukuthengisa"},
    "forecast_trend": {"en": "Trend", "sn": "Maitiro", "nd": "Ukuthambekela"},
    "forecast_confidence": {"en": "Confidence", "sn": "Chivimbo", "nd": "Ukuzethemba"},
    "forecast_accuracy": {"en": "Accuracy", "sn": "Kururama", "nd": "Ukunemba"},
    
    # Security
    "security_title": {"en": "Security Dashboard", "sn": "Chengetedzo", "nd": "Ezokuphepha"},
    "security_audit": {"en": "Audit Log", "sn": "Rekodhi Yekuongorora", "nd": "Ilogi Yokuhlola"},
    "security_2fa": {"en": "Two-Factor Authentication", "sn": "Kusimbisa Kaviri", "nd": "Ukuqinisekisa Kabili"},
    "security_session": {"en": "Active Sessions", "sn": "Seshoni Dzinoshanda", "nd": "Amaseshini Asebenzayo"},
    "security_whitelist": {"en": "IP Whitelist", "sn": "IP Whitelist", "nd": "IP Whitelist"},
}


def init_language_files():
    """Initialize language files"""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        
        if not TRANSLATIONS_FILE.exists():
            with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_TRANSLATIONS, f, ensure_ascii=False, indent=2)
        
        if not LANGUAGE_FILE.exists():
            settings = {
                "current_language": "en",
                "auto_detect": False,
                "last_updated": datetime.now().isoformat()
            }
            with open(LANGUAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error initializing language files: {e}")


def load_translations():
    """Load all translations"""
    try:
        init_language_files()
        with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading translations: {e}")
        return DEFAULT_TRANSLATIONS


def save_translations(translations):
    """Save translations to file"""
    try:
        with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(translations, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving translations: {e}")
        return False


def get_current_language():
    """Get current language setting"""
    try:
        init_language_files()
        with open(LANGUAGE_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
        return settings.get("current_language", "en")
    except Exception as e:
        print(f"Error getting current language: {e}")
        return "en"


def set_current_language(lang_code):
    """Set current language - FIXED: No rerun here"""
    try:
        init_language_files()
        
        if lang_code not in LANGUAGES:
            lang_code = "en"
        
        with open(LANGUAGE_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
        
        settings["current_language"] = lang_code
        settings["last_updated"] = datetime.now().isoformat()
        
        with open(LANGUAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        
        # Update session state
        st.session_state.current_language = lang_code
        
        return True
    except Exception as e:
        print(f"Error setting current language: {e}")
        return False


def _(key, language=None):
    """Translate a key to current language"""
    if language is None:
        language = get_current_language()
    
    try:
        translations = load_translations()
        
        if key in translations:
            translation = translations[key]
            if language in translation and translation[language]:
                return translation[language]
            elif "en" in translation and translation["en"]:
                return translation["en"]
        
        return key.replace("_", " ").title()
    except Exception:
        return key.replace("_", " ").title()


def get_language_name(lang_code):
    """Get language display name"""
    return LANGUAGES.get(lang_code, {}).get("name", "English")


def get_language_icon(lang_code):
    """Get language icon"""
    return LANGUAGES.get(lang_code, {}).get("icon", "🌐")


def get_available_languages():
    """Get list of available languages"""
    return LANGUAGES


def translate_text(text, target_lang):
    """Simple text translation using dictionary"""
    try:
        translations = load_translations()
        
        for key, value in translations.items():
            if value.get("en", "").lower() == text.lower():
                return value.get(target_lang, text)
        
        return text
    except Exception:
        return text


def init_session_language():
    """Initialize language in session state"""
    if "current_language" not in st.session_state:
        st.session_state.current_language = get_current_language()


def language_selector():
    """Display language selector in sidebar - FIXED: No continuous rerun"""
    
    init_session_language()
    current_lang = get_current_language()
    languages = get_available_languages()
    
    # Create language options
    lang_options = []
    lang_codes = []
    for code, info in languages.items():
        lang_options.append(f"{info['icon']} {info['name']}")
        lang_codes.append(code)
    
    try:
        current_index = lang_codes.index(current_lang)
    except ValueError:
        current_index = 0
    
    # Use a unique key for the selectbox
    selected = st.sidebar.selectbox(
        "Language",
        lang_options,
        index=current_index,
        key="language_selector_unique"
    )
    
    # Get selected language code
    selected_index = lang_options.index(selected)
    selected_code = lang_codes[selected_index]
    
    # Only update if changed and not already in the process
    if selected_code != current_lang:
        if set_current_language(selected_code):
            # Use st.rerun() only once after setting
            st.rerun()


# ==============================
# LANGUAGE DASHBOARD (Admin) - FIXED
# ==============================
def language_dashboard():
    """Language management dashboard for admins - FIXED: No continuous rerun"""
    
    st.title("Language Management")
    st.caption("Manage system languages and translations")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can manage language settings.")
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "Language Settings",
        "Edit Translations",
        "Translation Status"
    ])
    
    # ==============================
    # TAB 1: LANGUAGE SETTINGS - FIXED
    # ==============================
    with tab1:
        st.markdown("## System Language")
        
        current_lang = get_current_language()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Current Language")
            
            for code, info in LANGUAGES.items():
                if code == current_lang:
                    st.success(f"{info['icon']} **{info['name']}** ({info.get('native_name', '')})")
                else:
                    st.write(f"{info['icon']} {info['name']} ({info.get('native_name', '')})")
        
        with col2:
            st.markdown("### Change Language")
            
            for code, info in LANGUAGES.items():
                if st.button(f"{info['icon']} Switch to {info['name']}", key=f"switch_{code}", use_container_width=True):
                    if set_current_language(code):
                        st.success(f"Language changed to {info['name']}")
                        # Use rerun only once after successful change
                        st.rerun()
        
        st.markdown("---")
        
        # Language stats
        st.markdown("### Language Statistics")
        
        translations = load_translations()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Translation Keys", len(translations))
        
        with col2:
            en_complete = sum(1 for t in translations.values() if "en" in t and t["en"])
            st.metric("English Complete", f"{en_complete}/{len(translations)}")
        
        with col3:
            sn_complete = sum(1 for t in translations.values() if "sn" in t and t["sn"])
            st.metric("Shona Complete", f"{sn_complete}/{len(translations)}")
    
    # ==============================
    # TAB 2: EDIT TRANSLATIONS - FIXED
    # ==============================
    with tab2:
        st.markdown("## Edit Translations")
        st.caption("Add or edit translations for any language")
        
        translations = load_translations()
        
        edit_lang = st.selectbox(
            "Select Language",
            list(LANGUAGES.keys()),
            format_func=lambda x: f"{LANGUAGES[x]['icon']} {LANGUAGES[x]['name']}"
        )
        
        search = st.text_input("Search translation key", placeholder="Type to filter...")
        
        st.markdown("### Edit Translations")
        
        filtered_keys = list(translations.keys())
        if search:
            filtered_keys = [k for k in filtered_keys if search.lower() in k.lower()]
        
        # Pagination
        items_per_page = 20
        total_pages = (len(filtered_keys) + items_per_page - 1) // items_per_page if filtered_keys else 1
        
        if total_pages > 1:
            page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(filtered_keys))
            page_keys = filtered_keys[start_idx:end_idx]
        else:
            page_keys = filtered_keys
        
        if not page_keys:
            st.info("No translation keys found")
        else:
            for key in page_keys:
                with st.expander(f"{key}"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        current_value = translations[key].get(edit_lang, "")
                        new_value = st.text_area(
                            f"Translation for {key}",
                            value=current_value,
                            key=f"trans_{key}_{edit_lang}",
                            height=60
                        )
                    
                    with col2:
                        en_value = translations[key].get("en", "")
                        st.caption(f"English: {en_value[:50]}...")
                    
                    if new_value != current_value and new_value:
                        translations[key][edit_lang] = new_value
                        if save_translations(translations):
                            st.success(f"Updated: {key}")
                            # Don't rerun here, let the user continue editing
        
        if len(filtered_keys) > items_per_page:
            st.info(f"Showing {len(page_keys)} of {len(filtered_keys)} keys. Use search to filter.")
        
        # Add new translation key
        st.markdown("---")
        st.markdown("### Add New Translation Key")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_key = st.text_input("Translation Key", placeholder="e.g., new_feature_title")
        
        with col2:
            new_value = st.text_input("English Translation", placeholder="Enter English text")
        
        if st.button("Add New Translation", use_container_width=True):
            if new_key and new_value:
                if new_key in translations:
                    st.warning(f"Key '{new_key}' already exists. Use edit instead.")
                else:
                    translations[new_key] = {"en": new_value}
                    if save_translations(translations):
                        st.success(f"Added new translation key: {new_key}")
                        st.rerun()
            else:
                st.error("Please enter both key and value")
    
    # ==============================
    # TAB 3: TRANSLATION STATUS
    # ==============================
    with tab3:
        st.markdown("## Translation Status")
        
        translations = load_translations()
        
        completion_data = []
        for lang_code, lang_info in LANGUAGES.items():
            total = len(translations)
            completed = sum(1 for t in translations.values() if lang_code in t and t[lang_code])
            completion_data.append({
                "Language": f"{lang_info['icon']} {lang_info['name']}",
                "Code": lang_code,
                "Completed": completed,
                "Total": total,
                "Percentage": (completed / total * 100) if total > 0 else 0
            })
        
        completion_df = pd.DataFrame(completion_data)
        
        st.dataframe(
            completion_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Percentage": st.column_config.ProgressColumn("Completion", format="%.1f%%", min_value=0, max_value=100)
            }
        )
        
        # Missing translations
        st.markdown("### Missing Translations")
        
        missing_lang = st.selectbox(
            "Show missing translations for",
            list(LANGUAGES.keys()),
            format_func=lambda x: f"{LANGUAGES[x]['icon']} {LANGUAGES[x]['name']}"
        )
        
        missing_keys = []
        for key, value in translations.items():
            if missing_lang not in value or not value[missing_lang]:
                missing_keys.append(key)
        
        if missing_keys:
            st.warning(f"{len(missing_keys)} missing translations for {LANGUAGES[missing_lang]['name']}")
            
            missing_text = "\n".join(missing_keys[:100])
            st.text_area("Missing Keys (copy to work offline)", missing_text, height=200)
            
            if st.button("Auto-fill Missing with English", use_container_width=True):
                for key in missing_keys:
                    if "en" in translations[key] and translations[key]["en"]:
                        translations[key][missing_lang] = translations[key]["en"]
                if save_translations(translations):
                    st.success(f"Auto-filled {len(missing_keys)} missing translations")
                    st.rerun()
        else:
            st.success(f"All translations complete for {LANGUAGES[missing_lang]['name']}!")
        
        # Export/Import
        st.markdown("---")
        st.markdown("### Export/Import Translations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            export_data = {"key": [], "en": [], "sn": [], "nd": []}
            for key, value in translations.items():
                export_data["key"].append(key)
                export_data["en"].append(value.get("en", ""))
                export_data["sn"].append(value.get("sn", ""))
                export_data["nd"].append(value.get("nd", ""))
            
            export_df = pd.DataFrame(export_data)
            csv = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Translations (CSV)",
                data=csv,
                file_name=f"translations_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col2:
            uploaded_file = st.file_uploader("Import Translations (CSV)", type=["csv"])
            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file)
                    new_translations = {}
                    for _, row in df.iterrows():
                        key = row.get("key", "")
                        if key:
                            new_translations[key] = {
                                "en": str(row.get("en", "")),
                                "sn": str(row.get("sn", "")),
                                "nd": str(row.get("nd", ""))
                            }
                    if save_translations(new_translations):
                        st.success("Translations imported successfully!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error importing: {e}")


# ==============================
# TRANSLATION HELPER
# ==============================
def tr(key):
    """Shortcut for translation"""
    return _(key)


def apply_language_to_ui():
    """Apply language settings to UI elements"""
    init_session_language()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    language_dashboard()