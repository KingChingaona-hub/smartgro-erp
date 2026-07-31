# backend/admin/user_management.py
# User Management - Fully functional with Edit User fixed

import streamlit as st
import pandas as pd
from datetime import datetime
from backend.core.db_adapter import load_users, save_users
from backend.core.auth import hash_password, ROLES, init_users, check_login
from backend.utils.phone_utils import validate_zimbabwe_phone, format_phone_display
from backend.core.db_adapter import load_branches
import random
import string
import re
import secrets


def user_management_page():
    """User Management Page"""
    
    st.title("User Management")
    st.caption("Manage system users - Add, Edit, Delete, and Change Passwords")
    
    # Security check - only owner can access
    if st.session_state.get("role") != "owner":
        st.error("Access Denied. Only system owner can access this page.")
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
    if "um_force_refresh" not in st.session_state:
        st.session_state.um_force_refresh = False
    if "um_audit_log" not in st.session_state:
        st.session_state.um_audit_log = []
    if "user_created" not in st.session_state:
        st.session_state.user_created = False
    if "user_created_name" not in st.session_state:
        st.session_state.user_created_name = ""
    if "user_updated" not in st.session_state:
        st.session_state.user_updated = False
    if "user_updated_name" not in st.session_state:
        st.session_state.user_updated_name = ""
    
    # ==============================
    # AUDIT LOG FUNCTION
    # ==============================
    def log_audit(action, details=""):
        st.session_state.um_audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "user": st.session_state.get("username", "system"),
            "action": action,
            "details": details,
            "branch": st.session_state.get("branch", "HO")
        })
    
    # ==============================
    # LOAD USERS
    # ==============================
    try:
        if st.session_state.um_force_refresh:
            st.cache_data.clear()
            st.session_state.um_force_refresh = False
        
        users_df = load_users()
        branches_df = load_branches()
        
        if users_df.empty and not st.session_state.um_initialized:
            st.warning("No users found in the system.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Create Default Users", type="primary", use_container_width=True):
                    st.session_state.um_loading = True
                    with st.spinner("Creating default users..."):
                        users_df = init_users()
                        if not users_df.empty:
                            st.session_state.um_message = "Default users created successfully!"
                            st.session_state.um_message_type = "success"
                            st.session_state.um_initialized = True
                            st.session_state.um_force_refresh = True
                            log_audit("CREATE_DEFAULT_USERS", "Created default users")
                        else:
                            st.session_state.um_message = "Failed to create default users."
                            st.session_state.um_message_type = "error"
                        st.session_state.um_loading = False
            return
            
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return
    
    if not users_df.empty:
        st.session_state.um_initialized = True
    
    # Ensure required columns exist
    required_cols = ["username", "password", "role", "branch_id", "full_name", "phone", "whatsapp", "active", "last_login", "mobile_enabled", "two_factor_enabled", "force_password_change"]
    for col in required_cols:
        if col not in users_df.columns:
            if col in ["active", "mobile_enabled", "two_factor_enabled", "force_password_change"]:
                users_df[col] = False
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
        st.session_state.um_message = ""
        st.session_state.um_message_type = ""
    
    # Show update success message
    if st.session_state.user_updated:
        st.success(f"User '{st.session_state.user_updated_name}' updated successfully!")
        st.session_state.user_updated = False
        st.session_state.user_updated_name = ""
    
    # ==============================
    # METRICS
    # ==============================
    st.markdown("## User Metrics")
    
    total_users = len(users_df)
    active_users = len(users_df[users_df["active"] == True])
    inactive_users = total_users - active_users
    owners = len(users_df[users_df["role"] == "owner"])
    managers = len(users_df[users_df["role"] == "manager"])
    cashiers = len(users_df[users_df["role"] == "cashier"])
    viewers = len(users_df[users_df["role"] == "viewer"])
    mobile_users = len(users_df[users_df["mobile_enabled"] == True])
    
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
    
    with col1:
        st.metric("Total", total_users)
    with col2:
        st.metric("Active", active_users)
    with col3:
        st.metric("Inactive", inactive_users)
    with col4:
        st.metric("Owners", owners)
    with col5:
        st.metric("Managers", managers)
    with col6:
        st.metric("Cashiers", cashiers)
    with col7:
        st.metric("Viewers", viewers)
    with col8:
        st.metric("Mobile", mobile_users)
    
    st.markdown("---")
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Users",
        "Add User",
        "Edit User",
        "Password",
        "Delete/Deactivate",
        "Audit Log"
    ])
    
    # ==============================
    # TAB 1: USERS (View)
    # ==============================
    with tab1:
        st.subheader("User List")
        
        # Search and filter
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            search = st.text_input("Search", placeholder="Name, username, phone...")
        with col2:
            role_filter = st.selectbox("Filter Role", ["All"] + list(ROLES.keys()))
        with col3:
            status_filter = st.selectbox("Filter Status", ["All", "Active", "Inactive"])
        with col4:
            branch_filter = st.selectbox("Filter Branch", ["All"] + (branches_df["branch_id"].tolist() if not branches_df.empty else ["HO"]))
        
        # Apply filters
        filtered_df = users_df.copy()
        
        if search:
            search_lower = search.lower()
            filtered_df = filtered_df[
                filtered_df["username"].str.lower().str.contains(search_lower, na=False) |
                filtered_df["full_name"].str.lower().str.contains(search_lower, na=False) |
                filtered_df["phone"].astype(str).str.contains(search_lower, na=False) |
                filtered_df.get("whatsapp", pd.Series()).astype(str).str.contains(search_lower, na=False)
            ]
        
        if role_filter != "All":
            filtered_df = filtered_df[filtered_df["role"] == role_filter]
        
        if status_filter == "Active":
            filtered_df = filtered_df[filtered_df["active"] == True]
        elif status_filter == "Inactive":
            filtered_df = filtered_df[filtered_df["active"] == False]
        
        if branch_filter != "All" and not branches_df.empty:
            filtered_df = filtered_df[filtered_df["branch_id"] == branch_filter]
        
        # Display count
        st.caption(f"Showing {len(filtered_df)} of {len(users_df)} users")
        
        # Display table
        if not filtered_df.empty:
            display_df = filtered_df[["username", "full_name", "role", "branch_id", "phone", "whatsapp", "active", "mobile_enabled", "two_factor_enabled", "last_login"]].copy()
            
            # Apply formatting
            display_df["active"] = display_df["active"].apply(lambda x: "Active" if x else "Inactive")
            display_df["mobile_enabled"] = display_df["mobile_enabled"].apply(lambda x: "Yes" if x else "No")
            display_df["two_factor_enabled"] = display_df["two_factor_enabled"].apply(lambda x: "Yes" if x else "No")
            display_df["phone"] = display_df["phone"].apply(lambda x: format_phone_display(x) if x else "-")
            display_df["whatsapp"] = display_df["whatsapp"].apply(lambda x: format_phone_display(x) if x else "-")
            display_df["last_login"] = display_df["last_login"].fillna("Never")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # ==============================
    # TAB 2: ADD USER
    # ==============================
    with tab2:
        st.subheader("Add New User")
        st.caption("Create a new user account with proper validation")
        
        if st.session_state.user_created:
            st.success(f"User '{st.session_state.user_created_name}' created successfully!")
            st.balloons()
            st.session_state.user_created = False
            st.session_state.user_created_name = ""
        
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Username *", placeholder="Enter unique username").strip()
                new_password = st.text_input("Password *", type="password", placeholder="Enter password (min 8 characters)")
                show_password = st.checkbox("Show password")
                if show_password and new_password:
                    st.code(new_password)
                new_full_name = st.text_input("Full Name *", placeholder="Enter full name").strip()
                new_phone = st.text_input("Phone Number", placeholder="0782905853", help="Zimbabwe phone number")
            
            with col2:
                new_role = st.selectbox("Role *", list(ROLES.keys()))
                if not branches_df.empty:
                    new_branch = st.selectbox("Branch", branches_df["branch_id"].tolist())
                else:
                    new_branch = "HO"
                    st.warning("No branches found. Using default branch 'HO'")
                new_whatsapp = st.text_input("WhatsApp", placeholder="0782905853", help="Zimbabwe WhatsApp number")
                new_mobile = st.checkbox("Enable Mobile Access")
                new_2fa = st.checkbox("Enable 2FA")
                new_active = st.checkbox("Active", value=True)
                new_force_password = st.checkbox("Force Password Change on Next Login", value=True)
            
            submitted = st.form_submit_button("Create User", type="primary", use_container_width=True)
            
            if submitted:
                # Reload users to check for duplicates
                current_users = load_users()
                errors = []
                warnings = []
                standardized_phone = ""
                standardized_whatsapp = ""
                
                # Validation
                if not new_username:
                    errors.append("Username is required")
                elif len(new_username) < 3:
                    errors.append("Username must be at least 3 characters")
                elif not re.match(r'^[a-zA-Z0-9_]+$', new_username):
                    errors.append("Username can only contain letters, numbers, and underscores")
                elif not current_users.empty and new_username in current_users["username"].values:
                    errors.append(f"Username '{new_username}' already exists!")
                
                if not new_password:
                    errors.append("Password is required")
                elif len(new_password) < 8:
                    errors.append("Password must be at least 8 characters")
                else:
                    # Password strength check
                    strength = 0
                    if len(new_password) >= 8:
                        strength += 1
                    if re.search(r'[A-Z]', new_password):
                        strength += 1
                    if re.search(r'[a-z]', new_password):
                        strength += 1
                    if re.search(r'[0-9]', new_password):
                        strength += 1
                    if re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', new_password):
                        strength += 1
                    
                    if strength <= 2:
                        warnings.append("Password is weak. Consider using a stronger password with uppercase, lowercase, numbers, and special characters.")
                
                if not new_full_name:
                    errors.append("Full name is required")
                
                # Phone validation
                if new_phone:
                    valid, standardized_phone, msg = validate_zimbabwe_phone(new_phone)
                    if not valid:
                        errors.append(f"Phone: {msg}")
                    elif not current_users.empty and "phone" in current_users.columns and standardized_phone in current_users["phone"].values:
                        errors.append(f"Phone number {format_phone_display(standardized_phone)} already in use by another user")
                
                # WhatsApp validation
                if new_whatsapp:
                    valid, standardized_whatsapp, msg = validate_zimbabwe_phone(new_whatsapp)
                    if not valid:
                        errors.append(f"WhatsApp: {msg}")
                    elif "whatsapp" in current_users.columns and standardized_whatsapp in current_users["whatsapp"].values:
                        errors.append(f"WhatsApp number {format_phone_display(standardized_whatsapp)} already in use by another user")
                
                if errors:
                    for error in errors:
                        st.error(f"{error}")
                else:
                    if warnings:
                        for warning in warnings:
                            st.warning(f"{warning}")
                    
                    try:
                        # Hash the password
                        hashed_pw = hash_password(new_password)
                        
                        # Create new user DataFrame
                        new_user_data = {
                            "username": new_username,
                            "password": hashed_pw,
                            "role": new_role,
                            "branch_id": new_branch,
                            "full_name": new_full_name,
                            "phone": standardized_phone if new_phone else "",
                            "whatsapp": standardized_whatsapp if new_whatsapp else "",
                            "active": new_active,
                            "mobile_enabled": new_mobile,
                            "two_factor_enabled": new_2fa,
                            "force_password_change": new_force_password,
                            "last_login": "",
                            "last_mobile_login": "",
                            "device_info": "",
                            "session_token": "",
                            "receive_alerts": True
                        }
                        
                        new_user = pd.DataFrame([new_user_data])
                        
                        # IMPORTANT: Load fresh users before saving to avoid overwriting
                        fresh_users = load_users()
                        
                        if fresh_users.empty:
                            updated_users = new_user
                        else:
                            updated_users = pd.concat([fresh_users, new_user], ignore_index=True)
                        
                        # Save to database
                        save_users(updated_users)
                        
                        log_audit("USER_CREATED", f"Created user: {new_username} ({new_role})")
                        
                        # Set session state to show success message
                        st.session_state.user_created = True
                        st.session_state.user_created_name = new_username
                        st.session_state.um_force_refresh = True
                        
                        st.success(f"User '{new_username}' created successfully!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error creating user: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
    
    # ==============================
    # TAB 3: EDIT USER - FIXED
    # ==============================
    with tab3:
        st.subheader("Edit User")
        
        if not users_df.empty:
            user_list = users_df["username"].tolist()
            edit_user = st.selectbox("Select User to Edit", user_list)
            
            if edit_user:
                user_data = users_df[users_df["username"] == edit_user].iloc[0]
                
                # Show current user info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Username:** {edit_user}")
                with col2:
                    st.info(f"**Current Role:** {user_data.get('role', 'N/A')}")
                with col3:
                    status = "Active" if user_data.get('active', True) else "Inactive"
                    st.info(f"**Current Status:** {status}")
                
                st.markdown("---")
                
                with st.form("edit_user_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_full_name = st.text_input("Full Name", value=user_data.get("full_name", ""))
                        edit_phone = st.text_input("Phone", value=user_data.get("phone", ""))
                        edit_whatsapp = st.text_input("WhatsApp", value=user_data.get("whatsapp", ""))
                    
                    with col2:
                        edit_role = st.selectbox("Role", list(ROLES.keys()), index=list(ROLES.keys()).index(user_data.get("role", "cashier")))
                        if not branches_df.empty:
                            branch_list = branches_df["branch_id"].tolist()
                            current_branch = user_data.get("branch_id", "HO")
                            edit_branch = st.selectbox("Branch", branch_list, index=branch_list.index(current_branch) if current_branch in branch_list else 0)
                        else:
                            edit_branch = "HO"
                        
                        edit_mobile = st.checkbox("Mobile Access", value=user_data.get("mobile_enabled", False))
                        edit_2fa = st.checkbox("2FA Enabled", value=user_data.get("two_factor_enabled", False))
                        edit_active = st.checkbox("Active", value=user_data.get("active", True))
                        edit_force_password = st.checkbox("Force Password Change", value=user_data.get("force_password_change", False))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Save Changes", type="primary", use_container_width=True):
                            try:
                                # Load fresh data
                                current_users = load_users()
                                
                                # Find the user
                                user_mask = current_users["username"] == edit_user
                                if not user_mask.any():
                                    st.error(f"User '{edit_user}' not found")
                                    st.stop()
                                
                                idx = current_users[user_mask].index[0]
                                
                                # Validate phone
                                if edit_phone:
                                    valid, standardized_phone, msg = validate_zimbabwe_phone(edit_phone)
                                    if not valid:
                                        st.error(f"Phone: {msg}")
                                        st.stop()
                                    # Check if phone is used by another user
                                    phone_exists = False
                                    if "phone" in current_users.columns:
                                        for i, row in current_users.iterrows():
                                            if i != idx and row.get("phone") == standardized_phone:
                                                phone_exists = True
                                                break
                                    if phone_exists:
                                        st.error(f"Phone number {format_phone_display(standardized_phone)} already in use by another user")
                                        st.stop()
                                    current_users.loc[idx, "phone"] = standardized_phone
                                else:
                                    current_users.loc[idx, "phone"] = ""
                                
                                # Validate WhatsApp
                                if edit_whatsapp:
                                    valid, standardized_whatsapp, msg = validate_zimbabwe_phone(edit_whatsapp)
                                    if not valid:
                                        st.error(f"WhatsApp: {msg}")
                                        st.stop()
                                    # Check if WhatsApp is used by another user
                                    whatsapp_exists = False
                                    if "whatsapp" in current_users.columns:
                                        for i, row in current_users.iterrows():
                                            if i != idx and row.get("whatsapp") == standardized_whatsapp:
                                                whatsapp_exists = True
                                                break
                                    if whatsapp_exists:
                                        st.error(f"WhatsApp number {format_phone_display(standardized_whatsapp)} already in use by another user")
                                        st.stop()
                                    current_users.loc[idx, "whatsapp"] = standardized_whatsapp
                                else:
                                    current_users.loc[idx, "whatsapp"] = ""
                                
                                # Update other fields
                                current_users.loc[idx, "full_name"] = edit_full_name
                                current_users.loc[idx, "role"] = edit_role
                                current_users.loc[idx, "branch_id"] = edit_branch
                                current_users.loc[idx, "mobile_enabled"] = edit_mobile
                                current_users.loc[idx, "two_factor_enabled"] = edit_2fa
                                current_users.loc[idx, "active"] = edit_active
                                current_users.loc[idx, "force_password_change"] = edit_force_password
                                
                                # Save changes
                                save_users(current_users)
                                log_audit("USER_UPDATED", f"Updated user: {edit_user}")
                                
                                # Set session state and refresh
                                st.session_state.user_updated = True
                                st.session_state.user_updated_name = edit_user
                                st.session_state.um_force_refresh = True
                                
                                st.success(f"User '{edit_user}' updated successfully!")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Error updating user: {str(e)}")
                    
                    with col2:
                        if st.form_submit_button("Cancel", use_container_width=True):
                            st.rerun()
        else:
            st.info("No users found")
    
    # ==============================
    # TAB 4: PASSWORD MANAGEMENT
    # ==============================
    with tab4:
        st.subheader("Password Management")
        
        if not users_df.empty:
            user_list = users_df["username"].tolist()
            password_user = st.selectbox("Select User", user_list, key="password_user")
            
            if password_user:
                user_data = users_df[users_df["username"] == password_user].iloc[0]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"User: {password_user} ({user_data.get('role', 'N/A')})")
                
                with col2:
                    st.info(f"Status: {'Active' if user_data.get('active', True) else 'Inactive'}")
                
                with st.form("password_form"):
                    new_password = st.text_input("New Password", type="password", placeholder="Enter new password (min 8 characters)")
                    confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm new password")
                    force_change = st.checkbox("Force password change on next login", value=user_data.get("force_password_change", False))
                    
                    # Password strength meter
                    if new_password:
                        strength = 0
                        if len(new_password) >= 8:
                            strength += 1
                        if re.search(r'[A-Z]', new_password):
                            strength += 1
                        if re.search(r'[a-z]', new_password):
                            strength += 1
                        if re.search(r'[0-9]', new_password):
                            strength += 1
                        if re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', new_password):
                            strength += 1
                        
                        st.progress(strength / 5)
                        strength_text = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong"][strength-1] if strength > 0 else "Very Weak"
                        st.caption(f"Strength: {strength_text}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.form_submit_button("Change Password", type="primary", use_container_width=True):
                            if not new_password:
                                st.error("Please enter a new password")
                            elif len(new_password) < 8:
                                st.error("Password must be at least 8 characters")
                            elif new_password != confirm_password:
                                st.error("Passwords do not match")
                            else:
                                try:
                                    current_users = load_users()
                                    hashed_pw = hash_password(new_password)
                                    idx = current_users[current_users["username"] == password_user].index[0]
                                    current_users.loc[idx, "password"] = hashed_pw
                                    current_users.loc[idx, "force_password_change"] = force_change
                                    save_users(current_users)
                                    
                                    log_audit("PASSWORD_CHANGED", f"Changed password for: {password_user}")
                                    st.session_state.um_force_refresh = True
                                    st.success(f"Password for '{password_user}' changed successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error changing password: {str(e)}")
                    
                    with col2:
                        if st.form_submit_button("Generate Random Password", use_container_width=True):
                            try:
                                characters = string.ascii_letters + string.digits + "!@#$%^&*"
                                random_password = ''.join(random.choice(characters) for _ in range(12))
                                
                                current_users = load_users()
                                hashed_pw = hash_password(random_password)
                                idx = current_users[current_users["username"] == password_user].index[0]
                                current_users.loc[idx, "password"] = hashed_pw
                                current_users.loc[idx, "force_password_change"] = True
                                save_users(current_users)
                                
                                st.success(f"Password for '{password_user}' changed to:")
                                st.code(random_password)
                                st.info("Please provide this password to the user. They can change it later.")
                                log_audit("PASSWORD_RESET", f"Generated new password for: {password_user}")
                                st.session_state.um_force_refresh = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error generating password: {str(e)}")
        else:
            st.info("No users found")
    
    # ==============================
    # TAB 5: DELETE/DEACTIVATE
    # ==============================
    with tab5:
        st.subheader("Delete or Deactivate User")
        
        if not users_df.empty:
            current_user = st.session_state.get("username", "")
            user_options = [u for u in users_df["username"].tolist() if u != current_user]
            
            if user_options:
                delete_user = st.selectbox("Select User to Manage", user_options, key="delete_user")
                
                if delete_user:
                    user_data = users_df[users_df["username"] == delete_user].iloc[0]
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"**Username:** {delete_user}")
                    with col2:
                        st.info(f"**Role:** {user_data['role'].upper()}")
                    with col3:
                        status = "Active" if user_data.get('active', True) else "Inactive"
                        st.info(f"**Status:** {status}")
                    
                    st.markdown("---")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        current_status = user_data.get("active", True)
                        status_text = "Deactivate" if current_status else "Activate"
                        
                        if st.button(f"{status_text} User", use_container_width=True):
                            try:
                                current_users = load_users()
                                idx = current_users[current_users["username"] == delete_user].index[0]
                                current_users.loc[idx, "active"] = not current_status
                                save_users(current_users)
                                new_status = "deactivated" if not current_status else "activated"
                                log_audit(f"USER_{new_status.upper()}", f"{new_status} user: {delete_user}")
                                st.session_state.um_force_refresh = True
                                st.success(f"User '{delete_user}' {new_status} successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating user: {str(e)}")
                    
                    with col2:
                        if st.button("Delete User Permanently", use_container_width=True):
                            if delete_user in ["admin"]:
                                st.error("Cannot delete the admin user!")
                            else:
                                is_owner = user_data.get("role") == "owner"
                                if is_owner:
                                    owners_count = len(users_df[users_df["role"] == "owner"])
                                    if owners_count <= 1:
                                        st.error("Cannot delete the last owner!")
                                    else:
                                        st.warning(f"This will permanently delete user '{delete_user}'. This action CANNOT be undone.")
                                        confirm = st.checkbox("I understand this action CANNOT be undone")
                                        if confirm:
                                            try:
                                                current_users = load_users()
                                                current_users = current_users[current_users["username"] != delete_user]
                                                save_users(current_users)
                                                log_audit("USER_DELETED", f"Deleted user: {delete_user}")
                                                st.session_state.um_force_refresh = True
                                                st.success(f"User '{delete_user}' deleted permanently!")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Error deleting user: {str(e)}")
                                else:
                                    st.warning(f"This will permanently delete user '{delete_user}'. This action CANNOT be undone.")
                                    confirm = st.checkbox("I understand this action CANNOT be undone")
                                    if confirm:
                                        try:
                                            current_users = load_users()
                                            current_users = current_users[current_users["username"] != delete_user]
                                            save_users(current_users)
                                            log_audit("USER_DELETED", f"Deleted user: {delete_user}")
                                            st.session_state.um_force_refresh = True
                                            st.success(f"User '{delete_user}' deleted permanently!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error deleting user: {str(e)}")
        else:
            st.info("No users found")
    
    # ==============================
    # TAB 6: AUDIT LOG
    # ==============================
    with tab6:
        st.subheader("Audit Log")
        st.caption("Track all user management actions")
        
        if st.session_state.um_audit_log:
            audit_df = pd.DataFrame(st.session_state.um_audit_log)
            audit_df["timestamp"] = pd.to_datetime(audit_df["timestamp"])
            audit_df["timestamp"] = audit_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(audit_df, use_container_width=True, hide_index=True)
            
            # Export audit log
            csv = audit_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Audit Log (CSV)",
                data=csv,
                file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No audit logs recorded yet")
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.um_force_refresh = True
        st.rerun()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    user_management_page()