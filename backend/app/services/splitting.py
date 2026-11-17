"""Expense splitting and debt simplification (like Splitwise)."""


def shares_for(amount: float, members: list[str], custom: dict[str, float] | None = None) -> dict[str, float]:
    if custom:
        total = sum(custom.values())
        if abs(total - amount) > 0.01:
            raise ValueError(f"Custom shares add up to {total}, not {amount}")
        return {k: round(v, 2) for k, v in custom.items()}
    each = round(amount / len(members), 2)
    shares = {m: each for m in members}
    # Put any rounding paisa on the first member so totals match exactly
    shares[members[0]] = round(amount - each * (len(members) - 1), 2)
    return shares


def balances(expenses: list[dict], settlements: list[dict] | None = None) -> dict[str, float]:
    """Positive = others owe this person. Negative = this person owes."""
    bal: dict[str, float] = {}
    for e in expenses:
        bal[e["paid_by"]] = bal.get(e["paid_by"], 0) + e["amount"]
        for user, share in e["shares"].items():
            bal[user] = bal.get(user, 0) - share
    for s in settlements or []:
        bal[s["from_user"]] = bal.get(s["from_user"], 0) + s["amount"]
        bal[s["to_user"]] = bal.get(s["to_user"], 0) - s["amount"]
    return {k: round(v, 2) for k, v in bal.items()}


def simplify(bal: dict[str, float]) -> list[dict]:
    """Greedy: biggest debtor pays biggest creditor. Gives at most n-1 payments."""
    creditors = sorted([[u, v] for u, v in bal.items() if v > 0.009], key=lambda x: -x[1])
    debtors = sorted([[u, -v] for u, v in bal.items() if v < -0.009], key=lambda x: -x[1])
    payments = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        pay = round(min(debtors[i][1], creditors[j][1]), 2)
        payments.append({"from_user": debtors[i][0], "to_user": creditors[j][0], "amount": pay})
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] < 0.01:
            i += 1
        if creditors[j][1] < 0.01:
            j += 1
    return payments
