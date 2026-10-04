"""Generate the complete synthetic source dataset for the AI operations exception agent.

Python 3.12 standard library only.

The generator creates a clean baseline, injects four known exception types
deterministically, writes ground-truth labels separately, and validates that the
deterministic rules recover exactly the injected cases.
"""

from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


SEED = 42
ORDER_COUNT = 1_000
PERIOD_DAYS = 90
SKU_COUNT = 150
WAREHOUSE_ID = "WH-BER-01"

START_DATE = datetime(2026, 7, 4, tzinfo=timezone.utc)
END_DATE = START_DATE + timedelta(days=PERIOD_DAYS)
EVALUATION_TIME = END_DATE

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "generated"

ORDERS_FIELDS = (
    "order_id",
    "customer_id",
    "order_date",
    "status",
    "gross_revenue",
    "product_cost",
    "shipping_cost",
    "payment_status",
)

ORDER_ITEMS_FIELDS = (
    "order_item_id",
    "order_id",
    "sku",
    "quantity",
    "unit_price",
    "unit_product_cost",
)

SHIPMENTS_FIELDS = (
    "shipment_id",
    "order_id",
    "carrier",
    "shipped_at",
    "expected_delivery_at",
    "delivered_at",
    "shipment_status",
)

SHIPMENT_EVENTS_FIELDS = (
    "event_id",
    "shipment_id",
    "order_id",
    "event_type",
    "event_at",
    "event_sequence",
)

INVENTORY_FIELDS = (
    "sku",
    "warehouse_id",
    "available_quantity",
    "reserved_quantity",
    "updated_at",
)

BILLING_FIELDS = (
    "order_id",
    "billed_amount",
    "expected_amount",
    "invoice_status",
    "updated_at",
)

GROUND_TRUTH_FIELDS = (
    "order_id",
    "expected_exception_type",
    "expected_root_cause",
    "expected_escalation",
    "scenario_notes",
)

ALLOWED_ORDER_STATUSES = {
    "created",
    "processing",
    "packed",
    "shipped",
    "delivered",
    "cancelled",
}

ALLOWED_PAYMENT_STATUSES = {"paid", "pending", "refunded", "failed"}

ALLOWED_SHIPMENT_STATUSES = {
    "label_created",
    "carrier_accepted",
    "in_transit",
    "out_for_delivery",
    "delivered",
    "exception",
}

ALLOWED_EVENT_TYPES = {
    "LABEL_CREATED",
    "CARRIER_ACCEPTED",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "EXCEPTION",
}

ALLOWED_INVOICE_STATUSES = {"pending", "issued", "corrected", "cancelled"}


def money_to_cents(value: str | int | float | Decimal) -> int:
    """Convert a monetary value to exact integer cents."""
    amount = Decimal(str(value))
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_decimal(cents: int) -> Decimal:
    """Convert integer cents to a two-decimal Decimal."""
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def parse_datetime(value: str | datetime) -> datetime:
    """Return an offset-aware datetime from a generated value."""
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def format_datetime(value: datetime | None) -> str:
    """Format datetimes consistently for CSV output."""
    if value is None:
        return ""
    return value.isoformat(sep=" ")


def generate_orders() -> list[dict[str, str | float]]:
    """Generate exactly 1,000 baseline orders with healthy margins."""
    rng = random.Random(SEED)
    orders: list[dict[str, str | float]] = []

    for index in range(ORDER_COUNT):
        # First 90 orders guarantee at least one order on every dataset day.
        day_offset = index if index < PERIOD_DAYS else rng.randrange(PERIOD_DAYS)
        order_date = START_DATE + timedelta(
            days=day_offset,
            seconds=rng.randrange(24 * 60 * 60),
        )
        age_days = (END_DATE - order_date).total_seconds() / (24 * 60 * 60)

        if rng.random() < 0.06:
            status = "cancelled"
        elif age_days < 1:
            status = rng.choices(
                ["created", "processing", "packed"],
                weights=[55, 35, 10],
            )[0]
        elif age_days < 3:
            status = rng.choices(
                ["processing", "packed", "shipped"],
                weights=[25, 35, 40],
            )[0]
        elif age_days < 7:
            status = rng.choices(
                ["shipped", "delivered"],
                weights=[65, 35],
            )[0]
        else:
            status = "delivered"

        if status == "cancelled":
            payment_status = rng.choices(
                ["failed", "refunded", "pending"],
                weights=[45, 45, 10],
            )[0]
        elif status == "created":
            payment_status = rng.choices(
                ["pending", "paid"],
                weights=[75, 25],
            )[0]
        elif status == "processing":
            payment_status = rng.choices(
                ["paid", "pending"],
                weights=[95, 5],
            )[0]
        else:
            payment_status = "paid"

        gross_cents = rng.randint(1_995, 29_995)
        product_cents = round(gross_cents * rng.uniform(0.40, 0.75))
        shipping_cents = rng.choice([349, 449, 549, 649, 799])

        # Baseline rows stay at or above a 15% order margin.
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


def allocate_unit_cents(
    total_cents: int,
    quantities: list[int],
    rng: random.Random,
) -> list[int]:
    """Split an exact total into positive per-unit cent amounts."""
    remaining_cents = total_cents
    unit_amounts: list[int] = []

    for index, quantity in enumerate(quantities):
        if index == len(quantities) - 1:
            unit_cents = remaining_cents // quantity
        else:
            future_quantities = sum(quantities[index + 1 :])
            max_unit_cents = (remaining_cents - future_quantities) // quantity
            average_unit_cents = remaining_cents // (quantity + future_quantities)
            unit_cents = rng.randint(
                max(1, average_unit_cents // 2),
                min(max_unit_cents, max(1, average_unit_cents * 3 // 2)),
            )

        unit_amounts.append(unit_cents)
        remaining_cents -= unit_cents * quantity

    return unit_amounts


def generate_order_items(
    orders: list[dict[str, str | float]],
) -> list[dict[str, str | int | Decimal]]:
    """Generate 1-3 distinct SKU lines per order with exact financial totals."""
    rng = random.Random(SEED)
    order_items: list[dict[str, str | int | Decimal]] = []

    for order in orders:
        gross_cents = money_to_cents(order["gross_revenue"])
        product_cents = money_to_cents(order["product_cost"])
        item_count = rng.randint(1, 3)
        skus = rng.sample(range(1, SKU_COUNT + 1), item_count)

        if item_count == 1:
            valid_quantities = [
                quantity
                for quantity in range(1, 4)
                if gross_cents % quantity == 0
                and product_cents % quantity == 0
            ]
            quantities = [rng.choice(valid_quantities)]
        else:
            # Quantity one on the final line absorbs any remaining cents exactly.
            quantities = [
                rng.randint(1, 3)
                for _ in range(item_count - 1)
            ] + [1]

        unit_prices = allocate_unit_cents(gross_cents, quantities, rng)
        unit_costs = allocate_unit_cents(product_cents, quantities, rng)

        order_number = str(order["order_id"]).removeprefix("ORD-")

        for line_index, sku in enumerate(skus):
            order_items.append(
                {
                    "order_item_id": f"OI-{order_number}-{line_index + 1:02d}",
                    "order_id": order["order_id"],
                    "sku": f"SKU-{sku:04d}",
                    "quantity": quantities[line_index],
                    "unit_price": cents_to_decimal(unit_prices[line_index]),
                    "unit_product_cost": cents_to_decimal(
                        unit_costs[line_index]
                    ),
                }
            )

    return order_items


def choose_exception_cases(
    orders: list[dict[str, str | float]],
    order_items: list[dict[str, str | int | Decimal]],
) -> dict[str, set[str]]:
    """Choose deterministic exception cases with controlled overlaps."""
    rng = random.Random(SEED + 1_000)

    items_by_order: dict[str, list[dict[str, str | int | Decimal]]] = defaultdict(list)
    for item in order_items:
        items_by_order[str(item["order_id"])].append(item)

    shipped_ids = [
        str(order["order_id"])
        for order in orders
        if order["status"] == "shipped"
    ]

    if len(shipped_ids) < 35:
        raise ValueError("Not enough shipped orders to inject logistics exceptions.")

    delayed = set(rng.sample(shipped_ids, 20))
    missing_overlap = set(rng.sample(sorted(delayed), 5))
    remaining_shipped = [
        order_id
        for order_id in shipped_ids
        if order_id not in delayed
    ]
    missing = missing_overlap | set(rng.sample(remaining_shipped, 15))
    logistics_union = delayed | missing

    low_margin_eligible: list[str] = []
    for order in orders:
        order_id = str(order["order_id"])
        item_rows = items_by_order[order_id]
        single_line_is_divisible = (
            len(item_rows) > 1
            or int(item_rows[0]["quantity"]) == 1
        )
        if (
            order["status"] != "cancelled"
            and order["payment_status"] == "paid"
            and single_line_is_divisible
        ):
            low_margin_eligible.append(order_id)

    logistics_low_candidates = sorted(
        logistics_union & set(low_margin_eligible)
    )
    low_logistics_overlap = set(
        rng.sample(logistics_low_candidates, 5)
    )

    non_logistics_low_candidates = [
        order_id
        for order_id in low_margin_eligible
        if order_id not in logistics_union
    ]
    low_extra = set(rng.sample(non_logistics_low_candidates, 75))
    low_margin = low_logistics_overlap | low_extra

    low_billing_overlap = set(rng.sample(sorted(low_extra), 10))

    billing_candidates = [
        str(order["order_id"])
        for order in orders
        if order["status"] != "cancelled"
        and order["payment_status"] == "paid"
        and str(order["order_id"]) not in logistics_union
        and str(order["order_id"]) not in low_margin
    ]
    billing_extra = set(rng.sample(billing_candidates, 70))
    billing_mismatch = low_billing_overlap | billing_extra

    all_exception_orders = (
        logistics_union
        | low_margin
        | billing_mismatch
    )

    if len(all_exception_orders) != 180:
        raise AssertionError(
            "Expected exactly 180 unique exception orders."
        )

    return {
        "DELAYED_SHIPMENT": delayed,
        "MISSING_CARRIER_EVENT": missing,
        "LOW_MARGIN": low_margin,
        "BILLING_MISMATCH": billing_mismatch,
    }


def inject_low_margin_exceptions(
    orders: list[dict[str, str | float]],
    order_items: list[dict[str, str | int | Decimal]],
    low_margin_ids: set[str],
) -> None:
    """Raise product cost for known orders so margin falls below 5%."""
    rng = random.Random(SEED + 2_000)
    orders_by_id = {
        str(order["order_id"]): order
        for order in orders
    }
    items_by_order: dict[str, list[dict[str, str | int | Decimal]]] = defaultdict(list)

    for item in order_items:
        items_by_order[str(item["order_id"])].append(item)

    for order_id in sorted(low_margin_ids):
        order = orders_by_id[order_id]
        gross_cents = money_to_cents(order["gross_revenue"])
        shipping_cents = money_to_cents(order["shipping_cost"])

        target_margin_pct = rng.choice(
            [
                Decimal("0.01"),
                Decimal("0.02"),
                Decimal("0.03"),
                Decimal("0.04"),
            ]
        )
        margin_cents = max(
            1,
            int(
                (Decimal(gross_cents) * target_margin_pct).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            ),
        )
        new_product_cents = (
            gross_cents
            - shipping_cents
            - margin_cents
        )

        if new_product_cents <= 0:
            raise AssertionError(
                f"Invalid injected product cost for {order_id}."
            )

        order["product_cost"] = new_product_cents / 100

        item_rows = items_by_order[order_id]
        quantities = [
            int(item["quantity"])
            for item in item_rows
        ]
        allocated_costs = allocate_unit_cents(
            new_product_cents,
            quantities,
            rng,
        )

        for item, unit_cost_cents in zip(
            item_rows,
            allocated_costs,
            strict=True,
        ):
            item["unit_product_cost"] = cents_to_decimal(
                unit_cost_cents
            )


def generate_shipments_and_events(
    orders: list[dict[str, str | float]],
    exceptions: dict[str, set[str]],
) -> tuple[
    list[dict[str, str | datetime | None]],
    list[dict[str, str | int | datetime]],
    dict[tuple[str, str], str],
]:
    """Generate one shipment per order and an event timeline for each shipment."""
    rng = random.Random(SEED + 3_000)
    delayed_ids = exceptions["DELAYED_SHIPMENT"]
    missing_ids = exceptions["MISSING_CARRIER_EVENT"]

    shipments: list[dict[str, str | datetime | None]] = []
    shipment_events: list[dict[str, str | int | datetime]] = []
    root_causes: dict[tuple[str, str], str] = {}

    def add_event(
        shipment_id: str,
        order_id: str,
        event_type: str,
        event_at: datetime,
        sequence: int,
    ) -> None:
        shipment_events.append(
            {
                "event_id": f"EVT-{len(shipment_events) + 1:07d}",
                "shipment_id": shipment_id,
                "order_id": order_id,
                "event_type": event_type,
                "event_at": event_at,
                "event_sequence": sequence,
            }
        )

    for order in orders:
        order_id = str(order["order_id"])
        order_number = order_id.removeprefix("ORD-")
        shipment_id = f"SHP-{order_number}"
        order_date = parse_datetime(str(order["order_date"]))
        carrier = rng.choice(["DHL", "GLS"])

        shipped_at: datetime | None = None
        expected_delivery_at: datetime | None = None
        delivered_at: datetime | None = None
        shipment_status: str
        timeline: list[tuple[str, datetime]] = []

        status = str(order["status"])

        if status == "cancelled":
            shipment_status = "exception"
            event_at = min(
                order_date + timedelta(hours=2),
                EVALUATION_TIME - timedelta(minutes=1),
            )
            timeline = [("EXCEPTION", event_at)]

        elif status == "created":
            shipment_status = "label_created"
            label_at = min(
                order_date + timedelta(hours=1),
                EVALUATION_TIME - timedelta(minutes=1),
            )
            timeline = [("LABEL_CREATED", label_at)]

        elif status in {"processing", "packed"}:
            shipment_status = "label_created"
            recent_label = (
                EVALUATION_TIME
                - timedelta(hours=rng.randint(2, 20))
            )
            label_at = max(
                order_date + timedelta(hours=1),
                recent_label,
            )
            label_at = min(
                label_at,
                EVALUATION_TIME - timedelta(minutes=1),
            )
            timeline = [("LABEL_CREATED", label_at)]

        elif status == "shipped":
            if order_id in missing_ids:
                label_at = min(
                    order_date + timedelta(hours=4),
                    EVALUATION_TIME - timedelta(hours=36),
                )
                shipped_at = label_at + timedelta(hours=2)
                timeline = [("LABEL_CREATED", label_at)]
                shipment_status = "label_created"

                if order_id in delayed_ids:
                    expected_delivery_at = (
                        EVALUATION_TIME
                        - timedelta(hours=rng.randint(12, 48))
                    )
                    root_causes[
                        (order_id, "DELAYED_SHIPMENT")
                    ] = "carrier_handover_not_confirmed"
                else:
                    expected_delivery_at = (
                        EVALUATION_TIME
                        + timedelta(hours=rng.randint(12, 48))
                    )

                root_causes[
                    (order_id, "MISSING_CARRIER_EVENT")
                ] = "carrier_acceptance_scan_missing"

            else:
                label_at = (
                    order_date
                    + timedelta(hours=rng.randint(2, 8))
                )
                accepted_at = (
                    label_at
                    + timedelta(hours=rng.randint(2, 8))
                )
                shipped_at = accepted_at
                in_transit_at = (
                    accepted_at
                    + timedelta(hours=rng.randint(8, 20))
                )

                if order_id in delayed_ids:
                    expected_delivery_at = (
                        EVALUATION_TIME
                        - timedelta(hours=rng.randint(12, 48))
                    )
                    in_transit_at = min(
                        in_transit_at,
                        EVALUATION_TIME - timedelta(hours=18),
                    )
                    timeline = [
                        ("LABEL_CREATED", label_at),
                        ("CARRIER_ACCEPTED", accepted_at),
                        ("IN_TRANSIT", in_transit_at),
                    ]

                    if rng.random() < 0.35:
                        exception_at = min(
                            in_transit_at + timedelta(hours=6),
                            EVALUATION_TIME - timedelta(hours=6),
                        )
                        timeline.append(
                            ("EXCEPTION", exception_at)
                        )
                        shipment_status = "exception"
                        root_causes[
                            (order_id, "DELAYED_SHIPMENT")
                        ] = "carrier_exception_event"
                    else:
                        shipment_status = "in_transit"
                        root_causes[
                            (order_id, "DELAYED_SHIPMENT")
                        ] = "carrier_transit_delay"

                else:
                    expected_delivery_at = max(
                        shipped_at
                        + timedelta(days=rng.randint(2, 4)),
                        EVALUATION_TIME + timedelta(hours=12),
                    )
                    in_transit_at = min(
                        in_transit_at,
                        EVALUATION_TIME - timedelta(hours=1),
                    )
                    timeline = [
                        ("LABEL_CREATED", label_at),
                        ("CARRIER_ACCEPTED", accepted_at),
                        ("IN_TRANSIT", in_transit_at),
                    ]
                    shipment_status = "in_transit"

        elif status == "delivered":
            label_at = (
                order_date
                + timedelta(hours=rng.randint(2, 8))
            )
            accepted_at = (
                label_at
                + timedelta(hours=rng.randint(2, 8))
            )
            shipped_at = accepted_at
            expected_delivery_at = (
                shipped_at
                + timedelta(days=rng.randint(2, 4))
            )
            delivered_at = (
                shipped_at
                + timedelta(
                    days=rng.randint(1, 3),
                    hours=rng.randint(1, 12),
                )
            )
            delivered_at = min(
                delivered_at,
                EVALUATION_TIME - timedelta(hours=1),
            )

            if delivered_at <= accepted_at:
                delivered_at = accepted_at + timedelta(hours=24)

            in_transit_at = (
                accepted_at
                + timedelta(hours=rng.randint(8, 20))
            )
            timeline = [
                ("LABEL_CREATED", label_at),
                ("CARRIER_ACCEPTED", accepted_at),
                ("IN_TRANSIT", in_transit_at),
            ]

            if rng.random() < 0.50:
                out_for_delivery_at = min(
                    delivered_at
                    - timedelta(hours=rng.randint(2, 8)),
                    delivered_at - timedelta(minutes=30),
                )
                if out_for_delivery_at > in_transit_at:
                    timeline.append(
                        ("OUT_FOR_DELIVERY", out_for_delivery_at)
                    )

            timeline.append(("DELIVERED", delivered_at))
            shipment_status = "delivered"

        else:
            raise ValueError(f"Unexpected order status: {status}")

        timeline.sort(key=lambda event: event[1])

        for sequence, (event_type, event_at) in enumerate(
            timeline,
            start=1,
        ):
            add_event(
                shipment_id,
                order_id,
                event_type,
                event_at,
                sequence,
            )

        shipments.append(
            {
                "shipment_id": shipment_id,
                "order_id": order_id,
                "carrier": carrier,
                "shipped_at": shipped_at,
                "expected_delivery_at": expected_delivery_at,
                "delivered_at": delivered_at,
                "shipment_status": shipment_status,
            }
        )

    return shipments, shipment_events, root_causes


def generate_inventory(
    orders: list[dict[str, str | float]],
    order_items: list[dict[str, str | int | Decimal]],
) -> list[dict[str, str | int | datetime]]:
    """Generate one current inventory snapshot row per SKU."""
    rng = random.Random(SEED + 4_000)

    order_status = {
        str(order["order_id"]): str(order["status"])
        for order in orders
    }

    reserved_by_sku: Counter[str] = Counter()

    for item in order_items:
        if order_status[str(item["order_id"])] in {
            "created",
            "processing",
            "packed",
        }:
            reserved_by_sku[str(item["sku"])] += int(
                item["quantity"]
            )

    inventory: list[dict[str, str | int | datetime]] = []

    for sku_number in range(1, SKU_COUNT + 1):
        sku = f"SKU-{sku_number:04d}"
        reserved_quantity = reserved_by_sku.get(sku, 0)

        inventory.append(
            {
                "sku": sku,
                "warehouse_id": WAREHOUSE_ID,
                "available_quantity": (
                    reserved_quantity
                    + rng.randint(8, 140)
                ),
                "reserved_quantity": reserved_quantity,
                "updated_at": (
                    EVALUATION_TIME
                    - timedelta(minutes=rng.randint(5, 240))
                ),
            }
        )

    return inventory


def generate_billing(
    orders: list[dict[str, str | float]],
    billing_mismatch_ids: set[str],
) -> tuple[
    list[dict[str, str | Decimal | datetime]],
    dict[str, tuple[str, int]],
]:
    """Generate billing records and inject known over/under-billing cases."""
    rng = random.Random(SEED + 5_000)
    billing: list[dict[str, str | Decimal | datetime]] = []
    billing_root_causes: dict[str, tuple[str, int]] = {}

    for order in orders:
        order_id = str(order["order_id"])
        gross_cents = money_to_cents(order["gross_revenue"])

        if order["status"] == "cancelled":
            expected_cents = 0
            billed_cents = 0
            invoice_status = "cancelled"
        else:
            expected_cents = gross_cents
            billed_cents = gross_cents

            if order["status"] in {"created", "processing"}:
                invoice_status = "pending"
            else:
                invoice_status = "issued"

        if order_id in billing_mismatch_ids:
            delta_cents = rng.randint(150, 2_500)

            if rng.random() < 0.50:
                billed_cents = max(
                    1,
                    expected_cents - delta_cents,
                )
                root_cause = "underbilled_order"
            else:
                billed_cents = (
                    expected_cents + delta_cents
                )
                root_cause = "overbilled_order"

            invoice_status = "issued"
            billing_root_causes[order_id] = (
                root_cause,
                billed_cents - expected_cents,
            )

        order_date = parse_datetime(str(order["order_date"]))
        updated_at = min(
            order_date
            + timedelta(hours=rng.randint(4, 48)),
            EVALUATION_TIME - timedelta(minutes=1),
        )

        billing.append(
            {
                "order_id": order_id,
                "billed_amount": cents_to_decimal(
                    billed_cents
                ),
                "expected_amount": cents_to_decimal(
                    expected_cents
                ),
                "invoice_status": invoice_status,
                "updated_at": updated_at,
            }
        )

    return billing, billing_root_causes


def generate_ground_truth(
    orders: list[dict[str, str | float]],
    shipments: list[dict[str, str | datetime | None]],
    shipment_events: list[dict[str, str | int | datetime]],
    billing: list[dict[str, str | Decimal | datetime]],
    exceptions: dict[str, set[str]],
    shipment_root_causes: dict[tuple[str, str], str],
    billing_root_causes: dict[str, tuple[str, int]],
) -> list[dict[str, str]]:
    """Create agent-hidden ground-truth labels for evaluation."""
    orders_by_id = {
        str(order["order_id"]): order
        for order in orders
    }
    shipments_by_order = {
        str(shipment["order_id"]): shipment
        for shipment in shipments
    }
    billing_by_order = {
        str(record["order_id"]): record
        for record in billing
    }

    events_by_order: dict[
        str,
        list[dict[str, str | int | datetime]],
    ] = defaultdict(list)
    for event in shipment_events:
        events_by_order[str(event["order_id"])].append(event)

    ground_truth: list[dict[str, str]] = []

    for order_id in sorted(exceptions["DELAYED_SHIPMENT"]):
        shipment = shipments_by_order[order_id]
        root_cause = shipment_root_causes[
            (order_id, "DELAYED_SHIPMENT")
        ]

        note = (
            "Shipment expected by "
            f"{format_datetime(shipment['expected_delivery_at'])}; "
            "not delivered by evaluation time "
            f"{format_datetime(EVALUATION_TIME)}."
        )

        if root_cause == "carrier_exception_event":
            note += " Carrier timeline includes an EXCEPTION event."
        elif root_cause == "carrier_handover_not_confirmed":
            note += (
                " LABEL_CREATED is present but "
                "CARRIER_ACCEPTED is missing."
            )
        else:
            note += (
                " Carrier accepted the shipment, but it remains "
                "in transit past the expected delivery."
            )

        ground_truth.append(
            {
                "order_id": order_id,
                "expected_exception_type": "DELAYED_SHIPMENT",
                "expected_root_cause": root_cause,
                "expected_escalation": "false",
                "scenario_notes": note,
            }
        )

    for order_id in sorted(
        exceptions["MISSING_CARRIER_EVENT"]
    ):
        label_event = next(
            event
            for event in events_by_order[order_id]
            if event["event_type"] == "LABEL_CREATED"
        )

        ground_truth.append(
            {
                "order_id": order_id,
                "expected_exception_type": "MISSING_CARRIER_EVENT",
                "expected_root_cause": (
                    "carrier_acceptance_scan_missing"
                ),
                "expected_escalation": "false",
                "scenario_notes": (
                    "LABEL_CREATED at "
                    f"{format_datetime(label_event['event_at'])} "
                    "with no CARRIER_ACCEPTED event more than "
                    "24 hours later."
                ),
            }
        )

    for order_id in sorted(exceptions["LOW_MARGIN"]):
        order = orders_by_id[order_id]
        gross = Decimal(str(order["gross_revenue"]))
        product = Decimal(str(order["product_cost"]))
        shipping = Decimal(str(order["shipping_cost"]))
        margin_pct = (
            gross - product - shipping
        ) / gross

        ground_truth.append(
            {
                "order_id": order_id,
                "expected_exception_type": "LOW_MARGIN",
                "expected_root_cause": "high_product_cost",
                "expected_escalation": "true",
                "scenario_notes": (
                    "Injected product-cost increase leaves "
                    f"order margin at {margin_pct:.2%}, below "
                    "the 5% rule."
                ),
            }
        )

    for order_id in sorted(
        exceptions["BILLING_MISMATCH"]
    ):
        billing_record = billing_by_order[order_id]
        root_cause, delta_cents = (
            billing_root_causes[order_id]
        )

        ground_truth.append(
            {
                "order_id": order_id,
                "expected_exception_type": "BILLING_MISMATCH",
                "expected_root_cause": root_cause,
                "expected_escalation": "true",
                "scenario_notes": (
                    "Billed amount "
                    f"{billing_record['billed_amount']:.2f} "
                    "differs from expected amount "
                    f"{billing_record['expected_amount']:.2f} "
                    "by "
                    f"{abs(Decimal(delta_cents) / 100):.2f} EUR."
                ),
            }
        )

    return ground_truth


def detect_low_margin(
    orders: list[dict[str, str | float]],
) -> set[str]:
    """Apply the canonical LOW_MARGIN rule."""
    detected: set[str] = set()

    for order in orders:
        gross = Decimal(str(order["gross_revenue"]))
        product = Decimal(str(order["product_cost"]))
        shipping = Decimal(str(order["shipping_cost"]))

        margin_pct = (
            gross - product - shipping
        ) / gross

        if margin_pct < Decimal("0.05"):
            detected.add(str(order["order_id"]))

    return detected


def detect_billing_mismatch(
    billing: list[dict[str, str | Decimal | datetime]],
) -> set[str]:
    """Apply the canonical BILLING_MISMATCH rule."""
    return {
        str(record["order_id"])
        for record in billing
        if abs(
            Decimal(str(record["billed_amount"]))
            - Decimal(str(record["expected_amount"]))
        )
        > Decimal("0.01")
    }


def detect_delayed_shipments(
    orders: list[dict[str, str | float]],
    shipments: list[dict[str, str | datetime | None]],
) -> set[str]:
    """Apply the canonical DELAYED_SHIPMENT rule."""
    order_status = {
        str(order["order_id"]): str(order["status"])
        for order in orders
    }

    return {
        str(shipment["order_id"])
        for shipment in shipments
        if order_status[str(shipment["order_id"])] != "cancelled"
        and shipment["delivered_at"] is None
        and shipment["expected_delivery_at"] is not None
        and shipment["expected_delivery_at"] < EVALUATION_TIME
    }


def detect_missing_carrier_events(
    shipment_events: list[
        dict[str, str | int | datetime]
    ],
) -> set[str]:
    """Apply the canonical MISSING_CARRIER_EVENT rule."""
    events_by_order: dict[
        str,
        list[dict[str, str | int | datetime]],
    ] = defaultdict(list)

    for event in shipment_events:
        events_by_order[str(event["order_id"])].append(event)

    detected: set[str] = set()

    for order_id, events in events_by_order.items():
        label_times = [
            event["event_at"]
            for event in events
            if event["event_type"] == "LABEL_CREATED"
        ]
        accepted_exists = any(
            event["event_type"] == "CARRIER_ACCEPTED"
            for event in events
        )

        if (
            label_times
            and not accepted_exists
            and (
                EVALUATION_TIME
                - min(label_times)
            )
            > timedelta(hours=24)
        ):
            detected.add(order_id)

    return detected


def validate_dataset(
    orders: list[dict[str, str | float]],
    order_items: list[dict[str, str | int | Decimal]],
    shipments: list[dict[str, str | datetime | None]],
    shipment_events: list[dict[str, str | int | datetime]],
    inventory: list[dict[str, str | int | datetime]],
    billing: list[dict[str, str | Decimal | datetime]],
    ground_truth: list[dict[str, str]],
    exceptions: dict[str, set[str]],
) -> None:
    """Fail fast if relational or exception-generation invariants are broken."""
    if len(orders) != ORDER_COUNT:
        raise AssertionError("orders must contain exactly 1,000 rows.")

    order_ids = [
        str(order["order_id"])
        for order in orders
    ]

    if len(set(order_ids)) != ORDER_COUNT:
        raise AssertionError("order_id values must be unique.")

    if any(
        str(order["status"]) not in ALLOWED_ORDER_STATUSES
        for order in orders
    ):
        raise AssertionError("Unexpected order status found.")

    if any(
        str(order["payment_status"])
        not in ALLOWED_PAYMENT_STATUSES
        for order in orders
    ):
        raise AssertionError("Unexpected payment status found.")

    item_ids = [
        str(item["order_item_id"])
        for item in order_items
    ]

    if len(item_ids) != len(set(item_ids)):
        raise AssertionError(
            "order_item_id values must be unique."
        )

    if any(
        str(item["order_id"]) not in set(order_ids)
        for item in order_items
    ):
        raise AssertionError(
            "order_items contains an invalid order_id."
        )

    items_by_order: dict[
        str,
        list[dict[str, str | int | Decimal]],
    ] = defaultdict(list)

    for item in order_items:
        items_by_order[str(item["order_id"])].append(item)

        sku_number = int(str(item["sku"]).split("-")[1])
        if not 1 <= sku_number <= SKU_COUNT:
            raise AssertionError("SKU outside the canonical range.")

        if int(item["quantity"]) not in {1, 2, 3}:
            raise AssertionError("Invalid order-item quantity.")

        if (
            money_to_cents(item["unit_price"]) <= 0
            or money_to_cents(item["unit_product_cost"]) <= 0
        ):
            raise AssertionError(
                "Order-item prices and costs must be positive."
            )

    for order in orders:
        order_id = str(order["order_id"])
        item_rows = items_by_order[order_id]

        if not 1 <= len(item_rows) <= 3:
            raise AssertionError(
                f"{order_id} must have 1-3 order-item rows."
            )

        skus = [
            str(item["sku"])
            for item in item_rows
        ]
        if len(skus) != len(set(skus)):
            raise AssertionError(
                f"{order_id} contains a duplicate SKU."
            )

        item_revenue_cents = sum(
            money_to_cents(item["unit_price"])
            * int(item["quantity"])
            for item in item_rows
        )
        item_product_cents = sum(
            money_to_cents(item["unit_product_cost"])
            * int(item["quantity"])
            for item in item_rows
        )

        if item_revenue_cents != money_to_cents(
            order["gross_revenue"]
        ):
            raise AssertionError(
                f"Revenue does not reconcile for {order_id}."
            )

        if item_product_cents != money_to_cents(
            order["product_cost"]
        ):
            raise AssertionError(
                f"Product cost does not reconcile for {order_id}."
            )

    shipment_ids = [
        str(shipment["shipment_id"])
        for shipment in shipments
    ]

    if len(shipments) != ORDER_COUNT:
        raise AssertionError(
            "Expected one shipment record per order."
        )

    if len(set(shipment_ids)) != ORDER_COUNT:
        raise AssertionError(
            "shipment_id values must be unique."
        )

    if {
        str(shipment["order_id"])
        for shipment in shipments
    } != set(order_ids):
        raise AssertionError(
            "Shipment/order relationship is incomplete."
        )

    if any(
        str(shipment["shipment_status"])
        not in ALLOWED_SHIPMENT_STATUSES
        for shipment in shipments
    ):
        raise AssertionError(
            "Unexpected shipment status found."
        )

    event_ids = [
        str(event["event_id"])
        for event in shipment_events
    ]

    if len(event_ids) != len(set(event_ids)):
        raise AssertionError(
            "event_id values must be unique."
        )

    if any(
        str(event["event_type"]) not in ALLOWED_EVENT_TYPES
        for event in shipment_events
    ):
        raise AssertionError(
            "Unexpected shipment event type found."
        )

    events_by_shipment: dict[
        str,
        list[dict[str, str | int | datetime]],
    ] = defaultdict(list)

    for event in shipment_events:
        if str(event["shipment_id"]) not in set(shipment_ids):
            raise AssertionError(
                "Shipment event references an invalid shipment."
            )
        if str(event["order_id"]) not in set(order_ids):
            raise AssertionError(
                "Shipment event references an invalid order."
            )
        events_by_shipment[str(event["shipment_id"])].append(
            event
        )

    for shipment_id, event_rows in events_by_shipment.items():
        ordered_events = sorted(
            event_rows,
            key=lambda event: int(event["event_sequence"]),
        )
        expected_sequence = list(
            range(1, len(ordered_events) + 1)
        )
        actual_sequence = [
            int(event["event_sequence"])
            for event in ordered_events
        ]

        if actual_sequence != expected_sequence:
            raise AssertionError(
                f"Invalid event sequence for {shipment_id}."
            )

        event_times = [
            event["event_at"]
            for event in ordered_events
        ]
        if event_times != sorted(event_times):
            raise AssertionError(
                f"Non-chronological events for {shipment_id}."
            )

    if len(inventory) != SKU_COUNT:
        raise AssertionError(
            "inventory must contain exactly 150 SKU rows."
        )

    if len(
        {
            str(row["sku"])
            for row in inventory
        }
    ) != SKU_COUNT:
        raise AssertionError(
            "inventory SKUs must be unique."
        )

    if any(
        str(row["warehouse_id"]) != WAREHOUSE_ID
        for row in inventory
    ):
        raise AssertionError(
            "Unexpected warehouse_id found."
        )

    if any(
        int(row["available_quantity"]) < 0
        or int(row["reserved_quantity"]) < 0
        for row in inventory
    ):
        raise AssertionError(
            "Inventory quantities cannot be negative."
        )

    if len(billing) != ORDER_COUNT:
        raise AssertionError(
            "Expected one billing row per order."
        )

    if len(
        {
            str(row["order_id"])
            for row in billing
        }
    ) != ORDER_COUNT:
        raise AssertionError(
            "Billing order_id values must be unique."
        )

    if any(
        str(row["invoice_status"])
        not in ALLOWED_INVOICE_STATUSES
        for row in billing
    ):
        raise AssertionError(
            "Unexpected invoice status found."
        )

    detected = {
        "DELAYED_SHIPMENT": detect_delayed_shipments(
            orders,
            shipments,
        ),
        "MISSING_CARRIER_EVENT": detect_missing_carrier_events(
            shipment_events
        ),
        "LOW_MARGIN": detect_low_margin(orders),
        "BILLING_MISMATCH": detect_billing_mismatch(billing),
    }

    for exception_type, expected_ids in exceptions.items():
        if detected[exception_type] != expected_ids:
            unexpected = (
                detected[exception_type] - expected_ids
            )
            missing = (
                expected_ids - detected[exception_type]
            )
            raise AssertionError(
                f"{exception_type} detection mismatch. "
                f"Unexpected={sorted(unexpected)}; "
                f"missing={sorted(missing)}"
            )

    ground_truth_pairs = {
        (
            row["order_id"],
            row["expected_exception_type"],
        )
        for row in ground_truth
    }
    expected_pairs = {
        (order_id, exception_type)
        for exception_type, order_id_set
        in exceptions.items()
        for order_id in order_id_set
    }

    if ground_truth_pairs != expected_pairs:
        raise AssertionError(
            "Ground truth does not match injected exceptions."
        )

    unique_exception_orders = {
        row["order_id"]
        for row in ground_truth
    }

    if len(unique_exception_orders) != 180:
        raise AssertionError(
            "Expected exactly 180 unique exception orders."
        )

    if len(ground_truth) != 200:
        raise AssertionError(
            "Expected exactly 200 ground-truth exception rows."
        )


def write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict],
    money_fields: set[str] | None = None,
) -> None:
    """Write rows with stable datetime and money formatting."""
    money_fields = money_fields or set()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for source_row in rows:
            row = dict(source_row)

            for field in fieldnames:
                value = row.get(field)

                if field in money_fields:
                    row[field] = (
                        ""
                        if value is None
                        else f"{Decimal(str(value)):.2f}"
                    )
                elif isinstance(value, datetime):
                    row[field] = format_datetime(value)
                elif value is None:
                    row[field] = ""

            writer.writerow(row)


def main() -> None:
    orders = generate_orders()
    order_items = generate_order_items(orders)

    exceptions = choose_exception_cases(
        orders,
        order_items,
    )

    inject_low_margin_exceptions(
        orders,
        order_items,
        exceptions["LOW_MARGIN"],
    )

    (
        shipments,
        shipment_events,
        shipment_root_causes,
    ) = generate_shipments_and_events(
        orders,
        exceptions,
    )

    inventory = generate_inventory(
        orders,
        order_items,
    )

    billing, billing_root_causes = generate_billing(
        orders,
        exceptions["BILLING_MISMATCH"],
    )

    ground_truth = generate_ground_truth(
        orders,
        shipments,
        shipment_events,
        billing,
        exceptions,
        shipment_root_causes,
        billing_root_causes,
    )

    validate_dataset(
        orders,
        order_items,
        shipments,
        shipment_events,
        inventory,
        billing,
        ground_truth,
        exceptions,
    )

    write_csv(
        OUTPUT_DIR / "orders.csv",
        ORDERS_FIELDS,
        orders,
        {
            "gross_revenue",
            "product_cost",
            "shipping_cost",
        },
    )
    write_csv(
        OUTPUT_DIR / "order_items.csv",
        ORDER_ITEMS_FIELDS,
        order_items,
        {
            "unit_price",
            "unit_product_cost",
        },
    )
    write_csv(
        OUTPUT_DIR / "shipments.csv",
        SHIPMENTS_FIELDS,
        shipments,
    )
    write_csv(
        OUTPUT_DIR / "shipment_events.csv",
        SHIPMENT_EVENTS_FIELDS,
        shipment_events,
    )
    write_csv(
        OUTPUT_DIR / "inventory.csv",
        INVENTORY_FIELDS,
        inventory,
    )
    write_csv(
        OUTPUT_DIR / "billing.csv",
        BILLING_FIELDS,
        billing,
        {
            "billed_amount",
            "expected_amount",
        },
    )
    write_csv(
        OUTPUT_DIR / "ground_truth_exceptions.csv",
        GROUND_TRUTH_FIELDS,
        ground_truth,
    )

    unique_exception_orders = len(
        {
            row["order_id"]
            for row in ground_truth
        }
    )

    print("Synthetic dataset generated and validated successfully.")
    print(f"orders.csv: {len(orders)} rows")
    print(f"order_items.csv: {len(order_items)} rows")
    print(f"shipments.csv: {len(shipments)} rows")
    print(
        "shipment_events.csv: "
        f"{len(shipment_events)} rows"
    )
    print(f"inventory.csv: {len(inventory)} rows")
    print(f"billing.csv: {len(billing)} rows")
    print(
        "ground_truth_exceptions.csv: "
        f"{len(ground_truth)} rows"
    )
    print(
        "Unique orders with at least one injected exception: "
        f"{unique_exception_orders} "
        f"({unique_exception_orders / ORDER_COUNT:.1%})"
    )

    for exception_type in (
        "DELAYED_SHIPMENT",
        "MISSING_CARRIER_EVENT",
        "LOW_MARGIN",
        "BILLING_MISMATCH",
    ):
        print(
            f"{exception_type}: "
            f"{len(exceptions[exception_type])}"
        )


if __name__ == "__main__":
    main()
