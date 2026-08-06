import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestTC022:
    BASE_URL = "https://shop.shopsphere.com"
    ADMIN_EMAIL = "admin@shopsphere.com"
    ADMIN_PASSWORD = "AdminSecure@123"

    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 10)

        # Background: Given an Admin user is authenticated with the "Inventory Manager" role
        self.driver.get(f"{self.BASE_URL}/admin/login")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))).send_keys(self.ADMIN_EMAIL)
        self.driver.find_element(By.CSS_SELECTOR, "input[name='password']").send_keys(self.ADMIN_PASSWORD)
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/admin/dashboard"))

        # Navigate to Admin Inventory page
        self.driver.get(f"{self.BASE_URL}/admin/inventory")
        self.wait.until(EC.url_contains("/admin/inventory"))
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.inventory-table")))

    def teardown_method(self):
        if self.driver:
            self.driver.quit()

    def test_tc_022(self):
        # Given I am on the Admin Inventory page
        assert "admin/inventory" in self.driver.current_url
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1:contains('Inventory Management')")))

        # When I adjust the stock of SKU "PROD-001" with the following details:
        #   | Field             | Value             |
        #   | Current Stock     | 15                |
        #   | Reorder Threshold | 10                |
        #   | New Stock         | 8                 |
        #   | Reason            | Low stock test    |
        sku_id = "PROD-001"
        new_stock_quantity = "8"
        adjustment_reason = "Low stock test"

        # Find the row for the SKU and click the edit button
        sku_row_selector = f"tr[data-sku='{sku_id}']"
        edit_button_selector = f"{sku_row_selector} button.edit-stock-btn"
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, edit_button_selector))).click()

        # Wait for the stock adjustment modal to appear
        modal_selector = "div.stock-adjustment-modal"
        new_stock_input_selector = f"{modal_selector} input[name='newStockQuantity']"
        reason_textarea_selector = f"{modal_selector} textarea[name='adjustmentReason']"
        save_button_selector = f"{modal_selector} button[type='submit']"

        self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, new_stock_input_selector))).clear()
        self.driver.find_element(By.CSS_SELECTOR, new_stock_input_selector).send_keys(new_stock_quantity)
        self.driver.find_element(By.CSS_SELECTOR, reason_textarea_selector).send_keys(adjustment_reason)
        self.driver.find_element(By.CSS_SELECTOR, save_button_selector).click()

        # Wait for the modal to disappear and a success toast to appear
        self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, modal_selector)))
        success_toast_selector = ".toast-success"
        self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, success_toast_selector)))
        assert "Stock updated successfully" in self.driver.find_element(By.CSS_SELECTOR, success_toast_selector).text

        # And I refresh the inventory view
        self.driver.refresh()
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.inventory-table")))

        # Then SKU "PROD-001" should be flagged as "Low Stock" with a highlighted status badge
        low_stock_badge_selector = f"tr[data-sku='{sku_id}'] .status-badge.low-stock"
        low_stock_element = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, low_stock_badge_selector)))
        assert "Low Stock" in low_stock_element.text
        assert "low-stock" in low_stock_element.get_attribute("class")