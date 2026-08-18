# Servicios Automation & Booking Monitor 🚀

Automated Selenium test framework, forensic booking synchronization monitor, and real-time visual analytics dashboard for the **Servicios Admin Platform** (`coyoacan.io`).

---

## 📌 Project Overview

This repository provides an enterprise-grade QA & Forensic Monitoring suite designed to:
1. **Automate Browser Workflows**: Page Object Model (POM) architecture using Selenium WebDriver for login, navigation, and booking inspection.
2. **Track Booking Synchronization**: Standalone background monitor querying the backend API to detect new bookings in real-time, isolating synchronization latencies (especially for Booking.com integrations).
3. **Forensic Evidence Logging**: Captures complete payloads, machine detection timestamps (`first_observed_at`), hash verification, timeline logs, and individual JSON artifacts.
4. **Visual Analytics Dashboard**: Interactive real-time dark-mode dashboard (`dashboard.html`) to visualize detected bookings, inspect JSON payloads, filter by status/city, and export reports.

---

## 📂 Repository Structure

```
selenium-servicios/
│
├── .env                              # Active environment configuration (credentials & endpoints)
├── .env.example                      # Configuration template
├── .gitignore                        # Git ignore rules (caches, venvs, IDE configs)
├── requirements.txt                  # Python dependencies
├── conftest.py                       # Pytest fixtures & Selenium WebDriver setup
├── README.md                         # Main repository documentation
│
├── pages/                            # Page Object Model (POM) classes
│   ├── __init__.py
│   ├── base_page.py                  # Common element actions & explicit wait utilities
│   ├── login_page.py                 # Servicios authentication flows & error assertions
│   ├── dashboard_page.py             # Post-login overview & navigation
│   └── bookings_page.py              # Bookings table interactions & verification
│
├── tests/                            # Test automation suite
│   ├── __init__.py
│   └── test_booking_monitor.py       # Pytest test cases for monitoring & UI flows
│
└── monitoring/                       # Forensic Monitoring & Dashboard Engine
    ├── booking_monitor.py            # Polling engine with automated cookie & JWT transfer
    ├── dashboard.html                # Visual real-time analytics dashboard
    ├── view_dashboard.py             # Dashboard launcher & local server
    ├── README.md                     # In-depth technical documentation on monitoring
    │
    └── output/                       # Forensic evidence storage (preserved across runs)
        ├── seen_booking_ids.json     # Persistent state ledger of tracked booking IDs
        ├── booking_monitor.csv       # Summary CSV of all detected bookings
        ├── bookings.jsonl            # Line-delimited raw JSON audit payloads
        ├── polling_timeline.csv      # Timeline of every polling cycle & API status
        └── bookings/                 # Individual pretty-printed JSON records
            ├── booking_434201181.json
            └── ...
```

---

## 💻 Office Laptop / New Machine Setup

Follow these steps to clone and run the repository on your office laptop or any new PC:

### 1. Clone the Repository
```bash
git clone https://github.com/PranavThakur07/selenium-servicios.git
cd selenium-servicios
```

### 2. Set Up a Python Virtual Environment
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*Note: If PowerShell execution policy prevents script execution, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.*

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Verify Configuration (`.env`)
The `.env` file contains the required credentials and endpoints. If `.env` is already in the repository, you can review it or customize it. If starting fresh:
```bash
# Copy template if .env does not exist
cp .env.example .env
```

Key configuration parameters in `.env`:
```ini
SERVICIOS_ADMIN_EMAIL=admin@admin.com
SERVICIOS_ADMIN_PASSWORD=your_password
SERVICIOS_LOGIN_URL=https://admin.coyoacan.io/auth/login
SERVICIOS_BOOKING_API_URL=https://backend.coyoacan.io/api/v1/admin/bookings/getAll-bookingdotcomdata?search=&page=1&limit=150&query=new&city_name=Madrid&fromDate=&toDate=
SERVICIOS_FILTER_STATUS=NEW
SERVICIOS_BOOKING_POLL_INTERVAL=30
SERVICIOS_HEADLESS=false
SERVICIOS_OUTPUT_DIR=monitoring/output
```

---

## 🚀 How to Run

### Option A: Run the Live Booking Monitor
Continuously polls the Servicios API and logs all newly detected bookings:
```bash
python monitoring/booking_monitor.py
```
- **Stop**: Press `Ctrl + C` at any time. All collected forensic evidence is safely saved to `monitoring/output/`.

### Option B: Launch the Interactive Visual Dashboard
View and analyze all tracked bookings, latency metrics, and inspect JSON payloads in your browser:
```bash
python monitoring/view_dashboard.py
```
Or open `monitoring/dashboard.html` directly in Google Chrome.

### Option C: Run Pytest Automation Tests
Run end-to-end Selenium test suites:
```bash
pytest -v
```

---

## 🔍 Forensic Data & Evidence Artifacts

All data captured by the monitor is saved into `monitoring/output/` and committed to the repository:

| Output File | Description |
| :--- | :--- |
| `seen_booking_ids.json` | State database preventing duplicates across restarts and sessions. |
| `booking_monitor.csv` | Tabular summary containing `booking_id`, `created_at`, `first_observed_at`, passenger names, and route details. |
| `bookings.jsonl` | Complete, unmodified raw JSON response payloads enriched with observation metadata. |
| `polling_timeline.csv` | Chronological record of each cycle (timestamp, HTTP status, latency ms, booking count, errors). |
| `bookings/booking_<id>.json` | Individual formatted JSON files ready to attach to bug tickets or share with backend engineering. |

---

## 🛡️ Requirements & Compatibility
- **Python**: 3.10+
- **Browser**: Google Chrome (Selenium automatically resolves chromedriver via `webdriver-manager` / Selenium 4.15+ built-in manager)
- **OS**: Windows, macOS, Linux

---

## 👤 Author
- **Pranav Thakur** ([GitHub Profile](https://github.com/PranavThakur07))
