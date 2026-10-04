# Data Dictionary

## 1. Purpose

This document defines the canonical source-data contract for the AI Operations Exception Investigation and Resolution Agent.

The first implementation uses synthetic data.

If approved real operational data is introduced later, it should be transformed into this schema rather than changing the downstream system around source-specific column names.

No customer names, addresses, email addresses, phone numbers, payment-card data, or other unnecessary personal data are required.

---

## 2. Synthetic Business Context

- Business model: German B2C e-commerce
- Currency: EUR
- Primary warehouse: WH-BER-01
- Carriers: DHL and GLS
- Dataset period: 90 days
- Target order count: 1,000
- Data type: Synthetic
- Customer identifiers: Pseudonymous IDs only

---

# 3. Source Tables

## 3.1 `orders`

One row per customer order.

| Column | BigQuery Type | Required | Description | Example |
|---|---|---|---|---|
| `order_id` | STRING | Yes | Unique order identifier | ORD-000123 |
| `customer_id` | STRING | No | Pseudonymous customer identifier | CUS-00418 |
| `order_date` | TIMESTAMP | Yes | Time the order was created | 2026-08-14 10:32:00 |
| `status` | STRING | Yes | Current operational order status | shipped |
| `gross_revenue` | NUMERIC | Yes | Gross order revenue in EUR | 84.90 |
| `product_cost` | NUMERIC | Yes | Total product cost in EUR | 42.50 |
| `shipping_cost` | NUMERIC | Yes | Shipping cost in EUR | 5.49 |
| `payment_status` | STRING | Yes | Current payment status | paid |

### Allowed `status`

- created
- processing
- packed
- shipped
- delivered
- cancelled

### Allowed `payment_status`

- paid
- pending
- refunded
- failed

---

## 3.2 `order_items`

One row per SKU contained in an order.

An order may contain multiple order-item rows.

| Column | BigQuery Type | Required | Description | Example |
|---|---|---|---|---|
| `order_item_id` | STRING | Yes | Unique order-line identifier | OI-000123-01 |
| `order_id` | STRING | Yes | Parent order identifier | ORD-000123 |
| `sku` | STRING | Yes | Product SKU | SKU-0042 |
| `quantity` | INTEGER | Yes | Quantity ordered | 2 |
| `unit_price` | NUMERIC | Yes | Selling price per unit in EUR | 24.95 |
| `unit_product_cost` | NUMERIC | Yes | Product cost per unit in EUR | 11.50 |

---

## 3.3 `shipments`

One row per shipment.

The initial synthetic version assumes one shipment per order.

| Column | BigQuery Type | Required | Description | Example |
|---|---|---|---|---|
| `shipment_id` | STRING | Yes | Unique shipment identifier | SHP-000123 |
| `order_id` | STRING | Yes | Associated order | ORD-000123 |
| `carrier` | STRING | Yes | Shipping provider | DHL |
| `shipped_at` | TIMESTAMP | No | Time the order left the warehouse | 2026-08-15 09:10:00 |
| `expected_delivery_at` | TIMESTAMP | No | Expected delivery time | 2026-08-17 18:00:00 |
| `delivered_at` | TIMESTAMP | No | Actual delivery time | 2026-08-17 14:37:00 |
| `shipment_status` | STRING | Yes | Current shipment state | in_transit |

### Allowed `carrier`

- DHL
- GLS

### Allowed `shipment_status`

- label_created
- carrier_accepted
- in_transit
- out_for_delivery
- delivered
- exception

---

## 3.4 `shipment_events`

Carrier event history.

One shipment can contain multiple events.

| Column | BigQuery Type | Required | Description | Example |
|---|---|---|---|---|
| `event_id` | STRING | Yes | Unique carrier-event identifier | EVT-000123-03 |
| `shipment_id` | STRING | Yes | Associated shipment | SHP-000123 |
| `order_id` | STRING | Yes | Associated order | ORD-000123 |
| `event_type` | STRING | Yes | Carrier event type | IN_TRANSIT |
| `event_at` | TIMESTAMP | Yes | Event timestamp | 2026-08-16 04:15:00 |
| `event_sequence` | INTEGER | Yes | Chronological event order | 3 |

### Allowed `event_type`

- LABEL_CREATED
- CARRIER_ACCEPTED
- IN_TRANSIT
- OUT_FOR_DELIVERY
- DELIVERED
- EXCEPTION

---

## 3.5 `inventory`

Current warehouse inventory state per SKU.

| Column | BigQuery Type | Required | Description | Example |
|---|---|---|---|---|
| `sku` | STRING | Yes | Product SKU | SKU-0042 |
| `warehouse_id` | STRING | Yes | Warehouse identifier | WH-BER-01 |
| `available_quantity` | INTEGER | Yes | Available units | 57 |
| `reserved_quantity` | INTEGER | Yes | Units reserved for orders | 8 |
| `updated_at` | TIMESTAMP | Yes | Inventory snapshot timestamp | 2026-10-01 18:00:00 |

---

## 3.6 `billing`

One billing record per order.

| Column | BigQuery Type | Required | Description | Example |
|---|---|---|---|---|
| `order_id` | STRING | Yes | Associated order | ORD-000123 |
| `billed_amount` | NUMERIC | Yes | Amount actually billed in EUR | 84.90 |
| `expected_amount` | NUMERIC | Yes | Amount expected according to order logic | 84.90 |
| `invoice_status` | STRING | Yes | Current invoice state | issued |
| `updated_at` | TIMESTAMP | Yes | Last billing update | 2026-08-15 10:15:00 |

### Allowed `invoice_status`

- pending
- issued
- corrected
- cancelled

---

# 4. Table Relationships

```text
orders
  |
  +----< order_items >---- inventory
  |
  +---- shipments
  |        |
  |        +----< shipment_events
  |
  +---- billing