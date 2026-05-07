(function (global, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    global.DebateSettlerMetrics = factory();
  }
})(typeof window !== "undefined" ? window : this, function () {
  // ---------------------------------------------------------------------------
  // Small helpers
  // ---------------------------------------------------------------------------

  function parseDateTime(dateTimeStr) {
    if (!dateTimeStr) return null;
    return new Date(dateTimeStr.replace("Z", "+00:00"));
  }

  function minutesToTime(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return `${hours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}`;
  }

  function calculateStats(values) {
    if (values.length === 0) {
      return { mean: null, median: null, earliest: null, latest: null, count: 0 };
    }
    const sorted = [...values].sort((a, b) => a - b);
    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    const median =
      sorted.length % 2 === 0
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)];
    return {
      mean: minutesToTime(mean),
      median: minutesToTime(median),
      earliest: minutesToTime(Math.min(...values)),
      latest: minutesToTime(Math.max(...values)),
      count: values.length,
    };
  }

  function parseTimeToMinutes(timeStr) {
    if (!timeStr || timeStr === "N/A") return 0;
    const [hours, minutes] = timeStr.split(":").map(Number);
    return hours * 60 + minutes;
  }

  function calculateTrend(recent, baseline, thresholdMinutes = 15) {
    if (!recent || !baseline || recent === 0 || baseline === 0) {
      return { trend: "stable", difference: 0, percentage: 0 };
    }
    if (typeof recent === "string" && recent.includes(":")) {
      const recentMinutes = parseTimeToMinutes(recent);
      const baselineMinutes = parseTimeToMinutes(baseline);
      const diffMinutes = recentMinutes - baselineMinutes;
      if (Math.abs(diffMinutes) <= thresholdMinutes)
        return { trend: "stable", difference: diffMinutes, percentage: 0 };
      return { trend: diffMinutes > 0 ? "up" : "down", difference: diffMinutes, percentage: 0 };
    }
    const diffHours = recent - baseline;
    const diffMinutes = diffHours * 60;
    if (Math.abs(diffMinutes) <= thresholdMinutes)
      return { trend: "stable", difference: diffHours, percentage: 0 };
    const percentage = ((recent - baseline) / baseline) * 100;
    return {
      trend: diffHours > 0 ? "up" : "down",
      difference: diffHours,
      percentage: Math.round(percentage * 10) / 10,
    };
  }

  // ---------------------------------------------------------------------------
  // Working days
  // ---------------------------------------------------------------------------

  // Returns the unique list of YYYY-MM-DD dates that have at least one entry
  // with duration > 0, sorted ASCending.
  function computeAllWorkingDaysAsc(entries) {
    return [
      ...new Set(
        entries
          .filter((e) => e.duration > 0)
          .map((e) => {
            const t = parseDateTime(e.start);
            return t ? t.toISOString().split("T")[0] : null;
          })
          .filter((d) => d !== null),
      ),
    ].sort();
  }

  // Pick the working days that fall in the requested timeframe spec.
  // Spec shapes:
  //   { type: 'full' }
  //   { type: 'last_n_working_days', n }
  //   { type: 'calendar_range', start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' }   // inclusive
  function selectWorkingDays(allWorkingDaysAsc, spec) {
    switch (spec && spec.type) {
      case "full":
        return [...allWorkingDaysAsc];
      case "last_n_working_days": {
        const n = Math.max(1, spec.n | 0);
        return allWorkingDaysAsc.slice(-n);
      }
      case "calendar_range":
        return allWorkingDaysAsc.filter((d) => d >= spec.start && d <= spec.end);
      default:
        return [...allWorkingDaysAsc];
    }
  }

  // ---------------------------------------------------------------------------
  // Core metrics calculator (shared between processRawData and
  // processWithTimeframe). `workingDays` is an array of YYYY-MM-DD strings.
  // ---------------------------------------------------------------------------
  function calculateMetricsForDays(entries, workingDays) {
    const filteredEntries = entries.filter((entry) => {
      const startTime = parseDateTime(entry.start);
      if (!startTime || entry.duration <= 0) return false;
      const date = startTime.toISOString().split("T")[0];
      return workingDays.includes(date);
    });

    // Billable hours
    let totalBillableSeconds = 0;
    const dailyBillableHours = {};
    filteredEntries.forEach((entry) => {
      if (entry.billable && entry.duration > 0) {
        totalBillableSeconds += entry.duration;
        const date = parseDateTime(entry.start).toISOString().split("T")[0];
        if (!dailyBillableHours[date]) dailyBillableHours[date] = 0;
        dailyBillableHours[date] += entry.duration / 3600;
      }
    });
    const billableHours = totalBillableSeconds / 3600;
    const billableDays = Object.keys(dailyBillableHours).length;
    const dailyBillableAvg = billableDays > 0 ? billableHours / billableDays : 0;

    // Time away from home
    let totalAwaySeconds = 0;
    const dailyAwayHours = {};
    filteredEntries.forEach((entry) => {
      const tags = entry.tags || [];
      if (!tags.includes("HomeOffice") && entry.duration > 0) {
        totalAwaySeconds += entry.duration;
        const date = parseDateTime(entry.start).toISOString().split("T")[0];
        if (!dailyAwayHours[date]) dailyAwayHours[date] = 0;
        dailyAwayHours[date] += entry.duration / 3600;
      }
    });
    const awayFromHomeHours = totalAwaySeconds / 3600;
    const awayDays = Object.keys(dailyAwayHours).length;
    const dailyAwayAvg = awayDays > 0 ? awayFromHomeHours / awayDays : 0;

    // Back home times (only days with Commuting)
    const dailyLastEntries = {};
    filteredEntries.forEach((entry) => {
      const startTime = parseDateTime(entry.start);
      const endTime = parseDateTime(entry.stop);
      if (!startTime || !endTime) return;
      const date = startTime.toISOString().split("T")[0];
      if (!dailyLastEntries[date]) {
        dailyLastEntries[date] = {
          entries: [],
          lastCommutingTime: null,
          lastOverallEntry: null,
        };
      }
      dailyLastEntries[date].entries.push({
        startTime,
        endTime,
        tags: entry.tags || [],
        entry,
      });
    });

    Object.keys(dailyLastEntries).forEach((date) => {
      const dayData = dailyLastEntries[date];
      dayData.entries.sort((a, b) => a.startTime - b.startTime);
      let lastCommutingEntry = null;
      dayData.entries.forEach((entryData) => {
        if (entryData.tags.includes("Commuting")) lastCommutingEntry = entryData;
      });
      dayData.lastOverallEntry = lastCommutingEntry || null;
    });

    const backHomeTimes = Object.values(dailyLastEntries)
      .filter((dayData) => dayData.lastOverallEntry)
      .map(
        (dayData) =>
          dayData.lastOverallEntry.endTime.getHours() * 60 + dayData.lastOverallEntry.endTime.getMinutes(),
      );
    const backHomeStats = calculateStats(backHomeTimes);

    // HomeOffice end times (pure-HomeOffice days only)
    const dailyHomeOfficeEntries = {};
    filteredEntries.forEach((entry) => {
      const tags = entry.tags || [];
      const startTime = parseDateTime(entry.start);
      const endTime = parseDateTime(entry.stop);
      if (!startTime || !endTime) return;
      const date = startTime.toISOString().split("T")[0];
      if (!dailyHomeOfficeEntries[date]) {
        dailyHomeOfficeEntries[date] = { homeOfficeEntries: [], allEntries: [] };
      }
      dailyHomeOfficeEntries[date].allEntries.push({
        startTime,
        endTime,
        tags,
        isHomeOffice: tags.includes("HomeOffice"),
        entry,
      });
      if (tags.includes("HomeOffice")) {
        dailyHomeOfficeEntries[date].homeOfficeEntries.push({ startTime, endTime, tags, entry });
      }
    });

    const validHomeOfficeDays = {};
    Object.keys(dailyHomeOfficeEntries).forEach((date) => {
      const dayData = dailyHomeOfficeEntries[date];
      dayData.allEntries.sort((a, b) => a.startTime - b.startTime);
      dayData.homeOfficeEntries.sort((a, b) => a.startTime - b.startTime);
      if (dayData.homeOfficeEntries.length === 0) return;
      const lastEntryOfDay = dayData.allEntries[dayData.allEntries.length - 1];
      const lastHomeOfficeEntry = dayData.homeOfficeEntries[dayData.homeOfficeEntries.length - 1];
      const commutingEntries = dayData.allEntries.filter((e) => e.tags.includes("Commuting"));
      const lastCommutingEntry =
        commutingEntries.length > 0 ? commutingEntries[commutingEntries.length - 1] : null;
      if (lastCommutingEntry && lastHomeOfficeEntry.startTime > lastCommutingEntry.endTime) return;
      const entriesAfterLastHomeOffice = dayData.allEntries.filter(
        (e) => e.startTime > lastHomeOfficeEntry.endTime && !e.isHomeOffice,
      );
      if (entriesAfterLastHomeOffice.length > 0) return;
      if (lastEntryOfDay.isHomeOffice) validHomeOfficeDays[date] = lastHomeOfficeEntry;
    });

    const homeOfficeEndTimes = Object.values(validHomeOfficeDays).map(
      (entryData) => entryData.endTime.getHours() * 60 + entryData.endTime.getMinutes(),
    );
    const homeOfficeStats = calculateStats(homeOfficeEndTimes);

    // Late work frequency
    const workDays = new Set();
    const lateWorkDays = new Set();
    filteredEntries.forEach((entry) => {
      const startTime = parseDateTime(entry.start);
      const endTime = parseDateTime(entry.stop);
      if (!startTime) return;
      const date = startTime.toISOString().split("T")[0];
      workDays.add(date);
      if (startTime.getHours() >= 20 || (endTime && endTime.getHours() >= 20)) {
        lateWorkDays.add(date);
      }
    });
    const lateWorkPercentage = workDays.size > 0 ? (lateWorkDays.size / workDays.size) * 100 : 0;

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
        percentage: Math.round(lateWorkPercentage * 10) / 10,
      },
      total_entries: filteredEntries.length,
      working_days_analyzed: workingDays.length,
    };
  }

  // ---------------------------------------------------------------------------
  // Public APIs
  // ---------------------------------------------------------------------------

  // Original API: 30-day window with 7-vs-30 trends.
  // Kept unchanged for backward compatibility with the regression test and
  // any external consumer that already uses it.
  function processRawData(rawData) {
    const entries = rawData.raw_entries || [];
    const datesAsc = computeAllWorkingDaysAsc(entries);
    const datesDesc = [...datesAsc].reverse();

    const last30WorkingDays = datesDesc.slice(0, 30);
    const last7WorkingDays = datesDesc.slice(0, 7);

    const oldestWorkingDay30 = last30WorkingDays[last30WorkingDays.length - 1];
    const oldestWorkingDay7 = last7WorkingDays[last7WorkingDays.length - 1];

    console.log(
      `📊 Using last 30 working days: ${last30WorkingDays.length} days from ${oldestWorkingDay30} to ${last30WorkingDays[0]}`,
    );
    console.log(
      `📊 Using last 7 working days: ${last7WorkingDays.length} days from ${oldestWorkingDay7} to ${last7WorkingDays[0]}`,
    );

    const metrics30Days = calculateMetricsForDays(entries, last30WorkingDays);
    const metrics7Days = calculateMetricsForDays(entries, last7WorkingDays);

    const trends = {
      billable_hours: calculateTrend(
        metrics7Days.daily_billable_avg,
        metrics30Days.daily_billable_avg,
      ),
      back_home_time: calculateTrend(
        metrics7Days.back_home_stats.mean,
        metrics30Days.back_home_stats.mean,
      ),
    };

    console.log(`🏠 Valid HomeOffice days (30d): ${metrics30Days.home_office_end_stats.count}`);
    console.log(`🏠 Valid HomeOffice days (7d): ${metrics7Days.home_office_end_stats.count}`);
    console.log(`🚪 Back home times (30d): ${metrics30Days.back_home_stats.count} days (only days with commuting)`);
    console.log(`🚪 Back home times (7d): ${metrics7Days.back_home_stats.count} days (only days with commuting)`);
    console.log(`📈 Trends - Billable: ${trends.billable_hours.trend}, Back home: ${trends.back_home_time.trend}`);

    return {
      ...metrics30Days,
      date_range: {
        start: oldestWorkingDay30 || "N/A",
        end: last30WorkingDays[0] || "N/A",
      },
      last_7_days: metrics7Days,
      trends: trends,
    };
  }

  // New API: compute metrics for an arbitrary timeframe (working-day-based or
  // calendar-based). Trends are always recent (last 10 working days from the
  // entire history) vs the selected timeframe.
  //
  // Usage:
  //   processWithTimeframe(rawData, { type: 'last_n_working_days', n: 30 })
  //   processWithTimeframe(rawData, { type: 'calendar_range', start: '2025-11-01', end: '2025-11-30' })
  //   processWithTimeframe(rawData, { type: 'full' })
  function processWithTimeframe(rawData, timeframeSpec) {
    const entries = rawData.raw_entries || [];
    const datesAsc = computeAllWorkingDaysAsc(entries);
    const selectedDays = selectWorkingDays(datesAsc, timeframeSpec || { type: "full" });
    // Trend baseline: last 10 working days across the full history.
    const last10WorkingDays = datesAsc.slice(-10);

    const selectedMetrics = calculateMetricsForDays(entries, selectedDays);
    const last10Metrics = calculateMetricsForDays(entries, last10WorkingDays);

    const trends = {
      billable_hours: calculateTrend(
        last10Metrics.daily_billable_avg,
        selectedMetrics.daily_billable_avg,
      ),
      back_home_time: calculateTrend(
        last10Metrics.back_home_stats.mean,
        selectedMetrics.back_home_stats.mean,
      ),
    };

    return {
      ...selectedMetrics,
      timeframe: timeframeSpec || { type: "full" },
      date_range: {
        start: selectedDays[0] || "N/A",
        end: selectedDays[selectedDays.length - 1] || "N/A",
      },
      last_10_days: last10Metrics,
      trends: trends,
    };
  }

  return { processRawData, processWithTimeframe, calculateMetricsForDays, computeAllWorkingDaysAsc, selectWorkingDays };
});
