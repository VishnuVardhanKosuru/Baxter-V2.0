@ui_form_validation_—_negative
@authentication
@fr_001
Feature: User Registration & Authentication
  Allow new customers to create an account using email/password or federated OAuth 2.0 login (Google, Facebook), and allow returning customers to authenticate securely.

  Background:
    Given The ShopSphere application is running and accessible
    And User has a valid, unused email address (for email/password registration) or an existing Google/Facebook account

  Scenario: Login with invalid password
    Given I am on the Login page
    When I attempt to log in with the following credentials:
      | email            | password         |
      | user@example.com | WrongPassword123 |
    Then I should see the error message "Invalid email or password"
    And I should remain on the Login page