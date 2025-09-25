/**
 * DebateSettler Dashboard - Enhanced with Multi-Level Aggregations
 * Phase 1: Enhanced data collection with backward compatibility
 */

// Global state
let rawData = null;
let dailyKpis = null;
let weeklyKpis = null;
let monthlyKpis = null;
let workingDaysKpis = null;
let metrics = null;
let loading = true;
let error = null;
let currentAggregation = '30WD'; // Default to 30 working days

// DOM elements
const loadingContainer = document.getElementById('loading-container');
const errorContainer = document.getElementById('error-container');
const mainDashboard = document.getElementById('main-dashboard');
const retryButton = document.getElementById('retry-button');
const refreshButton = document.getElementById('refresh-button');
const githubActionsLink = document.getElementById('github-actions-link');

// Helper function to parse datetime with timezone handling
function parseDateTime(dateTimeStr) {
    if (!dateTimeStr) return null;
    return new Date(dateTimeStr.replace("Z", "+00:00"));
}

// Helper function to convert decimal hours to HH:MM format
function hoursToTime(decimalHours) {
    if (!decimalHours || decimalHours === 0) return 'N/A';
    const hours = Math.floor(decimalHours);
    const mins = Math.round((decimalHours - hours) * 60);
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

// Helper function to convert minutes to HH:MM format (legacy support)
function minutesToTime(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

// Enhanced function to get aggregated metrics based on current selection
function getAggregatedMetrics() {
    if (!dailyKpis) return null;

    switch(currentAggregation) {
        case '5WD':
        case '10WD':
        case '30WD':
            return workingDaysKpis?.[currentAggregation] || null;
        case 'weekly':
            // Get most recent week
            if (weeklyKpis) {
                const latestWeek = Object.keys(weeklyKpis).sort().pop();
                return weeklyKpis[latestWeek];
            }
            return null;
        case 'monthly':
            // Get most recent month
            if (monthlyKpis) {
                const latestMonth = Object.keys(monthlyKpis).sort().pop();
                return monthlyKpis[latestMonth];
            }
            return null;
        default:
            // Fallback to 30WD
            return workingDaysKpis?.['30WD'] || null;
    }
}

// Convert new aggregated format to legacy format for existing UI
function convertToLegacyFormat(aggregatedData) {
    if (!aggregatedData) return null;

    return {
        billable_hours: aggregatedData.billable_hours?.sum || 0,
        daily_billable_avg: aggregatedData.billable_hours?.mean || (aggregatedData.billable_hours?.sum / aggregatedData.working_days) || 0,
        absent_from_home_hours: aggregatedData.away_from_home_hours?.sum || 0,
        daily_away_avg: aggregatedData.away_from_home_hours?.mean || 0,
        back_home_stats: {
            count: aggregatedData.back_home_times ? 
                (Object.keys(aggregatedData.back_home_times).length > 0 ? aggregatedData.working_days : 0) : 0,
            mean: hoursToTime(aggregatedData.back_home_times?.mean),
            median: hoursToTime(aggregatedData.back_home_times?.median),
            earliest: hoursToTime(aggregatedData.back_home_times?.earliest),
            latest: hoursToTime(aggregatedData.back_home_times?.latest)
        },
        home_office_end_stats: {
            count: aggregatedData.home_office_end_times ? 
                (Object.keys(aggregatedData.home_office_end_times).length > 0 ? aggregatedData.working_days : 0) : 0,
            mean: hoursToTime(aggregatedData.home_office_end_times?.mean),
            median: hoursToTime(aggregatedData.home_office_end_times?.median),
            earliest: hoursToTime(aggregatedData.home_office_end_times?.earliest),
            latest: hoursToTime(aggregatedData.home_office_end_times?.latest)
        },
        late_work_frequency: {
            late_work_days: aggregatedData.late_work_frequency?.count || 0,
            total_work_days: aggregatedData.working_days || 0,
            percentage: aggregatedData.working_days > 0 ? 
                Math.round((aggregatedData.late_work_frequency?.count || 0) / aggregatedData.working_days * 100 * 10) / 10 : 0
        },
        total_entries: aggregatedData.total_entries || 0,
        working_days_analyzed: aggregatedData.working_days || 0,
        date_range: aggregatedData.date_range || { start: 'N/A', end: 'N/A' }
    };
}

// Load all aggregated data files
async function loadAggregatedData() {
    try {
        console.log('📊 Loading aggregated data files...');
        
        // Try to load new aggregated data files (using final filenames)
        const responses = await Promise.allSettled([
            fetch('./data/daily_kpis.json'),
            fetch('./data/weekly_aggregations.json'),  
            fetch('./data/monthly_aggregations.json'),
            fetch('./data/working_days_aggregations.json') // Using final filename
        ]);

        // Process daily KPIs
        if (responses[0].status === 'fulfilled' && responses[0].value.ok) {
            dailyKpis = await responses[0].value.json();
            console.log('✅ Loaded daily KPIs:', Object.keys(dailyKpis).length, 'days');
        } else {
            console.log('⚠️ Daily KPIs not found, will use raw data processing');
        }

        // Process weekly aggregations
        if (responses[1].status === 'fulfilled' && responses[1].value.ok) {
            weeklyKpis = await responses[1].value.json();
            console.log('✅ Loaded weekly aggregations:', Object.keys(weeklyKpis).length, 'weeks');
        } else {
            console.log('⚠️ Weekly aggregations not found');
        }

        // Process monthly aggregations  
        if (responses[2].status === 'fulfilled' && responses[2].value.ok) {
            monthlyKpis = await responses[2].value.json();
            console.log('✅ Loaded monthly aggregations:', Object.keys(monthlyKpis).length, 'months');
        } else {
            console.log('⚠️ Monthly aggregations not found');
        }

        // Process working days aggregations
        if (responses[3].status === 'fulfilled' && responses[3].value.ok) {
            workingDaysKpis = await responses[3].value.json();
            console.log('✅ Loaded working days aggregations:', Object.keys(workingDaysKpis).length, 'periods');
        } else {
            console.log('⚠️ Working days aggregations not found');
        }

        return true;
    } catch (err) {
        console.log('⚠️ Could not load aggregated data:', err.message);
        return false;
    }
}

// Legacy raw data processing (fallback)
function processRawDataLegacy(rawData) {
    console.log('📊 Using legacy raw data processing...');
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
    
    // Helper function to calculate statistics (mean, median, min, max)
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

        // Calculate HomeOffice end times (similar logic as existing)
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
            working_days_analyzed: workingDays.length,
            date_range: {
                start: oldestWorkingDay30 || 'N/A',
                end: last30WorkingDays[0] || 'N/A'
            }
        };
    }

    // Calculate metrics for 30 days (main display)
    const metrics30Days = calculateMetricsForDays(last30WorkingDays);
    
    return metrics30Days;
}

// Enhanced data processing that tries aggregated data first, falls back to legacy
function processData() {
    if (dailyKpis && workingDaysKpis) {
        console.log('📊 Using enhanced aggregated data...');
        const aggregatedData = getAggregatedMetrics();
        return convertToLegacyFormat(aggregatedData);
    } else if (rawData) {
        console.log('📊 Falling back to legacy raw data processing...');
        return processRawDataLegacy(rawData);
    }
    
    return null;
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
        `${metrics.working_days_analyzed} working days analyzed (${currentAggregation}): ${metrics.date_range.start} to ${metrics.date_range.end}` :
        'Loading analytics...';
    document.getElementById('analytics-info').textContent = analyticsInfo;

    // Status
    if (rawData?.fetched_at) {
        document.getElementById('last-updated').textContent = `Last updated: ${formatLastUpdated(rawData.fetched_at)}`;
    }
    
    const dataInfo = `Raw data from ${rawData?.date_range?.days || 180} days • Statistics from ${currentAggregation} • Enhanced processing`;
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

function updateSummary() {
    if (!metrics || !rawData) return;

    document.getElementById('total-entries-30').textContent = metrics.total_entries || 0;
    document.getElementById('total-entries-60').textContent = rawData.total_entries || 0;
    document.getElementById('working-days').textContent = metrics.working_days_analyzed || 0;
}

function updateFooter() {
    if (!rawData) return;
    
    document.getElementById('workspace-name').textContent = rawData.workspace_name || 'DRE-P';
    
    // Try to set up GitHub Actions link based on the current URL
    if (githubActionsLink && typeof window !== 'undefined') {
        const hostname = window.location.hostname;
        
        // Check if we're on GitHub Pages
        if (hostname.includes('github.io')) {
            // Extract username and repo from GitHub Pages URL
            // Format: username.github.io/repo-name
            const pathParts = window.location.pathname.split('/').filter(p => p);
            const username = hostname.split('.')[0];
            const repoName = pathParts[0] || 'argumentSettler';
            
            const actionsUrl = `https://github.com/${username}/${repoName}/actions/workflows/fetch-toggl-data-enhanced.yml`;
            githubActionsLink.href = actionsUrl;
            githubActionsLink.style.display = 'inline-flex';
            
            console.log(`🔗 GitHub Actions link set to: ${actionsUrl}`);
        } else {
            // For local development or other hosting, hide the button
            githubActionsLink.style.display = 'none';
        }
    }
}

// Fetch data from JSON files
async function fetchData() {
    try {
        loading = true;
        error = null;
        updateUI();
        
        // First, always load raw data
        console.log('🔄 Fetching raw data...');
        const rawResponse = await fetch('./data/raw_data.json');
        
        if (!rawResponse.ok) {
            throw new Error(`Failed to load raw data: ${rawResponse.status}`);
        }
        
        rawData = await rawResponse.json();
        console.log(`✅ Loaded raw data: ${rawData.total_entries} entries from ${rawData.date_range.start} to ${rawData.date_range.end}`);
        
        // Try to load aggregated data
        await loadAggregatedData();
        
        // Process data using best available method
        const calculatedMetrics = processData();
        metrics = calculatedMetrics;
        
        loading = false;
        error = null;
        
        console.log('🎉 Data processing completed successfully!');
        console.log('📊 Using aggregation:', currentAggregation);
        
    } catch (err) {
        loading = false;
        error = `Failed to load dashboard data: ${err.message}`;
        console.error('❌ Error fetching data:', err);
    } finally {
        updateUI();
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DebateSettler Enhanced Dashboard starting...');
    
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

// Make enhanced functions available globally for debugging
window.DebateSettlerEnhanced = {
    fetchData,
    rawData: () => rawData,
    dailyKpis: () => dailyKpis,
    weeklyKpis: () => weeklyKpis,
    monthlyKpis: () => monthlyKpis,
    workingDaysKpis: () => workingDaysKpis,
    metrics: () => metrics,
    currentAggregation: () => currentAggregation,
    setAggregation: (agg) => {
        currentAggregation = agg;
        metrics = processData();
        updateUI();
        console.log('📊 Switched to aggregation:', agg);
    }
};