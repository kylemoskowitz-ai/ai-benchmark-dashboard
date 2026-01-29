# Deploying to Streamlit Cloud

This guide walks you through deploying the AI Benchmark Dashboard to Streamlit Cloud for free hosting.

## Prerequisites

- GitHub account
- Streamlit Cloud account (free, uses GitHub OAuth)

## Step 1: Push to GitHub

Create a new repository on GitHub, then push this project:

```bash
cd ai-benchmark-dashboard

# Initialize git (if not already)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: AI Benchmark Dashboard"

# Add your GitHub repo as remote
git remote add origin https://github.com/YOUR_USERNAME/ai-benchmark-dashboard.git

# Push
git push -u origin main
```

## Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **"New app"**
3. Connect your GitHub account (if not already)
4. Select your repository: `YOUR_USERNAME/ai-benchmark-dashboard`
5. Set the **Main file path**: `src/dashboard/app.py`
6. Click **"Deploy!"**

## Step 3: Wait for Build

Streamlit Cloud will:
1. Clone your repo
2. Install dependencies from `requirements.txt`
3. Start the app

This takes 2-5 minutes for the first deployment.

## Your Live URL

Once deployed, you'll get a URL like:
```
https://your-app-name.streamlit.app
```

You can customize this in the app settings.

## Updating the Dashboard

Any push to `main` branch automatically redeploys:

```bash
git add .
git commit -m "Update dashboard"
git push
```

## Troubleshooting

### "Module not found" errors
- Check `requirements.txt` includes all dependencies
- Ensure imports use relative paths from project root

### Database issues
- The seed database (`data/benchmark.duckdb`) must be committed
- Check `.gitignore` doesn't exclude it

### App crashes on startup
- Check Streamlit Cloud logs in the dashboard
- Common issues: missing dependencies, path errors

## Secrets Management

For API keys or sensitive config, use Streamlit Cloud's secrets:

1. Go to your app settings
2. Click "Secrets"
3. Add secrets in TOML format:
   ```toml
   [api]
   key = "your-secret-key"
   ```
4. Access in code: `st.secrets["api"]["key"]`

## Custom Domain

Streamlit Cloud supports custom domains on the Team plan.
For free tier, you can use the provided `.streamlit.app` subdomain.
