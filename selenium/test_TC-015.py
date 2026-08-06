import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://shop.shopsphere.com"

class TestTC015:

    driver = None

    @pytest.fixture(scope="class", autouse=True)
    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
        self.driver.get(BASE_URL)
        yield
        self.driver.quit()

    def test_tc_015(self):
        driver = self.driver
        wait = WebDriverWait(driver, 20)

        # Background: Given a user has added an in-stock item to their cart
        # Navigate to a product page and add an item to the cart
        driver.get(f"{BASE_URL}/products/awesome-widget") # Assuming 'awesome-widget' is a valid product slug
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-testid='add-to-cart-button']"))).click()
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-badge[data-testid='cart-count'][data-count='1']")))

        # And the user is on the cart page
        driver.get(f"{BASE_URL}/cart")
        wait.until(EC.url_to_be(f"{BASE_URL}/cart"))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1[data-testid='cart-title']")))

        # When the user proceeds to checkout
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='proceed-to-checkout']"))).click()
        wait.until(EC.url_contains(f"{BASE_URL}/checkout"))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1[data-testid='checkout-title']")))

        # And the user enters shipping details and selects a shipping method
        # Data from Gherkin table:
        # | Full Name  | Address Line 1 | City    | State | Zip Code | Phone          | Shipping Method   |
        # | John Doe   | 123 Main St    | Anytown | CA    | 90210    | 555-123-4567   | Standard Shipping |
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='fullName']"))).send_keys("John Doe")
        driver.find_element(By.CSS_SELECTOR, "input[name='address1']").send_keys("123 Main St")
        driver.find_element(By.CSS_SELECTOR, "input[name='city']").send_keys("Anytown")
        # Assuming state is a dropdown or text input
        driver.find_element(By.CSS_SELECTOR, "input[name='state']").send_keys("CA") # Or select from dropdown if it's a select element
        driver.find_element(By.CSS_SELECTOR, "input[name='zipCode']").send_keys("90210")
        driver.find_element(By.CSS_SELECTOR, "input[name='phone']").send_keys("555-123-4567")

        # Select shipping method (assuming a radio button or similar)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='shippingMethod'][value='standard']"))).click()

        # And the user enters Stripe test card details
        # Data from Gherkin table:
        # | Card Number         | Expiry Date | CVC |
        # | 4242 4242 4242 4242 | 12/26       | 123 |

        # Switch to iframe for card number
        card_number_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title='Secure card number input frame']")))
        driver.switch_to.frame(card_number_iframe)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='cardnumber']"))).send_keys("4242424242424242")
        driver.switch_to.default_content()

        # Switch to iframe for expiry date
        expiry_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title='Secure expiration date input frame']")))
        driver.switch_to.frame(expiry_iframe)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='exp-date']"))).send_keys("12/26")
        driver.switch_to.default_content()

        # Switch to iframe for CVC
        cvc_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title='Secure CVC input frame']")))
        driver.switch_to.frame(cvc_iframe)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='cvc']"))).send_keys("123")
        driver.switch_to.default_content()

        # And the user clicks "Place Order"
        place_order_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='place-order-button']")))
        place_order_button.click()

        # Then the payment should be confirmed and the order status set to "Confirmed"
        # And the user should see an order confirmation screen with the order number
        wait.until(EC.url_contains(f"{BASE_URL}/order-confirmation"))
        order_confirmation_title = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1[data-testid='order-confirmation-title']")))
        assert "Order Confirmed" in order_confirmation_title.text

        order_number_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span[data-testid='order-number']")))
        assert order_number_element.text.strip() != "", "Order number should be displayed"