import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestTC008:
    BASE_URL = "https://shop.shopsphere.com"
    PRODUCT_ID = "P001"
    PRODUCT_NAME = "ShopSphere T-Shirt"
    PRODUCT_SIZE = "Medium"

    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(self.BASE_URL)
        self.driver.maximize_window()

    def teardown_method(self):
        if self.driver:
            self.driver.quit()

    def test_tc_008_add_product_to_cart(self):
        # Given I am on the product detail page for "ShopSphere T-Shirt" (P001)
        product_url = f"{self.BASE_URL}/products/shopsphere-t-shirt-{self.PRODUCT_ID.lower()}"
        self.driver.get(product_url)
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.product-title"))
        )
        product_title_element = self.driver.find_element(By.CSS_SELECTOR, "h1.product-title")
        assert self.PRODUCT_NAME in product_title_element.text
        print(f"Navigated to product detail page: {product_title_element.text}")

        # When I select size "Medium"
        # Assuming size selection is via buttons with data-size attribute
        size_selector = f"div.size-selector button[data-size='{self.PRODUCT_SIZE}']"
        size_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, size_selector))
        )
        size_button.click()
        print(f"Selected size: {self.PRODUCT_SIZE}")

        # And I click the "Add to Cart" button
        add_to_cart_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='add-to-cart']"))
        )
        add_to_cart_button.click()
        print("Clicked 'Add to Cart' button")

        # Then the cart badge count should display "1"
        cart_badge = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "span[data-testid='cart-count']"))
        )
        assert cart_badge.text == "1"
        print(f"Cart badge count is: {cart_badge.text}")

        # And a mini-cart confirmation drawer should display "ShopSphere T-Shirt (Medium)" with the updated subtotal
        mini_cart_drawer = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div[data-testid='mini-cart-drawer']"))
        )
        item_in_mini_cart = mini_cart_drawer.find_element(By.CSS_SELECTOR, "div[data-testid='mini-cart-item-name']")
        assert f"{self.PRODUCT_NAME} ({self.PRODUCT_SIZE})" in item_in_mini_cart.text
        
        # Optional: Verify subtotal presence
        subtotal_element = mini_cart_drawer.find_element(By.CSS_SELECTOR, "span[data-testid='mini-cart-subtotal']")
        assert subtotal_element.is_displayed()
        print(f"Mini-cart drawer displayed with item: {item_in_mini_cart.text} and subtotal: {subtotal_element.text}")