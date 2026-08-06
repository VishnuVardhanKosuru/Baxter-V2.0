@ui_element_interaction @shopping_cart @fr_003
Feature: Shopping Cart Management
  Provide a persistent cart that survives login/logout, device switches, and browser sessions, backed by Redis with PostgreSQL as the durable store.

  Background:
    Given Product is in stock (quantity > 0) at the time it is added.

  Scenario: Update quantity of an item in the cart
    Given I am on the cart page with "ShopSphere T-Shirt" added with quantity 1
    When I increase the quantity of "ShopSphere T-Shirt" by 1 using the stepper control
    Then The quantity of "ShopSphere T-Shirt" should be 2
    And The item subtotal and cart total should be updated accordingly
    And The updated quantity should persist after refreshing the page