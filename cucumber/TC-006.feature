@ui_dynamic_content_validation
@catalog_and_search
@fr_002
Feature: Product Catalog & Search
  Enable customers to browse the product catalog and search by keyword, with filtering by category, price range, brand, and rating, backed by an Elasticsearch index.

  Background:
    Given Product catalog is indexed in Elasticsearch and synced from PostgreSQL via the nightly ETL job.

  Scenario: Search for products by keyword
    Given I am on the home page
    When I enter 'running shoes' into the search bar
    And I click the search icon
    Then I should see relevant products for 'running shoes' displayed
    And the search results should be paginated with 24 items per page