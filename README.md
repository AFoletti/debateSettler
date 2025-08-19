# ArgumentSettler Dashboard

> Win debates with data, not emotions 📊

An attractive web dashboard that uses the Toggl Track API to pull time log entries and provide easy-to-understand metrics to settle arguments with hard data.

## 🎯 Features

- **Total Billable Hours** - Track your productive work time
- **Time Away from Home** - Hours without HomeOffice tag  
- **Commute Statistics** - When you get back home (mean, median, earliest, latest)
- **HomeOffice End Times** - When you finish work from home
- **Late Work Frequency** - How often you work after 8 PM

## 🚀 GitHub Pages Deployment

This app is designed to be deployed on GitHub Pages with daily automatic data updates via GitHub Actions.

### Setup Instructions

1. **Fork/Clone this repository**

2. **Set up GitHub Secret**
   - Go to your repository Settings → Secrets and Variables → Actions
   - Add a new secret named `TOGGL_API_TOKEN`
   - Set the value to your Toggl Track API token (found in Toggl Profile → API Token)

3. **Update package.json homepage**
   ```json
   {
     "homepage": "https://yourusername.github.io/argumentsettler-dashboard"
   }
   ```

4. **Enable GitHub Pages**
   - Go to repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: `gh-pages` (will be created automatically)

5. **Deploy**
   ```bash
   npm install
   npm run build
   npm run deploy
   ```

### Automatic Data Updates

The GitHub Action (`.github/workflows/fetch-toggl-data.yml`) runs daily at 6:00 AM UTC to:
- Fetch your latest Toggl data
- Update `data/metrics.json`
- Commit changes automatically

You can also trigger it manually from the Actions tab.

## 🛠️ Development

```bash
# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build

# Deploy to GitHub Pages
npm run deploy
```

## 📊 Data Structure

The dashboard displays metrics for the last 30 days:
- All billable hours worked
- Hours absent from home (entries without "HomeOffice" tag)
- Commute back home times (last "Commuting" entry per day)
- HomeOffice end times (last HomeOffice entry per day)
- Late work frequency (work after 20:00)

## 🔒 Security

- API token is stored securely in GitHub Secrets
- No sensitive data in the codebase
- Static site with no backend vulnerabilities

## 📱 Responsive Design

Built with Tailwind CSS for a beautiful, responsive experience on all devices.

---

**ArgumentSettler** - Because data always wins arguments! 🏆