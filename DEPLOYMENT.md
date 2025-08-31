# BunBot Deployment Guide

## Render Free Tier Deployment

This guide will help you deploy BunBot to Render's free tier for 24/7 hosting.

### Prerequisites

1. **GitHub Account** - Your code needs to be in a public GitHub repository
2. **Discord Bot Token** - From Discord Developer Portal
3. **Render Account** - Sign up at [render.com](https://render.com) (free)

### Step 1: Prepare Your Repository

Your repository should already have these files (created automatically):
- ✅ `Procfile` - Tells Render how to start your bot
- ✅ `render.yaml` - Render configuration
- ✅ `keep_alive.py` - Prevents sleeping on free tier
- ✅ `requirements.txt` - Python dependencies
- ✅ `bot.py` - Updated with keep-alive integration

### Step 2: Push to GitHub

```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

**Important:** Your repository must be **public** for Render's free tier.

### Step 3: Deploy to Render

1. **Sign up/Login to Render**
   - Go to [render.com](https://render.com)
   - Sign up with GitHub (recommended)

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub account if not already connected
   - Select your BunBot repository

3. **Configure Service**
   - **Name:** `bunbot-bot` (or your preferred name)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Plan:** `Free`

4. **Set Environment Variables**
   Click "Environment" tab and add:
   ```
   BOT_TOKEN = your_discord_bot_token_here
   LOG_LEVEL = INFO
   TLS_VERIFY = True
   CLUSTER_ID = 0
   TOTAL_CLUSTERS = 1
   TOTAL_SHARDS = 1
   DEMO_MODE = False
   ```

5. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment (5-10 minutes)
   - Check logs for "Bot ready" message

### Step 4: Verify Deployment

1. **Check Service Status**
   - Service should show "Live" status
   - Logs should show "BunBot - Discord radio bot"
   - Keep-alive server should start on port 8080

2. **Test Bot in Discord**
   - Bot should appear online in your Discord server
   - Try `/play` command to test functionality
   - Voice connections should work properly

### Render Free Tier Limitations

⚠️ **Important Limitations:**
- **Sleeps after 15 minutes** of no HTTP requests
- **750 hours/month** limit (about 25 days)
- **Slower cold starts** when waking up

✅ **How We Handle This:**
- Keep-alive server provides HTTP endpoint
- Bot wakes up instantly when Discord commands are used
- Most Discord servers don't have constant activity anyway

### Monitoring Your Bot

1. **Render Dashboard**
   - View logs in real-time
   - Monitor resource usage
   - Check deployment status

2. **Discord Bot Status**
   - Bot appears online when service is running
   - Bot appears offline when service is sleeping
   - Commands wake the bot immediately

### Troubleshooting

**Bot Not Starting:**
- Check environment variables (especially BOT_TOKEN)
- Verify Discord bot permissions in Developer Portal
- Check Render logs for error messages

**Bot Going Offline:**
- Normal behavior on free tier after 15 minutes
- Bot wakes up when someone uses a command
- Consider upgrading to paid plan for 24/7 uptime

**Voice Commands Not Working:**
- Ensure bot has voice permissions in Discord server
- Check that voice intents are enabled in Discord Developer Portal
- Verify bot is in a voice channel

### Upgrading to Paid Plan

For true 24/7 uptime without sleeping:
- Render Starter Plan: $7/month
- No sleep limitations
- Faster performance
- More resources

### Support

If you encounter issues:
1. Check Render logs first
2. Verify Discord bot configuration
3. Test locally to isolate cloud-specific issues
4. Check Discord API status

---

## Alternative Deployment Options

### Railway (Alternative)
- Similar to Render
- $5/month for hobby plan
- Easy GitHub integration

### DigitalOcean VPS
- $6/month for basic droplet
- Full control over environment
- Requires Linux knowledge

### Raspberry Pi (Home Hosting)
- One-time cost (~$75)
- Runs at home 24/7
- Depends on home internet

---

**Your BunBot bot is now ready for 24/7 cloud hosting! 🎵**
