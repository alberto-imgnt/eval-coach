# Test cases: customer support reply

## Criteria

### C1: Length
- Requirement: Keep the reply under 120 words
- Type: Format
- Threshold: Word count under 120 passes

### C2: Calm punctuation
- Requirement: No shouting
- Type: Format
- Threshold: Passes if there are no exclamation marks

### C3: No email wording
- Requirement: Not an email
- Type: Format
- Threshold: Passes if none of "Subject:", "Dear", "Regards" appear

### C4: Short opening
- Requirement: Start with a greeting
- Type: Format
- Threshold: Starts with "Hi"
