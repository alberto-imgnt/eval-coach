# Spec Delta

## MODIFIED Requirements

### Requirement: The two words are covered by tests that cannot be skipped
The content tests SHALL fail when "CLI" appears outside a vendor product name or the glossary entry, and when "Northwind" appears as an option name in participant-visible text. The tests SHALL check the text of every platform (Windows and Mac). The list of allowed places SHALL live in the test, not in the content. Source: series review items 15 and 16.

#### Scenario: A new bare CLI is caught
- **WHEN** a content string is changed to include "your CLI"
- **THEN** the content tests fail and name the file and the string

#### Scenario: A Mac-only string is caught
- **WHEN** a Mac platform entry is changed to include "your CLI"
- **THEN** the content tests fail and name the file, the key and the platform

#### Scenario: Allowed uses are explicit
- **WHEN** the tests run
- **THEN** each allowed use is a named exception with a reason
