import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestTC001:
    BASE_URL = "https://shop.shopsphere.com"

    @pytest.fixture(scope="class")
    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(self.BASE_URL)
        yield
        self.driver.quit()

    def test_tc_001(self, setup_method):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        # Given I am on the ShopSphere homepage
        assert driver.current_url == self.BASE_URL, f"Expected to be on {self.BASE_URL}, but found {driver.current_url}"

        # When I click on the "Sign Up" link
        signup_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/register'], .signup-link")))
        signup_link.click()

        # And I am on the registration page
        wait.until(EC.url_contains("/register"))
        assert "register" in driver.current_url, f"Expected URL to contain '/register', but found {driver.current_url}"
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h1:contains('Create Account'), .registration-form h2")))

        # And I fill in the registration form with:
        #   | Field      | Value             |
        #   | Email      | unique.user@test.com |
        #   | Full Name  | Test User         |
        #   | Password   | Secure@123        |
        email_field = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='email']")))
        email_field.send_keys("unique.user@test.com")

        full_name_field = driver.find_element(By.CSS_SELECTOR, "input[name='fullName'], input[name='name']")
        full_name_field.send_keys("Test User")

        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        password_field.send_keys("Secure@123")

        # And I click the "Create Account" button
        create_account_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], .btn-primary")))
        create_account_button.click()

        # Then I should be redirected to the homepage
        wait.until(EC.url_contains("/home")) # Assuming /home is the post-login homepage
        assert "home" in driver.current_url, f"Expected URL to contain '/home', but found {driver.current_url}"

        # And I should see a success message "Registration successful! Welcome to ShopSphere."
        success_message = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-success, [data-testid='success-message']")))
        assert "Registration successful! Welcome to ShopSphere." in success_message.text

        # And I should be logged in as "Test User"
        # This typically involves checking for a user's name in a header or profile link
        user_profile_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".user-profile-name, [data-testid='logged-in-user']")))
        assert "Test User" in user_profile_element.text