import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from backend.core.db_adapter import load_customers, load_sales
from backend.modules.loyalty import (
    load_loyalty,
    get_top_loyalty_customers,
    get_birthday_customers,
    get_customer_loyalty_info,
    get_tier_benefits
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
    # CUSTOMER LOYALTY SEARCH
    # ==============================
    st.markdown("## 🔍 Customer Loyalty Lookup")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_phone = st.text_input("Enter Customer Phone Number", placeholder="0712345678")
    
    with col2:
        if st.button("Search", use_container_width=True):
            if search_phone:
                customer_info = get_customer_loyalty_info(search_phone)
                
                if customer_info:
                    st.session_state.loyalty_customer = customer_info
                else:
                    st.error("Customer not found")
    
    # Display loyalty info if found
    if st.session_state.get("loyalty_customer"):
        info = st.session_state.loyalty_customer
        
        st.markdown("---")
        st.markdown(f"## 👤 {info['customer_name']}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🏆 Tier", info['tier'])
        with col2:
            st.metric("⭐ Points", f"{info['points']:,}")
        with col3:
            st.metric("💰 Total Spent", f"${info['total_spent']:,.2f}")
        with col4:
            st.metric("🛒 Orders", info['total_orders'])
        
        # Tier benefits
        with st.expander("✨ Tier Benefits"):
            benefits = info['benefits']
            st.write(f"📈 Points Multiplier: {benefits['points_multiplier']}x")
            st.write(f"🎁 Birthday Bonus: {benefits['birthday_bonus']} points")
            st.write(f"💰 Tier Discount: {benefits['discount']}%")
            st.write(f"🚚 Free Delivery: {'Yes' if benefits['free_delivery'] else 'No'}")
        
        # Points to next tier
        if info['points_to_next_tier'] > 0:
            st.progress(min(info['total_spent'] / 5000, 1.0))
            st.caption(f"Spend ${info['points_to_next_tier']:.2f} more to reach next tier")
    
    st.markdown("---")
    
    # ==============================
    # KEY METRICS
    # ==============================
    st.markdown("## 📊 Loyalty Program Metrics")
    
    total_customers = len(loyalty_df)
    total_points = loyalty_df["points"].sum() if not loyalty_df.empty else 0
    total_redeemable_value = total_points / 100
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 Loyalty Members", total_customers)
    with col2:
        st.metric("⭐ Total Points", f"{total_points:,}")
    with col3:
        st.metric("💰 Redeemable Value", f"${total_redeemable_value:,.2f}")
    with col4:
        avg_points = loyalty_df["points"].mean() if not loyalty_df.empty else 0
        st.metric("📊 Avg Points/Customer", f"{avg_points:.0f}")
    
    st.markdown("---")
    
    # ==============================
    # TIER DISTRIBUTION
    # ==============================
    st.markdown("## 🏆 Customer Tier Distribution")
    
    if not loyalty_df.empty:
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
            # Tier benefits summary
            st.markdown("### ✨ Tier Benefits")
            st.markdown("""
            | Tier | Multiplier | Discount | Birthday Bonus |
            |------|------------|----------|----------------|
            | 🥉 BRONZE | 1x | 0% | 50 points |
            | 🥈 SILVER | 1.2x | 5% | 100 points |
            | 🥇 GOLD | 1.5x | 10% | 200 points |
            | 👑 PLATINUM | 2x | 15% | 500 points |
            """)
    
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
        st.info("No birthdays this month")
    
    st.markdown("---")
    
    # ==============================
    # CUSTOMER SPENDING TRENDS
    # ==============================
    if not sales_df.empty and "customer" in sales_df.columns:
        st.markdown("## 📈 Customer Spending Trends")
        
        # Top spending customers
        customer_spending = sales_df.groupby("customer")["total"].sum().nlargest(10).reset_index()
        
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
    
    st.markdown("---")
    
    # ==============================
    # ALL LOYALTY MEMBERS
    # ==============================
    with st.expander("📋 All Loyalty Members"):
        if not loyalty_df.empty:
            st.dataframe(loyalty_df, use_container_width=True, hide_index=True)
            
            # Export
            csv = loyalty_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Loyalty Data (CSV)",
                data=csv,
                file_name=f"loyalty_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # ==============================
    # NEW TAB: WHATSAPP BULK MESSAGING
    # ==============================
    st.markdown("---")
    st.markdown("## 📱 WhatsApp Bulk Messaging")
    st.caption("Send promotions and notifications to customers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Select customer segment
        segment = st.selectbox(
            "Select Customer Segment",
            ["All Customers", "VIP Customers", "Active Customers", "Inactive Customers", "Birthday This Month"],
            key="whatsapp_segment"
        )
    
    with col2:
        # Message template
        message_type = st.selectbox(
            "Message Type",
            ["Promotion", "Birthday Greeting", "General Announcement"],
            key="whatsapp_message_type"
        )
    
    # Message input based on type
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
    
    else:
        announcement = st.text_area("Announcement", height=100, key="announcement")
        final_message = announcement
        if announcement:
            st.info(f"📱 Preview:\n\n{announcement}")
    
    # Customer count (estimate)
    if segment == "All Customers":
        customer_count = len(customers_df) if not customers_df.empty else 0
    elif segment == "VIP Customers":
        customer_count = len(loyalty_df[loyalty_df["tier"] == "👑 PLATINUM"]) if not loyalty_df.empty else 0
    elif segment == "Active Customers":
        customer_count = len(loyalty_df[loyalty_df["points"] > 100]) if not loyalty_df.empty else 0
    else:
        customer_count = 0
    
    st.info(f"📊 This message will be sent to approximately **{customer_count}** customers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📱 Send Bulk WhatsApp", type="primary", use_container_width=True):
            st.warning("⚠️ Bulk WhatsApp requires WhatsApp Business API. Use individual sending for now.")
            st.info("💡 Tip: Export customer list and use WhatsApp Broadcast feature")
    
    with col2:
        # Export customer list
        if not customers_df.empty:
            csv = customers_df[["customer_name", "phone"]].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Customer List for WhatsApp",
                data=csv,
                file_name=f"customers_for_whatsapp_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )