import streamlit as st
import json
from src.pipeline import run_pipeline

st.set_page_config(page_title="E-Commerce Support Agent", page_icon="🤖", layout="wide")

st.title("🛍️ E-Commerce Support Resolution Agent")
st.markdown("This multi-agent RAG system processes customer support tickets and checks them against our policy documentation.")

# Sidebar for Order Context Configuration
with st.sidebar:
    st.header("📋 Order Context")
    st.markdown("Simulate the data our system fetched from the order database.")
    
    order_id = st.text_input("Order ID", value="ORD-20250301-9823")
    order_date = st.date_input("Order Date")
    delivery_date = st.date_input("Delivery Date")
    
    item_category = st.selectbox(
        "Item Category", 
        ["apparel", "electronics", "hygiene", "perishable", "other"],
        index=3
    )
    
    fulfillment_type = st.selectbox(
        "Fulfillment Type",
        ["first-party", "marketplace_seller"]
    )
    
    shipping_region = st.selectbox(
        "Shipping Region",
        ["US", "EU", "Other"]
    )
    
    order_status = st.selectbox(
        "Order Status",
        ["placed", "processing", "shipped", "delivered", "returned"],
        index=3
    )
    
    payment_method = st.selectbox(
        "Payment Method",
        ["credit_card", "paypal", "store_credit"]
    )

st.header("💬 Customer Ticket")
ticket_text = st.text_area(
    "Enter the support ticket text from the customer:",
    value="I want to return the lipstick I bought. It was marked as Final Sale but I changed my mind.",
    height=150
)

if st.button("🚀 Process Ticket", type="primary"):
    with st.spinner("Processing ticket through Triage, Retrieval, Resolution, and Compliance agents..."):
        try:
            # Construct the input object expected by run_pipeline
            ticket_input = {
                "ticket_text": ticket_text,
                "order_context": {
                    "order_id": order_id,
                    "order_date": order_date.strftime("%Y-%m-%d"),
                    "delivery_date": delivery_date.strftime("%Y-%m-%d") if delivery_date else None,
                    "item_category": item_category,
                    "fulfillment_type": fulfillment_type,
                    "shipping_region": shipping_region,
                    "order_status": order_status,
                    "payment_method": payment_method
                }
            }
            
            # Run the agent pipeline
            result = run_pipeline(ticket_input)
            
            st.success("Analysis Complete!")
            
            # Display Results
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🤖 Agent Decision")
                st.info(f"**Decision:** {result['decision'].upper()}")
                st.markdown("**Rationale:**")
                st.write(result['rationale'])
                
                st.markdown("**Proposed Customer Response:**")
                st.info(result['response'])
                
                st.markdown("**Next Steps (Internal):**")
                st.write(result['next_steps'])
                
            with col2:
                st.subheader("📚 Policy Citations")
                if result['citations']:
                    for citation in result['citations']:
                        st.markdown(f"- `{citation}`")
                else:
                    st.write("No specific policy citations provided.")
                    
                st.subheader("🛡️ Compliance Check")
                if result['unsupported_claims_flag']:
                    st.error("⚠️ The compliance agent flagged unsupported claims in the rationale/response.")
                else:
                    st.success("✅ The response passed the compliance check (100% policy-supported).")
            
            # Enable debugging view
            with st.expander("Show raw JSON output"):
                st.json(result)
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.code(import traceback; traceback.format_exc())
