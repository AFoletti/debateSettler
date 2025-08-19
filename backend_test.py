#!/usr/bin/env python3
"""
Backend API Testing for ArgumentSettler Toggl Track Dashboard
Tests all API endpoints and validates expected data ranges
"""

import requests
import sys
import json
from datetime import datetime

class TogglDashboardTester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.results = {}

    def log_result(self, test_name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED")
        
        if details:
            print(f"   Details: {details}")
        
        self.results[test_name] = {
            "success": success,
            "details": details
        }

    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "status" in data and "timestamp" in data:
                    self.log_result("Health Check", True, f"Status: {data['status']}")
                    return True
                else:
                    self.log_result("Health Check", False, "Missing required fields in response")
                    return False
            else:
                self.log_result("Health Check", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Health Check", False, f"Exception: {str(e)}")
            return False

    def test_workspace_info_endpoint(self):
        """Test /api/workspace-info endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/workspace-info", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if "workspace_id" in data and "workspace_name" in data:
                    expected_workspace = "DRE-P"
                    if data["workspace_name"] == expected_workspace:
                        self.log_result("Workspace Info", True, 
                                      f"Workspace: {data['workspace_name']}, ID: {data['workspace_id']}")
                        return True
                    else:
                        self.log_result("Workspace Info", False, 
                                      f"Expected workspace 'DRE-P', got '{data['workspace_name']}'")
                        return False
                else:
                    self.log_result("Workspace Info", False, "Missing required fields in response")
                    return False
            else:
                self.log_result("Workspace Info", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Workspace Info", False, f"Exception: {str(e)}")
            return False

    def test_dashboard_metrics_endpoint(self):
        """Test /api/dashboard-metrics endpoint and validate expected data"""
        try:
            print("\n🔍 Testing Dashboard Metrics (this may take a moment to fetch from Toggl API)...")
            response = requests.get(f"{self.base_url}/api/dashboard-metrics", timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = [
                    "billable_hours", "absent_from_home_hours", "commute_back_home_stats",
                    "home_office_end_stats", "late_work_frequency", "date_range", "total_entries"
                ]
                
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    self.log_result("Dashboard Metrics Structure", False, 
                                  f"Missing fields: {missing_fields}")
                    return False
                
                self.log_result("Dashboard Metrics Structure", True, "All required fields present")
                
                # Validate expected data ranges based on the request
                self.validate_metrics_data(data)
                return True
                
            else:
                self.log_result("Dashboard Metrics", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Dashboard Metrics", False, f"Exception: {str(e)}")
            return False

    def validate_metrics_data(self, data):
        """Validate the metrics data against expected values"""
        print("\n📊 Validating Metrics Data:")
        
        # Expected values from the request
        expected_billable_hours = 88.97
        expected_absent_hours = 55.51
        expected_commute_sessions = 4
        expected_home_office_sessions = 8
        expected_late_work_percentage = 0
        expected_total_entries = 151
        
        # Validate billable hours
        billable_hours = data.get("billable_hours", 0)
        if abs(billable_hours - expected_billable_hours) < 1.0:  # Allow 1 hour tolerance
            self.log_result("Billable Hours Validation", True, 
                          f"Got {billable_hours}h (expected ~{expected_billable_hours}h)")
        else:
            self.log_result("Billable Hours Validation", False, 
                          f"Got {billable_hours}h, expected ~{expected_billable_hours}h")
        
        # Validate absent from home hours
        absent_hours = data.get("absent_from_home_hours", 0)
        if abs(absent_hours - expected_absent_hours) < 5.0:  # Allow 5 hour tolerance
            self.log_result("Absent Hours Validation", True, 
                          f"Got {absent_hours}h (expected ~{expected_absent_hours}h)")
        else:
            self.log_result("Absent Hours Validation", False, 
                          f"Got {absent_hours}h, expected ~{expected_absent_hours}h")
        
        # Validate commute sessions
        commute_count = data.get("commute_back_home_stats", {}).get("count", 0)
        if commute_count == expected_commute_sessions:
            self.log_result("Commute Sessions Validation", True, 
                          f"Got {commute_count} sessions (expected {expected_commute_sessions})")
        else:
            self.log_result("Commute Sessions Validation", False, 
                          f"Got {commute_count} sessions, expected {expected_commute_sessions}")
        
        # Validate home office sessions
        home_office_count = data.get("home_office_end_stats", {}).get("count", 0)
        if home_office_count == expected_home_office_sessions:
            self.log_result("Home Office Sessions Validation", True, 
                          f"Got {home_office_count} sessions (expected {expected_home_office_sessions})")
        else:
            self.log_result("Home Office Sessions Validation", False, 
                          f"Got {home_office_count} sessions, expected {expected_home_office_sessions}")
        
        # Validate late work frequency
        late_work_percentage = data.get("late_work_frequency", {}).get("percentage", -1)
        if late_work_percentage == expected_late_work_percentage:
            self.log_result("Late Work Frequency Validation", True, 
                          f"Got {late_work_percentage}% (expected {expected_late_work_percentage}%)")
        else:
            self.log_result("Late Work Frequency Validation", False, 
                          f"Got {late_work_percentage}%, expected {expected_late_work_percentage}%")
        
        # Validate total entries (allow some tolerance for time differences)
        total_entries = data.get("total_entries", 0)
        if abs(total_entries - expected_total_entries) < 10:  # Allow 10 entries tolerance
            self.log_result("Total Entries Validation", True, 
                          f"Got {total_entries} entries (expected ~{expected_total_entries})")
        else:
            self.log_result("Total Entries Validation", False, 
                          f"Got {total_entries} entries, expected ~{expected_total_entries}")
        
        # Print detailed metrics for review
        print(f"\n📋 Detailed Metrics Summary:")
        print(f"   Billable Hours: {billable_hours}h")
        print(f"   Time Away from Home: {absent_hours}h")
        print(f"   Commute Sessions: {commute_count}")
        print(f"   Home Office Sessions: {home_office_count}")
        print(f"   Late Work Frequency: {late_work_percentage}%")
        print(f"   Total Entries: {total_entries}")
        print(f"   Date Range: {data.get('date_range', {}).get('start')} to {data.get('date_range', {}).get('end')}")

    def run_all_tests(self):
        """Run all backend API tests"""
        print("🚀 Starting ArgumentSettler Toggl Dashboard Backend Tests")
        print(f"📡 Testing API at: {self.base_url}")
        print("=" * 60)
        
        # Test all endpoints
        self.test_health_endpoint()
        self.test_workspace_info_endpoint()
        self.test_dashboard_metrics_endpoint()
        
        # Print final results
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All backend tests PASSED!")
            return 0
        else:
            print("⚠️  Some backend tests FAILED!")
            return 1

def main():
    # Use the public endpoint from frontend .env
    tester = TogglDashboardTester("http://localhost:8001")
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())