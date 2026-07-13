import http.server
import socketserver
import json
import os
import urllib.parse
from pathlib import Path

PORT = 8080
DASHBOARD_DIR = Path(__file__).parent
PROJECT_ROOT = DASHBOARD_DIR.parent.parent.parent

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == '/api/traces':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Find traces
            traces = []
            trace_dir = PROJECT_ROOT / "tests" / "regression"
            if trace_dir.exists():
                for f in trace_dir.glob("*.json"):
                    traces.append(f.name)
            
            response = json.dumps({"traces": traces})
            self.wfile.write(response.encode('utf-8'))
            return
            
        elif path.startswith('/api/traces/'):
            trace_name = path.split('/')[-1]
            trace_path = PROJECT_ROOT / "tests" / "regression" / trace_name
            
            if trace_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                with open(trace_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "Not Found"}')
            return

        return super().do_GET()

def run_server(port=PORT):
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"Serving dashboard at http://localhost:{port}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
