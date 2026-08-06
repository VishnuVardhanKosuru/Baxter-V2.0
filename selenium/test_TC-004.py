import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://shop.shopsphere.com"

class TestTC004:
    driver = None

    def setup_method(self):
        """Set up the Chrome WebDriver before each test."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(f"{BASE_URL}/login")
        # Wait for the login page to load by checking for an input field
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))
        )

    def teardown_method(self):
        """Quit the WebDriver after each test."""
        if self.driver:
            self.driver.quit()

    def test_tc_004(self):
        """Test case for logging in with an invalid password."""

        # Given I am on the Login page
        # The setup_method already navigates to the login page.
        # Verify the current URL to ensure we are on the correct page.
        WebDriverWait(self.driver, 10).until(
            EC.url_to_be(f"{BASE_URL}/login")
        )
        assert f"{BASE_URL}/login" == self.driver.current_url, "Not on the login page."

        # When I attempt to log in with the following credentials:
        #   | email            | password         |
        #   | user@example.com | WrongPassword123 |
        email_field = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='email']"))
        )
        password_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")

        email_field.send_keys("user@example.com")
        password_field.send_keys("WrongPassword123")
        login_button.click()

        # Then I should see the error message "Invalid email or password"
        error_message_element = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".error-message, [data-testid='error']"))
        )
        assert "Invalid email or password" in error_message_element.text, \
            f"Expected error message 'Invalid email or password' but got '{error_message_element.text}'"

        # And I should remain on the Login page
        WebDriverWait(self.driver, 10).until(
            EC.url_to_be(f"{BASE_URL}/login")
        )
        assert f"{BASE_URL}/login" == self.driver.current_url, "User was redirected from the login page unexpectedly."