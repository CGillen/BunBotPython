"""
Keep-alive server for Render deployment
Provides a simple HTTP endpoint to prevent the service from sleeping
"""

import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logger = logging.getLogger('keep_alive')

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "BunBot"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default HTTP server logs
        pass

class KeepAliveServer:
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None
        
    def start(self):
        """Start the keep-alive server in a separate thread"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), HealthHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"Keep-alive server started on port {self.port}")
        except Exception as e:
            logger.warning(f"Failed to start keep-alive server: {e}")
    
    def stop(self):
        """Stop the keep-alive server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Keep-alive server stopped")

# Global instance
keep_alive_server = KeepAliveServer()

def start_keep_alive():
    """Start the keep-alive server"""
    keep_alive_server.start()

def stop_keep_alive():
    """Stop the keep-alive server"""
    keep_alive_server.stop()
