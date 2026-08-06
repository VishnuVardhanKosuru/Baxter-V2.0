import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class TestTC012:
    BASE_URL = "https://shop.shopsphere.com"
    
    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        # For this test, we assume direct navigation to a checkout review page with a pre-populated cart.
        # In a real scenario, items would be added to the cart first.
        self.driver.get(f"{self.BASE_URL}/checkout/review") 
        self.wait = WebDriverWait(self.driver, 10)

    def teardown_method(self):
        if self.driver:
            self.driver.quit()

    def test_tc_012(self):
        # Background: Given a valid, active coupon code "WELCOME10" exists in the system with a 10% discount and $50 minimum threshold
        # This is a system-level precondition and is assumed to be set up in the test environment.

        # Given I am on the checkout review page with a cart subtotal of "$100.00"
        try:
            self.wait.until(EC.url_contains("/checkout/review"))
            self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".order-summary")))
            subtotal_element = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='order-subtotal']")))
            assert "$100.00" in subtotal_element.text, f"Expected subtotal $100.00, but found {subtotal_element.text}"
            print(f"Current subtotal: {subtotal_element.text}")
        except TimeoutException:
            pytest.fail("Failed to load checkout review page or verify subtotal.")

        # When I enter "WELCOME10" into the coupon code field
        coupon_input = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='couponCode']")))
        coupon_input.send_keys("WELCOME10")
        assert coupon_input.get_attribute("value") == "WELCOME10", "Coupon code not entered correctly."

        # And I click the "Apply" button
        apply_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='apply-coupon-button']")))
        apply_button.click()

        # Then a "10%" discount of "$10.00" should be applied and itemized as "Discount (WELCOME10)" in the order summary
        discount_item_label = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='discount-item-label']")))
        assert "Discount (WELCOME10)" in discount_item_label.text, f"Discount item label mismatch: {discount_item_label.text}"
        discount_amount_value = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='discount-amount-value']")))
        assert "- $10.00" in discount_amount_value.text, f"Expected discount amount - $10.00, but found {discount_amount_value.text}"
        print(f"Discount applied: {discount_item_label.text} {discount_amount_value.text}")

        # And the order total should update to "$90.00"
        order_total_element = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='order-total']")))
        assert "$90.00" in order_total_element.text, f"Expected order total $90.00, but found {order_total_element.text}"
        print(f"Updated order total: {order_total_element.text}")