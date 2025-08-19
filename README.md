# 🎯 ArgumentSettler Dashboard

> **Win debates with data, not emotions** 📊

A sophisticated **static web dashboard** that transforms your Toggl Track time logs into powerful visual insights. Built for GitHub Pages deployment with automated daily data updates and advanced statistical analysis.

## ✨ Key Features

### 📊 **Comprehensive Time Analytics**
- **Total Billable Hours** - Track productive work with daily averages  
- **Time Away from Home** - Monitor hours without HomeOffice tag
- **Back Home Statistics** - Commute end times (mean, median, earliest, latest)
- **HomeOffice End Times** - Work-from-home completion patterns
- **Late Work Frequency** - Track work sessions after 8:00 PM

### 📈 **Advanced 7-Day vs 30-Day Trend Analysis**
- **Recent Trends Card** - Compare 7-day performance against 30-day baselines
- **Working Hours Trends** - Visual indicators for productivity changes
- **Back Home Trends** - Commute pattern analysis with color-coded arrows
- **Smart Thresholds** - ±15 minute differences considered "normal"

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
# Fork or clone this repository
git clone https://github.com/yourusername/argumentsettler
cd argumentsettler-dashboard
```

### 2. Configure GitHub Secrets
- Navigate to **Settings → Secrets and Variables → Actions**
- Add new secret: `TOGGL_API_TOKEN`
- Get your token from **Toggl Profile → API Token**

### 3. Update Homepage URL
```json
// package.json
{
  "homepage": "https://yourusername.github.io/argumentsettler"
}
```

### 4. Deploy to GitHub Pages
```bash
yarn install
yarn build
# Push to your repository - GitHub Actions handles the rest!
```

### 5. Enable GitHub Pages
- **Repository Settings → Pages**
- **Source**: Deploy from a branch
- **Branch**: `gh-pages` (auto-created by Actions)

## 📊 Data Architecture

### **Smart Working Days Logic**
- **30-Day Analysis**: Statistics from last 30 working days (days with actual entries)
- **7-Day Trends**: Recent performance from last 7 working days  
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

## 🛠️ Development

### **Local Development**
```bash
# Install dependencies (using Yarn)
yarn install

# Start development server
yarn start

# Build for production  
yarn build

# Test production build locally
yarn global add serve
serve -s build
```

### **Project Structure**
```
/app
├── src/
│   ├── App.js          # Main dashboard component with all logic
│   ├── App.css         # Dark theme and responsive styles
│   └── index.js        # React entry point
├── public/
│   └── data/           # Static data served to frontend
│       └── raw_data.json
├── scripts/
│   └── fetch-toggl-data.py  # Data fetching script
└── .github/workflows/
    └── fetch-toggl-data.yml # Automated daily updates
```

## 🎨 UI/UX Highlights

### **Dark Theme Design**
- **Professional Color Palette**: Deep grays, blues, and accent colors
- **High Contrast**: Optimized for data readability
- **Gradient Header**: Attractive visual hierarchy  
- **Card-based Layout**: Clean information grouping

### **Responsive Grid System**
- **Desktop**: 3-column layout (Back Home | HomeOffice | Trends)
- **Tablet**: Adaptive 2-column with stacking
- **Mobile**: Single column with touch-friendly interactions
- **Typography**: Scalable fonts for all screen sizes

### **Interactive Elements**
- **Refresh Button**: Manual data reload capability
- **Trend Indicators**: Color-coded arrows (🔴 Up, 🟢 Down, ⚪ Stable)
- **Hover States**: Enhanced visual feedback
- **Loading States**: Professional loading spinners

## 🔄 Automated Workflow

The GitHub Action runs daily and:

1. **Fetches Raw Data** (60 days, excluding today)
2. **Updates JSON File** (`data/raw_data.json`)
3. **Commits Changes** automatically
4. **Triggers Rebuild** for GitHub Pages
5. **Shows Status** in Actions tab

### **Manual Trigger Options**
- **GitHub Actions Tab** → "Fetch Toggl Data Daily" → "Run workflow"
- **API Call**: Trigger via GitHub API for custom schedules
- **Local Testing**: Run `python scripts/fetch-toggl-data.py` with API token

## 🔒 Security & Privacy

- ✅ **API Token Security**: Stored in GitHub Secrets, never exposed
- ✅ **No Backend**: Static site eliminates server vulnerabilities  
- ✅ **Client-Side Processing**: Data calculations in your browser only
- ✅ **No Third-Party Analytics**: Your data stays with you
- ✅ **HTTPS Deployment**: GitHub Pages provides SSL by default

## 🚦 Performance

- **⚡ Ultra-Fast Loading**: Static site with optimized bundles
- **📱 Mobile Optimized**: Responsive design for all devices
- **🔄 Efficient Updates**: Only data changes, not full rebuilds
- **💾 Small Footprint**: ~51KB main JS + 3.5KB CSS (gzipped)

## 🤝 Contributing

This is a personal time tracking dashboard, but feel free to:
- **Fork** for your own use case
- **Report Issues** if you find bugs
- **Suggest Features** via GitHub Issues
- **Share** your modifications and improvements

## 📈 Usage Analytics 

The dashboard provides insights into:
- **Productivity Trends**: Are you working more or less lately?
- **Work-Life Balance**: Commute patterns and home office efficiency  
- **Time Management**: Late work frequency and daily consistency
- **Location Efficiency**: Home vs office productivity comparison

---

## 🎉 **ArgumentSettler** 
*Because when you need to prove your loved ones you're not working too much, data is your best friend!* 

**Built with**: React • Tailwind CSS • GitHub Actions • Toggl Track API
