@ui_dynamic_content_validation
@admin_portal__inventory
@fr_006
Feature: Inventory Management (Admin)
  Enable Admin/Warehouse staff to manage stock levels, receive low-stock alerts, and reconcile inventory against incoming purchase orders.

  Background:
    Given an Admin user is authenticated with the "Inventory Manager" role

  Scenario: Low-Stock Alert is triggered for a SKU
    Given I am on the Admin Inventory page
    When I adjust the stock of SKU "PROD-001" with the following details:
      | Field             | Value             |
      | Current Stock     | 15                |
      | Reorder Threshold | 10                |
      | New Stock         | 8                 |
      | Reason            | Low stock test    |
    And I refresh the inventory view
    Then SKU "PROD-001" should be flagged as "Low Stock" with a highlighted status badge