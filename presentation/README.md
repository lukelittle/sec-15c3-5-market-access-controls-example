# Presentation Materials

Everything you need to deliver a 40-50 minute talk on this project.

## Section Files

The talk is broken into 10 sections, each in its own file with full speaker notes, code walkthroughs, presenter tips, and timing guidance.

| # | File | Topic | Duration |
|---|------|-------|----------|
| 1 | [01-introduction.md](01-introduction.md) | Who you are + the Knight Capital story | 7 min |
| 2 | [02-the-rule.md](02-the-rule.md) | SEC Rule 15c3-5 requirements | 4 min |
| 3 | [03-architecture.md](03-architecture.md) | System architecture walkthrough | 5 min |
| 4 | [04-kafka-deep-dive.md](04-kafka-deep-dive.md) | Kafka topics, compaction, schemas | 4 min |
| 5 | [05-spark-windowing.md](05-spark-windowing.md) | Line-by-line `risk_detector_local.py` walkthrough | 7 min |
| 6 | [06-order-routing.md](06-order-routing.md) | Order router enforcement code | 4 min |
| 7 | [07-kill-switch-lifecycle.md](07-kill-switch-lifecycle.md) | Aggregator + operator console | 3 min |
| 8 | [08-live-demo.md](08-live-demo.md) | Full demo script with exact commands | 8-10 min |
| 9 | [09-exercises.md](09-exercises.md) | Hands-on exercises with code changes | 2 min |
| 10 | [10-close.md](10-close.md) | Career relevance, Q&A prep, closing | 4 min |

**Total: ~48-50 minutes** (including Q&A buffer)

## Other Materials

| File | What It Is |
|------|-----------|
| [SCRIPT.md](SCRIPT.md) | Condensed single-file script (bullet-point version) |
| [EXERCISES.md](EXERCISES.md) | Full exercise descriptions for students |
| [../docs/presentation.pptx](../docs/presentation.pptx) | 15-slide deck (dark navy theme) |
| [../docs/05-run-demo.md](../docs/05-run-demo.md) | Standalone demo instructions |

## Quick Prep

1. Read the section files in order (01 through 10)
2. Start Docker 15 min before: `cd local && docker compose up --build -d`
3. Open slides, AKHQ (localhost:8080), and a terminal
4. Give the talk

## If Running Long

Cut these sections first (saves ~5 min):
- **04-kafka-deep-dive.md** — reduce to 2 min (they know Kafka basics)
- **07-kill-switch-lifecycle.md** — skip (covered during the demo)
- **08-live-demo.md** — skip the global kill and compacted topic parts

## If Running Short

Expand the demo:
- Show a global kill (the nuclear option)
- Trigger panic mode and watch Spark auto-detect
- Walk through AKHQ message contents in detail
- Let students ask questions during the demo
