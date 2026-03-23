# Section 2: SEC Rule 15c3-5 — The Market Access Rule

**Duration:** 4 minutes
**Goal:** Translate regulation into engineering requirements the audience can implement.

---

## The Four Requirements

> "Two years before Knight Capital's disaster, in 2010, the SEC passed Rule 15c3-5 — the Market Access Rule. It says: if you're a broker-dealer giving people access to the stock market, you need four things."

Walk through each one. For each requirement, immediately connect it to a component in the system they're about to see.

### Requirement 1: Pre-Trade Risk Controls

> "**One:** Pre-trade risk controls. Every order has to be checked **before** it reaches the exchange. Not after. Before. If an order violates risk limits, it never leaves your system."

**Map to code:**
- This is the Order Router (`services/order_router/route_local.py`)
- Every order passes through `check_kill_status()` before it can reach `orders.gated.v1`
- The router sits between the order source and the market — it's a gate, not a logger

> "In our system, this is the Order Router. It sits between incoming orders and the market. Every single order passes through a function called `check_kill_status()`. If the account is killed, the order is dropped. It never reaches the gated topic. It never leaves the building."

### Requirement 2: Kill Switch

> "**Two:** A kill switch. You must be able to immediately halt all trading from any account, any time. Not 'within a few minutes.' Immediately."

**Map to code:**
- This is the compacted Kafka topic `killswitch.state.v1` plus the Operator Console
- One curl command changes state; the router enforces it on the next order
- "Immediately" in practice means "within the next poll cycle" — sub-second

> "In our system, this is a single curl command to the Operator Console. POST /kill with a scope and a reason. That publishes a command to Kafka, the aggregator updates the state, and the router starts dropping orders. The whole propagation takes less than a second."

### Requirement 3: Direct and Exclusive Control

> "**Three:** Direct and exclusive control. The broker-dealer controls the switch — not the customer, not a third party, not an algorithm. A human at the firm."

**Map to code:**
- The Operator Console (`services/operator_console/api_local.py`) is the human interface
- Spark can auto-detect and auto-kill, but **recovery always requires a human**
- The `triggered_by` field distinguishes `"spark"` from `"api"` (human operator)

> "This is why we have the Operator Console as a separate service. Spark can detect problems and trigger kills automatically. But notice: Spark never issues an UNKILL. Recovery always requires a human operator. That's the 'direct and exclusive control' requirement."

**This is a subtle but important point.** Pause and make sure they get it:

> "Automatic detection, manual recovery. The machine can pull the emergency brake. Only a human can release it."

### Requirement 4: Audit Trail

> "**Four:** Audit trail. You have to be able to prove all of this happened. Every decision, every action, logged and traceable. If the SEC asks 'why did you drop this order?' you need an answer with a timestamp and a correlation ID."

**Map to code:**
- The `audit.v1` topic captures every routing decision
- Every event has a `corr_id` that traces back through the entire chain
- The `killswitch.commands.v1` topic is the historical record of every command ever issued

> "In our system, every order routing decision — ALLOW or DROP — is written to the audit topic with a correlation ID. That correlation ID connects back to the kill command that triggered the drop, which connects back to the Spark detection or operator action that initiated it. You can trace any decision from the market all the way back to its root cause."

---

## The One-Sentence Summary

After the four requirements, synthesize:

> "In one sentence: before an order touches the market, something must check it. If something goes wrong, you must stop everything immediately. And you must prove you did."

Pause. Let them write this down if they want.

---

## Transition to Architecture

> "So now we have the requirements. Four things: pre-trade checks, kill switch, human control, audit trail. How do you actually build a system that does all four? That's what this project is. Let me show you the architecture."

---

## Presenter Notes

**Why this section matters:** Without this section, the code walkthrough is "here's how to use Kafka and Spark." With this section, every line of code maps to a regulatory requirement. That's the difference between a demo and a lesson.

**If someone asks "does this apply to crypto?":** Crypto exchanges are largely unregulated (as of 2024), but the same engineering problems exist. FTX's collapse was partly a controls failure. The patterns apply even where the regulation doesn't — yet.

**If someone asks "what happens if you violate the rule?":** Fines. Knight Capital was fined $12M separately from their trading losses. Other firms have been fined for inadequate pre-trade controls. The SEC publishes enforcement actions.

**Don't get bogged down in legal details.** You're an engineer, not a lawyer. The point is: regulation creates engineering requirements. Your job is to build systems that meet those requirements.

---

## Timing Check

By the end of this section, you should be at **11 minutes** total. You've set up the problem (Knight Capital), defined the requirements (the rule), and now you're about to show the solution (the architecture). The audience should be leaning forward.
