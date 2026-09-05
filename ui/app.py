import os
import streamlit as st
import requests
import json
import pandas as pd

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="AutoStock-AI | Autonomous Procurement Hub",
    page_icon="📦",
    layout="wide"
)

st.title("📦 AutoStock-AI: Autonomous Procurement Hub")
st.markdown("Automated Inventory Monitoring, RAG-Driven Contract Sizing, and Policy-Gated Replenishment.")

tab1, tab2, tab3 = st.tabs([
    "📋 Inventory Hub (JSON / DB)",
    "📚 Knowledge Base (RAG Ingestion)",
    "🤖 Agent Console & HITL"
])

# =====================================================================
# TAB 1: INVENTORY MANAGEMENT
# =====================================================================
with tab1:
    st.header("Warehouse Inventory Manager")
    st.caption("Inspect live inventory, adjust stock, or upload a custom JSON dataset to simulate stockouts.")

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        refresh_stock = st.button("🔄 Refresh Live Inventory")

    try:
        res = requests.get(f"{API_URL}/inventory")
        if res.status_code == 200:
            current_inv = res.json()
            df_inv = pd.DataFrame(current_inv)
            
            st.dataframe(
                df_inv.style.map(
                    lambda v: 'background-color: #ffcccc; color: #990000; font-weight: bold;' if v == 'Critical'
                    else ('background-color: #fff2cc; color: #8a6d3b;' if v == 'Watch' else ''),
                    subset=['urgency']
                ) if not df_inv.empty else df_inv,
                width="stretch",
                hide_index=True
            )
        else:
            st.error("Failed to load inventory from backend.")
    except Exception as e:
        st.error(f"Cannot reach FastAPI backend at {API_URL}. Ensure it is running. Error: {e}")

    st.markdown("---")
    st.subheader("Load Custom Inventory via JSON")

    default_sample = [
        {
            "sku": "SKU-1003",
            "item_name": "Lithium-Ion Battery Pack",
            "category": "Electronics",
            "current_stock": 9,
            "reorder_point": 25,
            "daily_sales_rate": 5.0,
            "unit_holding_cost": 2.5
        },
        {
            "sku": "SKU-2001",
            "item_name": "Hydraulic Seal Ring",
            "category": "Hardware",
            "current_stock": 45,
            "reorder_point": 40,
            "daily_sales_rate": 2.0,
            "unit_holding_cost": 0.8
        },
        {
            "sku": "SKU-1001",
            "item_name": "Microcontroller Unit MCU-32",
            "category": "Electronics",
            "current_stock": 150,
            "reorder_point": 50,
            "daily_sales_rate": 4.0,
            "unit_holding_cost": 1.2
        }
    ]

    json_input = st.text_area(
        "Paste Custom Inventory JSON Array:",
        value=json.dumps(default_sample, indent=2),
        height=220
    )

    if st.button("📥 Sync Custom JSON to Warehouse DB", type="primary"):
        try:
            parsed = json.loads(json_input)
            sync_res = requests.post(f"{API_URL}/inventory/load-json", json=parsed)
            if sync_res.status_code == 200:
                st.success(f"Successfully loaded {len(parsed)} items into the active warehouse database!")
                st.rerun()
            else:
                st.error(f"Sync failed: {sync_res.text}")
        except json.JSONDecodeError as err:
            st.error(f"Invalid JSON format: {err}")

# =====================================================================
# TAB 2: KNOWLEDGE BASE INGESTION (RAG)
# =====================================================================
with tab2:
    st.header("Supplier Contracts & Governance Knowledge Base")
    st.caption("Ingest, categorize, and inspect documents driving autonomous supplier matching and policy enforcement.")

    col_form, col_view = st.columns([1, 1], gap="large")

    with col_form:
        st.subheader("📤 Document Upload & Ingestion")

        doc_type = st.selectbox(
            "Document Category",
            [
                "Vendor Pricing Sheet & MOQ Schedule",
                "Vendor Master Service Agreement (MSA/SLA)",
                "Internal Corporate Procurement Policy",
                "Emergency Supplier Addendum"
            ]
        )

        vendor_scope = st.selectbox(
            "Associated Vendor",
            ["Global / All Vendors", "VEND-001 (TechCorp)", "VEND-002 (GlobalParts)", "VEND-003 (Apex Logistics)"]
        )

        uploaded_files = st.file_uploader(
            "Choose PDF or Markdown files",
            type=["pdf", "md"],
            accept_multiple_files=True
        )

        if st.button("⚡ Ingest & Index Document(s)", type="primary", width="stretch"):
            if uploaded_files:
                progress = st.progress(0)
                status_text = st.empty()
                for idx, file in enumerate(uploaded_files):
                    status_text.text(f"Processing and embedding: {file.name}...")
                    files = {"file": (file.name, file.getvalue(), "application/octet-stream")}
                    res = requests.post(f"{API_URL}/rag/upload-document", files=files)
                    if res.status_code != 200:
                        st.error(f"Failed to ingest {file.name}: {res.text}")
                        break
                    progress.progress((idx + 1) / len(uploaded_files))

                status_text.empty()
                st.success("Successfully processed and indexed into ChromaDB & BM25!")
            else:
                st.warning("Please select at least one document to upload.")

    with col_view:
        st.subheader("📑 Currently Indexed Knowledge Base")
        contracts_dir = "data/raw/supplier_contracts"
        if os.path.exists(contracts_dir):
            files_on_disk = [
                f for f in os.listdir(contracts_dir)
                if f.endswith(".pdf") or f.endswith(".md")
            ]
            
            docs_summary = []
            for f in files_on_disk:
                path = os.path.join(contracts_dir, f)
                size_kb = round(os.path.getsize(path) / 1024, 1)
                
                if "policy" in f.lower():
                    cat = "Internal Policy"
                elif "pricing" in f.lower() or "sla" in f.lower():
                    cat = "Vendor Pricing / SLA"
                elif "msa" in f.lower():
                    cat = "Master Agreement"
                else:
                    cat = "General Reference"
                
                docs_summary.append({
                    "Document Name": f,
                    "Category": cat,
                    "File Size (KB)": f"{size_kb} KB"
                })
            
            if docs_summary:
                st.dataframe(pd.DataFrame(docs_summary), hide_index=True, width="stretch")
            else:
                st.info("No documents found in data/raw/supplier_contracts.")
        else:
            st.info("Contracts directory not created yet.")

# =====================================================================
# TAB 3: AUTONOMOUS REPLENISHMENT & HITL CONSOLE
# =====================================================================
with tab3:
    st.header("Autonomous Replenishment Engine")
    st.caption("Run the multi-agent decision loop: SQL Scan ➔ RAG Contract Matching ➔ vLLM PO Reasoning ➔ Gatekeeper.")

    col_trig, _ = st.columns([2, 5])
    with col_trig:
        trigger_clicked = st.button("🚀 Trigger Autonomous Replenishment", type="primary", width="stretch")

    if trigger_clicked:
        with st.spinner("Multi-agent cycle executing (scanning stock, evaluating contracts, generating PO)..."):
            try:
                run_res = requests.post(f"{API_URL}/trigger-replenishment")
                if run_res.status_code == 200:
                    st.session_state["agent_result"] = run_res.json()
                else:
                    st.error(f"Agent execution failed: {run_res.text}")
            except Exception as e:
                st.error(f"Failed to connect to agent service: {e}")

    # Display Active Evaluation
    if "agent_result" in st.session_state and st.session_state["agent_result"]:
        res_data = st.session_state["agent_result"]
        
        if res_data.get("action_type") == "no_action_needed":
            st.success(f"✅ {res_data.get('reasoning')}")
        else:
            st.markdown("### 📊 Active Item Under Evaluation")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Target SKU", res_data.get("active_sku"))
            c2.metric("Urgency", res_data.get("urgency"))
            c3.metric("Selected Vendor", res_data.get("vendor_id"))
            c4.metric("Total Order Amount", f"${res_data.get('total_amount', 0.0):,.2f}")

            st.info(f"**Agent Reasoning:** {res_data.get('reasoning')}")

            # Human Review Decision Form
            if res_data.get("action_type") == "pending_review":
                st.warning("⚠️ **Human-in-the-Loop Policy Gate Triggered**: Order exceeds autonomous limits or requires confirmation.")
                
                with st.expander("📝 Review & Sign Off Purchase Order", expanded=True):
                    st.json(res_data.get("po_draft"))

                    col_qty, col_notes = st.columns([1, 2])
                    with col_qty:
                        override_qty = st.number_input(
                            "Override Quantity (0 = use drafted qty)",
                            min_value=0,
                            value=0,
                            step=1
                        )
                    with col_notes:
                        notes = st.text_input("Manager Review Notes", value="Approved critical replenishment.")

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("✅ Approve & Process Next SKU", type="primary", width="stretch"):
                            approval_payload = {
                                "sku": res_data["active_sku"],
                                "approved": True,
                                "override_quantity": override_qty,
                                "reviewer_notes": notes
                            }
                            app_resp = requests.post(f"{API_URL}/approve-po", json=approval_payload)
                            if app_resp.status_code == 200:
                                # Advance to the next SKU immediately
                                next_run = requests.post(f"{API_URL}/trigger-replenishment")
                                if next_run.status_code == 200:
                                    st.session_state["agent_result"] = next_run.json()
                                else:
                                    st.session_state.pop("agent_result", None)
                                st.rerun()
                            else:
                                st.error(f"Approval failed: {app_resp.text}")
                    
                    with btn_col2:
                        if st.button("❌ Reject & Process Next SKU", width="stretch"):
                            rejection_payload = {
                                "sku": res_data["active_sku"],
                                "approved": False,
                                "override_quantity": 0,
                                "reviewer_notes": notes
                            }
                            rej_resp = requests.post(f"{API_URL}/approve-po", json=rejection_payload)
                            if rej_resp.status_code == 200:
                                # Advance to the next SKU immediately
                                next_run = requests.post(f"{API_URL}/trigger-replenishment")
                                if next_run.status_code == 200:
                                    st.session_state["agent_result"] = next_run.json()
                                else:
                                    st.session_state.pop("agent_result", None)
                                st.rerun()
                            else:
                                st.error(f"Rejection failed: {rej_resp.text}")
            else:
                st.success("✅ **Autonomous PO Executed**: Order within policy thresholds; transmitted directly to supplier.")
                with st.expander("View Executed PO Details"):
                    st.json(res_data.get("po_draft"))

    # Backlog Section
    st.markdown("---")
    st.subheader("📋 Pending Human Review Backlog")
    try:
        q_res = requests.get(f"{API_URL}/pending-reviews")
        if q_res.status_code == 200:
            queue_data = q_res.json().get("queue", [])
            if queue_data:
                st.dataframe(pd.DataFrame(queue_data), width="stretch", hide_index=True)
            else:
                st.write("No purchase orders currently pending approval.")
    except Exception:
        pass