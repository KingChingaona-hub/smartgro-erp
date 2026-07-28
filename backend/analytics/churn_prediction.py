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
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
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
# FEATURE ENGINEERING
# ==============================

def calculate_rfm_metrics(customer_transactions_df, sales_df, customers_df):
    """
    Calculate RFM (Recency, Frequency, Monetary) metrics for each customer.
    """
    rfm_data = {}
    
    if customers_df.empty:
        return pd.DataFrame()
    
    # Get customer list
    customer_col = get_customer_column(customers_df)
    if customer_col is None:
        return pd.DataFrame()
    
    # Get phone column for matching
    phone_col = get_phone_column(customers_df)
    
    # Get date column from sales
    sales_date_col = get_date_column(sales_df)
    
    # Get amount column from sales
    amount_col = get_amount_column(sales_df)
    
    # Find customer column in sales
    sales_customer_col = get_customer_column(sales_df)
    
    # Process each customer
    for idx, customer in customers_df.iterrows():
        customer_name = safe_str(customer.get(customer_col, ""))
        customer_phone = safe_str(customer.get(phone_col, "")) if phone_col else ""
        
        # Find this customer's sales
        customer_sales = pd.DataFrame()
        
        if not sales_df.empty and sales_customer_col:
            # Match by name
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )]
            except:
                customer_sales = pd.DataFrame()
        
        # If no sales by name, try by phone
        if customer_sales.empty and phone_col and "customer_phone" in sales_df.columns:
            try:
                customer_sales = sales_df[sales_df["customer_phone"].astype(str) == str(customer_phone)]
            except:
                customer_sales = pd.DataFrame()
        
        if customer_sales.empty:
            # No sales for this customer
            rfm_data[customer_name] = {
                "customer_name": customer_name,
                "phone": customer_phone,
                "recency_days": 999,
                "frequency": 0,
                "monetary": 0,
                "avg_order_value": 0,
                "is_churned": 1  # Mark as churned if no sales
            }
            continue
        
        # Calculate metrics
        if sales_date_col and amount_col:
            try:
                # Convert dates
                customer_sales[sales_date_col] = pd.to_datetime(customer_sales[sales_date_col], errors="coerce")
                customer_sales = customer_sales.dropna(subset=[sales_date_col])
                
                if not customer_sales.empty:
                    # Recency: days since last purchase
                    last_purchase = customer_sales[sales_date_col].max()
                    recency_days = (datetime.now() - last_purchase).days
                    
                    # Frequency: number of purchases
                    frequency = len(customer_sales)
                    
                    # Monetary: total spent
                    monetary = safe_float(customer_sales[amount_col].sum())
                    
                    # Average order value
                    avg_order_value = monetary / frequency if frequency > 0 else 0
                    
                    # Determine if churned (no purchase in last 90 days)
                    is_churned = 1 if recency_days > 90 else 0
                    
                    rfm_data[customer_name] = {
                        "customer_name": customer_name,
                        "phone": customer_phone,
                        "recency_days": recency_days,
                        "frequency": frequency,
                        "monetary": monetary,
                        "avg_order_value": avg_order_value,
                        "is_churned": is_churned
                    }
                else:
                    rfm_data[customer_name] = {
                        "customer_name": customer_name,
                        "phone": customer_phone,
                        "recency_days": 999,
                        "frequency": 0,
                        "monetary": 0,
                        "avg_order_value": 0,
                        "is_churned": 1
                    }
            except Exception as e:
                rfm_data[customer_name] = {
                    "customer_name": customer_name,
                    "phone": customer_phone,
                    "recency_days": 999,
                    "frequency": 0,
                    "monetary": 0,
                    "avg_order_value": 0,
                    "is_churned": 1
                }
        else:
            rfm_data[customer_name] = {
                "customer_name": customer_name,
                "phone": customer_phone,
                "recency_days": 999,
                "frequency": 0,
                "monetary": 0,
                "avg_order_value": 0,
                "is_churned": 1
            }
    
    return pd.DataFrame(rfm_data).T


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
    
    # Get products data for categories
    products_df = load_products()
    
    for idx, customer in customers_df.iterrows():
        customer_name = safe_str(customer.get(customer_col, ""))
        customer_phone = safe_str(customer.get(phone_col, "")) if phone_col else ""
        
        # Get RFM features
        rfm_data = rfm_df[rfm_df["customer_name"] == customer_name]
        if not rfm_data.empty:
            rfm_row = rfm_data.iloc[0]
        else:
            rfm_row = pd.Series({
                "recency_days": 999,
                "frequency": 0,
                "monetary": 0,
                "avg_order_value": 0,
                "is_churned": 1
            })
        
        # Get loyalty features
        loyalty_points = 0
        loyalty_tier = "BRONZE"
        if not loyalty_df.empty:
            try:
                loyalty_data = loyalty_df[loyalty_df["phone"].astype(str) == str(customer_phone)]
                if not loyalty_data.empty:
                    loyalty_points = safe_int(loyalty_data.iloc[0].get("points", 0))
                    loyalty_tier = safe_str(loyalty_data.iloc[0].get("tier", "BRONZE"))
            except:
                loyalty_points = 0
        
        # Calculate additional features
        # 1. Purchase regularity (std dev of days between purchases)
        purchase_regularity = 0
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
            except:
                purchase_regularity = 0
        
        # 2. Customer tenure (days since first purchase)
        tenure_days = 0
        if not sales_df.empty and date_col and sales_customer_col:
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )].copy()
                
                if not customer_sales.empty:
                    customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
                    customer_sales = customer_sales.dropna(subset=[date_col])
                    
                    if not customer_sales.empty:
                        first_purchase = customer_sales[date_col].min()
                        tenure_days = (datetime.now() - first_purchase).days
            except:
                tenure_days = 0
        
        # 3. Average items per order
        avg_items = 0
        if not sales_df.empty and sales_customer_col:
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )].copy()
                
                if not customer_sales.empty and "items" in customer_sales.columns:
                    avg_items = safe_float(customer_sales["items"].mean())
            except:
                avg_items = 0
        
        # 4. Payment method diversity (FIXED: count unique methods, not sum)
        payment_diversity = 0
        payment_methods = []
        if not sales_df.empty and sales_customer_col:
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )].copy()
                
                if not customer_sales.empty:
                    payment_col = get_payment_method_column(customer_sales)
                    if payment_col and payment_col in customer_sales.columns:
                        # Get unique payment methods, filter out empty/unknown
                        payment_methods = customer_sales[payment_col].dropna().unique().tolist()
                        # Filter out empty strings and 'Unknown'
                        payment_methods = [p for p in payment_methods if p and str(p).strip() and str(p).lower() != 'unknown']
                        payment_diversity = len(payment_methods)
            except:
                payment_diversity = 0
        
        # 5. Favorite category (if products data available)
        favorite_category = "Unknown"
        if not sales_df.empty and sales_customer_col and "barcode" in sales_df.columns:
            try:
                customer_sales = sales_df[sales_df[sales_customer_col].astype(str).str.contains(
                    customer_name, case=False, na=False
                )].copy()
                
                if not customer_sales.empty and "barcode" in customer_sales.columns:
                    # Get product categories
                    if not products_df.empty and "barcode" in products_df.columns and "category" in products_df.columns:
                        product_categories = {}
                        for _, sale in customer_sales.iterrows():
                            barcode = safe_str(sale.get("barcode", ""))
                            product = products_df[products_df["barcode"].astype(str) == barcode]
                            if not product.empty:
                                category = safe_str(product.iloc[0].get("category", "Unknown"))
                                product_categories[category] = product_categories.get(category, 0) + 1
                        
                        if product_categories:
                            favorite_category = max(product_categories, key=product_categories.get)
            except:
                favorite_category = "Unknown"
        
        # Build feature vector
        features.append({
            "customer_name": customer_name,
            "phone": customer_phone,
            "recency_days": safe_float(rfm_row.get("recency_days", 999)),
            "frequency": safe_float(rfm_row.get("frequency", 0)),
            "monetary": safe_float(rfm_row.get("monetary", 0)),
            "avg_order_value": safe_float(rfm_row.get("avg_order_value", 0)),
            "loyalty_points": safe_float(loyalty_points),
            "purchase_regularity": safe_float(purchase_regularity),
            "tenure_days": safe_float(tenure_days),
            "avg_items": safe_float(avg_items),
            "payment_diversity": safe_float(payment_diversity),
            "is_churned": safe_float(rfm_row.get("is_churned", 1)),
            "favorite_category": safe_str(favorite_category)
        })
    
    return pd.DataFrame(features)


# ==============================
# ML MODEL TRAINING
# ==============================

class ChurnPredictor:
    """Customer Churn Prediction Model"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoders = {}
        self.feature_columns = []
        self.model_trained = False
        self.performance_metrics = {}
        self.feature_importance = {}
    
    def prepare_data(self, features_df):
        """Prepare data for training"""
        if features_df.empty:
            return None, None, None, None
        
        # Define features to use
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
        
        # Handle categorical features
        X = features_df[self.feature_columns].copy()
        
        # Remove any non-numeric values
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)
        
        y = features_df["is_churned"].values
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=X.columns)
        
        return X_scaled, y, features_df
    
    def train(self, features_df, test_size=0.3, random_state=42):
        """Train the churn prediction model"""
        
        X, y, df = self.prepare_data(features_df)
        
        if X is None or y is None:
            return False, "No data available for training"
        
        # Check class balance
        n_churned = sum(y)
        n_active = len(y) - n_churned
        
        if n_churned == 0 or n_active == 0:
            return False, "Need both churned and active customers for training. Try adding more data."
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        # Train model - using Random Forest for better performance
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
        
        # Calculate metrics
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
        
        # Feature importance
        if hasattr(self.model, "feature_importances_"):
            importance = self.model.feature_importances_
            feature_names = X.columns.tolist()
            self.feature_importance = dict(zip(feature_names, importance))
        
        return True, "Model trained successfully"
    
    def predict(self, customer_data):
        """Predict churn probability for a single customer"""
        if not self.model_trained:
            return None, "Model not trained yet"
        
        try:
            # Prepare data
            X = pd.DataFrame([customer_data])[self.feature_columns].fillna(0)
            
            # Convert to numeric
            for col in X.columns:
                X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)
            
            # Scale
            X_scaled = self.scaler.transform(X)
            
            # Predict
            proba = self.model.predict_proba(X_scaled)[0, 1]
            prediction = self.model.predict(X_scaled)[0]
            
            return {
                "probability": round(proba * 100, 1),
                "will_churn": bool(prediction),
                "risk_level": self.get_risk_level(proba),
                "recommendation": self.get_recommendation(proba)
            }
        except Exception as e:
            return {
                "probability": 0,
                "will_churn": False,
                "risk_level": "UNKNOWN",
                "recommendation": f"Error: {str(e)}"
            }
    
    def predict_batch(self, features_df):
        """Predict churn probability for all customers"""
        if not self.model_trained:
            return None, "Model not trained yet"
        
        try:
            # Prepare data
            X = features_df[self.feature_columns].copy()
            
            # Convert to numeric
            for col in X.columns:
                X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)
            
            # Scale
            X_scaled = self.scaler.transform(X)
            
            # Predict
            probabilities = self.model.predict_proba(X_scaled)[:, 1]
            predictions = self.model.predict(X_scaled)
            
            results = features_df.copy()
            results["churn_probability"] = (probabilities * 100).round(1)
            results["will_churn"] = predictions.astype(bool)
            results["risk_level"] = results["churn_probability"].apply(self.get_risk_level)
            results["recommendation"] = results["churn_probability"].apply(self.get_recommendation)
            
            return results, "Predictions generated"
        except Exception as e:
            return None, f"Error generating predictions: {str(e)}"
    
    def get_risk_level(self, probability):
        """Get risk level based on probability"""
        if probability >= 0.7:
            return "HIGH"
        elif probability >= 0.4:
            return "MEDIUM"
        elif probability >= 0.2:
            return "LOW"
        else:
            return "VERY LOW"
    
    def get_recommendation(self, probability):
        """Get recommendation based on probability"""
        if probability >= 0.7:
            return "IMMEDIATE ACTION: Call customer and offer retention discount"
        elif probability >= 0.4:
            return "Send re-engagement offer and follow up"
        elif probability >= 0.2:
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
    
    if customers_df.empty:
        st.warning("No customer data available. Please add customers first.")
        return
    
    if sales_df.empty:
        st.warning("No sales data available. Complete some transactions first.")
        return
    
    # Initialize model in session state
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
        
        # Calculate basic stats
        customer_col = get_customer_column(customers_df)
        phone_col = get_phone_column(customers_df)
        date_col = get_date_column(sales_df)
        amount_col = get_amount_column(sales_df)
        sales_customer_col = get_customer_column(sales_df)
        
        total_customers = len(customers_df)
        
        # Count active vs churned (based on last 90 days)
        active_customers = 0
        churned_customers = 0
        
        sales_date_col = get_date_column(sales_df)
        if sales_date_col:
            try:
                cutoff_date = datetime.now() - timedelta(days=90)
                recent_customers = set()
                
                if sales_customer_col:
                    sales_df[sales_date_col] = pd.to_datetime(sales_df[sales_date_col], errors="coerce")
                    recent_sales = sales_df[sales_df[sales_date_col] >= cutoff_date]
                    
                    if not recent_sales.empty:
                        recent_customers = set(recent_sales[sales_customer_col].astype(str).unique())
                
                # Check each customer
                for _, customer in customers_df.iterrows():
                    customer_name = safe_str(customer.get(customer_col, ""))
                    
                    # Check if customer has recent sales
                    has_recent = False
                    for name in recent_customers:
                        if name and customer_name and (name in customer_name or customer_name in name):
                            has_recent = True
                            break
                    
                    if has_recent:
                        active_customers += 1
                    else:
                        churned_customers += 1
            except:
                active_customers = 0
                churned_customers = total_customers
        else:
            # Fallback: use last_purchase_date if available
            if "last_purchase_date" in customers_df.columns:
                try:
                    customers_df["last_purchase_date"] = pd.to_datetime(
                        customers_df["last_purchase_date"], errors="coerce"
                    )
                    cutoff_date = datetime.now() - timedelta(days=90)
                    active_customers = len(customers_df[customers_df["last_purchase_date"] >= cutoff_date])
                    churned_customers = total_customers - active_customers
                except:
                    active_customers = 0
                    churned_customers = total_customers
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Customers", total_customers)
        with col2:
            st.metric("Active Customers", active_customers)
        with col3:
            st.metric("Churned Customers", churned_customers)
        with col4:
            churn_rate = (churned_customers / total_customers * 100) if total_customers > 0 else 0
            st.metric("Churn Rate", f"{churn_rate:.1f}%")
        
        # Model status
        st.markdown("---")
        st.markdown("### Model Status")
        
        if st.session_state.churn_model_trained:
            st.success("Model is trained and ready")
            
            # Show model performance
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
                
                # Feature importance
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
                    # Prepare data
                    rfm_df = calculate_rfm_metrics(
                        load_customer_transactions() if not load_customer_transactions().empty else pd.DataFrame(),
                        sales_df,
                        customers_df
                    )
                    features_df = calculate_customer_features(
                        customers_df, rfm_df, loyalty_df, sales_df
                    )
                    
                    if not features_df.empty:
                        success, message = st.session_state.churn_model.train(features_df)
                        if success:
                            st.session_state.churn_model_trained = True
                            st.success(f"{message}")
                            st.rerun()
                        else:
                            st.error(f"{message}")
                    else:
                        st.error("Could not prepare features")
    
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
        
        col1, col2 = st.columns(2)
        
        with col1:
            test_size = st.slider("Test Size", 0.1, 0.4, 0.3, 0.05, help="Portion of data to use for testing")
            random_state = st.number_input("Random Seed", 1, 100, 42, step=1, help="For reproducible results")
        
        with col2:
            st.markdown("### Data Overview")
            
            customer_count = len(customers_df)
            sales_count = len(sales_df)
            
            st.write(f"**Customers:** {customer_count}")
            st.write(f"**Sales Records:** {sales_count}")
            
            if customer_col:
                st.write(f"**Customer Column:** {customer_col}")
        
        if st.button("Train Model", type="primary", use_container_width=True):
            with st.spinner("Training model... This may take a few seconds."):
                # Prepare features
                rfm_df = calculate_rfm_metrics(
                    load_customer_transactions() if not load_customer_transactions().empty else pd.DataFrame(),
                    sales_df,
                    customers_df
                )
                
                if rfm_df.empty:
                    st.error("Could not calculate RFM metrics. Please ensure you have sales data.")
                else:
                    features_df = calculate_customer_features(
                        customers_df, rfm_df, loyalty_df, sales_df
                    )
                    
                    if features_df.empty:
                        st.error("Could not prepare features. Please check your data.")
                    else:
                        st.session_state.churn_model = ChurnPredictor()
                        success, message = st.session_state.churn_model.train(
                            features_df, test_size=test_size, random_state=random_state
                        )
                        
                        if success:
                            st.session_state.churn_model_trained = True
                            st.success(f"{message}")
                            st.balloons()
                            
                            # Show metrics
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
                            
                            # Confusion Matrix
                            cm = metrics.get("confusion_matrix", [[0, 0], [0, 0]])
                            if cm:
                                st.markdown("### Confusion Matrix")
                                cm_df = pd.DataFrame(
                                    cm,
                                    index=["Actual Active", "Actual Churned"],
                                    columns=["Predicted Active", "Predicted Churned"]
                                )
                                st.dataframe(cm_df, use_container_width=True)
                                if "roc_auc" in metrics:
                                    st.caption(f"ROC AUC: {metrics['roc_auc']:.3f}")
                        else:
                            st.error(f"{message}")
    
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
                        load_customer_transactions() if not load_customer_transactions().empty else pd.DataFrame(),
                        sales_df,
                        customers_df
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
                                st.success(f"{message}")
                            else:
                                st.error(f"{message}")
            
            # Display results
            if st.session_state.churn_results is not None:
                results_df = st.session_state.churn_results
                
                col1, col2 = st.columns(2)
                with col1:
                    risk_filter = st.selectbox(
                        "Filter by Risk Level",
                        ["All", "HIGH", "MEDIUM", "LOW", "VERY LOW"]
                    )
                with col2:
                    st.caption("Sort by probability (highest risk first)")
                
                filtered_df = results_df.copy()
                if risk_filter != "All":
                    filtered_df = filtered_df[filtered_df["risk_level"] == risk_filter]
                
                # Show metrics
                high_risk = len(results_df[results_df["risk_level"] == "HIGH"])
                medium_risk = len(results_df[results_df["risk_level"] == "MEDIUM"])
                low_risk = len(results_df[results_df["risk_level"] == "LOW"])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.error(f"High Risk: {high_risk}")
                with col2:
                    st.warning(f"Medium Risk: {medium_risk}")
                with col3:
                    st.info(f"Low Risk: {low_risk}")
                
                st.markdown("---")
                
                # Display table
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
                    
                    # Export
                    csv = filtered_df[available_cols].to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download At-Risk Customers (CSV)",
                        data=csv,
                        file_name=f"at_risk_customers_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
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
                        # Find customer
                        customer_results = customers_df[
                            customers_df[customer_col].astype(str).str.contains(search_term, case=False) |
                            customers_df["phone"].astype(str).str.contains(search_term, case=False)
                        ]
                        
                        if not customer_results.empty:
                            selected_customer = customer_results.iloc[0]
                            customer_name = safe_str(selected_customer.get(customer_col, ""))
                            customer_phone = safe_str(selected_customer.get("phone", ""))
                            
                            # Get customer features
                            rfm_df = calculate_rfm_metrics(
                                load_customer_transactions() if not load_customer_transactions().empty else pd.DataFrame(),
                                sales_df,
                                customers_df
                            )
                            
                            if not rfm_df.empty:
                                features_df = calculate_customer_features(
                                    customers_df, rfm_df, loyalty_df, sales_df
                                )
                                
                                customer_data = features_df[features_df["customer_name"] == customer_name]
                                
                                if not customer_data.empty:
                                    # Predict churn
                                    row = customer_data.iloc[0].to_dict()
                                    prediction = st.session_state.churn_model.predict(row)
                                    
                                    if prediction:
                                        st.markdown("### Customer Risk Assessment")
                                        
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.metric("Customer", customer_name)
                                        with col2:
                                            st.metric("Phone", customer_phone)
                                        with col3:
                                            risk_color = {
                                                "HIGH": "🔴",
                                                "MEDIUM": "🟡",
                                                "LOW": "🟢",
                                                "VERY LOW": "✅"
                                            }.get(prediction["risk_level"], "❓")
                                            st.metric("Risk Level", f"{risk_color} {prediction['risk_level']}")
                                        
                                        st.markdown("### Churn Probability")
                                        
                                        fig_gauge = go.Figure(go.Indicator(
                                            mode="gauge+number",
                                            value=prediction["probability"],
                                            title={"text": "Churn Probability"},
                                            gauge={
                                                "axis": {"range": [0, 100]},
                                                "bar": {"color": "red" if prediction["probability"] > 40 else "orange" if prediction["probability"] > 20 else "green"},
                                                "steps": [
                                                    {"range": [0, 20], "color": "lightgreen"},
                                                    {"range": [20, 40], "color": "yellow"},
                                                    {"range": [40, 70], "color": "orange"},
                                                    {"range": [70, 100], "color": "red"}
                                                ]
                                            }
                                        ))
                                        fig_gauge.update_layout(height=250)
                                        st.plotly_chart(fig_gauge, use_container_width=True)
                                        
                                        st.markdown("### Recommendation")
                                        st.info(prediction["recommendation"])
                                        
                                        # Show customer details
                                        with st.expander("Customer Details"):
                                            details_cols = ["recency_days", "frequency", "monetary", "avg_order_value"]
                                            details = {col: row.get(col, 0) for col in details_cols}
                                            
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                st.write(f"**Days Since Last Purchase:** {details['recency_days']}")
                                                st.write(f"**Total Purchases:** {details['frequency']}")
                                            with col2:
                                                st.write(f"**Total Spent:** ${details['monetary']:.2f}")
                                                st.write(f"**Avg Order Value:** ${details['avg_order_value']:.2f}")
                                    else:
                                        st.warning("Could not generate prediction")
                                else:
                                    st.warning("No feature data available for this customer")
                        else:
                            st.warning("Customer not found")
                    except Exception as e:
                        st.error(f"Error searching customer: {str(e)}")
            else:
                st.warning("Customer column not found in data")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    churn_prediction_dashboard()