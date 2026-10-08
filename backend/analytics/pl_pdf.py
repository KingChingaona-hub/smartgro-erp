from backend.analytics.pl_engine import profit_loss_account
from backend.analytics.pl_pdf import generate_pl_pdf
from backend.core.db_adapter import load_branches
import streamlit as st

# Determine scope
role = st.session_state.get("role", "cashier")
branch_id = st.session_state.get("user_branch") or st.session_state.get("current_branch_code") or "HO"

# Owner can run company-wide — gate on the same selector your reports dashboard uses
if role in ("owner", "admin"):
    branches_df = load_branches()
    opts = ["All Branches"] + [
        f"{r['branch_name']} ({r['branch_id']})"
        for _, r in branches_df.iterrows()
    ]
    choice = st.selectbox("Branch scope", opts, key="pl_pdf_branch_scope")
    if choice == "All Branches":
        from backend.analytics.reports_engine import ALL_BRANCHES
        branch_id = ALL_BRANCHES
        branch_label = "All Branches"
    else:
        import re
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        branch_id = m.group(1).strip() if m else branch_id
        branch_label = choice
else:
    branch_label = branch_id
    try:
        bdf = load_branches()
        match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
        if not match.empty:
            row = match.iloc[0]
            branch_label = f"{row['branch_name']} ({row['branch_id']})"
    except Exception:
        pass

# Build the P&L for the correct scope
report = profit_loss_account(branch_id=branch_id, year=year, month=month)

# Build the PDF with a readable branch label
pdf_buffer = generate_pl_pdf(report, year, month, branch_name=branch_label)

st.download_button(
    label="Download Trading & P/L (PDF)",
    data=pdf_buffer.getvalue(),
    file_name=f"trading_pl_{branch_id}_{year}"
              + (f"_{month:02d}" if month else "")
              + ".pdf",
    mime="application/pdf",
)