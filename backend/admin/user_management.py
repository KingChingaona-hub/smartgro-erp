# backend/admin/user_management.py
import streamlit as st
import pandas as pd
from backend.core.db_adapter import load_users, save_users
from backend.core.auth import hash_password, ROLES, init_users
from backend.utils.phone_utils import validate_zimbabwe_phone, format_phone_display
from backend.core.db_adapter import load_branches
import random
import string


def user_management_page():
    """User Management Page (Owner only) - No Auto-Reruns"""
    
    st.title("👥 User Management")
    st.caption("Manage system users - Add, Edit, Delete, and Change Passwords")
    
    # Security check - only owner can access
    if st.session_state.get("role") != "owner":
        st.error("❌ Access Denied. Only system owner can access this page.")
        return
    
    # ==============================
    # SESSION STATE INITIALIZATION
    # ==============================
    if "um_initialized" not in st.session_state:
        st.session_state.um_initialized = False
    
    if "um_message" not in st.session_state:
        st.session_state.um_message = ""
    
    if "um_message_type" not in st.session_state:
        st.session_state.um_message_type = ""
    
    if "um_loading" not in st.session_state:
        st.session_state.um_loading = False
    
    # ==============================
    # LOAD USERS - With Init Check
    # ==============================
    try:
        # Only load users
        users_df = load_users()
        branches_df = load_branches()
        
        # If no users and not initialized, show create button
        if users_df.empty and not st.session_state.um_initialized:
            st.warning("⚠️ No users found in the system.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Create Default Users", type="primary", use_container_width=True):
                    st.session_state.um_loading = True
                    with st.spinner("Creating default users..."):
                        users_df = init_users()
                        if not users_df.empty:
                            st.session_state.um_message = "✅ Default users created successfully!"
                            st.session_state.um_message_type = "success"
                            st.session_state.um_initialized = True
                        else:
                            st.session_state.um_message = "❌ Failed to create default users."
                            st.session_state.um_message_type = "error"
                        st.session_state.um_loading = False
                        st.rerun()
            
            with col2:
                if st.button("🔄 Refresh", use_container_width=True):
                    st.cache_data.clear()
                    st.rerun()
            return
            
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return
    
    # Mark as initialized
    if not users_df.empty:
        st.session_state.um_initialized = True
    
    # Ensure required columns exist
    required_cols = ["username", "password", "role", "branch_id", "full_name", "phone", "active", "last_login"]
    for col in required_cols:
        if col not in users_df.columns:
            if col == "active":
                users_df[col] = True
            elif col == "last_login":
                users_df[col] = ""
            else:
                users_df[col] = ""
    
    # ==============================
    # DISPLAY MESSAGE
    # ==============================
    if st.session_state.um_message:
        if st.session_state.um_message_type == "success":
            st.success(st.session_state.um_message)
        elif st.session_state.um_message_type == "error":
            st.error(st.session_state.um_message)
        else:
            st.info(st.session_state.um_message)
        # Clear message after display
        st.session_state.um_message = ""
        st.session_state.um_message_type = ""
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 View Users",
        "➕ Add New User",
        "🔐 Change Password",
        "🗑️ Delete/Deactivate User"
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
            
            # Export users
            csv = users_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Users (CSV)",
                data=csv,
                file_name="users_export.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No users found.")
    
    # ==============================
    # TAB 2: ADD NEW USER
    # ==============================
    with tab2:
        st.subheader("➕ Add New User")
        st.caption("Create a new user account with proper password hashing")
        
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Username *", placeholder="Enter unique username").strip()
                new_password = st.text_input("Password *", type="password", placeholder="Enter password (min 6 characters)")
                new_full_name = st.text_input("Full Name", placeholder="Enter full name").strip()
            
            with col2:
                new_role = st.selectbox(
                    "Role *", 
                    list(ROLES.keys()), 
                    format_func=lambda x: f"{x.upper()} - {ROLES[x]['description'][:30]}..."
                )
                if not branches_df.empty:
                    new_branch = st.selectbox("Branch", branches_df["branch_id"].tolist())
                else:
                    new_branch = "HO"
                    st.warning("No branches found. Using default branch 'HO'")
                new_phone = st.text_input("Phone Number", placeholder="0777123456", help="Zimbabwe phone number")
            
            new_active = st.checkbox("Active", value=True)
            
            submitted = st.form_submit_button("➕ Create User", type="primary", use_container_width=True)
            
            if submitted:
                # Validate inputs
                if not new_username:
                    st.error("❌ Username is required")
                elif len(new_username) < 3:
                    st.error("❌ Username must be at least 3 characters")
                elif not new_password:
                    st.error("❌ Password is required")
                elif len(new_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                elif new_username in users_df["username"].values:
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
                        try:
                            # Hash the password properly
                            hashed_pw = hash_password(new_password)
                            
                            new_user = pd.DataFrame([{
                                "username": new_username,
                                "password": hashed_pw,
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
                            st.info(f"🔑 Password: {new_password}")
                            st.balloons()
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error creating user: {str(e)}")
    
    # ==============================
    # TAB 3: CHANGE PASSWORD
    # ==============================
    with tab3:
        st.subheader("🔐 Change User Password")
        st.caption("Update passwords for existing users with proper hashing")
        
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
                    - Status: {"✅ Active" if user_data.get('active', True) else "❌ Inactive"}
                    """)
                
                st.markdown("---")
                
                # Password change form
                with st.form("change_password_form"):
                    st.markdown("### Enter New Password")
                    
                    new_password = st.text_input("New Password", type="password", placeholder="Enter new password (min 6 characters)", key="new_pass")
                    confirm_password = st.text_input("Confirm New Password", type="password", placeholder="Confirm new password", key="confirm_pass")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.form_submit_button("🔐 Change Password", type="primary", use_container_width=True):
                            if not new_password:
                                st.error("❌ Please enter a new password")
                            elif len(new_password) < 6:
                                st.error("❌ Password must be at least 6 characters")
                            elif new_password != confirm_password:
                                st.error("❌ Passwords do not match")
                            else:
                                try:
                                    # Update password with proper hashing
                                    hashed_pw = hash_password(new_password)
                                    idx = users_df[users_df["username"] == selected_user].index[0]
                                    users_df.loc[idx, "password"] = hashed_pw
                                    save_users(users_df)
                                    
                                    st.success(f"✅ Password for '{selected_user}' changed successfully!")
                                    st.info(f"🔑 New password: {new_password}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error changing password: {str(e)}")
                    
                    with col2:
                        if st.form_submit_button("🎲 Generate Random Password", use_container_width=True):
                            try:
                                # Generate a random 10-character password
                                characters = string.ascii_letters + string.digits + "!@#$%^&*"
                                random_password = ''.join(random.choice(characters) for _ in range(10))
                                
                                # Update password with proper hashing
                                hashed_pw = hash_password(random_password)
                                idx = users_df[users_df["username"] == selected_user].index[0]
                                users_df.loc[idx, "password"] = hashed_pw
                                save_users(users_df)
                                
                                st.success(f"✅ Password for '{selected_user}' changed to: **{random_password}**")
                                st.info("📋 Please provide this password to the user. They can change it later.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error generating password: {str(e)}")
    
    # ==============================
    # TAB 4: DELETE/DEACTIVATE USER
    # ==============================
    with tab4:
        st.subheader("🗑️ Delete or Deactivate User")
        st.caption("Manage user accounts - Deactivate, Reactivate, or Permanently Delete")
        
        if not users_df.empty:
            # Filter out the current logged-in user to prevent self-deletion
            current_user = st.session_state.get("username", "")
            user_options = [u for u in users_df["username"].tolist() if u != current_user]
            
            if user_options:
                user_to_manage = st.selectbox("Select User to Manage", user_options, key="delete_user_select")
                
                if user_to_manage:
                    user_data = users_df[users_df["username"] == user_to_manage].iloc[0]
                    
                    # Display user info
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"**Username:** {user_data['username']}")
                    with col2:
                        st.info(f"**Role:** {user_data['role'].upper()}")
                    with col3:
                        status = "🟢 Active" if user_data.get('active', True) else "🔴 Inactive"
                        st.info(f"**Status:** {status}")
                    
                    st.markdown("---")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Toggle active status
                        current_status = users_df[users_df["username"] == user_to_manage]["active"].iloc[0]
                        status_text = "Deactivate" if current_status else "Activate"
                        
                        if st.button(f"🔘 {status_text} User", use_container_width=True):
                            try:
                                idx = users_df[users_df["username"] == user_to_manage].index[0]
                                users_df.loc[idx, "active"] = not current_status
                                save_users(users_df)
                                new_status = "deactivated" if not current_status else "activated"
                                st.success(f"✅ User '{user_to_manage}' {new_status} successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error updating user: {str(e)}")
                    
                    with col2:
                        # Delete user
                        if st.button("🗑️ Delete User Permanently", use_container_width=True):
                            if user_to_manage in ["admin"]:
                                st.error("❌ Cannot delete the admin user!")
                            else:
                                confirm = st.checkbox("⚠️ I understand this action CANNOT be undone")
                                if confirm:
                                    try:
                                        users_df = users_df[users_df["username"] != user_to_manage]
                                        save_users(users_df)
                                        st.success(f"✅ User '{user_to_manage}' deleted permanently!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error deleting user: {str(e)}")
                    
                    # Quick actions
                    st.markdown("---")
                    st.markdown("### 🔧 Quick Actions")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("🔐 Reset Password (Random)", use_container_width=True):
                            try:
                                characters = string.ascii_letters + string.digits + "!@#$%^&*"
                                random_password = ''.join(random.choice(characters) for _ in range(10))
                                hashed_pw = hash_password(random_password)
                                idx = users_df[users_df["username"] == user_to_manage].index[0]
                                users_df.loc[idx, "password"] = hashed_pw
                                save_users(users_df)
                                st.success(f"✅ Password reset to: **{random_password}**")
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                    
                    with col2:
                        if st.button("🔄 Reactivate User", use_container_width=True):
                            try:
                                idx = users_df[users_df["username"] == user_to_manage].index[0]
                                users_df.loc[idx, "active"] = True
                                save_users(users_df)
                                st.success(f"✅ User '{user_to_manage}' reactivated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                    
                    with col3:
                        if st.button("📝 Edit User Details", use_container_width=True):
                            st.session_state.editing_user = user_to_manage
                            st.rerun()
            else:
                st.info("No other users available to manage.")
        else:
            st.info("No users found.")
    
    # ==============================
    # EDIT USER DETAILS (Modal-like)
    # ==============================
    if st.session_state.get("editing_user"):
        edit_user = st.session_state.editing_user
        st.markdown("---")
        st.subheader(f"✏️ Edit User: {edit_user}")
        
        user_data = users_df[users_df["username"] == edit_user].iloc[0]
        
        with st.form("edit_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                edit_full_name = st.text_input("Full Name", value=user_data.get("full_name", ""))
                edit_phone = st.text_input("Phone", value=user_data.get("phone", ""))
            
            with col2:
                edit_role = st.selectbox(
                    "Role", 
                    list(ROLES.keys()), 
                    index=list(ROLES.keys()).index(user_data.get("role", "cashier"))
                )
                if not branches_df.empty:
                    branch_list = branches_df["branch_id"].tolist()
                    current_branch = user_data.get("branch_id", "HO")
                    if current_branch in branch_list:
                        branch_index = branch_list.index(current_branch)
                    else:
                        branch_index = 0
                    edit_branch = st.selectbox("Branch", branch_list, index=branch_index)
                else:
                    edit_branch = "HO"
            
            edit_active = st.checkbox("Active", value=user_data.get("active", True))
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                    try:
                        idx = users_df[users_df["username"] == edit_user].index[0]
                        users_df.loc[idx, "full_name"] = edit_full_name
                        users_df.loc[idx, "role"] = edit_role
                        users_df.loc[idx, "branch_id"] = edit_branch
                        users_df.loc[idx, "active"] = edit_active
                        
                        # Validate phone if provided
                        if edit_phone:
                            valid, standardized_phone, msg = validate_zimbabwe_phone(edit_phone)
                            if valid:
                                users_df.loc[idx, "phone"] = standardized_phone
                            else:
                                st.warning(f"Phone validation: {msg}")
                        else:
                            users_df.loc[idx, "phone"] = ""
                        
                        save_users(users_df)
                        st.success(f"✅ User '{edit_user}' updated successfully!")
                        st.session_state.editing_user = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error updating user: {str(e)}")
            
            with col2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.editing_user = None
                    st.rerun()
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()