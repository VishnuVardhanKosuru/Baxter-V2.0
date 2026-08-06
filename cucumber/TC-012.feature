@ui_form_validation @coupons_and_discounts @fr_010
Feature: Coupon & Discount Engine
  Allow customers to apply promotional coupon codes at checkout, with validation of eligibility rules.

  Background:
    Given a valid, active coupon code "WELCOME10" exists in the system with a 10% discount and $50 minimum threshold

  Scenario: Apply a valid coupon code at checkout
    Given I am on the checkout review page with a cart subtotal of "$100.00"
    When I enter "WELCOME10" into the coupon code field
    And I click the "Apply" button
    Then a "10%" discount of "$10.00" should be applied and itemized as "Discount (WELCOME10)" in the order summary
    And the order total should update to "$90.00"