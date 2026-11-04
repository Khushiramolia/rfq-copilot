"""Compare parsed quotes and pick a supplier. Deterministic and explainable."""

WEIGHTS = {
    "balanced": (0.50, 0.30, 0.20),  # cost, speed, payment terms
    "cost": (0.70, 0.20, 0.10),
    "speed": (0.30, 0.55, 0.15),
}


def fmt_money(cur, v):
    return f"{cur}{v:,.0f}" if v >= 100 else f"{cur}{v:,.2f}"


def analyze(quotes: list, quantity: int, priority: str = "balanced") -> dict:
    w_cost, w_speed, w_pay = WEIGHTS.get(priority, WEIGHTS["balanced"])
    rows = []
    for q in quotes:
        r = dict(q)
        price = q.get("unit_price")
        r["total"] = price * quantity if price else None
        r["flags"] = []
        if not price:
            r["flags"].append("No price found - cannot be ranked")
        if q.get("delivery_days") is None:
            r["flags"].append("Delivery time not stated")
        if q.get("payment_days") is None:
            r["flags"].append("Payment terms not stated")
        if q.get("moq") and q["moq"] > quantity:
            r["flags"].append(f"MOQ {q['moq']:,} is above your quantity of {quantity:,}")
        rows.append(r)

    ranked = [r for r in rows if r["total"]]
    if not ranked:
        return {"rows": rows, "best": None, "summary": "No usable prices found in the quotes.", "email": ""}

    min_total = min(r["total"] for r in ranked)
    days = [r["delivery_days"] for r in ranked if r.get("delivery_days")]
    min_days = min(days) if days else None

    for r in rows:
        if not r["total"]:
            r["score"] = 0
            continue
        cost_s = min_total / r["total"] * 100
        speed_s = (min_days / r["delivery_days"] * 100) if (min_days and r.get("delivery_days")) else 40
        pay_s = (min(r["payment_days"], 60) / 60 * 100) if r.get("payment_days") is not None else 0
        score = w_cost * cost_s + w_speed * speed_s + w_pay * pay_s
        if q_moq_bad(r, quantity):
            score -= 15
        r["score"] = round(max(score, 0), 1)

    rows.sort(key=lambda r: r["score"], reverse=True)
    best = rows[0]
    cheapest = min(ranked, key=lambda r: r["total"])
    fastest = min((r for r in ranked if r.get("delivery_days")), key=lambda r: r["delivery_days"], default=None)
    cur = best.get("currency") or "₹"

    reasons = []
    if best is cheapest:
        reasons.append(f"lowest total cost ({fmt_money(cur, best['total'])} for {quantity:,} units)")
    else:
        extra = best["total"] - cheapest["total"]
        reasons.append(f"{fmt_money(cur, extra)} more than the cheapest option ({cheapest['supplier']})")
    if fastest is not None and best is fastest:
        reasons.append(f"fastest delivery ({best['delivery_days']} days)")
    elif best.get("delivery_days"):
        reasons.append(f"delivers in {best['delivery_days']} days")
    if best.get("payment_days"):
        reasons.append(f"Net {best['payment_days']} payment terms")
    elif best.get("payment_days") == 0:
        reasons.append("requires advance payment")

    summary = f"Recommended: {best['supplier']} (score {best['score']}/100) - " + "; ".join(reasons) + "."
    if cheapest is not best:
        summary += f" {cheapest['supplier']} is cheaper but scored lower on delivery or payment terms."
    if best["flags"]:
        summary += " Check before ordering: " + "; ".join(best["flags"]) + "."

    return {
        "rows": rows,
        "best": best["supplier"],
        "summary": summary,
        "email": draft_email(best, cheapest, quantity),
    }


def q_moq_bad(r, quantity):
    return bool(r.get("moq") and r["moq"] > quantity)


def draft_email(best, cheapest, quantity):
    cur = best.get("currency") or "₹"
    lines = [
        f"Subject: Quotation for {quantity:,} units - next steps",
        "",
        f"Dear {best['supplier']} team,",
        "",
        f"Thank you for your quotation of {fmt_money(cur, best['unit_price'])} per unit for {quantity:,} units.",
        "We are reviewing several offers and your proposal is among our top choices.",
    ]
    if cheapest is not best:
        lines.append(
            f"Another offer we received is priced at {fmt_money(cur, cheapest['unit_price'])} per unit. "
            "Could you review your pricing for this volume?"
        )
    else:
        lines.append("Could you share any volume discount available above this quantity?")
    asks = []
    if best.get("payment_days") is not None and best["payment_days"] < 45:
        asks.append("extended payment terms (Net 45 if possible)")
    if best.get("delivery_days") and best["delivery_days"] > 7:
        asks.append("whether delivery can be expedited")
    if best.get("moq") and best["moq"] > quantity:
        asks.append(f"flexibility on the minimum order quantity of {best['moq']:,}")
    if asks:
        lines.append("We would also like to confirm: " + ", and ".join(asks) + ".")
    lines += ["", "We hope to finalise the order shortly.", "", "Best regards,", "[Your name]", "[Company]"]
    return "\n".join(lines)
