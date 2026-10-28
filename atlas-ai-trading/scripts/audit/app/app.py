"""Audit phase 1 (jetable) : application Databricks Apps minimale (bibliothèque standard uniquement)."""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class Hello(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("hello from atlas audit app".encode())


HTTPServer(("0.0.0.0", int(os.environ.get("DATABRICKS_APP_PORT", "8000"))), Hello).serve_forever()
