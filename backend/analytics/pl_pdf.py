# backend/analytics/pl_pdf.py
# Profit & Loss PDF generator.
# Branch-aware: header and footer show the branch label when available.

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.core.db_adapter import load_branches


# ==============================
# DEFAULT COMPANY HEADER
# ==============================
_DEFAULT_COMPANY = "AZIEL INVESTMENTS"
_DEFAULT_ADDRESS = "Retreat Park, Harare"
_DEFAULT_PHONE = "0782 905 853"
_DEFAULT_EMAIL = "info@azielinvestments.co.zw"


# ==============================
# SESSION BRANCH HELPERS
# ==============================
def _get_session_branch():
    """
    Return the authoritative branch for the current session.
    Prefers `current_branch_code` over `user_branch`.
    """
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        # st may not be available if the PDF is generated outside a Streamlit run
        return "HO"


def _branch_label(branch_id):
    """Human-readable branch label: 'Name (CODE)' when available."""
    if not branch_id:
        return "HO"
    try:
        df = load_branches()
        if df is not None and not df.empty and "branch_id" in df.columns:
            match = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                name = match.iloc[0].get("branch_name", "")
                if name:
                    return f"{name} ({branch_id})"
    except Exception:
        pass
    return str(branch_id)


def _resolve_branch_header(branch_id=None):
    """
    Return (company, address, phone, email) for the PDF header/footer.
    Falls back to the Aziel defaults when the branches table doesn't
    expose those columns.
    """
    if branch_id is None:
        branch_id = _get_session_branch()

    company = _DEFAULT_COMPANY
    address = _DEFAULT_ADDRESS
    phone = _DEFAULT_PHONE
    email = _DEFAULT_EMAIL

    try:
        df = load_branches()
        if df is not None and not df.empty and "branch_id" in df.columns:
            match = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                if "branch_name" in row and row["branch_name"]:
                    company = f"{_DEFAULT_COMPANY} - {row['branch_name']}"
                if "address" in row and row["address"]:
                    address = str(row["address"])
                if "phone" in row and row["phone"]:
                    phone = str(row["phone"])
                if "email" in row and row["email"]:
                    email = str(row["email"])
    except Exception:
        pass

    return company, address, phone, email


# ==============================
# PDF GENERATOR
# ==============================
def generate_pl_pdf(pl_data, year=None, month=None, branch_id=None):
    """
    Generate a Profit & Loss PDF from a `profit_loss_account()` dict.

    Parameters
    ----------
    pl_data : dict
        The dict returned by `profit_loss_account(...)`.
    year : int, optional
        Year label for the header.
    month : int, optional
        Month label for the header (1-12).
    branch_id : str, optional
        Branch to scope the PDF header/footer to. Defaults to the session branch.

    Returns
    -------
    bytes
        PDF file contents.
    """
    if not isinstance(pl_data, dict):
        pl_data = {}

    company, address, phone, email = _resolve_branch_header(branch_id)
    branch_label = _branch_label(branch_id if branch_id is not None else _get_session_branch())

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    y = 750

    # =========================
    # HEADER
    # =========================
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(150, y, "PROFIT & LOSS STATEMENT")
    y -= 18

    pdf.setFont("Helvetica", 10)
    pdf.drawString(150, y, company)
    y -= 14

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(150, y, f"Branch: {branch_label}")
    y -= 22

    pdf.setFont("Helvetica", 10)
    period_bits = []
    if year:
        period_bits.append(str(year))
    if month:
        try:
            period_bits.append(f"{int(month):02d}")
        except Exception:
            period_bits.append(str(month))
    period_label = "-".join(period_bits) if period_bits else "All periods"

    pdf.drawString(50, y, f"Period: {period_label}")
    y -= 14
    pdf.drawString(50, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 25

    # =========================
    # SUMMARY TABLE
    # =========================
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "SUMMARY")
    y -= 18

    pdf.setFont("Helvetica", 10)

    rows = [
        ("Gross Profit", pl_data.get("gross_profit", 0)),
        ("Other Income", pl_data.get("other_income", 0)),
        ("Operating Expenses", pl_data.get("operating_expenses", 0)),
        ("Net Profit Before Tax", pl_data.get("net_profit_before_tax", 0)),
        ("Tax", pl_data.get("tax", 0)),
        ("Net Profit", pl_data.get("net_profit", 0)),
        ("Net Margin (%)", pl_data.get("net_margin", 0)),
    ]

    for label, value in rows:
        try:
            if "margin" in label.lower():
                line = f"{label}: {float(value):.2f}%"
            else:
                line = f"{label}: ${float(value):,.2f}"
        except (TypeError, ValueError):
            line = f"{label}: {value}"

        # Page break guard
        if y < 80:
            pdf.showPage()
            y = 750
            pdf.setFont("Helvetica", 10)

        pdf.drawString(50, y, line)
        y -= 15

    # =========================
    # FOOTER
    # =========================
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(50, 60, company)
    pdf.drawString(50, 48, f"Address: {address}")
    pdf.drawString(50, 36, f"Contact: {phone} | Email: {email}")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()