# Worked examples: two criteria

These two examples show how a criterion and its threshold are written, and how a passing and a failing text look next to them. They use the Northwind update, a made-up learning example that is never something to submit. They are the only criteria written out for you. Finding the rest is your job.

## A passing update

**Northwind**
- Two client meetings on the new reporting feature; built the feature Mon–Tue
- Prepared and ran the demo Wed; fixed demo feedback issues Fri
- Blocker: lost half a day Thu waiting on client test data access. Need: access granted before Monday so testing can continue.

**Contoso**
- Reviewed the estimate

**Internal**
- Onboarded a new teammate; attended the AI lunch & learn; worked on documentation while blocked

## Example 1: Length (format)

- Requirement: It must be under 150 words
- Type: Format
- Threshold: Word count under 150 passes

**Passes.** The passing update above has about 70 words.

**Fails.** This day-by-day version repeats every note and runs past 150 words:

> Monday: I attended the standup and then took part in two Northwind client meetings about the new reporting feature. Monday and Tuesday: I worked on the Northwind reporting feature and made steady progress on it. Wednesday: I helped onboard a new teammate and showed them how our projects are set up. Wednesday: I also prepared and ran the Northwind demo, which went well and gave us useful feedback from the client. Thursday: I was blocked for half a day waiting on client test data access, so I worked on documentation instead. Thursday: I attended the internal AI lunch and learn, where we heard about several new ideas for our own work. Friday: I fixed the issues from the demo feedback and reviewed a Contoso estimate for the project lead. Overall it was a busy week with many different activities, and I am looking forward to continuing the work on every project next week.

A script counts the words and gets the same answer every time. That is what makes it a good threshold.

## Example 2: Blocker and ask (content)

- Requirement: Call out the blocker and what you need to resolve it
- Type: Content
- Threshold: Passes if a "Blocker:" label and a "Need:" label both appear

**Passes.** The passing update above has both labels, with a reason for the blocker and the access that is needed.

**Fails.** Two texts that hide the problem:

> Northwind: reporting feature work and the demo. Thu: worked on documentation. Fri: fixed demo feedback.

The blocker is hidden inside an ordinary line, and nothing says what is needed.

> Northwind: reporting feature work and the demo. Had a small delay on Thursday.

The delay is vague, it has no cause and it makes no ask.

Both texts could be short and neat. Only a content criterion catches them.
