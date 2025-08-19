#!/usr/bin/env python3
"""
Backend Testing for ArgumentSettler Dashboard
Tests the Python data fetching script and static file serving
"""

import requests
import sys
import json
import os
from datetime import datetime

class ArgumentSettlerTester:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, test_func):
        """Run a single test"""
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            success = test_func()
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - {name}")
            else:
                print(f"❌ Failed - {name}")
            return success
        except Exception as e:
            print(f"❌ Failed - {name}: {str(e)}")
            return False

    def test_favicon(self):
        """Test favicon loads correctly"""
        response = requests.get(f"{self.base_url}/favicon.ico")
        success = response.status_code == 200
        if success:
            print(f"   Favicon size: {len(response.content)} bytes")
        return success

    def test_data_endpoint(self):
        """Test data/metrics.json endpoint"""
        response = requests.get(f"{self.base_url}/argumentsettler-dashboard/data/metrics.json")
        success = response.status_code == 200
        if success:
            data = response.json()
            print(f"   Billable Hours: {data.get('billable_hours', 'N/A')}h")
            print(f"   Time Away: {data.get('absent_from_home_hours', 'N/A')}h")
            print(f"   Total Entries: {data.get('total_entries', 'N/A')}")
            print(f"   Last Updated: {data.get('last_updated', 'N/A')}")
        return success

    def test_dashboard_html(self):
        """Test dashboard HTML loads"""
        response = requests.get(f"{self.base_url}/argumentsettler-dashboard/")
        success = response.status_code == 200 and "ArgumentSettler Dashboard" in response.text
        if success:
            print(f"   HTML size: {len(response.text)} bytes")
        return success

    def test_static_assets(self):
        """Test static assets load"""
        # Test CSS
        response = requests.get(f"{self.base_url}/argumentsettler-dashboard/static/css/main.0c8af8a7.css")
        css_success = response.status_code == 200
        
        # Test JS
        response = requests.get(f"{self.base_url}/argumentsettler-dashboard/static/js/main.08e231fb.js")
        js_success = response.status_code == 200
        
        success = css_success and js_success
        if success:
            print(f"   CSS and JS assets loaded successfully")
        return success

    def test_python_script_structure(self):
        """Test Python script exists and has correct structure"""
        script_path = "/app/scripts/fetch-toggl-data.py"
        success = os.path.exists(script_path)
        if success:
            with open(script_path, 'r') as f:
                content = f.read()
                # Check for key components
                has_toggl_class = "class TogglDataFetcher" in content
                has_main_func = "def main():" in content
                has_api_calls = "requests.get" in content
                success = has_toggl_class and has_main_func and has_api_calls
                if success:
                    print(f"   Script structure verified")
        return success

    def test_data_file_structure(self):
        """Test data file has correct structure"""
        data_path = "/app/data/metrics.json"
        success = os.path.exists(data_path)
        if success:
            with open(data_path, 'r') as f:
                data = json.load(f)
                required_fields = [
                    'billable_hours', 'absent_from_home_hours', 
                    'commute_back_home_stats', 'home_office_end_stats',
                    'late_work_frequency', 'total_entries'
                ]
                success = all(field in data for field in required_fields)
                if success:
                    print(f"   All required fields present")
        return success

def main():
    print("🚀 ArgumentSettler Dashboard Testing")
    print("=" * 50)
    
    tester = ArgumentSettlerTester()
    
    # Run all tests
    tests = [
        ("Favicon Loading", tester.test_favicon),
        ("Data Endpoint", tester.test_data_endpoint),
        ("Dashboard HTML", tester.test_dashboard_html),
        ("Static Assets", tester.test_static_assets),
        ("Python Script Structure", tester.test_python_script_structure),
        ("Data File Structure", tester.test_data_file_structure),
    ]
    
    for test_name, test_func in tests:
        tester.run_test(test_name, test_func)
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())