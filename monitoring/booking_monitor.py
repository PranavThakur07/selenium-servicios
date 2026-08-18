#!/usr/bin/env python3
"""
Servicios Booking Monitor (Standalone, Read-Only QA & Forensic Tool)
Target: Staging Environment (https://staging-admin.coyoacan.io)

This tool continuously monitors the Servicios Booking API to detect, capture,
and forensically log bookings that appear in the system.

CRITICAL SAFETY:
This tool is STRICTLY READ-ONLY. It never mutates, accepts, rejects, assigns,
edits, or deletes any bookings.
"""

import os
import sys
import time
import json
import csv
import signal
import logging
import threading
import http.server
import socketserver
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Third-party dependencies
try:
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print(f"[FATAL] Missing required Python package: {e}")
    print("Please install requirements using: pip install -r requirements.txt")
    sys.exit(1)

# Load environment variables
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
load_dotenv()  # Fallback to current working directory .env

# Configure logging
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ServiciosBookingMonitor")


class BookingMonitor:
    """
    Forensic monitoring engine for the Servicios Staging Booking API.
    Handles authentication transfer, baseline tracking, deduplication,
    and multi-format forensic logging.
    """

    def __init__(self):
        self._load_configuration()
        self._setup_output_paths()
        self._setup_signal_handlers()

        self.session: requests.Session = requests.Session()
        self.seen_booking_ids: Dict[str, Dict[str, Any]] = {}
        self.baseline_initialized: bool = False
        self.running: bool = True
        self.poll_cycle: int = 0
        self.new_bookings_detected_session: int = 0

        # Load any previously persisted seen IDs to avoid false alerts on restart
        self._load_seen_booking_ids()

    def _load_configuration(self) -> None:
        """Validate and load required environment variables."""
        self.login_url = os.getenv(
            "SERVICIOS_LOGIN_URL",
            os.getenv("SERVICIOS_STAGING_LOGIN_URL", "https://admin.coyoacan.io/auth/login")
        )
        self.bookings_url = os.getenv(
            "SERVICIOS_BOOKINGS_URL",
            os.getenv("SERVICIOS_STAGING_BOOKINGS_URL", "https://admin.coyoacan.io/bookings?category=booking")
        )
        self.environment = "PRODUCTION" if "staging" not in self.bookings_url.lower() else "STAGING"

        self.email = os.getenv("SERVICIOS_ADMIN_EMAIL", "").strip()
        self.password = os.getenv("SERVICIOS_ADMIN_PASSWORD", "").strip()
        self.api_url = os.getenv("SERVICIOS_BOOKING_API_URL", "").strip()
        self.auth_token = os.getenv("SERVICIOS_BOOKING_AUTH_TOKEN", "").strip()
        
        try:
            self.poll_interval = int(os.getenv("SERVICIOS_BOOKING_POLL_INTERVAL", "30"))
        except ValueError:
            self.poll_interval = 30

        self.filter_status = os.getenv("SERVICIOS_FILTER_STATUS", "NEW").strip().upper()
        self.headless = os.getenv("SERVICIOS_HEADLESS", "false").lower() in ("true", "1", "yes")
        self.verify_ui = os.getenv("SERVICIOS_VERIFY_UI", "false").lower() in ("true", "1", "yes")

    def _setup_output_paths(self) -> None:
        """Initialize directories and file paths for forensic evidence."""
        output_dir_env = os.getenv("SERVICIOS_OUTPUT_DIR", "monitoring/output")
        self.output_dir = PROJECT_ROOT / output_dir_env
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.individual_bookings_dir = self.output_dir / "bookings"
        self.individual_bookings_dir.mkdir(parents=True, exist_ok=True)

        self.seen_ids_file = self.output_dir / "seen_booking_ids.json"
        self.csv_file = self.output_dir / "booking_monitor.csv"
        self.jsonl_file = self.output_dir / "bookings.jsonl"
        self.timeline_csv_file = self.output_dir / "polling_timeline.csv"

        self._initialize_csv_headers()
        self._initialize_timeline_headers()

    def _initialize_csv_headers(self) -> None:
        """Create CSV header if file does not exist."""
        if not self.csv_file.exists():
            headers = [
                "booking_id",
                "booking_custref",
                "current_status",
                "booking_status",
                "booking_date",
                "created_at",
                "updated_at",
                "pickup_date_time",
                "pickup_date_time_zone",
                "passenger_name",
                "city_name",
                "pickup_location",
                "drop_off_location",
                "flight_no",
                "vehicle_type",
                "currency",
                "total_amt",
                "token_source",
                "first_observed_at",
                "first_observed_timezone"
            ]
            with open(self.csv_file, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)

    def _initialize_timeline_headers(self) -> None:
        """Create polling timeline CSV header if file does not exist."""
        if not self.timeline_csv_file.exists():
            headers = [
                "cycle_number",
                "poll_timestamp",
                "timezone",
                "http_status",
                "response_time_ms",
                "total_bookings_in_api",
                "new_bookings_detected",
                "error_message"
            ]
            with open(self.timeline_csv_file, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)

    def _setup_signal_handlers(self) -> None:
        """Register graceful shutdown handlers for SIGINT (Ctrl+C) and SIGTERM."""
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame) -> None:
        """Gracefully handle termination signal."""
        self.running = False
        print("\n")
        print("=" * 60)
        print("                   MONITORING STOPPED")
        print("=" * 60)
        print(f"Total unique bookings tracked : {len(self.seen_booking_ids)}")
        print(f"New bookings detected today   : {self.new_bookings_detected_session}")
        print(f"Output directory              : {self.output_dir.resolve()}")
        print("=" * 60)
        self._save_seen_booking_ids()
        sys.exit(0)

    def _load_seen_booking_ids(self) -> None:
        """Load previously tracked booking IDs from disk to prevent duplicate reporting."""
        if self.seen_ids_file.exists():
            try:
                with open(self.seen_ids_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.seen_booking_ids = data
                    elif isinstance(data, list):
                        # Convert legacy list format to dictionary
                        self.seen_booking_ids = {str(item): {"first_observed_at": "unknown"} for item in data}
                logger.info("Loaded %d previously seen booking IDs from disk.", len(self.seen_booking_ids))
            except Exception as e:
                logger.warning("Could not read %s (%s). Starting fresh.", self.seen_ids_file, e)
                self.seen_booking_ids = {}

    def _save_seen_booking_ids(self) -> None:
        """Persist tracked booking IDs to disk."""
        try:
            temp_file = self.seen_ids_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.seen_booking_ids, f, indent=2)
            temp_file.replace(self.seen_ids_file)
        except Exception as e:
            logger.error("Failed to save seen booking IDs to disk: %s", e)

    def validate_environment(self) -> bool:
        """Check all required environment variables and show helpful guidance if missing."""
        errors = []

        if not self.email:
            errors.append("SERVICIOS_ADMIN_EMAIL is missing in .env")
        if not self.password:
            errors.append("SERVICIOS_ADMIN_PASSWORD is missing in .env")

        if not self.api_url:
            print("\n" + "=" * 65)
            print("  CONFIGURATION ERROR: SERVICIOS_BOOKING_API_URL IS NOT SET")
            print("=" * 65)
            print("To monitor the booking API, you must provide the exact API Request URL.\n")
            print("HOW TO GET THE EXACT BOOKING API URL:")
            print("  1. Open Google Chrome and navigate to:")
            print(f"     {self.login_url}")
            print("  2. Log in with your admin credentials.")
            print("  3. Open Chrome Developer Tools (F12 or Ctrl+Shift+I / Cmd+Option+I).")
            print("  4. Switch to the 'Network' tab and select the 'Fetch/XHR' filter.")
            print("  5. Navigate to the Bookings section:")
            print(f"     {self.bookings_url}")
            print("  6. Inspect the network requests and find the booking endpoint")
            print("     (e.g., /api/... or /admin/bookings...).")
            print("  7. Right-click the request -> Copy -> Copy URL.")
            print("  8. Add it to your .env file:")
            print("     SERVICIOS_BOOKING_API_URL=https://<exact_api_request_url_here>")
            print("=" * 65 + "\n")
            return False

        if errors:
            print("\n[ERROR] Missing required configuration:")
            for err in errors:
                print(f"  - {err}")
            return False

        return True

    def _matches_status_filter(self, booking: Dict[str, Any]) -> bool:
        """Check if booking matches the configured status filter (e.g. NEW)."""
        if not self.filter_status or self.filter_status in ("ALL", "*"):
            return True
        c_status = str(booking.get("current_status") or "").strip().upper()
        b_status = str(booking.get("booking_status") or "").strip().upper()
        return c_status == self.filter_status or b_status == self.filter_status

    @staticmethod
    def _find_token_in_object(obj: Any) -> Optional[str]:
        """Recursively scan nested dicts/lists/strings for JWT or auth tokens."""
        if isinstance(obj, str):
            val = obj.strip()
            # If string is JSON-encoded, parse and recurse
            if (val.startswith("{") and val.endswith("}")) or (val.startswith("[") and val.endswith("]")):
                try:
                    parsed = json.loads(val)
                    res = BookingMonitor._find_token_in_object(parsed)
                    if res:
                        return res
                except Exception:
                    pass
            # Check if this string itself is a JWT (typically 3 parts separated by dots, starts with eyJ)
            if val.startswith("eyJ") and len(val) > 20 and val.count(".") == 2:
                return val
            if val.lower().startswith("bearer ") and len(val) > 10:
                return val.split(" ", 1)[1].strip()
        elif isinstance(obj, dict):
            # Check priority keys first
            priority_keys = ["token", "accessToken", "access_token", "authToken", "auth_token", "jwt", "id_token", "user"]
            for pk in priority_keys:
                if pk in obj and obj[pk]:
                    candidate = obj[pk]
                    if isinstance(candidate, str) and candidate.strip():
                        sub = BookingMonitor._find_token_in_object(candidate)
                        if sub:
                            return sub
                        if len(candidate.strip()) > 15:
                            return candidate.strip()
                    res = BookingMonitor._find_token_in_object(candidate)
                    if res:
                        return res
            # Scan other keys
            for k, v in obj.items():
                if any(x in k.lower() for x in ["auth", "user", "token", "session", "persist"]):
                    res = BookingMonitor._find_token_in_object(v)
                    if res:
                        return res
        elif isinstance(obj, list):
            for item in obj:
                res = BookingMonitor._find_token_in_object(item)
                if res:
                    return res
        return None

    def authenticate_via_selenium(self) -> bool:
        """
        Log in to the Servicios Staging Admin using Selenium Chrome,
        extract session cookies and storage tokens, and attach them
        to the requests.Session.
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from pages.login_page import LoginPage
            from pages.dashboard_page import DashboardPage
            from pages.bookings_page import BookingsPage
        except ImportError as e:
            logger.error("Failed to import Selenium or Page Objects: %s", e)
            return False

        logger.info("Initializing Selenium Chrome for staging login...")
        
        options = Options()
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

        if self.headless:
            options.add_argument("--headless=new")

        driver = None
        try:
            driver = webdriver.Chrome(options=options)
            login_page = LoginPage(driver)
            dashboard_page = DashboardPage(driver)
            bookings_page = BookingsPage(driver)

            # 1. Navigate to login
            logger.info("Navigating to login page: %s", self.login_url)
            login_page.navigate_to_login(self.login_url)

            # 2. Perform Login
            logger.info("Submitting admin credentials...")
            login_page.login(self.email, self.password)

            # 3. Wait for Dashboard
            logger.info("Waiting for dashboard verification...")
            if not dashboard_page.is_dashboard_displayed(timeout=25):
                err = login_page.get_error_message(timeout=3)
                curr_url = driver.current_url
                if err:
                    logger.error("Login failed with message: '%s' (Current URL: %s)", err, curr_url)
                else:
                    logger.error("Login timeout: Dashboard was not reached. Current URL: %s", curr_url)
                return False

            logger.info("Dashboard reached successfully.")

            # 4. Navigate to Bookings page to ensure proper session context
            logger.info("Navigating to bookings page: %s", self.bookings_url)
            bookings_page.navigate_to_bookings(self.bookings_url)
            bookings_page.is_bookings_page_displayed(timeout=15)

            # 5. Extract Cookies
            cookies = driver.get_cookies()
            logger.info("Extracted %d session cookies from browser.", len(cookies))
            for cookie in cookies:
                self.session.cookies.set(
                    name=cookie["name"],
                    value=cookie["value"],
                    domain=cookie.get("domain", ""),
                    path=cookie.get("path", "/")
                )

            # 6. Extract token from browser storage
            storage_dump = driver.execute_script("""
                let items = {};
                for (let i = 0; i < localStorage.length; i++) {
                    let k = localStorage.key(i);
                    items[k] = localStorage.getItem(k);
                }
                for (let i = 0; i < sessionStorage.length; i++) {
                    let k = sessionStorage.key(i);
                    items['session_' + k] = sessionStorage.getItem(k);
                }
                return items;
            """)
            
            auto_detected_token = self._find_token_in_object(storage_dump)
            if not auto_detected_token:
                # Also check cookies
                for c in cookies:
                    cname = c.get("name", "").lower()
                    if any(x in cname for x in ["token", "jwt", "auth"]):
                        cval = c.get("value", "")
                        if cval:
                            auto_detected_token = cval
                            break

            # Determine origin from bookings URL
            from urllib.parse import urlparse
            parsed_origin = urlparse(self.bookings_url)
            origin_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"

            # Setup default headers
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": self.bookings_url,
                "Origin": origin_url
            })

            # Attach Bearer token if present (env override takes precedence)
            token_to_use = self.auth_token or auto_detected_token
            if token_to_use:
                # Only log the presence of token, never its value
                logger.info("Authorization token detected and configured for API requests.")
                if not token_to_use.lower().startswith("bearer "):
                    self.session.headers["Authorization"] = f"Bearer {token_to_use}"
                else:
                    self.session.headers["Authorization"] = token_to_use
            else:
                logger.warning("No Authorization token found in browser storage. If API requires Bearer auth, set SERVICIOS_BOOKING_AUTH_TOKEN in .env.")

            logger.info("Authentication complete. Browser session transferred to requests engine.")
            return True

        except Exception as e:
            logger.error("Selenium authentication encountered an error: %s", e, exc_info=True)
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _parse_api_response(self, response_json: Any) -> Tuple[List[Dict[str, Any]], int]:
        """
        Safely extract the list of bookings and total count from various API response shapes.
        Expected shape: { success: true, data: { total: N, data: [ ... ] } }
        """
        bookings = []
        total = 0

        if isinstance(response_json, dict):
            # Check nested data.data
            data_field = response_json.get("data")
            if isinstance(data_field, dict):
                total = data_field.get("total", 0)
                raw_list = data_field.get("data", [])
                if isinstance(raw_list, list):
                    bookings = raw_list
            elif isinstance(data_field, list):
                bookings = data_field
                total = len(bookings)
            elif "bookings" in response_json and isinstance(response_json["bookings"], list):
                bookings = response_json["bookings"]
                total = len(bookings)
        elif isinstance(response_json, list):
            bookings = response_json
            total = len(bookings)

        if total == 0 and bookings:
            total = len(bookings)

        return bookings, total

    def _get_current_timestamps(self) -> Tuple[str, str]:
        """
        Generate timezone-aware local ISO 8601 timestamp and timezone identifier.
        Generated on the monitoring machine at the exact second of observation.
        """
        now = datetime.now().astimezone()
        first_observed_at = now.isoformat()
        
        # Determine timezone name / offset
        tz_offset = now.strftime("%z")
        tz_name = now.tzname() or ""
        first_observed_timezone = f"{tz_offset} ({tz_name})".strip() if tz_name else tz_offset

        return first_observed_at, first_observed_timezone

    def _record_timeline_cycle(
        self,
        cycle_number: int,
        http_status: int,
        response_time_ms: int,
        total_bookings: int,
        new_bookings: int,
        error_message: str = ""
    ) -> None:
        """Record every polling cycle for timeline analysis."""
        timestamp, tz_str = self._get_current_timestamps()
        try:
            with open(self.timeline_csv_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    cycle_number,
                    timestamp,
                    tz_str,
                    http_status,
                    response_time_ms,
                    total_bookings,
                    new_bookings,
                    error_message
                ])
        except Exception as e:
            logger.error("Failed to append to timeline CSV: %s", e)

    def _save_new_booking(self, booking: Dict[str, Any], first_observed_at: str, first_observed_timezone: str) -> None:
        """
        Save newly detected booking across all forensic output targets:
        1. booking_monitor.csv
        2. bookings.jsonl (complete JSON + forensic metadata)
        3. individual JSON file
        """
        booking_id = str(booking.get("booking_id") or booking.get("id") or "").strip()

        # 1. Append to CSV
        csv_row = [
            booking_id,
            booking.get("booking_custref", ""),
            booking.get("current_status", ""),
            booking.get("booking_status", ""),
            booking.get("booking_date", ""),
            booking.get("created_at", ""),
            booking.get("updated_at", ""),
            booking.get("pickup_date_time", ""),
            booking.get("pickup_date_time_zone", ""),
            booking.get("passenger_name", ""),
            booking.get("city_name", ""),
            booking.get("pickup_location", ""),
            booking.get("drop_off_location", ""),
            booking.get("flight_no", ""),
            booking.get("vehicle_type", ""),
            booking.get("currency", ""),
            booking.get("total_amt", ""),
            booking.get("token_source", ""),
            first_observed_at,
            first_observed_timezone
        ]
        with open(self.csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(csv_row)

        # 2. Append full raw JSON to JSONL with forensic metadata
        forensic_payload = {
            "first_observed_at": first_observed_at,
            "first_observed_timezone": first_observed_timezone,
            "raw_booking": booking
        }
        with open(self.jsonl_file, mode="a", encoding="utf-8") as f:
            f.write(json.dumps(forensic_payload, ensure_ascii=False) + "\n")

        # 3. Save individual JSON for easy developer ticket attachments
        single_json_path = self.individual_bookings_dir / f"booking_{booking_id}.json"
        with open(single_json_path, mode="w", encoding="utf-8") as f:
            json.dump(forensic_payload, f, indent=2, ensure_ascii=False)

    def _print_new_booking_card(self, booking: Dict[str, Any], first_observed_at: str) -> None:
        """Format and print a clean terminal alert when a new booking is observed."""
        booking_id = str(booking.get("booking_id") or booking.get("id") or "N/A")
        cust_ref = str(booking.get("booking_custref") or "N/A")
        current_status = str(booking.get("current_status") or "N/A")
        booking_status = str(booking.get("booking_status") or "N/A")
        created_at = str(booking.get("created_at") or "N/A")
        passenger = str(booking.get("passenger_name") or "N/A")
        pickup = str(booking.get("pickup_location") or "N/A")
        dropoff = str(booking.get("drop_off_location") or "N/A")

        # Truncate long locations for clean card display
        if len(pickup) > 55:
            pickup = pickup[:52] + "..."
        if len(dropoff) > 55:
            dropoff = dropoff[:52] + "..."

        print("\n" + "=" * 60)
        print("                 NEW BOOKING DETECTED")
        print("=" * 60)
        print(f"Booking ID       : {booking_id}")
        print(f"Customer Ref     : {cust_ref}")
        print(f"Current Status   : {current_status}")
        print(f"Booking Status   : {booking_status}")
        print(f"Created At       : {created_at}")
        print(f"Observed At      : {first_observed_at}")
        print(f"Passenger        : {passenger}")
        print(f"Pickup           : {pickup}")
        print(f"Dropoff          : {dropoff}")
        print("\nSaved to:")
        print(f"  {self.csv_file.relative_to(PROJECT_ROOT)}")
        print(f"  {self.jsonl_file.relative_to(PROJECT_ROOT)}")
        print("=" * 60 + "\n")

    def poll_once(self) -> None:
        """Execute a single polling cycle against the booking API."""
        self.poll_cycle += 1
        time_str = datetime.now().strftime("%H:%M:%S")
        print(f"[{time_str}] Checking bookings (Cycle #{self.poll_cycle})...")

        start_time = time.time()
        http_status = 0
        response_time_ms = 0
        total_bookings_count = 0
        new_detected_in_cycle = 0

        try:
            response = self.session.get(self.api_url, timeout=30)
            response_time_ms = int((time.time() - start_time) * 1000)
            http_status = response.status_code

            time_str = datetime.now().strftime("%H:%M:%S")
            print(f"[{time_str}] API status: {http_status} ({response_time_ms}ms)")

            if http_status in (401, 403):
                logger.error("Authentication appears to have expired (HTTP %d).", http_status)
                self._record_timeline_cycle(
                    self.poll_cycle, http_status, response_time_ms, 0, 0,
                    f"Authentication expired (HTTP {http_status})"
                )
                print(f"[{time_str}] Warning: Authentication expired. Will attempt re-polling...")
                return

            if http_status != 200:
                logger.warning("API returned non-200 status code: %d", http_status)
                self._record_timeline_cycle(
                    self.poll_cycle, http_status, response_time_ms, 0, 0,
                    f"HTTP error {http_status}: {response.text[:200]}"
                )
                return

            # Parse JSON
            try:
                response_json = response.json()
            except ValueError as json_err:
                logger.error("Failed to parse JSON response: %s", json_err)
                self._record_timeline_cycle(
                    self.poll_cycle, http_status, response_time_ms, 0, 0,
                    f"JSON parse error: {json_err}"
                )
                return

            bookings, total_count = self._parse_api_response(response_json)
            total_bookings_count = len(bookings)

            # Filter bookings by status (e.g., NEW)
            if self.filter_status and self.filter_status not in ("ALL", "*"):
                active_bookings = [b for b in bookings if self._matches_status_filter(b)]
            else:
                active_bookings = bookings

            time_str = datetime.now().strftime("%H:%M:%S")
            filter_note = f" (Matching '{self.filter_status}': {len(active_bookings)})" if (self.filter_status and self.filter_status not in ("ALL", "*")) else ""
            print(f"[{time_str}] Bookings received: {total_bookings_count}{filter_note}")

            # Baseline initialization
            if not self.baseline_initialized:
                baseline_ts, baseline_tz = self._get_current_timestamps()
                for b in active_bookings:
                    bid = str(b.get("booking_id") or b.get("id") or "").strip()
                    if bid:
                        prev_entry = self.seen_booking_ids.get(bid, {})
                        prev_ts = prev_entry.get("first_observed_at")
                        observed_ts = baseline_ts if (not prev_ts or prev_ts == "BASELINE_INITIAL") else prev_ts
                        observed_tz = baseline_tz if (not prev_entry.get("first_observed_timezone") or prev_entry.get("first_observed_timezone") == "BASELINE") else prev_entry.get("first_observed_timezone")

                        self.seen_booking_ids[bid] = {
                            "booking_id": bid,
                            "booking_custref": b.get("booking_custref", ""),
                            "passenger_name": b.get("passenger_name", ""),
                            "current_status": b.get("current_status", ""),
                            "booking_status": b.get("booking_status", ""),
                            "pickup_location": b.get("pickup_location", ""),
                            "drop_off_location": b.get("drop_off_location", ""),
                            "created_at": b.get("created_at", ""),
                            "flight_no": b.get("flight_no", ""),
                            "first_observed_at": observed_ts,
                            "first_observed_timezone": observed_tz,
                            "is_baseline": True,
                            "raw_booking": b
                        }
                self.baseline_initialized = True
                self._save_seen_booking_ids()
                print(f"[{time_str}] Baseline initialized with {len(self.seen_booking_ids)} bookings (Timestamp: {baseline_ts}).")
                self._record_timeline_cycle(
                    self.poll_cycle, http_status, response_time_ms, total_bookings_count, 0,
                    f"Baseline initialized ({len(self.seen_booking_ids)} {self.filter_status})"
                )
                return

            # Detection of new bookings in subsequent cycles
            for b in active_bookings:
                bid = str(b.get("booking_id") or b.get("id") or "").strip()
                if not bid:
                    continue

                if bid not in self.seen_booking_ids:
                    # Brand new booking detected!
                    first_observed_at, first_observed_tz = self._get_current_timestamps()
                    self.seen_booking_ids[bid] = {
                        "booking_id": bid,
                        "booking_custref": b.get("booking_custref", ""),
                        "passenger_name": b.get("passenger_name", ""),
                        "current_status": b.get("current_status", ""),
                        "booking_status": b.get("booking_status", ""),
                        "pickup_location": b.get("pickup_location", ""),
                        "drop_off_location": b.get("drop_off_location", ""),
                        "created_at": b.get("created_at", ""),
                        "flight_no": b.get("flight_no", ""),
                        "first_observed_at": first_observed_at,
                        "first_observed_timezone": first_observed_tz,
                        "is_baseline": False,
                        "raw_booking": b
                    }
                    self._save_new_booking(b, first_observed_at, first_observed_tz)
                    self._print_new_booking_card(b, first_observed_at)
                    new_detected_in_cycle += 1
                    self.new_bookings_detected_session += 1
                else:
                    # Enrich existing entry with full booking details if missing
                    if "passenger_name" not in self.seen_booking_ids[bid]:
                        self.seen_booking_ids[bid].update({
                            "booking_id": bid,
                            "booking_custref": b.get("booking_custref", ""),
                            "passenger_name": b.get("passenger_name", ""),
                            "current_status": b.get("current_status", ""),
                            "booking_status": b.get("booking_status", ""),
                            "pickup_location": b.get("pickup_location", ""),
                            "drop_off_location": b.get("drop_off_location", ""),
                            "created_at": b.get("created_at", ""),
                            "flight_no": b.get("flight_no", ""),
                            "raw_booking": b
                        })

            if new_detected_in_cycle > 0:
                self._save_seen_booking_ids()
                print(f"Total tracked bookings: {len(self.seen_booking_ids)}")

            self._record_timeline_cycle(
                self.poll_cycle, http_status, response_time_ms, total_bookings_count, new_detected_in_cycle
            )

        except requests.exceptions.Timeout:
            time_str = datetime.now().strftime("%H:%M:%S")
            logger.warning("API request timed out (30s).")
            self._record_timeline_cycle(self.poll_cycle, 408, 30000, 0, 0, "Request Timeout (30s)")
        except requests.exceptions.ConnectionError as conn_err:
            time_str = datetime.now().strftime("%H:%M:%S")
            logger.warning("Network/connection error: %s", conn_err)
            self._record_timeline_cycle(self.poll_cycle, 0, 0, 0, 0, f"Connection error: {conn_err}")
        except Exception as e:
            time_str = datetime.now().strftime("%H:%M:%S")
            logger.error("Unexpected error during poll cycle: %s", e, exc_info=True)
            self._record_timeline_cycle(self.poll_cycle, 0, 0, 0, 0, f"Unexpected error: {e}")

    def _start_dashboard_server(self, port: int = 8080) -> int:
        """Start a lightweight embedded HTTP server on a daemon thread for the dashboard."""
        monitoring_dir = PROJECT_ROOT / "monitoring"

        class DashboardHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(monitoring_dir), **kwargs)

            def do_GET(self):
                if self.path in ("/", ""):
                    self.path = "/dashboard.html"
                return super().do_GET()

            def log_message(self, format, *args):
                # Suppress noisy HTTP logs in main monitor terminal
                pass

            def end_headers(self):
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Access-Control-Allow-Origin", "*")
                super().end_headers()

        socketserver.TCPServer.allow_reuse_address = True
        actual_port = port
        httpd = None
        for p in [port, 8081, 8082, 8090]:
            try:
                httpd = socketserver.TCPServer(("", p), DashboardHandler)
                actual_port = p
                break
            except OSError:
                continue

        if httpd:
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            return actual_port
        return 0

    def run(self) -> None:
        """Main monitoring loop."""
        if not self.validate_environment():
            sys.exit(1)

        # Start the embedded dashboard web server
        dashboard_port = self._start_dashboard_server(port=8080)
        dashboard_url = f"http://localhost:{dashboard_port}" if dashboard_port else "Disabled"

        print("\n" + "=" * 60)
        print("           SERVICIOS BOOKING MONITOR")
        print("=" * 60)
        print(f"Environment     : {self.environment}")
        print(f"Target URL      : {self.bookings_url}")
        print(f"Status Filter   : {self.filter_status}")
        print(f"Live Dashboard  : {dashboard_url}")
        print(f"Poll Interval   : {self.poll_interval} seconds")
        print(f"Output Directory: {self.output_dir.resolve()}")
        print("=" * 60 + "\n")

        # Authenticate via Selenium
        auth_success = self.authenticate_via_selenium()
        if not auth_success:
            logger.error("Authentication failed. Cannot start API monitor.")
            sys.exit(1)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Live Dashboard is available at: {dashboard_url}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting API monitoring loop (Press Ctrl+C to stop)...\n")

        while self.running:
            self.poll_once()
            if not self.running:
                break
            time_str = datetime.now().strftime("%H:%M:%S")
            print(f"[{time_str}] Next check in {self.poll_interval} seconds...\n")
            
            # Sleep in 1-second chunks to respond immediately to Ctrl+C
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)


def main():
    monitor = BookingMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
