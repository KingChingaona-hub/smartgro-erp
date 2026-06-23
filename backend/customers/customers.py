import streamlit as st
from backend.core.db_adapter import record_customer_purchase


# ==============================
# CUSTOMER SESSION INIT
# ==============================
def init_customer_session():
    
    if "customer_name" not in st.session_state:
        st.session_state.customer_name = ""

    if "customer_phone" not in st.session_state:
        st.session_state.customer_phone = ""

    if "customer_attached" not in st.session_state:
        st.session_state.customer_attached = False
        
        
# ==============================
# CUSTOMER CAPTURE FORM (POS SIDE)
# ==============================
def customer_capture_form():

    st.markdown("## 👤 Customer Details")

    col1, col2 = st.columns(2)

    name = col1.text_input(
        "Customer Name",
        value=st.session_state.customer_name
    )

    phone = col2.text_input(
        "Phone Number",
        value=st.session_state.customer_phone
    )

    attach = st.button("➕ Attach Customer to Sale")

    if attach:

        if name.strip() == "" or phone.strip() == "":
            st.error("Customer name and phone are required")
            return False

        st.session_state.customer_name = name
        st.session_state.customer_phone = phone
        st.session_state.customer_attached = True

        st.success(f"Customer attached: {name} ({phone})")
        return True

    return st.session_state.customer_attached


# ==============================
# RESET CUSTOMER AFTER SALE
# ==============================
def reset_customer():

    st.session_state.customer_name = ""
    st.session_state.customer_phone = ""
    st.session_state.customer_attached = False


# ==============================
# FINALIZE CUSTOMER SALE
# ==============================
def finalize_customer_sale(cart, total, receipt_no):

    if not st.session_state.customer_attached:
        return False

    if not cart:
        return False

    record_customer_purchase(
        customer_name=st.session_state.customer_name,
        phone=st.session_state.customer_phone,
        cart=cart,
        total=total,
        receipt_no=receipt_no
    )

    reset_customer()
    return True


# ==============================
# CUSTOMER SUMMARY WIDGET (OPTIONAL UI HELP)
# ==============================
def show_customer_summary():

    if st.session_state.customer_attached:

        st.info(
            f"👤 Selling to: {st.session_state.customer_name} | "
            f"{st.session_state.customer_phone}"
        )
    else:
        st.warning("No customer attached (Walk-in sale)")