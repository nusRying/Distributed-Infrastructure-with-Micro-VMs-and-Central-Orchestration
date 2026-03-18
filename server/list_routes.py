import sys
import os
# Ensure current directory is in path
sys.path.append(os.getcwd())

try:
    from main import app
    print("Listing Registered Routes:")
    for route in app.routes:
        methods = getattr(route, 'methods', '[]')
        print(f"Path: {route.path} | Methods: {methods}")
except Exception as e:
    print(f"Error importing app: {e}")
