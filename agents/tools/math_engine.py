from typing import Dict, Any

def calculate_restock_quantity(current_stock: int, daily_sales: float, target_buffer_days: int = 14) -> int:
    """Calculates units needed to restore the 14-day target safety buffer."""
    target_stock = daily_sales * target_buffer_days
    deficit = target_stock - current_stock
    return max(int(deficit), 0)

def compute_order_total(quantity: int, unit_price: float, expedite_surcharge: float = 0.0) -> float:
    """Computes total cost inclusive of applicable surcharges."""
    base_cost = quantity * unit_price
    total = base_cost * (1.0 + expedite_surcharge)
    return round(total, 2)