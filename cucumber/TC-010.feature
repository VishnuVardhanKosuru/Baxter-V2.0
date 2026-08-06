@ui_field-level_validation
@shopping_cart
@fr_003
Feature: Shopping Cart Management
  As a Guest User or Registered Customer
  I want to manage my shopping cart
  So that I can purchase items efficiently

  Background:
    Given I am on the ShopSphere homepage

  Scenario: Cart Quantity Exceeds Available Stock
    Given a product "Limited Stock Item" with 3 units in stock is available
    And I am on the product page for "Limited Stock Item"
    When I add 1 unit of "Limited Stock Item" to the cart
    And I navigate to the shopping cart page
    And I attempt to set the quantity of "Limited Stock Item" to 5
    Then the quantity for "Limited Stock Item" should be capped at 3
    And I should see the warning message "Only 3 left in stock"