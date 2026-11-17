# Spec Delta

## MODIFIED Requirements

### Requirement: Lessons stay short
Each lesson SHALL have a body of no more than 300 words, except a Part's first lesson (`mission`, `p1-mission`, `p2-mission`), which SHALL have no more than 450 words, and a Part's last lesson that also carries a closing orientation passage (`baseline-why`, `p1-benefits`, `p2-testfile`), which SHALL have no more than 400 words. Lessons are in plain language with no code.

#### Scenario: Word cap
- **WHEN** the content tests count each lesson body
- **THEN** none exceeds its cap
