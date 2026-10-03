# Project 1 - AI Operations Exception Investigation and Resolution Agent

## 1. Project purpose

Build a production-oriented bounded agentic system that detects operational exceptions using deterministic logic, then uses an AI agent to investigate the likely cause, gather evidence through approved tools, recommend an action, and escalate to a human when evidence is incomplete or the proposed action is consequential.

This project is built from scratch.

It should demonstrate a practical AI automation pattern relevant to Operations, Logistics, Fulfilment, E-commerce, and Finance.

The system must not simply ask an LLM to summarize a row from a database. The AI component must perform bounded investigation through tool use.

---

# 2. Business problem

Operations teams often spend time investigating repetitive exceptions such as:

- delayed shipments
- missing carrier events
- low-margin orders
- billing inconsistencies
- inventory mismatches
- duplicate or conflicting order records
- orders stuck in an operational state
- unusual fulfilment or shipping patterns

Traditional rules are good at detecting that something is wrong.

They are not always enough to determine:

- why it happened
- which systems should be inspected
- whether the issue has happened before
- which evidence is relevant
- what action should be recommended

This creates a recurring manual investigation workload.

---

# 3. Business user

Primary users:

- Operations Analyst
- Fulfilment Manager
- Logistics Operations
- E-commerce Operations
- Finance Operations

Secondary users:

- Customer Support
- Supply Chain
- Management

---

# 4. Manual current-state workflow

A typical manual process may look like:

```text
Daily export / dashboard
        |
        v
Employee notices exception
        |
        v
Open order system
        |
        v
Open shipment / carrier data
        |
        v
Check inventory record
        |
        v
Check billing or margin
        |
        v
Search previous incidents
        |
        v
Decide likely cause
        |
        v
Contact another team
        |
        v
Record action manually
```

Pain points:

- repetitive investigation
- multiple systems
- inconsistent investigation quality
- important evidence can be missed
- repeated issues may not be recognized
- no standardized audit trail
- slow resolution
- difficult to measure investigation effort

---

# 5. Target future-state workflow

```text
Operational data
      |
      v
n8n ingestion
      |
      v
Python schema validation
      |
      v
BigQuery
      |
      v
Deterministic SQL rules
      |
      v
Exception created
      |
      v
BOUNDED OPERATIONS AGENT
      |
      v
Agent receives investigation goal
      |
      v
Agent selects approved tools
      |
      v
Tool result
      |
      v
Enough evidence?
   /        \
 no          yes
 |            |
another      conclusion
tool call    + evidence
 |            |
max steps    recommendation
      \      /
       v    v
      Human review
          |
          v
approved action / escalation
          |
          v
resolution + telemetry
          |
          v
BigQuery + Looker Studio
```

---

# 6. Why this is agentic

Deterministic rules detect the exception.

Example:

```sql
CASE
  WHEN delivered_at IS NULL
   AND expected_delivery_at < CURRENT_TIMESTAMP()
  THEN 'DELAYED_SHIPMENT'
END
```

That is not an AI task.

The agent receives:

> Investigate why case EXC-1042 triggered a delayed-shipment exception. Gather sufficient evidence, identify the most probable cause, and recommend the next operational action.

The agent can decide whether it needs to inspect:

- order details
- carrier events
- inventory status
- billing record
- previous exceptions
- operations policy

The path is not identical for every exception.

That decision process creates genuine bounded agentic behavior.

---

# 7. Technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Workflow orchestration | n8n | triggers, branching, tool calls, retries, alerts |
| Agent LLM | Ollama with suitable local tool-capable model | local agent reasoning |
| Data warehouse | BigQuery | source tables, exception tables, telemetry |
| Business rules | SQL | deterministic exception detection |
| Supporting code | Python | validation, transformation, tool endpoints |
| BI | Looker Studio | operational and agent-performance dashboards |
| Packaging | Docker | reproducible local services |
| Version control | Git/GitHub | code, workflow export, documentation |
| Optional alerting | email or Slack-style mock | human notification |

---

# 8. Proposed data model

## orders

Potential fields:

- order_id
- customer_id
- order_date
- status
- gross_revenue
- product_cost
- shipping_cost
- payment_status

## shipments

- shipment_id
- order_id
- carrier
- created_at
- expected_delivery_at
- delivered_at
- latest_event
- latest_event_at

## inventory

- sku
- available_quantity
- reserved_quantity
- warehouse
- updated_at

## billing

- order_id
- billed_amount
- expected_amount
- invoice_status
- updated_at

## exception_cases

- exception_id
- order_id
- exception_type
- severity
- created_at
- status
- deterministic_rule
- current_owner
- resolved_at

## agent_runs

Use the shared telemetry schema described later in this document.

Synthetic data is acceptable and preferred during development.

---

# 9. Deterministic exception types

Initial scope should remain small.

Recommended first four:

1. delayed shipment
2. missing carrier event
3. low-margin order
4. billing mismatch

Do not begin with ten exception types.

The goal is to create a robust architecture that can be extended later.

---

# 10. Agent goal

Canonical goal:

> Investigate the detected operational exception using only the approved read-only tools. Gather sufficient evidence, identify the most probable cause, state uncertainty explicitly, and recommend the safest next action. If evidence is insufficient, return UNKNOWN and escalate for human review.

---

# 11. Approved agent tools

## get_order_details(order_id)

Returns:

- order metadata
- products
- status
- financial summary

## get_shipment_events(order_id)

Returns:

- carrier
- event timeline
- timestamps
- current shipment state

## get_inventory_status(order_id)

Returns:

- relevant SKUs
- stock state
- reservation state

## get_billing_record(order_id)

Returns:

- billed amount
- expected amount
- discrepancy

## get_previous_exceptions(order_id or pattern)

Returns:

- similar previous exceptions
- historical outcomes

## search_operations_policy(query)

Returns:

- approved policy text
- policy ID
- source reference

Initial tools should be read-only.

The agent must not directly:

- refund customers
- update invoices
- adjust stock
- delete records
- send external customer communications

---

# 12. Agent output schema

Example:

```json
{
  "exception_id": "EXC-1042",
  "conclusion": "Carrier acceptance scan missing",
  "confidence": 0.83,
  "evidence": [
    {
      "source": "shipment_events",
      "fact": "Label created but no carrier acceptance scan exists"
    }
  ],
  "recommended_action": "Ask fulfilment team to verify physical handover",
  "escalation_required": true,
  "missing_information": [],
  "tools_used": [
    "get_order_details",
    "get_shipment_events"
  ]
}
```

If evidence is insufficient:

```json
{
  "conclusion": "UNKNOWN",
  "confidence": 0.31,
  "recommended_action": "Human investigation required",
  "escalation_required": true
}
```

---

# 13. Agent boundaries

Mandatory:

- maximum tool-call count
- maximum loop count
- read-only tools initially
- structured output
- UNKNOWN path
- human review
- no destructive actions
- no financial correction without approval
- all tool calls logged

Potential initial maximum:

- 5 agent tool calls

This can be adjusted after testing.

---

# 14. Human-in-the-loop design

Human review screen or notification should show:

- exception type
- deterministic rule
- agent conclusion
- confidence
- evidence
- tools used
- proposed action

Human options:

- approve recommendation
- reject recommendation
- edit recommendation
- escalate
- mark false positive

The human decision becomes evaluation data.

---

# 15. Reliability requirements

The workflow should handle:

- malformed input
- missing order
- duplicate ingestion
- duplicate exception
- unavailable BigQuery query
- Python validation failure
- agent timeout
- invalid structured output
- Ollama unavailable
- tool endpoint failure
- maximum-step limit reached

Required mechanisms:

- retries with limits
- failed-job queue
- error workflow
- clear status transitions
- idempotency keys
- logging
- alerts for persistent failures

---

# 16. Shared observability fields

Every run should log:

- event_id
- project_id
- exception_id
- timestamp
- workflow_version
- model
- prompt_version
- agent_steps
- tool_call_count
- tools_used
- duration_ms
- success
- failure
- error_type
- human_override
- escalated
- confidence
- estimated_manual_minutes
- automated_minutes

For local Ollama:

- API cost should remain zero, but inference time should still be recorded.

---

# 17. Evaluation plan

Create a reviewed evaluation dataset with known exception cases.

The evaluation set should include:

- obvious delayed shipment
- misleading status
- missing event
- valid shipment falsely appearing delayed
- billing mismatch with correct shipment
- low margin caused by shipping
- insufficient evidence case
- conflicting evidence case

Evaluate:

## Deterministic layer

- exception precision
- false-positive rate

## Agent layer

- root-cause correctness
- evidence quality
- correct tool selection
- unnecessary tool-call rate
- UNKNOWN behavior
- escalation correctness
- human override rate
- average agent steps
- average latency

---

# 18. Business impact metrics

Potential measures:

- manual investigation minutes per case
- agent-assisted investigation minutes
- estimated hours saved
- time to first actionable recommendation
- repeat exception recognition
- human override rate
- resolution time
- false-positive burden

Any time-saved number must clearly distinguish:

- measured
- estimated
- simulated

---

# 19. Shared dashboard

Use Looker Studio with BigQuery.

Suggested pages:

## Operations view

- open exceptions
- exceptions by type
- exceptions by severity
- aging
- recurring cases
- status

## Agent performance

- success rate
- escalation rate
- override rate
- average tool calls
- average latency
- UNKNOWN rate

## Business impact

- estimated manual time
- automated time
- estimated time saved
- cases resolved
- high-risk exceptions

---

# 20. Proposed execution methodology

## Phase 1 - Define business baseline

Create:

- business problem statement
- user
- manual workflow
- four exception types
- baseline assumptions
- success KPIs

Do not start with the agent.

## Phase 2 - Build deterministic detection

Create:

- synthetic dataset
- BigQuery tables
- SQL exception logic
- validated exception table

Verify the rule engine separately.

## Phase 3 - Create first agent tools

Start with:

- get_order_details
- get_shipment_events

Build one exception end-to-end.

## Phase 4 - Add bounded agent loop

Implement:

- goal
- tool selection
- observations
- max steps
- structured output
- UNKNOWN path

## Phase 5 - Add remaining tools

Only after the vertical slice is stable.

## Phase 6 - Add human review

Record:

- approval
- rejection
- correction
- false positive

## Phase 7 - Reliability engineering

Break the system intentionally.

Test:

- downstream failures
- invalid LLM output
- duplicate events
- unavailable model

## Phase 8 - Evaluation

Create a reviewed benchmark set and measure agent behavior.

## Phase 9 - Dashboard and documentation

Only after the workflow works reliably.

---

# 21. Minimum viable vertical slice

First complete milestone:

```text
Synthetic shipment
  -> n8n
  -> BigQuery
  -> SQL detects delayed shipment
  -> agent receives exception
  -> agent calls order tool
  -> agent calls shipment tool
  -> agent returns evidence-based recommendation
  -> human approves/rejects
  -> result logged
```

If this works and can be explained confidently, continue.

---

# 22. Cost strategy

Target:

- near-zero development cost

Use:

- local n8n
- local Docker
- Ollama
- BigQuery free usage where practical
- Looker Studio
- synthetic data

Avoid:

- paid hosting at the beginning
- unnecessary SaaS tools
- paid LLM APIs for this project

---

# 23. Security and privacy

Use synthetic data.

Store secrets outside code.

Avoid logging sensitive payloads unnecessarily.

Document:

- what data the agent can access
- which tools are read-only
- which actions require approval
- retention assumptions
- audit trail

---

# 24. GitHub deliverables

Repository should contain:

- README
- business case
- architecture diagram
- data model
- synthetic dataset or generator
- SQL rules
- n8n workflow export
- Python tool service
- Docker setup
- evaluation dataset
- evaluation notebook/report
- dashboard screenshots
- error-handling notes
- limitations
- runbook
- demo instructions

---

# 25. Interview story

Be able to explain:

1. Why SQL detects the exception instead of the LLM.
2. Why an agent is useful for investigation.
3. How the agent selects tools.
4. Why tools are initially read-only.
5. How the system handles uncertainty.
6. How you know whether the agent is correct.
7. What happens when a tool fails.
8. How human overrides become evaluation data.
9. What the system costs.
10. When you would choose a deterministic workflow instead of an agent.

---

# 26. Completion criteria

Project is portfolio-ready when:

- four exception types work
- agent chooses tools dynamically
- max-step control exists
- UNKNOWN path works
- human review exists
- failures are recoverable
- evaluation results exist
- telemetry exists
- dashboard exists
- setup is reproducible
- limitations are documented
- the full system can be explained without relying on hidden manual steps
