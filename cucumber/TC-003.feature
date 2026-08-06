@ui_form_validation_and_redirect
@authentication
@fr_001
Feature: User Registration & Authentication
  Allow new customers to create an account using email/password or federated OAuth 2.0 login (Google, Facebook), and allow returning customers to authenticate securely.

  Background:
    Given I am on the Login page

  Scenario: Login with valid credentials
    When I enter the following credentials:
      | Field    | Value                  |
      | email    | user@example.com       |
      | password | SecurePassword123!     |
    And I click the "Log In" button
    Then I should be redirected to the homepage
    And I should see a successful login indication