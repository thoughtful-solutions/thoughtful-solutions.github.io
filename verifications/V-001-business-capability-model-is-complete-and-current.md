# V: Business capability model is complete and current

(Verification that the business capability model contains all required capabilities with assigned owners, maturity scores, and current business value metrics to support strategic decision-making.)

## Gherkin Verification

```gherkin
Feature: Verification for Business Capability Model Completeness
  As an Enterprise Architect
  I want to ensure the business capability model is complete and current
  So that strategic decisions are based on accurate capability assessment.

  Scenario: All Level 1 capabilities are defined with owners
    Given I have access to the business capability model
    When I analyze the capability hierarchy
    Then all Level 1 capabilities should be defined
    And each capability should have a clearly assigned owner
    And 90% of capabilities should have current maturity scores
    And business value metrics should be defined for critical capabilities

  Scenario: Capability data is current and traceable
    Given I have HR system API access
    When I query organizational structure data
    Then org chart data should be less than 24 hours old
    And capability ownership should be traceable to current employees
    And role definitions should be complete and current
```