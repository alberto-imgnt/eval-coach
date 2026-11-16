# Test cases: customer support reply

## Test input
- Customer: order 4821 arrived damaged and the customer wants a refund or a replacement

## Criteria

### C1: Length
- Requirement: Keep the reply under 120 words
- Type: Format
- Threshold: Word count under 120 passes

### C2: Order number
- Requirement: Mention the order number
- Type: Content
- Threshold: Passes if the text "4821" appears

### C3: Offer
- Requirement: Offer a refund or a replacement
- Type: Content
- Threshold: Passes if at least 1 of refund, replacement appears

### C4: No delivery promise
- Requirement: Do not promise a delivery date
- Type: Format
- Threshold: Passes if none of "tomorrow", "by Friday", "next week" appear
