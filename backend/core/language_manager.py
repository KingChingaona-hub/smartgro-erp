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
        "direction": "ltr"
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
    
    # Common Actions
    "action_add": {"en": "Add", "sn": "Wedzera", "nd": "Faka"},
    "action_edit": {"en": "Edit", "sn": "Chinja", "nd": "Hlela"},
    "action_delete": {"en": "Delete", "sn": "Bvisa", "nd": "Susa"},
    "action_save": {"en": "Save", "sn": "Chengeta", "nd": "Gcina"},
    "action_cancel": {"en": "Cancel", "sn": "Ramba", "nd": "Khansela"},
    "action_search": {"en": "Search", "sn": "Tsvaga", "nd": "Sesha"},
    "action_clear": {"en": "Clear", "sn": "Bvisa", "nd": "Sula"},
    "action_confirm": {"en": "Confirm", "sn": "Simbisa", "nd": "Qinisekisa"},
    
    # POS
    "pos_title": {"en": "Point of Sale", "sn": "Nzvimbo Yekutengesa", "nd": "Indawo Yokuthengisa"},
    "pos_cart": {"en": "Current Cart", "sn": "Tenga Zviri Mutokari", "nd": "Izinga Lokuthenga"},
    "pos_subtotal": {"en": "Subtotal", "sn": "Mutengo Wese", "nd": "Inani Ese"},
    "pos_final_total": {"en": "Final Total", "sn": "Mutengo Wese", "nd": "Isamba Sokugcina"},
    "pos_payment": {"en": "Payment", "sn": "Kubhadhara", "nd": "Inkokhelo"},
    "pos_cash": {"en": "Cash", "sn": "Mari", "nd": "Imali"},
    "pos_credit": {"en": "Credit", "sn": "Chikwereti", "nd": "Isikweleti"},
    "pos_checkout": {"en": "Checkout", "sn": "Bhadhara", "nd": "Khokha"},
    
    # Stock
    "stock_dashboard": {"en": "Stock Dashboard", "sn": "Zvitoro", "nd": "Isitoko"},
    "stock_low": {"en": "Low Stock", "sn": "Zvitoro Zvishoma", "nd": "Isitoko Esincane"},
    "stock_out": {"en": "Out of Stock", "sn": "Zvatorwa", "nd": "Akuphelile"},
    "stock_value": {"en": "Stock Value", "sn": "Mutengo Wezvitoro", "nd": "Inani Lesitoko"},
    
    # Customers
    "customer_name": {"en": "Customer Name", "sn": "Zita Remutengi", "nd": "Igama Lomthengi"},
    "customer_phone": {"en": "Phone Number", "sn": "Nhamba Yefoni", "nd": "Inombolo Yocingo"},
    "customer_points": {"en": "Loyalty Points", "sn": "Mapoinzi", "nd": "Amaphoyinti"},
    "customer_tier": {"en": "Tier", "sn": "Chikamu", "nd": "Isigaba"},
    
    # Messages
    "msg_success": {"en": "Success", "sn": "Zvabudirira", "nd": "Kuphumelele"},
    "msg_error": {"en": "Error", "sn": "Kanganiso", "nd": "Iphutha"},
    "msg_warning": {"en": "Warning", "sn": "Yambiro", "nd": "Isixwayiso"},
    "msg_info": {"en": "Information", "sn": "Ruzivo", "nd": "Ulwazi"},
    "msg_loading": {"en": "Loading...", "sn": "Kurodha...", "nd": "Iyalayisha..."},
    "msg_no_data": {"en": "No data available", "sn": "Hapana data", "nd": "Ayikho idatha"},
    
    # Buttons
    "btn_login": {"en": "Login", "sn": "Pinda", "nd": "Ngena"},
    "btn_logout": {"en": "Logout", "sn": "Buda", "nd": "Phuma"},
    "btn_register": {"en": "Register", "sn": "Nyorera", "nd": "Bhalisa"},
    "btn_submit": {"en": "Submit", "sn": "Tuma", "nd": "Thumela"},
    "btn_print": {"en": "Print", "sn": "Dhindha", "nd": "Phrinta"},
    "btn_download": {"en": "Download", "sn": "Dhawunirodha", "nd": "Landa"},
    
    # Time
    "today": {"en": "Today", "sn": "Nhasi", "nd": "Namuhla"},
    "yesterday": {"en": "Yesterday", "sn": "Nezuro", "nd": "Izolo"},
    "this_week": {"en": "This Week", "sn": "Svondo Ino", "nd": "Kuleli Viki"},
    "this_month": {"en": "This Month", "sn": "Mwedzi Uno", "nd": "Kuleli Nyanga"},
    "this_year": {"en": "This Year", "sn": "Gore Rino", "nd": "Kulo Nyaka"},
    
    # Footer
    "footer_copyright": {"en": "All Rights Reserved", "sn": "Kodzero Dzose Dzachengetedzwa", "nd": "Wonke Amalungelo Agodliwe"},
    "footer_version": {"en": "Version", "sn": "Shanduro", "nd": "Inguqulo"},
    
    # Receipt
    "receipt_header": {"en": "AZIEL INVESTMENTS", "sn": "AZIEL INVESTMENTS", "nd": "AZIEL INVESTMENTS"},
    "receipt_thanks": {"en": "THANK YOU FOR SHOPPING!", "sn": "TINOKUTENDA NEKUTENGA!", "nd": "SIYABONGA NGOKUTHENGA!"},
    "receipt_change": {"en": "Change", "sn": "Kumukira", "nd": "Ukushintsha"},
}


def init_language_files():
    """Initialize language files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Create translations file if not exists
    if not TRANSLATIONS_FILE.exists():
        with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_TRANSLATIONS, f, ensure_ascii=False, indent=2)
    
    # Create language settings file if not exists
    if not LANGUAGE_FILE.exists():
        settings = {
            "current_language": "en",
            "auto_detect": True,
            "last_updated": datetime.now().isoformat()
        }
        with open(LANGUAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)


def load_translations():
    """Load all translations"""
    init_language_files()
    with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_translations(translations):
    """Save translations to file"""
    with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)


def get_current_language():
    """Get current language setting"""
    init_language_files()
    with open(LANGUAGE_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings.get("current_language", "en")


def set_current_language(lang_code):
    """Set current language"""
    init_language_files()
    with open(LANGUAGE_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
    
    settings["current_language"] = lang_code
    settings["last_updated"] = datetime.now().isoformat()
    
    with open(LANGUAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    
    # Update session state
    st.session_state.current_language = lang_code


def _(key, language=None):
    """Translate a key to current language"""
    if language is None:
        language = get_current_language()
    
    translations = load_translations()
    
    if key in translations:
        translation = translations[key]
        if language in translation:
            return translation[language]
        elif "en" in translation:
            return translation["en"]
    
    # Return key if translation not found
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
    translations = load_translations()
    
    # Search for the text in translations
    for key, value in translations.items():
        if value.get("en", "").lower() == text.lower():
            return value.get(target_lang, text)
    
    return text


def language_selector():
    """Display language selector in sidebar"""
    
    current_lang = get_current_language()
    languages = get_available_languages()
    
    # Create language options
    lang_options = []
    for code, info in languages.items():
        lang_options.append(f"{info['icon']} {info['name']}")
    
    current_index = list(languages.keys()).index(current_lang)
    
    selected = st.sidebar.selectbox(
        _("nav_language"),
        lang_options,
        index=current_index,
        key="language_selector"
    )
    
    # Get selected language code
    selected_code = list(languages.keys())[lang_options.index(selected)]
    
    if selected_code != current_lang:
        set_current_language(selected_code)
        st.rerun()


# ==============================
# LANGUAGE DASHBOARD (Admin)
# ==============================
def language_dashboard():
    """Language management dashboard for admins"""
    
    st.title("🌐 Language Management")
    st.caption("Manage system languages and translations")
    
    role = st.session_state.get("role", "cashier")
    
    # Only owner and managers can access language settings
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can manage language settings.")
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "🌍 Language Settings",
        "📝 Edit Translations",
        "📊 Translation Status"
    ])
    
    # ==============================
    # TAB 1: LANGUAGE SETTINGS
    # ==============================
    with tab1:
        st.markdown("## 🌍 System Language")
        
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
                    set_current_language(code)
                    st.success(f"Language changed to {info['name']}")
                    st.rerun()
        
        st.markdown("---")
        
        # Language stats
        st.markdown("### 📊 Language Statistics")
        
        translations = load_translations()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Translation Keys", len(translations))
        
        with col2:
            en_complete = sum(1 for t in translations.values() if "en" in t)
            st.metric("English Complete", f"{en_complete}/{len(translations)}")
        
        with col3:
            sn_complete = sum(1 for t in translations.values() if "sn" in t)
            st.metric("Shona Complete", f"{sn_complete}/{len(translations)}")
    
    # ==============================
    # TAB 2: EDIT TRANSLATIONS
    # ==============================
    with tab2:
        st.markdown("## 📝 Edit Translations")
        st.caption("Add or edit translations for any language")
        
        translations = load_translations()
        
        # Select language to edit
        edit_lang = st.selectbox(
            "Select Language",
            list(LANGUAGES.keys()),
            format_func=lambda x: f"{LANGUAGES[x]['icon']} {LANGUAGES[x]['name']}"
        )
        
        # Search/filter
        search = st.text_input("Search translation key", placeholder="Type to filter...")
        
        # Display editable table
        st.markdown("### Edit Translations")
        
        filtered_keys = list(translations.keys())
        if search:
            filtered_keys = [k for k in filtered_keys if search.lower() in k.lower()]
        
        # Show limited number for performance
        for key in filtered_keys[:50]:
            with st.expander(f"🔑 {key}"):
                current_value = translations[key].get(edit_lang, "")
                new_value = st.text_area(
                    f"Translation for {key}",
                    value=current_value,
                    key=f"trans_{key}_{edit_lang}",
                    height=60
                )
                
                if new_value != current_value:
                    translations[key][edit_lang] = new_value
                    save_translations(translations)
                    st.success(f"Updated: {key}")
        
        if len(filtered_keys) > 50:
            st.info(f"Showing 50 of {len(filtered_keys)} keys. Use search to filter.")
        
        # Add new translation key
        st.markdown("---")
        st.markdown("### ➕ Add New Translation Key")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_key = st.text_input("Translation Key", placeholder="e.g., new_feature_title")
        
        with col2:
            new_value = st.text_input("English Translation", placeholder="Enter English text")
        
        if st.button("➕ Add New Translation", use_container_width=True):
            if new_key and new_value:
                translations[new_key] = {"en": new_value}
                save_translations(translations)
                st.success(f"Added new translation key: {new_key}")
                st.rerun()
            else:
                st.error("Please enter both key and value")
    
    # ==============================
    # TAB 3: TRANSLATION STATUS
    # ==============================
    with tab3:
        st.markdown("## 📊 Translation Status")
        
        translations = load_translations()
        
        # Calculate completion for each language
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
        st.markdown("### 📋 Missing Translations")
        
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
            
            # Show missing keys in a text area for copying
            missing_text = "\n".join(missing_keys[:100])
            st.text_area("Missing Keys (copy to work offline)", missing_text, height=200)
            
            # Option to auto-fill with English
            if st.button("📝 Auto-fill Missing with English", use_container_width=True):
                for key in missing_keys:
                    if "en" in translations[key]:
                        translations[key][missing_lang] = translations[key]["en"]
                save_translations(translations)
                st.success(f"Auto-filled {len(missing_keys)} missing translations")
                st.rerun()
        else:
            st.success(f"✅ All translations complete for {LANGUAGES[missing_lang]['name']}!")
        
        # Export/Import
        st.markdown("---")
        st.markdown("### 📥 Export/Import Translations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv = pd.DataFrame(translations).T.reset_index().to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Translations (CSV)",
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
                        key = row.get("index", row.get("key", ""))
                        if key:
                            new_translations[key] = {
                                "en": row.get("en", ""),
                                "sn": row.get("sn", ""),
                                "nd": row.get("nd", "")
                            }
                    save_translations(new_translations)
                    st.success("Translations imported successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error importing: {e}")


# ==============================
# TRANSLATION HELPER FOR STREAMLIT
# ==============================
def tr(key):
    """Shortcut for translation - use in all UI components"""
    return _(key)


def apply_language_to_ui():
    """Apply language settings to UI elements (to be called in each page)"""
    pass


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    language_dashboard()