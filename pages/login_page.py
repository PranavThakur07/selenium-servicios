"""
LoginPage Object Model representing the Servicios Admin Login Page.
Target: https://staging-admin.coyoacan.io/auth/login
Strictly read-only and credentials-safe (never logs passwords).
"""

import logging
from typing import Optional, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from pages.base_page import BasePage

logger = logging.getLogger("ServiciosAutomation.LoginPage")


class LoginPage(BasePage):
    """Page Object for Servicios Admin Login."""

    EMAIL_LOCATORS = [
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.CSS_SELECTOR, "input[name='email']"),
        (By.ID, "email"),
        (By.XPATH, "//input[@name='email' or @id='email' or @type='email']"),
        (By.XPATH, "//input[contains(@placeholder, 'mail') or contains(@placeholder, 'Mail') or contains(@placeholder, 'username')]"),
        (By.CSS_SELECTOR, "input[type='text']")
    ]

    PASSWORD_LOCATORS = [
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.CSS_SELECTOR, "input[name='password']"),
        (By.ID, "password"),
        (By.XPATH, "//input[@type='password']")
    ]

    SUBMIT_LOCATORS = [
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.XPATH, "//button[@type='submit']"),
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign')]"),
        (By.XPATH, "//input[@type='submit']"),
        (By.CSS_SELECTOR, ".btn-primary")
    ]

    ERROR_LOCATORS = [
        (By.CSS_SELECTOR, ".alert-danger"),
        (By.CSS_SELECTOR, ".error-message"),
        (By.CSS_SELECTOR, "[role='alert']"),
        (By.CSS_SELECTOR, ".toast-error"),
        (By.CSS_SELECTOR, ".text-danger")
    ]

    def __init__(self, driver: WebDriver, default_timeout: int = 15):
        super().__init__(driver, default_timeout)

    def navigate_to_login(self, login_url: str = "https://staging-admin.coyoacan.io/auth/login") -> None:
        """Navigate to the staging login page."""
        logger.info("Opening login page: %s", login_url)
        self.navigate(login_url)

    def _find_first_available(self, locators: list, timeout: int = 10) -> Tuple[By, str]:
        """Find the first locator from a candidate list that exists on the page."""
        for by, value in locators:
            try:
                if self.is_visible(by, value, timeout=2):
                    return by, value
            except Exception:
                continue
        return locators[0]

    def is_login_page_displayed(self, timeout: int = 10) -> bool:
        """Check if login input elements are present."""
        for by, value in self.EMAIL_LOCATORS:
            if self.is_visible(by, value, timeout=2):
                return True
        return False

    def login(self, email: str, password: str, timeout: Optional[int] = None) -> None:
        """
        Execute login with email and password using resilient locator resolution.
        Explicitly masks password in logs.
        """
        logger.info("Attempting login for user: %s", email)
        
        email_by, email_val = self._find_first_available(self.EMAIL_LOCATORS, timeout=timeout or self.timeout)
        self.fill(email_by, email_val, email, timeout=timeout, mask_log=False)

        pwd_by, pwd_val = self._find_first_available(self.PASSWORD_LOCATORS, timeout=timeout or self.timeout)
        self.fill(pwd_by, pwd_val, password, timeout=timeout, mask_log=True)

        # Submit form: click button and send Enter as backup
        try:
            btn_by, btn_val = self._find_first_available(self.SUBMIT_LOCATORS, timeout=3)
            self.click(btn_by, btn_val, timeout=3)
        except Exception:
            logger.info("Clicking submit button timed out, sending ENTER key to password input...")
            pwd_el = self.find_element(pwd_by, pwd_val, timeout=2)
            pwd_el.send_keys(Keys.RETURN)

    def get_error_message(self, timeout: int = 5) -> str:
        """Retrieve any error text if login failed."""
        for by, value in self.ERROR_LOCATORS:
            text = self.get_text(by, value, timeout=1)
            if text:
                return text
        return ""
