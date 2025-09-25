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
let currentAggregation = 'trend'; // Default to trends view

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

// Helper function to convert HH:MM format to display (no conversion needed)
function timeToDisplay(timeStr) {
    return timeStr || 'N/A';
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
        case 'daily':
            // For daily, get most recent day
            const latestDate = Object.keys(dailyKpis).sort().pop();
            return dailyKpis[latestDate] || null;
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
        case '5WD':
        case '10WD':
        case '30WD':
            return workingDaysKpis?.[currentAggregation] || null;
        default:
            // Fallback to 30WD
            return workingDaysKpis?.['30WD'] || null;
    }
}

// Convert new aggregated format to legacy format for existing UI
function convertToLegacyFormat(aggregatedData) {
    if (!aggregatedData) return null;

    // Handle daily format (different structure)
    if (currentAggregation === 'daily') {
        return {
            billable_hours: aggregatedData.billable_hours?.sum || 0,
            daily_billable_avg: aggregatedData.billable_hours?.sum || 0, // For daily, avg = total
            absent_from_home_hours: aggregatedData.away_from_home_hours?.sum || 0,
            daily_away_avg: aggregatedData.away_from_home_hours?.sum || 0, // For daily, avg = total
            back_home_stats: {
                count: aggregatedData.back_home_times?.time ? 1 : 0,
                mean: timeToDisplay(aggregatedData.back_home_times?.time),
                median: timeToDisplay(aggregatedData.back_home_times?.time),
                earliest: timeToDisplay(aggregatedData.back_home_times?.time),
                latest: timeToDisplay(aggregatedData.back_home_times?.time)
            },
            home_office_end_stats: {
                count: aggregatedData.home_office_end_times?.time ? 1 : 0,
                mean: timeToDisplay(aggregatedData.home_office_end_times?.time),
                median: timeToDisplay(aggregatedData.home_office_end_times?.time),
                earliest: timeToDisplay(aggregatedData.home_office_end_times?.time),
                latest: timeToDisplay(aggregatedData.home_office_end_times?.time)
            },
            late_work_frequency: {
                late_work_days: aggregatedData.late_work_frequency?.count || 0,
                total_work_days: 1,
                percentage: (aggregatedData.late_work_frequency?.count || 0) * 100
            },
            total_entries: aggregatedData.total_entries || 0,
            working_days_analyzed: 1,
            date_range: { start: aggregatedData.date, end: aggregatedData.date }
        };
    }

    // Handle aggregated format (weekly, monthly, working days)
    return {
        billable_hours: aggregatedData.billable_hours?.sum || 0,
        daily_billable_avg: aggregatedData.billable_hours?.mean || (aggregatedData.billable_hours?.sum / aggregatedData.working_days) || 0,
        absent_from_home_hours: aggregatedData.away_from_home_hours?.sum || 
                               (aggregatedData.away_from_home_hours?.mean ? 
                                Math.round(aggregatedData.away_from_home_hours.mean * aggregatedData.working_days * 100) / 100 : 0),
        daily_away_avg: aggregatedData.away_from_home_hours?.mean || 0,
        back_home_stats: {
            count: aggregatedData.back_home_times?.count || 0,
            mean: timeToDisplay(aggregatedData.back_home_times?.mean),
            median: timeToDisplay(aggregatedData.back_home_times?.median),
            earliest: timeToDisplay(aggregatedData.back_home_times?.earliest),
            latest: timeToDisplay(aggregatedData.back_home_times?.latest)
        },
        home_office_end_stats: {
            count: aggregatedData.home_office_end_times?.count || 0,
            mean: timeToDisplay(aggregatedData.home_office_end_times?.mean),
            median: timeToDisplay(aggregatedData.home_office_end_times?.median),
            earliest: timeToDisplay(aggregatedData.home_office_end_times?.earliest),
            latest: timeToDisplay(aggregatedData.home_office_end_times?.latest)
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

// Check if current aggregation is a trends view
function isTrendsView() {
    return currentAggregation === 'trend';
}

// Enhanced function to get aggregated metrics based on current selection
function getAggregatedMetrics() {
    if (!dailyKpis) return null;

    switch(currentAggregation) {
        case 'daily':
            // For daily, get most recent day
            const latestDate = Object.keys(dailyKpis).sort().pop();
            return dailyKpis[latestDate] || null;
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
        case 'trend':
            // For trends, return 30WD as baseline
            return workingDaysKpis?.['30WD'] || null;
        default:
            // Fallback to 30WD
            return workingDaysKpis?.['30WD'] || null;
    }
}
// Calculate differences between working days periods
function calculateWorkingDaysDifferences() {
    if (!workingDaysKpis) return null;
    
    const periods = ['5WD', '10WD', '30WD'];
    const differences = {};
    
    // Helper function to calculate difference between two values
    function calculateDiff(val1, val2, isTime = false) {
        if (!val1 || !val2 || val1 === 'N/A' || val2 === 'N/A') return null;
        
        if (isTime) {
            // Convert HH:MM to minutes for calculation
            const timeToMinutes = (timeStr) => {
                if (!timeStr || timeStr === 'N/A') return null;
                const [hours, minutes] = timeStr.split(':').map(Number);
                return hours * 60 + minutes;
            };
            
            const min1 = timeToMinutes(val1);
            const min2 = timeToMinutes(val2);
            if (min1 === null || min2 === null) return null;
            
            return min1 - min2; // Difference in minutes
        } else {
            return val1 - val2;
        }
    }
    
    // Helper function to format difference display
    function formatDifference(diff, isTime = false, isPercentage = false) {
        if (diff === null || diff === 0) return { text: '—', trend: 'stable' };
        
        const sign = diff > 0 ? '+' : '';
        
        if (isTime) {
            const hours = Math.floor(Math.abs(diff) / 60);
            const minutes = Math.abs(diff) % 60;
            let timeStr = '';
            if (hours > 0) timeStr += `${hours}h `;
            if (minutes > 0) timeStr += `${minutes}m`;
            return {
                text: `${sign}${timeStr}`,
                trend: diff > 0 ? 'up' : 'down'
            };
        } else if (isPercentage) {
            return {
                text: `${sign}${diff.toFixed(1)}%`,
                trend: diff > 0 ? 'up' : 'down'
            };
        } else {
            // For hours, show in minutes if less than 1 hour
            const absValue = Math.abs(diff);
            if (absValue < 1) {
                const minutes = Math.round(absValue * 60);
                return {
                    text: `${sign}${minutes}min`,
                    trend: diff > 0 ? 'up' : 'down'
                };
            } else {
                return {
                    text: `${sign}${diff.toFixed(1)}h`,
                    trend: diff > 0 ? 'up' : 'down'
                };
            }
        }
    }
    
    // Calculate differences for each metric
    const metrics = ['billable_hours', 'away_from_home_hours', 'back_home_times', 'home_office_end_times', 'late_work_frequency'];
    
    metrics.forEach(metric => {
        differences[metric] = {};
        
        if (metric === 'billable_hours') {
            // Daily averages for billable hours
            const val5 = workingDaysKpis['5WD']?.billable_hours?.sum / 5;
            const val10 = workingDaysKpis['10WD']?.billable_hours?.sum / 10;
            const val30 = workingDaysKpis['30WD']?.billable_hours?.sum / 30;
            
            differences[metric]['5_to_10'] = formatDifference(calculateDiff(val5, val10));
            differences[metric]['10_to_30'] = formatDifference(calculateDiff(val10, val30));
            differences[metric]['5_to_30'] = formatDifference(calculateDiff(val5, val30));
            
        } else if (metric === 'away_from_home_hours') {
            // Daily averages for away hours
            const val5 = workingDaysKpis['5WD']?.away_from_home_hours?.mean;
            const val10 = workingDaysKpis['10WD']?.away_from_home_hours?.mean;
            const val30 = workingDaysKpis['30WD']?.away_from_home_hours?.mean;
            
            differences[metric]['5_to_10'] = formatDifference(calculateDiff(val5, val10));
            differences[metric]['10_to_30'] = formatDifference(calculateDiff(val10, val30));
            differences[metric]['5_to_30'] = formatDifference(calculateDiff(val5, val30));
            
        } else if (metric === 'back_home_times' || metric === 'home_office_end_times') {
            // Time-based metrics
            const val5 = workingDaysKpis['5WD']?.[metric]?.mean;
            const val10 = workingDaysKpis['10WD']?.[metric]?.mean;
            const val30 = workingDaysKpis['30WD']?.[metric]?.mean;
            
            differences[metric]['5_to_10'] = formatDifference(calculateDiff(val5, val10, true), true);
            differences[metric]['10_to_30'] = formatDifference(calculateDiff(val10, val30, true), true);
            differences[metric]['5_to_30'] = formatDifference(calculateDiff(val5, val30, true), true);
            
        } else if (metric === 'late_work_frequency') {
            // Percentage-based metric
            const val5 = workingDaysKpis['5WD']?.working_days > 0 ? 
                (workingDaysKpis['5WD']?.late_work_frequency?.count / workingDaysKpis['5WD']?.working_days * 100) : 0;
            const val10 = workingDaysKpis['10WD']?.working_days > 0 ? 
                (workingDaysKpis['10WD']?.late_work_frequency?.count / workingDaysKpis['10WD']?.working_days * 100) : 0;
            const val30 = workingDaysKpis['30WD']?.working_days > 0 ? 
                (workingDaysKpis['30WD']?.late_work_frequency?.count / workingDaysKpis['30WD']?.working_days * 100) : 0;
            
            differences[metric]['5_to_10'] = formatDifference(calculateDiff(val5, val10), false, true);
            differences[metric]['10_to_30'] = formatDifference(calculateDiff(val10, val30), false, true);
            differences[metric]['5_to_30'] = formatDifference(calculateDiff(val5, val30), false, true);
        }
    });
    
    return differences;
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
    
    // Check if we should show trends view or regular view
    if (isTrendsView() && workingDaysKpis) {
        showTrendsView();
    } else {
        showRegularView();
        updateMetrics();
    }
    
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

// Show regular metric cards view
function showRegularView() {
    const metricsGrid = document.querySelector('.metrics-grid');
    if (!metricsGrid) return;
    
    // Remove any existing trends cards
    const existingTrendsCards = metricsGrid.querySelectorAll('.trend-comparison-card');
    existingTrendsCards.forEach(card => card.remove());
    
    // Show regular metric cards
    const regularCards = metricsGrid.querySelectorAll('.metric-card:not(.trend-comparison-card)');
    regularCards.forEach(card => card.style.display = 'block');
}

// Show trends comparison view for working days
function showTrendsView() {
    const metricsGrid = document.querySelector('.metrics-grid');
    if (!metricsGrid || !workingDaysKpis) return;
    
    // Hide regular metric cards
    const regularCards = metricsGrid.querySelectorAll('.metric-card:not(.trend-comparison-card)');
    regularCards.forEach(card => card.style.display = 'none');
    
    // Remove existing trends cards
    const existingTrendsCards = metricsGrid.querySelectorAll('.trend-comparison-card');
    existingTrendsCards.forEach(card => card.remove());
    
    // Calculate differences
    const differences = calculateWorkingDaysDifferences();
    
    // Create trend comparison cards
    createTrendCard('billable_hours', 'Total Billable Hours', differences);
    createTrendCard('away_from_home_hours', 'Time Away from Home', differences);
    createTrendCard('late_work_frequency', 'Late Work Frequency', differences);
    createTrendCard('back_home_times', 'Back Home Times', differences);
    createTrendCard('home_office_end_times', 'HomeOffice End Times', differences);
}

// Create a single trend comparison card
function createTrendCard(metricKey, title, differences) {
    const metricsGrid = document.querySelector('.metrics-grid');
    if (!metricsGrid) return;
    
    const card = document.createElement('div');
    card.className = 'metric-card trend-comparison-card';
    
    // Get icon for metric
    const icons = {
        'billable_hours': `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>`,
        'away_from_home_hours': `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>`,
        'late_work_frequency': `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>`,
        'back_home_times': `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>`,
        'home_office_end_times': `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>`
    };
    
    // Helper function to format values for display
    function formatValue(data, metricKey) {
        if (!data) return 'N/A';
        
        switch(metricKey) {
            case 'billable_hours':
                return `${Math.round((data.billable_hours?.sum / data.working_days) * 100) / 100}h`;
            case 'away_from_home_hours':
                return `${Math.round((data.away_from_home_hours?.mean || 0) * 100) / 100}h`;
            case 'late_work_frequency':
                const percentage = data.working_days > 0 ? 
                    Math.round((data.late_work_frequency?.count / data.working_days * 100) * 10) / 10 : 0;
                return `${percentage}%`;
            case 'back_home_times':
            case 'home_office_end_times':
                return data[metricKey]?.mean || 'N/A';
            default:
                return 'N/A';
        }
    }
    
    // Helper function to get trend arrow
    function getTrendArrow(trend) {
        switch(trend) {
            case 'up': return '↗️';
            case 'down': return '↘️';
            default: return '→';
        }
    }
    
    // Helper function to get trend class
    function getTrendClass(trend) {
        switch(trend) {
            case 'up': return 'trend-up';
            case 'down': return 'trend-down';
            default: return 'trend-stable';
        }
    }
    
    card.innerHTML = `
        <div class="metric-header">
            <svg class="metric-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                ${icons[metricKey]}
            </svg>
            <h3 class="metric-title">${title}</h3>
        </div>
        <div class="metric-content">
            <div class="trends-comparison">
                <div class="trend-period">
                    <div class="trend-period-header">
                        <span class="trend-period-title">5 Working Days</span>
                        <span class="trend-period-dates">${workingDaysKpis['5WD']?.date_range?.start || 'N/A'} to ${workingDaysKpis['5WD']?.date_range?.end || 'N/A'}</span>
                    </div>
                    <div class="trend-value">${formatValue(workingDaysKpis['5WD'], metricKey)}</div>
                </div>
                
                <div class="trend-arrow-section">
                    <div class="trend-arrow-container">
                        <span class="trend-arrow ${getTrendClass(differences?.[metricKey]?.['5_to_10']?.trend)}">${getTrendArrow(differences?.[metricKey]?.['5_to_10']?.trend)}</span>
                        <span class="trend-diff">${differences?.[metricKey]?.['5_to_10']?.text || '—'}</span>
                    </div>
                </div>
                
                <div class="trend-period">
                    <div class="trend-period-header">
                        <span class="trend-period-title">10 Working Days</span>
                        <span class="trend-period-dates">${workingDaysKpis['10WD']?.date_range?.start || 'N/A'} to ${workingDaysKpis['10WD']?.date_range?.end || 'N/A'}</span>
                    </div>
                    <div class="trend-value">${formatValue(workingDaysKpis['10WD'], metricKey)}</div>
                </div>
                
                <div class="trend-arrow-section">
                    <div class="trend-arrow-container">
                        <span class="trend-arrow ${getTrendClass(differences?.[metricKey]?.['10_to_30']?.trend)}">${getTrendArrow(differences?.[metricKey]?.['10_to_30']?.trend)}</span>
                        <span class="trend-diff">${differences?.[metricKey]?.['10_to_30']?.text || '—'}</span>
                    </div>
                </div>
                
                <div class="trend-period">
                    <div class="trend-period-header">
                        <span class="trend-period-title">30 Working Days</span>
                        <span class="trend-period-dates">${workingDaysKpis['30WD']?.date_range?.start || 'N/A'} to ${workingDaysKpis['30WD']?.date_range?.end || 'N/A'}</span>
                    </div>
                    <div class="trend-value">${formatValue(workingDaysKpis['30WD'], metricKey)}</div>
                </div>
            </div>
            
            ${differences?.[metricKey]?.['5_to_30'] ? `
            <div class="trend-summary">
                <span class="trend-summary-label">5-day vs 30-day:</span>
                <span class="trend-arrow ${getTrendClass(differences[metricKey]['5_to_30'].trend)}">${getTrendArrow(differences[metricKey]['5_to_30'].trend)}</span>
                <span class="trend-diff">${differences[metricKey]['5_to_30'].text}</span>
            </div>
            ` : ''}
        </div>
    `;
    
    metricsGrid.appendChild(card);
}

function updateMetrics() {
    if (!metrics) return;

    // Get aggregation display name
    const aggregationNames = {
        'daily': 'Daily',
        'weekly': 'Weekly', 
        'monthly': 'Monthly',
        '5WD': '5 working days',
        '10WD': '10 working days',
        '30WD': '30 working days'
    };
    
    const aggregationDisplay = aggregationNames[currentAggregation] || currentAggregation;

    // Analytics info
    const analyticsInfo = metrics.working_days_analyzed ? 
        `${metrics.working_days_analyzed} working days analyzed (${aggregationDisplay}): ${metrics.date_range.start} to ${metrics.date_range.end}` :
        'Loading analytics...';
    document.getElementById('analytics-info').textContent = analyticsInfo;

    // Status
    if (rawData?.fetched_at) {
        document.getElementById('last-updated').textContent = `Last updated: ${formatLastUpdated(rawData.fetched_at)}`;
    }
    
    const dataInfo = `Raw data from ${rawData?.date_range?.days || 90} days • Statistics from ${aggregationDisplay} • Enhanced processing`;
    document.getElementById('data-info').textContent = dataInfo;

    // Update metric labels based on aggregation - BE MORE SPECIFIC
    const getAggregationLabel = (aggregation) => {
        switch(aggregation) {
            case 'daily': return 'Most recent day';
            case 'weekly': return 'Current week';  
            case 'monthly': return 'Current month';
            case '5WD': return 'Last 5 working days';
            case '10WD': return 'Last 10 working days';
            case '30WD': return 'Last 30 working days';
            default: return aggregationDisplay;
        }
    };
    
    const metricLabel = getAggregationLabel(currentAggregation);
    
    // Update billable hours metric label
    const billableLabel = document.querySelector('#billable-hours').parentElement.querySelector('.metric-label');
    if (billableLabel) {
        billableLabel.textContent = metricLabel;
    }

    // Billable Hours
    document.getElementById('billable-hours').textContent = `${Math.round((metrics.billable_hours || 0) * 100) / 100}h`;
    document.getElementById('billable-avg').innerHTML = `Daily average: <span>${Math.round((metrics.daily_billable_avg || 0) * 100) / 100}h</span>`;

    // Time Away from Home
    document.getElementById('away-hours').textContent = `${Math.round((metrics.absent_from_home_hours || 0) * 100) / 100}h`;
    document.getElementById('away-avg').innerHTML = `Daily average: <span>${Math.round((metrics.daily_away_avg || 0) * 100) / 100}h</span>`;

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

    // Get aggregation display names for labels
    const getAggregationLabel = (aggregation) => {
        switch(aggregation) {
            case 'daily': return 'Most Recent Day';
            case 'weekly': return 'Current Week'; 
            case 'monthly': return 'Current Month';
            case '5WD': return '5 Working Days';
            case '10WD': return '10 Working Days';
            case '30WD': return '30 Working Days';
            default: return aggregation;
        }
    };

    // Update values
    document.getElementById('total-entries-30').textContent = metrics.total_entries || 0;
    document.getElementById('total-entries-60').textContent = rawData.total_entries || 0;
    document.getElementById('working-days').textContent = metrics.working_days_analyzed || 0;
    
    // Update dynamic labels
    const currentAggregationLabel = getAggregationLabel(currentAggregation);
    const rawDataPeriod = rawData?.date_range?.days || 90;
    
    // Update the summary labels dynamically
    const summaryLabels = document.querySelectorAll('.summary-label');
    if (summaryLabels.length >= 3) {
        summaryLabels[0].textContent = `Time Entries (${currentAggregationLabel})`;
        summaryLabels[1].textContent = `Total Raw Entries (${rawDataPeriod} days)`;
        summaryLabels[2].textContent = 'Working Days Analyzed';
    }
}

function updateFooter() {
    if (!rawData) return;
    
    document.getElementById('workspace-name').textContent = rawData.workspace_name || 'DRE-P';
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
    
    // Aggregation dropdown
    const aggregationDropdown = document.getElementById('aggregation-dropdown');
    aggregationDropdown.addEventListener('change', function() {
        // Get selected aggregation value
        const newAggregation = this.value;
        
        // Update current aggregation
        currentAggregation = newAggregation;
        
        // Reprocess data and update UI
        const aggregatedData = getAggregatedMetrics();
        metrics = convertToLegacyFormat(aggregatedData);
        updateUI();
        
        console.log('📊 Switched to aggregation:', newAggregation);
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
