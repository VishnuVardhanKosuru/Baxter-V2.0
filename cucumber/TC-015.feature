@ui_form_validation_and_redirect @checkout_and_payment @fr_004
Feature: Checkout & Payment Processing
  Provide a unified two-step checkout flow supporting guest checkout, saved addresses, and saved/new payment methods processed through Stripe.

  Background:
    Given a user has added an in-stock item to their cart
    And the user is on the cart page

  Scenario: Successful checkout with valid payment details
    When the user proceeds to checkout
    And the user enters shipping details and selects a shipping method
      | Full Name  | Address Line 1 | City    | State | Zip Code | Phone          | Shipping Method   |
      | John Doe   | 123 Main St    | Anytown | CA    | 90210    | 555-123-4567   | Standard Shipping |
    And the user enters Stripe test card details
      | Card Number         | Expiry Date | CVC |
      | 4242 4242 4242 4242 | 12/26       | 123 |
    And the user clicks "Place Order"
    Then the payment should be confirmed and the order status set to "Confirmed"
    And the user should see an order confirmation screen with the order number