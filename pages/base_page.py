"""
Base Page Object Model for Servicios Automation.
Provides explicit waits, safe element interactions, and cookie extraction.
Strictly read-only and non-destructive.
"""

import logging
from typing import List, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger("ServiciosAutomation.BasePage")


class BasePage:
    """Base Page Object containing reusable WebDriver helpers with explicit waits."""

    def __init__(self, driver: WebDriver, default_timeout: int = 15):
        self.driver = driver
        self.timeout = default_timeout
        self.wait = WebDriverWait(self.driver, self.timeout)

    def navigate(self, url: str) -> None:
        """Navigate to a specified URL."""
        logger.info("Navigating to: %s", url)
        self.driver.get(url)

    def get_current_url(self) -> str:
        """Get the current page URL."""
        return self.driver.current_url

    def get_page_title(self) -> str:
        """Get the current page title."""
        return self.driver.title

    def find_element(self, by: By, value: str, timeout: Optional[int] = None) -> WebElement:
        """Find a single web element with explicit wait."""
        wait = WebDriverWait(self.driver, timeout or self.timeout)
        return wait.until(EC.presence_of_element_located((by, value)))

    def find_elements(self, by: By, value: str, timeout: Optional[int] = None) -> List[WebElement]:
        """Find multiple web elements with explicit wait."""
        wait = WebDriverWait(self.driver, timeout or self.timeout)
        try:
            return wait.until(EC.presence_of_all_elements_located((by, value)))
        except TimeoutException:
            return []

    def wait_for_visibility(self, by: By, value: str, timeout: Optional[int] = None) -> WebElement:
        """Wait until an element is visible on the DOM."""
        wait = WebDriverWait(self.driver, timeout or self.timeout)
        return wait.until(EC.visibility_of_element_located((by, value)))

    def wait_for_clickable(self, by: By, value: str, timeout: Optional[int] = None) -> WebElement:
        """Wait until an element is clickable."""
        wait = WebDriverWait(self.driver, timeout or self.timeout)
        return wait.until(EC.element_to_be_clickable((by, value)))

    def click(self, by: By, value: str, timeout: Optional[int] = None) -> None:
        """Click on an element after waiting for it to be clickable."""
        element = self.wait_for_clickable(by, value, timeout)
        element.click()

    def fill(self, by: By, value: str, text: str, timeout: Optional[int] = None, mask_log: bool = False) -> None:
        """Clear and type text into an input element."""
        if mask_log:
            logger.info("Filling input '%s' with [PROTECTED_VALUE]", value)
        else:
            logger.info("Filling input '%s' with '%s'", value, text)
        element = self.wait_for_visibility(by, value, timeout)
        element.clear()
        element.send_keys(text)

    def get_text(self, by: By, value: str, timeout: Optional[int] = None) -> str:
        """Retrieve text from an element."""
        try:
            element = self.wait_for_visibility(by, value, timeout)
            return element.text.strip()
        except TimeoutException:
            return ""

    def is_visible(self, by: By, value: str, timeout: int = 5) -> bool:
        """Check if an element is visible within a brief timeout."""
        try:
            WebDriverWait(self.driver, timeout).until(EC.visibility_of_element_located((by, value)))
            return True
        except (TimeoutException, NoSuchElementException):
            return False

    def wait_for_url_contains(self, url_substring: str, timeout: Optional[int] = None) -> bool:
        """Wait until the current URL contains a given substring."""
        wait = WebDriverWait(self.driver, timeout or self.timeout)
        try:
            return wait.until(EC.url_contains(url_substring))
        except TimeoutException:
            return False

    def get_cookies(self) -> List[dict]:
        """Extract all cookies from the current browser session."""
        return self.driver.get_cookies()

    def get_local_storage_item(self, key: str) -> Optional[str]:
        """Safely retrieve an item from browser localStorage."""
        try:
            return self.driver.execute_script(f"return window.localStorage.getItem('{key}');")
        except Exception:
            return None

    def get_session_storage_item(self, key: str) -> Optional[str]:
        """Safely retrieve an item from browser sessionStorage."""
        try:
            return self.driver.execute_script(f"return window.sessionStorage.getItem('{key}');")
        except Exception:
            return None
