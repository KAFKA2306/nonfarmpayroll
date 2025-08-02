#!/usr/bin/env python3
"""
Simple HTTP server to serve the Employment Statistics Dashboard
Serves the HTML dashboard with proper CORS headers for local file access
"""

import http.server
import socketserver
import webbrowser
import os
import sys
from pathlib import Path

class DashboardHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler with CORS headers"""
    
    def end_headers(self):
        # Add CORS headers to allow local file access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.end_headers()

def serve_dashboard(port=8080, open_browser=True):
    """
    Start the dashboard web server
    
    Args:
        port (int): Port to serve on (default: 8080)
        open_browser (bool): Whether to open browser automatically
    """
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Check if required files exist
    required_files = [
        'dashboard.html',
        'dashboard.css', 
        'dashboard.js',
        'data_processed/nfp_revisions.csv',
        'data_processed/summary_report.json'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("⚠️  Warning: Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        print("\nThe dashboard may not work correctly.")
        print("Run the data processing pipeline first to generate missing data files.")
        print("")
    
    # Start server
    try:
        with socketserver.TCPServer(("", port), DashboardHTTPRequestHandler) as httpd:
            dashboard_url = f"http://localhost:{port}/dashboard.html"
            
            print("🎯 Employment Statistics Dashboard Server")
            print("=" * 50)
            print(f"Server running at: {dashboard_url}")
            print(f"Project directory: {project_dir}")
            print("")
            print("📊 Available endpoints:")
            print(f"   Dashboard:     {dashboard_url}")
            print(f"   CSV Data:      http://localhost:{port}/data_processed/nfp_revisions.csv")
            print(f"   JSON Summary:  http://localhost:{port}/data_processed/summary_report.json")
            print("")
            print("Press Ctrl+C to stop the server")
            print("=" * 50)
            
            # Open browser automatically
            if open_browser:
                print(f"🌐 Opening browser...")
                try:
                    webbrowser.open(dashboard_url)
                except Exception as e:
                    print(f"Could not open browser automatically: {e}")
                    print(f"Please open {dashboard_url} manually")
            
            # Start serving
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
        sys.exit(0)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is already in use")
            print(f"Try a different port: python serve_dashboard.py --port {port + 1}")
            sys.exit(1)
        else:
            print(f"❌ Server error: {e}")
            sys.exit(1)

def main():
    """Main function with command line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Serve Employment Statistics Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python serve_dashboard.py                    # Serve on port 8080
  python serve_dashboard.py --port 8090       # Serve on port 8090
  python serve_dashboard.py --no-browser      # Don't open browser
        """
    )
    
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8080,
        help='Port to serve on (default: 8080)'
    )
    
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Don\'t open browser automatically'
    )
    
    args = parser.parse_args()
    
    serve_dashboard(port=args.port, open_browser=not args.no_browser)

if __name__ == "__main__":
    main()