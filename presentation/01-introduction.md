# Section 1: Introduction and the Knight Capital Story

**Duration:** 7 minutes (2 min intro + 5 min story)
**Goal:** Hook the audience with a real disaster, establish why this system exists.

---

## 1A: Who You Are (2 minutes)

Open the title slide. Don't rush this — the audience needs to know why they should listen to you.

**Say something like:**

> "I'm [name]. I work in [area]. I built this project because I wanted to show you what it looks like when the things you're learning in this class — Spark, Kafka, AWS — come together to solve a real problem. Not a textbook problem. A problem that destroyed a company."

**What to hit:**
- Your name, your background, 1-2 sentences max
- Connect your experience to their curriculum (Spark, streaming, cloud)
- Tease the story — "destroyed a company" is the hook that keeps attention

**Don't do:**
- Don't read your resume. Nobody cares about your job history.
- Don't explain the project yet. The story comes first.

---

## 1B: The Knight Capital Story (5 minutes)

This is the most important five minutes of the talk. If you lose them here, you won't get them back. Tell it like a story, not a lecture. You're a narrator, not a professor.

### Beat 1: Set the Scene

> "August 1st, 2012. Knight Capital Group. They were one of the biggest electronic market makers in the United States — handling roughly 10% of all US equity trading volume. Billions of dollars flowing through their systems every day."

**Why this matters to say:** The audience needs to understand this wasn't some small shop. This was a pillar of the US financial system. The scale makes the failure dramatic.

### Beat 2: The Deployment

> "That morning, they deployed new trading software to their production servers. It was supposed to be routine. But an old piece of code — something called 'Power Peg,' which was supposed to have been deactivated years earlier — got accidentally reactivated on one of their eight servers."

**Why this matters to say:** This is a deployment bug. Every person in this room will deploy code to production someday. This is relatable.

### Beat 3: The Cascade

> "Within minutes, this code started sending millions of erroneous orders into the market. It was buying stocks at the ask price and selling at the bid price — the exact opposite of what a market maker does. It was doing this across 150 different stocks simultaneously."

**Pause here.** Let that sink in. Buying high, selling low, 150 stocks, millions of orders.

### Beat 4: The Inability to Stop

This is the critical beat. This is why this project exists.

> "The operations team realized something was wrong almost immediately. Within the first few minutes, they could see abnormal trading patterns. But here's the problem — and this is the whole point of today's talk — **there was no centralized kill switch.**"

> "There was no single button to press that says 'stop everything.' They had to manually log into individual servers and shut them down one by one. Some servers got missed. Some were restarted by automated systems. The bleeding continued."

**Emphasize:** The technology to detect the problem existed (they saw it). The technology to generate orders existed (obviously). What was missing was the technology to **stop** them. That's the gap.

### Beat 5: The Damage

> "Forty-five minutes. That's how long it took to fully stop the bleeding. In those forty-five minutes, Knight Capital accumulated $440 million in losses. That's more than the company was worth."

> "Knight Capital was acquired by Getco six months later at a fraction of its former value. A company that was a central piece of US market infrastructure effectively ceased to exist because of a software deployment gone wrong and the inability to stop it quickly."

### Beat 6: The Transition

> "So what happened after this? The SEC had actually already anticipated this kind of problem. Two years before Knight Capital's disaster, in 2010, they passed a rule specifically about this. Let's look at what that rule requires."

---

## Presenter Notes

**Common mistake:** Rushing through the story to get to the "technical stuff." Don't. The story is what makes every piece of code we show later feel important. Without the story, it's just another Kafka demo.

**If someone asks "could this happen today?":** Yes. In 2012, Knight had no kill switch. Today, Rule 15c3-5 requires one. But implementation quality varies. The 2020 BATS flash crash and various crypto exchange incidents show that the problem hasn't gone away — it's just moved to new markets.

**If someone asks about the $440M:** It was real trading losses from unfavorable executions, not a fine. The SEC separately fined Knight $12M for the incident. But the trading losses are what killed the company.

**Body language:** Stand, don't sit. Move to the front of the room for the story. Make eye contact. This is theater, not a code review.

---

## Timing Check

By the end of this section, you should be at **7 minutes**. If you're at 10, you talked too much about yourself. If you're at 5, you rushed the story — slow down on the next section.
