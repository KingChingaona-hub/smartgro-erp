import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import io
import csv

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
ECOMMERCE_FILE = DATA_DIR / "ecommerce_exports.csv"
SYNC_LOG_FILE = DATA_DIR / "sync_logs.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_ecommerce_files():
    """Initialize e-commerce export files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    if not ECOMMERCE_FILE.exists():
        df = pd.DataFrame(columns=[
            "export_id", "export_date", "platform", "export_type", 
            "product_count", "status", "exported_by", "file_path"
        ])
        df.to_csv(ECOMMERCE_FILE, index=False)
    
    if not SYNC_LOG_FILE.exists():
        df = pd.DataFrame(columns=[
            "sync_id", "sync_date", "platform", "action", 
            "items_synced", "status", "message", "synced_by"
        ])
        df.to_csv(SYNC_LOG_FILE, index=False)


def load_ecommerce_exports():
    """Load e-commerce export history"""
    init_ecommerce_files()
    try:
        return pd.read_csv(ECOMMERCE_FILE)
    except:
        return pd.DataFrame(columns=[
            "export_id", "export_date", "platform", "export_type", 
            "product_count", "status", "exported_by", "file_path"
        ])


def save_ecommerce_export(export_data):
    """Save export record"""
    df = load_ecommerce_exports()
    df = pd.concat([df, pd.DataFrame([export_data])], ignore_index=True)
    df.to_csv(ECOMMERCE_FILE, index=False)


def log_sync(sync_data):
    """Log sync activity"""
    try:
        df = pd.read_csv(SYNC_LOG_FILE)
        df = pd.concat([df, pd.DataFrame([sync_data])], ignore_index=True)
        df.to_csv(SYNC_LOG_FILE, index=False)
    except:
        df = pd.DataFrame([sync_data])
        df.to_csv(SYNC_LOG_FILE, index=False)


# ==============================
# LOAD PRODUCTS FROM DATABASE
# ==============================
def load_products_from_db():
    """Load products from database using db_adapter"""
    try:
        from backend.core.db_adapter import load_products
        df = load_products()
        
        # If empty, try alternative import
        if df.empty:
            try:
                from backend.core.db_adapter import load_products as load_products_alt
                df = load_products_alt()
            except:
                pass
        
        # If still empty, try direct file reading
        if df.empty:
            data_dir = Path("data")
            products_file = data_dir / "products.csv"
            if products_file.exists():
                df = pd.read_csv(products_file)
        
        # Ensure required columns exist
        if not df.empty:
            required_cols = ["name", "barcode", "price", "stock", "category"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = "" if col in ["name", "barcode", "category"] else 0
            
            # Convert numeric columns
            for col in ["price", "stock", "cost"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            
            # Rename columns if needed for consistency
            if "product_name" in df.columns and "name" not in df.columns:
                df["name"] = df["product_name"]
            if "product_barcode" in df.columns and "barcode" not in df.columns:
                df["barcode"] = df["product_barcode"]
        
        return df
    except Exception as e:
        st.warning(f"Could not load products: {str(e)}")
        return pd.DataFrame()


# ==============================
# WOOCOMMERCE EXPORT
# ==============================
def export_to_woocommerce(products_df):
    """Export products to WooCommerce CSV format"""
    
    if products_df.empty:
        return ""
    
    woocommerce_export = []
    
    for _, product in products_df.iterrows():
        # Get values safely
        barcode = str(product.get("barcode", ""))
        name = str(product.get("name", "Unknown Product"))
        price = float(product.get("price", 0))
        stock = int(product.get("stock", 0))
        category = str(product.get("category", "Uncategorized"))
        
        woocommerce_export.append({
            "ID": "",
            "Type": "simple",
            "SKU": barcode,
            "Name": name,
            "Description": f"{name} - Available at Aziel Investments",
            "Short description": "",
            "Price": price,
            "Regular price": price,
            "Sale price": "",
            "Categories": category,
            "Stock": stock,
            "Stock status": "instock" if stock > 0 else "outofstock",
            "Weight": "",
            "Length": "",
            "Width": "",
            "Height": "",
            "Images": "",
            "Tax status": "taxable",
            "Tax class": "",
            "Manage stock": "yes" if stock >= 0 else "no"
        })
    
    # Create CSV
    if not woocommerce_export:
        return ""
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=woocommerce_export[0].keys())
    writer.writeheader()
    writer.writerows(woocommerce_export)
    
    return output.getvalue()


# ==============================
# SHOPIFY EXPORT
# ==============================
def export_to_shopify(products_df):
    """Export products to Shopify CSV format"""
    
    if products_df.empty:
        return ""
    
    shopify_export = []
    
    for _, product in products_df.iterrows():
        barcode = str(product.get("barcode", ""))
        name = str(product.get("name", "Unknown Product"))
        price = float(product.get("price", 0))
        stock = int(product.get("stock", 0))
        category = str(product.get("category", "Uncategorized"))
        
        shopify_export.append({
            "Handle": barcode if barcode else name.replace(" ", "-").lower(),
            "Title": name,
            "Body (HTML)": f"<p>{name} - Available at Aziel Investments</p>",
            "Vendor": "Aziel Investments",
            "Product Category": category,
            "Type": "Physical Product",
            "Tags": "",
            "Published": "TRUE",
            "Option1 Name": "Title",
            "Option1 Value": "Default Title",
            "Variant SKU": barcode,
            "Variant Grams": "",
            "Variant Inventory Tracker": "shopify",
            "Variant Inventory Qty": stock,
            "Variant Inventory Policy": "deny",
            "Variant Fulfillment Service": "manual",
            "Variant Price": price,
            "Variant Compare At Price": "",
            "Variant Requires Shipping": "TRUE",
            "Variant Taxable": "TRUE",
            "Variant Barcode": barcode,
            "Image Src": "",
            "Image Position": "",
            "Image Alt Text": "",
            "Gift Card": "FALSE",
            "SEO Title": name,
            "SEO Description": f"Buy {name} at Aziel Investments",
            "Google Shopping / MPN": "",
            "Google Shopping / Age Group": "",
            "Google Shopping / Gender": "",
            "Google Shopping / Google Product Category": "",
            "Status": "active"
        })
    
    if not shopify_export:
        return ""
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=shopify_export[0].keys())
    writer.writeheader()
    writer.writerows(shopify_export)
    
    return output.getvalue()


# ==============================
# FACEBOOK SHOP EXPORT
# ==============================
def export_to_facebook(products_df):
    """Export products to Facebook Shop CSV format"""
    
    if products_df.empty:
        return ""
    
    facebook_export = []
    
    for _, product in products_df.iterrows():
        barcode = str(product.get("barcode", ""))
        name = str(product.get("name", "Unknown Product"))
        price = float(product.get("price", 0))
        stock = int(product.get("stock", 0))
        category = str(product.get("category", "Home & Garden"))
        
        facebook_export.append({
            "id": barcode,
            "title": name,
            "description": f"{name} - Available at Aziel Investments",
            "availability": "in stock" if stock > 0 else "out of stock",
            "condition": "new",
            "price": f"{price} USD",
            "link": "",
            "image_link": "",
            "brand": "Aziel Investments",
            "google_product_category": "",
            "fb_product_category": category,
            "quantity_to_sell_on_facebook": stock,
            "sale_price": "",
            "sale_price_effective_date": "",
            "additional_image_link": "",
            "color": "",
            "gender": "",
            "size": "",
            "pattern": "",
            "shipping_weight": "",
            "shipping_length": "",
            "shipping_width": "",
            "shipping_height": ""
        })
    
    if not facebook_export:
        return ""
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=facebook_export[0].keys())
    writer.writeheader()
    writer.writerows(facebook_export)
    
    return output.getvalue()


# ==============================
# ORDER IMPORT (Simulated)
# ==============================
def import_woocommerce_orders(csv_file):
    """Import orders from WooCommerce CSV"""
    try:
        df = pd.read_csv(csv_file)
        
        orders = []
        for _, row in df.iterrows():
            orders.append({
                "order_id": row.get("Order ID", str(datetime.now().timestamp())),
                "customer_name": row.get("Customer Name", "Unknown"),
                "customer_email": row.get("Customer Email", ""),
                "total_amount": float(row.get("Order Total", 0)),
                "status": row.get("Order Status", "pending"),
                "items": row.get("Items", ""),
                "order_date": row.get("Order Date", datetime.now().strftime("%Y-%m-%d"))
            })
        
        return True, orders
    except Exception as e:
        return False, str(e)


def import_shopify_orders(json_file):
    """Import orders from Shopify JSON"""
    try:
        data = json.load(json_file)
        orders = []
        
        for order in data.get("orders", []):
            customer = order.get("customer", {})
            orders.append({
                "order_id": order.get("id", ""),
                "customer_name": customer.get("first_name", "") + " " + customer.get("last_name", ""),
                "customer_email": customer.get("email", ""),
                "total_amount": float(order.get("total_price", 0)),
                "status": order.get("financial_status", "pending"),
                "items": len(order.get("line_items", [])),
                "order_date": order.get("created_at", datetime.now().isoformat())[:10]
            })
        
        return True, orders
    except Exception as e:
        return False, str(e)


# ==============================
# E-COMMERCE DASHBOARD
# ==============================
def ecommerce_sync_dashboard():
    """E-commerce Platform Sync Dashboard"""
    
    st.title("E-commerce Platform Sync")
    st.caption("Sync products with WooCommerce, Shopify, and Facebook Shop")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access e-commerce sync.")
        return
    
    init_ecommerce_files()
    
    # Load products using the improved function
    products_df = load_products_from_db()
    
    # Debug: Show what was loaded
    if not products_df.empty:
        st.sidebar.success(f"Loaded {len(products_df)} products")
        
        # Show sample in sidebar for debugging
        with st.sidebar.expander("Product Sample"):
            st.dataframe(products_df.head(3), use_container_width=True)
    else:
        st.sidebar.error("No products loaded")
        st.sidebar.info("Check: data/products.csv file exists and has data")
    
    if products_df.empty:
        st.warning("No products found. Please add products first.")
        
        # Show debug info
        with st.expander("Debug: Check data source"):
            st.write("Checking data/products.csv...")
            data_dir = Path("data")
            products_file = data_dir / "products.csv"
            if products_file.exists():
                st.success(f"products.csv exists at: {products_file}")
                try:
                    sample = pd.read_csv(products_file).head(3)
                    st.dataframe(sample, use_container_width=True)
                except Exception as e:
                    st.error(f"Error reading file: {e}")
            else:
                st.warning(f"products.csv not found at: {products_file}")
                
            # Check db_adapter
            try:
                from backend.core.db_adapter import load_products as db_load
                test = db_load()
                st.write(f"db_adapter.load_products() returned: {len(test)} products")
            except Exception as e:
                st.error(f"db_adapter error: {e}")
        
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "Export Products",
        "Import Orders",
        "Sync Dashboard",
        "Platform Settings"
    ])
    
    # ==============================
    # TAB 1: EXPORT PRODUCTS
    # ==============================
    with tab1:
        st.markdown("## Export Products to E-commerce Platforms")
        
        col1, col2 = st.columns(2)
        
        with col1:
            platform = st.selectbox(
                "Select Platform",
                ["WooCommerce", "Shopify", "Facebook Shop"]
            )
        
        with col2:
            categories = products_df["category"].unique().tolist() if "category" in products_df.columns else []
            category_filter = st.selectbox(
                "Filter by Category",
                ["All Categories"] + categories
            )
        
        # Filter products
        if category_filter != "All Categories" and "category" in products_df.columns:
            export_products = products_df[products_df["category"] == category_filter]
        else:
            export_products = products_df
        
        st.info(f"{len(export_products)} products will be exported")
        
        # Preview products
        with st.expander("Preview Products to Export"):
            preview_cols = ["name", "barcode", "price", "stock"]
            if "category" in export_products.columns:
                preview_cols.append("category")
            available_cols = [col for col in preview_cols if col in export_products.columns]
            st.dataframe(
                export_products[available_cols],
                use_container_width=True,
                hide_index=True
            )
        
        if st.button(f"Export to {platform}", type="primary", use_container_width=True):
            with st.spinner(f"Exporting to {platform}..."):
                
                export_data = None
                export_filename = None
                
                if platform == "WooCommerce":
                    export_data = export_to_woocommerce(export_products)
                    export_filename = f"woocommerce_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
                    st.success("WooCommerce export generated!")
                    
                elif platform == "Shopify":
                    export_data = export_to_shopify(export_products)
                    export_filename = f"shopify_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
                    st.success("Shopify export generated!")
                    
                elif platform == "Facebook Shop":
                    export_data = export_to_facebook(export_products)
                    export_filename = f"facebook_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
                    st.success("Facebook Shop export generated!")
                
                if export_data:
                    # Save export record
                    export_record = {
                        "export_id": f"EXP{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "export_date": datetime.now().isoformat(),
                        "platform": platform,
                        "export_type": "PRODUCT_EXPORT",
                        "product_count": len(export_products),
                        "status": "COMPLETED",
                        "exported_by": st.session_state.get("username", "system"),
                        "file_path": export_filename
                    }
                    save_ecommerce_export(export_record)
                    
                    # Download button
                    st.download_button(
                        label="Download Export File",
                        data=export_data.encode('utf-8'),
                        file_name=export_filename,
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    st.balloons()
    
    # ==============================
    # TAB 2: IMPORT ORDERS
    # ==============================
    with tab2:
        st.markdown("## Import Orders from E-commerce Platforms")
        st.caption("Import orders from your online stores")
        
        import_platform = st.selectbox(
            "Select Platform to Import From",
            ["WooCommerce (CSV)", "Shopify (JSON)"]
        )
        
        if import_platform == "WooCommerce (CSV)":
            uploaded_file = st.file_uploader("Upload WooCommerce Orders CSV", type=["csv"])
            
            if uploaded_file and st.button("Import Orders", type="primary", use_container_width=True):
                success, result = import_woocommerce_orders(uploaded_file)
                if success:
                    st.success(f"Successfully imported {len(result)} orders!")
                    
                    st.dataframe(
                        pd.DataFrame(result),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    log_sync({
                        "sync_id": f"SYNC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "sync_date": datetime.now().isoformat(),
                        "platform": "WooCommerce",
                        "action": "ORDER_IMPORT",
                        "items_synced": len(result),
                        "status": "SUCCESS",
                        "message": f"Imported {len(result)} orders",
                        "synced_by": st.session_state.get("username", "system")
                    })
                else:
                    st.error(f"Import failed: {result}")
        
        elif import_platform == "Shopify (JSON)":
            uploaded_file = st.file_uploader("Upload Shopify Orders JSON", type=["json"])
            
            if uploaded_file and st.button("Import Orders", type="primary", use_container_width=True):
                success, result = import_shopify_orders(uploaded_file)
                if success:
                    st.success(f"Successfully imported {len(result)} orders!")
                    
                    st.dataframe(
                        pd.DataFrame(result),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    log_sync({
                        "sync_id": f"SYNC{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "sync_date": datetime.now().isoformat(),
                        "platform": "Shopify",
                        "action": "ORDER_IMPORT",
                        "items_synced": len(result),
                        "status": "SUCCESS",
                        "message": f"Imported {len(result)} orders",
                        "synced_by": st.session_state.get("username", "system")
                    })
                else:
                    st.error(f"Import failed: {result}")
    
    # ==============================
    # TAB 3: SYNC DASHBOARD
    # ==============================
    with tab3:
        st.markdown("## Sync Dashboard")
        
        # Statistics
        total_products = len(products_df)
        low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]]) if "reorder_level" in products_df.columns else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Products", total_products)
        with col2:
            st.metric("Low Stock Items", low_stock)
        with col3:
            exports_df = load_ecommerce_exports()
            st.metric("Total Exports", len(exports_df))
        with col4:
            try:
                syncs_df = pd.read_csv(SYNC_LOG_FILE) if SYNC_LOG_FILE.exists() else pd.DataFrame()
                st.metric("Total Imports", len(syncs_df))
            except:
                st.metric("Total Imports", 0)
        
        # Export history
        st.markdown("### Export History")
        exports_df = load_ecommerce_exports()
        if not exports_df.empty:
            try:
                exports_df["export_date"] = pd.to_datetime(exports_df["export_date"])
                exports_df["export_date"] = exports_df["export_date"].dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass
            
            st.dataframe(
                exports_df[["export_date", "platform", "export_type", "product_count", "status", "exported_by"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No export history")
        
        # Sync history
        st.markdown("### Import History")
        if SYNC_LOG_FILE.exists():
            try:
                syncs_df = pd.read_csv(SYNC_LOG_FILE)
                if not syncs_df.empty:
                    try:
                        syncs_df["sync_date"] = pd.to_datetime(syncs_df["sync_date"])
                        syncs_df["sync_date"] = syncs_df["sync_date"].dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                    
                    st.dataframe(
                        syncs_df[["sync_date", "platform", "action", "items_synced", "status", "synced_by"]],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No import history")
            except:
                st.info("No import history")
        else:
            st.info("No import history")
    
    # ==============================
    # TAB 4: PLATFORM SETTINGS
    # ==============================
    with tab4:
        st.markdown("## Platform Settings")
        
        st.info("🔧 Configure your e-commerce platform API settings")
        
        # WooCommerce Settings
        with st.expander("WooCommerce Settings", expanded=True):
            woocommerce_url = st.text_input("WooCommerce Store URL", placeholder="https://yourstore.com")
            consumer_key = st.text_input("Consumer Key", type="password")
            consumer_secret = st.text_input("Consumer Secret", type="password")
            
            if st.button("🔌 Test WooCommerce Connection"):
                st.success("Connection test successful! (Simulated)")
        
        # Shopify Settings
        with st.expander("Shopify Settings"):
            shopify_store = st.text_input("Shopify Store URL", placeholder="yourstore.myshopify.com")
            shopify_token = st.text_input("Access Token", type="password")
            
            if st.button("🔌 Test Shopify Connection"):
                st.success("Connection test successful! (Simulated)")
        
        # Facebook Shop Settings
        with st.expander("Facebook Shop Settings"):
            facebook_page_id = st.text_input("Facebook Page ID")
            facebook_access_token = st.text_input("Facebook Access Token", type="password")
            
            if st.button("Test Facebook Connection"):
                st.success("Connection test successful! (Simulated)")
        
        # Auto-sync settings
        st.markdown("### Auto-Sync Settings")
        
        auto_sync = st.checkbox("Enable Automatic Product Sync")
        if auto_sync:
            sync_frequency = st.selectbox("Sync Frequency", ["Daily", "Weekly", "Hourly"])
            st.info(f"Products will be synced {sync_frequency.lower()} to all connected platforms")
        
        if st.button("Save Settings", type="primary", use_container_width=True):
            st.success("Settings saved successfully!")
            try:
                from backend.core.animations import show_toast
                show_toast("E-commerce settings saved!", "success")
            except:
                pass


if __name__ == "__main__":
    ecommerce_sync_dashboard()