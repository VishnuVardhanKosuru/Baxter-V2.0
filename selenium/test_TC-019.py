import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestTC019:
    BASE_URL = "https://shop.shopsphere.com"

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

    def test_tc_019(self):
        # Background: Given a registered customer is logged in
        self.driver.get(f"{self.BASE_URL}/login")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))).send_keys("customer@shopsphere.com")
        self.driver.find_element(By.CSS_SELECTOR, "input[name='password']").send_keys("SecureShop@123")
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/dashboard")) # Assuming successful login redirects to dashboard
        assert "dashboard" in self.driver.current_url.lower(), "Login failed: Not redirected to dashboard."

        # Given I am on the product detail page for 'ShopSphere Smartwatch'
        product_slug = "shopsphere-smartwatch-p001"
        self.driver.get(f"{self.BASE_URL}/products/{product_slug}")
        product_title_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product-title")))
        assert "ShopSphere Smartwatch" in product_title_element.text, "Product detail page not loaded correctly."

        # When I click the 'Add to Wishlist' icon
        add_to_wishlist_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='add-to-wishlist']")))
        add_to_wishlist_button.click()

        # Then the product 'ShopSphere Smartwatch' should be added to my wishlist
        # And the 'Add to Wishlist' icon should be in an active state
        # We verify this by checking for a change in the button's data-testid or class
        # Assuming the button changes to 'remove-from-wishlist' or gets an 'active' class
        remove_from_wishlist_button = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-testid='remove-from-wishlist']")))
        assert remove_from_wishlist_button.is_displayed(), "Wishlist icon did not change to active state."

        # And a success message 'Product added to wishlist!' should be displayed
        success_toast = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-message.success, [data-testid='success-message']")))
        assert "Product added to wishlist!" in success_toast.text, f"Expected success message not found. Actual: {success_toast.text}"