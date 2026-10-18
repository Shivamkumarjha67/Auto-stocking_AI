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
    with col_btn2:
        if st.button("⏮️ Reset DB to Clean Demo State"):
            try:
                r = requests.post(f"{API_URL}/inventory/reset-db")
                if r.status_code == 200:
                    st.toast("Database reset to clean demo state!", icon="✨")
                    st.session_state.pop("batch_summary", None)
                    st.rerun()
                else:
                    st.error(f"Reset failed: {r.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

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
    st.header("Autonomous Replenishment Engine & Multi-Agent HITL")
    st.caption("Continuously scans warehouse stock, matches supplier contracts via RAG, enforces policy gates, executes autonomous purchase orders, and stages high-value replenishment for human review.")

    col_trig, col_reset, _ = st.columns([3, 2, 3])
    with col_trig:
        trigger_clicked = st.button("🚀 Run Continuous Autonomous Replenishment", type="primary", width="stretch")
    with col_reset:
        if st.button("⏮️ Reset Demo DB", width="stretch"):
            try:
                r = requests.post(f"{API_URL}/inventory/reset-db")
                if r.status_code == 200:
                    st.toast("Database reset to clean demo state!", icon="✨")
                    st.session_state.pop("batch_summary", None)
                    st.rerun()
                else:
                    st.error(f"Reset failed: {r.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

    if trigger_clicked:
        with st.spinner("Multi-agent cycle executing for all low-stock SKUs..."):
            try:
                run_res = requests.post(f"{API_URL}/trigger-replenishment")
                if run_res.status_code == 200:
                    summary = run_res.json()
                    st.session_state["batch_summary"] = summary
                    st.toast(f"Evaluated {summary.get('total_evaluated', 0)} SKU(s)!", icon="📦")
                else:
                    st.error(f"Agent execution failed: {run_res.text}")
            except Exception as e:
                st.error(f"Failed to connect to agent service: {e}")

    if "batch_summary" in st.session_state:
        b_sum = st.session_state["batch_summary"]
        st.info(f"ℹ️ **Latest Run Status:** {b_sum.get('message', 'Completed')}")

    # -----------------------------------------------------------------
    # SECTION 1: EXECUTED REPLENISHMENT TICKETS
    # -----------------------------------------------------------------
    st.markdown("---")
    st.subheader("🎟️ Executed Replenishment Tickets")
    st.caption("All purchase orders executed—either directly by autonomous agents (≤ $5,000) or authorized by human review—with complete contract agreement attributions.")

    try:
        t_res = requests.get(f"{API_URL}/tickets")
        tickets = t_res.json() if t_res.status_code == 200 else []
    except Exception:
        tickets = []

    if tickets:
        # High-level summary metrics
        total_tickets = len(tickets)
        total_spend = sum(float(t.get("total_amount", 0.0)) for t in tickets)
        direct_count = sum(1 for t in tickets if t.get("execution_type") == "DIRECT_AUTONOMOUS")
        hitl_count = total_tickets - direct_count

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Executed Orders", total_tickets)
        m2.metric("Total Committed Spend", f"${total_spend:,.2f}")
        m3.metric("⚡ Autonomous Direct", direct_count)
        m4.metric("🛡️ HITL Approved", hitl_count)

        st.write("")
        for ticket in tickets:
            with st.container(border=True):
                exec_type = ticket.get("execution_type", "DIRECT_AUTONOMOUS")
                is_auto = exec_type == "DIRECT_AUTONOMOUS"
                badge_color = "#28a745" if is_auto else "#007bff"
                badge_text = "⚡ DIRECT AUTONOMOUS EXECUTION" if is_auto else "🛡️ HITL MANAGER APPROVED"

                # Header with PO number and badge
                col_h1, col_h2 = st.columns([3, 2])
                with col_h1:
                    st.markdown(
                        f"#### 📄 `{ticket.get('po_number')}` &nbsp; "
                        f"<span style='background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;'>{badge_text}</span>",
                        unsafe_allow_html=True
                    )
                with col_h2:
                    st.caption(f"🕒 Executed: {ticket.get('executed_at')}")

                # Details row
                d1, d2, d3, d4 = st.columns(4)
                d1.write(f"**SKU:** `{ticket.get('sku')}`")
                d1.write(f"**Item:** {ticket.get('item_name')}")
                d2.write(f"**Category:** {ticket.get('category')}")
                d2.write(f"**Supplier:** {ticket.get('vendor_name')} (`{ticket.get('vendor_id')}`)")
                d3.write(f"**Quantity:** {ticket.get('order_quantity'):,} units")
                d3.write(f"**Unit Price:** ${ticket.get('unit_price', 0.0):.2f}")
                d4.write(f"**Total Amount:**")
                d4.markdown(f"### **${ticket.get('total_amount', 0.0):,.2f}**")

                # Agreement Attribution Box
                st.markdown("##### 📜 Agreement & Policy Terms Applied")
                agr_source = ticket.get("agreement_source") or "Contract on file"
                agr_terms = ticket.get("agreement_terms") or "Standard volume pricing tier"
                st.info(
                    f"**Contract Document:** `{agr_source}`\n\n"
                    f"**Applied Clauses & SLA:** {agr_terms}"
                )

                # Reasoning & Review Notes
                if ticket.get("reasoning"):
                    st.caption(f"🧠 **Agent Selection Rationale:** {ticket.get('reasoning')}")
                if ticket.get("reviewer_notes") and not is_auto:
                    st.caption(f"✍️ **Manager Review Notes:** {ticket.get('reviewer_notes')}")

                # Telemetry
                telem_raw = ticket.get("telemetry_json")
                if telem_raw:
                    try:
                        telem = json.loads(telem_raw) if isinstance(telem_raw, str) else telem_raw
                        t1, t2, t3 = st.columns(3)
                        t1.caption(f"⚡ Latency: {telem.get('execution_time_ms', 0):.0f}ms")
                        t2.caption(f"🪙 Tokens: {telem.get('total_tokens', 0)}")
                        t3.caption(f"💵 LLM Cost: ${telem.get('estimated_cost_usd', 0.0):.5f}")
                    except Exception:
                        pass
    else:
        st.info("No replenishment tickets executed yet. Click 'Run Continuous Autonomous Replenishment' above to evaluate stock and execute orders.")

    # -----------------------------------------------------------------
    # SECTION 2: HUMAN-IN-THE-LOOP REVIEW QUEUE (SEQUENTIAL APPROVAL)
    # -----------------------------------------------------------------
    st.markdown("---")
    st.subheader("🛡️ Human-in-the-Loop Review Queue")
    st.caption("Purchase orders exceeding autonomous policy limits (> $5,000) or requiring manual verification.")

    try:
        q_res = requests.get(f"{API_URL}/pending-reviews")
        queue_data = q_res.json().get("queue", []) if q_res.status_code == 200 else []
    except Exception:
        queue_data = []

    if queue_data:
        st.warning(f"⚠️ **{len(queue_data)} purchase order(s) awaiting managerial review.** Please evaluate and approve sequentially below:")

        active_review = queue_data[0]
        with st.container(border=True):
            st.markdown(f"### 🔍 Reviewing 1 of {len(queue_data)}: `{active_review['sku']}` ({active_review.get('item_name')})")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Target SKU", active_review.get("sku"))
            c2.metric("Urgency", active_review.get("urgency"))
            c3.metric("Selected Supplier", f"{active_review.get('vendor_name') or active_review.get('vendor_id')}")
            c4.metric("Proposed Total", f"${active_review.get('total_amount', 0.0):,.2f}")

            st.error(f"⚠️ **Policy Gate Reason:** {active_review.get('reasoning')}")

            # Agreement Details
            st.markdown("##### 📜 Agreement & Pricing Basis")
            st.info(
                f"**Contract Document:** `{active_review.get('agreement_source')}`\n\n"
                f"**Applied Clauses & SLA:** {active_review.get('agreement_terms')}"
            )

            # Decision controls
            col_qty, col_notes = st.columns([1, 2])
            with col_qty:
                override_qty = st.number_input(
                    "Override Quantity (0 = use drafted qty)",
                    min_value=0,
                    value=0,
                    step=1,
                    key=f"override_{active_review['sku']}"
                )
            with col_notes:
                notes = st.text_input(
                    "Manager Review Notes",
                    value="Approved critical replenishment after SLA verification.",
                    key=f"notes_{active_review['sku']}"
                )

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("✅ Approve PO & Execute Order", type="primary", key=f"app_{active_review['sku']}", width="stretch"):
                    approval_payload = {
                        "sku": active_review["sku"],
                        "approved": True,
                        "override_quantity": override_qty,
                        "reviewer_notes": notes
                    }
                    app_resp = requests.post(f"{API_URL}/approve-po", json=approval_payload)
                    if app_resp.status_code == 200:
                        st.success(f"PO for {active_review['sku']} approved! Stock replenished and ticket created.")
                        st.rerun()
                    else:
                        st.error(f"Approval failed: {app_resp.text}")

            with btn_col2:
                if st.button("❌ Reject PO", key=f"rej_{active_review['sku']}", width="stretch"):
                    rejection_payload = {
                        "sku": active_review["sku"],
                        "approved": False,
                        "override_quantity": 0,
                        "reviewer_notes": notes
                    }
                    rej_resp = requests.post(f"{API_URL}/approve-po", json=rejection_payload)
                    if rej_resp.status_code == 200:
                        st.info(f"PO for {active_review['sku']} rejected.")
                        st.rerun()
                    else:
                        st.error(f"Rejection failed: {rej_resp.text}")

        # If there are additional items in queue, show backlog expander
        if len(queue_data) > 1:
            with st.expander(f"📋 View remaining {len(queue_data) - 1} items waiting in queue"):
                st.dataframe(pd.DataFrame(queue_data[1:]), width="stretch", hide_index=True)
    else:
        st.success("✅ **HITL Queue Clear**: No purchase orders currently pending manual approval.")

    # -----------------------------------------------------------------
    # SECTION 3: WAREHOUSE REORDER MONITOR
    # -----------------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 Warehouse Low-Stock Monitor")
    st.caption("Live stock vs reorder thresholds to verify replenishment impact.")
    try:
        inv_res = requests.get(f"{API_URL}/inventory")
        if inv_res.status_code == 200:
            inv_data = inv_res.json()
            low_stock = [i for i in inv_data if i.get("urgency") in ["Critical", "Watch"]]
            if low_stock:
                st.dataframe(pd.DataFrame(low_stock), width="stretch", hide_index=True)
            else:
                st.write("🎉 All inventory SKUs currently have healthy stock levels above reorder thresholds.")
    except Exception:
        pass