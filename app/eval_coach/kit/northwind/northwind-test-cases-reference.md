# Test cases: Northwind end-of-week update

<!-- Catch-up copy. Use this file only if you do not have your own Part 2 test cases. -->

## Test input
- Mon: standup and two Northwind client meetings about the new reporting feature
- Mon–Tue: worked on the Northwind reporting feature
- Wed: helped onboard a new teammate
- Wed: prepared and ran the Northwind demo
- Thu: blocked for half a day waiting on client test data access; worked on documentation instead
- Thu: attended the internal AI lunch & learn
- Fri: fixed issues from demo feedback; reviewed a Contoso estimate

## Criteria

### C1: Length
- Requirement: It must be under 150 words
- Type: Format
- Threshold: Word count under 150 passes

### C2: Grouped by client
- Requirement: Group the work by client, not by day
- Type: Format
- Threshold: Passes only if Northwind, Contoso and Internal all appear as labels and no day name is used as a label

### C3: Blocker and ask
- Requirement: Call out the blocker and what you need to resolve it
- Type: Content
- Threshold: Passes if a "Blocker:" label and a "Need:" label both appear

### C4: Teams, not email
- Requirement: Sent as a Teams message, not an email
- Type: Format
- Threshold: Passes if none of "Subject:", "Dear", "Regards", "Sincerely" appear

### C5: Factual tone
- Requirement: Factual, not self-promotional
- Type: Format (proxy)
- Threshold: Passes if zero words from the banned list appear and there are no exclamation marks

### C6: Uses the rough notes
- Requirement: Turn the rough notes into the update
- Type: Content
- Threshold: Passes only if every note item is found by keyword (estimate, onboard, demo, lunch, documentation, reporting feature)

## Supporting lists
- Banned words: excited, thrilled, proud, amazing, incredible, awesome, delighted, successfully, crushed, "happy to report"
- Required labels: Northwind, Contoso, Internal, Blocker:, Need:
