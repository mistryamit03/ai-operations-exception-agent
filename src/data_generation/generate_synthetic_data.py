"""Generate the synthetic orders source table using Python 3.12's standard library."""

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


SEED = 42
ORDER_COUNT = 1_000
PERIOD_DAYS = 90
# Fixed UTC dates keep the dataset reproducible regardless of the execution date.
START_DATE = datetime(2026, 7, 4, tzinfo=timezone.utc)
END_DATE = START_DATE + timedelta(days=PERIOD_DAYS)
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data/generated/orders.csv"
FIELDNAMES = (
    "order_id",
    "customer_id",
    "order_date",
    "status",
    "gross_revenue",
    "product_cost",
    "shipping_cost",
    "payment_status",
)


def generate_orders() -> list[dict[str, str | float]]:
    """Return exactly 1,000 orders with one or more orders on every day."""
    rng = random.Random(SEED)
    orders = []

    for index in range(ORDER_COUNT):
        # The first 90 orders guarantee coverage of every calendar day.
        day_offset = index if index < PERIOD_DAYS else rng.randrange(PERIOD_DAYS)
        order_date = START_DATE + timedelta(
            days=day_offset, seconds=rng.randrange(24 * 60 * 60)
        )
        age_days = (END_DATE - order_date).total_seconds() / (24 * 60 * 60)

        # Recent orders are still progressing; older orders are mostly delivered.
        if rng.random() < 0.06:
            status = "cancelled"
        elif age_days < 1:
            status = rng.choices(
                ["created", "processing", "packed"], weights=[55, 35, 10]
            )[0]
        elif age_days < 3:
            status = rng.choices(
                ["processing", "packed", "shipped"], weights=[25, 35, 40]
            )[0]
        elif age_days < 7:
            status = rng.choices(["shipped", "delivered"], weights=[65, 35])[0]
        else:
            status = "delivered"

        # Fulfilled orders are paid; cancellations reflect payment or refund outcomes.
        if status == "cancelled":
            payment_status = rng.choices(
                ["failed", "refunded", "pending"], weights=[45, 45, 10]
            )[0]
        elif status == "created":
            payment_status = rng.choices(["pending", "paid"], weights=[75, 25])[0]
        elif status == "processing":
            payment_status = rng.choices(["paid", "pending"], weights=[95, 5])[0]
        else:
            payment_status = "paid"

        # Calculate in integer cents, then expose ordinary EUR numeric values.
        gross_cents = rng.randint(1_995, 29_995)
        product_cents = round(gross_cents * rng.uniform(0.40, 0.75))
        shipping_cents = rng.choice([349, 449, 549, 649, 799])
        # Baseline costs leave at least 15% margin; floor the cap to whole cents.
        max_product_cents = (gross_cents * 85) // 100 - shipping_cents
        product_cents = min(product_cents, max_product_cents)
        orders.append(
            {
                "order_id": f"ORD-{index + 1:06d}",
                "customer_id": f"CUS-{rng.randint(1, 600):05d}",
                "order_date": order_date.isoformat(sep=" "),
                "status": status,
                "gross_revenue": gross_cents / 100,
                "product_cost": product_cents / 100,
                "shipping_cost": shipping_cents / 100,
                "payment_status": payment_status,
            }
        )

    return orders


def main() -> None:
    orders = generate_orders()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for order in orders:
            # CSV uses decimal points and two places, without currency symbols.
            row = order.copy()
            for column in ("gross_revenue", "product_cost", "shipping_cost"):
                row[column] = f"{order[column]:.2f}"
            writer.writerow(row)
    print(f"Generated {len(orders)} orders at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
