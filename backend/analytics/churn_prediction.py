# backend/analytics/churn_prediction.py
"""
Customer Churn Prediction Module
ML-based prediction of customer churn probability
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, 
    precision_score, 
    recall_score, 
    f1_score,
    roc_auc_score,
    confusion_matrix
)
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_sales,
    load_customers,
    load_customer_transactions,
    load_loyalty,
    load_products,
    to_float
)


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        if isinstance(value, str):
            cleaned = ''.join(c for c in value if c.isdigit() or c == '.')
            if cleaned:
                return float(cleaned)
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value, default=""):
    """Safely convert value to string"""
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


def get_customer_column(df):
    """Find customer name column"""
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "name", "client_name"]:
        if col in df.columns:
            return col
    return None


def get_phone_column(df):
    """Find phone column"""
    if df is None or df.empty:
        return None
    for col in ["phone", "customer_phone", "contact", "mobile"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    """Find date column in dataframe"""
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at", "last_purchase_date"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent", "total_spent"]:
        if col in df.columns:
            return col
    return None


def get_payment_method_column(df):
    """Find payment method column"""
    if df is None or df.empty:
        return None
    for col in ["payment_method", "payment_type", "payment"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


# ==============================
# COUNT UNIQUE CUSTOMERS FROM SALES
# ==============================

def count_unique_customers_from_sales(sales_df):
    """
    Count unique customers from sales data excluding 'Walk-in'
    Returns: (count, list_of_customer_names)
    """
    if sales_df.empty:
        return 0, []
    
    customer_col = get_customer_column(sales_df)
    if customer_col is None:
        return 0, []
    
    receipt_col = get_receipt_column(sales_df)
    
    # Use receipt-level deduplication if possible
    if receipt_col:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customers = unique_receipts[customer_col].astype(str).str.strip()
    else:
        customers = sales_df[customer_col].astype(str).str.strip()
    
    # Filter out invalid customers
    valid_customers = customers[
        ~customers.str.lower().str.contains('walk-in', na=False) &
        ~customers.str.lower().str.contains('unknown', na=False) &
        ~customers.str.lower().str.contains('none', na=False) &
        (customers != '') &
        (customers != 'nan') &
        (customers != 'None') &
        (customers.str.len() > 0)
    ]
    
    unique_customers = valid_customers.unique().tolist()
    unique_customers = [c for c in unique_customers if c and c.strip()]
    
    return len(unique_customers), unique_customers


# ==============================
# FEATURE ENGINEERING
# ==============================

def get_customers_from_sales(sales_df):
    """
    Extract unique customers from sales data.
    """
    if sales_df.empty:
        return pd.DataFrame()
    
    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    
    if customer_col is None:
        return pd.DataFrame()
    
    receipt_col = get_receipt_column(sales_df)
    
    # Use receipt-level deduplication
    if receipt_col:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customer_data = unique_receipts[[customer_col]].copy()
    else:
        customer_data = sales_df[[customer_col]].copy()
    
    # Rename column
    customer_data.columns = ["customer_name"]
    
    # Add phone if available
    if phone_col and phone_col in sales_df.columns:
        if receipt_col:
            phone_data = sales_df.drop_duplicates(subset=[receipt_col])[[phone_col]].copy()
        else:
            phone_data = sales_df[[phone_col]].copy()
        customer_data["phone"] = phone_data[phone_col].astype(str)
    else:
        customer_data["phone"] = ""
    
    # Clean data
    customer_data = customer_data.drop_duplicates(subset=["customer_name"])
    customer_data = customer_data[
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('walk-in', na=False) &
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('unknown', na=False) &
        (customer_data["customer_name"].astype(str).str.strip() != '') &
        (customer_data["customer_name"].astype(str).str.strip() != 'nan') &
        (customer_data["customer_name"].astype(str).str.strip() != 'None')
    ]
    
    return customer_data


def calculate_rfm_metrics(sales_df, customers_df):
    """
    Calculate RFM metrics for each customer.
    """
    rfm_data = []
    
    if customers_df.empty:
        return pd.DataFrame()
    
    customer_col = get_customer_column(customers_df)
    if customer_col is None:
        return pd.DataFrame()
    
    sales_date_col = get_date_column(sales_df)
    amount_col = get_amount_column(sales_df)
    sales_customer_col = get_customer_column(sales_df)
    
    for _, customer in customers_df.iterrows():
        customer_name = safe_str(customer.get(customer_col, ""))
        customer_phone = safe_str(customer.get("phone", ""))
        
        if not customer_name or customer_name.strip() == "":
            continue
        
        # Find sales for this customer
        customer_sales = pd.DataFrame()
        if not sales_df.empty and sales_customer_col:
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )]
            except:
                customer_sales = pd.DataFrame()
        
        recency_days = 999.0
        frequency = 0.0
        monetary = 0.0
        avg_order_value = 0.0
        is_churned = 1.0
        
        if not customer_sales.empty and sales_date_col and amount_col:
            try:
                customer_sales[sales_date_col] = pd.to_datetime(customer_sales[sales_date_col], errors="coerce")
                customer_sales = customer_sales.dropna(subset=[sales_date_col])
                
                if not customer_sales.empty:
                    last_purchase = customer_sales[sales_date_col].max()
                    recency_days = float((datetime.now() - last_purchase).days)
                    frequency = float(len(customer_sales))
                    monetary = safe_float(customer_sales[amount_col].sum())
                    avg_order_value = monetary / frequency if frequency > 0 else 0.0
                    is_churned = 1.0 if recency_days > 90 else 0.0
            except:
                pass
        
        rfm_data.append({
            "customer_name": customer_name,
            "phone": customer_phone,
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary": monetary,
            "avg_order_value": avg_order_value,
            "is_churned": is_churned
        })
    
    if not rfm_data:
        return pd.DataFrame()
    
    return pd.DataFrame(rfm_data)


def calculate_customer_features(customers_df, rfm_df, loyalty_df, sales_df):
    """
    Build comprehensive feature set for each customer.
    """
    if customers_df.empty:
        return pd.DataFrame()
    
    features = []
    customer_col = get_customer_column(customers_df)
    
    if customer_col is None:
        return pd.DataFrame()
    
    for _, customer in customers_df.iterrows():
        customer_name = safe_str(customer.get(customer_col, ""))
        customer_phone = safe_str(customer.get("phone", ""))
        
        if not customer_name or customer_name.strip() == "":
            continue
        
        rfm_data = rfm_df[rfm_df["customer_name"] == customer_name]
        if not rfm_data.empty:
            rfm_row = rfm_data.iloc[0]
        else:
            rfm_row = {
                "recency_days": 999.0,
                "frequency": 0.0,
                "monetary": 0.0,
                "avg_order_value": 0.0,
                "is_churned": 1.0
            }
        
        loyalty_points = 0.0
        if not loyalty_df.empty:
            try:
                loyalty_data = loyalty_df[loyalty_df["phone"].astype(str) == str(customer_phone)]
                if not loyalty_data.empty:
                    loyalty_points = safe_float(loyalty_data.iloc[0].get("points", 0))
            except:
                loyalty_points = 0.0
        
        features.append({
            "customer_name": customer_name,
            "phone": customer_phone,
            "recency_days": float(rfm_row.get("recency_days", 999)),
            "frequency": float(rfm_row.get("frequency", 0)),
            "monetary": float(rfm_row.get("monetary", 0)),
            "avg_order_value": float(rfm_row.get("avg_order_value", 0)),
            "loyalty_points": float(loyalty_points),
            "is_churned": float(rfm_row.get("is_churned", 1))
        })
    
    if not features:
        return pd.DataFrame()
    
    return pd.DataFrame(features)


# ==============================
# ML MODEL TRAINING
# ==============================

class ChurnPredictor:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.model_trained = False
        self.performance_metrics = {}
        self.feature_importance = {}
    
    def prepare_data(self, features_df):
        if features_df.empty:
            return None, None, None, None
        
        self.feature_columns = [
            "recency_days", "frequency", "monetary", "avg_order_value", "loyalty_points"
        ]
        
        X = features_df[self.feature_columns].copy()
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)
        
        y = pd.to_numeric(features_df["is_churned"], errors="coerce").fillna(1).values
        
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, y, features_df
    
    def train(self, features_df, test_size=0.3, random_state=42):
        X, y, df = self.prepare_data(features_df)
        
        if X is None or y is None:
            return False, "No data available for training"
        
        if len(y) < 10:
            return False, f"Need at least 10 customers. Currently have {len(y)}."
        
        n_churned = sum(y)
        n_active = len(y) - n_churned
        
        if n_churned == 0:
            return False, "No churned customers found. Need both active and churned customers."
        
        if n_active == 0:
            return False, "No active customers found. Need both active and churned customers."
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=5,
            min_samples_leaf=2, random_state=random_state, class_weight="balanced"
        )
        
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)[:, 1] if hasattr(self.model, "predict_proba") else None
        
        self.performance_metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()
        }
        
        if y_proba is not None:
            self.performance_metrics["roc_auc"] = roc_auc_score(y_test, y_proba)
        
        self.model_trained = True
        
        if hasattr(self.model, "feature_importances_"):
            self.feature_importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        
        return True, f"✅ Model trained on {len(X)} customers."
    
    def predict_batch(self, features_df):
        if not self.model_trained:
            return None, "Model not trained yet"
        
        try:
            X = features_df[self.feature_columns].copy()
            for col in X.columns:
                X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)
            
            X_scaled = self.scaler.transform(X)
            
            probabilities = self.model.predict_proba(X_scaled)[:, 1]
            predictions = self.model.predict(X_scaled)
            
            results = features_df.copy()
            results["churn_probability"] = (probabilities * 100).round(1)
            results["will_churn"] = predictions.astype(bool)
            results["risk_level"] = results["churn_probability"].apply(self.get_risk_level)
            
            return results, "Predictions generated"
        except Exception as e:
            return None, f"Error: {str(e)}"
    
    def get_risk_level(self, probability):
        if probability >= 70:
            return "HIGH"
        elif probability >= 40:
            return "MEDIUM"
        elif probability >= 20:
            return "LOW"
        else:
            return "VERY LOW"


# ==============================
# DASHBOARD
# ==============================

def churn_prediction_dashboard():
    st.title("Customer Churn Prediction")
    st.caption("AI-powered churn prediction to help you retain customers")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access churn prediction.")
        return
    
    # Load data
    with st.spinner("Loading data..."):
        sales_df = load_sales()
        customers_df = load_customers()
        loyalty_df = load_loyalty()
    
    if sales_df.empty:
        st.warning("No sales data available. Complete some transactions first.")
        return
    
    # ==============================
    # COUNT UNIQUE CUSTOMERS FROM SALES
    # ==============================
    customer_count, customer_names = count_unique_customers_from_sales(sales_df)
    
    # Show customer count
    st.sidebar.markdown("### 👥 Customer Analysis")
    st.sidebar.write(f"**Unique Customers (excluding Walk-in):** {customer_count}")
    
    if customer_count > 0 and customer_count <= 10:
        st.sidebar.warning(f"⚠️ Only {customer_count} customers found. Need at least 10 for training.")
    
    # Show sample customers
    if customer_names:
        sample = customer_names[:5] if len(customer_names) > 5 else customer_names
        st.sidebar.write(f"**Sample Customers:** {', '.join(sample)}")
        if len(customer_names) > 5:
            st.sidebar.caption(f"... and {len(customer_names) - 5} more")
    
    # ==============================
    # FIX: Use customers from sales if needed
    # ==============================
    if customers_df.empty or len(customers_df) < 5:
        st.info("📊 Extracting customers from sales data...")
        customers_df = get_customers_from_sales(sales_df)
    
    # Filter out Walk-in
    customer_col = get_customer_column(customers_df)
    if customer_col:
        customers_df = customers_df[
            ~customers_df[customer_col].astype(str).str.lower().str.contains('walk-in', na=False) &
            ~customers_df[customer_col].astype(str).str.lower().str.contains('unknown', na=False) &
            (customers_df[customer_col].astype(str).str.strip() != '') &
            (customers_df[customer_col].astype(str).str.strip() != 'nan')
        ]
    
    if customers_df.empty:
        st.warning("No valid customers found. Please record customer names during checkout (avoid 'Walk-in').")
        return
    
    # Initialize model
    if "churn_model" not in st.session_state:
        st.session_state.churn_model = ChurnPredictor()
        st.session_state.churn_model_trained = False
        st.session_state.churn_results = None
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "Overview",
        "Train Model",
        "At-Risk Customers"
    ])
    
    # ==============================
    # TAB 1: OVERVIEW
    # ==============================
    with tab1:
        st.markdown("## Churn Prediction Overview")
        
        total_customers = len(customers_df)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Customers", total_customers)
        with col2:
            st.metric("Customers with Sales", customer_count)
        with col3:
            st.metric("Customers without Sales", total_customers - customer_count)
        
        if customer_count < 10:
            st.warning(f"⚠️ Only {customer_count} customers with sales. Need at least 10 for training.")
            st.info("💡 Tip: When recording sales, enter a customer name instead of 'Walk-in'.")
        
        st.markdown("---")
        st.markdown("### Model Status")
        
        if st.session_state.churn_model_trained:
            st.success("✅ Model is trained and ready")
            
            metrics = st.session_state.churn_model.performance_metrics
            if metrics:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Accuracy", f"{metrics.get('accuracy', 0)*100:.1f}%")
                with col2:
                    st.metric("Precision", f"{metrics.get('precision', 0)*100:.1f}%")
                with col3:
                    st.metric("Recall", f"{metrics.get('recall', 0)*100:.1f}%")
                with col4:
                    st.metric("F1 Score", f"{metrics.get('f1', 0)*100:.1f}%")
        else:
            st.warning("⚠️ Model not trained yet.")
            
            if customer_count >= 10:
                if st.button("Quick Train Model", use_container_width=True):
                    with st.spinner("Training model..."):
                        rfm_df = calculate_rfm_metrics(sales_df, customers_df)
                        if not rfm_df.empty:
                            features_df = calculate_customer_features(customers_df, rfm_df, loyalty_df, sales_df)
                            if not features_df.empty:
                                success, message = st.session_state.churn_model.train(features_df)
                                if success:
                                    st.session_state.churn_model_trained = True
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
            else:
                st.info(f"Need {10 - customer_count} more customers with sales to train the model.")
    
    # ==============================
    # TAB 2: TRAIN MODEL
    # ==============================
    with tab2:
        st.markdown("## Train Churn Prediction Model")
        
        st.info("""
        Train a machine learning model to predict which customers are likely to churn.
        
        **Features used:**
        - Recency (days since last purchase)
        - Frequency (number of purchases)
        - Monetary (total spent)
        - Average order value
        - Loyalty points
        """)
        
        st.markdown("### Customer Data Status")
        
        if customer_count > 0:
            st.write(f"**Customers with sales:** {customer_count}")
            st.write(f"**Total customers:** {len(customers_df)}")
            
            if customer_count < 10:
                st.warning(f"⚠️ Need {10 - customer_count} more customers with sales.")
        
        if customer_count >= 10:
            if st.button("Train Model", type="primary", use_container_width=True):
                with st.spinner("Training model..."):
                    rfm_df = calculate_rfm_metrics(sales_df, customers_df)
                    if not rfm_df.empty:
                        features_df = calculate_customer_features(customers_df, rfm_df, loyalty_df, sales_df)
                        if not features_df.empty:
                            st.session_state.churn_model = ChurnPredictor()
                            success, message = st.session_state.churn_model.train(features_df)
                            if success:
                                st.session_state.churn_model_trained = True
                                st.success(message)
                                st.balloons()
                            else:
                                st.error(message)
        else:
            st.info("Add more customers with sales to enable training.")
    
    # ==============================
    # TAB 3: AT-RISK CUSTOMERS
    # ==============================
    with tab3:
        st.markdown("## At-Risk Customers")
        
        if not st.session_state.churn_model_trained:
            st.warning("Model not trained yet. Please train the model first.")
        else:
            if st.button("Identify At-Risk Customers", type="primary", use_container_width=True):
                with st.spinner("Analyzing customers..."):
                    rfm_df = calculate_rfm_metrics(sales_df, customers_df)
                    if not rfm_df.empty:
                        features_df = calculate_customer_features(customers_df, rfm_df, loyalty_df, sales_df)
                        if not features_df.empty:
                            results, message = st.session_state.churn_model.predict_batch(features_df)
                            if results is not None:
                                st.session_state.churn_results = results.sort_values(
                                    "churn_probability", ascending=False
                                )
                                st.success(message)
                            else:
                                st.error(message)
            
            if st.session_state.churn_results is not None:
                results_df = st.session_state.churn_results
                
                risk_filter = st.selectbox(
                    "Filter by Risk Level",
                    ["All", "HIGH", "MEDIUM", "LOW", "VERY LOW"]
                )
                
                filtered_df = results_df.copy()
                if risk_filter != "All":
                    filtered_df = filtered_df[filtered_df["risk_level"] == risk_filter]
                
                high_risk = len(results_df[results_df["risk_level"] == "HIGH"])
                medium_risk = len(results_df[results_df["risk_level"] == "MEDIUM"])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.error(f"High Risk: {high_risk}")
                with col2:
                    st.warning(f"Medium Risk: {medium_risk}")
                with col3:
                    st.info(f"Total Analyzed: {len(results_df)}")
                
                st.markdown("---")
                
                display_cols = ["customer_name", "phone", "churn_probability", "risk_level", "recency_days", "frequency", "monetary"]
                available_cols = [col for col in display_cols if col in filtered_df.columns]
                
                if available_cols:
                    st.dataframe(
                        filtered_df[available_cols],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "churn_probability": st.column_config.ProgressColumn(
                                "Churn %", 
                                min_value=0, 
                                max_value=100,
                                format="%.1f%%"
                            ),
                            "monetary": st.column_config.NumberColumn("Total Spent", format="$%.2f")
                        }
                    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    churn_prediction_dashboard()