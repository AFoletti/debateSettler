from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import requests
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import statistics
from dotenv import load_dotenv
import base64

load_dotenv()

app = FastAPI(title="Toggl Track Dashboard API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017/toggl_dashboard")
client = MongoClient(mongo_url)
db = client.get_database()

# Toggl API configuration
TOGGL_API_TOKEN = os.getenv("TOGGL_API_TOKEN")
TOGGL_WORKSPACE = os.getenv("TOGGL_WORKSPACE")
TOGGL_BASE_URL = "https://api.track.toggl.com/api/v9"

# Create auth header for Toggl API
auth_header = base64.b64encode(f"{TOGGL_API_TOKEN}:api_token".encode()).decode()

class TogglService:
    def __init__(self):
        self.headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json"
        }
        self.workspace_id = None
    
    def get_workspace_id(self):
        """Get workspace ID by name"""
        if self.workspace_id:
            return self.workspace_id
            
        response = requests.get(f"{TOGGL_BASE_URL}/workspaces", headers=self.headers)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch workspaces")
        
        workspaces = response.json()
        for workspace in workspaces:
            if workspace["name"] == TOGGL_WORKSPACE:
                self.workspace_id = workspace["id"]
                return self.workspace_id
        
        raise HTTPException(status_code=404, detail=f"Workspace '{TOGGL_WORKSPACE}' not found")
    
    def get_time_entries(self, start_date: str, end_date: str):
        """Fetch time entries from Toggl API"""
        workspace_id = self.get_workspace_id()
        
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        response = requests.get(
            f"{TOGGL_BASE_URL}/me/time_entries",
            headers=self.headers,
            params=params
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch time entries")
        
        return response.json()

class MetricsCalculator:
    def __init__(self, time_entries: List[Dict]):
        self.time_entries = time_entries
    
    def calculate_billable_hours(self) -> float:
        """Calculate total billable hours in the last 30 days"""
        total_seconds = 0
        for entry in self.time_entries:
            if entry.get("billable", False) and entry.get("duration", 0) > 0:
                total_seconds += entry["duration"]
        return total_seconds / 3600  # Convert to hours
    
    def calculate_absent_from_home_hours(self) -> float:
        """Calculate hours absent from home (no HomeOffice tag)"""
        total_seconds = 0
        for entry in self.time_entries:
            if entry.get("duration", 0) > 0:
                tags = entry.get("tags", [])
                if "HomeOffice" not in tags:
                    total_seconds += entry["duration"]
        return total_seconds / 3600
    
    def get_commute_back_home_times(self) -> Dict[str, Any]:
        """Get statistics for commute back home times (last Commuting entry each day)"""
        daily_last_commute = {}
        
        for entry in self.time_entries:
            if entry.get("duration", 0) > 0:
                tags = entry.get("tags", [])
                if "Commuting" in tags:
                    # Parse the start time
                    start_time = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
                    date_key = start_time.date()
                    
                    # Keep only the latest commute entry for each day
                    if date_key not in daily_last_commute or start_time > daily_last_commute[date_key]["datetime"]:
                        daily_last_commute[date_key] = {
                            "datetime": start_time,
                            "end_time": datetime.fromisoformat(entry["stop"].replace("Z", "+00:00")) if entry.get("stop") else None
                        }
        
        # Extract end times (back home times)
        back_home_times = []
        for entry in daily_last_commute.values():
            if entry["end_time"]:
                back_home_times.append(entry["end_time"].time())
        
        if not back_home_times:
            return {"mean": None, "median": None, "earliest": None, "latest": None, "count": 0}
        
        # Convert times to minutes for calculations
        times_in_minutes = [t.hour * 60 + t.minute for t in back_home_times]
        
        mean_minutes = statistics.mean(times_in_minutes)
        median_minutes = statistics.median(times_in_minutes)
        earliest_minutes = min(times_in_minutes)
        latest_minutes = max(times_in_minutes)
        
        # Convert back to time format
        def minutes_to_time(minutes):
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours:02d}:{mins:02d}"
        
        return {
            "mean": minutes_to_time(mean_minutes),
            "median": minutes_to_time(median_minutes),
            "earliest": minutes_to_time(earliest_minutes),
            "latest": minutes_to_time(latest_minutes),
            "count": len(back_home_times)
        }
    
    def get_home_office_end_times(self) -> Dict[str, Any]:
        """Get statistics for HomeOffice end times"""
        daily_last_home_office = {}
        
        for entry in self.time_entries:
            if entry.get("duration", 0) > 0:
                tags = entry.get("tags", [])
                if "HomeOffice" in tags:
                    start_time = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
                    date_key = start_time.date()
                    
                    # Keep only the latest HomeOffice entry for each day
                    if date_key not in daily_last_home_office or start_time > daily_last_home_office[date_key]["datetime"]:
                        daily_last_home_office[date_key] = {
                            "datetime": start_time,
                            "end_time": datetime.fromisoformat(entry["stop"].replace("Z", "+00:00")) if entry.get("stop") else None
                        }
        
        # Extract end times
        end_times = []
        for entry in daily_last_home_office.values():
            if entry["end_time"]:
                end_times.append(entry["end_time"].time())
        
        if not end_times:
            return {"mean": None, "median": None, "earliest": None, "latest": None, "count": 0}
        
        # Convert times to minutes for calculations
        times_in_minutes = [t.hour * 60 + t.minute for t in end_times]
        
        mean_minutes = statistics.mean(times_in_minutes)
        median_minutes = statistics.median(times_in_minutes)
        earliest_minutes = min(times_in_minutes)
        latest_minutes = max(times_in_minutes)
        
        # Convert back to time format
        def minutes_to_time(minutes):
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours:02d}:{mins:02d}"
        
        return {
            "mean": minutes_to_time(mean_minutes),
            "median": minutes_to_time(median_minutes),
            "earliest": minutes_to_time(earliest_minutes),
            "latest": minutes_to_time(latest_minutes),
            "count": len(end_times)
        }
    
    def calculate_late_work_frequency(self) -> Dict[str, Any]:
        """Calculate how often work happened after 20:00"""
        late_work_days = set()
        total_work_days = set()
        
        for entry in self.time_entries:
            if entry.get("duration", 0) > 0:
                start_time = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
                date_key = start_time.date()
                total_work_days.add(date_key)
                
                # Check if work started after 20:00 or ended after 20:00
                end_time = datetime.fromisoformat(entry["stop"].replace("Z", "+00:00")) if entry.get("stop") else start_time
                
                if start_time.hour >= 20 or end_time.hour >= 20:
                    late_work_days.add(date_key)
        
        total_days = len(total_work_days)
        late_days = len(late_work_days)
        percentage = (late_days / total_days * 100) if total_days > 0 else 0
        
        return {
            "late_work_days": late_days,
            "total_work_days": total_days,
            "percentage": round(percentage, 1)
        }

toggl_service = TogglService()

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/dashboard-metrics")
async def get_dashboard_metrics():
    """Get all dashboard metrics for the last 30 days"""
    try:
        # Calculate date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Format dates for Toggl API (ISO format)
        start_date_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_date_str = end_date.strftime("%Y-%m-%dT23:59:59Z")
        
        # Fetch time entries from Toggl
        time_entries = toggl_service.get_time_entries(start_date_str, end_date_str)
        
        # Calculate metrics
        calculator = MetricsCalculator(time_entries)
        
        metrics = {
            "billable_hours": round(calculator.calculate_billable_hours(), 2),
            "absent_from_home_hours": round(calculator.calculate_absent_from_home_hours(), 2),
            "commute_back_home_stats": calculator.get_commute_back_home_times(),
            "home_office_end_stats": calculator.get_home_office_end_times(),
            "late_work_frequency": calculator.calculate_late_work_frequency(),
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "total_entries": len(time_entries)
        }
        
        # Cache results in MongoDB
        db.metrics.replace_one(
            {"type": "dashboard_metrics"},
            {"type": "dashboard_metrics", "data": metrics, "updated_at": datetime.now()},
            upsert=True
        )
        
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")

@app.get("/api/workspace-info")
async def get_workspace_info():
    """Get workspace information"""
    try:
        workspace_id = toggl_service.get_workspace_id()
        return {"workspace_id": workspace_id, "workspace_name": TOGGL_WORKSPACE}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching workspace info: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)