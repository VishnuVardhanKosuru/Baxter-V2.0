import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

BASE_URL = "https://shop.shopsphere.com"
PRODUCT_SLUG = "limited-stock-item-prod-005" # Assuming a slug for a product with limited stock
PRODUCT_PAGE_URL = f"{BASE_URL}/products/{PRODUCT_SLUG}"
PRODUCT_NAME = "Limited Stock Item"
AVAILABLE_STOCK = 3
EXCESSIVE_QUANTITY = 5

class TestTC010:

    driver = None

    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # For CI/CD environments
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(BASE_URL)
        self.driver.maximize_window() # Maximize for better visibility in non-headless

    def teardown_method(self):
        if self.driver:
            self.driver.quit()

    def test_tc_010(self):
        # Given I am on the ShopSphere homepage
        WebDriverWait(self.driver, 10).until(EC.url_to_be(BASE_URL + "/"))
        assert self.driver.current_url == BASE_URL + "/", "Failed to navigate to homepage"

        # Given a product "Limited Stock Item" with 3 units in stock is available
        # This step is conceptual for Selenium. We assume the product exists and navigate to it.
        # The actual stock check would be an API call or database query in a real BDD setup,
        # but for UI automation, we proceed assuming the product page reflects this.

        # And I am on the product page for "Limited Stock Item"
        self.driver.get(PRODUCT_PAGE_URL)
        WebDriverWait(self.driver, 10).until(EC.url_to_be(PRODUCT_PAGE_URL))
        product_title = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.product-title"))
        )
        assert product_title.text == PRODUCT_NAME, f"Expected product title '{PRODUCT_NAME}' but got '{product_title.text}'"
        stock_display = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".product-stock-count"))
        )
        assert f"{AVAILABLE_STOCK} units in stock" in stock_display.text, f"Expected stock count '{AVAILABLE_STOCK}' but got '{stock_display.text}'"

        # When I add 1 unit of "Limited Stock Item" to the cart
        add_to_cart_btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.add-to-cart-btn"))
        )
        add_to_cart_btn.click()
        # Wait for success toast and cart badge update
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast.success"))
        )
        cart_badge = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-badge"))
        )
        assert cart_badge.text == "1", "Cart badge did not update to 1"

        # And I navigate to the shopping cart page
        cart_link = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/cart']"))
        )
        cart_link.click()
        WebDriverWait(self.driver, 10).until(EC.url_to_be(BASE_URL + "/cart"))
        cart_item_name = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item-name"))
        )
        assert cart_item_name.text == PRODUCT_NAME, f"Expected cart item '{PRODUCT_NAME}' but got '{cart_item_name.text}'"

        # And I attempt to set the quantity of "Limited Stock Item" to 5
        # Assuming a quantity input field specific to the item
        quantity_input = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, f"input.cart-item-quantity[data-product-id='{PRODUCT_SLUG}']"))
        )
        quantity_input.clear()
        quantity_input.send_keys(str(EXCESSIVE_QUANTITY))
        # Simulate losing focus to trigger update, e.g., click on another element
        self.driver.find_element(By.CSS_SELECTOR, "body").click() # Click body to unfocus

        # Then the quantity for "Limited Stock Item" should be capped at 3
        WebDriverWait(self.driver, 10).until(
            EC.text_to_be_present_in_element_value((By.CSS_SELECTOR, f"input.cart-item-quantity[data-product-id='{PRODUCT_SLUG}']"), str(AVAILABLE_STOCK))
        )
        assert quantity_input.get_attribute("value") == str(AVAILABLE_STOCK), \
            f"Expected quantity to be capped at {AVAILABLE_STOCK}, but found {quantity_input.get_attribute('value')}"

        # And I should see the warning message "Only 3 left in stock"
        warning_message = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item-stock-warning")) # Assuming a specific class for stock warnings
        )
        assert warning_message.is_displayed(), "Stock warning message is not displayed"
        assert warning_message.text == f"Only {AVAILABLE_STOCK} left in stock", \
            f"Expected warning message 'Only {AVAILABLE_STOCK} left in stock' but got '{warning_message.text}'"