import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://shop.shopsphere.com"

class TestTC009:

    driver = None

    @pytest.fixture(scope="class", autouse=True)
    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
        self.driver.get(BASE_URL)
        yield
        self.driver.quit()

    def test_tc_009(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        # Given I am on the cart page with "ShopSphere T-Shirt" added with quantity 1
        # Navigate to a product page and add an item
        driver.get(f"{BASE_URL}/products/SS-TSHIRT-BLK")
        add_to_cart_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".add-to-cart-btn")))
        add_to_cart_button.click()

        # Wait for success message or cart update, then navigate to cart page
        # Assuming a toast message or cart icon update, then direct navigation to cart
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-success, .cart-badge[data-count='1']")))
        driver.get(f"{BASE_URL}/cart")

        # Verify item is in cart with quantity 1
        cart_item_name = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item-name"))).text
        assert "ShopSphere T-Shirt" in cart_item_name

        initial_quantity_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] input[name='quantity']")))
        assert initial_quantity_input.get_attribute("value") == "1"

        initial_item_subtotal_text = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] .cart-item-subtotal"))).text
        initial_item_subtotal = float(initial_item_subtotal_text.replace('$', ''))

        initial_cart_total_text = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-total-amount"))).text
        initial_cart_total = float(initial_cart_total_text.replace('$', ''))

        # When I increase the quantity of "ShopSphere T-Shirt" by 1 using the stepper control
        increase_quantity_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] .quantity-stepper .plus-btn")))
        increase_quantity_button.click()

        # Then The quantity of "ShopSphere T-Shirt" should be 2
        wait.until(EC.text_to_be_present_in_element_value((By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] input[name='quantity']"), "2"))
        updated_quantity_input = driver.find_element(By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] input[name='quantity']")
        assert updated_quantity_input.get_attribute("value") == "2"

        # And The item subtotal and cart total should be updated accordingly
        updated_item_subtotal_text = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] .cart-item-subtotal"))).text
        updated_item_subtotal = float(updated_item_subtotal_text.replace('$', ''))
        assert updated_item_subtotal > initial_item_subtotal

        updated_cart_total_text = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-total-amount"))).text
        updated_cart_total = float(updated_cart_total_text.replace('$', ''))
        assert updated_cart_total > initial_cart_total

        # And The updated quantity should persist after refreshing the page
        driver.refresh()

        # Verify quantity after refresh
        persisted_quantity_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] input[name='quantity']")))
        assert persisted_quantity_input.get_attribute("value") == "2"

        # Verify subtotals after refresh
        persisted_item_subtotal_text = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-item[data-product-id='SS-TSHIRT-BLK'] .cart-item-subtotal"))).text
        persisted_item_subtotal = float(persisted_item_subtotal_text.replace('$', ''))
        assert persisted_item_subtotal == updated_item_subtotal

        persisted_cart_total_text = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-total-amount"))).text
        persisted_cart_total = float(persisted_cart_total_text.replace('$', ''))
        assert persisted_cart_total == updated_cart_total