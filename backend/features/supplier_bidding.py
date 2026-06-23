import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import hashlib

from backend.core.db_adapter import load_purchases, load_products, save_purchases

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
BIDDING_FILE = DATA_DIR / "supplier_bids.csv"
BIDDING_SETTINGS_FILE = DATA_DIR / "bidding_settings.json"
SUPPLIERS_FILE = DATA_DIR / "suppliers.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_bidding_files():
    """Initialize bidding-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Suppliers file
    if not SUPPLIERS_FILE.exists():
        suppliers_df = pd.DataFrame(columns=[
            "supplier_id",
            "supplier_name",
            "contact_person",
            "email",
            "phone",
            "address",
            "payment_terms",
            "lead_time_days",
            "rating",
            "active",
            "created_date"
        ])
        suppliers_df.to_csv(SUPPLIERS_FILE, index=False)
    
    # Bids file
    if not BIDDING_FILE.exists():
        df = pd.DataFrame(columns=[
            "bid_id",
            "po_number",
            "supplier_id",
            "supplier_name",
            "bid_amount",
            "original_amount",
            "bid_date",
            "delivery_days",
            "warranty_months",
            "payment_terms",
            "status",  # PENDING, ACCEPTED, REJECTED, EXPIRED
            "notes",
            "evaluated_by",
            "evaluated_date"
        ])
        df.to_csv(BIDDING_FILE, index=False)
    
    # Bidding settings
    if not BIDDING_SETTINGS_FILE.exists():
        settings = {
            "auto_accept_lowest_bid": True,
            "bidding_duration_days": 7,
            "require_minimum_bids": 2,
            "auto_reject_after_days": 14,
            "notify_suppliers": True,
            "preferred_supplier_bonus": 5,  # 5% preference for preferred suppliers
            "minimum_bid_reduction": 5,  # Minimum 5% reduction to auto-accept
            "last_updated": datetime.now().isoformat()
        }
        with open(BIDDING_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)


def load_suppliers():
    """Load all suppliers"""
    init_bidding_files()
    return pd.read_csv(SUPPLIERS_FILE)


def save_suppliers(df):
    """Save suppliers to file"""
    df.to_csv(SUPPLIERS_FILE, index=False)


def load_bids():
    """Load all bids"""
    init_bidding_files()
    return pd.read_csv(BIDDING_FILE)


def save_bids(df):
    """Save bids to file"""
    df.to_csv(BIDDING_FILE, index=False)


def load_bidding_settings():
    """Load bidding settings"""
    init_bidding_files()
    with open(BIDDING_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_bidding_settings(settings):
    """Save bidding settings"""
    with open(BIDDING_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def add_supplier(supplier_name, contact_person, email, phone, address="", payment_terms="NET30", lead_time_days=7):
    """Add a new supplier"""
    suppliers_df = load_suppliers()
    
    supplier_id = f"SUP{len(suppliers_df)+1:03d}"
    
    new_supplier = pd.DataFrame([{
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "contact_person": contact_person,
        "email": email,
        "phone": phone,
        "address": address,
        "payment_terms": payment_terms,
        "lead_time_days": lead_time_days,
        "rating": 0,
        "active": True,
        "created_date": datetime.now().isoformat()
    }])
    
    suppliers_df = pd.concat([suppliers_df, new_supplier], ignore_index=True)
    save_suppliers(suppliers_df)
    
    return supplier_id


def create_bidding_opportunity(po_number, total_amount, supplier_ids=None):
    """Create a bidding opportunity for a purchase order"""
    
    bids_df = load_bids()
    suppliers_df = load_suppliers()
    
    # Get eligible suppliers
    if supplier_ids:
        eligible_suppliers = suppliers_df[suppliers_df["supplier_id"].isin(supplier_ids)]
    else:
        eligible_suppliers = suppliers_df[suppliers_df["active"] == True]
    
    # Create bid records for each supplier
    new_bids = []
    for _, supplier in eligible_suppliers.iterrows():
        bid_id = hashlib.md5(f"{po_number}{supplier['supplier_id']}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        new_bid = {
            "bid_id": bid_id,
            "po_number": po_number,
            "supplier_id": supplier["supplier_id"],
            "supplier_name": supplier["supplier_name"],
            "bid_amount": total_amount,
            "original_amount": total_amount,
            "bid_date": datetime.now().isoformat(),
            "delivery_days": supplier.get("lead_time_days", 7),
            "warranty_months": 12,
            "payment_terms": supplier.get("payment_terms", "NET30"),
            "status": "PENDING",
            "notes": "",
            "evaluated_by": "",
            "evaluated_date": ""
        }
        new_bids.append(new_bid)
    
    if new_bids:
        new_bids_df = pd.DataFrame(new_bids)
        bids_df = pd.concat([bids_df, new_bids_df], ignore_index=True)
        save_bids(bids_df)
    
    return len(new_bids)


def submit_bid(po_number, supplier_id, supplier_name, bid_amount, delivery_days, warranty_months, payment_terms, notes=""):
    """Submit a bid for a purchase order"""
    
    bids_df = load_bids()
    
    # Check if supplier already has a bid for this PO
    existing = bids_df[(bids_df["po_number"] == po_number) & (bids_df["supplier_id"] == supplier_id)]
    
    if not existing.empty:
        # Update existing bid
        idx = existing.index[0]
        bids_df.loc[idx, "bid_amount"] = bid_amount
        bids_df.loc[idx, "delivery_days"] = delivery_days
        bids_df.loc[idx, "warranty_months"] = warranty_months
        bids_df.loc[idx, "payment_terms"] = payment_terms
        bids_df.loc[idx, "notes"] = notes
        bids_df.loc[idx, "bid_date"] = datetime.now().isoformat()
    else:
        # Create new bid
        bid_id = hashlib.md5(f"{po_number}{supplier_id}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        # Get original amount from purchase order
        purchases_df = load_purchases()
        po_data = purchases_df[purchases_df["po_number"] == po_number]
        original_amount = po_data["total_cost"].iloc[0] if not po_data.empty else bid_amount
        
        new_bid = pd.DataFrame([{
            "bid_id": bid_id,
            "po_number": po_number,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "bid_amount": bid_amount,
            "original_amount": original_amount,
            "bid_date": datetime.now().isoformat(),
            "delivery_days": delivery_days,
            "warranty_months": warranty_months,
            "payment_terms": payment_terms,
            "status": "PENDING",
            "notes": notes,
            "evaluated_by": "",
            "evaluated_date": ""
        }])
        bids_df = pd.concat([bids_df, new_bid], ignore_index=True)
    
    save_bids(bids_df)
    return True


def evaluate_bids(po_number):
    """Evaluate all bids for a purchase order and select the best one"""
    
    bids_df = load_bids()
    settings = load_bidding_settings()
    
    po_bids = bids_df[(bids_df["po_number"] == po_number) & (bids_df["status"] == "PENDING")]
    
    if po_bids.empty:
        return None, "No bids to evaluate"
    
    # Calculate scores for each bid
    scores = []
    for _, bid in po_bids.iterrows():
        score = 100
        
        # Price score (lower is better) - 50% weight
        min_bid = po_bids["bid_amount"].min()
        if min_bid > 0:
            price_score = (min_bid / bid["bid_amount"]) * 50
        else:
            price_score = 0
        
        # Delivery score (faster is better) - 20% weight
        min_delivery = po_bids["delivery_days"].min()
        if min_delivery > 0:
            delivery_score = (min_delivery / bid["delivery_days"]) * 20
        else:
            delivery_score = 0
        
        # Warranty score (longer is better) - 15% weight
        max_warranty = po_bids["warranty_months"].max()
        if max_warranty > 0:
            warranty_score = (bid["warranty_months"] / max_warranty) * 15
        else:
            warranty_score = 0
        
        # Payment terms score - 15% weight
        payment_score = 15 if bid["payment_terms"] in ["NET15", "COD"] else 10
        
        total_score = price_score + delivery_score + warranty_score + payment_score
        scores.append({
            "bid": bid,
            "score": total_score,
            "price_score": price_score,
            "delivery_score": delivery_score,
            "warranty_score": warranty_score,
            "payment_score": payment_score
        })
    
    # Sort by score (highest first)
    scores.sort(key=lambda x: x["score"], reverse=True)
    
    # Auto-accept if settings allow
    best = scores[0]
    if settings.get("auto_accept_lowest_bid", True):
        # Check if bid is at least X% lower than original
        original_amount = best["bid"]["original_amount"]
        reduction_pct = ((original_amount - best["bid"]["bid_amount"]) / original_amount) * 100 if original_amount > 0 else 0
        
        min_reduction = settings.get("minimum_bid_reduction", 5)
        if reduction_pct >= min_reduction:
            accept_bid(best["bid"]["bid_id"])
            return best["bid"], f"Auto-accepted {best['bid']['supplier_name']} (${best['bid']['bid_amount']:,.2f})"
    
    return best["bid"], f"Best bid: {best['bid']['supplier_name']} (Score: {best['score']:.1f})"


def accept_bid(bid_id):
    """Accept a specific bid"""
    
    bids_df = load_bids()
    purchases_df = load_purchases()
    
    idx = bids_df[bids_df["bid_id"] == bid_id].index
    if len(idx) == 0:
        return False
    
    # Update bid status
    bids_df.loc[idx[0], "status"] = "ACCEPTED"
    bids_df.loc[idx[0], "evaluated_date"] = datetime.now().isoformat()
    
    # Reject all other bids for this PO
    po_number = bids_df.loc[idx[0], "po_number"]
    bids_df.loc[(bids_df["po_number"] == po_number) & (bids_df["bid_id"] != bid_id), "status"] = "REJECTED"
    
    # Update purchase order with selected supplier
    purchases_df.loc[purchases_df["po_number"] == po_number, "supplier"] = bids_df.loc[idx[0], "supplier_name"]
    purchases_df.loc[purchases_df["po_number"] == po_number, "status"] = "APPROVED"
    
    save_bids(bids_df)
    save_purchases(purchases_df)
    
    return True


def get_bidding_summary():
    """Get summary of all bidding activity"""
    
    bids_df = load_bids()
    
    if bids_df.empty:
        return {
            "total_bids": 0,
            "pending_bids": 0,
            "accepted_bids": 0,
            "rejected_bids": 0,
            "total_savings": 0,
            "avg_discount": 0
        }
    
    total_bids = len(bids_df)
    pending = len(bids_df[bids_df["status"] == "PENDING"])
    accepted = len(bids_df[bids_df["status"] == "ACCEPTED"])
    rejected = len(bids_df[bids_df["status"] == "REJECTED"])
    
    # Calculate savings
    accepted_bids = bids_df[bids_df["status"] == "ACCEPTED"]
    if not accepted_bids.empty:
        savings = (accepted_bids["original_amount"] - accepted_bids["bid_amount"]).sum()
        avg_discount = ((accepted_bids["original_amount"] - accepted_bids["bid_amount"]) / accepted_bids["original_amount"] * 100).mean()
    else:
        savings = 0
        avg_discount = 0
    
    return {
        "total_bids": total_bids,
        "pending_bids": pending,
        "accepted_bids": accepted,
        "rejected_bids": rejected,
        "total_savings": savings,
        "avg_discount": avg_discount
    }


# ==============================
# SUPPLIER MANAGEMENT PAGE
# ==============================
def supplier_management_page():
    """Supplier Management Page - Add and manage suppliers"""
    
    st.markdown("## 🏪 Supplier Management")
    st.caption("Manage suppliers for bidding system")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can manage suppliers.")
        return
    
    init_bidding_files()
    
    tab1, tab2 = st.tabs(["➕ Add Supplier", "📋 Supplier List"])
    
    with tab1:
        st.markdown("### Add New Supplier")
        
        col1, col2 = st.columns(2)
        
        with col1:
            supplier_name = st.text_input("Supplier Name *", placeholder="e.g., National Foods")
            contact_person = st.text_input("Contact Person *", placeholder="John Doe")
            email = st.text_input("Email", placeholder="supplier@company.com")
        
        with col2:
            phone = st.text_input("Phone", placeholder="0777123456")
            payment_terms = st.selectbox("Payment Terms", ["NET15", "NET30", "NET45", "NET60", "COD"])
            lead_time = st.number_input("Lead Time (days)", min_value=1, max_value=60, value=7)
        
        address = st.text_area("Address", placeholder="Physical address")
        
        if st.button("➕ Add Supplier", type="primary", use_container_width=True):
            if supplier_name and contact_person:
                supplier_id = add_supplier(
                    supplier_name=supplier_name,
                    contact_person=contact_person,
                    email=email,
                    phone=phone,
                    address=address,
                    payment_terms=payment_terms,
                    lead_time_days=lead_time
                )
                st.success(f"✅ Supplier {supplier_name} added! ID: {supplier_id}")
                st.rerun()
            else:
                st.error("Please enter supplier name and contact person")
    
    with tab2:
        st.markdown("### Supplier List")
        
        suppliers_df = load_suppliers()
        
        if not suppliers_df.empty:
            st.dataframe(
                suppliers_df[["supplier_id", "supplier_name", "contact_person", "email", "phone", "payment_terms", "lead_time_days", "active"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No suppliers found. Add your first supplier above.")


# ==============================
# SUPPLIER BIDDING DASHBOARD
# ==============================
def supplier_bidding_dashboard():
    """Supplier Bidding System Dashboard"""
    
    st.title("🏪 Supplier Bidding System")
    st.caption("Competitive bidding for purchase orders - get the best prices")
    
    role = st.session_state.get("role", "cashier")
    
    # Only owner and managers can access bidding system
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can manage supplier bidding.")
        return
    
    init_bidding_files()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Bidding Overview",
        "📝 Create Bid Opportunity",
        "💵 Evaluate Bids",
        "🏪 Supplier Management",
        "⚙️ Bidding Settings"
    ])
    
    # ==============================
    # TAB 1: BIDDING OVERVIEW
    # ==============================
    with tab1:
        st.markdown("## 📊 Bidding Overview")
        
        summary = get_bidding_summary()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Bids", summary["total_bids"])
        with col2:
            st.metric("Pending Bids", summary["pending_bids"])
        with col3:
            st.metric("Accepted Bids", summary["accepted_bids"])
        with col4:
            st.metric("Total Savings", f"${summary['total_savings']:,.2f}")
        
        st.markdown("---")
        
        # Recent bids
        st.markdown("### 📋 Recent Bids")
        
        bids_df = load_bids()
        if not bids_df.empty:
            recent_bids = bids_df.sort_values("bid_date", ascending=False).head(20)
            st.dataframe(
                recent_bids[["bid_date", "po_number", "supplier_name", "bid_amount", "status"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "bid_amount": st.column_config.NumberColumn("Bid Amount", format="$%.2f")
                }
            )
        else:
            st.info("No bids yet. Create a bid opportunity to get started.")
        
        # Savings chart
        if summary["total_savings"] > 0:
            st.markdown("### 💰 Savings Impact")
            
            accepted_bids = bids_df[bids_df["status"] == "ACCEPTED"]
            if not accepted_bids.empty:
                savings_data = []
                for _, bid in accepted_bids.iterrows():
                    savings_data.append({
                        "PO": bid["po_number"],
                        "Supplier": bid["supplier_name"],
                        "Original": bid["original_amount"],
                        "Bid": bid["bid_amount"],
                        "Saved": bid["original_amount"] - bid["bid_amount"]
                    })
                savings_df = pd.DataFrame(savings_data)
                fig = px.bar(savings_df, x="PO", y="Saved", title="Savings per Purchase Order", color="Supplier")
                st.plotly_chart(fig, use_container_width=True)
    
    # ==============================
    # TAB 2: CREATE BID OPPORTUNITY
    # ==============================
    with tab2:
        st.markdown("## 📝 Create Bid Opportunity")
        st.caption("Create a competitive bidding opportunity for suppliers")
        
        # Load pending purchase orders
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            st.info("No purchase orders found. Create a purchase order first.")
            if st.button("Go to Purchases"):
                st.session_state.current_page = "Purchases"
                st.rerun()
        else:
            # Get POs that haven't been bid on yet
            bids_df = load_bids()
            pos_with_bids = bids_df["po_number"].unique().tolist()
            pending_pos = purchases_df[~purchases_df["po_number"].isin(pos_with_bids)]
            pending_pos = pending_pos[pending_pos["status"].isin(["PENDING", "APPROVED"])]
            
            if pending_pos.empty:
                st.info("No pending purchase orders available for bidding.")
            else:
                selected_po = st.selectbox(
                    "Select Purchase Order",
                    pending_pos["po_number"].tolist(),
                    format_func=lambda x: f"{x} - ${pending_pos[pending_pos['po_number'] == x]['total_cost'].iloc[0]:,.2f}"
                )
                
                if selected_po:
                    po_data = pending_pos[pending_pos["po_number"] == selected_po].iloc[0]
                    po_total = po_data.get("total_cost", 0)
                    
                    st.markdown("### PO Details")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**PO Number:** {selected_po}")
                        st.write(f"**Total Value:** ${po_total:,.2f}")
                    with col2:
                        items_count = len(purchases_df[purchases_df["po_number"] == selected_po])
                        st.write(f"**Items:** {items_count}")
                    
                    # Select suppliers
                    suppliers_df = load_suppliers()
                    
                    if suppliers_df.empty:
                        st.warning("No suppliers found. Add suppliers in Supplier Management tab.")
                    else:
                        st.markdown("### Select Suppliers to Invite")
                        
                        all_suppliers = st.checkbox("Invite All Active Suppliers", value=True)
                        
                        if all_suppliers:
                            selected_suppliers = suppliers_df[suppliers_df["active"] == True]["supplier_id"].tolist()
                            st.info(f"Will invite {len(selected_suppliers)} suppliers")
                        else:
                            selected_suppliers = st.multiselect(
                                "Select Suppliers",
                                suppliers_df["supplier_id"].tolist(),
                                format_func=lambda x: suppliers_df[suppliers_df["supplier_id"] == x]["supplier_name"].iloc[0]
                            )
                        
                        if st.button("📢 Create Bidding Opportunity", type="primary", use_container_width=True):
                            if selected_suppliers:
                                count = create_bidding_opportunity(selected_po, po_total, selected_suppliers)
                                st.success(f"✅ Bidding opportunity created! {count} suppliers invited.")
                                st.info("Suppliers can now submit their bids.")
                            else:
                                st.error("Please select at least one supplier")
    
    # ==============================
    # TAB 3: EVALUATE BIDS
    # ==============================
    with tab3:
        st.markdown("## 💵 Evaluate Bids")
        st.caption("Review and accept the best bids from suppliers")
        
        bids_df = load_bids()
        pending_bids = bids_df[bids_df["status"] == "PENDING"]
        
        if pending_bids.empty:
            st.info("No pending bids to evaluate")
        else:
            # Group by PO
            pos_with_bids = pending_bids["po_number"].unique()
            
            for po_number in pos_with_bids:
                po_bids = pending_bids[pending_bids["po_number"] == po_number]
                
                with st.expander(f"📦 PO: {po_number} - {len(po_bids)} bids received"):
                    # Display bids
                    bid_data = []
                    for _, bid in po_bids.iterrows():
                        reduction = ((bid["original_amount"] - bid["bid_amount"]) / bid["original_amount"] * 100) if bid["original_amount"] > 0 else 0
                        bid_data.append({
                            "Supplier": bid["supplier_name"],
                            "Bid Amount": f"${bid['bid_amount']:,.2f}",
                            "Original": f"${bid['original_amount']:,.2f}",
                            "Savings": f"${bid['original_amount'] - bid['bid_amount']:,.2f}",
                            "Reduction": f"{reduction:.1f}%",
                            "Delivery": f"{bid['delivery_days']} days",
                            "Warranty": f"{bid['warranty_months']} months",
                            "Payment Terms": bid["payment_terms"],
                            "bid_id": bid["bid_id"]
                        })
                    
                    bid_df = pd.DataFrame(bid_data)
                    st.dataframe(bid_df.drop(columns=["bid_id"]), use_container_width=True, hide_index=True)
                    
                    # Evaluate button
                    if st.button(f"🤖 Evaluate Best Bid for {po_number}", key=f"eval_{po_number}"):
                        best_bid, message = evaluate_bids(po_number)
                        if best_bid:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.warning(message)
                    
                    # Manual accept
                    st.markdown("**Or manually accept a bid:**")
                    selected_bid = st.selectbox(
                        f"Select bid to accept",
                        bid_df["bid_id"].tolist(),
                        key=f"accept_{po_number}",
                        format_func=lambda x: bid_df[bid_df["bid_id"] == x]["Supplier"].iloc[0]
                    )
                    
                    if st.button(f"✅ Accept Selected Bid", key=f"accept_btn_{po_number}"):
                        if accept_bid(selected_bid):
                            st.success("Bid accepted! Purchase order updated.")
                            st.rerun()
    
    # ==============================
    # TAB 4: SUPPLIER MANAGEMENT
    # ==============================
    with tab4:
        supplier_management_page()
    
    # ==============================
    # TAB 5: BIDDING SETTINGS
    # ==============================
    with tab5:
        st.markdown("## ⚙️ Bidding Settings")
        st.caption("Configure automated bidding rules")
        
        settings = load_bidding_settings()
        
        col1, col2 = st.columns(2)
        
        with col1:
            auto_accept = st.toggle("Auto-accept lowest bid", value=settings.get("auto_accept_lowest_bid", True))
            bidding_days = st.number_input("Bidding duration (days)", min_value=1, max_value=30, value=settings.get("bidding_duration_days", 7))
            min_bids = st.number_input("Minimum bids required", min_value=1, max_value=5, value=settings.get("require_minimum_bids", 2))
        
        with col2:
            auto_reject = st.number_input("Auto-reject after (days)", min_value=7, max_value=60, value=settings.get("auto_reject_after_days", 14))
            min_reduction = st.number_input("Minimum reduction % for auto-accept", min_value=0, max_value=50, value=settings.get("minimum_bid_reduction", 5))
            preferred_bonus = st.number_input("Preferred supplier bonus (%)", min_value=0, max_value=20, value=settings.get("preferred_supplier_bonus", 5))
        
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            settings["auto_accept_lowest_bid"] = auto_accept
            settings["bidding_duration_days"] = bidding_days
            settings["require_minimum_bids"] = min_bids
            settings["auto_reject_after_days"] = auto_reject
            settings["minimum_bid_reduction"] = min_reduction
            settings["preferred_supplier_bonus"] = preferred_bonus
            settings["last_updated"] = datetime.now().isoformat()
            save_bidding_settings(settings)
            st.success("✅ Settings saved successfully!")
        
        st.markdown("---")
        st.markdown("### 📖 How Bidding Works")
        
        st.info("""
        **Bidding Process:**
        
        1. **Create Opportunity** - Select a purchase order and invite suppliers
        2. **Suppliers Bid** - Suppliers submit their best offers
        3. **Automatic Evaluation** - System scores bids based on price, delivery, warranty, and payment terms
        4. **Auto-Accept** - If bid saves >5%, auto-accept the best bid
        5. **Manual Approval** - You can manually review and accept any bid
        
        **Scoring Weights:**
        - Price: 50%
        - Delivery Time: 20%
        - Warranty: 15%
        - Payment Terms: 15%
        """)


# ==============================
# SUPPLIER PORTAL BIDDING (for suppliers)
# ==============================
def supplier_bidding_portal():
    """Portal for suppliers to view and submit bids"""
    
    st.title("🏪 Supplier Bidding Portal")
    st.caption("View bidding opportunities and submit your best offers")
    
    # This would be accessed by suppliers through their login
    supplier_id = st.session_state.get("supplier_id", None)
    supplier_name = st.session_state.get("supplier_name", None)
    
    if not supplier_id:
        st.warning("Please login as a supplier to access this portal")
        st.info("Demo Supplier Login - Coming Soon")
        return
    
    bids_df = load_bids()
    
    # Get bids for this supplier
    supplier_bids = bids_df[bids_df["supplier_id"] == supplier_id]
    
    # Get open bidding opportunities (where this supplier hasn't bid yet)
    all_bids_for_supplier = bids_df[bids_df["supplier_id"] == supplier_id]
    bid_pos = all_bids_for_supplier["po_number"].tolist()
    
    # Load open POs
    purchases_df = load_purchases()
    open_pos = purchases_df[(purchases_df["status"] == "PENDING") & (~purchases_df["po_number"].isin(bid_pos))]
    
    if not open_pos.empty:
        st.markdown("### 📋 Open Bidding Opportunities")
        
        selected_po = st.selectbox("Select PO to bid on", open_pos["po_number"].tolist())
        
        if selected_po:
            po_data = open_pos[open_pos["po_number"] == selected_po].iloc[0]
            
            st.markdown("### Submit Your Bid")
            
            col1, col2 = st.columns(2)
            
            with col1:
                bid_amount = st.number_input("Your Bid Amount ($)", min_value=0.01, value=float(po_data.get("total_cost", 0)), step=10.0)
                delivery_days = st.number_input("Delivery Time (days)", min_value=1, value=7, step=1)
            
            with col2:
                warranty_months = st.number_input("Warranty (months)", min_value=0, value=12, step=1)
                payment_terms = st.selectbox("Payment Terms", ["NET15", "NET30", "NET45", "NET60", "COD"])
            
            notes = st.text_area("Additional Notes", placeholder="Any special conditions or offers...")
            
            if st.button("💰 Submit Bid", type="primary", use_container_width=True):
                submit_bid(
                    po_number=selected_po,
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    bid_amount=bid_amount,
                    delivery_days=delivery_days,
                    warranty_months=warranty_months,
                    payment_terms=payment_terms,
                    notes=notes
                )
                st.success("✅ Bid submitted successfully!")
                st.rerun()
    
    # Show existing bids
    if not supplier_bids.empty:
        st.markdown("### 📜 Your Submitted Bids")
        st.dataframe(
            supplier_bids[["po_number", "bid_amount", "delivery_days", "status", "bid_date"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "bid_amount": st.column_config.NumberColumn("Bid Amount", format="$%.2f")
            }
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    supplier_bidding_dashboard()