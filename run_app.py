#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HYCOM Data Downloader Flask Application Launcher
Simple script to run the Flask web application
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import and run the Flask app
from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("HYCOM Data Downloader - Web Interface")
    print("=" * 60)
    print("Starting Flask application...")
    print("Web interface will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        print("Goodbye!")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
