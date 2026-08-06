@ui_dynamic_content_validation @order_management @fr_005
Feature: Order Management & Tracking
  Allow customers to view order history, track real-time fulfillment status, cancel eligible orders, and initiate returns.

  Background:
    Given a registered customer is logged in
    And at least one order exists for the customer with 'Shipped' status

  Scenario: Verify real-time order tracking updates
    Given I am on the 'My Orders' page
    When I select an order marked as 'Shipped'
    And I navigate to the order tracking timeline
    Then the tracking timeline should display the latest carrier scan event
    And the estimated delivery date should be visible