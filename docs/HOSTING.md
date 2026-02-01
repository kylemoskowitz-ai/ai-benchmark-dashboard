# Hosting Setup Guide

This guide covers deploying the AI Benchmark Dashboard to Cloudflare Pages with automatic data updates via GitHub Actions.

## Prerequisites

- GitHub repository with the codebase
- Cloudflare account (free tier is sufficient)
- Node.js 20+ and Python 3.11+ installed locally

## Local Development

### 1. Install dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd web && npm install
```

### 2. Run data pipeline

```bash
# Refresh all benchmark data
python -m src.cli.refresh_data

# Generate JSON artifacts for frontend
python -m src.export.generate_artifacts
```

### 3. Start development server

```bash
cd web
npm run dev
```

Visit http://localhost:3000 to see the dashboard.

### 4. Build for production

```bash
cd web
npm run build
```

The static site is output to `web/out/`.

---

## Cloudflare Pages Deployment

### Step 1: Create Cloudflare Pages Project

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → Pages
2. Click "Create a project" → "Connect to Git"
3. Select your GitHub repository
4. Configure build settings:
   - **Framework preset**: None
   - **Build command**: `cd web && npm ci && npm run build`
   - **Build output directory**: `web/out`
   - **Root directory**: `/`
5. Click "Save and Deploy"

### Step 2: Get API Credentials

1. Go to Cloudflare Dashboard → Profile → API Tokens
2. Click "Create Token" → "Custom token"
3. Configure:
   - **Token name**: `GitHub Actions Deploy`
   - **Permissions**: `Account / Cloudflare Pages / Edit`
4. Copy the token
5. Note your **Account ID** from the Cloudflare dashboard URL or overview page

### Step 3: Add GitHub Secrets

In your GitHub repository:

1. Go to Settings → Secrets and variables → Actions
2. Add the following secrets:
   - `CLOUDFLARE_API_TOKEN`: Your API token from step 2
   - `CLOUDFLARE_ACCOUNT_ID`: Your account ID

---

## GitHub Actions Workflows

### Automatic Data Updates (`update-data.yml`)

Runs every Sunday at 2 AM UTC (configurable):
- Refreshes all benchmark data from sources
- Generates new JSON artifacts
- Commits and pushes changes
- Deploys to Cloudflare Pages

### Manual Trigger

1. Go to your repo → Actions → "Update Benchmark Data"
2. Click "Run workflow"
3. Optionally specify a single benchmark to update

### Deployment on Code Changes (`deploy.yml`)

Automatically deploys when changes are pushed to:
- `web/**` (frontend code)
- `.github/workflows/deploy.yml`

---

## Configuration

### Update Schedule

Edit `.github/workflows/update-data.yml`:

```yaml
on:
  schedule:
    # Current: Every Sunday at 2 AM UTC
    - cron: '0 2 * * 0'

    # Alternative: Every Monday and Thursday at 4 AM UTC
    # - cron: '0 4 * * 1,4'

    # Alternative: 1st and 15th of each month at midnight UTC
    # - cron: '0 0 1,15 * *'
```

### Adding New Benchmarks

1. Create a new ingestor in `src/ingestors/`
2. Register it in `src/ingestors/__init__.py`
3. Add to `src/cli/refresh_data.py` if needed
4. Run locally to test: `python -m src.cli.refresh_data --benchmark your_new_benchmark`

### Updating Curated Snapshots

For benchmarks using curated data (not scraped):

1. Edit the CSV in `data/snapshots/`
2. Commit and push
3. Manually trigger the workflow or wait for schedule

---

## Monitoring

### Build Status

Check GitHub Actions tab for workflow status.

### Site Status

Cloudflare Pages dashboard shows deployment history and analytics.

### Data Freshness

The footer of the live site shows the last update timestamp.

---

## Troubleshooting

### Build Fails

- Check Node.js version matches (20+)
- Verify `web/package-lock.json` is committed
- Check for TypeScript errors: `cd web && npm run build`

### Data Not Updating

- Check GitHub Actions logs for errors
- Verify Python dependencies are installed
- Check if source websites changed their format

### Deployment Fails

- Verify Cloudflare API token has correct permissions
- Check account ID is correct
- Ensure build output directory is `web/out`

---

## Cost

- **Cloudflare Pages Free Tier**: 500 builds/month, unlimited bandwidth
- **GitHub Actions Free Tier**: 2,000 minutes/month for private repos, unlimited for public

For a "set and forget" dashboard with weekly updates, you'll use:
- ~4 builds/month
- ~20 action minutes/month

Well within free tier limits.
