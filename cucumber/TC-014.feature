@ui_multi-page_navigation @checkout @fr_004
Feature: Checkout & Payment Processing
  Provide a unified two-step checkout flow supporting guest checkout, saved addresses, and saved/new payment methods processed through Stripe.

  Background:
    Given a cart contains at least one in-stock item with a valid shipping destination supported by the platform

  Scenario: Guest user can successfully complete a full checkout flow
    Given I am on the product page for "ShopSphere T-Shirt"
    When I add "1" item to the cart
    And I proceed to checkout as a guest
    And I enter the following shipping details:
      | Field          | Value             |
      | First Name     | John              |
      | Last Name      | Doe               |
      | Address Line 1 | 123 Test St       |
      | City           | Anytown           |
      | State          | CA                |
      | Zip Code       | 90210             |
      | Email          | guest@example.com |
      | Phone          | 555-123-4567      |
    And I enter the following payment details:
      | Field           | Value                  |
      | Card Number     | 4242 4242 4242 4242    |
      | Expiry Date     | 12/26                  |
      | CVC             | 123                    |
      | Cardholder Name | John Doe               |
    And I place the order
    Then I should see the order confirmation page
    And the order should be placed successfully without account creation
    And an order-tracking link should be emailed to "guest@example.com"