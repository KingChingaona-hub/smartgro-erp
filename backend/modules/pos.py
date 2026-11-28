# backend/modules/pos.py
# COMPACT LAYOUT:
#   - Product search, cart, totals, customer, payment, and checkout all live
#     inside a single two-column card so the cashier never scrolls far to checkout.
#   - Cleanter (Bluetooth 58mm thermal printer) integration preserved.
#   - Cart quantity merging preserved (clicking an existing item increments qty).

import streamlit as st
import pandas as pd
from datetime import datetime
import time
import requests

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
# CLEANTER INTEGRATION
# ==============================
CLEANTER_URL = "http://localhost:9100/print"
CLEANTER_HEALTH_URL = "http://localhost:9100/health"


def check_cleanter_running():
    try:
        res = requests.get(CLEANTER_HEALTH_URL, timeout=2)
        return res.status_code == 200
    except Exception:
        return False


def _cleanter_payload_from_state():
    cart = st.session_state.get("last_cart", [])
    receipt_no = st.session_state.get("last_receipt_no", "N/A")
    payment_method = st.session_state.get("last_payment_method", "CASH")
    customer_name = st.session_state.get("last_customer_display", "Walk-in")
    customer_phone = st.session_state.get("last_customer_phone", "")
    subtotal = float(st.session_state.get("last_subtotal", 0) or 0)
    discount = float(st.session_state.get("last_discount_amount", 0) or 0)
    tax = float(st.session_state.get("last_tax_amount", 0) or 0)
    final_total = float(st.session_state.get("last_final_total", 0) or 0)
    cash_received = float(st.session_state.get("last_cash_received", 0) or 0)
    change = float(st.session_state.get("last_change", 0) or 0)

    content = []
    content.append({"type": "text", "text": "AZIEL INVESTMENTS", "align": "center", "bold": True, "size": "large"})
    content.append({"type": "text", "text": "Smart Business Management... Made Easy!", "align": "center"})
    content.append({"type": "divider"})
    content.append({"type": "text", "text": f"Receipt: {receipt_no}", "align": "left"})
    content.append({"type": "text", "text": f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", "align": "left"})
    content.append({"type": "text", "text": f"Customer: {customer_name}", "align": "left"})
    if customer_phone:
        content.append({"type": "text", "text": f"Phone: {customer_phone}", "align": "left"})
    content.append({"type": "divider"})

    for item in cart:
        name = str(item.get("name", "Item"))
        qty = float(item.get("qty", 1))
        line_total = float(item.get("total", 0))
        price = float(item.get("price", 0))
        qty_str = f"{int(qty)} x ${price:.2f}" if qty.is_integer() else f"{qty:.2f} x ${price:.2f}"
        content.append({"type": "row", "left": f"{name[:20]}", "right": f"${line_total:.2f}"})
        content.append({"type": "text", "text": f"   {qty_str}", "align": "left", "size": "small"})

    content.append({"type": "divider"})
    content.append({"type": "row", "left": "Subtotal", "right": f"${subtotal:.2f}"})
    if discount > 0:
        content.append({"type": "row", "left": "Discount", "right": f"-${discount:.2f}"})
    if tax > 0:
        content.append({"type": "row", "left": "Tax", "right": f"${tax:.2f}"})
    content.append({"type": "divider"})
    content.append({"type": "row", "left": "TOTAL", "right": f"${final_total:.2f}", "bold": True, "size": "large"})
    content.append({"type": "text", "text": f"Payment: {payment_method}", "align": "left"})
    if payment_method == "CASH" and cash_received > 0:
        content.append({"type": "row", "left": "Cash", "right": f"${cash_received:.2f}"})
        content.append({"type": "row", "left": "Change", "right": f"${change:.2f}"})

    content.append({"type": "divider"})
    content.append({"type": "text", "text": "Thank you for your business!", "align": "center"})
    content.append({"type": "text", "text": "Aziel Investments", "align": "center"})
    content.append({"type": "text", "text": "0782905853 / 0776067967", "align": "center", "size": "small"})
    content.append({"type": "feed", "lines": 3})
    return {"content": content}


def print_receipt_to_cleanter():
    payload = _cleanter_payload_from_state()
    try:
        res = requests.post(CLEANTER_URL, json=payload, timeout=8)
        res.raise_for_status()
        return True, "Receipt sent to printer ✅"
    except requests.exceptions.ConnectionError:
        return False, "Cannot reach Cleanter. Open the Cleanter app on this device and tap 'Start'."
    except requests.exceptions.Timeout:
        return False, "Printer did not respond in time. Check the Bluetooth pairing and that the printer is switched on."
    except Exception as e:
        return False, f"Print error: {e}"


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
    if "customer_name_input" not in st.session_state:
        st.session_state.customer_name_input = "Walk-in"
    if "customer_phone_input" not in st.session_state:
        st.session_state.customer_phone_input = ""
    if "cleanter_message" not in st.session_state:
        st.session_state.cleanter_message = None
    if "cleanter_message_type" not in st.session_state:
        st.session_state.cleanter_message_type = "info"


# ==============================
# HELPERS
# ==============================
def _get_session_branch():
    return (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or "HO"
    )


def _ensure_branch_consistency():
    current = _get_session_branch()
    last = st.session_state.get("_pos_last_branch")
    if last != current:
        for k in list(st.session_state.keys()):
            if k.startswith("_products_cache_"):
                del st.session_state[k]
        st.session_state["_pos_last_branch"] = current


def _drop_product_cache():
    for k in list(st.session_state.keys()):
        if k.startswith("_products_cache_"):
            del st.session_state[k]


def add_item_to_cart(cart, product, qty, is_decimal):
    barcode = product["barcode"]
    stock = float(product["stock"])
    price = float(product["price"])
    for item in cart:
        if item["barcode"] == barcode:
            new_qty = float(item["qty"]) + float(qty)
            if new_qty > stock + 0.001:
                return False, float(item["qty"]), True
            item["qty"] = new_qty
            item["total"] = new_qty * price
            return False, new_qty, False
    cart.append({
        "barcode": barcode, "name": product["name"], "price": price,
        "cost": float(product["cost"]), "qty": float(qty), "total": price * float(qty),
    })
    return True, float(qty), False


def get_customer_suggestions(branch_id: str):
    try:
        sales_df = load_sales(branch_id=branch_id)
        if sales_df.empty:
            return []
        customer_col = None
        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                customer_col = col
                break
        if not customer_col:
            return []
        customers = sales_df[customer_col].dropna().unique().tolist()
        customers = [c for c in customers if str(c).strip() and str(c).strip().lower() != "walk-in"]
        return sorted(set(customers))
    except Exception:
        return []


def get_customer_phone_suggestions(branch_id: str):
    try:
        sales_df = load_sales(branch_id=branch_id)
        if sales_df.empty:
            return {}
        customer_col = None
        phone_col = None
        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                customer_col = col
                break
        for col in ["customer_phone", "phone", "Phone"]:
            if col in sales_df.columns:
                phone_col = col
                break
        if not customer_col or not phone_col:
            return {}
        phones = {}
        for _, row in sales_df.iterrows():
            name = row.get(customer_col)
            phone = row.get(phone_col)
            if name and str(name).strip() and str(name).strip().lower() != "walk-in":
                if phone and str(phone).strip():
                    phones[str(name).strip()] = str(phone).strip()
        return phones
    except Exception:
        return {}


def get_products():
    branch_id = _get_session_branch()
    cache_key = f"_products_cache_{branch_id}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = load_products(branch_id=branch_id)
    return st.session_state[cache_key]


def get_credit_scores(branch_id: str):
    try:
        df = get_credit_score()
        if df is not None and not df.empty and "branch_id" in df.columns:
            df = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
        return df
    except Exception:
        return pd.DataFrame()


def check_credit_allowed(customer_phone, amount):
    branch_id = _get_session_branch()
    if not customer_phone:
        return False, "No customer phone provided"
    scores_df = get_credit_scores(branch_id)
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


def get_debtors_for_branch(branch_id: str):
    try:
        df = load_debtors(branch_id=branch_id)
        if df is not None and not df.empty and "branch_id" in df.columns:
            df = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
        return df
    except Exception:
        return pd.DataFrame()


def has_active_credit(phone):
    branch_id = _get_session_branch()
    debts = get_debtors_for_branch(branch_id)
    if debts.empty:
        return False
    match = debts[(debts["phone"] == phone) & (debts["balance"] > 0)]
    return not match.empty


def check_stock_available(products_df, cart):
    for item in cart:
        product = products_df[products_df["barcode"] == item["barcode"]]
        if product.empty:
            return False, f"{item['name']} not found"
        stock = float(product.iloc[0]["stock"])
        qty = float(item["qty"])
        if qty > stock + 0.001:
            return False, f"{item['name']} only has {stock:.2f} units available"
    return True, "OK"


def save_current_cart(cart_name):
    if cart_name and st.session_state.cart:
        st.session_state.saved_carts[cart_name] = st.session_state.cart.copy()
        return True
    return False


def load_saved_cart(cart_name):
    if cart_name in st.session_state.saved_carts:
        st.session_state.cart = st.session_state.saved_carts[cart_name].copy()
        return True
    return False


def add_recent_customer(name, phone):
    customer = {"name": name, "phone": phone}
    st.session_state.recent_customers = [c for c in st.session_state.recent_customers if c["phone"] != phone]
    st.session_state.recent_customers.insert(0, customer)
    st.session_state.recent_customers = st.session_state.recent_customers[:10]


def get_branch_shift_status(branch_id):
    active_shift = get_active_shift_for_branch(branch_id)
    if active_shift:
        return {
            "active": True,
            "shift_id": active_shift.get("shift_id"),
            "started_by": active_shift.get("cashier_name", "Unknown"),
            "start_time": active_shift.get("start_time"),
            "opening_cash": active_shift.get("opening_cash", 0),
            "branch_name": active_shift.get("branch_name", ""),
        }
    return {"active": False, "shift_id": None, "started_by": None, "start_time": None, "opening_cash": 0, "branch_name": ""}


def remove_from_cart(index):
    st.session_state.cart.pop(index)
    return True


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


def supports_decimal_quantity(product_name, category=""):
    if not product_name:
        return False
    name_lower = product_name.lower()
    category_lower = str(category).lower()
    decimal_products = ["gas", "kg", "bread", "loaf", "flour", "sugar", "rice", "maize meal", "cooking oil", "milk", "liquid", "weight"]
    for keyword in decimal_products:
        if keyword in name_lower or keyword in category_lower:
            return True
    return False


# ==============================
# POS PAGE — COMPACT SINGLE-BOX LAYOUT
# ==============================
def pos_page():
    init_session()
    _ensure_branch_consistency()

    st.title("AZIEL INVESTMENTS POS")
    st.caption("Point of Sale")

    try:
        st.image("aziellogo.png", width=90)
    except:
        pass

    products_df = get_products()
    cart = st.session_state.cart

    # Cleanter message banner
    if st.session_state.get("cleanter_message"):
        mt = st.session_state.get("cleanter_message_type", "info")
        if mt == "success":
            st.success(st.session_state.cleanter_message)
        elif mt == "error":
            st.error(st.session_state.cleanter_message)
        else:
            st.info(st.session_state.cleanter_message)
        st.session_state.cleanter_message = None
        st.session_state.cleanter_message_type = "info"

    # ---------- Shift status (compact inline) ----------
    user_branch = _get_session_branch()
    branch_shift = get_branch_shift_status(user_branch)
    active_shift_id = branch_shift.get("shift_id") if branch_shift.get("active") else None
    session_shift_id = st.session_state.get("active_shift_id")
    shift_to_use = active_shift_id if active_shift_id else session_shift_id
    st.session_state.branch_shift_id = shift_to_use
    st.session_state.branch_shift_active = branch_shift.get("active", False)

    if branch_shift.get("active"):
        st.success(f"✅ Shift ACTIVE — {branch_shift.get('branch_name', user_branch)}")
    else:
        st.warning("⚠️ No Active Shift — start one in Cash Dashboard.")
        if st.session_state.get("role") in ["owner", "manager"]:
            if st.button("Go to Cash Dashboard", use_container_width=True):
                st.session_state.current_page = "Cash Dashboard"
                st.rerun()

    st.markdown("---")

    # ============================================================
    # SINGLE CARD: TWO COLUMNS (Left = Products+Cart, Right = Checkout)
    # ============================================================
    left_col, right_col = st.columns([3, 2], gap="medium")

    # ============================================================
    # LEFT COLUMN — products, quick actions, cart
    # ============================================================
    with left_col:
        # Quick action products (3 cols compact)
        if not products_df.empty:
            sales_df = load_sales(branch_id=user_branch)
            if not sales_df.empty and "name" in sales_df.columns:
                top_products = sales_df.groupby("name")["items"].sum().nlargest(6).index.tolist()
                quick_products = products_df[products_df["name"].isin(top_products)]
            else:
                quick_products = products_df.head(6)

            if not quick_products.empty:
                st.markdown("**⚡ Quick Products**")
                qcols = st.columns(3)
                for idx, (_, product) in enumerate(quick_products.iterrows()):
                    with qcols[idx % 3]:
                        if st.button(
                            f"{product['name'][:12]}\n${product['price']:.2f}",
                            key=f"quick_{product['barcode']}_{idx}",
                            use_container_width=True,
                        ):
                            if product["stock"] <= 0:
                                st.toast(f"{product['name']} out of stock")
                            else:
                                is_dec = supports_decimal_quantity(product["name"], product.get("category", ""))
                                added_new, new_qty, exceeded = add_item_to_cart(cart, product, 1.0, is_dec)
                                if exceeded:
                                    st.toast(f"Stock limit reached ({float(product['stock']):.2f})")
                                elif added_new:
                                    st.toast(f"Added {product['name']}")
                                else:
                                    st.toast(f"Updated {product['name']} → qty {int(new_qty) if not is_dec else f'{new_qty:.2f}'}")

        # Search + add to cart
        st.markdown("**🔍 Search Product**")
        s1, s2, s3 = st.columns([3, 1, 1])
        with s1:
            search = st.text_input("Search", placeholder="Name or barcode", key="search_input", label_visibility="collapsed")
        with s2:
            quick_qty = st.number_input("Qty", min_value=0.0, value=1.0, step=0.5, format="%.2f", key="quick_qty", label_visibility="collapsed")
        with s3:
            quick_mode = st.selectbox("Mode", ["Qty", "Amt"], key="quick_mode", label_visibility="collapsed")

        if products_df.empty:
            st.warning(f"No products for branch **{user_branch}**.")
            if st.button("Go to Inventory"):
                st.session_state.current_page = "Inventory"
                st.rerun()
            return

        filtered_df = products_df.copy()
        if search:
            filtered_df = products_df[
                products_df["barcode"].astype(str).str.contains(search, case=False)
                | products_df["name"].str.contains(search, case=False)
            ]

        if not filtered_df.empty:
            selected_product = st.selectbox("Product", filtered_df["name"].tolist(), key="product_select", label_visibility="collapsed")
            if selected_product:
                product = filtered_df[filtered_df["name"] == selected_product].iloc[0]
                is_decimal = supports_decimal_quantity(product["name"], product.get("category", ""))
                p1, p2, p3 = st.columns(3)
                with p1:
                    st.caption(f"**${product['price']:.2f}**")
                with p2:
                    if product["stock"] <= 0:
                        st.caption("❌ OUT")
                    elif product["stock"] <= product["reorder_level"]:
                        st.caption(f"⚠️ {product['stock']:.2f}")
                    else:
                        st.caption(f"✅ {product['stock']:.2f}")
                with p3:
                    st.caption(f"{product['category']}")

                final_qty = quick_qty
                price_per_unit = float(product["price"])
                if quick_mode == "Amt":
                    if quick_qty > 0 and price_per_unit > 0:
                        final_qty = quick_qty / price_per_unit
                    else:
                        final_qty = 0
                if not is_decimal:
                    final_qty = int(final_qty) if final_qty > 0 else 0

                if st.button("➕ Add to Cart", key="add_to_cart_btn", use_container_width=True, type="primary"):
                    if product["stock"] <= 0:
                        st.toast(f"{product['name']} out of stock")
                    elif final_qty <= 0:
                        st.toast("Enter valid qty/amount")
                    elif final_qty > product["stock"]:
                        st.toast(f"Only {product['stock']:.2f} available")
                    else:
                        added_new, new_qty, exceeded = add_item_to_cart(cart, product, final_qty, is_decimal)
                        if exceeded:
                            st.toast(f"Stock limit ({float(product['stock']):.2f})")
                        elif added_new:
                            st.toast(f"Added {product['name']}")
                        else:
                            st.toast(f"Updated {product['name']} → qty {new_qty:.2f}")

        st.markdown("---")

        # Cart display
        st.markdown(f"**🛒 Cart ({len(cart)} items)**")

        if not cart:
            st.info("Cart empty.")
        else:
            # Compact cart table using HTML (avoids wide Streamlit rows)
            for idx, item in enumerate(cart):
                c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
                with c1:
                    qty_display = int(item["qty"]) if float(item["qty"]).is_integer() else f"{item['qty']:.2f}"
                    st.markdown(f"**{item['name'][:22]}**  \n<small>{qty_display} × ${item['price']:.2f}</small>", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"**${item['total']:.2f}**")
                with c3:
                    if st.button("−", key=f"minus_{idx}_{item['barcode']}"):
                        update_cart_quantity(idx, float(item["qty"]) - 1)
                        st.rerun()
                with c4:
                    if st.button("🗑", key=f"del_{idx}_{item['barcode']}"):
                        remove_from_cart(idx)
                        st.rerun()

    # ============================================================
    # RIGHT COLUMN — totals, customer, payment, checkout
    # ============================================================
    with right_col:
        if not cart:
            st.info("Add items to see totals and checkout.")
            return

        cart_df = pd.DataFrame(cart)
        subtotal = cart_df["total"].sum()

        # ---------- Totals + discount + tax (compact) ----------
        st.markdown("**Totals**")
        t1, t2 = st.columns(2)
        with t1:
            discount_type = st.selectbox("Discount", ["NONE", "PERCENT", "FIXED"], key="discount_type", label_visibility="collapsed")
        with t2:
            discount_value = st.number_input("Value", min_value=0.0, value=0.0, key="discount_value", label_visibility="collapsed")

        tax_rate = st.number_input("Tax %", min_value=0.0, value=0.0, key="tax_rate")

        discount_amount = 0
        if discount_type == "PERCENT":
            discount_amount = subtotal * (discount_value / 100)
        elif discount_type == "FIXED":
            discount_amount = discount_value

        tax_amount = ((subtotal - discount_amount) * tax_rate) / 100
        final_total = (subtotal - discount_amount) + tax_amount

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Subtotal", f"${subtotal:.2f}")
        with m2:
            st.metric("Discount", f"-${discount_amount:.2f}")
        with m3:
            st.metric("TOTAL", f"${final_total:.2f}")

        st.markdown("---")

        # ---------- Customer (compact) ----------
        st.markdown("**👤 Customer**")
        customer_suggestions = get_customer_suggestions(user_branch)
        customer_phones = get_customer_phone_suggestions(user_branch)

        all_options = ["Walk-in"] + customer_suggestions if customer_suggestions else ["Walk-in"]
        current_name = st.session_state.get("customer_name_input", "Walk-in")
        if current_name not in all_options and current_name != "Walk-in" and current_name.strip():
            all_options.append(current_name)

        selected_customer = st.selectbox(
            "Customer", options=all_options,
            index=all_options.index(current_name) if current_name in all_options else 0,
            key="customer_name_select", label_visibility="collapsed",
        )
        new_customer_name = st.text_input(
            "New customer name (optional)",
            placeholder="Or type a new name...",
            key="new_customer_name_input", label_visibility="collapsed",
        )
        if new_customer_name.strip():
            selected_customer = new_customer_name.strip()

        st.session_state.customer_name_input = selected_customer

        auto_phone = customer_phones.get(selected_customer, "") if selected_customer != "Walk-in" else ""
        customer_phone = st.text_input(
            "Phone", value=st.session_state.get("customer_phone_input", auto_phone),
            key="customer_phone_field", label_visibility="collapsed",
            placeholder="Phone number",
        )
        st.session_state.customer_phone_input = customer_phone

        customer_display = selected_customer.strip().title() if selected_customer and selected_customer.strip() else "Walk-in"
        customer_phone_clean = customer_phone.strip() if customer_phone else ""

        if customer_display != "Walk-in" and customer_phone_clean:
            add_recent_customer(customer_display, customer_phone_clean)

        st.markdown("---")

        # ---------- Receipt style (compact) ----------
        receipt_style = st.selectbox(
            "Receipt Format",
            ["Standard", "Premium (Boxed)", "Thermal (58mm)", "HTML Print"],
            key="receipt_style_selector", label_visibility="collapsed",
        )
        st.session_state.receipt_style = receipt_style

        # ---------- Payment (compact) ----------
        st.markdown("**Payment**")
        p1, p2 = st.columns(2)
        with p1:
            payment_method = st.selectbox("Method", ["CASH", "ECOCASH", "CARD", "CREDIT"], key="payment_method", label_visibility="collapsed")
        with p2:
            cash_received = st.number_input("Cash Recv.", min_value=0.0, value=0.0, key="cash_received", label_visibility="collapsed")

        change = cash_received - final_total
        can_checkout = True

        if payment_method == "CASH":
            if cash_received < final_total:
                st.error(f"Insufficient — need ${final_total - cash_received:.2f} more")
                can_checkout = False
            else:
                st.success(f"Change: ${change:.2f}")
        elif payment_method == "CREDIT":
            if has_active_credit(customer_phone_clean):
                st.error("Customer has unpaid debt")
                can_checkout = False
            else:
                allowed, msg = check_credit_allowed(customer_phone_clean, final_total)
                if not allowed:
                    st.error(f"❌ {msg}")
                    can_checkout = False
                else:
                    st.warning(f"✅ {msg}")

        # ---------- Loyalty (compact) ----------
        points_earned = 0
        points_used = 0
        if customer_phone_clean and payment_method != "CREDIT":
            loyalty = get_customer_loyalty_info(customer_phone_clean)
            if loyalty and loyalty["points"] >= 100:
                st.markdown("---")
                st.caption(f"{loyalty['points']} points available (${loyalty['points']/100:.2f})")
                redeem = st.checkbox("Redeem points", key="redeem_points_checkbox")
                if redeem:
                    max_redeem = min(loyalty["points"], final_total * 100)
                    points_to_redeem = st.number_input(
                        "Points", min_value=100, max_value=int(max_redeem), step=100,
                        value=min(500, int(max_redeem)), key="points_to_redeem",
                    )
                    if points_to_redeem >= 100:
                        ok, disc, _msg = redeem_points(customer_phone_clean, points_to_redeem, None)
                        if ok:
                            final_total -= disc
                            points_used = points_to_redeem
                            st.success(f"Redeemed {points_to_redeem} pts → -${disc:.2f}")

        st.markdown("---")

        # ---------- Actions (compact grid) ----------
        a1, a2 = st.columns(2)
        with a1:
            if st.button("Clear Cart", key="clear_cart_btn", use_container_width=True):
                st.session_state.cart = []
                st.rerun()
        with a2:
            if not st.session_state.branch_shift_active:
                st.button("Checkout", key="checkout_btn", type="primary", use_container_width=True, disabled=True)
            elif st.session_state.checkout_processing:
                st.button("Processing...", key="checkout_btn", type="primary", use_container_width=True, disabled=True)
            else:
                if st.button("CHECKOUT", key="checkout_btn", type="primary", use_container_width=True):
                    if not can_checkout:
                        st.error("Fix payment before checkout")
                        st.stop()

                    fresh = load_products(branch_id=_get_session_branch())
                    stock_ok, stock_msg = check_stock_available(fresh, cart)
                    if not stock_ok:
                        st.error(f"STOCK: {stock_msg}")
                        _drop_product_cache()
                        st.stop()

                    receipt_no = datetime.now().strftime("%Y%m%d%H%M%S")
                    st.session_state.receipt_no = receipt_no
                    shift_id = st.session_state.branch_shift_id or st.session_state.get("shift_id", "")

                    if customer_phone_clean and payment_method != "CREDIT":
                        try:
                            points_earned = add_loyalty_points(
                                customer_name=customer_display, phone=customer_phone_clean,
                                amount_spent=final_total, receipt_no=receipt_no,
                            )
                        except:
                            points_earned = 0

                    st.session_state.checkout_processing = True

                    checkout_data = {
                        "cart": cart.copy(), "receipt_no": receipt_no,
                        "payment_method": payment_method, "customer_name": customer_display,
                        "customer_phone": customer_phone_clean, "final_total": final_total,
                        "shift_id": shift_id, "cashier": st.session_state.get("username", "system"),
                    }

                    success, message = process_checkout_batch(
                        branch_id=_get_session_branch(), checkout_data=checkout_data
                    )

                    if success:
                        style = st.session_state.get("receipt_style", "Standard")
                        if style == "Premium (Boxed)":
                            receipt_text = generate_premium_receipt(
                                cart=cart.copy(), total_amount=subtotal, receipt_no=receipt_no,
                                payment_method=payment_method, customer_name=customer_display,
                                customer_phone=customer_phone_clean,
                                discount_amount=discount_amount,
                                discount_percent=(discount_value if discount_type == "PERCENT" else 0),
                                tax_amount=tax_amount, tax_percent=tax_rate,
                                cash_received=cash_received, change=change, final_total=final_total,
                                loyalty_points_earned=points_earned, loyalty_points_used=points_used,
                            )
                        elif style == "Thermal (58mm)":
                            receipt_text = generate_thermal_receipt(
                                cart=cart.copy(), total_amount=subtotal, receipt_no=receipt_no,
                                payment_method=payment_method, customer_name=customer_display,
                                final_total=final_total,
                            )
                        else:
                            receipt_text = generate_receipt(
                                cart.copy(), subtotal, receipt_no, payment_method,
                                customer_display, discount_amount, tax_amount,
                                cash_received, change, final_total,
                            )

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
                        _drop_product_cache()
                        st.success("Transaction completed")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"Checkout failed: {message}")
                        st.session_state.checkout_processing = False
                        _drop_product_cache()

        # Saved carts (small section)
        if st.session_state.saved_carts:
            with st.expander("Saved Carts", expanded=False):
                for cname in list(st.session_state.saved_carts.keys()):
                    cc1, cc2 = st.columns([3, 1])
                    with cc1:
                        st.caption(cname)
                    with cc2:
                        if st.button("Load", key=f"load_{cname}"):
                            load_saved_cart(cname)
                            st.rerun()

    # ============================================================
    # RECEIPT MODAL (full-width, below both columns)
    # ============================================================
    if st.session_state.get("show_receipt", False) and st.session_state.receipt:
        st.markdown("---")
        st.subheader("Receipt")

        # Cleanter print button
        st.markdown("### Thermal Printer (58mm)")
        pc1, pc2 = st.columns([2, 1])
        with pc1:
            st.caption("Ensure **Cleanter** is open and started on this device, then click below.")
        with pc2:
            if st.button("Print to Thermal", key="print_to_thermal_btn", type="primary", use_container_width=True):
                ok, msg = print_receipt_to_cleanter()
                st.session_state.cleanter_message = msg
                st.session_state.cleanter_message_type = "success" if ok else "error"
                st.rerun()

        st.markdown("---")

        style = st.session_state.get("receipt_style", "Standard")
        if style == "HTML Print":
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
                change=st.session_state.get("last_change", 0),
            )
            st.components.v1.html(html_receipt, height=600, scrolling=True)
        else:
            st.text_area("Preview", st.session_state.receipt, height=250, key="receipt_preview")

        pdf_file = generate_receipt_pdf(st.session_state.receipt)
        if pdf_file:
            st.download_button(
                "Download PDF", data=pdf_file,
                file_name=f"receipt_{st.session_state.get('last_receipt_no', 'receipt')}.pdf",
                mime="application/pdf", key="download_pdf_receipt", use_container_width=True,
            )

        customer_phone_data = st.session_state.get("last_customer_phone", "")
        if customer_phone_data:
            wa = generate_whatsapp_receipt(
                st.session_state.get("last_cart", []), st.session_state.get("last_subtotal", 0),
                st.session_state.get("last_receipt_no", "N/A"),
                st.session_state.get("last_payment_method", "CASH"),
                st.session_state.get("last_customer_display", "Walk-in"),
                st.session_state.get("last_final_total", 0),
                st.session_state.get("last_discount_amount", 0),
                st.session_state.get("last_tax_amount", 0),
                st.session_state.get("last_cash_received", 0),
                st.session_state.get("last_change", 0),
            )
            link = get_whatsapp_link(customer_phone_data, wa)
            if link:
                st.markdown(
                    f'<a href="{link}" target="_blank"><button style="background:#25D366;color:white;'
                    f'border:none;border-radius:30px;padding:10px 20px;width:100%;cursor:pointer;">'
                    f'Send via WhatsApp</button></a>',
                    unsafe_allow_html=True,
                )

        if st.button("Close Receipt", key="close_receipt_btn", use_container_width=True):
            st.session_state.show_receipt = False
            st.rerun()

    # Last receipt reprint
    if st.session_state.last_receipt and not st.session_state.get("show_receipt", False):
        with st.expander("Last Receipt (Reprint)"):
            st.text_area("Last Receipt", st.session_state.last_receipt, height=120, key="last_receipt_text")
            lr1, lr2, lr3 = st.columns(3)
            with lr1:
                if st.button("Reprint", key="reprint_btn", use_container_width=True):
                    st.session_state.receipt = st.session_state.last_receipt
                    st.session_state.show_receipt = True
                    st.rerun()
            with lr2:
                if st.button("Thermal", key="reprint_thermal_btn", use_container_width=True):
                    ok, msg = print_receipt_to_cleanter()
                    st.session_state.cleanter_message = msg
                    st.session_state.cleanter_message_type = "success" if ok else "error"
                    st.rerun()
            with lr3:
                pdf = generate_receipt_pdf(st.session_state.last_receipt)
                if pdf:
                    st.download_button("PDF", data=pdf, file_name="receipt_last.pdf",
                                       mime="application/pdf", key="download_last_pdf",
                                       use_container_width=True)

    if st.button("Refresh Page", key="refresh_page_btn", use_container_width=True):
        _drop_product_cache()
        st.rerun()


if __name__ == "__main__":
    pos_page()