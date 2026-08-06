import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://shop.shopsphere.com"

class TestTC021:

    driver = None

    @pytest.fixture(scope="class", autouse=True)
    def setup_method(self):
        # Configure Chrome options for headless execution
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        # Initialize the WebDriver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(BASE_URL)
        self.driver.maximize_window()
        yield
        # Teardown: Quit the driver
        if self.driver:
            self.driver.quit()

    def test_tc_021(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        # Given I am logged in to the Admin Portal as a 'Catalog Manager'
        driver.get(f"{BASE_URL}/admin/login")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']"))).send_keys("catalog.manager@shopsphere.com")
        driver.find_element(By.CSS_SELECTOR, "input[name='password']").send_keys("AdminSecure@123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        wait.until(EC.url_contains("/admin/dashboard"))
        assert "Admin Dashboard" in driver.title

        # When I navigate to the 'Add Product' page
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/admin/products/new']"))).click()
        wait.until(EC.url_contains("/admin/products/new"))
        assert "Add New Product" in driver.title

        # And I fill in the product details with:
        product_details = {
            "Name": "Wireless Ergonomic Mouse",
            "SKU": "WM-ERGO-001",
            "Price": "49.99",
            "Category": "Peripherals",
            "Images": "mouse_front.jpg,mouse_side.jpg", # Assuming a text field for image URLs or names
            "Initial Stock": "100"
        }

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='name']"))).send_keys(product_details["Name"])
        driver.find_element(By.CSS_SELECTOR, "input[name='sku']").send_keys(product_details["SKU"])
        driver.find_element(By.CSS_SELECTOR, "input[name='price']").send_keys(product_details["Price"])
        # Assuming category is a select dropdown, otherwise it would be input[name='category']
        # For simplicity, if it's a text input, use send_keys. If it's a select, use Select class.
        # Let's assume a text input for this example.
        driver.find_element(By.CSS_SELECTOR, "input[name='category']").send_keys(product_details["Category"])
        # For images, assuming a text input for file names/URLs. Actual file upload is more complex.
        driver.find_element(By.CSS_SELECTOR, "input[name='images']").send_keys(product_details["Images"])
        driver.find_element(By.CSS_SELECTOR, "input[name='stock']").send_keys(product_details["Initial Stock"])

        # And I click the 'Save Product' button
        driver.find_element(By.CSS_SELECTOR, "button[type='submit'][data-testid='save-product-btn']").click()

        # Then the product 'Wireless Ergonomic Mouse' should be successfully added to the catalog
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".toast-success")))
        success_message = driver.find_element(By.CSS_SELECTOR, ".toast-success").text
        assert "Product added successfully" in success_message or "Product created" in success_message
        wait.until(EC.url_contains("/admin/products")) # Redirected to product list
        # Verify product in admin list (optional, but good for full coverage)
        wait.until(EC.presence_of_element_located((By.XPATH, f"//td[contains(text(), '{product_details['Name']}')]")))
        assert product_details['Name'] in driver.page_source

        # And it should be immediately purchasable on the storefront
        driver.get(BASE_URL)
        search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='q']")))
        search_input.send_keys(product_details["Name"])
        driver.find_element(By.CSS_SELECTOR, "button[type='submit'][data-testid='search-button']").click()

        wait.until(EC.url_contains(f"/search?q={product_details['Name'].replace(' ', '%20')}"))
        product_card_selector = f"[data-testid='product-card-{product_details['Name'].replace(' ', '-')}-price-{product_details['Price'].replace('.', '-')}-sku-{product_details['SKU']}']"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, product_card_selector)))
        assert product_details["Name"] in driver.page_source

        # Navigate to product detail page to check 'Add to Cart'
        driver.find_element(By.CSS_SELECTOR, product_card_selector).click()
        wait.until(EC.url_contains(f"/products/{product_details['SKU']}"))
        add_to_cart_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-testid='add-to-cart-btn']")))
        assert add_to_cart_button.is_displayed()
        assert add_to_cart_button.text == "Add to Cart"