"""
BookingsPage Object Model representing the Servicios Admin Bookings Page.
Target: https://staging-admin.coyoacan.io/bookings?category=booking
Strictly READ-ONLY: Never interacts with mutating buttons (accept, reject, assign, edit, delete).
"""

import logging
from typing import List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from pages.base_page import BasePage

logger = logging.getLogger("ServiciosAutomation.BookingsPage")


class BookingsPage(BasePage):
    """
    Page Object for Servicios Admin Bookings View.
    Strictly read-only for monitoring and UI verification.
    """

    # Locators
    BOOKINGS_CONTAINER = (By.CSS_SELECTOR, ".bookings-container, table, .table-responsive, [data-testid='bookings-table'], .ant-table, .data-table")
    TABLE_ROWS = (By.CSS_SELECTOR, "table tbody tr, .table-row, [role='row']")
    PAGE_HEADER = (By.CSS_SELECTOR, "h1, h2, .page-title, .page-header")
    LOADING_SPINNER = (By.CSS_SELECTOR, ".loading, .spinner, .ant-spin, .loader")

    def __init__(self, driver: WebDriver, default_timeout: int = 20):
        super().__init__(driver, default_timeout)

    def navigate_to_bookings(self, bookings_url: str = "https://staging-admin.coyoacan.io/bookings?category=booking") -> None:
        """Navigate directly to the bookings page."""
        logger.info("Navigating to bookings page: %s", bookings_url)
        self.navigate(bookings_url)

    def is_bookings_page_displayed(self, timeout: Optional[int] = None) -> bool:
        """Verify the bookings page container is loaded."""
        t = timeout or self.timeout
        return self.is_visible(self.BOOKINGS_CONTAINER[0], self.BOOKINGS_CONTAINER[1], timeout=t)

    def get_displayed_booking_count_from_ui(self) -> int:
        """
        Read-only helper to count rows visible in the UI table.
        Safe for future UI verification without performing any mutations.
        """
        rows = self.find_elements(self.TABLE_ROWS[0], self.TABLE_ROWS[1], timeout=5)
        return len(rows)

    def get_visible_booking_ids_from_ui(self) -> List[str]:
        """
        Extract text from table rows for passive observation.
        Strictly read-only.
        """
        rows = self.find_elements(self.TABLE_ROWS[0], self.TABLE_ROWS[1], timeout=5)
        extracted = []
        for row in rows:
            try:
                text = row.text.strip()
                if text:
                    extracted.append(text)
            except Exception:
                continue
        return extracted
