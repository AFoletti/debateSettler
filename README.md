# 🎯 DebateSettler Dashboard
> **Prove your point with data, without starting a war** 📊

DebateSettler is here to help you settle those classic debates about your working hours and family time—without the endless “You’re always late!” claims. Let’s be honest, perception is a sneaky trickster when all you have are memories to rely on. Now you can calmly show that no, you’re not always walking in the door after 19:00; most days you’re home closer to 18:00. Yes, sometimes you work late, but those evenings after 20:00? Just a few in the last two months, really. Better yet, DebateSettler isn’t about blame—it's about reassurance and finding common ground so you can agree on what's really going on and maybe even improve things together. Because sometimes, it’s not as tough as it seems—just a little data, a little empathy, and a lot less grumbling.

A **pure static HTML/CSS/JS** dashboard that transforms your Toggl Track time logs into easy to understand visual insights. Optimized for GitHub Pages deployment with zero build process - edit directly on GitHub!

## 📁 Simple File Structure

```
/
├── index.html          # Main dashboard (edit directly!)
├── style.css           # All styling (pure CSS, no frameworks)  
├── script.js           # All functionality (vanilla JavaScript)
├── manifest.json       # PWA manifest
├── favicon.ico         # Site icon
├── data/
│   └── raw_data.json   # Auto-updated by GitHub Actions
└── scripts/
    └── fetch-toggl-data.py  # Data fetching (unchanged)
```

## ✨ Key Features

### 📊 **Comprehensive Time Analytics**
- **Total Billable Hours** - Track productive work with daily averages
- **Time Away from Home** - Monitor hours away from home
- **Back Home Statistics** - Commute end times (mean, median, earliest, latest)
- **HomeOffice End Times** - Work-from-home work patterns
- **Late Work Frequency** - Track work sessions after 20:00
- **Recent Trends Card** - Compare 7-day mean against 30-day baseline

### 🎨 **Modern Dark UI**
- **Dark Theme by Default** - Easy on the eyes for data analysis
- **Responsive Design** - Perfect on desktop, tablet, and mobile
- **Professional Layout** - Clean 3-column grid with intuitive cards
- **Real-time Data Status** - Shows last update time and data freshness

### 🤖 **Fully Automated**
- **GitHub Actions Integration** - Daily data fetching at 6:00 AM UTC
- **Static Site Deployment** - No backend required, ultra-fast loading
- **Client-side Processing** - All calculations performed in your browser
- **Yesterday-Only Data** - Ensures complete day statistics (excludes current day)

## 🚀 Quick Setup for GitHub Pages

### 1. Repository Setup
```bash
# Fork or use this repository as-is
# No installation required - it's all static files!
```

### 2. Configure GitHub Secrets
- Navigate to **Settings → Secrets and Variables → Actions**
- Add new secret: `TOGGL_API_TOKEN`
- Get your token from **Toggl Profile → API Token**

### 3. Enable GitHub Pages
- **Repository Settings → Pages**
- **Source**: Deploy from a branch
- **Branch**: `main` (serves files directly from root)

### 4. Start Editing Directly on GitHub!
- Edit `index.html` for content changes
- Edit `style.css` for styling tweaks  
- Edit `script.js` for functionality modifications
- Changes are live immediately!

## 📊 Data Architecture

### **Smart Working Days Logic**
- **30-Day Analysis**: Statistics from last 30 working days (days with actual entries)
- **7-Day Trends**: Recent trend from last 7 working days
- **Calendar vs Working Days**: Excludes weekends/holidays without entries
- **Yesterday Boundary**: Data always ends yesterday for complete statistics

### **Advanced Filtering Rules**
- **Back Home Times**: Only days with actual commuting tracked
- **HomeOffice End Times**: Pure HomeOffice days (no mixed work patterns)
- **Edge Case Handling**: Complex day-mixing logic (HomeOffice + Commuting)
- **Late Work Detection**: Entries starting or ending after 20:00

### **Raw Data Processing**
- **60-Day Data Fetch**: Ensures sufficient working days for analysis
- **Client-Side Calculations**: No server dependency, works offline
- **Real-time Processing**: Metrics calculated on every page load
- **Debug Logging**: Console shows calculation details for transparency

## 🛠️ Development & Customization

### **Local Testing**
```bash
# Serve the files locally (any static server works)
python -m http.server 8000
# or
npx serve .
# or just open index.html in your browser!
```

### **Customizing Colors**
Edit the CSS variables in `style.css`:
```css
:root {
    --primary-400: #60a5fa;  /* Change primary color */
    --dark-100: #2a2a2a;     /* Change card background */
    /* ... modify any colors you want */
}
```

### **Adding New Metrics**
1. Add HTML in `index.html` for the new metric display
2. Add styling in `style.css` if needed
3. Add calculation logic in `script.js` in the `processRawData` function
4. Update the `updateUI` function to display your new metric

## 🔄 Automated Workflow

The GitHub Action runs daily and:
1. **Fetches Raw Data** (60 days, excluding today)
2. **Updates JSON File** (`data/raw_data.json`)
3. **Commits Changes** automatically
4. **Data is Live** immediately (no build step!)

### **Manual Trigger Options**
- **GitHub Actions Tab** → "Fetch Toggl Data Daily" → "Run workflow"
- **"Fetch New Data" Button** → Auto-opens GitHub Actions page
- **API Call**: Trigger via GitHub API for custom schedules
- **Local Testing**: Run `python scripts/fetch-toggl-data.py` with API token

## 🔒 Security & Privacy

- **API Token Security**: Stored in GitHub Secrets, never exposed
- **No Backend**: Static site eliminates server vulnerabilities
- **Client-Side Processing**: Data calculations in your browser only
- **No Third-Party Analytics**: Your data stays with you
- **HTTPS Deployment**: GitHub Pages provides SSL by default

## 🚦 Performance
- **Ultra-Fast Loading**: Static files, no build process
- **Mobile Optimized**: Responsive design for all devices
- **Efficient Updates**: Only data changes, instant updates
- **Tiny Footprint**: ~15KB HTML + ~8KB CSS + ~12KB JS (uncompressed)

**Built with**: Pure HTML • Pure CSS • Vanilla JavaScript • GitHub Actions • Toggl Track API
