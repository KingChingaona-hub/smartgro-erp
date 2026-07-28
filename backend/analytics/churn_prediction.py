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
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score, 
    precision_score, 
    recall_score, 
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report
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


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(float(value))
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


def get_date_column(df):
    """Find date column in dataframe"""
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at", "last_purchase_date"]:
        if col in df.columns:
            return col
    return None


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


# ==============================
# FEATURE ENGINEERING - COMPLETELY REWRITTEN
# ==============================

def calculate_rfm_metrics(customer_transactions_df, sales_df, customers_df):
    """
    Calculate RFM (Recency, Frequency, Monetary) metrics for each customer.
    """
    rfm_data = []
    
    if customers_df.empty:
        return pd.DataFrame()
    
    customer_col = get_customer_column(customers_df)
    phone_col = get_phone_column(customers_df)
    sales_date_col = get_date_column(sales_df)
    amount_col = get_amount_column(sales_df)
    sales_customer_col = get_customer_column(sales_df)
    
    if customer_col is None:
        return pd.DataFrame()
    
    # Get unique customers with valid names
    for idx, customer in customers_df.iterrows():
        customer_name = safe_str(customer.get(customer_col, ""))
        customer_phone = safe_str(customer.get(phone_col, "")) if phone_col else ""
        
        # Skip customers with empty names
        if not customer_name or customer_name.strip() == "":
            continue
        
        # Find this customer's sales
        customer_sales = pd.DataFrame()
        
        if not sales_df.empty and sales_customer_col:
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )]
            except:
                customer_sales = pd.DataFrame()
        
        if customer_sales.empty and phone_col and "customer_phone" in sales_df.columns:
            try:
                customer_sales = sales_df[sales_df["customer_phone"].astype(str) == str(customer_phone)]
            except:
                customer_sales = pd.DataFrame()
        
        # Initialize with default values
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
    phone_col = get_phone_column(customers_df)
    
    if customer_col is None:
        return pd.DataFrame()
    
    products_df = load_products()
    
    # Get unique customers with valid names
    for idx, customer in customers_df.iterrows():
        customer_name = safe_str(customer.get(customer_col, ""))
        customer_phone = safe_str(customer.get(phone_col, "")) if phone_col else ""
        
        # Skip customers with empty names
        if not customer_name or customer_name.strip() == "":
            continue
        
        # Get RFM features
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
        
        # Get loyalty features
        loyalty_points = 0.0
        if not loyalty_df.empty:
            try:
                loyalty_data = loyalty_df[loyalty_df["phone"].astype(str) == str(customer_phone)]
                if not loyalty_data.empty:
                    loyalty_points = safe_float(loyalty_data.iloc[0].get("points", 0))
            except:
                loyalty_points = 0.0
        
        # Initialize features
        purchase_regularity = 0.0
        tenure_days = 0.0
        avg_items = 0.0
        payment_diversity = 0.0
        
        date_col = get_date_column(sales_df)
        sales_customer_col = get_customer_column(sales_df)
        
        if not sales_df.empty and date_col and sales_customer_col:
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )].copy()
                
                if not customer_sales.empty:
                    customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
                    customer_sales = customer_sales.dropna(subset=[date_col])
                    customer_sales = customer_sales.sort_values(date_col)
                    
                    if len(customer_sales) > 1:
                        date_diffs = customer_sales[date_col].diff().dt.days.dropna()
                        if not date_diffs.empty:
                            purchase_regularity = safe_float(date_diffs.std())
                    
                    if not customer_sales.empty:
                        first_purchase = customer_sales[date_col].min()
                        tenure_days = safe_float((datetime.now() - first_purchase).days)
                    
                    if "items" in customer_sales.columns:
                        avg_items = safe_float(customer_sales["items"].mean())
                    
                    payment_col = get_payment_method_column(customer_sales)
                    if payment_col and payment_col in customer_sales.columns:
                        try:
                            payment_methods = customer_sales[payment_col].dropna().unique().tolist()
                            payment_methods = [
                                p for p in payment_methods 
                                if p and str(p).strip() and str(p).lower() not in ['unknown', 'none', 'null', '']
                            ]
                            payment_diversity = float(len(payment_methods))
                        except:
                            payment_diversity = 0.0
            except:
                pass
        
        features.append({
            "customer_name": customer_name,
            "phone": customer_phone,
            "recency_days": float(rfm_row.get("recency_days", 999)),
            "frequency": float(rfm_row.get("frequency", 0)),
            "monetary": float(rfm_row.get("monetary", 0)),
            "avg_order_value": float(rfm_row.get("avg_order_value", 0)),
            "loyalty_points": float(loyalty_points),
            "purchase_regularity": float(purchase_regularity),
            "tenure_days": float(tenure_days),
            "avg_items": float(avg_items),
            "payment_diversity": float(payment_diversity),
            "is_churned": float(rfm_row.get("is_churned", 1))
        })
    
    if not features:
        return pd.DataFrame()
    
    return pd.DataFrame(features)


# ==============================
# ML MODEL TRAINING
# ==============================

class ChurnPredictor:
    """Customer Churn Prediction Model"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.model_trained = False
        self.performance_metrics = {}
        self.feature_importance = {}
    
    def prepare_data(self, features_df):
        """Prepare data for training"""
        if features_df.empty:
            return None, None, None, None
        
        # Define numeric features
        self.feature_columns = [
            "recency_days",
            "frequency",
            "monetary",
            "avg_order_value",
            "loyalty_points",
            "purchase_regularity",
            "tenure_days",
            "avg_items",
            "payment_diversity"
        ]
        
        # Extract and validate numeric features
        X = features_df[self.feature_columns].copy()
        
        # Convert ALL columns to numeric
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)
        
        # Get target
        y = pd.to_numeric(features_df["is_churned"], errors="coerce").fillna(1).values
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, y, features_df
    
    def train(self, features_df, test_size=0.3, random_state=42):
        """Train the churn prediction model"""
        
        X, y, df = self.prepare_data(features_df)
        
        if X is None or y is None:
            return False, "No data available for training"
        
        if len(y) < 10:
            return False, "Need at least 10 customers for training. Add more customers."
        
        n_churned = sum(y)
        n_active = len(y) - n_churned
        
        if n_churned == 0 or n_active == 0:
            return False, "Need both churned and active customers for training."
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=random_state,
            class_weight="balanced"
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
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
            feature_names = self.feature_columns
            self.feature_importance = dict(zip(feature_names, self.model.feature_importances_))
        
        return True, f"Model trained successfully on {len(X)} customers."
    
    def predict_batch(self, features_df):
        """Predict churn probability for all customers"""
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
            results["recommendation"] = results["churn_probability"].apply(self.get_recommendation)
            
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
    
    def get_recommendation(self, probability):
        if probability >= 70:
            return "IMMEDIATE ACTION: Call customer and offer retention discount"
        elif probability >= 40:
            return "Send re-engagement offer and follow up"
        elif probability >= 20:
            return "Send personalized recommendation email"
        else:
            return "Maintain regular communication"


# ==============================
# CHURN PREDICTION DASHBOARD
# ==============================

def churn_prediction_dashboard():
    """Customer Churn Prediction Dashboard"""
    
    st.title("Customer Churn Prediction")
    st.caption("AI-powered churn prediction to help you retain customers")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access churn prediction.")
        return
    
    # Load data
    with st.spinner("Loading customer data..."):
        customers_df = load_customers()
        sales_df = load_sales()
        loyalty_df = load_loyalty()
    
    # Debug: Show customer data info
    st.sidebar.markdown("### Debug Info")
    st.sidebar.write(f"Customers: {len(customers_df)}")
    st.sidebar.write(f"Sales: {len(sales_df)}")
    
    if customers_df.empty:
        st.warning("No customer data available. Please add customers first.")
        return
    
    if sales_df.empty:
        st.warning("No sales data available. Complete some transactions first.")
        return
    
    # Initialize model
    if "churn_model" not in st.session_state:
        st.session_state.churn_model = ChurnPredictor()
        st.session_state.churn_model_trained = False
        st.session_state.churn_results = None
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "Overview",
        "Train Model",
        "At-Risk Customers",
        "Customer Lookup"
    ])
    
    # ==============================
    # TAB 1: OVERVIEW
    # ==============================
    with tab1:
        st.markdown("## Churn Prediction Overview")
        
        customer_col = get_customer_column(customers_df)
        total_customers = len(customers_df)
        
        # Count customers with sales
        customers_with_sales = 0
        if customer_col and not sales_df.empty:
            sales_customer_col = get_customer_column(sales_df)
            if sales_customer_col:
                sales_customers = set(sales_df[sales_customer_col].astype(str).unique())
                customers_with_sales = sum(1 for _, c in customers_df.iterrows() 
                                          if safe_str(c.get(customer_col, "")) in sales_customers)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Customers", total_customers)
        with col2:
            st.metric("Customers with Sales", customers_with_sales)
        with col3:
            st.metric("Customers without Sales", total_customers - customers_with_sales)
        
        st.markdown("---")
        st.markdown("### Model Status")
        
        if st.session_state.churn_model_trained:
            st.success("Model is trained and ready")
            
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
                
                if st.session_state.churn_model.feature_importance:
                    st.markdown("### Feature Importance")
                    importance = st.session_state.churn_model.feature_importance
                    imp_df = pd.DataFrame({
                        "Feature": list(importance.keys()),
                        "Importance": list(importance.values())
                    }).sort_values("Importance", ascending=False)
                    
                    fig = px.bar(
                        imp_df,
                        x="Importance",
                        y="Feature",
                        orientation="h",
                        title="What Drives Churn?",
                        color="Importance",
                        color_continuous_scale="Reds"
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Model not trained yet. Go to 'Train Model' tab to train.")
            
            if st.button("Quick Train Model", use_container_width=True):
                with st.spinner("Training model..."):
                    rfm_df = calculate_rfm_metrics(
                        pd.DataFrame(), sales_df, customers_df
                    )
                    
                    if rfm_df.empty:
                        st.error("Could not calculate RFM metrics.")
                    else:
                        features_df = calculate_customer_features(
                            customers_df, rfm_df, loyalty_df, sales_df
                        )
                        
                        if features_df.empty:
                            st.error("Could not prepare features.")
                        else:
                            success, message = st.session_state.churn_model.train(features_df)
                            if success:
                                st.session_state.churn_model_trained = True
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
    
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
        - Purchase regularity
        - Customer tenure
        - Average items per order
        - Payment method diversity
        """)
        
        if st.button("Train Model", type="primary", use_container_width=True):
            with st.spinner("Training model..."):
                rfm_df = calculate_rfm_metrics(
                    pd.DataFrame(), sales_df, customers_df
                )
                
                if rfm_df.empty:
                    st.error("Could not calculate RFM metrics.")
                else:
                    features_df = calculate_customer_features(
                        customers_df, rfm_df, loyalty_df, sales_df
                    )
                    
                    if features_df.empty:
                        st.error("Could not prepare features.")
                    else:
                        st.session_state.churn_model = ChurnPredictor()
                        success, message = st.session_state.churn_model.train(features_df)
                        
                        if success:
                            st.session_state.churn_model_trained = True
                            st.success(message)
                            st.balloons()
                            
                            metrics = st.session_state.churn_model.performance_metrics
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
                            st.error(message)
    
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
                    rfm_df = calculate_rfm_metrics(
                        pd.DataFrame(), sales_df, customers_df
                    )
                    
                    if not rfm_df.empty:
                        features_df = calculate_customer_features(
                            customers_df, rfm_df, loyalty_df, sales_df
                        )
                        
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
                
                col1, col2 = st.columns(2)
                with col1:
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
                
                display_cols = [
                    "customer_name", "phone", "churn_probability", "risk_level", 
                    "recommendation", "recency_days", "frequency", "monetary"
                ]
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
    # TAB 4: CUSTOMER LOOKUP
    # ==============================
    with tab4:
        st.markdown("## Customer Lookup")
        
        if not st.session_state.churn_model_trained:
            st.warning("Model not trained yet. Please train the model first.")
        else:
            customer_col = get_customer_column(customers_df)
            
            if customer_col:
                search_term = st.text_input("Search Customer by Name or Phone", placeholder="Type name or phone...")
                
                if search_term:
                    try:
                        customer_results = customers_df[
                            customers_df[customer_col].astype(str).str.contains(search_term, case=False) |
                            customers_df["phone"].astype(str).str.contains(search_term, case=False)
                        ]
                        
                        if not customer_results.empty:
                            selected_customer = customer_results.iloc[0]
                            customer_name = safe_str(selected_customer.get(customer_col, ""))
                            
                            st.markdown("### Customer Found")
                            st.write(f"**Name:** {customer_name}")
                            st.write(f"**Phone:** {safe_str(selected_customer.get('phone', ''))}")
                            
                            # Check if customer has sales
                            sales_customer_col = get_customer_column(sales_df)
                            has_sales = False
                            if sales_customer_col:
                                has_sales = any(sales_df[sales_customer_col].astype(str).str.contains(
                                    customer_name, case=False, na=False
                                ))
                            
                            if has_sales:
                                st.success("This customer has sales records")
                            else:
                                st.warning("This customer has no sales records yet")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    churn_prediction_dashboard()