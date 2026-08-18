"""
Pytest configuration and fixtures for Servicios Automation.
Provides Chrome WebDriver with notifications disabled and configurable headless mode.
"""

import os
import pytest
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Load environment variables
load_dotenv()


def get_chrome_options() -> Options:
    """Build Chrome options according to project standards."""
    options = Options()
    
    # Disable browser notifications
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    headless = os.getenv("SERVICIOS_HEADLESS", "false").lower() in ("true", "1", "yes")
    if headless:
        options.add_argument("--headless=new")
        
    return options


@pytest.fixture(scope="function")
def driver():
    """Pytest fixture providing a fresh Selenium Chrome WebDriver instance."""
    options = get_chrome_options()
    driver_instance = webdriver.Chrome(options=options)
    driver_instance.implicitly_wait(0)  # Use explicit waits exclusively
    yield driver_instance
    try:
        driver_instance.quit()
    except Exception:
        pass
