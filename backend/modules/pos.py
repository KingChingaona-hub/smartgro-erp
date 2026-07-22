import streamlit as st
import pandas as pd
from datetime import datetime
import time

from backend.core.db_adapter import (
    load_products,
    save_products,
    load_sales,
    save_sales,
    record_customer_purchase,
    process_checkout_batch
)

from backend.modules.receipt import (
    generate_receipt, 
    generate_receipt_pdf, 
    generate_premium_receipt,
    generate_thermal_receipt,
    generate_html_receipt
)
from backend.modules.cash_register import record_cash_sale, record_credit_sale

from backend.analytics.debtors_engine import (
    get_credit_score,
    get_blocked_customers,
    create_debt,
    load_debtors
)

from backend.modules.loyalty import add_loyalty_points, redeem_points, get_customer_loyalty_info
from backend.modules.shift_manager import update_shift_stats, get_active_shift_for_branch
from backend.utils.utils import generate_whatsapp_receipt, get_whatsapp_link


# ==============================
# SESSION INIT
# ==============================
def init_session():
    if "cart" not in st.session_state:
        st.session_state.cart = []
    if "receipt" not in st.session_state:
        st.session_state.receipt = ""
    if "last_receipt" not in st.session_state:
        st.session_state.last_receipt = ""
    if "receipt_no" not in st.session_state:
        st.session_state.receipt_no = None
    if "show_receipt" not in st.session_state:
        st.session_state.show_receipt = False
    if "shift_id" not in st.session_state:
        st.session_state.shift_id = None
    if "saved_carts" not in st.session_state:
        st.session_state.saved_carts = {}
    if "recent_customers" not in st.session_state:
        st.session_state.recent_customers = []
    if "receipt_style" not in st.session_state:
        st.session_state.receipt_style = "Standard"
    if "checkout_processing" not in st.session_state:
        st.session_state.checkout_processing = False


# ==============================
# PRODUCTS - CACHED
# ==============================
@st.cache_data(ttl=5)
def get_cached_products():
    """Cache products for 5 seconds to reduce DB hits"""
    return load_products()


def get_products():
    return get_cached_products()


# ==============================
# CREDIT CHECK - CACHED
# ==============================
@st.cache_data(ttl=60)
def get_cached_credit_score():
    return get_credit_score()


def check_credit_allowed(customer_phone, amount):
    if not customer_phone:
        return False, "No customer phone provided"
    
    scores_df = get_cached_credit_score()
    if scores_df.empty:
        return True, "New customer"
    
    match = scores_df[scores_df["phone"] == customer_phone]
    if match.empty:
        return True, "New customer - limited credit allowed"
    
    score = int(match.iloc[0]["credit_score"])
    
    if score <= 30:
        return False, "Customer blocked due to poor credit history"
    if score <= 60 and amount > 100:
        return False, "Credit limit exceeded for medium risk customer"
    
    return True, "Credit approved"


# ==============================
# ACTIVE DEBT CHECK - CACHED
# ==============================
@st.cache_data(ttl=60)
def get_cached_debtors():
    return load_debtors()


def has_active_credit(phone):
    debts = get_cached_debtors()
    if debts.empty:
        return False
    match = debts[(debts["phone"] == phone) & (debts["balance"] > 0)]
    return not match.empty


# ==============================
# STOCK VALIDATION - SUPPORTS DECIMALS
# ==============================
def check_stock_available(products_df, cart):
    for item in cart:
        product = products_df[products_df["barcode"] == item["barcode"]]
        if product.empty:
            return False, f"{item['name']} not found"
        stock = float(product.iloc[0]["stock"])
        qty = float(item["qty"])
        if qty > stock + 0.001:  # Small tolerance for floating point
            return False, f"{item['name']} only has {stock:.2f} units available"
    return True, "OK"


# ==============================
# SAVE CART
# ==============================
def save_current_cart(cart_name):
    if cart_name and st.session_state.cart:
        st.session_state.saved_carts[cart_name] = st.session_state.cart.copy()
        return True
    return False


# ==============================
# LOAD CART
# ==============================
def load_saved_cart(cart_name):
    if cart_name in st.session_state.saved_carts:
        st.session_state.cart = st.session_state.saved_carts[cart_name].copy()
        return True
    return False


# ==============================
# ADD TO RECENT CUSTOMERS
# ==============================
def add_recent_customer(name, phone):
    customer = {"name": name, "phone": phone}
    st.session_state.recent_customers = [c for c in st.session_state.recent_customers if c["phone"] != phone]
    st.session_state.recent_customers.insert(0, customer)
    st.session_state.recent_customers = st.session_state.recent_customers[:10]


# ==============================
# CHECK BRANCH SHIFT STATUS
# ==============================
def get_branch_shift_status(branch_id):
    """Get the active shift status for a branch"""
    active_shift = get_active_shift_for_branch(branch_id)
    
    if active_shift:
        return {
            "active": True,
            "shift_id": active_shift.get("shift_id"),
            "started_by": active_shift.get("cashier_name", "Unknown"),
            "start_time": active_shift.get("start_time"),
            "opening_cash": active_shift.get("opening_cash", 0),
            "branch_name": active_shift.get("branch_name", "")
        }
    else:
        return {
            "active": False,
            "shift_id": None,
            "started_by": None,
            "start_time": None,
            "opening_cash": 0,
            "branch_name": ""
        }


# ==============================
# REMOVE ITEM FROM CART
# ==============================
def remove_from_cart(index):
    st.session_state.cart.pop(index)
    return True


# ==============================
# UPDATE ITEM QUANTITY - SUPPORTS DECIMALS
# ==============================
def update_cart_quantity(index, new_qty):
    if index < len(st.session_state.cart):
        try:
            new_qty = float(new_qty)
            if new_qty <= 0:
                st.session_state.cart.pop(index)
            else:
                st.session_state.cart[index]["qty"] = new_qty
                st.session_state.cart[index]["total"] = new_qty * st.session_state.cart[index]["price"]
            return True
        except ValueError:
            return False
    return False


# ==============================
# CHECK IF PRODUCT SUPPORTS DECIMAL
# ==============================
def supports_decimal_quantity(product_name, category=""):
    """Check if a product supports decimal quantities"""
    if not product_name:
        return False
    
    name_lower = product_name.lower()
    category_lower = str(category).lower()
    
    # Products that support decimal quantities
    decimal_products = [
        "gas", "kg", "bread", "loaf", "flour", "sugar", "rice", 
        "maize meal", "cooking oil", "milk", "liquid", "weight"
    ]
    
    for keyword in decimal_products:
        if keyword in name_lower or keyword in category_lower:
            return True
    
    return False


# ==============================
# POS PAGE - WITH DECIMAL SUPPORT
# ==============================
def pos_page():
    init_session()
    
    st.title("AZIEL INVESTMENTS POS SYSTEM")
    st.caption("Fast, efficient, and modern point of sale")
    
    try:
        st.image("aziellogo.png", width=120)
    except:
        pass
    
    # Load products once with caching
    products_df = get_products()
    cart = st.session_state.cart
    
    # ==============================
    # SHIFT STATUS - FAST
    # ==============================
    user_branch = st.session_state.get("user_branch", "HO")
    branch_shift = get_branch_shift_status(user_branch)
    active_shift_id = branch_shift.get("shift_id") if branch_shift.get("active") else None
    session_shift_id = st.session_state.get("active_shift_id")
    shift_to_use = active_shift_id if active_shift_id else session_shift_id
    
    st.session_state.branch_shift_id = shift_to_use
    st.session_state.branch_shift_active = branch_shift.get("active", False)
    
    if branch_shift.get("active"):
        st.success(f"Shift ACTIVE - Branch: {branch_shift.get('branch_name', user_branch)}")
    else:
        st.warning("No Active Shift. Please start a shift in Cash Dashboard.")
        user_role = st.session_state.get("role", "cashier")
        if user_role in ["owner", "manager"]:
            if st.button("Go to Cash Dashboard", use_container_width=True):
                st.session_state.current_page = "Cash Dashboard"
                st.rerun()
    
    # ==============================
    # QUICK ACTION BUTTONS
    # ==============================
    st.markdown("## Quick Action Products")
    
    # Load sales for quick products - cached
    sales_df = load_sales()
    if not sales_df.empty and "name" in sales_df.columns:
        top_products = sales_df.groupby("name")["items"].sum().nlargest(6).index.tolist()
        quick_products = products_df[products_df["name"].isin(top_products)]
    else:
        quick_products = products_df.head(6) if not products_df.empty else pd.DataFrame()
    
    if not quick_products.empty:
        cols = st.columns(min(6, len(quick_products)))
        for idx, (_, product) in enumerate(quick_products.iterrows()):
            if idx < len(cols):
                with cols[idx]:
                    if st.button(
                        f"{product['name'][:15]}...\n${product['price']:.2f}",
                        key=f"quick_product_{product['barcode']}_{idx}",
                        use_container_width=True
                    ):
                        if product["stock"] > 0:
                            found = False
                            for item in cart:
                                if item["barcode"] == product["barcode"]:
                                    item["qty"] += 1
                                    item["total"] = item["qty"] * item["price"]
                                    found = True
                                    break
                            if not found:
                                cart.append({
                                    "barcode": product["barcode"],
                                    "name": product["name"],
                                    "price": float(product["price"]),
                                    "cost": float(product["cost"]),
                                    "qty": 1.0,
                                    "total": float(product["price"])
                                })
                            st.toast(f"Added: {product['name']}")
                        else:
                            st.toast(f"{product['name']} is out of stock!")
    
    st.markdown("---")
    
    # ==============================
    # PRODUCT SEARCH WITH DECIMAL SUPPORT
    # ==============================
    st.markdown("## Search Products")
    
    if products_df.empty:
        st.warning("No products found. Please add products in Inventory first.")
        if st.button("Go to Inventory", key="go_to_inventory_btn"):
            st.session_state.current_page = "Inventory"
            st.rerun()
        return
    
    # Add mode selector for decimal products
    col_search, col_qty, col_mode = st.columns([3, 1, 1])
    
    with col_search:
        search = st.text_input(
            "Scan Barcode / Search Product",
            placeholder="Type product name or scan barcode...",
            key="search_input"
        )
    
    with col_qty:
        # Allow decimal quantities with step of 0.5
        quick_qty = st.number_input(
            "Qty", 
            min_value=0.0, 
            value=1.0, 
            step=0.5,
            format="%.2f",
            key="quick_qty"
        )
    
    with col_mode:
        # Add option to input by amount instead of quantity
        quick_mode = st.selectbox(
            "Mode",
            ["Quantity", "Amount ($)"],
            key="quick_mode"
        )
    
    filtered_df = products_df.copy()
    if search:
        filtered_df = products_df[
            products_df["barcode"].astype(str).str.contains(search, case=False) |
            products_df["name"].str.contains(search, case=False)
        ]
    
    if not filtered_df.empty:
        selected_product = st.selectbox(
            "Select Product",
            filtered_df["name"].tolist(),
            key="product_select"
        )
        
        if selected_product:
            product = filtered_df[filtered_df["name"] == selected_product].iloc[0]
            
            # Check if this product supports decimal quantities
            is_decimal = supports_decimal_quantity(
                product["name"], 
                product.get("category", "")
            )
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Price:** ${product['price']:.2f}")
            with col2:
                if product["stock"] <= 0:
                    st.error(f"**Stock:** OUT OF STOCK")
                elif product["stock"] <= product["reorder_level"]:
                    st.warning(f"**Stock:** {product['stock']:.2f} (LOW)")
                else:
                    st.success(f"**Stock:** {product['stock']:.2f} units")
            with col3:
                st.write(f"**Category:** {product['category']}")
            
            # Show decimal support info
            if is_decimal:
                st.info("🔢 Decimal quantities supported (e.g., 0.5, 1.5, 2.0)")
                st.caption("💡 Use 'Amount ($)' mode to buy by value instead of weight")
            
            # Calculate quantity based on mode
            final_qty = quick_qty
            price_per_unit = float(product["price"])
            
            if quick_mode == "Amount ($)":
                # User enters amount they want to spend
                amount_to_spend = quick_qty
                if amount_to_spend > 0 and price_per_unit > 0:
                    final_qty = amount_to_spend / price_per_unit
                    st.caption(f"💡 ${amount_to_spend:.2f} = {final_qty:.2f} units @ ${price_per_unit:.2f}")
                else:
                    final_qty = 0
            else:
                final_qty = quick_qty
            
            # For non-decimal products, ensure quantity is integer
            if not is_decimal:
                final_qty = int(final_qty) if final_qty > 0 else 0
                if final_qty != quick_qty:
                    st.info(f"Quantity rounded to {final_qty} (whole units only)")
            
            if st.button("Add to Cart", key="add_to_cart_btn", use_container_width=True):
                if product["stock"] <= 0:
                    st.toast(f"{product['name']} is out of stock!")
                elif final_qty <= 0:
                    st.toast("Please enter a valid quantity or amount")
                elif final_qty > product["stock"]:
                    st.toast(f"Only {product['stock']:.2f} units available for {product['name']}")
                else:
                    found = False
                    for item in cart:
                        if item["barcode"] == product["barcode"]:
                            new_qty = float(item["qty"]) + final_qty
                            if new_qty > product["stock"]:
                                st.toast(f"Cart exceeds available stock ({product['stock']:.2f})")
                                found = True
                                break
                            item["qty"] = new_qty
                            item["total"] = new_qty * item["price"]
                            found = True
                            if is_decimal:
                                st.toast(f"Updated: {product['name']} x{new_qty:.2f}")
                            else:
                                st.toast(f"Updated: {product['name']} x{int(new_qty)}")
                            break
                    
                    if not found:
                        cart.append({
                            "barcode": product["barcode"],
                            "name": product["name"],
                            "price": float(product["price"]),
                            "cost": float(product["cost"]),
                            "qty": final_qty,
                            "total": float(product["price"]) * final_qty
                        })
                        if is_decimal:
                            st.toast(f"Added: {product['name']} x{final_qty:.2f}")
                        else:
                            st.toast(f"Added: {product['name']} x{int(final_qty)}")
    
    st.markdown("---")
    
    # ==============================
    # CART DISPLAY WITH DECIMAL SUPPORT
    # ==============================
    st.markdown("## Current Cart")
    
    if not cart:
        st.info("Cart is empty. Add products to continue.")
        
        if st.session_state.saved_carts:
            with st.expander("Saved Carts"):
                for cart_name in st.session_state.saved_carts.keys():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{cart_name}")
                    with col2:
                        if st.button("Load", key=f"load_cart_{cart_name}"):
                            load_saved_cart(cart_name)
                            st.rerun()
        return
    
    # Cart items with management - supports decimals
    st.write("### Cart Items")
    
    for idx, item in enumerate(cart):
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
        
        with col1:
            st.write(f"**{item['name']}**")
            # Show if it's a decimal quantity
            if isinstance(item["qty"], float) and item["qty"] % 1 != 0:
                st.caption(f"🔢 {item['qty']:.2f} units")
        
        with col2:
            new_qty = st.number_input(
                "Qty",
                min_value=0.0,
                value=float(item["qty"]),
                step=0.5,
                format="%.2f",
                key=f"qty_{idx}_{item['barcode']}",
                label_visibility="collapsed"
            )
            if new_qty != item["qty"]:
                update_cart_quantity(idx, new_qty)
                st.rerun()
        
        with col3:
            st.write(f"${item['price']:.2f}")
        
        with col4:
            st.write(f"${item['total']:.2f}")
        
        with col5:
            if st.button("Remove", key=f"remove_{idx}_{item['barcode']}"):
                remove_from_cart(idx)
                st.rerun()
        
        st.divider()
    
    cart_df = pd.DataFrame(cart)
    # Display with proper decimal formatting
    st.dataframe(
        cart_df[["name", "qty", "price", "total"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "qty": st.column_config.NumberColumn("Quantity", format="%.2f"),
            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "total": st.column_config.NumberColumn("Total", format="$%.2f")
        }
    )
    
    subtotal = cart_df["total"].sum()
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Subtotal", f"${subtotal:.2f}")
    
    # ==============================
    # DISCOUNTS & TAX
    # ==============================
    col1, col2 = st.columns(2)
    with col1:
        discount_type = st.selectbox("Discount Type", ["NONE", "PERCENT", "FIXED"], key="discount_type")
        discount_value = st.number_input("Discount Value", min_value=0.0, value=0.0, key="discount_value")
    with col2:
        tax_rate = st.number_input("Tax %", min_value=0.0, value=0.0, key="tax_rate")
    
    discount_amount = 0
    if discount_type == "PERCENT":
        discount_amount = subtotal * (discount_value / 100)
    elif discount_type == "FIXED":
        discount_amount = discount_value
    
    tax_amount = ((subtotal - discount_amount) * tax_rate) / 100
    final_total = (subtotal - discount_amount) + tax_amount
    
    with col3:
        st.metric("Final Total", f"${final_total:.2f}", delta=f"-${discount_amount:.2f}" if discount_amount > 0 else None)
    
    st.markdown("---")
    
    # ==============================
    # CUSTOMER DETAILS
    # ==============================
    st.markdown("## Customer Details")
    
    if st.session_state.recent_customers:
        st.markdown("**Recent Customers:**")
        recent_cols = st.columns(min(5, len(st.session_state.recent_customers)))
        for idx, customer in enumerate(st.session_state.recent_customers[:5]):
            with recent_cols[idx]:
                if st.button(f"{customer['name'][:10]}", key=f"recent_customer_{idx}"):
                    st.session_state.customer_name_input = customer['name']
                    st.session_state.customer_phone_input = customer['phone']
    
    col1, col2 = st.columns(2)
    with col1:
        customer_name = st.text_input(
            "Customer Name",
            value=st.session_state.get("customer_name_input", ""),
            key="customer_name"
        )
    with col2:
        customer_phone = st.text_input(
            "Phone",
            value=st.session_state.get("customer_phone_input", ""),
            key="customer_phone"
        )
    
    customer_display = customer_name.strip().title() if customer_name and customer_name.strip() else "Walk-in"
    customer_phone_clean = customer_phone.strip() if customer_phone else ""
    
    if customer_name and customer_name.strip() and customer_phone and customer_phone.strip():
        add_recent_customer(customer_name.strip().title(), customer_phone.strip())
    
    # ==============================
    # RECEIPT STYLE
    # ==============================
    st.markdown("## Receipt Style")
    
    receipt_style = st.selectbox(
        "Select Receipt Format",
        ["Standard", "Premium (Boxed)", "Thermal (58mm)", "HTML Print"],
        key="receipt_style_selector"
    )
    st.session_state.receipt_style = receipt_style
    
    # ==============================
    # PAYMENT METHOD
    # ==============================
    st.markdown("## Payment")
    
    col1, col2 = st.columns(2)
    with col1:
        payment_method = st.selectbox(
            "Payment Method",
            ["CASH", "ECOCASH", "CARD", "CREDIT"],
            key="payment_method"
        )
    with col2:
        cash_received = st.number_input("Cash Received", min_value=0.0, value=0.0, key="cash_received")
    
    change = cash_received - final_total
    
    can_checkout = True
    
    if payment_method == "CASH":
        if cash_received < final_total:
            st.error("Insufficient cash")
            can_checkout = False
        else:
            st.success(f"Change: ${change:.2f}")
    
    elif payment_method == "CREDIT":
        if has_active_credit(customer_phone_clean):
            st.error("Customer already has unpaid debt")
            can_checkout = False
        else:
            allowed, message = check_credit_allowed(customer_phone_clean, final_total)
            if not allowed:
                st.error(f"CREDIT DENIED: {message}")
                can_checkout = False
            else:
                st.warning(f"CREDIT APPROVED: {message}")
    
    # ==============================
    # LOYALTY POINTS
    # ==============================
    points_earned = 0
    points_used = 0
    
    if customer_phone_clean and payment_method != "CREDIT":
        customer_loyalty = get_customer_loyalty_info(customer_phone_clean)
        
        if customer_loyalty and customer_loyalty["points"] >= 100:
            st.markdown("---")
            st.markdown("## Loyalty Points")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"Available Points: {customer_loyalty['points']} (Worth ${customer_loyalty['points']/100:.2f})")
            
            with col2:
                redeem = st.checkbox("Redeem points for this purchase", key="redeem_points_checkbox")
            
            if redeem:
                max_redeem = min(customer_loyalty["points"], final_total * 100)
                points_to_redeem = st.number_input(
                    "Points to redeem",
                    min_value=100,
                    max_value=int(max_redeem),
                    step=100,
                    value=min(500, int(max_redeem)),
                    key="points_to_redeem"
                )
                
                if points_to_redeem >= 100:
                    success, discount_amount_loyalty, message = redeem_points(
                        customer_phone_clean,
                        points_to_redeem,
                        None
                    )
                    if success:
                        final_total -= discount_amount_loyalty
                        points_used = points_to_redeem
                        st.success(f"Redeemed {points_to_redeem} points for ${discount_amount_loyalty:.2f} discount!")
                        st.info(f"New total: ${final_total:.2f}")
    
    # ==============================
    # CHECKOUT BUTTONS - USING BATCH
    # ==============================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Clear Cart", key="clear_cart_btn", use_container_width=True):
            st.session_state.cart = []
            st.rerun()
    
    with col2:
        cart_name = st.text_input("Save Cart As", placeholder="Cart name", key="save_cart_name", label_visibility="collapsed")
        if st.button("Save Cart", key="save_cart_btn", use_container_width=True):
            if cart_name:
                save_current_cart(cart_name)
                st.success(f"Cart saved as '{cart_name}'")
            else:
                st.warning("Enter a name for the cart")
    
    with col3:
        if st.session_state.saved_carts:
            load_cart_name = st.selectbox("Load Cart", [""] + list(st.session_state.saved_carts.keys()), key="load_cart_name", label_visibility="collapsed")
            if load_cart_name and st.button("Load Cart", key="load_cart_btn", use_container_width=True):
                load_saved_cart(load_cart_name)
                st.rerun()
    
    with col4:
        if not st.session_state.branch_shift_active:
            st.error("No active shift")
            st.button("Checkout", key="checkout_btn", type="primary", use_container_width=True, disabled=True)
        elif st.session_state.checkout_processing:
            st.button("Processing...", key="checkout_btn", type="primary", use_container_width=True, disabled=True)
        else:
            if st.button("Checkout", key="checkout_btn", type="primary", use_container_width=True):
                # Validate
                if not can_checkout:
                    st.error("Checkout validation failed. Please check payment details.")
                    st.stop()
                
                # Check stock - quick (supports decimals)
                products_df = get_products()
                stock_ok, stock_message = check_stock_available(products_df, cart)
                if not stock_ok:
                    st.error(f"STOCK ERROR: {stock_message}")
                    st.stop()
                
                # Generate receipt number
                receipt_no = datetime.now().strftime("%Y%m%d%H%M%S")
                st.session_state.receipt_no = receipt_no
                
                # Get shift ID
                shift_id = st.session_state.branch_shift_id or st.session_state.get("shift_id", "")
                
                # Add loyalty points - only if customer has phone
                points_earned = 0
                if customer_phone_clean and payment_method != "CREDIT":
                    try:
                        points_earned = add_loyalty_points(
                            customer_name=customer_display,
                            phone=customer_phone_clean,
                            amount_spent=final_total,
                            receipt_no=receipt_no
                        )
                    except:
                        points_earned = 0
                
                # Set processing flag to prevent double click
                st.session_state.checkout_processing = True
                
                # Prepare checkout data for batch processing
                checkout_data = {
                    "cart": cart.copy(),
                    "receipt_no": receipt_no,
                    "payment_method": payment_method,
                    "customer_name": customer_display,
                    "customer_phone": customer_phone_clean,
                    "final_total": final_total,
                    "shift_id": shift_id,
                    "cashier": st.session_state.get("username", "system")
                }
                
                # USE BATCH CHECKOUT - ONE DATABASE TRANSACTION
                success, message = process_checkout_batch(
                    branch_id=st.session_state.get("user_branch", "HO"),
                    checkout_data=checkout_data
                )
                
                if success:
                    # Generate receipt
                    selected_style = st.session_state.get("receipt_style", "Standard")
                    
                    if selected_style == "Premium (Boxed)":
                        receipt_text = generate_premium_receipt(
                            cart=cart.copy(),
                            total_amount=subtotal,
                            receipt_no=receipt_no,
                            payment_method=payment_method,
                            customer_name=customer_display,
                            customer_phone=customer_phone_clean,
                            discount_amount=discount_amount,
                            discount_percent=discount_value if discount_type == "PERCENT" else 0,
                            tax_amount=tax_amount,
                            tax_percent=tax_rate,
                            cash_received=cash_received,
                            change=change,
                            final_total=final_total,
                            loyalty_points_earned=points_earned,
                            loyalty_points_used=points_used
                        )
                    elif selected_style == "Thermal (58mm)":
                        receipt_text = generate_thermal_receipt(
                            cart=cart.copy(),
                            total_amount=subtotal,
                            receipt_no=receipt_no,
                            payment_method=payment_method,
                            customer_name=customer_display,
                            final_total=final_total
                        )
                    else:
                        receipt_text = generate_receipt(
                            cart.copy(), subtotal, receipt_no, payment_method, customer_display,
                            discount_amount, tax_amount, cash_received, change, final_total
                        )
                    
                    # Store transaction data
                    st.session_state.last_cart = cart.copy()
                    st.session_state.last_subtotal = subtotal
                    st.session_state.last_receipt_no = receipt_no
                    st.session_state.last_payment_method = payment_method
                    st.session_state.last_customer_display = customer_display
                    st.session_state.last_customer_phone = customer_phone_clean
                    st.session_state.last_discount_amount = discount_amount
                    st.session_state.last_tax_amount = tax_amount
                    st.session_state.last_cash_received = cash_received
                    st.session_state.last_change = change
                    st.session_state.last_final_total = final_total
                    st.session_state.last_points_earned = points_earned
                    st.session_state.last_points_used = points_used
                    st.session_state.receipt = receipt_text
                    st.session_state.last_receipt = receipt_text
                    st.session_state.show_receipt = True
                    st.session_state.cart = []
                    st.session_state.checkout_processing = False
                    
                    st.success("Transaction completed successfully!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"Checkout failed: {message}")
                    st.session_state.checkout_processing = False
    
    # ==============================
    # RECEIPT DISPLAY
    # ==============================
    if st.session_state.get("show_receipt", False) and st.session_state.receipt:
        st.markdown("---")
        st.subheader("RECEIPT")
        
        selected_style = st.session_state.get("receipt_style", "Standard")
        
        if selected_style == "HTML Print":
            html_receipt = generate_html_receipt(
                cart=st.session_state.get("last_cart", []),
                total_amount=st.session_state.get("last_subtotal", 0),
                receipt_no=st.session_state.get("last_receipt_no", "N/A"),
                payment_method=st.session_state.get("last_payment_method", "CASH"),
                customer_name=st.session_state.get("last_customer_display", "Walk-in"),
                discount_amount=st.session_state.get("last_discount_amount", 0),
                tax_amount=st.session_state.get("last_tax_amount", 0),
                final_total=st.session_state.get("last_final_total", 0),
                cash_received=st.session_state.get("last_cash_received", 0),
                change=st.session_state.get("last_change", 0)
            )
            st.components.v1.html(html_receipt, height=600, scrolling=True)
        else:
            st.text_area("Receipt Preview", st.session_state.receipt, height=300, key="receipt_preview")
        
        # PDF Download
        pdf_file = generate_receipt_pdf(st.session_state.receipt)
        if pdf_file:
            st.download_button(
                "Download PDF Receipt",
                data=pdf_file,
                file_name=f"receipt_{st.session_state.get('last_receipt_no', 'receipt')}.pdf",
                mime="application/pdf",
                key="download_pdf_receipt",
                use_container_width=True
            )
        
        # WhatsApp
        customer_phone_data = st.session_state.get("last_customer_phone", "")
        if customer_phone_data:
            whatsapp_receipt = generate_whatsapp_receipt(
                st.session_state.get("last_cart", []),
                st.session_state.get("last_subtotal", 0),
                st.session_state.get("last_receipt_no", "N/A"),
                st.session_state.get("last_payment_method", "CASH"),
                st.session_state.get("last_customer_display", "Walk-in"),
                st.session_state.get("last_final_total", 0),
                st.session_state.get("last_discount_amount", 0),
                st.session_state.get("last_tax_amount", 0),
                st.session_state.get("last_cash_received", 0),
                st.session_state.get("last_change", 0)
            )
            whatsapp_link = get_whatsapp_link(customer_phone_data, whatsapp_receipt)
            if whatsapp_link:
                st.markdown(f"""
                <a href="{whatsapp_link}" target="_blank">
                    <button style="background:#25D366;color:white;border:none;border-radius:30px;padding:10px 20px;width:100%;cursor:pointer;margin:5px 0;">
                        Send via WhatsApp
                    </button>
                </a>
                """, unsafe_allow_html=True)
        
        # Print
        if selected_style != "HTML Print":
            print_html = f"""
            <html>
            <head>
            <style>
                body {{ font-family: monospace; padding: 20px; white-space: pre; }}
                @media print {{ button {{ display: none; }} }}
            </style>
            </head>
            <body>
                <button onclick="window.print()" style="padding:10px 20px;margin-bottom:20px;cursor:pointer;">Print Receipt</button>
                <pre>{st.session_state.receipt}</pre>
            </body>
            </html>
            """
            st.components.v1.html(print_html, height=400, scrolling=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Print", key="print_receipt_btn", use_container_width=True):
                st.info("Click the print button in the preview above")
        with col2:
            if st.button("Close Receipt", key="close_receipt_btn", use_container_width=True):
                st.session_state.show_receipt = False
                st.rerun()
    
    # ==============================
    # LAST RECEIPT (REPRINT)
    # ==============================
    if st.session_state.last_receipt and not st.session_state.get("show_receipt", False):
        st.markdown("---")
        with st.expander("Last Receipt (Reprint)"):
            st.text_area("Last Receipt", st.session_state.last_receipt, height=150, key="last_receipt_text")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Reprint", key="reprint_btn", use_container_width=True):
                    st.session_state.receipt = st.session_state.last_receipt
                    st.session_state.show_receipt = True
                    st.rerun()
            with col2:
                pdf_file = generate_receipt_pdf(st.session_state.last_receipt)
                if pdf_file:
                    st.download_button(
                        "Download PDF",
                        data=pdf_file,
                        file_name="receipt_last.pdf",
                        mime="application/pdf",
                        key="download_last_pdf",
                        use_container_width=True
                    )
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("Refresh Page", key="refresh_page_btn", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    pos_page()