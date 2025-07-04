# Telegram Bot Conflict Resolution

## Problem
The error "Conflict: terminated by other getUpdates request; make sure that only one bot instance is running" occurs when multiple instances of your bot try to poll for updates simultaneously.

## Common Causes
1. **Multiple deployments running** - Multiple instances on Render or other platforms
2. **Local development conflicts** - Testing locally while production is running
3. **Previous instances not terminated** - Old processes still polling
4. **Webhook conflicts** - Webhooks interfering with polling

## Solutions Implemented

### 1. Automatic Conflict Resolution
The bot now includes automatic conflict resolution:
- Clears webhooks on startup
- Retries polling with exponential backoff
- Better process cleanup

### 2. Clean Deployment Script
Use `deploy_clean.py` instead of `main.py` for deployment:
```bash
python deploy_clean.py
```

This script:
- Clears bot conflicts first
- Waits for system stabilization
- Starts the main application cleanly

### 3. Manual Conflict Resolution
If you still experience conflicts, run:
```bash
python clear_bot_conflicts.py
```

This utility:
- Tests bot connectivity
- Clears any existing webhooks
- Drops pending updates
- Tests polling capability

### 4. Process Cleanup
The bot automatically kills conflicting processes on startup, looking for:
- `main.py`
- `telegram_bot`
- `bybit`
- `scanner`
- `bot`

## Deployment Changes
- **Procfile**: Now uses `python deploy_clean.py`
- **render.yaml**: Updated startCommand to use clean deployment

## Troubleshooting

### If conflicts persist:
1. **Check for multiple deployments**: Ensure only one instance is deployed
2. **Wait for timeout**: Telegram API has a timeout period (usually 1-2 minutes)
3. **Manual cleanup**: Run `python clear_bot_conflicts.py`
4. **Check logs**: Look for other instances in your deployment platform

### For development:
1. **Stop production**: Temporarily stop production instance
2. **Clear conflicts**: Run conflict resolution script
3. **Test locally**: Start your local instance
4. **Restart production**: After local testing

## Prevention
- Always use the clean deployment script
- Don't run multiple instances simultaneously
- Use proper shutdown procedures
- Monitor deployment logs for conflicts

## Emergency Recovery
If the bot is completely stuck:
1. Stop all deployments
2. Wait 5 minutes
3. Run `python clear_bot_conflicts.py`
4. Redeploy using `python deploy_clean.py`