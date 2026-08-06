import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://shop.shopsphere.com"

class TestTC011:

    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(BASE_URL)
        self.wait = WebDriverWait(self.driver, 10)

    def teardown_method(self):
        if self.driver:
            self.driver.quit()

    def test_tc_011(self):
        # Given I am on the product page for "Awesome Widget"
        self.driver.get(f"{BASE_URL}/products/awesome-widget")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product-title")))

        # And I add "Awesome Widget" to the cart
        add_to_cart_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.add-to-cart")))
        add_to_cart_button.click()
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cart-badge:not([data-count='0'])")))
        cart_count = self.driver.find_element(By.CSS_SELECTOR, ".cart-badge").text
        assert cart_count == "1", f"Expected cart count 1, but got {cart_count}"

        # And I am on the product page for "Super Gadget"
        self.driver.get(f"{BASE_URL}/products/super-gadget")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product-title")))

        # And I add "Super Gadget" to the cart
        add_to_cart_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.add-to-cart")))
        add_to_cart_button.click()
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".cart-badge"), "2"))
        cart_count = self.driver.find_element(By.CSS_SELECTOR, ".cart-badge").text
        assert cart_count == "2", f"Expected cart count 2, but got {cart_count}"

        # And I navigate to the shopping cart page
        self.driver.get(f"{BASE_URL}/cart")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.cart-title")))
        # Verify both items are present
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cart-item[data-item-name='Awesome Widget']")))
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cart-item[data-item-name='Super Gadget']")))

        # When I click the remove button for "Awesome Widget"
        remove_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.cart-item[data-item-name='Awesome Widget'] .remove-item-btn")))
        remove_button.click()

        # Then "Awesome Widget" should no longer be in the cart
        self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.cart-item[data-item-name='Awesome Widget']")))
        assert not self.driver.find_elements(By.CSS_SELECTOR, "div.cart-item[data-item-name='Awesome Widget']"), "Awesome Widget is still in the cart"

        # And the cart badge count should be 1
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".cart-badge"), "1"))
        cart_count_after_removal = self.driver.find_element(By.CSS_SELECTOR, ".cart-badge").text
        assert cart_count_after_removal == "1", f"Expected cart count 1 after removal, but got {cart_count_after_removal}"

        # And the cart total should reflect the remaining item
        # Assuming 'Super Gadget' costs $10.00 for this assertion
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".cart-total-amount"), "$10.00"))
        cart_total_element = self.driver.find_element(By.CSS_SELECTOR, ".cart-total-amount")
        assert cart_total_element.text == "$10.00", f"Expected cart total $10.00, but got {cart_total_element.text}"