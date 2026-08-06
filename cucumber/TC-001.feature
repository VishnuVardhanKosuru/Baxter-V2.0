@ui_form_validation@registration@fr_001
Feature: User Registration & Authentication
  Allow new customers to create an account using email/password or federated OAuth 2.0 login (Google, Facebook), and allow returning customers to authenticate securely.

  Background:
    Given User has a valid, unused email address for registration

  Scenario: Successful user registration with valid credentials
    Given I am on the ShopSphere homepage
    When I click on the "Sign Up" link
    And I am on the registration page
    And I fill in the registration form with:
      | Field      | Value             |
      | Email      | unique.user@test.com |
      | Full Name  | Test User         |
      | Password   | Secure@123        |
    And I click the "Create Account" button
    Then I should be redirected to the homepage
    And I should see a success message "Registration successful! Welcome to ShopSphere."
    And I should be logged in as "Test User"