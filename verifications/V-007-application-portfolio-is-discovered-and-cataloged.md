# V: Application portfolio is discovered and cataloged

(Verification that 95% of production applications are automatically discovered and cataloged with business criticality, technical health, dependencies, and cost information.)

## Gherkin Verification

```gherkin
Feature: Verification for Application Portfolio Discovery
  As an Application Architect
  I want to ensure the application portfolio is completely discovered and cataloged
  So that portfolio optimization decisions are based on complete and accurate data.

  Scenario: Production applications are automatically discovered
    Given I have automated discovery tools scanning infrastructure
    When I analyze application inventory completeness
    Then 95% of production applications should be automatically discovered
    And each application should have business capability mapping
    And technical health scores should be current within 24 hours
    And business criticality should be assigned based on usage patterns

  Scenario: Application dependencies and costs are documented
    Given I have infrastructure monitoring and cost management tools
    When I validate application dependency data
    Then service dependencies should be automatically mapped
    And infrastructure costs should be allocated to applications
    And performance metrics should be collected for all critical applications
    And redundant or underutilized applications should be identified
```