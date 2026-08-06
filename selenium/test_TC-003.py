import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestTC003:
    BASE_URL = "https://shop.shopsphere.com"

    @pytest.fixture(scope="class")
    def setup_method(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10) # Set implicit wait for elements to be found
        yield
        try:
            self.driver.quit()
        except Exception as e:
            print(f"Error quitting driver: {e}")

    def test_tc_003(self, setup_method):
        driver = self.driver
        wait = WebDriverWait(driver, 15)

        # Background: Given I am on the Login page
        driver.get(f"{self.BASE_URL}/login")
        wait.until(EC.url_to_be(f"{self.BASE_URL}/login"))
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='email']")))
        assert "Login" in driver.title
        print("Navigated to Login page.")

        # When I enter the following credentials:
        #   | Field    | Value                  |
        #   | email    | user@example.com       |
        #   | password | SecurePassword123!     |
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']")))
        password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']")))

        email_input.send_keys("user@example.com")
        password_input.send_keys("SecurePassword123!")
        print("Entered credentials.")

        # And I click the "Log In" button
        login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
        login_button.click()
        print("Clicked Log In button.")

        # Then I should be redirected to the homepage
        wait.until(EC.url_changes(f"{self.BASE_URL}/login"))
        wait.until(EC.url_to_be(f"{self.BASE_URL}/")) # Assuming homepage is root path after login
        assert driver.current_url == f"{self.BASE_URL}/"
        print("Redirected to homepage.")

        # And I should see a successful login indication
        # This could be a welcome message, a profile icon, or absence of login/register links
        welcome_message = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".user-profile-link, [data-testid='welcome-message']")))
        assert welcome_message.is_displayed()
        print("Successful login indication found.")