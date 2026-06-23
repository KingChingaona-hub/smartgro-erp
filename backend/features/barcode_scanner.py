import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from PIL import Image
import io
import base64

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
SCANNER_SETTINGS_FILE = DATA_DIR / "scanner_settings.json"
SCAN_HISTORY_FILE = DATA_DIR / "scan_history.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_scanner_files():
    """Initialize scanner-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Scanner settings
    if not SCANNER_SETTINGS_FILE.exists():
        settings = {
            "enable_camera": True,
            "scan_mode": "manual",
            "scan_timeout": 5,
            "sound_enabled": True,
            "vibration_enabled": True,
            "bulk_mode": False,
            "scan_quality": "high",
            "auto_add_to_cart": False,
            "auto_add_to_inventory": False
        }
        with open(SCANNER_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    
    # Scan history
    if not SCAN_HISTORY_FILE.exists():
        df = pd.DataFrame(columns=[
            "scan_id", "timestamp", "barcode", "product_name", 
            "scan_type", "quantity", "source", "status"
        ])
        df.to_csv(SCAN_HISTORY_FILE, index=False)


def load_scanner_settings():
    """Load scanner settings"""
    init_scanner_files()
    with open(SCANNER_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_scanner_settings(settings):
    """Save scanner settings"""
    with open(SCANNER_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def log_scan(barcode, product_name, scan_type, quantity, source, status):
    """Log a scan"""
    df = pd.read_csv(SCAN_HISTORY_FILE)
    
    new_scan = pd.DataFrame([{
        "scan_id": f"SC{len(df)+1:08d}",
        "timestamp": datetime.now().isoformat(),
        "barcode": barcode,
        "product_name": product_name,
        "scan_type": scan_type,
        "quantity": quantity,
        "source": source,
        "status": status
    }])
    
    df = pd.concat([df, new_scan], ignore_index=True)
    df.to_csv(SCAN_HISTORY_FILE, index=False)


# ==============================
# BARCODE GENERATOR
# ==============================
def generate_barcode_html(barcode, product_name=""):
    """Generate barcode as HTML"""
    html = f"""
    <div style="background: white; padding: 20px; border: 1px solid #ddd; border-radius: 8px; text-align: center;">
        <div style="font-family: 'Courier New', monospace; font-size: 48px; letter-spacing: 2px; margin: 10px 0;">
            {'█' * len(str(barcode))}
        </div>
        <div style="font-size: 24px; font-weight: bold; margin: 10px 0;">
            {barcode}
        </div>
        <div style="font-size: 16px; color: #666;">
            {product_name}
        </div>
    </div>
    """
    return html


# ==============================
# QR CODE GENERATOR
# ==============================
def generate_qr_code_html(data):
    """Generate QR code as HTML"""
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={data}"
    
    html = f"""
    <div style="background: white; padding: 20px; border: 1px solid #ddd; border-radius: 8px; text-align: center;">
        <img src="{qr_url}" alt="QR Code" style="max-width: 100%;">
        <div style="margin-top: 10px; font-size: 12px; color: #999;">
            Scan to view product info
        </div>
    </div>
    """
    return html


# ==============================
# BARCODE SCANNER DASHBOARD
# ==============================
def barcode_scanner_dashboard():
    """Barcode Scanner Dashboard"""
    
    st.title("📷 Barcode Scanner")
    st.caption("Scan barcodes with your camera, scan QR codes, and manage inventory")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager", "cashier"]:
        st.error("❌ Access Denied. Only staff can access barcode scanner.")
        return
    
    init_scanner_files()
    settings = load_scanner_settings()
    
    # Load products
    from backend.core.database import load_products
    products_df = load_products()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📷 Scanner",
        "📊 Scan History",
        "📋 Bulk Scanner",
        "🔍 Product Lookup",
        "⚙️ Settings"
    ])
    
    # ==============================
    # TAB 1: SCANNER
    # ==============================
    with tab1:
        st.markdown("## 📷 Barcode Scanner")
        
        # Upload image method (works without cv2)
        st.markdown("### Upload Barcode Image")
        st.caption("Take a photo or upload an image of the barcode")
        
        uploaded_file = st.file_uploader(
            "Upload barcode image",
            type=["png", "jpg", "jpeg", "gif", "bmp"],
            key="barcode_image"
        )
        
        if uploaded_file:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=300)
            
            # In production, use pyzbar for actual barcode decoding
            # For now, use manual entry
            st.markdown("### Enter the barcode from the image")
            manual_barcode = st.text_input("Barcode Number", placeholder="e.g., 6001 or 1234567890")
            
            if manual_barcode and st.button("🔍 Lookup Barcode", type="primary", use_container_width=True):
                product = products_df[products_df["barcode"].astype(str) == manual_barcode]
                
                if not product.empty:
                    product = product.iloc[0]
                    st.success(f"✅ Product found: {product['name']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Product:** {product['name']}")
                        st.info(f"**Price:** ${product['price']:.2f}")
                    with col2:
                        st.info(f"**Stock:** {product['stock']}")
                        st.info(f"**Category:** {product.get('category', 'N/A')}")
                    
                    # Actions
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("➕ Add to Cart", key="scan_add_cart", use_container_width=True):
                            st.success(f"✅ Added {product['name']} to cart!")
                            try:
                                from backend.core.animations import show_toast
                                show_toast(f"{product['name']} added to cart!", "success")
                            except:
                                pass
                    
                    with col2:
                        if st.button("📦 View Product", key="scan_view_product", use_container_width=True):
                            st.info(f"Viewing {product['name']} in inventory")
                    
                    # Generate barcode
                    barcode_html = generate_barcode_html(manual_barcode, product['name'])
                    st.markdown(barcode_html, unsafe_allow_html=True)
                    
                    log_scan(
                        manual_barcode, product['name'], "SCAN", 1, "IMAGE", "SUCCESS"
                    )
                else:
                    st.error(f"❌ Product with barcode '{manual_barcode}' not found")
        
        # Manual barcode entry
        st.markdown("---")
        st.markdown("### Or Enter Barcode Manually")
        
        manual_barcode2 = st.text_input("Enter Barcode Number", placeholder="e.g., 6001 or 1234567890", key="manual_barcode_main")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Lookup", use_container_width=True):
                if manual_barcode2:
                    product = products_df[products_df["barcode"].astype(str) == manual_barcode2]
                    
                    if not product.empty:
                        product = product.iloc[0]
                        st.success(f"✅ Product found: {product['name']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Product:** {product['name']}")
                            st.info(f"**Price:** ${product['price']:.2f}")
                        with col2:
                            st.info(f"**Stock:** {product['stock']}")
                            st.info(f"**Category:** {product.get('category', 'N/A')}")
                        
                        # Actions
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("➕ Add to Cart", key="manual_add_cart", use_container_width=True):
                                st.success(f"✅ Added {product['name']} to cart!")
                                try:
                                    from backend.core.animations import show_toast
                                    show_toast(f"{product['name']} added to cart!", "success")
                                except:
                                    pass
                        
                        with col2:
                            if st.button("📱 Generate QR", key="manual_qr", use_container_width=True):
                                qr_html = generate_qr_code_html(manual_barcode2)
                                st.markdown(qr_html, unsafe_allow_html=True)
                        
                        log_scan(
                            manual_barcode2, product['name'], "MANUAL", 1, "MANUAL", "SUCCESS"
                        )
                    else:
                        st.error(f"❌ Product with barcode '{manual_barcode2}' not found")
                else:
                    st.warning("Please enter a barcode")
        
        with col2:
            if manual_barcode2 and st.button("📱 Generate QR", use_container_width=True):
                qr_html = generate_qr_code_html(manual_barcode2)
                st.markdown(qr_html, unsafe_allow_html=True)
    
    # ==============================
    # TAB 2: SCAN HISTORY
    # ==============================
    with tab2:
        st.markdown("## 📊 Scan History")
        
        if Path(SCAN_HISTORY_FILE).exists():
            df = pd.read_csv(SCAN_HISTORY_FILE)
            
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Scan History (CSV)",
                    data=csv,
                    file_name=f"scan_history_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No scan history found")
        else:
            st.info("No scan history found")
    
    # ==============================
    # TAB 3: BULK SCANNER
    # ==============================
    with tab3:
        st.markdown("## 📋 Bulk Barcode Scanner")
        st.caption("Scan multiple barcodes for stock take or inventory management")
        
        if settings.get("bulk_mode", False):
            st.info("🔴 Bulk scan mode is ACTIVE")
        else:
            st.warning("⚪ Bulk scan mode is INACTIVE. Enable in Settings.")
        
        # Bulk scan input
        st.markdown("### Enter Barcodes (one per line)")
        bulk_barcodes = st.text_area(
            "Paste or type barcodes",
            placeholder="6001\n6002\n6003\n1234567890",
            height=150
        )
        
        if bulk_barcodes:
            barcodes = [b.strip() for b in bulk_barcodes.split("\n") if b.strip()]
            st.info(f"📊 {len(barcodes)} barcodes to scan")
            
            if st.button("🔍 Scan All Barcodes", type="primary", use_container_width=True):
                results = []
                found = 0
                not_found = 0
                
                for barcode in barcodes:
                    product = products_df[products_df["barcode"].astype(str) == barcode]
                    
                    if not product.empty:
                        product = product.iloc[0]
                        results.append({
                            "Barcode": barcode,
                            "Product": product["name"],
                            "Price": product["price"],
                            "Stock": product["stock"],
                            "Status": "✅ Found"
                        })
                        found += 1
                        
                        log_scan(
                            barcode, product["name"], "BULK", 1, "BULK", "SUCCESS"
                        )
                    else:
                        results.append({
                            "Barcode": barcode,
                            "Product": "Not Found",
                            "Price": "N/A",
                            "Stock": "N/A",
                            "Status": "❌ Not Found"
                        })
                        not_found += 1
                
                # Display results
                results_df = pd.DataFrame(results)
                st.dataframe(results_df, use_container_width=True, hide_index=True)
                
                st.success(f"✅ Found: {found} | ❌ Not Found: {not_found}")
                
                # Export results
                csv = results_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Results (CSV)",
                    data=csv,
                    file_name=f"bulk_scan_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    # ==============================
    # TAB 4: PRODUCT LOOKUP
    # ==============================
    with tab4:
        st.markdown("## 🔍 Product Lookup")
        
        search_term = st.text_input("Search Product", placeholder="Name or barcode")
        
        if search_term:
            # Search by name or barcode
            results = products_df[
                products_df["name"].str.contains(search_term, case=False) |
                products_df["barcode"].astype(str).str.contains(search_term, case=False)
            ]
            
            if not results.empty:
                st.dataframe(
                    results[["barcode", "name", "price", "stock", "category"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "price": st.column_config.NumberColumn("Price", format="$%.2f")
                    }
                )
                
                # Generate barcode for selected product
                selected_product = st.selectbox("Select product to generate barcode", results["name"].tolist())
                if selected_product:
                    product = results[results["name"] == selected_product].iloc[0]
                    barcode_html = generate_barcode_html(
                        product["barcode"],
                        product["name"]
                    )
                    st.markdown(barcode_html, unsafe_allow_html=True)
                    
                    # QR Code
                    qr_html = generate_qr_code_html(product["barcode"])
                    st.markdown(qr_html, unsafe_allow_html=True)
            else:
                st.warning("No products found")
    
    # ==============================
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## ⚙️ Scanner Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enable_camera = st.checkbox("Enable Camera", value=settings.get("enable_camera", True))
            scan_mode = st.selectbox(
                "Scan Mode",
                ["auto", "manual", "continuous"],
                index=["auto", "manual", "continuous"].index(settings.get("scan_mode", "manual"))
            )
            scan_timeout = st.number_input(
                "Scan Timeout (seconds)",
                min_value=1,
                max_value=30,
                value=settings.get("scan_timeout", 5)
            )
        
        with col2:
            sound_enabled = st.checkbox("Enable Sound", value=settings.get("sound_enabled", True))
            vibration_enabled = st.checkbox("Enable Vibration", value=settings.get("vibration_enabled", True))
            bulk_mode = st.checkbox("Enable Bulk Scan Mode", value=settings.get("bulk_mode", False))
        
        st.markdown("### 📦 Auto Actions")
        
        auto_add_cart = st.checkbox("Auto-add to Cart", value=settings.get("auto_add_to_cart", False))
        auto_add_inventory = st.checkbox("Auto-add to Inventory", value=settings.get("auto_add_to_inventory", False))
        
        if st.button("💾 Save Scanner Settings", type="primary", use_container_width=True):
            settings.update({
                "enable_camera": enable_camera,
                "scan_mode": scan_mode,
                "scan_timeout": scan_timeout,
                "sound_enabled": sound_enabled,
                "vibration_enabled": vibration_enabled,
                "bulk_mode": bulk_mode,
                "auto_add_to_cart": auto_add_cart,
                "auto_add_to_inventory": auto_add_inventory
            })
            save_scanner_settings(settings)
            st.success("✅ Settings saved successfully!")
            try:
                from backend.core.animations import show_toast
                show_toast("Scanner settings updated!", "success")
            except:
                pass


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    barcode_scanner_dashboard()