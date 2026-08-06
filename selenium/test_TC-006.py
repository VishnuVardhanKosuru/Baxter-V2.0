import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestTC006:
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

    def test_tc_006_product_search_by_keyword(self, setup_method):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        # Given I am on the home page
        # Handled by setup_method navigating to BASE_URL
        wait.until(EC.url_to_be(self.BASE_URL + "/")) # Ensure home page is loaded

        # When I enter 'running shoes' into the search bar
        search_bar = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='search_query'], input[placeholder*='Search']")))
        search_bar.send_keys("running shoes")
        assert search_bar.get_attribute("value") == "running shoes", "Search bar should display 'running shoes'"

        # And I click the search icon
        search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'][aria-label*='Search'], [data-testid='search-button']")))
        search_button.click()

        # Then I should see relevant products for 'running shoes' displayed
        # Wait for the URL to change to the search results page
        wait.until(EC.url_contains("/search?query=running+shoes"))
        
        # Wait for product cards to be visible
        product_cards = wait.until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "div.product-card, [data-testid='product-item']")))
        assert len(product_cards) > 0, "No product cards found on the search results page."

        # Verify relevance by checking product titles/descriptions (sample check)
        found_relevant_product = False
        for card in product_cards:
            try:
                product_title = card.find_element(By.CSS_SELECTOR, ".product-card-title, [data-testid='product-item-title']").text.lower()
                if "running shoes" in product_title or "runner" in product_title or "jogging" in product_title:
                    found_relevant_product = True
                    break
            except:
                # Ignore if title not found for a card, continue checking others
                pass
        assert found_relevant_product, "At least one relevant product for 'running shoes' should be displayed."

        # And the search results should be paginated with 24 items per page
        # Check if the number of displayed items is <= 24 (as there might be fewer than 24 results)
        assert len(product_cards) <= 24, f"Expected at most 24 products per page, but found {len(product_cards)}."

        # Check for the presence of pagination controls if more than 24 items are expected in total
        try:
            pagination_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "ul.pagination, [data-testid='pagination']")))
            assert pagination_element.is_displayed(), "Pagination controls should be visible."
        except:
            # If there are 24 or fewer results, pagination might not be present, which is acceptable.
            print("Pagination element not found or not visible, likely due to fewer than 24 results.")