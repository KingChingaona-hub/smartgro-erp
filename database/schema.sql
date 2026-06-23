-- ============================================================
-- SMARTGRO ERP SYSTEM - COMPLETE POSTGRESQL DATABASE SCHEMA
-- Version: 3.0 (Zimbabwe Edition)
-- ============================================================

-- ============================================================
-- 1. BRANCHES
-- ============================================================
CREATE TABLE IF NOT EXISTS branches (
    branch_id VARCHAR(10) PRIMARY KEY,
    branch_name VARCHAR(100) NOT NULL,
    location VARCHAR(255),
    level INTEGER DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE SET NULL,
    full_name VARCHAR(100),
    phone VARCHAR(20),
    active BOOLEAN DEFAULT TRUE,
    mobile_enabled BOOLEAN DEFAULT TRUE,
    whatsapp VARCHAR(20),
    receive_alerts BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    last_mobile_login TIMESTAMP,
    device_info TEXT,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    session_token VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 3. PRODUCTS
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    barcode VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2) DEFAULT 0,
    cost DECIMAL(10,2) DEFAULT 0,
    stock INTEGER DEFAULT 0,
    reorder_level INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, barcode)
);

CREATE INDEX idx_products_barcode ON products(barcode);
CREATE INDEX idx_products_branch ON products(branch_id);
CREATE INDEX idx_products_name ON products(name);

-- ============================================================
-- 4. SALES
-- ============================================================
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    receipt_no VARCHAR(50) NOT NULL,
    barcode VARCHAR(50),
    product_name VARCHAR(200),
    items INTEGER DEFAULT 0,
    total DECIMAL(10,2) DEFAULT 0,
    profit DECIMAL(10,2) DEFAULT 0,
    payment_method VARCHAR(50),
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    final_total DECIMAL(10,2) DEFAULT 0,
    shift_id VARCHAR(50),
    cashier VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sales_receipt ON sales(receipt_no);
CREATE INDEX idx_sales_date ON sales(sale_date);
CREATE INDEX idx_sales_branch ON sales(branch_id);
CREATE INDEX idx_sales_customer ON sales(customer_phone);

-- ============================================================
-- 5. CUSTOMERS
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    customer_id VARCHAR(20) UNIQUE NOT NULL,
    customer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    total_orders INTEGER DEFAULT 0,
    total_spent DECIMAL(10,2) DEFAULT 0,
    last_purchase_date TIMESTAMP,
    favorite_product VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, phone)
);

CREATE INDEX idx_customers_phone ON customers(phone);
CREATE INDEX idx_customers_name ON customers(customer_name);

-- ============================================================
-- 6. CUSTOMER TRANSACTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS customer_transactions (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(100),
    phone VARCHAR(20),
    receipt_no VARCHAR(50),
    barcode VARCHAR(50),
    product_name VARCHAR(200),
    quantity INTEGER DEFAULT 0,
    amount DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_trans_phone ON customer_transactions(phone);
CREATE INDEX idx_customer_trans_receipt ON customer_transactions(receipt_no);

-- ============================================================
-- 7. DEBTORS
-- ============================================================
CREATE TABLE IF NOT EXISTS debtors (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    debt_id VARCHAR(50) UNIQUE NOT NULL,
    date_borrowed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    total_amount DECIMAL(10,2) DEFAULT 0,
    amount_paid DECIMAL(10,2) DEFAULT 0,
    balance DECIMAL(10,2) DEFAULT 0,
    credit_limit DECIMAL(10,2) DEFAULT 0,
    expected_repayment_date DATE,
    repayment_date DATE,
    status VARCHAR(50) DEFAULT 'NOT PAID',
    risk_level VARCHAR(20) DEFAULT 'LOW',
    payment_plan VARCHAR(50),
    installment_amount DECIMAL(10,2) DEFAULT 0,
    installment_frequency VARCHAR(20),
    next_payment_date DATE,
    provision_bad_debt DECIMAL(10,2) DEFAULT 0,
    bad_debt DECIMAL(10,2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_debtors_phone ON debtors(phone);
CREATE INDEX idx_debtors_status ON debtors(status);
CREATE INDEX idx_debtors_branch ON debtors(branch_id);

-- ============================================================
-- 8. DEBTOR PAYMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS debtor_payments (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    debt_id VARCHAR(50) REFERENCES debtors(debt_id) ON DELETE CASCADE,
    customer_name VARCHAR(100),
    amount_paid DECIMAL(10,2) DEFAULT 0,
    balance_after DECIMAL(10,2) DEFAULT 0,
    receipt_no VARCHAR(50),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_debtor_payments_debt ON debtor_payments(debt_id);

-- ============================================================
-- 9. DEBTOR ITEMS
-- ============================================================
CREATE TABLE IF NOT EXISTS debtor_items (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    debt_id VARCHAR(50) REFERENCES debtors(debt_id) ON DELETE CASCADE,
    customer_name VARCHAR(100),
    barcode VARCHAR(50),
    product_name VARCHAR(200),
    quantity INTEGER DEFAULT 0,
    unit_price DECIMAL(10,2) DEFAULT 0,
    total_price DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 10. LOYALTY POINTS
-- ============================================================
CREATE TABLE IF NOT EXISTS loyalty_points (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    customer_name VARCHAR(100),
    phone VARCHAR(20) UNIQUE NOT NULL,
    points INTEGER DEFAULT 0,
    tier VARCHAR(50) DEFAULT '🥉 BRONZE',
    total_spent DECIMAL(10,2) DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    last_visit DATE,
    birthday DATE,
    joined_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_loyalty_phone ON loyalty_points(phone);

-- ============================================================
-- 11. LOYALTY REDEMPTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS loyalty_redemptions (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    redemption_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(100),
    points_used INTEGER DEFAULT 0,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    receipt_no VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 12. PURCHASES (Purchase Orders)
-- ============================================================
CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    date_ordered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    supplier VARCHAR(100),
    product_name VARCHAR(200),
    barcode VARCHAR(50),
    quantity_ordered INTEGER DEFAULT 0,
    quantity_received INTEGER DEFAULT 0,
    cost_price DECIMAL(10,2) DEFAULT 0,
    total_cost DECIMAL(10,2) DEFAULT 0,
    expected_date DATE,
    date_received DATE,
    status VARCHAR(50) DEFAULT 'PENDING',
    payment_status VARCHAR(50) DEFAULT 'UNPAID',
    invoice_no VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_purchases_po ON purchases(po_number);
CREATE INDEX idx_purchases_supplier ON purchases(supplier);
CREATE INDEX idx_purchases_branch ON purchases(branch_id);

-- ============================================================
-- 13. EXPENSES
-- ============================================================
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    expense_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expense_type VARCHAR(50),
    category VARCHAR(100),
    description TEXT,
    amount DECIMAL(10,2) DEFAULT 0,
    vendor VARCHAR(100),
    payment_method VARCHAR(50),
    recorded_by VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_expenses_category ON expenses(category);
CREATE INDEX idx_expenses_date ON expenses(expense_date);
CREATE INDEX idx_expenses_branch ON expenses(branch_id);

-- ============================================================
-- 14. INCOME
-- ============================================================
CREATE TABLE IF NOT EXISTS income (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    income_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    income_source VARCHAR(100),
    description TEXT,
    amount DECIMAL(10,2) DEFAULT 0,
    recorded_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_income_date ON income(income_date);
CREATE INDEX idx_income_branch ON income(branch_id);

-- ============================================================
-- 15. CASH REGISTER
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_register (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    cash_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shift_id VARCHAR(50),
    type VARCHAR(50),
    amount DECIMAL(10,2) DEFAULT 0,
    receipt_no VARCHAR(50),
    customer_name VARCHAR(100),
    payment_method VARCHAR(50),
    note TEXT,
    cashier VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cash_shift ON cash_register(shift_id);
CREATE INDEX idx_cash_branch ON cash_register(branch_id);

-- ============================================================
-- 16. SHIFTS
-- ============================================================
CREATE TABLE IF NOT EXISTS shifts (
    id SERIAL PRIMARY KEY,
    shift_id VARCHAR(50) UNIQUE NOT NULL,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    branch_name VARCHAR(100),
    cashier_username VARCHAR(50),
    cashier_name VARCHAR(100),
    manager_username VARCHAR(50),
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    opening_cash DECIMAL(10,2) DEFAULT 0,
    closing_cash DECIMAL(10,2) DEFAULT 0,
    cash_sales DECIMAL(10,2) DEFAULT 0,
    credit_sales DECIMAL(10,2) DEFAULT 0,
    debt_payments DECIMAL(10,2) DEFAULT 0,
    expenses DECIMAL(10,2) DEFAULT 0,
    total_revenue DECIMAL(10,2) DEFAULT 0,
    profit DECIMAL(10,2) DEFAULT 0,
    transactions INTEGER DEFAULT 0,
    variance DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'OPEN',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shifts_cashier ON shifts(cashier_username);
CREATE INDEX idx_shifts_status ON shifts(status);
CREATE INDEX idx_shifts_branch ON shifts(branch_id);

-- ============================================================
-- 17. EXPENSE BUDGET
-- ============================================================
CREATE TABLE IF NOT EXISTS expense_budget (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    category VARCHAR(100) NOT NULL,
    budget_amount DECIMAL(10,2) DEFAULT 0,
    actual_amount DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, year, month, category)
);

-- ============================================================
-- 18. RECURRING EXPENSES
-- ============================================================
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    recurring_id VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(100),
    amount DECIMAL(10,2) DEFAULT 0,
    frequency VARCHAR(20),
    day_of_month INTEGER DEFAULT 1,
    vendor VARCHAR(100),
    payment_method VARCHAR(50),
    start_date DATE,
    end_date DATE,
    active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 19. SUPPLIERS
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    supplier_id VARCHAR(20) UNIQUE NOT NULL,
    supplier_name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    address TEXT,
    payment_terms VARCHAR(50),
    lead_time_days INTEGER DEFAULT 7,
    rating DECIMAL(3,1) DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 20. SUPPLIER BIDS
-- ============================================================
CREATE TABLE IF NOT EXISTS supplier_bids (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    bid_id VARCHAR(50) UNIQUE NOT NULL,
    po_number VARCHAR(50) REFERENCES purchases(po_number) ON DELETE CASCADE,
    supplier_id VARCHAR(20) REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    supplier_name VARCHAR(100),
    bid_amount DECIMAL(10,2) DEFAULT 0,
    original_amount DECIMAL(10,2) DEFAULT 0,
    bid_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_days INTEGER DEFAULT 7,
    warranty_months INTEGER DEFAULT 12,
    payment_terms VARCHAR(50),
    status VARCHAR(50) DEFAULT 'PENDING',
    notes TEXT,
    evaluated_by VARCHAR(50),
    evaluated_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 21. RETURNS
-- ============================================================
CREATE TABLE IF NOT EXISTS returns (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    return_id VARCHAR(50) UNIQUE NOT NULL,
    receipt_no VARCHAR(50),
    sale_id VARCHAR(50),
    return_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    product_barcode VARCHAR(50),
    product_name VARCHAR(200),
    quantity_returned INTEGER DEFAULT 0,
    refund_amount DECIMAL(10,2) DEFAULT 0,
    return_reason VARCHAR(100),
    condition VARCHAR(50),
    status VARCHAR(50) DEFAULT 'PENDING',
    refund_method VARCHAR(50),
    store_credit_id VARCHAR(50),
    processed_by VARCHAR(50),
    processed_date TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_returns_receipt ON returns(receipt_no);
CREATE INDEX idx_returns_customer ON returns(customer_phone);
CREATE INDEX idx_returns_branch ON returns(branch_id);

-- ============================================================
-- 22. REFUNDS
-- ============================================================
CREATE TABLE IF NOT EXISTS refunds (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    refund_id VARCHAR(50) UNIQUE NOT NULL,
    return_id VARCHAR(50),
    receipt_no VARCHAR(50),
    refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(100),
    amount DECIMAL(10,2) DEFAULT 0,
    refund_method VARCHAR(50),
    reference_no VARCHAR(50),
    processed_by VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 23. STORE CREDIT
-- ============================================================
CREATE TABLE IF NOT EXISTS store_credit (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    credit_id VARCHAR(50) UNIQUE NOT NULL,
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    amount DECIMAL(10,2) DEFAULT 0,
    remaining_balance DECIMAL(10,2) DEFAULT 0,
    issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date DATE,
    status VARCHAR(50) DEFAULT 'ACTIVE',
    issued_by VARCHAR(50),
    used_transactions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_store_credit_phone ON store_credit(customer_phone);
CREATE INDEX idx_store_credit_branch ON store_credit(branch_id);

-- ============================================================
-- 24. WARRANTY REGISTRATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS warranty_registrations (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    warranty_id VARCHAR(50) UNIQUE NOT NULL,
    receipt_no VARCHAR(50),
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    product_barcode VARCHAR(50),
    product_name VARCHAR(200),
    purchase_date DATE,
    warranty_months INTEGER DEFAULT 12,
    expiry_date DATE,
    status VARCHAR(50) DEFAULT 'ACTIVE',
    claimed_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 25. AUDIT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    username VARCHAR(50),
    action VARCHAR(100),
    details TEXT,
    ip_address VARCHAR(45),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_log(username);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_date ON audit_log(timestamp);

-- ============================================================
-- 26. TWO-FACTOR AUTHENTICATION CODES
-- ============================================================
CREATE TABLE IF NOT EXISTS twofa_codes (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    username VARCHAR(50),
    code VARCHAR(10),
    expiry TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 27. ACTIVE SESSIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS active_sessions (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50),
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    device_info TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 28. PAYMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    payment_id VARCHAR(50) UNIQUE NOT NULL,
    receipt_no VARCHAR(50),
    amount DECIMAL(10,2) DEFAULT 0,
    payment_method VARCHAR(50),
    status VARCHAR(50) DEFAULT 'PENDING',
    reference VARCHAR(100),
    transaction_id VARCHAR(100),
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    processed_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 29. ECOCASH TRANSACTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS ecocash_transactions (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    transaction_id VARCHAR(50) UNIQUE NOT NULL,
    receipt_no VARCHAR(50),
    amount DECIMAL(10,2) DEFAULT 0,
    customer_phone VARCHAR(20),
    merchant_code VARCHAR(50),
    status VARCHAR(50) DEFAULT 'PENDING',
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP,
    reference VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 30. CARD TRANSACTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS card_transactions (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    transaction_id VARCHAR(50) UNIQUE NOT NULL,
    receipt_no VARCHAR(50),
    amount DECIMAL(10,2) DEFAULT 0,
    card_type VARCHAR(20),
    last_four VARCHAR(4),
    status VARCHAR(50) DEFAULT 'PENDING',
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auth_code VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 31. SMS LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS sms_logs (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    sms_id VARCHAR(50) UNIQUE NOT NULL,
    recipient VARCHAR(20),
    message TEXT,
    type VARCHAR(50),
    status VARCHAR(50),
    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_by VARCHAR(50),
    response TEXT,
    cost DECIMAL(10,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sms_recipient ON sms_logs(recipient);
CREATE INDEX idx_sms_date ON sms_logs(sent_date);

-- ============================================================
-- 32. APPROVALS (Workflow)
-- ============================================================
CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    approval_id VARCHAR(50) UNIQUE NOT NULL,
    type VARCHAR(50),
    reference VARCHAR(100),
    requested_by VARCHAR(50),
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    amount DECIMAL(10,2) DEFAULT 0,
    details TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    approved_by VARCHAR(50),
    approved_date TIMESTAMP,
    rejected_by VARCHAR(50),
    rejected_date TIMESTAMP,
    rejection_reason TEXT,
    level INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_approvals_branch ON approvals(branch_id);

-- ============================================================
-- 33. APPROVAL HISTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS approval_history (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    history_id VARCHAR(50) UNIQUE NOT NULL,
    approval_id VARCHAR(50) REFERENCES approvals(approval_id) ON DELETE CASCADE,
    action VARCHAR(50),
    performed_by VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comments TEXT,
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 34. REPLENISHMENT SETTINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS replenishment_settings (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    auto_replenish BOOLEAN DEFAULT TRUE,
    reorder_point_multiplier DECIMAL(3,1) DEFAULT 1.5,
    safety_stock_days INTEGER DEFAULT 7,
    lead_time_days INTEGER DEFAULT 3,
    max_order_quantity INTEGER DEFAULT 1000,
    min_order_quantity INTEGER DEFAULT 10,
    supplier_preference VARCHAR(50) DEFAULT 'best_price',
    auto_approve BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 35. AUTO PURCHASE ORDERS
-- ============================================================
CREATE TABLE IF NOT EXISTS auto_purchase_orders (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    supplier VARCHAR(100),
    product_name VARCHAR(200),
    product_barcode VARCHAR(50),
    quantity INTEGER DEFAULT 0,
    cost_price DECIMAL(10,2) DEFAULT 0,
    total_cost DECIMAL(10,2) DEFAULT 0,
    reorder_level INTEGER DEFAULT 0,
    current_stock INTEGER DEFAULT 0,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'PENDING_APPROVAL',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_date TIMESTAMP,
    approved_by VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 36. REPLENISHMENT LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS replenishment_logs (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    log_id VARCHAR(50) UNIQUE NOT NULL,
    log_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    product_name VARCHAR(200),
    barcode VARCHAR(50),
    current_stock INTEGER DEFAULT 0,
    reorder_level INTEGER DEFAULT 0,
    recommended_qty INTEGER DEFAULT 0,
    action VARCHAR(50),
    status VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 37. FOLLow-UP SETTINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS followup_settings (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    enabled BOOLEAN DEFAULT TRUE,
    thank_you_enabled BOOLEAN DEFAULT TRUE,
    thank_you_delay_hours INTEGER DEFAULT 2,
    review_enabled BOOLEAN DEFAULT TRUE,
    review_delay_days INTEGER DEFAULT 3,
    reengagement_enabled BOOLEAN DEFAULT TRUE,
    reengagement_inactive_days INTEGER DEFAULT 30,
    reengagement_discount INTEGER DEFAULT 10,
    birthday_enabled BOOLEAN DEFAULT TRUE,
    birthday_discount INTEGER DEFAULT 15,
    abandoned_cart_enabled BOOLEAN DEFAULT TRUE,
    abandoned_cart_delay_hours INTEGER DEFAULT 24,
    sms_enabled BOOLEAN DEFAULT TRUE,
    email_enabled BOOLEAN DEFAULT FALSE,
    whatsapp_enabled BOOLEAN DEFAULT TRUE,
    max_followups_per_day INTEGER DEFAULT 50,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 38. FOLLOW-UP LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS followup_logs (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    log_id VARCHAR(50) UNIQUE NOT NULL,
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    customer_email VARCHAR(100),
    followup_type VARCHAR(50),
    message TEXT,
    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50),
    response TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_followup_phone ON followup_logs(customer_phone);

-- ============================================================
-- 39. SYSTEM SETTINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(10) REFERENCES branches(branch_id) ON DELETE CASCADE,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    setting_group VARCHAR(50),
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default settings
INSERT INTO system_settings (setting_key, setting_value, setting_group, description) VALUES
('store_name', 'Aziel Investments', 'store', 'Business name'),
('store_phone', '+263 78 290 5853', 'store', 'Store phone number'),
('store_email', 'info@azielinvestments.co.zw', 'store', 'Store email address'),
('store_address', 'Retreat Park, Harare, Zimbabwe', 'store', 'Store physical address'),
('default_currency', 'ZWL', 'store', 'Default currency'),
('default_tax_rate', '15', 'store', 'Default tax rate percentage'),
('receipt_footer', 'Thank you for shopping with us!', 'store', 'Receipt footer message'),
('pwa_enabled', 'true', 'pwa', 'Enable Progressive Web App'),
('offline_mode', 'true', 'system', 'Enable offline mode'),
('session_timeout_minutes', '30', 'security', 'User session timeout in minutes');

-- ============================================================
-- 40. VIEWS FOR COMMON QUERIES
-- ============================================================

-- View: Today's Sales Summary
CREATE OR REPLACE VIEW v_today_sales AS
SELECT 
    branch_id,
    COUNT(DISTINCT receipt_no) as transactions,
    SUM(total) as total_sales,
    SUM(profit) as total_profit,
    SUM(items) as items_sold
FROM sales
WHERE DATE(sale_date) = CURRENT_DATE
GROUP BY branch_id;

-- View: Low Stock Products
CREATE OR REPLACE VIEW v_low_stock AS
SELECT 
    branch_id,
    id,
    barcode,
    name,
    stock,
    reorder_level,
    (reorder_level - stock) as units_to_order
FROM products
WHERE stock <= reorder_level
ORDER BY (stock / reorder_level) ASC;

-- View: Customer Lifetime Value
CREATE OR REPLACE VIEW v_customer_lifetime_value AS
SELECT 
    customer_name,
    phone,
    total_orders,
    total_spent,
    CASE 
        WHEN total_orders > 0 THEN total_spent / total_orders 
        ELSE 0 
    END as avg_order_value,
    ROUND(total_spent * total_orders * 0.1, 2) as clv_score
FROM customers;

-- View: Monthly Sales
CREATE OR REPLACE VIEW v_monthly_sales AS
SELECT 
    branch_id,
    DATE_TRUNC('month', sale_date) as month,
    SUM(total) as total_sales,
    SUM(profit) as total_profit,
    COUNT(DISTINCT receipt_no) as transactions
FROM sales
GROUP BY branch_id, DATE_TRUNC('month', sale_date)
ORDER BY month DESC;

-- View: Debtor Aging
CREATE OR REPLACE VIEW v_debtor_aging AS
SELECT 
    branch_id,
    customer_name,
    phone,
    balance,
    expected_repayment_date,
    CASE 
        WHEN balance <= 0 THEN 'Paid'
        WHEN expected_repayment_date >= CURRENT_DATE THEN 'Current'
        WHEN expected_repayment_date >= (CURRENT_DATE - INTERVAL '30 days') THEN '1-30 Days Overdue'
        WHEN expected_repayment_date >= (CURRENT_DATE - INTERVAL '60 days') THEN '31-60 Days Overdue'
        WHEN expected_repayment_date >= (CURRENT_DATE - INTERVAL '90 days') THEN '61-90 Days Overdue'
        ELSE '90+ Days (Critical)'
    END as aging_bucket
FROM debtors;

-- ============================================================
-- 41. TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================

-- Trigger: Update updated_at on update
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN 
        SELECT table_name 
        FROM information_schema.columns 
        WHERE column_name = 'updated_at'
    LOOP
        EXECUTE format('
            CREATE TRIGGER trigger_update_%I 
            BEFORE UPDATE ON %I 
            FOR EACH ROW 
            EXECUTE FUNCTION update_updated_at()
        ', t, t);
    END LOOP;
END;
$$;

-- ============================================================
-- 42. INDEX PERFORMANCE OPTIMIZATION
-- ============================================================

-- Additional indexes for common queries
CREATE INDEX idx_sales_branch_date ON sales(branch_id, sale_date);
CREATE INDEX idx_debtors_branch_status ON debtors(branch_id, status);
CREATE INDEX idx_purchases_branch_status ON purchases(branch_id, status);
CREATE INDEX idx_cash_register_branch_date ON cash_register(branch_id, cash_date);
CREATE INDEX idx_customers_branch_name ON customers(branch_id, customer_name);
CREATE INDEX idx_expenses_branch_date ON expenses(branch_id, expense_date);

-- ============================================================
-- 43. INITIAL DATA - DEFAULT BRANCHES
-- ============================================================

INSERT INTO branches (branch_id, branch_name, location, level, active) VALUES
('HO', 'Head Office', 'Harare', 1, TRUE),
('NAT', 'National Branch', 'Harare', 2, TRUE),
('PRO', 'Provincial Branch', 'Bulawayo', 3, TRUE),
('DIS', 'District Branch', 'Mutare', 4, TRUE),
('VIL', 'Village Branch', 'Gweru', 5, TRUE)
ON CONFLICT (branch_id) DO NOTHING;

-- ============================================================
-- 44. COMPLETION
-- ============================================================
COMMENT ON DATABASE smartgro IS 'SmartGro ERP System - Zimbabwe Retail Management';