import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://shop.shopsphere.com"

class TestTC014:

    driver = None

    @pytest.fixture(scope="class", autouse=True)
    def setup_method(self):
        # Configure Chrome options for headless execution
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")

        self.driver = webdriver.Chrome(options=options)
        self.driver.get(BASE_URL)
        self.driver.maximize_window()
        yield
        # Teardown: Quit the driver
        if self.driver:
            self.driver.quit()

    def test_tc_014(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        # Given I am on the product page for "ShopSphere T-Shirt"
        product_slug = "shopsphere-t-shirt"
        driver.get(f"{BASE_URL}/products/{product_slug}")
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.product-title")))
        assert product_slug in driver.current_url

        # When I add "1" item to the cart
        quantity_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='quantity']")))
        quantity_input.clear()
        quantity_input.send_keys("1")
        add_to_cart_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.add-to-cart")))
        add_to_cart_button.click()
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-success")))
        cart_badge = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cart-badge")))
        assert cart_badge.text == "1"

        # And I proceed to checkout as a guest
        cart_icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".cart-icon-link")))
        cart_icon.click()
        proceed_to_checkout_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.proceed-to-checkout")))
        proceed_to_checkout_button.click()
        checkout_as_guest_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='checkout-as-guest']")))
        checkout_as_guest_button.click()
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='firstName']")))
        assert "checkout" in driver.current_url

        # And I enter the following shipping details:
        shipping_details = {
            "First Name": "John",
            "Last Name": "Doe",
            "Address Line 1": "123 Test St",
            "City": "Anytown",
            "State": "CA",
            "Zip Code": "90210",
            "Email": "guest@example.com",
            "Phone": "555-123-4567"
        }

        driver.find_element(By.CSS_SELECTOR, "input[name='firstName']").send_keys(shipping_details["First Name"])
        driver.find_element(By.CSS_SELECTOR, "input[name='lastName']").send_keys(shipping_details["Last Name"])
        driver.find_element(By.CSS_SELECTOR, "input[name='address1']").send_keys(shipping_details["Address Line 1"])
        driver.find_element(By.CSS_SELECTOR, "input[name='city']").send_keys(shipping_details["City"])
        driver.find_element(By.CSS_SELECTOR, "input[name='state']").send_keys(shipping_details["State"])
        driver.find_element(By.CSS_SELECTOR, "input[name='zipCode']").send_keys(shipping_details["Zip Code"])
        driver.find_element(By.CSS_SELECTOR, "input[name='email']").send_keys(shipping_details["Email"])
        driver.find_element(By.CSS_SELECTOR, "input[name='phone']").send_keys(shipping_details["Phone"])

        continue_to_payment_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='continue-to-payment']")))
        continue_to_payment_button.click()
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".payment-section")))

        # And I enter the following payment details:
        payment_details = {
            "Card Number": "4242 4242 4242 4242",
            "Expiry Date": "12/26",
            "CVC": "123",
            "Cardholder Name": "John Doe"
        }

        # Assuming Stripe elements are in an iframe
        stripe_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[name^='__privateStripeFrame']")))
        driver.switch_to.frame(stripe_iframe)

        card_number_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='cardnumber']")))
        card_number_input.send_keys(payment_details["Card Number"])
        driver.find_element(By.CSS_SELECTOR, "input[name='exp-date']").send_keys(payment_details["Expiry Date"])
        driver.find_element(By.CSS_SELECTOR, "input[name='cvc']").send_keys(payment_details["CVC"])
        driver.find_element(By.CSS_SELECTOR, "input[name='cardholder-name']").send_keys(payment_details["Cardholder Name"])

        driver.switch_to.default_content() # Switch back from iframe

        # And I place the order
        place_order_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='place-order']")))
        place_order_button.click()

        # Then I should see the order confirmation page
        wait.until(EC.url_contains("/order-confirmation"))
        order_confirmation_title = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.order-confirmation-title")))
        assert "Order Confirmed" in order_confirmation_title.text

        # And the order should be placed successfully without account creation
        order_id_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".order-id")))
        assert "Order ID:" in order_id_element.text
        # Implicitly, no account creation prompt means guest checkout was successful

        # And an order-tracking link should be emailed to "guest@example.com"
        email_confirmation_message = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".order-tracking-email-message")))
        assert f"An order confirmation and tracking link has been sent to {shipping_details['Email']}" in email_confirmation_message.text