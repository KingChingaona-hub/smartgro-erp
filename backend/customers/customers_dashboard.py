import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import re

from backend.core.db_adapter import load_customers, load_sales
from backend.modules.loyalty import (
    load_loyalty,
    get_top_loyalty_customers,
    get_birthday_customers,
    get_customer_loyalty_info,
    get_tier_benefits,
    save_loyalty
)
from backend.utils.utils import generate_whatsapp_promotion
from backend.utils.phone_utils import get_whatsapp_link


def customers_dashboard():
    """Enhanced Customer Intelligence Dashboard"""
    
    st.title("👥 Customer Intelligence Dashboard")
    st.caption("Track loyalty, spending patterns, and customer engagement")
    
    customers_df = load_customers()
    loyalty_df = load_loyalty()
    sales_df = load_sales()
    
    # ==============================
    # INITIALIZE LOYALTY DATA IF EMPTY
    # ==============================
    if loyalty_df.empty and not customers_df.empty:
        st.warning("⚠️ Loyalty data is empty. Initializing loyalty records for existing customers...")
        
        loyalty_records = []
        for _, customer in customers_df.iterrows():
            loyalty_records.append({
                "customer_name": customer.get("customer_name", "Unknown"),
                "phone": str(customer.get("phone", "")),
                "points": 0,
                "tier": "🥉 BRONZE",
                "total_spent": float(customer.get("total_spent", 0)),
                "total_orders": int(customer.get("total_orders", 0)),
                "last_visit": datetime.now().strftime("%Y-%m-%d"),
                "birthday": "",
                "joined_date": datetime.now().strftime("%Y-%m-%d")
            })
        
        if loyalty_records:
            loyalty_df = pd.DataFrame(loyalty_records)
            save_loyalty(loyalty_df)
            st.success(f"✅ Created loyalty records for {len(loyalty_records)} customers!")
            st.rerun()
    
    # ==============================
    # CUSTOMER LOYALTY SEARCH
    # ==============================
    st.markdown("## 🔍 Customer Loyalty Lookup")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_phone = st.text_input("Enter Customer Phone Number", placeholder="0712345678 or 782905853")
    
    with col2:
        if st.button("🔍 Search", use_container_width=True):
            if search_phone:
                customer_info = get_customer_loyalty_info(search_phone)
                
                if customer_info:
                    st.session_state.loyalty_customer = customer_info
                    st.success(f"✅ Found customer: {customer_info.get('customer_name', 'Unknown')}")
                else:
                    st.error("❌ Customer not found in loyalty system")
                    st.session_state.loyalty_customer = None
    
    # Display loyalty info if found
    if st.session_state.get("loyalty_customer"):
        info = st.session_state.loyalty_customer
        
        st.markdown("---")
        st.markdown(f"## 👤 {info.get('customer_name', 'Unknown')}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🏆 Tier", info.get('tier', '🥉 BRONZE'))
        with col2:
            st.metric("⭐ Points", f"{info.get('points', 0):,}")
        with col3:
            st.metric("💰 Total Spent", f"${info.get('total_spent', 0):,.2f}")
        with col4:
            st.metric("🛒 Orders", info.get('total_orders', 0))
        
        with st.expander("✨ Tier Benefits"):
            benefits = info.get('benefits', {})
            st.write(f"📈 Points Multiplier: {benefits.get('points_multiplier', 1)}x")
            st.write(f"🎁 Birthday Bonus: {benefits.get('birthday_bonus', 50)} points")
            st.write(f"💰 Tier Discount: {benefits.get('discount', 0)}%")
            st.write(f"🚚 Free Delivery: {'✅ Yes' if benefits.get('free_delivery', False) else '❌ No'}")
        
        points_to_next = info.get('points_to_next_tier', 0)
        if points_to_next > 0:
            st.progress(min(info.get('total_spent', 0) / 5000, 1.0))
            st.caption(f"Spend ${points_to_next:.2f} more to reach next tier")
        else:
            st.success("🎉 You've reached the highest tier!")
    
    st.markdown("---")
    
    # ==============================
    # KEY METRICS
    # ==============================
    st.markdown("## 📊 Loyalty Program Metrics")
    
    total_customers = len(loyalty_df) if not loyalty_df.empty else 0
    total_points = loyalty_df["points"].sum() if not loyalty_df.empty and "points" in loyalty_df.columns else 0
    total_redeemable_value = total_points / 100 if total_points > 0 else 0
    avg_points = loyalty_df["points"].mean() if not loyalty_df.empty and "points" in loyalty_df.columns else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 Loyalty Members", total_customers)
    with col2:
        st.metric("⭐ Total Points", f"{total_points:,.0f}")
    with col3:
        st.metric("💰 Redeemable Value", f"${total_redeemable_value:,.2f}")
    with col4:
        st.metric("📊 Avg Points/Customer", f"{avg_points:.0f}")
    
    st.markdown("---")
    
    # ==============================
    # TIER DISTRIBUTION
    # ==============================
    st.markdown("## 🏆 Customer Tier Distribution")
    
    if not loyalty_df.empty and "tier" in loyalty_df.columns:
        tier_counts = loyalty_df["tier"].value_counts().reset_index()
        tier_counts.columns = ["Tier", "Count"]
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_tier = px.pie(
                tier_counts,
                values="Count",
                names="Tier",
                title="Customer Tier Breakdown",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_tier.update_layout(height=350)
            st.plotly_chart(fig_tier, use_container_width=True)
        
        with col2:
            st.markdown("### ✨ Tier Benefits")
            st.markdown("""
            | Tier | Multiplier | Discount | Birthday Bonus |
            |------|------------|----------|----------------|
            | 🥉 BRONZE | 1x | 0% | 50 points |
            | 🥈 SILVER | 1.2x | 5% | 100 points |
            | 🥇 GOLD | 1.5x | 10% | 200 points |
            | 👑 PLATINUM | 2x | 15% | 500 points |
            """)
    else:
        st.info("No tier data available. Add loyalty records to see distribution.")
    
    st.markdown("---")
    
    # ==============================
    # TOP LOYALTY CUSTOMERS
    # ==============================
    st.markdown("## 🏆 Top Loyalty Customers")
    
    top_customers = get_top_loyalty_customers(10)
    
    if not top_customers.empty:
        fig_top = px.bar(
            top_customers,
            x="points",
            y="customer_name",
            orientation="h",
            title="Top 10 Customers by Points",
            color="tier",
            color_discrete_sequence=px.colors.qualitative.Set1,
            text="points"
        )
        fig_top.update_traces(texttemplate="%{text}", textposition="outside")
        fig_top.update_layout(height=400, xaxis_title="Points", yaxis_title="")
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No loyalty data available yet.")
    
    st.markdown("---")
    
    # ==============================
    # BIRTHDAY REMINDERS
    # ==============================
    st.markdown("## 🎂 Birthday This Month")
    
    birthday_customers = get_birthday_customers()
    
    if not birthday_customers.empty:
        st.success(f"🎉 {len(birthday_customers)} customers celebrating birthdays this month!")
        st.dataframe(birthday_customers, use_container_width=True, hide_index=True)
        
        if st.button("🎁 Send Birthday Greetings"):
            st.info("Birthday messages would be sent here. (SMS/Email integration coming soon)")
    else:
        st.info("No birthdays this month or no birthday data available")
    
    st.markdown("---")
    
    # ==============================
    # CUSTOMER SPENDING TRENDS
    # ==============================
    if not sales_df.empty and "customer" in sales_df.columns:
        st.markdown("## 📈 Customer Spending Trends")
        
        customer_spending = sales_df.groupby("customer")["total"].sum().nlargest(10).reset_index()
        
        if not customer_spending.empty:
            fig_spend = px.bar(
                customer_spending,
                x="total",
                y="customer",
                orientation="h",
                title="Top 10 Customers by Spending",
                color="total",
                color_continuous_scale="Greens",
                text="total"
            )
            fig_spend.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig_spend.update_layout(height=400, xaxis_title="Total Spent ($)", yaxis_title="")
            st.plotly_chart(fig_spend, use_container_width=True)
    else:
        st.info("No sales data available for spending trends")
    
    st.markdown("---")
    
    # ==============================
    # ALL LOYALTY MEMBERS
    # ==============================
    with st.expander("📋 All Loyalty Members"):
        if not loyalty_df.empty:
            st.dataframe(loyalty_df, use_container_width=True, hide_index=True)
            
            csv = loyalty_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Loyalty Data (CSV)",
                data=csv,
                file_name=f"loyalty_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No loyalty data available")
    
    # ==============================
    # WHATSAPP BULK MESSAGING
    # ==============================
    st.markdown("---")
    st.markdown("## 📱 WhatsApp Bulk Messaging")
    st.caption("Send promotions and notifications to customers via WhatsApp")
    
    if customers_df.empty:
        st.warning("No customers available for messaging")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        segment = st.selectbox(
            "Select Customer Segment",
            ["All Customers", "VIP Customers", "Active Customers", "Inactive Customers", "Birthday This Month"],
            key="whatsapp_segment"
        )
    
    with col2:
        message_type = st.selectbox(
            "Message Type",
            ["Promotion", "Birthday Greeting", "General Announcement", "Custom Message"],
            key="whatsapp_message_type"
        )
    
    # Get filtered customer list based on segment
    filtered_customers = customers_df.copy()
    
    if segment == "VIP Customers" and not loyalty_df.empty:
        vip_phones = loyalty_df[loyalty_df["tier"] == "👑 PLATINUM"]["phone"].astype(str).tolist()
        filtered_customers = filtered_customers[filtered_customers["phone"].astype(str).isin(vip_phones)]
    elif segment == "Active Customers" and not loyalty_df.empty:
        active_phones = loyalty_df[loyalty_df["points"] > 100]["phone"].astype(str).tolist()
        filtered_customers = filtered_customers[filtered_customers["phone"].astype(str).isin(active_phones)]
    elif segment == "Inactive Customers" and not loyalty_df.empty:
        inactive_phones = loyalty_df[loyalty_df["points"] == 0]["phone"].astype(str).tolist()
        filtered_customers = filtered_customers[filtered_customers["phone"].astype(str).isin(inactive_phones)]
    elif segment == "Birthday This Month":
        if not birthday_customers.empty:
            birthday_phones = birthday_customers["phone"].astype(str).tolist()
            filtered_customers = filtered_customers[filtered_customers["phone"].astype(str).isin(birthday_phones)]
        else:
            filtered_customers = pd.DataFrame()
    
    # Message input
    final_message = ""
    
    if message_type == "Promotion":
        promo_message = st.text_area("Promotion Message", height=100, 
                                     placeholder="e.g., 20% OFF on all products this weekend!",
                                     key="promo_message")
        discount_code = st.text_input("Discount Code (optional)", placeholder="e.g., SAVE20", key="discount_code")
        
        if promo_message:
            final_message = generate_whatsapp_promotion(promo_message, discount_code)
            st.info(f"📱 Preview:\n\n{final_message}")
    
    elif message_type == "Birthday Greeting":
        birthday_message = st.text_area("Birthday Message", height=100,
                                        placeholder="e.g., Happy Birthday! Enjoy 15% OFF today!",
                                        key="birthday_message")
        final_message = birthday_message
        if birthday_message:
            st.info(f"📱 Preview:\n\n{birthday_message}")
    
    elif message_type == "General Announcement":
        announcement = st.text_area("Announcement", height=100, key="announcement")
        final_message = announcement
        if announcement:
            st.info(f"📱 Preview:\n\n{announcement}")
    
    else:
        custom_message = st.text_area("Custom Message", height=100,
                                      placeholder="Type your custom message here...",
                                      key="custom_message")
        final_message = custom_message
        if custom_message:
            st.info(f"📱 Preview:\n\n{custom_message}")
    
    # Display customer count
    customer_count = len(filtered_customers) if not filtered_customers.empty else 0
    st.info(f"📊 This message will be sent to **{customer_count}** customers")
    
    # Show filtered customers
    if not filtered_customers.empty and customer_count > 0:
        with st.expander("📋 View Recipient List"):
            st.dataframe(
                filtered_customers[["customer_name", "phone"]],
                use_container_width=True,
                hide_index=True
            )
    
    col1, col2 = st.columns(2)
    
    with col1:
        send_button = st.button("📱 Send Bulk WhatsApp", type="primary", use_container_width=True)
        
        if send_button:
            if filtered_customers.empty:
                st.error("❌ No customers found in this segment")
            elif not final_message:
                st.error("❌ Please enter a message to send")
            else:
                # Generate WhatsApp links for each customer
                whatsapp_links = []
                for _, customer in filtered_customers.iterrows():
                    phone = str(customer["phone"])
                    # Clean phone number
                    phone_clean = re.sub(r'\D', '', phone)
                    if phone_clean.startswith('0'):
                        phone_clean = '263' + phone_clean[1:]
                    elif not phone_clean.startswith('263'):
                        phone_clean = '263' + phone_clean
                    
                    name = customer.get("customer_name", "Customer")
                    # Fix: Encode message properly without backslash in f-string
                    encoded_message = final_message.replace(' ', '%20').replace('\n', '%0A')
                    whatsapp_link = f"https://wa.me/{phone_clean}?text={encoded_message}"
                    whatsapp_links.append({
                        "Customer": name,
                        "Phone": phone,
                        "WhatsApp Link": whatsapp_link
                    })
                
                # Display all WhatsApp links
                st.success(f"✅ Generated {len(whatsapp_links)} WhatsApp links!")
                
                links_df = pd.DataFrame(whatsapp_links)
                
                # Display clickable links
                st.markdown("### 📱 Click to send messages")
                
                for idx, row in links_df.iterrows():
                    st.markdown(f"**{row['Customer']}** ({row['Phone']}): [📤 Send WhatsApp]({row['WhatsApp Link']})")
                
                # Download all links as CSV
                csv_links = links_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download WhatsApp Links (CSV)",
                    data=csv_links,
                    file_name=f"whatsapp_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                st.info("💡 Click each link above to send the message via WhatsApp")
    
    with col2:
        # Export customer list for manual WhatsApp Broadcast
        if not customers_df.empty:
            csv_export = customers_df[["customer_name", "phone"]].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Customer List for WhatsApp Broadcast",
                data=csv_export,
                file_name=f"customers_for_whatsapp_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.caption("💡 Import this CSV to WhatsApp Business for bulk broadcast")


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    customers_dashboard()