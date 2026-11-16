# Evaluated Systems
## Intent

By the end of this series, the goal is for you to have the knowledge and the techniques to judge the work AI gives you. Once you can judge it, you can trust it for the right reasons. That trust comes from checking the work, not from hoping it is right. This is true whatever your role, with or without a technical background.

You get there in two steps:

1. **Ask better.** You learn how a structured prompt differs from an unstructured one, and what structure gives you. The AI has to guess less, the first answer is better, problems are easier to fix, and you get the same quality each time.
2. **Check and improve.** You learn to say what "good" means, to score AI answers against it, and to improve your prompt with proof.

Put together, these skills let you decide when AI work is good enough to use, and explain to others why you trust it.

## What you will learn

You learn one method and use it again and again:

```
ask clearly --> know what you need --> turn it into rules --> score the result --> improve --> keep a record
```

| Part | You learn to | In simple words |
|---|---|---|
| 1. Structured prompting | See the difference between a structured and an unstructured prompt, and use structure to tell the AI what it needs | Weak AI answers usually come from things you knew but never said. You try the same task both ways, compare the answers, and see what structure gives you: fewer guesses, better first answers, easier fixes and results you can repeat. |
| 2. Defining evaluation criteria | Turn "that looks good" into clear rules | Words like "clear" or "short" become something you can check, like a word limit or a required label. |
| 3. Running evals and baseline | Measure instead of guess | You check five AI answers against your rules and write down a starting score. One good answer proves little, because AI answers change from one try to the next. |
| 4. Iterating with evaluation-driven development | Improve with proof | You change your prompt, check again with the same rules and compare. If the score did not move, the change did not help. |
| 5. Load-bearing audit and packaging | Keep only what works | Every instruction in your prompt must help meet at least one rule. You remove the rest and put your work together so someone else can use it. |
| 6. Your own task | Use it on your real work | You pick a task that repeats, has clear requirements and can be checked by rules. A task from your own job is the best choice, because it makes the method relevant to you, but any task that fits works. Part 6 is a live working meeting, where you can talk your ideas through. |

Along the way you also learn to **explain it**: in plain words to someone who is not technical, and in more detail to someone who is. Knowing the method is not enough if you cannot tell a colleague what it does and why it matters.

## Why it matters

- **AI sounds sure of itself even when it is wrong.** "It looks fine" is how a mistake, a wrong tone or a missing detail ends up in front of a client or a manager.
- **"Better" is often just an opinion.** Without a way to measure, changing a prompt is guesswork, and two people cannot settle who is right.
- **AI answers change from try to try.** Judging one answer is like judging a person by a single meeting. A score across several tries is the honest picture.
- **You can only trust AI if you can check it.** Trust that rests on a good feeling breaks the first time the AI is wrong. Trust that rests on clear rules, a score and a record holds up, and you can show it to others.
- **Proof builds trust.** A starting score, a recorded change and a score that moved let you say "this is reliable enough to use" and show why.
- **Good work can be shared.** Once a task has clear rules, a colleague can use it and get the same quality.
- **You do not need to write code.** You decide what "good" means. An AI agent builds the checker. People who like code can use a developer tool instead, and both end up with the same kind of record.

## How it helps in your day-to-day work

Whenever you use AI for work you do again and again, this method applies. Only the task changes.

| Kind of work | A task that repeats | What you can check |
|---|---|---|
| Working with clients (sales, account management) | A follow-up message after a client call | Names what the client asked for, gives a next step and date, makes no promise you are not allowed to make, stays short |
| Writing and communication (marketing, internal communications) | A product description or announcement from a brief | The key message is there, banned words are not, the call to action is included, the length is right |
| Managing and running things | A summary of a long email thread or meeting | Every decision and owner is listed, nothing is made up, the same headings every time (Decisions, Risks, Next steps) |
| Project and client delivery | A weekly update to a project lead | The right channel, under the word limit, grouped by client, the problem and what you need are stated, a factual tone |
| People and administration | A job description or a policy summary | Every required section is there, excluded wording is not, every must-have from the brief is included |
| Technical roles (engineering, data, testing) | A ticket summary, test ideas or review notes | The same method, with an optional developer tool |

These are examples of the idea. You will practice on one shared example, a weekly update, because everyone writes something like it.

There are two ways to work through the series:

- **Script track.** You write your rules in plain text, and an AI agent builds and runs the checker for you. No coding skills needed.
- **promptfoo track.** For people who prefer a developer tool.

## What to keep in mind

- The examples in this series are practice cases. They show you the techniques, and they are not the only way to check AI work. Your own tasks will be different, and the right rules will depend on what you are doing.
- Some things are hard to check with simple rules. In the practice example, tone can only be roughly checked with a list of words to avoid. Your own tasks may have other qualities that are hard to check, and this material cannot cover every one of them. When a rule cannot judge something, say so by marking it "not checked" instead of pretending.
- The goal is general knowledge and techniques that you can take to many different tasks. You will still need to think about what matters for each one.
- You are not asked to trust AI blindly, or to distrust it blindly. You are asked to say what good looks like and check for it.
- A good score tells you how one prompt did against one set of rules. It does not guarantee every future answer.

## How this connects to Stage 3 certification

Everything above is worth learning for its own sake. As a result, the work you produce also matches what the Stage 3 certification asks for.

For Stage 3, you submit a ZIP file with three things, and each is checked against the Stage 3 criteria. You can add a README file to explain how your files are organized.

| What you submit | What Stage 3 looks for | Where you build it |
|---|---|---|
| **The Prompt**: a text file with your prompt or command | A structured prompt (RTCC or a similar structure) | Part 1 |
| | Instructions chosen on purpose | Parts 1 and 5 |
| | At least 90% of your instructions each help meet at least one rule | Part 5 |
| | No filler or wasted words | Part 5 |
| **The Evaluations**: scripts, promptfoo files or written test cases | At least 3 different rules, not the same check worded three ways | Part 2 |
| | Real quality checks, not rules that only look good | Parts 2 and 3 |
| | Able to score 95% or higher when the prompt works well | Part 4 |
| | Works with mid-level AI models (for example Sonnet or GPT-4), with no top-end model needed | Part 3 |
| | Clear pass or fail limits, or a clear scoring guide | Part 2 |
| **The Log**: a record of how your prompt changed | At least 2 recorded rounds of improvement | Parts 3 and 4 |
| | Each round shows the starting score, your guess about what would help, the change you made, the new score and your reasoning | Parts 3 and 4 |
| | A test-first habit: write the checks, see them fail, improve the prompt until they pass, then tidy up | Part 4 |
| | A clear order of events, where each change leads to the next | Parts 3 to 5 |

In Part 6 you choose your own task, and that is the task you submit. The weekly update used for practice is only a learning example and is never a task you can submit.

This series teaches the skills. It does not certify you, score your submission or tell you how to submit. The Stage 3 program's own instructions decide what to submit.
