import streamlit as st
from datetime import datetime

def get_system_manual():
    """Return the complete system manual as a string"""
    
    manual = f"""
{'='*70}
                    AZIEL INVESTMENTS - SMARTGRO ERP SYSTEM
                    COMPLETE USER MANUAL
{'='*70}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                        SYSTEM OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SmartGro is a comprehensive Enterprise Resource Planning (ERP) system designed 
specifically for retail businesses in Zimbabwe. The system provides complete 
management of sales, inventory, customers, debtors, expenses, and multi-branch 
operations.

┌─────────────────────────────────────────────────────────────────────────────┐
│  DEVELOPER INFORMATION                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Founder & Lead Developer:  King T Chingaona , Walker Takaendesa                               │
│  System Name:               SmartGro ERP System                              │
│  Version:                   3.0 (Zimbabwe Edition)                           │
│  Release Date:              June 2024                                        │
│  Target Market:             Zimbabwe Retail Businesses                       │
└─────────────────────────────────────────────────────────────────────────────┘

Key Features:
• Multi-branch support (Head Office, National, Provincial, District, Village)
• Role-based access control (Owner, Manager, Cashier)
• Point of Sale (POS) with receipt printing
• Inventory management with stock alerts
• Customer database and loyalty points
• Debtors management with credit scoring
• Expense and income tracking
• Profit & Loss reporting
• Business intelligence and AI advisor
• Multi-currency support (ZWL, USD, ZiG, RAND)
• WhatsApp integration for receipts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    SYSTEM REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hardware Requirements:
• Processor: Intel Core i3 or equivalent
• RAM: 4GB minimum (8GB recommended)
• Storage: 500MB free space
• Internet: Required for initial setup (offline capable after)
• Barcode Scanner: USB compatible (optional)
• Printer: Any printer for receipts

Software Requirements:
• Operating System: Windows 10/11, macOS, or Linux
• Python 3.8 or higher
• Web Browser: Chrome, Firefox, or Edge

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    INSTALLATION GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Install Python
• Download Python from python.org (version 3.8 or higher)
• During installation, check "Add Python to PATH"
• Verify installation: Open Command Prompt and type "python --version"

Step 2: Install Required Libraries
Open Command Prompt/Terminal and run:

    pip install streamlit pandas numpy plotly scikit-learn reportlab

Step 3: Download SmartGro System
• Download the SmartGro_System folder to your computer
• Ensure all files are in the correct directory structure

Step 4: Run the System
Navigate to the SmartGro_System folder and run:

    streamlit run app.py

Step 5: Access the System
• Open your web browser
• Go to: http://localhost:8501
• Login using the provided credentials

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    LOGIN & ACCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Branch Selection:
┌─────────┬─────────────────────┬──────────┬───────────────┐
│ Branch  │ Code                │ Password │ Level         │
├─────────┼─────────────────────┼──────────┼───────────────┤
│ Head Office    │ HO               │ ho123    │ 1             │
│ National       │ NAT              │ nat123   │ 2             │
│ Provincial     │ PRO              │ pro123   │ 3             │
│ District       │ DIS              │ dis123   │ 4             │
│ Village        │ VIL              │ vil123   │ 5             │
└─────────┴─────────────────────┴──────────┴───────────────┘

User Login Credentials:
┌─────────────┬──────────────┬─────────────────────────────────┐
│ Username    │ Password     │ Role                            │
├─────────────┼──────────────┼─────────────────────────────────┤
│ admin       │ admin123     │ Owner (Full System Access)      │
│ manager     │ manager123   │ Manager (Operations Access)     │
│ cashier     │ cash123      │ Cashier (POS Only)              │
└─────────────┴──────────────┴─────────────────────────────────┘

Login Process:
1. Select your branch from the branch selection screen
2. Enter the branch password
3. Enter your username and password
4. Click "Login" to access the system

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    USER ROLES & PERMISSIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────┬─────────────────────────────────────────────────────────────┐
│ Role        │ Permissions                                                   │
├─────────────┼─────────────────────────────────────────────────────────────┤
│ OWNER       │ Full system access:                                          │
│             │ • All modules                                                │
│             │ • User management                                            │
│             │ • Branch management                                          │
│             │ • System settings                                            │
│             │ • View all branch data                                       │
├─────────────┼─────────────────────────────────────────────────────────────┤
│ MANAGER     │ Operations access:                                           │
│             │ • Inventory management                                       │
│             │ • Sales reports                                              │
│             │ • Purchases                                                  │
│             │ • Expenses & Income                                          │
│             │ • Customer management                                        │
│             │ • Debtors management                                         │
│             │ • Shift management                                           │
│             │ • Branch performance (view only)                             │
├─────────────┼─────────────────────────────────────────────────────────────┤
│ CASHIER     │ Limited access:                                              │
│             │ • Point of Sale (POS)                                        │
│             │ • View inventory                                             │
│             │ • View sales history                                         │
│             │ • Create customers                                           │
│             │ • Process returns                                            │
└─────────────┴─────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    MODULE GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. STOCK DASHBOARD
Purpose: View inventory overview and stock health
Features:
• Total products, stock units, and inventory value
• Stock health gauge (0-100%)
• Low stock alerts and reorder suggestions
• Stock distribution by category charts
• Export inventory reports

2. INVENTORY
Purpose: Manage all products in the system
Features:
• Add new products (barcode, name, price, cost, stock)
• Edit existing product details
• Delete products
• Search products by name or barcode
• Stock level alerts
• Bulk import/export

3. POINT OF SALE (POS)
Purpose: Process customer sales
Features:
• Search products by name or barcode
• Add items to cart
• Apply discounts (percentage or fixed)
• Apply tax
• Multiple payment methods (Cash, EcoCash, Card, Credit)
• Print receipts (PDF or physical)
• Customer loyalty points
• Save cart for later
• Reprint last receipt

4. SALES HISTORY
Purpose: View all completed sales
Features:
• Filter by date range
• Search by receipt number
• View transaction details
• Re-print receipts
• Export sales data

5. SALES DASHBOARD
Purpose: Analyze sales performance
Features:
• Total revenue and profit
• Top selling products
• Daily/weekly/monthly trends
• Payment method distribution
• Best customers report
• Profit margin analysis

6. CASH DASHBOARD
Purpose: Manage cash register and shifts
Features:
• Start/end cashier shifts
• Track cash sales
• Record expenses
• Cash reconciliation
• Variance reporting
• Petty cash management

7. PURCHASES
Purpose: Manage supplier purchases
Features:
• Create purchase orders
• Receive stock against POs
• Track supplier performance
• Purchase history
• Expected profit calculation

8. EXPENSES
Purpose: Track business expenses
Features:
• Record expenses by category
• Set budgets
• Budget vs actual analysis
• Expense trends
• Vendor tracking

9. INCOME
Purpose: Track non-sales income
Features:
• Record other income sources
• Income by category
• Monthly income trends

10. P&L DASHBOARD
Purpose: Profit & Loss reporting
Features:
• Trading account
• Profit & loss statement
• Key financial ratios
• Break-even analysis
• Year-over-year comparison

11. CUSTOMERS
Purpose: Manage customer database
Features:
• Customer profiles
• Purchase history
• Customer segmentation
• Retention analytics
• Lifetime value calculation

12. DEBTORS
Purpose: Manage customer credit
Features:
• Create debt records
• Record debt payments
• Credit scoring system
• Overdue debtors alerts
• Aging reports
• Payment reminders

13. BUSINESS ADVISOR
Purpose: AI-powered business insights
Features:
• Business health score
• Sales forecasting
• Anomaly detection
• Intelligent recommendations
• Seasonal trend analysis

14. REPORTS
Purpose: Generate business reports
Features:
• Sales reports (PDF/CSV)
• Inventory reports
• Financial reports
• Debtors reports
• Export all data

15. BRANCH MANAGEMENT
Purpose: Manage multi-branch operations
Features:
• Add new branches
• Edit branch details
• Delete branches
• Branch performance comparison

16. SHIFT MANAGEMENT
Purpose: Manage cashier shifts
Features:
• Start shift for cashier
• End shift with reconciliation
• Shift history
• Cashier performance

17. USER MANAGEMENT
Purpose: Manage system users
Features:
• Add new users
• Assign roles
• Reset passwords
• Activate/deactivate users

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    QUICK START GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For Cashiers:
1. Manager must start a shift for you
2. Login with your cashier credentials
3. Go to POS module
4. Search/add products to cart
5. Process payment
6. Print receipt

For Managers:
1. Login with manager credentials
2. Start shifts for cashiers
3. Monitor inventory levels
4. Review sales reports
5. Manage customers and debtors
6. Process purchases and expenses

For Owners:
1. Login with admin credentials
2. Manage users and branches
3. View all business reports
4. Analyze P&L statements
5. Review business advisor insights
6. Export all data for accounting

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: Cannot login
Solution: 
• Verify branch selection is correct
• Check username and password
• Ensure branch is active
• Contact system administrator

Issue: Products not saving
Solution:
• Refresh the page
• Check file permissions
• Clear browser cache
• Restart the application

Issue: Receipt not printing
Solution:
• Check printer connection
• Use PDF download as alternative
• Try printing from browser
• Check receipt paper

Issue: Branch data not showing
Solution:
• Verify you are logged into correct branch
• Check branch data files exist
• Refresh the page
• Contact support

Issue: Slow performance
Solution:
• Clear old data (Sales History)
• Reduce date range in reports
• Restart the application
• Check available disk space

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    SUPPORT & CONTACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Developer:          King T Chingaona, Walker Takaendesa
System Name:        SmartGro ERP System
Version:            3.0 (Zimbabwe Edition)
Email Support:      aziel@investments.co.zw
Phone Support:      +263 78 290 5853
Website:            www.azielinvestments.co.zw

Office Address:
Aziel Investments
Retreat Park, Harare
Zimbabwe

Support Hours:
Monday - Friday: 8:00 AM - 5:00 PM
Saturday: 9:00 AM - 1:00 PM
Sunday: Closed

Emergency Support: +263 78 290 5853

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    LICENSE & COPYRIGHT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SmartGro ERP System
Copyright © 2024 Aziel Investments

All rights reserved. This software is proprietary and confidential.
Unauthorized copying, distribution, or modification is strictly prohibited.

This software is licensed for use by Aziel Investments and its authorized
branches only. The software may not be resold, sublicensed, or used for
commercial purposes without explicit written permission.

For licensing inquiries, please contact:
aziel@investments.co.zw

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ACKNOWLEDGMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Special thanks to:
• The entire Aziel Investments team
• Beta testers who provided valuable feedback
• All branch managers and cashiers for their input
• The Zimbabwe business community for inspiration

Technology Stack:
• Streamlit - Web Framework
• Pandas - Data Management
• Plotly - Data Visualization
• Scikit-learn - Machine Learning
• ReportLab - PDF Generation

This manual was last updated on: {datetime.now().strftime('%B %d, %Y')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    END OF MANUAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SmartGro ERP System - Empowering Zimbabwean Retail Businesses
Developed with ❤️ by King T Chingaona & Walker Takaendesa 

{'='*70}
"""
    
    return manual


def display_manual_page():
    """Display the manual in the app"""
    
    st.title("📖 SmartGro System User Manual")
    st.caption("Complete documentation for the SmartGro ERP System")
    
    st.info("""
    📚 **User Manual**
    
    This comprehensive manual covers all aspects of the SmartGro ERP System.
    You can read it online or download a PDF version for offline use.
    """)
    
    # Display manual content in an expander
    with st.expander("📖 Read Full Manual Online", expanded=False):
        manual_text = get_system_manual()
        st.text_area("System Manual", manual_text, height=600, key="manual_display")
    
    st.markdown("---")
    
    # Download section
    st.subheader("📥 Download Manual")
    st.write("Click the button below to download the complete user manual.")
    
    manual_text = get_system_manual()
    
    # Create downloadable file
    st.download_button(
        label="📄 Download User Manual (TXT)",
        data=manual_text,
        file_name=f"SmartGro_User_Manual_{datetime.now().strftime('%Y%m%d')}.txt",
        mime="text/plain",
        use_container_width=True
    )
    
    # PDF download option (using reportlab if available)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from io import BytesIO
        
        def create_pdf_manual():
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16)
            
            story = []
            
            # Title
            story.append(Paragraph("AZIEL INVESTMENTS - SMARTGRO ERP SYSTEM", title_style))
            story.append(Paragraph("Complete User Manual", styles['Heading2']))
            story.append(Spacer(1, 20))
            
            # Convert manual text to paragraphs (simplified)
            lines = manual_text.split('\n')
            for line in lines[:500]:  # Limit for PDF
                if line.strip():
                    if line.startswith('━') or line.startswith('┌') or line.startswith('└'):
                        continue
                    story.append(Paragraph(line.replace(' ', '&nbsp;'), styles['Normal']))
                    story.append(Spacer(1, 6))
            
            doc.build(story)
            buffer.seek(0)
            return buffer
        
        pdf_buffer = create_pdf_manual()
        st.download_button(
            label="📕 Download User Manual (PDF)",
            data=pdf_buffer,
            file_name=f"SmartGro_User_Manual_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except:
        st.info("PDF generation requires reportlab. Install with: pip install reportlab")