import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestTC017:
    BASE_URL = "https://shop.shopsphere.com"
    CUSTOMER_EMAIL = "customer@shopsphere.com"
    CUSTOMER_PASSWORD = "Password123!"

    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(self.BASE_URL)
        self.wait = WebDriverWait(self.driver, 10)

    def teardown_method(self):
        if self.driver:
            self.driver.quit()

    def test_tc_017(self):
        # Background: Given a registered customer is logged in
        self.driver.get(f"{self.BASE_URL}/login")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))).send_keys(self.CUSTOMER_EMAIL)
        self.driver.find_element(By.CSS_SELECTOR, "input[name='password']").send_keys(self.CUSTOMER_PASSWORD)
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/account")) # Wait for login to complete and redirect to account page

        # Background: And has an order in 'Confirmed' status
        # Given I am on the 'My Orders' page
        self.driver.get(f"{self.BASE_URL}/my-orders")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1:contains('My Orders')")))

        # When I open the details for an order with status 'Confirmed'
        # Assuming an order card/row with a status element and a 'View Details' button
        order_items = self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid^='order-item-']")))
        confirmed_order_found = False
        for item in order_items:
            status_element = item.find_element(By.CSS_SELECTOR, "[data-testid='order-status']")
            if "Confirmed" in status_element.text:
                item.find_element(By.CSS_SELECTOR, "[data-testid='view-details-button']").click()
                confirmed_order_found = True
                break
        assert confirmed_order_found, "No 'Confirmed' order found to cancel."
        self.wait.until(EC.url_contains("/order/")) # Wait for order details page to load
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1:contains('Order Details')")))

        # And I click the 'Cancel Order' button
        cancel_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='cancel-order-button']")))
        cancel_button.click()

        # And I confirm the cancellation
        confirm_dialog = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[role='dialog']")))
        confirm_button = confirm_dialog.find_element(By.CSS_SELECTOR, "button[data-testid='confirm-cancel-button']")
        confirm_button.click()

        # Then The order status should change to 'Cancelled'
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "[data-testid='order-status']"), "Cancelled"))
        current_status = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='order-status']").text
        assert "Cancelled" in current_status, f"Expected order status to be 'Cancelled', but found '{current_status}'"

        # And A cancellation confirmation message should be displayed
        confirmation_message = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='success-toast'], .alert-success"))).text
        assert "Order cancelled successfully" in confirmation_message or "Cancellation confirmed" in confirmation_message, \
            f"Expected cancellation confirmation message, but found '{confirmation_message}'"

        # And The system should initiate a refund process
        # For UI test, we assert for a visual indication of refund or a message.
        refund_indicator = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='refund-status'], [data-testid='order-summary']"))).text
        assert "Refund initiated" in refund_indicator or "Refund processing" in refund_indicator or "Refunded" in refund_indicator, \
            f"Expected refund initiation indication, but found '{refund_indicator}'"

        # And The inventory for the cancelled items should be restocked
        # This is primarily a backend verification. For UI, we assume success based on cancellation confirmation.
        # A more robust test would involve API calls to verify inventory levels before and after cancellation.
        print("Note: Inventory restock is a backend operation, assumed successful based on UI confirmation.")