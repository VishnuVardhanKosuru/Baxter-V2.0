@ui_form_validation @admin_portal__catalog @fr_002
Feature: Product Catalog & Search
  Enable customers to browse the product catalog and search by keyword, with filtering by category, price range, brand, and rating, backed by an Elasticsearch index.

  Background:
    * Product catalog is indexed in Elasticsearch and synced from PostgreSQL via the nightly ETL job.

  Scenario: Admin adds a new product to the catalog
    Given I am logged in to the Admin Portal as a 'Catalog Manager'
    When I navigate to the 'Add Product' page
    And I fill in the product details with:
      | Field         | Value                      |
      | Name          | Wireless Ergonomic Mouse   |
      | SKU           | WM-ERGO-001                |
      | Price         | 49.99                      |
      | Category      | Peripherals                |
      | Images        | mouse_front.jpg,mouse_side.jpg |
      | Initial Stock | 100                        |
    And I click the 'Save Product' button
    Then the product 'Wireless Ergonomic Mouse' should be successfully added to the catalog
    And it should be immediately purchasable on the storefront