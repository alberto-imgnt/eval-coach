# Course context: what came before the app

eval-coach teaches **Part 3: running evals and baseline**. This document records what the participant has already learned in Part 1 (structured prompting) and Part 2 (defining evaluation criteria), and where the rest of the series goes. It is background for writing app content, lessons and the Parts 1 and 2 material the app covers. It is not shown to participants.

Two documents say what the whole series is for and what Stage 3 asks for, and they come first when a question is about intent or certification: [SERIES-INTENT.md](SERIES-INTENT.md) (the purpose: judge AI work and trust it because it was checked; the method; the six Parts; why it matters; the Stage 3 link) and [STAGE3-TASK-SPEC.md](STAGE3-TASK-SPEC.md) (what the Stage 3 task is: the Prompt, the Evaluations and the Log). The Part names below are the intent's names. This document adds the example and the Part 1 and 2 detail; if it disagrees with those two documents about intent or Stage 3, they win.

Source material: the Part 1 and Part 2 session plans, decks and handouts (OneDrive, read-only). Only their content and deliverables matter here, not when they were delivered or how they were run.

## The series

The series is "Evaluated Systems (Stage 3)". Its goal: **every participant, technical or not, can submit a Stage 3-ready task with documented, runnable test cases.**

Series principles:
- Parts 1 to 5 use the same example throughout (the Northwind weekly update). It is a learning sample and is never a submission option. Participants read it as the "Practice task"; "Northwind" appears only inside the example's own text. Participants read "your AI" and "AI window" where this document says CLI. Mission lessons (Parts 1 to 3) share one shape (the goal, why it matters to you, what you will do, what you leave with), show no map of the Parts, and Part 1's mission alone carries the series framing (OpenSpec change `content-clarity`).
- Part 6 is reserved for the participant's own task.
- Two lanes for evaluations: non-technical participants write markdown test cases and have an AI agent build and run a deterministic checker (the app's **Script track**); developers can use promptfoo (the **promptfoo track**).
- Tool-agnostic: any agentic tool that can run code (for example GitHub Copilot or Claude).
- The free Copilot Chat was found to be insufficient (it cannot run code or work with files). Participants were told in Part 2 to request a license for an approved tool before Part 3. The app must never suggest Copilot Chat.
- Every evaluation criterion traces to a stated task requirement, and the set covers both format and content.

| Part | Topic | The participant leaves able to | App coverage |
|---|---|---|---|
| 1 | Structured prompting | Name the parts of a framework, rewrite a vague prompt into a structured one, explain why each instruction is there, hand-score an output against requirements | **Built** on the stand-in (see [SPEC.md](SPEC.md) "Part 1") |
| 2 | Defining evaluation criteria | Turn requirements into 3+ criteria that test real quality, give each a runnable pass/fail threshold, document them as markdown test cases | **Built** on the stand-in (see [SPEC.md](SPEC.md) "Part 2") |
| 3 | Running evals and baseline | Have an agent build a checker, check the checker can be trusted, run it on five outputs from a mid-tier model, record per-criterion baseline scores in the iteration-log format | **Built** (see [SPEC.md](SPEC.md)) |
| 4 | Iterating with evaluation-driven development (EDD) | Confirm the checker scores 95%+ on a known-good output, run a red/green/refactor cycle, document two iterations | Coming soon (Series map row) |
| 5 | Load-bearing audit and packaging | Map every prompt instruction to the criterion it serves, cut or rework the rest to reach 90%+ load-bearing, package the submission | Coming soon (Series map row) |
| 6 | Own task | Brainstorm tasks, run each through a fit check (repeatable, clear requirements, output checkable by rules), leave with one chosen task. A task from their own work is recommended, not required; the aim is to apply the method in a way that is relevant to them | Informational only: Part 6 is a live troubleshooting meeting where people share and discuss ideas for their submission. The Series map row says it is a "Live meeting" and what it is about (no office hours, AIR discussion, people or places). The one pointer to office hours and the AIR discussion stays a single note in `baseline-why` |

How the parts feed each other: the Part 1 prompt and hand-scoring become the Part 2 criteria; the Part 2 markdown test case file is the input to Part 3, where an agent turns it into a checker. The app's `test-cases.md`, `prompt-v0.md` and `check.py` follow that chain.

**Course structure in the app (Part 3).** The course is seven concept lessons, one concept each, in the order of the series method (ask clearly, know what you need, turn it into rules, score the result, improve, keep a record): `mission`, `hook`, `several-runs`, `rules`, `trust`, `surprise` and `baseline-why`. The procedure is carried by the nine steps (`generate`, `build`, `fixtures`, `readback`, `predict`, `key`, `run`, `fix`, `baseline`), which sit between the lessons; the roles of the two chats, the blind folder, five runs, the checker layout and the fixture order are explained in the step that does them, as this course's way of working and not the only way. The lessons never replace the steps and the steps never teach the idea. The course list groups lessons and steps under six headings that follow the method. The mission carries the series purpose, why checking matters and a six-row map of the Parts; `baseline-why` ends with a short Stage 3 note built on the Prompt, Evaluations and Log structure. Content is ranked tier 1 core knowledge, tier 2 context, tier 3 certification (see "Learning priorities" in [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md)). Lesson list and order: [PHASE3.md](PHASE3.md) and "Course and lessons" in [SPEC.md](SPEC.md).

## The shared example: Northwind weekly update

A Friday end-of-week update, sent to a project lead, written from rough notes. Northwind and Contoso are Microsoft sample company names, chosen so they are never mistaken for real clients.

Five requirements the participant "knows" but that are not in the notes (they stand for context people normally carry in their heads):
1. It is sent as a Teams message, not an email.
2. It is under 150 words.
3. Work is grouped by client (Northwind, Contoso, Internal), not by day.
4. It calls out the blocker and what is needed to resolve it.
5. The tone is factual, not self-promotional.

Rough notes:
- Mon: standup and two Northwind client meetings about the new reporting feature
- Mon to Tue: worked on the Northwind reporting feature
- Wed: helped onboard a new teammate
- Wed: prepared and ran the Northwind demo
- Thu: blocked for half a day waiting on client test data access; worked on documentation instead
- Thu: attended the internal AI lunch & learn
- Fri: fixed issues from demo feedback; reviewed a Contoso estimate

Why this scenario: everyone writes a weekly update whatever their role, the gaps are obvious without technical judgment, and because it recurs it shows the repeatability benefit.

## Part 1: structured prompting

**Core outcome: the why.** The participant understands why a framework gets better results and knows they can use an existing one or create their own. Part 1 does not recommend a framework, teach what every letter means, or measure quality.

**Method: discovery before theory.**
1. Write a cold prompt in their own words, one shot, no coaching.
2. Score the output against the five requirements.
3. Name the gaps and notice every gap was something the AI could not have known, because the prompt never said it.
4. Sort gaps into five plain-language buckets, then learn that people have named these buckets: those names are prompting frameworks.
5. Rewrite the prompt with a framework's labels in a new chat, run once, score again, compare.

**The five buckets and two sample frameworks:**

| Bucket | Example gap | RTCC | RISE |
|---|---|---|---|
| 1. Role: who the AI acts as | Sounded self-promotional | Role | Role |
| 2. What to produce | An email with a subject line, not a Teams message | Task | Steps |
| 3. Background | Did not know who the update was for | Context | Input |
| 4. Limits and format | Over 150 words; ordered by day | Constraints | Expectation (partly) |
| 5. A good result | Blocker buried, no clear ask | Constraints (partly) | Expectation |

These are sample frameworks. The letters use common expansions (RTCC: Role, Task, Context, Constraints; RISE: Role, Input, Steps, Expectation) and other sources define them differently. CO-STAR and RISEN are named as others that exist. The uneven fit is deliberate: each framework emphasizes some buckets more, yet both beat the cold prompt, which shows the benefit comes from structure, not from a particular framework. **When the app covers Part 1 it must say the same: frameworks shown are samples, buckets 4 and 5 map only partly, and covering the buckets matters more than the letters.**

**Four benefits a participant should be able to name:**
- **Completeness:** the AI guesses less because the prompt covers what it needs.
- **Better first results:** fewer rounds of back-and-forth.
- **Easier fixes:** when output misses, the framework shows which part of the prompt to change.
- **Repeatability:** the same structure works for the next task, and teammates can follow it.

**Takeaway:** "Give the AI what it needs. Use a framework, or build your own."

**Deliverables carried forward:** a before/after prompt pair with both outputs, and one real prompt from the participant's own work rewritten with a framework. In the app this homework becomes an exercise inside a lesson.

**Set aside for later parts:** invented details (hallucinations), judging output quality, and variation between runs of the same prompt. All belong to evaluation.

**The question that leads into Part 2:** real work does not come with a card of requirements, so how do you know the second output is better?

**How the app delivers it (OpenSpec change `add-part-1`).** The live session's methods carry over to self-paced, hands-on work with the participant's own CLI. The scenario card is shown inside the `cold` step, and the app adds the rough notes under the participant's own words, so both runs use the same notes. The "run it once, no second tries" rule is one captured run per step (the best-guess reply is a troubleshooting entry). The self-scored chat waterfall becomes a score form (five yes or no answers, one gap, "was it in my prompt?"); what other people typically notice is a bundled list of typical gaps, sorted into five common kinds of missing information in `p1-gaps` (an example, not a complete list) with a set-aside group for invented details and quality judgments. The reveal, the partial fits of kinds 4 and 5, CO-STAR and RISEN, and "or build your own" are in `p1-frameworks`. The two breakout groups become a choice of RTCC, RISE or the participant's own labels; the other framework is shown as a bundled sample after the rewrite, in `p1-benefits`. The compare questions are written answers in `rescore`, next to both prompts, outputs and scores. The homework is the `own` step. The four benefits, the takeaway and the open question close `p1-benefits`. Timing, slides and room logistics are not carried over.

## Part 2: defining evaluation criteria

**Core idea:** hand scoring becomes criteria precise enough for a machine to check. Nothing is run in Part 2; running starts in Part 3.

**Steps:**
1. **Recap** Part 1: a framework is a checklist, structured beats vague, hand scoring was reading the requirements and counting how many were met.
2. **Requirements to criteria.** Rules: every criterion traces to a stated requirement; the set covers both format and content; no two criteria check the same thing. Draft at least three, at least one on content.
3. **Pass/fail thresholds.** Give each criterion a rule a script could decide.
4. **Markdown test cases.** Record everything in the test case file.

**Format and content:**
- **Format** is how it looks (word count, labels). Format checks are legitimate when the task requires them.
- **Content** is what it says (the blocker, the ask, every note item present).
- **Bad-output test:** write a polished but wrong output; if it passes, the checks are window dressing. (From the series outline; it returns in Part 3's check that the checker can be trusted.)

**Thresholds:**
- Vague words such as "clear", "good" and "concise" become a number or a keyword.
- **Script test:** could a script decide this with no human judgment? If not, tighten it.
- Two patterns that carry to any task:
  - **Structure (preferred):** the prompt asks for fixed labels (for example `Blocker:` and `Need:`) and the threshold checks that those labels exist. Works for any scenario, is easy for non-technical participants, and links prompt instructions to criteria, which sets up Part 5's load-bearing audit.
  - **Required term:** a key fact from the input appears in the output.

**Reference criteria for Northwind:**

| ID | Criterion | Type | Pass/fail rule |
|---|---|---|---|
| C1 | Length | Format | Word count under 150 |
| C2 | Grouped by client | Format | Northwind, Contoso and Internal all appear as labels and no day name is used as a label |
| C3 | Blocker and ask | Content | A `Blocker:` label and a `Need:` label both appear |
| C4 | Teams, not email | Format | None of `Subject:`, `Dear`, `Regards`, `Sincerely` appear |
| C5 | Factual tone | Format (proxy) | No banned-list words and no exclamation marks |
| C6 | Uses the rough notes | Content | Every note item found by keyword (estimate, onboard, demo, lunch, documentation, reporting feature) |

**Tone is a proxy.** A banned-word list stands in for tone and can miss real tone problems. It is the example of where rule-based checks reach their limits.

**Banned list (Northwind reference only):** excited, thrilled, proud, amazing, incredible, awesome, delighted, successfully, crushed, "happy to report", plus exclamation marks. Participants write their own list for their own task and keep it in their test case file so the check stays runnable. If the prompt also tells the model to avoid those words, the instruction and criterion line up, which supports Part 5.

**Examples used to teach the criteria:**
- Passing update (about 75 words): sections for Northwind, Contoso and Internal, with a line `Blocker: lost half a day Thu waiting on client test data access. Need: access granted before Monday so testing can continue.`
- Failing for C3: "Thu: worked on documentation" (blocker hidden, no ask) and "Had a small delay on Thursday" (vague, no cause, no ask).
- Failing for C1: a day-by-day version repeating every note and running past 150 words.

**Test case file format** (the file the app's parser reads):

```markdown
# Test cases: <task name>

## Test input
<the input the prompt works from>

## Criteria

### C1: <short name>
- Requirement: <the stated requirement it traces to>
- Type: <Format or Content>
- Threshold: <pass/fail rule a script can decide>

## Supporting lists
- Banned words: word1, word2, word3
```

Sections: test input, criteria (ID, requirement, type, threshold), supporting lists. A threshold points at a list; the list lives in the same file.

**Deliverable carried forward:** the markdown test case file. A participant also arrives at Part 3 with an agentic tool license (requested in advance) and Python or Node.js installed.

**How the app delivers it (OpenSpec change `add-part-2`).** The live session's methods carry over to self-paced work with no CLI, because nothing is run. The scenario card is shown inside the `draft` step, and the participant's own Part 1 marks and gap appear there when they exist (read-only, optional). The recap becomes the `p2-mission` page, which opens on Part 1's question. The live session's two worked criteria (length, and the blocker and ask) are the only Northwind criteria in the lessons; the rest are left for the participant to find. One worksheet is shared by `draft` and `thresholds`, and the Threshold column appears in the second step. The self-check is two ticks in `draft`, and the script test is a lesson passage, a sort activity and a tick in `thresholds`, with non-blocking notes on vague words. The `test-file` step builds the markdown test case file from the worksheet; the participant edits and saves it in `part-2\test-cases.md` and passes the file checks. The live session's reference tables are shown only in the `reference` step, after the file is done; the review of a partner's criteria becomes a choice per reference criterion ("I had this one", "I missed this one", "Mine differs but works", "Mine was too vague"). The Northwind reference file is also part of Part 3's kit, so the app guarantees a discovery order inside Part 2, not a seal. The participant writes their own banned or required list; none is pre-filled, and the Northwind list is shown only in `reference`. Part 3 is not wired to load the Part 2 file: its "My own files" import accepts it. Timing, slides and room logistics are not carried over.

## Open items for app implementation

- **Banned words (resolved by `add-part-2`):** Part 2 has participants write and store their own list in the `Supporting lists` section of their test case file. The app pre-fills none (the built file holds one example line with no Northwind word), the Northwind list appears only in the `reference` step marked as the example's own, and a threshold that points to a list with no entry gets a non-blocking note. The existing banned-word scans in `tests/test_content_banned_words.py` still guard the content.
- **Terminology:** the app uses "Part" (or "phase") for what the source material calls sessions. Do not carry over dates, session numbers, facilitator, breakout-room or chat-based wording (see the plain-language rule in [SPEC.md](SPEC.md)).
- **Homework:** the "bring one real prompt rewritten with a framework" task becomes a lesson exercise. The content is what matters, not the source wording.
