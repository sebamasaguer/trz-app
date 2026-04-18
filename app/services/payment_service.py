from typing import Iterable

from ..models import CashPaymentStatus


def money(v) -> float:
    return float(v or 0)


def summarize_payment_rows(rows: Iterable) -> dict:
    total_amount = 0.0
    accredited_total = 0.0
    pending_total = 0.0

    for row in rows:
        amount = money(getattr(row, "amount", 0))
        total_amount += amount

        status = getattr(row, "status", None)
        status_value = status.value if hasattr(status, "value") else str(status) if status else ""

        if status_value == CashPaymentStatus.ACREDITADO.value:
            accredited_total += amount
        elif status_value == CashPaymentStatus.PENDIENTE.value:
            pending_total += amount

    return {
        "total_amount": total_amount,
        "accredited_total": accredited_total,
        "pending_total": pending_total,
    }