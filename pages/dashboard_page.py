"""
DashboardPage Object Model representing the post-login Servicios Admin Dashboard.
Strictly read-only.
"""

import logging
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from pages.base_page import BasePage

logger = logging.getLogger("ServiciosAutomation.DashboardPage")


class DashboardPage(BasePage):
    """Page Object for Servicios Admin Dashboard post-login."""

    # Locators
    DASHBOARD_INDICATOR = (By.CSS_SELECTOR, ".dashboard-container, nav.navbar, aside.sidebar, header, [data-testid='dashboard'], a[href*='/bookings'], main")
    BOOKINGS_NAV_LINK = (By.XPATH, "//a[contains(@href, '/bookings')] | //span[contains(text(), 'Booking')]")
    USER_PROFILE_MENU = (By.CSS_SELECTOR, ".user-profile, .avatar, [data-testid='user-menu']")

    def __init__(self, driver: WebDriver, default_timeout: int = 20):
        super().__init__(driver, default_timeout)

    def is_dashboard_displayed(self, timeout: Optional[int] = None) -> bool:
        """
        Wait for login completion: URL changes away from /auth/login and dashboard loads.
        """
        t = timeout or self.timeout
        wait = WebDriverWait(self.driver, t)
        try:
            # Explicitly wait until the page navigates away from /auth/login
            wait.until(lambda d: "/auth/login" not in d.current_url)
            logger.info("URL transitioned away from login page to: %s", self.get_current_url())
            return True
        except TimeoutException:
            # Fallback check: see if dashboard element or bookings nav is visible
            if self.is_visible(self.DASHBOARD_INDICATOR[0], self.DASHBOARD_INDICATOR[1], timeout=2):
                return True
            logger.warning("Timed out waiting for URL to transition away from /auth/login. Current URL: %s", self.get_current_url())
            return False

    def navigate_to_bookings_via_ui(self, timeout: Optional[int] = None) -> None:
        """Click the Bookings link from the sidebar/navbar navigation."""
        logger.info("Navigating to Bookings via UI menu link")
        self.click(self.BOOKINGS_NAV_LINK[0], self.BOOKINGS_NAV_LINK[1], timeout=timeout)
