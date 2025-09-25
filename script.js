/**
 * ArgumentSettler Dashboard - Static JavaScript Version
 * Converts the React application to vanilla JavaScript
 */

// Global state
let rawData = null;
let metrics = null;
let loading = true;
let error = null;

// DOM elements
const loadingContainer = document.getElementById('loading-container');
const errorContainer = document.getElementById('error-container');
const mainDashboard = document.getElementById('main-dashboard');
const retryButton = document.getElementById('retry-button');

// Helper function to parse datetime with timezone handling
function parseDateTime(dateTimeStr) {
    if (!dateTimeStr) return null;
    return new Date(dateTimeStr.replace("Z", "+00:00"));
}

// Helper function to convert minutes to HH:MM format
function minutesToTime(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

// Calculate statistics (mean, median, min, max)
function calculateStats(values) {
    if (values.length === 0) {
        return { mean: null, median: null, earliest: null, latest: null, count: 0 };
    }

    const sorted = [...values].sort((a, b) => a - b);
    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    const median = sorted.length % 2 === 0 
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)];

    return {
        mean: minutesToTime(mean),
        median: minutesToTime(median),
        earliest: minutesToTime(Math.min(...values)),
        latest: minutesToTime(Math.max(...values)),
        count: values.length
    };
}

// Process raw data and calculate all metrics
function processRawData(rawData) {
    const entries = rawData.raw_entries || [];
    
    // Get all unique dates that have entries, sorted by date (most recent first)
    const datesWithEntries = [...new Set(
        entries
            .filter(entry => entry.duration > 0)
            .map(entry => {
                const startTime = parseDateTime(entry.start);
                return startTime ? startTime.toISOString().split('T')[0] : null;
            })
            .filter(date => date !== null)
    )].sort().reverse(); // Most recent first
    
    // Take the last 30 and 7 working days
    const last30WorkingDays = datesWithEntries.slice(0, 30);
    const last7WorkingDays = datesWithEntries.slice(0, 7);
    
    const oldestWorkingDay30 = last30WorkingDays[last30WorkingDays.length - 1];
    const oldestWorkingDay7 = last7WorkingDays[last7WorkingDays.length - 1];
    
    console.log(`📊 Using last 30 working days: ${last30WorkingDays.length} days from ${oldestWorkingDay30} to ${last30WorkingDays[0]}`);
    console.log(`📊 Using last 7 working days: ${last7WorkingDays.length} days from ${oldestWorkingDay7} to ${last7WorkingDays[0]}`);
    
    // Helper function to calculate metrics for a specific set of working days
    function calculateMetricsForDays(workingDays) {
        // Filter entries to only include those from the specified working days
        const filteredEntries = entries.filter(entry => {
            const startTime = parseDateTime(entry.start);
            if (!startTime || entry.duration <= 0) return false;
            
            const date = startTime.toISOString().split('T')[0];
            return workingDays.includes(date);
        });

        // Calculate billable hours
        let totalBillableSeconds = 0;
        const dailyBillableHours = {};
        
        filteredEntries.forEach(entry => {
            if (entry.billable && entry.duration > 0) {
                totalBillableSeconds += entry.duration;
                
                const date = parseDateTime(entry.start).toISOString().split('T')[0];
                if (!dailyBillableHours[date]) dailyBillableHours[date] = 0;
                dailyBillableHours[date] += entry.duration / 3600;
            }
        });
        
        const billableHours = totalBillableSeconds / 3600;
        const billableDays = Object.keys(dailyBillableHours).length;
        const dailyBillableAvg = billableDays > 0 ? billableHours / billableDays : 0;

        // Calculate time away from home
        let totalAwaySeconds = 0;
        const dailyAwayHours = {};
        
        filteredEntries.forEach(entry => {
            const tags = entry.tags || [];
            if (!tags.includes("HomeOffice") && entry.duration > 0) {
                totalAwaySeconds += entry.duration;
                
                const date = parseDateTime(entry.start).toISOString().split('T')[0];
                if (!dailyAwayHours[date]) dailyAwayHours[date] = 0;
                dailyAwayHours[date] += entry.duration / 3600;
            }
        });
        
        const awayFromHomeHours = totalAwaySeconds / 3600;
        const awayDays = Object.keys(dailyAwayHours).length;
        const dailyAwayAvg = awayDays > 0 ? awayFromHomeHours / awayDays : 0;

        // Calculate back home times (only days with commuting)
        const dailyLastEntries = {};
        
        filteredEntries.forEach(entry => {
            const startTime = parseDateTime(entry.start);
            const endTime = parseDateTime(entry.stop);
            if (!startTime || !endTime) return;
            
            const date = startTime.toISOString().split('T')[0];
            
            if (!dailyLastEntries[date]) {
                dailyLastEntries[date] = {
                    entries: [],
                    lastCommutingTime: null,
                    lastOverallEntry: null
                };
            }
            
            // Track all entries for this date
            dailyLastEntries[date].entries.push({
                startTime,
                endTime,
                tags: entry.tags || [],
                entry
            });
        });
        
        // Process each day to find the correct "back home" time
        Object.keys(dailyLastEntries).forEach(date => {
            const dayData = dailyLastEntries[date];
            
            // Sort entries by start time
            dayData.entries.sort((a, b) => a.startTime - b.startTime);
            
            // Find the last Commuting entry
            let lastCommutingEntry = null;
            dayData.entries.forEach(entryData => {
                if (entryData.tags.includes("Commuting")) {
                    lastCommutingEntry = entryData;
                }
            });
            
            // IMPORTANT: Only days with commuting should have "back home" times
            if (lastCommutingEntry) {
                dayData.lastOverallEntry = lastCommutingEntry;
            } else {
                dayData.lastOverallEntry = null;
            }
        });
        
        const backHomeTimes = Object.values(dailyLastEntries)
            .filter(dayData => dayData.lastOverallEntry)
            .map(dayData => dayData.lastOverallEntry.endTime.getHours() * 60 + dayData.lastOverallEntry.endTime.getMinutes());
        
        const backHomeStats = calculateStats(backHomeTimes);

        // Calculate HomeOffice end times
        const dailyHomeOfficeEntries = {};
        
        filteredEntries.forEach(entry => {
            const tags = entry.tags || [];
            const startTime = parseDateTime(entry.start);
            const endTime = parseDateTime(entry.stop);
            if (!startTime || !endTime) return;
            
            const date = startTime.toISOString().split('T')[0];
            
            if (!dailyHomeOfficeEntries[date]) {
                dailyHomeOfficeEntries[date] = {
                    homeOfficeEntries: [],
                    allEntries: []
                };
            }
            
            // Track all entries for this date
            dailyHomeOfficeEntries[date].allEntries.push({
                startTime,
                endTime,
                tags,
                isHomeOffice: tags.includes("HomeOffice"),
                entry
            });
            
            // Track HomeOffice entries
            if (tags.includes("HomeOffice")) {
                dailyHomeOfficeEntries[date].homeOfficeEntries.push({
                    startTime,
                    endTime,
                    tags,
                    entry
                });
            }
        });
        
        // Process each day to determine if it's a valid "HomeOffice day"
        const validHomeOfficeDays = {};
        
        Object.keys(dailyHomeOfficeEntries).forEach(date => {
            const dayData = dailyHomeOfficeEntries[date];
            
            // Sort all entries by start time
            dayData.allEntries.sort((a, b) => a.startTime - b.startTime);
            dayData.homeOfficeEntries.sort((a, b) => a.startTime - b.startTime);
            
            if (dayData.homeOfficeEntries.length === 0) return;
            
            // Find the last entry of the day (any type)
            const lastEntryOfDay = dayData.allEntries[dayData.allEntries.length - 1];
            
            // Find the last HomeOffice entry
            const lastHomeOfficeEntry = dayData.homeOfficeEntries[dayData.homeOfficeEntries.length - 1];
            
            // Find the last Commuting entry
            const commutingEntries = dayData.allEntries.filter(e => e.tags.includes("Commuting"));
            const lastCommutingEntry = commutingEntries.length > 0 ? commutingEntries[commutingEntries.length - 1] : null;
            
            // Rule 1: If there's HomeOffice AFTER the last Commuting entry, ignore it for end-of-day calculations
            if (lastCommutingEntry && lastHomeOfficeEntry.startTime > lastCommutingEntry.endTime) {
                return;
            }
            
            // Rule 2: Check if this is a "mixed day" (HomeOffice followed by non-HomeOffice)
            const entriesAfterLastHomeOffice = dayData.allEntries.filter(e => 
                e.startTime > lastHomeOfficeEntry.endTime && !e.isHomeOffice
            );
            
            if (entriesAfterLastHomeOffice.length > 0) {
                return;
            }
            
            // Rule 3: Only count if the last entry of the day is HomeOffice
            if (lastEntryOfDay.isHomeOffice) {
                validHomeOfficeDays[date] = lastHomeOfficeEntry;
            }
        });
        
        const homeOfficeEndTimes = Object.values(validHomeOfficeDays)
            .map(entryData => entryData.endTime.getHours() * 60 + entryData.endTime.getMinutes());
        
        const homeOfficeStats = calculateStats(homeOfficeEndTimes);

        // Calculate late work frequency
        const workDays = new Set();
        const lateWorkDays = new Set();
        
        filteredEntries.forEach(entry => {
            const startTime = parseDateTime(entry.start);
            const endTime = parseDateTime(entry.stop);
            if (!startTime) return;
            
            const date = startTime.toISOString().split('T')[0];
            workDays.add(date);
            
            // Check if work started after 20:00 or ended after 20:00
            if ((startTime.getHours() >= 20) || (endTime && endTime.getHours() >= 20)) {
                lateWorkDays.add(date);
            }
        });
        
        const lateWorkPercentage = workDays.size > 0 ? (lateWorkDays.size / workDays.size * 100) : 0;

        return {
            billable_hours: Math.round(billableHours * 100) / 100,
            daily_billable_avg: Math.round(dailyBillableAvg * 100) / 100,
            absent_from_home_hours: Math.round(awayFromHomeHours * 100) / 100,
            daily_away_avg: Math.round(dailyAwayAvg * 100) / 100,
            back_home_stats: backHomeStats,
            home_office_end_stats: homeOfficeStats,
            late_work_frequency: {
                late_work_days: lateWorkDays.size,
                total_work_days: workDays.size,
                percentage: Math.round(lateWorkPercentage * 10) / 10
            },
            total_entries: filteredEntries.length,
            working_days_analyzed: workingDays.length
        };
    }

    // Calculate metrics for both 30 and 7 days
    const metrics30Days = calculateMetricsForDays(last30WorkingDays);
    const metrics7Days = calculateMetricsForDays(last7WorkingDays);
    
    // Calculate trends
    function calculateTrend(recent, baseline, thresholdMinutes = 15) {
        if (!recent || !baseline || recent === 0 || baseline === 0) {
            return { trend: 'stable', difference: 0, percentage: 0 };
        }
        
        // For time-based comparisons (in minutes)
        if (typeof recent === 'string' && recent.includes(':')) {
            const recentMinutes = parseTimeToMinutes(recent);
            const baselineMinutes = parseTimeToMinutes(baseline);
            const diffMinutes = recentMinutes - baselineMinutes;
            
            if (Math.abs(diffMinutes) <= thresholdMinutes) return { trend: 'stable', difference: diffMinutes, percentage: 0 };
            return { trend: diffMinutes > 0 ? 'up' : 'down', difference: diffMinutes, percentage: 0 };
        }
        
        // For numeric comparisons (hours)
        const diffHours = recent - baseline;
        const diffMinutes = diffHours * 60;
        
        if (Math.abs(diffMinutes) <= thresholdMinutes) return { trend: 'stable', difference: diffHours, percentage: 0 };
        
        const percentage = ((recent - baseline) / baseline) * 100;
        return { trend: diffHours > 0 ? 'up' : 'down', difference: diffHours, percentage: Math.round(percentage * 10) / 10 };
    }
    
    function parseTimeToMinutes(timeStr) {
        if (!timeStr || timeStr === 'N/A') return 0;
        const [hours, minutes] = timeStr.split(':').map(Number);
        return hours * 60 + minutes;
    }

    const trends = {
        billable_hours: calculateTrend(metrics7Days.daily_billable_avg, metrics30Days.daily_billable_avg),
        back_home_time: calculateTrend(metrics7Days.back_home_stats.mean, metrics30Days.back_home_stats.mean)
    };

    // Debug logging
    console.log(`🏠 Valid HomeOffice days (30d): ${metrics30Days.home_office_end_stats.count}`);
    console.log(`🏠 Valid HomeOffice days (7d): ${metrics7Days.home_office_end_stats.count}`);
    console.log(`🚪 Back home times (30d): ${metrics30Days.back_home_stats.count} days (only days with commuting)`);
    console.log(`🚪 Back home times (7d): ${metrics7Days.back_home_stats.count} days (only days with commuting)`);
    console.log(`📈 Trends - Billable: ${trends.billable_hours.trend}, Back home: ${trends.back_home_time.trend}`);

    return {
        // 30-day metrics (main display)
        ...metrics30Days,
        date_range: {
            start: oldestWorkingDay30 || 'N/A',
            end: last30WorkingDays[0] || 'N/A'
        },
        
        // 7-day metrics (for trends)
        last_7_days: metrics7Days,
        
        // Trend analysis
        trends: trends
    };
}

// Format last updated timestamp
function formatLastUpdated(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short'
        });
    } catch {
        return 'Unknown';
    }
}

// Update UI with calculated metrics
function updateUI() {
    if (loading) {
        showLoading();
        return;
    }

    if (error) {
        showError(error);
        return;
    }

    showDashboard();
    
    // Update all UI elements
    updateMetrics();
    updateTrends();
    updateSummary();
    updateFooter();
}

function showLoading() {
    loadingContainer.style.display = 'flex';
    errorContainer.style.display = 'none';
    mainDashboard.style.display = 'none';
}

function showError(errorMessage) {
    loadingContainer.style.display = 'none';
    errorContainer.style.display = 'flex';
    mainDashboard.style.display = 'none';
    
    document.getElementById('error-message').textContent = errorMessage;
}

function showDashboard() {
    loadingContainer.style.display = 'none';
    errorContainer.style.display = 'none';
    mainDashboard.style.display = 'block';
}

function updateMetrics() {
    if (!metrics) return;

    // Analytics info
    const analyticsInfo = metrics.working_days_analyzed ? 
        `${metrics.working_days_analyzed} working days analyzed: ${metrics.date_range.start} to ${metrics.date_range.end}` :
        'Loading analytics...';
    document.getElementById('analytics-info').textContent = analyticsInfo;

    // Status
    if (rawData?.fetched_at) {
        document.getElementById('last-updated').textContent = `Last updated: ${formatLastUpdated(rawData.fetched_at)}`;
    }
    
    const dataInfo = `Raw data from ${rawData?.date_range?.days || 60} days • Statistics from last ${metrics.working_days_analyzed || 30} working days • Client-side calculations`;
    document.getElementById('data-info').textContent = dataInfo;

    // Billable Hours
    document.getElementById('billable-hours').textContent = `${metrics.billable_hours || 0}h`;
    document.getElementById('billable-avg').innerHTML = `Daily average: <span>${metrics.daily_billable_avg || 0}h</span>`;

    // Time Away from Home
    document.getElementById('away-hours').textContent = `${metrics.absent_from_home_hours || 0}h`;
    document.getElementById('away-avg').innerHTML = `Daily average: <span>${metrics.daily_away_avg || 0}h</span>`;

    // Late Work Frequency
    document.getElementById('late-work-percentage').textContent = `${metrics.late_work_frequency?.percentage || 0}%`;
    document.getElementById('late-work-subtitle').textContent = 
        `${metrics.late_work_frequency?.late_work_days || 0} out of ${metrics.late_work_frequency?.total_work_days || 0} work days after 20:00`;

    // Back Home Times
    document.getElementById('back-home-count').textContent = metrics.back_home_stats?.count || 0;
    document.getElementById('back-home-mean').textContent = metrics.back_home_stats?.mean || 'N/A';
    document.getElementById('back-home-median').textContent = metrics.back_home_stats?.median || 'N/A';
    document.getElementById('back-home-earliest').textContent = metrics.back_home_stats?.earliest || 'N/A';
    document.getElementById('back-home-latest').textContent = metrics.back_home_stats?.latest || 'N/A';

    // HomeOffice End Times
    document.getElementById('home-office-count').textContent = metrics.home_office_end_stats?.count || 0;
    document.getElementById('home-office-mean').textContent = metrics.home_office_end_stats?.mean || 'N/A';
    document.getElementById('home-office-median').textContent = metrics.home_office_end_stats?.median || 'N/A';
    document.getElementById('home-office-earliest').textContent = metrics.home_office_end_stats?.earliest || 'N/A';
    document.getElementById('home-office-latest').textContent = metrics.home_office_end_stats?.latest || 'N/A';
}

function updateTrends() {
    if (!metrics?.trends) return;

    const trendsCard = document.getElementById('trends-card');
    trendsCard.style.display = 'block';

    const billableTrend = metrics.trends.billable_hours;
    const homeTrend = metrics.trends.back_home_time;

    // Update billable hours trend
    const billableIcon = document.getElementById('billable-trend-icon');
    const billableText = document.getElementById('billable-trend-text');
    const billableDiff = document.getElementById('billable-trend-diff');

    switch(billableTrend.trend) {
        case 'up':
            billableIcon.textContent = '↗️';
            billableIcon.className = 'trend-icon trend-up';
            billableText.textContent = 'Longer';
            break;
        case 'down':
            billableIcon.textContent = '↘️';
            billableIcon.className = 'trend-icon trend-down';
            billableText.textContent = 'Shorter';
            break;
        default:
            billableIcon.textContent = '→';
            billableIcon.className = 'trend-icon trend-stable';
            billableText.textContent = 'Same';
            break;
    }

    if (Math.abs(billableTrend.difference) > 0) {
        billableDiff.textContent = `${billableTrend.difference > 0 ? '+' : ''}${(billableTrend.difference * 60).toFixed(0)}min`;
        billableDiff.style.display = 'block';
    } else {
        billableDiff.style.display = 'none';
    }

    // Update back home trend
    const homeIcon = document.getElementById('home-trend-icon');
    const homeText = document.getElementById('home-trend-text');  
    const homeDiff = document.getElementById('home-trend-diff');

    switch(homeTrend.trend) {
        case 'up':
            homeIcon.textContent = '↗️';
            homeIcon.className = 'trend-icon trend-up';
            homeText.textContent = 'Later';
            break;
        case 'down':
            homeIcon.textContent = '↘️';
            homeIcon.className = 'trend-icon trend-down';
            homeText.textContent = 'Earlier';
            break;
        default:
            homeIcon.textContent = '→';
            homeIcon.className = 'trend-icon trend-stable';
            homeText.textContent = 'Same';
            break;
    }

    if (Math.abs(homeTrend.difference) > 0) {
        homeDiff.textContent = `${homeTrend.difference > 0 ? '+' : ''}${homeTrend.difference.toFixed(0)}min`;
        homeDiff.style.display = 'block';
    } else {
        homeDiff.style.display = 'none';
    }
}

function updateSummary() {
    if (!metrics || !rawData) return;

    document.getElementById('total-entries-30').textContent = metrics.total_entries || 0;
    document.getElementById('total-entries-60').textContent = rawData.total_entries || 0;
    document.getElementById('working-days').textContent = metrics.working_days_analyzed || 0;
}

function updateFooter() {
    if (!rawData) return;
    
    document.getElementById('workspace-name').textContent = rawData.workspace_name || 'DRE-P';
}

// Fetch data from JSON file
async function fetchData() {
    try {
        loading = true;
        error = null;
        updateUI();
        
        // Fetch raw data from GitHub Pages with proper path handling
        const dataUrl = './data/raw_data.json';
        console.log('Fetching data from:', dataUrl);
        const response = await fetch(dataUrl);
        
        if (!response.ok) {
            throw new Error(`Failed to load data: ${response.status}`);
        }
        
        const data = await response.json();
        rawData = data;
        
        // Process raw data to calculate metrics
        const calculatedMetrics = processRawData(data);
        metrics = calculatedMetrics;
        
        loading = false;
        error = null;
        
    } catch (err) {
        loading = false;
        error = `Failed to load dashboard data: ${err.message}`;
        console.error('Error fetching data:', err);
    } finally {
        updateUI();
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initial data fetch
    fetchData();
    
    // Retry button
    retryButton.addEventListener('click', fetchData);
    
    // Refresh button  
    refreshButton.addEventListener('click', async function() {
        refreshButton.disabled = true;
        refreshButton.textContent = 'Refreshing...';
        
        try {
            await fetchData();
            console.log('🔄 Data refreshed successfully');
        } catch (error) {
            console.error('❌ Error refreshing data:', error);
        } finally {
            refreshButton.disabled = false;
            refreshButton.innerHTML = `
                <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                </svg>
                Refresh Data
            `;
        }
    });
});

// Make functions available globally for debugging
window.ArgumentSettler = {
    fetchData,
    rawData: () => rawData,
    metrics: () => metrics,
    processRawData
};