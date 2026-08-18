"""
Unit tests for the standalone BookingMonitor.
Tests baseline initialization, new booking detection, polling timeline recording,
error resilience, and file persistence.
"""

import json
import csv
import os
import shutil
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from monitoring.booking_monitor import BookingMonitor

TEST_OUTPUT_DIR = Path(__file__).resolve().parent / "test_output"

SAMPLE_BASELINE_BOOKING = {
    "id": 396100,
    "booking_id": "100000001",
    "booking_custref": "REF001",
    "city_name": "Newark Liberty International Airport",
    "current_status": "NEW",
    "booking_date": "2026-08-17T20:00:00.000Z",
    "pickup_date_time": "2026-08-24T18:00:00.000Z",
    "pickup_date_time_zone": "America/New_York",
    "passenger_name": "Alice Smith",
    "mobile_no": "+1234567890",
    "pickup_location": "EWR Airport",
    "drop_off_location": "Times Square Hotel",
    "flight_no": "UA100",
    "vehicle_type": "SEDAN",
    "currency": "USD",
    "total_amt": 75,
    "token_source": "client1",
    "created_at": "2026-08-17T20:00:00.000Z",
    "updated_at": "2026-08-17T20:00:00.000Z",
    "booking_status": "Pending"
}

SAMPLE_NEW_BOOKING = {
    "id": 396149,
    "booking_id": "156926547",
    "booking_custref": "877068503",
    "city_name": "Newark Liberty International Airport",
    "current_status": "NEW",
    "booking_date": "2026-08-17T21:33:58.000Z",
    "pickup_date_time": "2026-08-24T18:05:00.000Z",
    "pickup_date_time_zone": "America/New_York",
    "passenger_name": "Elisa Cianciolo",
    "mobile_no": "+393495549068",
    "pickup_location": "Newark Liberty International Airport (EWR)",
    "drop_off_location": "Hotel Riu Plaza New York Times Square",
    "flight_no": "LH8958",
    "vehicle_type": "PEOPLE_CARRIER",
    "currency": "USD",
    "total_amt": 80,
    "token_source": "client3",
    "created_at": "2026-08-17T21:36:05.000Z",
    "updated_at": "2026-08-17T22:26:21.000Z",
    "booking_status": "Pending"
}


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Isolate output files to a clean test directory."""
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SERVICIOS_OUTPUT_DIR", str(TEST_OUTPUT_DIR))
    monkeypatch.setenv("SERVICIOS_ADMIN_EMAIL", "test_qa@coyoacan.io")
    monkeypatch.setenv("SERVICIOS_ADMIN_PASSWORD", "test_secret_pass")
    monkeypatch.setenv("SERVICIOS_BOOKING_API_URL", "https://staging-admin.coyoacan.io/api/mock/bookings")
    monkeypatch.setenv("SERVICIOS_BOOKING_POLL_INTERVAL", "5")

    yield

    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)


def test_missing_api_url_validation(monkeypatch):
    """Validate that missing SERVICIOS_BOOKING_API_URL fails gracefully with helpful message."""
    monkeypatch.setenv("SERVICIOS_BOOKING_API_URL", "")
    monitor = BookingMonitor()
    assert monitor.validate_environment() is False


def test_baseline_initialization():
    """Verify that the first poll populates baseline without reporting false alerts."""
    monitor = BookingMonitor()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "message": "Booking data fetched successfully",
        "data": {
            "total": 1,
            "data": [SAMPLE_BASELINE_BOOKING]
        }
    }
    
    with patch.object(monitor.session, "get", return_value=mock_response):
        monitor.poll_once()

    # Baseline should be marked initialized
    assert monitor.baseline_initialized is True
    assert "100000001" in monitor.seen_booking_ids
    assert monitor.new_bookings_detected_session == 0

    # CSV should only contain headers, no data rows yet
    with open(monitor.csv_file, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 1  # only header row

    # Timeline CSV should have 1 record with total_bookings_in_api = 1 and new_bookings_detected = 0
    with open(monitor.timeline_csv_file, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 2  # header + 1 cycle
        assert reader[1][0] == "1"  # cycle 1
        assert reader[1][3] == "200"  # status 200
        assert reader[1][5] == "1"  # total bookings
        assert reader[1][6] == "0"  # new bookings


def test_new_booking_detection():
    """Verify that new bookings in subsequent polls are recorded across all forensic targets."""
    monitor = BookingMonitor()

    # 1. Baseline poll
    mock_response_1 = MagicMock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = {
        "success": True,
        "data": {
            "total": 1,
            "data": [SAMPLE_BASELINE_BOOKING]
        }
    }
    with patch.object(monitor.session, "get", return_value=mock_response_1):
        monitor.poll_once()

    # 2. Subsequent poll with 1 new booking
    mock_response_2 = MagicMock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = {
        "success": True,
        "data": {
            "total": 2,
            "data": [SAMPLE_BASELINE_BOOKING, SAMPLE_NEW_BOOKING]
        }
    }
    with patch.object(monitor.session, "get", return_value=mock_response_2):
        monitor.poll_once()

    # Verify detection count
    assert monitor.new_bookings_detected_session == 1
    assert "156926547" in monitor.seen_booking_ids

    # Verify CSV output
    with open(monitor.csv_file, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        assert len(rows) == 2  # header + 1 new row
        new_row = rows[1]
        assert new_row[0] == "156926547"  # booking_id
        assert new_row[1] == "877068503"  # custref
        assert new_row[9] == "Elisa Cianciolo"  # passenger
        assert new_row[18] != ""  # first_observed_at
        assert new_row[19] != ""  # first_observed_timezone

    # Verify JSONL output
    with open(monitor.jsonl_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        jsonl_record = json.loads(lines[0])
        assert jsonl_record["first_observed_at"] != ""
        assert jsonl_record["raw_booking"]["booking_id"] == "156926547"
        assert jsonl_record["raw_booking"]["passenger_name"] == "Elisa Cianciolo"

    # Verify individual JSON output
    single_json_path = monitor.individual_bookings_dir / "booking_156926547.json"
    assert single_json_path.exists()
    with open(single_json_path, "r", encoding="utf-8") as f:
        single_data = json.load(f)
        assert single_data["raw_booking"]["booking_id"] == "156926547"


def test_persistence_across_restarts():
    """Verify that restarting the monitor retains seen IDs from disk without re-alerting."""
    # First run: Baseline + 1 new booking
    monitor_1 = BookingMonitor()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": {
            "total": 1,
            "data": [SAMPLE_NEW_BOOKING]
        }
    }
    with patch.object(monitor_1.session, "get", return_value=mock_resp):
        monitor_1.poll_once()

    assert "156926547" in monitor_1.seen_booking_ids
    monitor_1._save_seen_booking_ids()

    # Second run: Starts afresh, loads seen_booking_ids.json
    monitor_2 = BookingMonitor()
    assert "156926547" in monitor_2.seen_booking_ids

    # Poll with same booking again
    with patch.object(monitor_2.session, "get", return_value=mock_resp):
        monitor_2.poll_once()

    # Should NOT be alerted as new
    assert monitor_2.new_bookings_detected_session == 0


def test_error_resilience():
    """Verify monitor handles transient HTTP 500/503 errors and connection errors without crashing."""
    monitor = BookingMonitor()

    # Simulate HTTP 500
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.text = "Internal Server Error"
    with patch.object(monitor.session, "get", return_value=mock_500):
        monitor.poll_once()

    # Simulate Connection Timeout
    import requests
    with patch.object(monitor.session, "get", side_effect=requests.exceptions.Timeout("Timeout")):
        monitor.poll_once()

    # Ensure monitor continues running and logs timeline cycles
    assert monitor.poll_cycle == 2
    with open(monitor.timeline_csv_file, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        assert len(rows) == 3  # header + 2 cycles
        assert rows[1][3] == "500"
        assert rows[2][3] == "408"


def test_status_filtering(monkeypatch):
    """Verify that only bookings matching the configured status filter (e.g. NEW) are tracked."""
    monkeypatch.setenv("SERVICIOS_FILTER_STATUS", "NEW")
    monitor = BookingMonitor()

    accepted_booking = dict(SAMPLE_BASELINE_BOOKING)
    accepted_booking["booking_id"] = "200000001"
    accepted_booking["current_status"] = "ACCEPTED"

    new_booking = dict(SAMPLE_BASELINE_BOOKING)
    new_booking["booking_id"] = "300000001"
    new_booking["current_status"] = "NEW"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": {
            "total": 2,
            "data": [accepted_booking, new_booking]
        }
    }

    with patch.object(monitor.session, "get", return_value=mock_resp):
        monitor.poll_once()

    # Only the NEW booking should be in seen_booking_ids
    assert "300000001" in monitor.seen_booking_ids
    assert "200000001" not in monitor.seen_booking_ids
    assert len(monitor.seen_booking_ids) == 1
