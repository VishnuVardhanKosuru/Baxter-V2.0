@ui_element_interaction @shopping_cart @fr_003
Feature: Shopping Cart Management
  Provide a persistent cart that survives login/logout, device switches, and browser sessions, backed by Redis with PostgreSQL as the durable store.

  Background:
    Given product is in stock (quantity > 0) at the time it is added.

  Scenario: Remove an item from the shopping cart
    Given I am on the product page for "Awesome Widget"
    And I add "Awesome Widget" to the cart
    And I am on the product page for "Super Gadget"
    And I add "Super Gadget" to the cart
    And I navigate to the shopping cart page
    When I click the remove button for "Awesome Widget"
    Then "Awesome Widget" should no longer be in the cart
    And the cart badge count should be 1
    And the cart total should reflect the remaining item