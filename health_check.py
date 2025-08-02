#!/usr/bin/env python3
"""
Simple health check endpoint for cloud deployment
"""
import os
import pickle
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json
import logging

logger = logging.getLogger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            try:
                # Check if bot is running by verifying pickle file exists
                pickle_file = os.getenv('PERSISTENCE_FILE', 'bybit_bot_dashboard_v4.1_enhanced.pkl')
                
                health_status = {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "pickle_file_exists": os.path.exists(pickle_file),
                    "bot_uptime": "running"
                }
                
                # Try to read pickle file to verify bot data integrity
                if os.path.exists(pickle_file):
                    try:
                        with open(pickle_file, 'rb') as f:
                            data = pickle.load(f)
                            health_status["positions_count"] = len(data.get('positions', {}))
                            health_status["monitors_count"] = len(data.get('enhanced_monitors', {}))
                    except Exception as e:
                        health_status["pickle_error"] = str(e)
                        health_status["status"] = "degraded"
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(health_status).encode())
                
            except Exception as e:
                error_response = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default HTTP logs to avoid spam
        pass

def start_health_server(port=8000):
    """Start health check server in background thread"""
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        logger.info(f"Health check server started on port {port}")
        return server
    except Exception as e:
        logger.warning(f"Could not start health check server: {e}")
        return None