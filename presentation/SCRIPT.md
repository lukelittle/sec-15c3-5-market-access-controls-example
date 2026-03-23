# Presentation Script: SEC Rule 15c3-5 Market Access Controls

**Class:** ITCS 6190/8190 — Cloud Computing for Data Analysis
**Duration:** 30-40 minutes + Q&A
**Audience:** Graduate CS students who know Spark, Spark SQL, and streaming. Now learning AWS.

---

## Before Class (15 minutes before)

Start the local stack:

```bash
cd local
docker compose up --build -d
```

Verify:

```bash
docker compose ps
curl http://localhost:8000/health
docker compose logs order-generator --tail 3
```

Have ready:
- Terminal in project root
- Browser with AKHQ at http://localhost:8080
- Slides open (docs/presentation.pptx)
- This script on a second screen or printed

---

## SECTION 1: Who I Am (2 minutes)

> *Slide 1: Title*

Introduce yourself. Keep it brief — name, background, what you do, why you're here. Connect your experience to what they're learning. Something like:

> "I'm [name]. I work in [area]. I built this project because I wanted to show you what it looks like when the things you're learning in this class — Spark, Kafka, AWS — come together to solve a real problem. Not a textbook problem. A problem that destroyed a company."

---

## SECTION 2: The Knight Capital Story (5 minutes)

> *Slide 2: Knight Capital*

This is the hook. Tell it like a story, not a lecture.

> "August 1st, 2012. Knight Capital Group. They were one of the biggest electronic market makers in the US — they handled something like 10% of all US equity trading volume."

> "That morning, they deployed new trading software. But an old piece of code — something that was supposed to be deactivated — got accidentally reactivated on one of their servers."

> "Within minutes, this code started sending millions of erroneous orders. Buying stocks at the ask, selling at the bid. The opposite of what you want. Across 150 different stocks."

> "The operations team realized something was wrong almost immediately. But here's the problem: there was no centralized kill switch. No single button to press that says 'stop everything.' They had to manually log into individual servers and shut them down one by one. And some servers got missed."

Pause for effect.

> "Forty-five minutes. Four hundred and forty million dollars in losses. More than the company was worth."

> "Knight Capital was acquired by Getco six months later at a fraction of its former value. The company effectively ceased to exist because of a software deployment gone wrong and the inability to stop it."

**Transition:**

> "So what happened after this? The SEC had actually already anticipated this kind of thing."

---

## SECTION 3: The Rule and Requirements (4 minutes)

> *Slide 3: SEC Rule 15c3-5*

> "Two years before Knight Capital's disaster, in 2010, the SEC passed Rule 15c3-5 — the Market Access Rule. It says: if you're a broker-dealer giving people access to the stock market, you need four things."

Go through the four requirements on the slide:

> "**One:** Pre-trade risk controls. Every order has to be checked before it reaches the exchange. Not after. Before."

> "**Two:** A kill switch. You must be able to immediately halt all trading from any account, any time."

> "**Three:** Direct and exclusive control. The broker-dealer controls the switch — not the customer, not a third party. You."

> "**Four:** Audit trail. You have to be able to prove all of this happened. Every decision, every action, logged and traceable."

> "In one sentence: before an order touches the market, something must check it. If something goes wrong, you must stop everything immediately. And you must prove you did."

**Transition:**

> "So now we have the requirements. How do you actually build this? That's what this project is."

---

## SECTION 4: Architecture (5 minutes)

> *Slide 4: System Architecture*

Walk through the diagram top to bottom.

> "Orders come into the system through the Order Generator. In production this would be customer orders; here it's synthetic data. They go onto a Kafka topic called `orders.v1`."

> "Two things consume those orders simultaneously. The Spark Risk Detector and the Order Router."

> "Spark is doing the analysis — it's watching every order in 60-second windows, computing risk metrics. If something looks wrong, it emits a KILL command."

> "That command goes through the Kill Switch Aggregator, which maintains the authoritative state on a compacted Kafka topic. One record per scope. If account 12345 is killed, that's the latest state."

> "The Order Router checks every single order against that state. If the account is killed, the order is dropped. If it's not, the order goes through. Either way, the decision is written to the audit topic."

> "And then there's the Operator Console — a simple REST API. POST /kill, POST /unkill. This is the 'direct and exclusive control' the rule requires. A human can kill or unkill at any time, regardless of what Spark thinks."

**Key principle — say this explicitly:**

> "Notice the separation. Detection is separate from control is separate from enforcement. Spark detects. The compacted topic is the control plane. The router enforces. If Spark goes down, the last known kill state is still enforced. If a human spots something Spark didn't, they can kill directly through the API."

---

## SECTION 5: Kafka Deep Dive (3 minutes)

> *Slide 5: Kafka — The Event Backbone*

> "You've been working with Kafka in this class. Here's how it shows up in a real system."

> "We have six topics. Each one has a specific job."

Point to the topic list on the slide, then focus on compaction:

> "The interesting one is `killswitch.state.v1`. This is a compacted topic. Kafka's log compaction means it keeps only the latest value per key. The key here is the scope — like `ACCOUNT:12345`."

> "So if account 12345 was killed, then unkilled, then killed again — the compacted topic has exactly one record: the latest state."

> "Contrast that with the commands topic, which has every command ever issued. Commands topic is your audit trail — everything that ever happened. State topic is your current truth — what's true right now."

> "Any new service that joins the system can read the state topic from the beginning and immediately know the current state of every kill switch. That's the power of compaction."

---

## SECTION 6: Spark Windowing and PySpark (5 minutes)

> *Slide 6: Spark Windowing*

> "You learned about windowing in weeks 9 and 10. Here's what it looks like applied to a real problem."

Point to the window visualization on the slide:

> "We're using 60-second tumbling windows, grouped by account ID. Every 60 seconds, Spark computes a summary for each account: how many orders, how much total dollar exposure, which symbols."

Show the code snippet:

> "This is the actual code. `withWatermark` tells Spark how late data can arrive. `groupBy` with `window` and `account_id` creates the buckets. And then we aggregate — count, sum, collect_list for computing symbol concentration."

> *Slide 7: Three Thresholds*

> "From those aggregations, we check three thresholds."

Go through each one:

> "**Order rate** — more than 100 orders in 60 seconds. A human can't do that. That's a bot, and if it's not supposed to be running that fast, something is wrong."

> "**Notional value** — more than a million dollars in 60 seconds. Too much exposure accumulating too quickly."

> "**Symbol concentration** — more than 70% of orders in a single symbol. That's either a broken algorithm hammering one stock, or deliberate manipulation."

> "Knight Capital's algorithm would have tripped all three of these within seconds."

---

## SECTION 7: Kafka and EMR on AWS (3 minutes)

> *Slide 9: Why AWS*

> "Everything we just talked about runs locally on Docker. But in production, you'd run this on AWS. And the nice thing is: every component has a managed service equivalent."

Go through the list:

> "**MSK Serverless** — that's managed Kafka. You don't run brokers, you don't manage ZooKeeper, you don't worry about storage. AWS handles all of that."

> "**EMR Serverless** — managed Spark. You submit a job, it scales up, processes your data, scales down. You pay for what you use."

> "**Lambda** — your functions run without servers. The order router, the kill switch aggregator, the operator console — they're all Lambda functions."

> "The whole system runs for about five dollars an hour on AWS."

---

## SECTION 8: Kill Switch Lifecycle (2 minutes)

> *Slide 8: Kill Switch Lifecycle*

> "Let me walk you through the full lifecycle."

Point to each step:

> "Normal operation — orders flowing, everything is ALLOW. Then Spark detects a breach. It emits a KILL command. The aggregator updates the state. The router starts dropping orders from that account. An operator reviews and decides it's safe to resume. They issue an UNKILL. Orders flow again."

> "Automatic detection, manual recovery. Every step audited. That's the regulatory requirement in action."

---

## SECTION 9: Live Demo (8-10 minutes)

> *Slide 10: Live Demo*

> "Let's see it run."

Switch to terminal and browser.

### 9a. Show Normal Operation (2 min)

Open AKHQ (localhost:8080). Click Topics.

> "Here are all six topics. You can see the message counts climbing — orders are flowing."

Click into `orders.v1`, show a message:

> "Each order has an ID, timestamp, account, symbol, side, quantity, price, and strategy."

Show the router logs:

```bash
docker compose logs order-router --tail 10
```

> "Everything is ALLOW. The system is healthy."

### 9b. Trigger the Kill Switch (3 min)

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"suspicious trading activity"}'
```

> "One curl command. I just killed account 12345."

Show propagation:

```bash
docker compose logs killswitch-aggregator --tail 5
```

> "The aggregator picked up the command and updated the state."

```bash
docker compose logs order-router --tail 10
```

> "And now the router is dropping orders from account 12345. Look — DROPPED, DROPPED, DROPPED. But orders from other accounts are still flowing."

In AKHQ, click `audit.v1`, find a DROP message:

> "Every decision is audited. This shows the decision was DROP, the account, the reason, and a correlation ID that traces back to the original kill command."

> "One curl command stopped all trading for that account across the entire system in under a second. That's what 'direct and exclusive control' means."

### 9c. Recovery (2 min)

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"cleared after review"}'
```

```bash
docker compose logs order-router --tail 5
```

> "Account 12345 is active again. Orders are flowing. And the unkill is also audited — you can trace the full lifecycle."

### 9d. Show Automatic Detection (2 min)

```bash
docker compose logs killswitch-aggregator --tail 20
```

> "While we were talking, Spark has been running in the background. Look — it's already detected some accounts with high symbol concentration and auto-killed them. No human involved in the detection. But recovery still requires a human."

---

## SECTION 10: Try It Yourself (2 minutes)

> *Slide 11: Try It Yourself*

> "Everything I just showed you is in a public GitHub repo. You can run it on your laptop right now."

Show the three commands:

> "Clone it. cd into local. docker compose up. That's it. Kafka, Spark, all four services, the Kafka UI. Zero cost."

> *Slide 12: Terraform*

> "If you want to deploy to AWS, the entire infrastructure is defined in Terraform. Eight modules. One command to deploy, one command to tear it down. This is how real teams manage cloud infrastructure — not clicking through the AWS console."

> *Slide 13: AWS Deployment + Costs*

> "The AWS deployment costs about five dollars an hour. Deploy before a demo, destroy after. Less than a coffee."

---

## SECTION 11: Exercises and Call to Action (2 minutes)

> *Slide 15: Get Involved*

> "The repo has 10 exercises if you want to go deeper. Here are a few:"

Pick 2-3 that are relevant to their course projects:

> "**Add a symbol-level kill switch** — right now we kill by account. What if you want to halt trading in a specific stock? That's exercise 1, it's a good beginner exercise."

> "**Build a real-time dashboard** — consume from the Kafka topics, visualize order rates and kill switch state. Exercise 6."

> "**Multi-window risk detection** — instead of just 60-second windows, detect across 1-minute, 5-minute, and 15-minute windows simultaneously. Exercise 4. That directly builds on what you learned in streaming week."

> "If you're working on your course project and want to add a streaming component or a detection pipeline, these patterns apply directly."

---

## SECTION 12: Career Relevance and Close (2 minutes)

> *Slide 14: Career*

> "Last thing. These aren't academic technologies. Kafka is running at LinkedIn, Netflix, Uber, every major bank. Spark Streaming powers fraud detection at Capital One. Terraform is on every cloud engineering job listing."

> "The patterns we covered today — streaming detection, event-driven architecture, kill switches, audit trails — they show up everywhere. Fraud detection, infrastructure monitoring, IoT, content moderation. If you can reason about a system like this, you can talk about it in an interview."

> "The repo is public. Clone it, break it, extend it. Questions?"

---

## Q&A Prep

Common questions and answers:

**"What happens if Kafka goes down?"**
> In production, MSK is multi-AZ with replication — it's designed not to go down. Locally, if Kafka dies, everything stops. It's the backbone.

**"Why not use a database for kill state?"**
> You could. But Kafka compaction gives you real-time pub/sub AND durable state in one system. A database would need polling or change data capture.

**"How does this scale?"**
> MSK scales automatically. EMR scales automatically. Lambda scales automatically. The hard part is the architecture — and the architecture is what we just walked through.

**"Is this real production code?"**
> No. It's educational. Production adds encryption at rest, API authentication, secrets management, disaster recovery. But the patterns are real.

**"Could you use Flink instead of Spark?"**
> Absolutely. Flink is actually better for low-latency streaming. We used Spark because that's what you know from this course. The architecture doesn't change.

**"How long did this take to build?"**
> The Terraform and services are maybe 2,000 lines of Python and 2,000 lines of HCL. A few weeks of focused work. The local Docker Compose version is much simpler.

---

## Timing Summary

| Section | Duration | Running Total |
|---------|----------|---------------|
| Who I am | 2 min | 2 min |
| Knight Capital story | 5 min | 7 min |
| The rule + requirements | 4 min | 11 min |
| Architecture | 5 min | 16 min |
| Kafka deep dive | 3 min | 19 min |
| Spark windowing + PySpark | 5 min | 24 min |
| AWS services | 3 min | 27 min |
| Kill switch lifecycle | 2 min | 29 min |
| Live demo | 8-10 min | 37-39 min |
| Try it yourself + exercises | 2 min | 39-41 min |
| Career + close | 2 min | 41-43 min |
| Q&A | 5-10 min | ~50 min |

If running long, cut the Kafka deep dive (they know Kafka) and the kill switch lifecycle slide (covered in demo). That saves 5 minutes.

If running short, expand the demo — show a global kill, show the code, let students ask questions during the demo.

---

## If Things Go Wrong

**Docker isn't running:** You should have started it 15 minutes before class. If it fails, have screenshots of a working demo as backup. The architecture walkthrough carries the talk.

**Spark container crashes:** The rest of the system works fine. Demo manual kill/unkill. Mention that this actually demonstrates separation of concerns — detection is down, but enforcement is still running.

**Network issues in classroom:** Everything runs on localhost. No internet needed for the demo.

**Nobody asks questions:** Have 2-3 questions ready to ask THEM. "What would you add to this system?" "Which exercise interests you most?" "Where else could you apply this pattern?"
