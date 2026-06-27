# backend/admin/user_management.py
import streamlit as st
import pandas as pd
from backend.core.database import load_users, save_users
from backend.core.auth import hash_password, ROLES
from backend.utils.phone_utils import validate_zimbabwe_phone, format_phone_display
from backend.core.db_adapter import load_branches


def user_management_page():
    """User Management Page (Owner only) - With Password Change"""
    
    st.title("👥 User Management")
    st.caption("Manage system users - Add, Edit, Delete, and Change Passwords")
    
    # Security check - only owner can access
    if st.session_state.get("role") != "owner":
        st.error("❌ Access Denied. Only system owner can access this page.")
        return
    
    # Load data
    users_df = load_users()
    branches_df = load_branches()
    
    # Ensure required columns exist
    required_cols = ["username", "password", "role", "branch_id", "full_name", "phone", "active", "last_login"]
    for col in required_cols:
        if col not in users_df.columns:
            if col == "active":
                users_df[col] = True
            elif col == "last_login":
                users_df[col] ""
            else:
                users_df[col] = ""
    
    # ==============================
    # CHECK IF USERS EXIST - CREATE DEFAULTS IF EMPTY
    # ==============================
    if users_df.empty:
        st.warning("⚠️ No users found in the system. Creating default users...")
        from backend.core.auth import init_users
        users_df = init_users()
        if users_df.empty:
            st.error("❌ Failed to create default users. Please check database connection.")
            return
        st.success("✅ Default users created successfully!")
        st.rerun()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "👥 View Users",
        "➕ Add New User",
        "🔐 Change Password"
    ])
    
    # ==============================
    # TAB 1: VIEW USERS
    # ==============================
    with tab1:
        st.subheader("📋 Existing Users")
        
        if not users_df.empty:
            # Prepare display dataframe
            display_df = users_df[["username", "full_name", "role", "branch_id", "phone", "active", "last_login"]].copy()
            display_df["active"] = display_df["active"].apply(lambda x: "✅ Active" if x else "❌ Inactive")
            display_df["phone"] = display_df["phone"].apply(lambda x: format_phone_display(x) if x else "-")
            display_df["last_login"] = display_df["last_login"].fillna("-")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Users", len(users_df))
            with col2:
                st.metric("Active Users", len(users_df[users_df["active"] == True]))
            with col3:
                st.metric("Owners", len(users_df[users_df["role"] == "owner"]))
            with col4:
                st.metric("Cashiers", len(users_df[users_df["role"] == "cashier"]))
        else:
            st.info("No users found")
            if st.button("🔄 Create Default Users"):
                from backend.core.auth import init_users
                users_df = init_users()
                st.rerun()
    
    # ==============================
    # TAB 2: ADD NEW USER
    # ==============================
    with tab2:
        st.subheader("➕ Add New User")
        
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Username *", placeholder="Enter unique username")
                new_password = st.text_input("Password *", type="password", placeholder="Enter password")
                new_full_name = st.text_input("Full Name", placeholder="Enter full name")
            
            with col2:
                new_role = st.selectbox("Role *", list(ROLES.keys()), 
                                       format_func=lambda x: f"{x.upper()} - {ROLES[x]['description'][:30]}...")
                new_branch = st.selectbox("Branch", branches_df["branch_id"].tolist())
                new_phone = st.text_input("Phone Number", placeholder="0777123456", help="Zimbabwe phone number")
            
            new_active = st.checkbox("Active", value=True)
            
            if st.form_submit_button("➕ Create User", type="primary", use_container_width=True):
                if new_username and new_password:
                    if new_username in users_df["username"].values:
                        st.error(f"❌ Username '{new_username}' already exists!")
                    else:
                        # Validate phone if provided
                        phone_valid = True
                        standardized_phone = ""
                        if new_phone:
                            valid, standardized_phone, msg = validate_zimbabwe_phone(new_phone)
                            if not valid:
                                st.error(f"❌ {msg}")
                                phone_valid = False
                        
                        if phone_valid:
                            new_user = pd.DataFrame([{
                                "username": new_username,
                                "password": hash_password(new_password),
                                "role": new_role,
                                "branch_id": new_branch,
                                "full_name": new_full_name if new_full_name else new_username,
                                "phone": standardized_phone,
                                "active": new_active,
                                "last_login": ""
                            }])
                            
                            users_df = pd.concat([users_df, new_user], ignore_index=True)
                            save_users(users_df)
                            st.success(f"✅ User '{new_username}' created successfully!")
                            st.rerun()
                else:
                    st.error("❌ Username and password are required")
    
    # ==============================
    # TAB 3: CHANGE PASSWORD
    # ==============================
    with tab3:
        st.subheader("🔐 Change User Password")
        st.caption("Update passwords for existing users")
        
        if not users_df.empty:
            # Select user to change password
            user_list = users_df["username"].tolist()
            selected_user = st.selectbox("Select User", user_list, key="password_user_select")
            
            if selected_user:
                user_data = users_df[users_df["username"] == selected_user].iloc[0]
                
                # Display user info
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"""
                    **User Information:**
                    - Username: {user_data['username']}
                    - Full Name: {user_data.get('full_name', 'N/A')}
                    - Role: {user_data['role'].upper()}
                    - Branch: {user_data.get('branch_id', 'N/A')}
                    """)
                
                with col2:
                    st.warning(f"""
                    **Password Security:**
                    - Last Login: {user_data.get('last_login', 'Never') if user_data.get('last_login') else 'Never'}
                    - Status: {"Active" if user_data.get('active', True) else "Inactive"}
                    """)
                
                st.markdown("---")
                
                # Password change form
                with st.form("change_password_form"):
                    st.markdown("### Enter New Password")
                    
                    new_password = st.text_input("New Password", type="password", placeholder="Enter new password", key="new_pass")
                    confirm_password = st.text_input("Confirm New Password", type="password", placeholder="Confirm new password", key="confirm_pass")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.form_submit_button("🔐 Change Password", type="primary", use_container_width=True):
                            if not new_password:
                                st.error("❌ Please enter a new password")
                            elif len(new_password) < 4:
                                st.error("❌ Password must be at least 4 characters")
                            elif new_password != confirm_password:
                                st.error("❌ Passwords do not match")
                            else:
                                # Update password
                                idx = users_df[users_df["username"] == selected_user].index[0]
                                users_df.loc[idx, "password"] = hash_password(new_password)
                                save_users(users_df)
                                
                                st.success(f"✅ Password for '{selected_user}' changed successfully!")
                                st.info("🔒 User can now login with the new password")
                                st.rerun()
                    
                    with col2:
                        # Generate random password button
                        if st.form_submit_button("🎲 Generate Random Password", use_container_width=True):
                            import random
                            import string
                            
                            # Generate a random 8-character password
                            characters = string.ascii_letters + string.digits
                            random_password = ''.join(random.choice(characters) for _ in range(8))
                            
                            # Update password
                            idx = users_df[users_df["username"] == selected_user].index[0]
                            users_df.loc[idx, "password"] = hash_password(random_password)
                            save_users(users_df)
                            
                            st.success(f"✅ Password for '{selected_user}' changed to: **{random_password}**")
                            st.info("📋 Please provide this password to the user. They can change it later.")
                            st.rerun()
                
                # Reset password warning
                st.markdown("---")
                st.warning("""
                ⚠️ **Password Security Notes:**
                - Passwords are stored using SHA-256 encryption
                - Users should change their password regularly
                - Never share passwords via insecure channels
                - Contact administrator if a user forgets their password
                """)
        else:
            st.info("No users found. Add users first.")
    
    # ==============================
    # DELETE/DEACTIVATE USER SECTION
    # ==============================
    st.markdown("---")
    st.subheader("🗑️ Delete or Deactivate User")
    
    if not users_df.empty and len(users_df) > 1:
        user_to_manage = st.selectbox("Select User to Manage", users_df["username"].tolist(), key="delete_user_select")
        
        if user_to_manage != "admin":
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Toggle active status
                current_status = users_df[users_df["username"] == user_to_manage]["active"].iloc[0]
                status_text = "Deactivate" if current_status else "Activate"
                if st.button(f"🔘 {status_text} User", use_container_width=True):
                    idx = users_df[users_df["username"] == user_to_manage].index[0]
                    users_df.loc[idx, "active"] = not current_status
                    save_users(users_df)
                    st.success(f"✅ User '{user_to_manage}' {status_text}d successfully!")
                    st.rerun()
            
            with col2:
                # Reset password (quick option)
                if st.button("🔐 Reset Password", use_container_width=True):
                    import random
                    import string
                    
                    random_password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
                    idx = users_df[users_df["username"] == user_to_manage].index[0]
                    users_df.loc[idx, "password"] = hash_password(random_password)
                    save_users(users_df)
                    st.success(f"✅ Password reset to: **{random_password}**")
                    st.info("Share this password with the user")
            
            with col3:
                # Delete user
                if st.button("🗑️ Delete User", use_container_width=True):
                    confirm = st.checkbox("⚠️ I understand this action CANNOT be undone")
                    if confirm:
                        users_df = users_df[users_df["username"] != user_to_manage]
                        save_users(users_df)
                        st.success(f"✅ User '{user_to_manage}' deleted successfully!")
                        st.rerun()
        else:
            st.info("Admin user cannot be deleted or deactivated")
    else:
        st.info("Cannot delete the only remaining admin user")
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()