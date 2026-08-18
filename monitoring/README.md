# Servicios Booking Monitor (Forensic Evidence & QA Tool)

## 1. Purpose of the Monitor
The Servicios Booking Monitor is a standalone, read-only Python tool designed to investigate intermittent booking synchronization delays between Booking.com and the Servicios Admin platform (specifically during the 00:00–02:00 Madrid time window). 

The tool continuously queries the staging booking API to establish an undeniable timeline of:
- When a booking first appears in the backend API.
- The exact machine timestamp (`first_observed_at` and timezone) when the monitoring process detected it.
- The complete raw booking payload for backend engineers to cross-reference with backend database logs.
- A per-cycle polling log (`polling_timeline.csv`) recording API availability, response times, and booking count progression.

---

## 2. Why It Is Staging-Only
- **Safety First**: Staging environment (`https://staging-admin.coyoacan.io`) ensures zero risk of disturbing production operations.
- **Verification**: Proves the correctness of the monitoring logic, cookie synchronization, baseline initialization, and forensic data output before any production monitoring is ever considered.
- **Controlled Testing**: Allows QA and backend engineers to simulate delayed synchronization without impacting real drivers or passengers.

---

## 3. Environment Variables
All configuration is managed via `.env` in the project root. Copy `.env.example` to `.env` before running:

```ini
# Admin Credentials
SERVICIOS_ADMIN_EMAIL=your_staging_email@example.com
SERVICIOS_ADMIN_PASSWORD=your_staging_password

# Target URLs (STAGING ONLY)
SERVICIOS_STAGING_LOGIN_URL=https://staging-admin.coyoacan.io/auth/login
SERVICIOS_STAGING_BOOKINGS_URL=https://staging-admin.coyoacan.io/bookings?category=booking

# Exact Staging Booking API Endpoint (Obtained via Chrome DevTools)
SERVICIOS_BOOKING_API_URL=https://staging-admin.coyoacan.io/api/v1/admin/bookings?category=booking&limit=150

# Optional: Bearer Token or Custom Auth Header (if required in addition to browser cookies)
SERVICIOS_BOOKING_AUTH_TOKEN=

# Monitoring Polling Interval in seconds (Default: 30)
SERVICIOS_BOOKING_POLL_INTERVAL=30

# Selenium Execution Mode (true = headless, false = visible browser window)
SERVICIOS_HEADLESS=false

# Future UI Verification toggle (Default: false)
SERVICIOS_VERIFY_UI=false

# Output directory for forensic evidence logs
SERVICIOS_OUTPUT_DIR=monitoring/output
```

---

## 4. How to Find the Exact Staging API URL Using Chrome DevTools
To ensure the monitor queries the exact same endpoint used by the web frontend:

1. Open **Google Chrome** and navigate to:
   `https://staging-admin.coyoacan.io/auth/login`
2. Log in with your admin credentials.
3. Open **Chrome Developer Tools** (`F12` or `Ctrl + Shift + I` / `Cmd + Option + I`).
4. Click on the **Network** tab and select the **Fetch/XHR** filter.
5. In the web application, navigate to **Bookings**:
   `https://staging-admin.coyoacan.io/bookings?category=booking`
6. Observe the incoming network requests. Look for the API request fetching the booking list (e.g., `bookings?category=booking...` or `/api/admin/bookings...`).
7. Click on the request -> In the **Headers** tab, find **Request URL**.
8. Right-click the URL -> **Copy** -> **Copy URL**.
9. Paste this into your `.env` file as `SERVICIOS_BOOKING_API_URL`.

---

## 5. How Authentication Works
1. **Automated Selenium Login**: The monitor launches Chrome, navigates to the login page, enters the credentials from `.env`, and waits for the post-login dashboard.
2. **Session Cookie Transfer**: Once the browser reaches the Bookings page, all authenticated session cookies are extracted (`driver.get_cookies()`) and transferred directly to a persistent `requests.Session`.
3. **Storage & Token Extraction**: The script also checks `localStorage` and `sessionStorage` for any active JWT/Bearer tokens and sets the `Authorization` header if found or if `SERVICIOS_BOOKING_AUTH_TOKEN` is configured.
4. **Lightweight Polling**: Once authenticated, the browser instance is cleanly released, and all subsequent polling is performed efficiently via `requests`.

---

## 6. How Baseline Detection Works
- When the monitor launches, the API may already return hundreds of active or past bookings.
- During the **first successful API poll**, the monitor collects all `booking_id`s present in the response and registers them in `seen_booking_ids.json` as baseline entries.
- The terminal outputs:
  ```
  [03:30:01] Baseline initialized with 150 bookings.
  ```
- **Zero false alerts**: None of the baseline bookings are logged as new or alerted.

---

## 7. How New Booking Detection Works
- On every subsequent polling cycle (every 30 seconds by default):
  1. The monitor fetches the latest booking list from the API.
  2. For every booking in the response, it extracts `booking["booking_id"]`.
  3. If a `booking_id` is NOT found in `seen_booking_ids`, it is identified as a **NEW BOOKING**.
  4. The monitor immediately generates a local machine timestamp (`first_observed_at`) with timezone information.
  5. The booking is logged across CSV, JSONL, individual JSON files, and printed as a card in the terminal.
  6. The `booking_id` is added to `seen_booking_ids.json` on disk to ensure it is never reported twice, even if the monitor is restarted.

---

## 8. What `first_observed_at` Means
- `created_at`: The timestamp when the booking was originally created according to the database or external platform (e.g., `2026-08-17T21:36:05.000Z`).
- `first_observed_at`: The **exact local time generated by the monitoring machine** when the monitor detected this booking appearing in the staging API for the very first time (e.g., `2026-08-18T03:32:05+05:30`).
- **Forensic Value**: Comparing `first_observed_at` against `created_at` provides definitive proof of synchronization latency (e.g., booking created at 00:15 but not visible in the API until 02:05).

---

## 9. Output Files
All forensic data is preserved under `monitoring/output/`:

| File | Description |
| :--- | :--- |
| `booking_monitor.csv` | Tabular summary containing all key fields (`booking_id`, `created_at`, `first_observed_at`, `passenger_name`, `pickup_location`, etc.). |
| `bookings.jsonl` | Line-delimited JSON storing the **complete, unmodified raw booking payload** enriched with forensic observation metadata. |
| `seen_booking_ids.json` | Persistent dictionary of all tracked IDs and their detection timestamps to prevent duplicates across restarts. |
| `polling_timeline.csv` | Complete timeline log of every single API check (cycle number, timestamp, HTTP status, response time ms, booking count, errors). |
| `bookings/booking_<id>.json` | Individual pretty-printed JSON file for each detected booking, ideal for attaching to Jira/backend bug tickets. |

---

## 10. How to Run
From the project root:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env
cp .env.example .env
# (Edit .env with your credentials and SERVICIOS_BOOKING_API_URL)

# 3. Start monitoring
python monitoring/booking_monitor.py
```

---

## 11. How to Stop
- Press `Ctrl + C` in the terminal.
- The script intercepts `SIGINT`/`SIGTERM`, safely flushes all data files to disk, and displays a summary banner:
  ```
  ============================================================
                     MONITORING STOPPED
  ============================================================
  Total unique bookings tracked : 151
  New bookings detected today   : 1
  Output directory              : .../monitoring/output
  ============================================================
  ```

---

## 12. How to Interpret the Collected Evidence
When presenting evidence to backend engineers:
1. Open `monitoring/output/booking_monitor.csv` to find the `booking_id` and compare `created_at` vs `first_observed_at`.
2. Check `monitoring/output/polling_timeline.csv` during the 00:00–02:00 Madrid window:
   - If total bookings stayed flat or dropped, and suddenly jumped after 02:00, this proves the API was not serving the bookings during that window.
3. Attach `monitoring/output/bookings/booking_<id>.json` to the bug ticket so the backend team has the full payload, `state_hash`, `token_source`, and IDs to search in their server logs.
