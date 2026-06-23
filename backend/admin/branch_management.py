import streamlit as st
import pandas as pd
from backend.core.db_adapter import load_branches, save_branches


def branch_management_page():
    """Branch Management Page - Add, Edit, Delete Branches"""
    
    st.title("🏢 Branch Management")
    st.caption("Manage your business branches - Add, Edit, or Delete branches")
    
    # Security check - only owner can access
    if st.session_state.get("role") != "owner":
        st.error("❌ Access Denied. Only system owner can access branch management.")
        return
    
    # Load branches
    df = load_branches()
    
    # ==============================
    # ENSURE REQUIRED COLUMNS EXIST
    # ==============================
    required_columns = ["branch_id", "branch_name", "location", "level", "active"]
    
    for col in required_columns:
        if col not in df.columns:
            if col == "active":
                df[col] = True
            elif col == "level":
                df[col] = 1
            else:
                df[col] = ""
    
    save_branches(df)
    
    # ==============================
    # DISPLAY EXISTING BRANCHES
    # ==============================
    st.subheader("📋 Existing Branches")
    
    if not df.empty:
        # Format for display
        display_df = df.copy()
        display_df["active"] = display_df["active"].apply(lambda x: "✅ Active" if x else "❌ Inactive")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🏢 Total Branches", len(df))
        with col2:
            st.metric("✅ Active Branches", len(df[df["active"] == True]))
        with col3:
            st.metric("📊 Total Levels", df["level"].nunique())
    else:
        st.info("No branches available. Add your first branch below.")
    
    st.markdown("---")
    
    # ==============================
    # ADD NEW BRANCH
    # ==============================
    st.subheader("➕ Add New Branch")
    
    with st.form("add_branch_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            branch_id = st.text_input("Branch Code *", placeholder="e.g., BR004 or HO", help="Unique branch identifier")
            branch_name = st.text_input("Branch Name *", placeholder="e.g., Harare City Centre")
            location = st.text_input("Location", placeholder="e.g., Harare, Bulawayo, Mutare")
        
        with col2:
            level = st.selectbox("Branch Level", [1, 2, 3, 4, 5, 6], 
                                help="1=Head Office, 2=National, 3=Provincial, 4=District, 5=Village, 6=Other")
            active = st.checkbox("Active Branch", value=True)
        
        submitted = st.form_submit_button("➕ Add Branch", type="primary", use_container_width=True)
        
        if submitted:
            if branch_id.strip() == "":
                st.error("❌ Branch Code is required")
            elif branch_name.strip() == "":
                st.error("❌ Branch Name is required")
            elif branch_id.upper() in df["branch_id"].astype(str).str.upper().tolist():
                st.error(f"❌ Branch Code '{branch_id.upper()}' already exists!")
            else:
                new_branch = pd.DataFrame([{
                    "branch_id": branch_id.strip().upper(),
                    "branch_name": branch_name.strip(),
                    "location": location.strip(),
                    "level": level,
                    "active": active
                }])
                
                df = pd.concat([df, new_branch], ignore_index=True)
                save_branches(df)
                
                st.success(f"✅ Branch '{branch_name}' added successfully!")
                st.balloons()
                st.rerun()
    
    st.markdown("---")
    
    # ==============================
    # UPDATE / EDIT BRANCH
    # ==============================
    st.subheader("✏️ Update / Edit Branch")
    
    if not df.empty:
        # Create a list of branch names for selection
        branch_names = df["branch_name"].tolist()
        selected_branch = st.selectbox("Select Branch to Update", branch_names, key="update_branch_select")
        
        if selected_branch:
            row = df[df["branch_name"] == selected_branch].iloc[0]
            
            with st.form("update_branch_form", clear_on_submit=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.text_input("Branch Code", value=row["branch_id"], disabled=True, help="Branch code cannot be changed")
                    update_branch_name = st.text_input("Branch Name", value=row["branch_name"])
                    update_location = st.text_input("Location", value=row["location"])
                
                with col2:
                    update_level = st.selectbox("Level", [1, 2, 3, 4, 5, 6], 
                                               index=int(row["level"]) - 1 if int(row["level"]) <= 6 else 0)
                    update_active = st.checkbox("Active", value=bool(row["active"]))
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                        idx = row.name
                        df.at[idx, "branch_name"] = update_branch_name
                        df.at[idx, "location"] = update_location
                        df.at[idx, "level"] = update_level
                        df.at[idx, "active"] = update_active
                        
                        save_branches(df)
                        st.success(f"✅ Branch '{update_branch_name}' updated successfully!")
                        st.rerun()
                
                with col_btn2:
                    if st.form_submit_button("🗑️ Delete Branch", use_container_width=True):
                        st.warning("⚠️ Check the box below to confirm deletion")
                        confirm = st.checkbox("I understand this action CANNOT be undone")
                        if confirm:
                            if len(df) <= 1:
                                st.error("❌ At least one branch must remain in the system.")
                            else:
                                df = df[df["branch_name"] != selected_branch]
                                save_branches(df)
                                st.success(f"✅ Branch '{selected_branch}' deleted successfully!")
                                st.rerun()
    else:
        st.info("No branches available to update. Add a branch first.")
    
    st.markdown("---")
    
    # ==============================
    # QUICK DELETE SECTION (Alternative)
    # ==============================
    st.subheader("🗑️ Quick Delete Branch")
    
    if not df.empty and len(df) > 1:
        delete_branch_name = st.selectbox("Select Branch to Delete", df["branch_name"].tolist(), key="delete_branch_select")
        
        if delete_branch_name:
            branch_to_delete = df[df["branch_name"] == delete_branch_name].iloc[0]
            st.warning(f"You are about to delete: **{delete_branch_name}** ({branch_to_delete['branch_id']})")
            
            if st.button("🗑️ Confirm Delete", use_container_width=True):
                confirm = st.checkbox("✅ I confirm I want to delete this branch")
                if confirm:
                    df = df[df["branch_name"] != delete_branch_name]
                    save_branches(df)
                    st.success(f"✅ Branch '{delete_branch_name}' deleted successfully!")
                    st.rerun()
    elif not df.empty and len(df) == 1:
        st.info("Cannot delete the only remaining branch. Add another branch first.")
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()