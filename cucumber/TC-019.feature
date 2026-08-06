@ui_element_interaction @wishlist @fr_008
Feature: Wishlist & Product Reviews
  Allow registered customers to save products to a wishlist and submit star ratings with written reviews for purchased products.

  Background:
    Given a registered customer is logged in

  Scenario: Add a product to the wishlist from its detail page
    Given I am on the product detail page for 'ShopSphere Smartwatch'
    When I click the 'Add to Wishlist' icon
    Then the product 'ShopSphere Smartwatch' should be added to my wishlist
    And the 'Add to Wishlist' icon should be in an active state
    And a success message 'Product added to wishlist!' should be displayed