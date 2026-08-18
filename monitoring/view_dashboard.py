#!/usr/bin/env python3
"""
Lightweight Web Viewer for Servicios Booking Monitor Dashboard.
Serves the monitoring forensic dashboard on http://localhost:8080 with auto-reload.
"""

import os
import sys
import webbrowser
import http.server
import socketserver
from pathlib import Path

PORT = 8080
MONITORING_DIR = Path(__file__).resolve().parent

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MONITORING_DIR), **kwargs)

    def do_GET(self):
        # Redirect root / to /dashboard.html
        if self.path in ("/", ""):
            self.path = "/dashboard.html"
        return super().do_GET()

    def end_headers(self):
        # Disable caching so live log updates are instantly reflected
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def run_viewer():
    os.chdir(MONITORING_DIR)
    url = f"http://localhost:{PORT}/dashboard.html"
    
    print("\n" + "=" * 60)
    print("      SERVICIOS FORENSIC DASHBOARD VIEWER")
    print("=" * 60)
    print(f"Dashboard URL : {url}")
    print(f"Serving from  : {MONITORING_DIR}")
    print("Auto-refresh  : Every 10 seconds")
    print("=" * 60)
    print("Opening in browser... (Press Ctrl+C to stop viewer)\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard viewer stopped.")
            sys.exit(0)


if __name__ == "__main__":
    run_viewer()
