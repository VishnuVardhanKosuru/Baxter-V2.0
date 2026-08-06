import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestTC018:
    BASE_URL = "https://shop.shopsphere.com"

    @pytest.fixture(scope="class")
    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.maximize_window()
        self.driver.get(self.BASE_URL)
        yield
        self.driver.quit()

    def test_tc_018(self, setup_method):
        driver = self.driver
        wait = WebDriverWait(driver, 15)

        # Background: Given a registered customer is logged in
        driver.get(f"{self.BASE_URL}/login")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))).send_keys("existing_user@test.com")
        driver.find_element(By.CSS_SELECTOR, "input[name='password']").send_keys("Secure@123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        wait.until(EC.url_contains("/dashboard")) # Assuming successful login redirects to dashboard or home

        # Background: And at least one order exists for the customer with 'Shipped' status
        # This is a pre-condition assumed to be set up in the test environment.
        # The next step will navigate to 'My Orders' page directly.

        # Scenario: Given I am on the 'My Orders' page
        driver.get(f"{self.BASE_URL}/my-orders")
        wait.until(EC.url_contains("/my-orders"))
        assert "My Orders" in driver.title or "Order History" in driver.page_source

        # When I select an order marked as 'Shipped'
        # Assuming order cards have a data-status attribute or a visible status text
        shipped_order_card = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'order-card') and .//span[contains(text(), 'Shipped')]]")))
        # Click on a link or button within the shipped order card to view details
        # Assuming there's a 'View Details' link or the card itself is clickable
        shipped_order_card.click() # Or find a specific link within it
        wait.until(EC.url_contains("/order/")) # Assuming URL changes to /order/{order_id}

        # And I navigate to the order tracking timeline
        # Assuming the order details page automatically shows the tracking timeline or has a dedicated button
        # If there's a specific 'Track Order' button on the details page:
        # track_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.track-order-button")))
        # track_button.click()
        # For this scenario, we assume the timeline is part of the order details page itself.
        tracking_timeline_section = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.tracking-timeline")))
        assert tracking_timeline_section.is_displayed(), "Order tracking timeline section is not displayed."

        # Then the tracking timeline should display the latest carrier scan event
        latest_scan_event = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.tracking-timeline .latest-scan-event")))
        assert latest_scan_event.is_displayed(), "Latest carrier scan event is not displayed."
        assert latest_scan_event.text.strip() != "", "Latest carrier scan event text is empty."
        print(f"Latest Scan Event: {latest_scan_event.text.strip()}")

        # And the estimated delivery date should be visible
        estimated_delivery_date = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.tracking-timeline .estimated-delivery-date")))
        assert estimated_delivery_date.is_displayed(), "Estimated delivery date is not displayed."
        assert estimated_delivery_date.text.strip() != "", "Estimated delivery date text is empty."
        print(f"Estimated Delivery Date: {estimated_delivery_date.text.strip()}")