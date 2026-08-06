@ui_element_interaction @shopping_cart @fr_003
Feature: Shopping Cart Management
  Provide a persistent cart that survives login/logout, device switches, and browser sessions, backed by Redis with PostgreSQL as the durable store.

  Background:
    * Product is in stock (quantity > 0) at the time it is added.

  Scenario: Add an in-stock product to the cart
    Given I am on the product detail page for "ShopSphere T-Shirt" (P001)
    When I select size "Medium"
    And I click the "Add to Cart" button
    Then the cart badge count should display "1"
    And a mini-cart confirmation drawer should display "ShopSphere T-Shirt (Medium)" with the updated subtotal