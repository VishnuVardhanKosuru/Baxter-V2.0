@ui_element_interaction@order_management@fr_005
Feature: Order Management & Tracking
  Allow customers to view order history, track real-time fulfillment status, cancel eligible orders, and initiate returns.

  Background:
    Given a registered customer is logged in
    And has an order in 'Confirmed' status
    And the order is within the cancellation window

  Scenario: Cancel an order within the allowed window
    Given I am on the 'My Orders' page
    When I open the details for an order with status 'Confirmed'
    And I click the 'Cancel Order' button
    And I confirm the cancellation
    Then The order status should change to 'Cancelled'
    And A cancellation confirmation message should be displayed
    And The system should initiate a refund process
    And The inventory for the cancelled items should be restocked