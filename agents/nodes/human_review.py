from agents.state import ReplenishmentState

def human_review_node(state: ReplenishmentState) -> dict:
    """
    Acts as a policy enforcement gate and human approval checkpoint.
    Flags high-value purchase orders (> $5,000.00) or explicit escalations.
    """
    total = state.get("total_amount", 0.0)
    current_action = state.get("action_type", "pending_review")

    # Hard ceiling check from internal procurement policy ($5,000 max autonomous limit)
    if total > 5000.0 or current_action == "pending_review":
        return {
            "approval_granted": False,
            "action_type": "pending_review",
            "reasoning": (
                f"Autonomous spending limit breached (Total: ${total:,.2f} > $5,000.00). "
                "Order routed to Supply Chain Manager queue for manual review."
            )
        }
    
    if current_action == "reject_and_escalate":
        return {
            "approval_granted": False,
            "action_type": "reject_and_escalate",
            "reasoning": state.get("reasoning", "Order rejected due to policy or SLA non-compliance.")
        }

    # Autonomous execution approval
    return {
        "approval_granted": True,
        "action_type": "execute_po"
    }