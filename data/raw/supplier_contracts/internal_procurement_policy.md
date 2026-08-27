# AutoStock-AI Internal Procurement Policy

**Document Type:** Internal Procurement Policy & Governance Rules
**Applies To:** All autonomous and manual purchase order (PO) activity across contracted vendors VEND-001 (TechCorp Logistics), VEND-002 (GlobalParts Direct), and VEND-003 (Apex Supply Co.)
**Owner:** Supply Chain & Procurement Operations
**Policy Status:** Active

---

## 1. Purpose

This document defines the internal governance rules that constrain and guide the AutoStock-AI autonomous replenishment agent when evaluating supplier proposals, generating purchase orders, negotiating terms, and escalating exceptions. All autonomous purchasing actions must comply with the thresholds and rules defined below. Any action that would violate a hard constraint in this policy must be routed to `reject_and_escalate` or `clarify_ambiguity` rather than executed directly.

---

## 2. Autonomous Purchase Order Authority Limit

- **Maximum Autonomous PO Value:** **$5,000.00** per single purchase order, calculated as the full `total_amount` across all line items on that PO.
- Purchase orders with a calculated `total_amount` **at or below $5,000.00** may be executed autonomously by the replenishment agent without manager sign-off, provided all other policy conditions in this document are satisfied.
- Purchase orders with a calculated `total_amount` **above $5,000.00** require **manager approval** before execution. The agent must set PO status to `pending_review` and generate an escalation summary rather than finalizing the order.
- This limit applies per PO, not per SKU or per vendor. Splitting a single replenishment need across multiple POs to circumvent this limit is prohibited and is itself an escalation trigger if detected.

---

## 3. Target Safety Stock Buffer

- **Target Safety Stock Buffer:** **14 days** of coverage at current daily sales velocity, for all SKUs across both the Electronics category (SKU-1001–SKU-1005) and Hardware category (SKU-2001–SKU-2005).
- Safety stock buffer is calculated as: `Current Stock (units) / Daily Sales Velocity (units/day) = Runway (days)`.
- **Runway Classification:**
  - **Critical:** Runway under 3 days — immediate action required; prioritize fastest available vendor (typically VEND-001) or negotiate a split/expedited order regardless of price premium, within the autonomous PO limit.
  - **Watch:** Runway between 3 and 14 days — standard replenishment order should be placed against the lowest total-cost vendor whose lead time fits within the remaining runway.
  - **Healthy:** Runway at or above 14 days — no immediate action required; may defer to next scheduled review cycle or route to bulk vendor (VEND-002) for cost optimization.
- Replenishment orders should be sized to restore the 14-day target buffer, not merely to prevent an immediate stockout.

---

## 4. Preferred Payment Terms

- The agent should favor vendor proposals that align with the following preferred payment terms ranking, from most to least preferred, when multiple vendors offer comparable pricing and lead time for the same SKU:
  1. **2/10 Net 60** (early payment discount available) — currently offered by VEND-002 (GlobalParts Direct)
  2. **Net 45** — currently offered by VEND-003 (Apex Supply Co.)
  3. **Net 30** — currently offered by VEND-001 (TechCorp Logistics)
- Payment term preference is a **secondary factor** and must not override primary decision criteria (stockout runway, price ceiling compliance, and vendor reliability threshold in Sections 5 and 6). Payment terms are used only as a tie-breaker between otherwise comparable vendor options.
- Any vendor proposal requiring payment terms shorter than Net 30 or requiring pre-payment in full (100% deposit) must be flagged via `clarify_ambiguity` or `reject_and_escalate` for manual review, as this falls outside standard contracted terms for all three approved vendors.

---

## 5. Mandatory Multi-Quote Evaluation Rules

- **Threshold for Mandatory Multi-Quote:** Any planned (non-critical) replenishment order with an estimated `total_amount` **above $1,500.00** must be evaluated against **at least two of the three approved vendors** (VEND-001, VEND-002, VEND-003) before an autonomous purchase decision is finalized, where the requested SKU is available from more than one contracted vendor.
- **Critical Runway Exception:** Orders classified as **Critical** (runway under 3 days, per Section 3) are exempt from the multi-quote requirement and may proceed with the single fastest-available vendor to prevent stockout, even above the $1,500.00 threshold.
- **Single-Source SKUs:** SKUs contracted with only one vendor (e.g., SKU-1001–SKU-1005 are available from both VEND-001 and VEND-002 but not VEND-003; SKU-2001–SKU-2005 are available from VEND-002 and VEND-003 but not VEND-001) are exempt from the multi-quote requirement when only one contracted vendor carries that SKU at the required volume tier.
- **Documentation Requirement:** When multiple quotes are evaluated, the agent's `reasoning` field must explicitly compare total landed cost (unit price × quantity, inclusive of any expedite fees) and lead time across the evaluated vendors, and state the basis for the final vendor selection.

---

## 6. Vendor Reliability Threshold

- **Minimum Acceptable Reliability Score:** **6.0 / 10**, based on each vendor's trailing 12-month internal reliability score (on-time delivery rate, order accuracy, defect rate).
- Current reliability scores on file:
  - VEND-001 (TechCorp Logistics): 8.7 / 10
  - VEND-002 (GlobalParts Direct): 6.4 / 10
  - VEND-003 (Apex Supply Co.): 7.5 / 10
- Any vendor whose reliability score falls **below 6.0 / 10** at time of evaluation must not receive an autonomous purchase order regardless of price or lead time advantage; the proposal must be routed to `reject_and_escalate` with secondary vendor routing flagged.

---

## 7. Unit Price Ceiling Enforcement

- Each SKU carries a contracted unit price ceiling derived from the applicable vendor's Master Pricing & SLA Schedule (see `vendor_techcorp_pricing_sla.md`, `vendor_globalparts_pricing_sla.md`, and `vendor_apex_pricing_sla.md`).
- Any supplier quote **exceeding the contracted tiered price ceiling** for the corresponding SKU and volume tier must not be accepted directly. The agent must first attempt `negotiate_counter` where a split or reduced-quantity order can bring the effective cost within ceiling; if no such path exists, the proposal must be routed to `reject_and_escalate`.
- Quotes that are **below** the contracted ceiling (e.g., a promotional or one-time discount) may be accepted directly provided all other conditions in this policy are met.

---

## 8. Lead Time vs. Runway Enforcement

- A supplier's quoted lead time must not exceed the current stockout runway for the affected SKU (Section 3) unless a split/expedited partial order is used to bridge the coverage gap.
- If no combination of available vendors and expedite options can close the coverage gap before stockout, the agent must route the case to `reject_and_escalate` with an explicit note that stockout is unavoidable under current vendor terms, so the escalation reviewer can consider emergency spot-market sourcing outside the approved vendor list.

---

## 9. Escalation & Review Cadence

- All `reject_and_escalate` and `pending_review` (>$5,000) actions generate an escalation summary routed to the Supply Chain Manager queue for same-business-day review.
- Vendor reliability scores (Section 6) are reviewed and updated on a **quarterly** cadence, or immediately following three or more late-delivery incidents from a single vendor within a rolling 90-day period.
- This policy document is reviewed **semi-annually** or upon renegotiation of any vendor's Master Pricing & SLA Schedule.
