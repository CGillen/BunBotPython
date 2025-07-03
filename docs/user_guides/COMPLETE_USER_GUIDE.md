# BunBot Complete User Guide

Welcome to BunBot - the advanced Discord radio streaming bot! This guide covers all features and commands available in the latest version.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Commands](#basic-commands)
3. [Favorites System](#favorites-system)
4. [Audio Enhancement](#audio-enhancement)
5. [Interactive UI Features](#interactive-ui-features)
6. [Second Life Integration](#second-life-integration)
7. [Features](#features)
8. [Deployment](#deployment)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites
- BunBot must be added to your Discord server with appropriate permissions
- You need to be in a voice channel to start streaming
- Bot requires Voice Channel permissions

### Quick Start
1. Join a voice channel
2. Use `/play <stream_url>` to start playing a radio stream
3. Use `/song` to see what's currently playing
4. Use `/leave` to stop the stream

---

## Basic Commands

### Core Streaming Commands

#### `/play <url>`
**Description:** Begin playback of a Shoutcast/Icecast stream
- **Usage:** `/play http://example.com:8000/stream`
- **Permissions:** None required
- **Cooldown:** 5 seconds

#### `/leave [force]`
**Description:** Remove the bot from the voice channel
- **Usage:** `/leave` or `/leave force:True`
- **Features:**
  - Automatic state recovery if desync detected
  - Force option to clear stale bot state
- **Cooldown:** 5 seconds

#### `/song`
**Description:** Display current song information
- **Usage:** `/song`
- **Shows:** Current track, station name, stream metadata
- **Cooldown:** 5 seconds

#### `/refresh`
**Description:** Refresh the current stream
- **Usage:** `/refresh`
- **Note:** Bot may briefly disconnect and reconnect
- **Cooldown:** 5 seconds

---

## Favorites System

### Managing Favorites

#### `/set-favorite <url> [name]`
**Description:** Add a radio station to your server's favorites
- **Usage:** `/set-favorite http://stream.url Optional Name`
- **Features:**
  - Automatic stream validation
  - Custom naming support
  - Numbered for easy access
- **Cooldown:** 5 seconds

#### `/play-favorite <number>`
**Description:** Play a favorite station by its number
- **Usage:** `/play-favorite 1`
- **Note:** Use `/list-favorites` to see available numbers
- **Cooldown:** 5 seconds

#### `/favorites`
**Description:** Interactive favorites browser with clickable buttons
- **Usage:** `/favorites`
- **Features:**
  - Rich embeds with station info
  - Interactive play buttons
  - Pagination for many favorites
- **Cooldown:** 10 seconds

#### `/list-favorites`
**Description:** Simple text list of all favorites (mobile-friendly)
- **Usage:** `/list-favorites`
- **Features:**
  - Clean text format
  - Shows all favorite numbers and names
  - Mobile-optimized display
- **Cooldown:** 5 seconds

#### `/remove-favorite <number>`
**Description:** Remove a favorite station
- **Usage:** `/remove-favorite 3`
- **Note:** Subsequent favorites will be renumbered
- **Cooldown:** 5 seconds

---

## Audio Enhancement

BunBot includes advanced audio processing features for enhanced listening experience.

### Volume Control

#### `/volume <level>`
**Description:** Adjust master volume
- **Usage:** `/volume 75`
- **Range:** 0-100
- **Features:**
  - Real-time volume adjustment
  - Guild-specific settings
  - Persistent across streams
- **Cooldown:** 3 seconds

### Equalizer System

#### `/eq <bass> <mid> <treble>`
**Description:** Adjust 3-band equalizer
- **Usage:** `/eq bass:2.0 mid:-1.0 treble:3.5`
- **Range:** -12.0 to +12.0 dB for each band
- **Features:**
  - Real-time EQ adjustment
  - Independent band control
  - Professional-grade processing
- **Cooldown:** 3 seconds

#### `/eq-preset <preset>`
**Description:** Apply predefined equalizer presets
- **Usage:** `/eq-preset rock`
- **Available Presets:**
  - `flat` - No EQ modification
  - `rock` - Enhanced bass and treble
  - `pop` - Balanced for pop music
  - `classical` - Enhanced mids and treble
  - `bass-boost` - Heavy bass enhancement
  - `treble-boost` - Enhanced highs
  - `voice` - Optimized for talk radio
- **Cooldown:** 3 seconds

### Audio Information

#### `/audio-info`
**Description:** Display current audio processing settings
- **Usage:** `/audio-info`
- **Shows:**
  - Current volume level
  - EQ settings (bass, mid, treble)
  - Audio quality level
  - Sample rate and channels
  - Processing features status
- **Cooldown:** 5 seconds

---

## UI Features

BunBot provides modern interactive UI components that enhance the user experience with clickable controls and real-time updates.

### Button-Based Controls

#### Favorites Browser
- **Access:** Use `/favorites` command
- **Features:**
  - ✅ **Play Buttons**: Click to instantly play any favorite station
  - ✅ **Navigation**: Previous/Next page buttons for large favorite lists
  - ✅ **Add/Remove**: Quick action buttons for managing favorites
  - ✅ **Real-time Updates**: Live status updates when stations change

#### Command Responses
- **Play Commands**: Interactive buttons for stop/refresh/favorite/volume
- **Song Information**: Share/lyrics/skip/info buttons with live updates
- **Error Responses**: Retry/help/support buttons for better error recovery
- **Volume Controls**: Quick +10%/-10% volume adjustment buttons

---

## Second Life Integration

BunBot includes comprehensive Second Life integration through a REST API server and LSL script toolkit, enabling seamless control from virtual worlds.

### 🌐 **REST API Server**

#### API Endpoints Overview
BunBot provides **24 REST API endpoints** across 5 categories for complete remote control:

**Stream Control (5 endpoints):**
- `POST /api/v1/streams/play` - Start stream playback
- `POST /api/v1/streams/stop` - Stop current stream
- `GET /api/v1/streams/status` - Get playback status
- `POST /api/v1/streams/refresh` - Refresh stream connection
- `GET /api/v1/streams/history` - Get stream history

**Audio Control (4 endpoints):**
- `POST /api/v1/audio/volume` - Set master volume
- `POST /api/v1/audio/eq` - Adjust equalizer settings
- `POST /api/v1/audio/preset` - Apply EQ presets
- `GET /api/v1/audio/info` - Get audio configuration

**Favorites Management (5 endpoints):**
- `GET /api/v1/favorites` - List all favorites
- `POST /api/v1/favorites` - Add new favorite
- `PUT /api/v1/favorites/{id}` - Update favorite
- `DELETE /api/v1/favorites/{id}` - Remove favorite
- `POST /api/v1/favorites/{id}/play` - Play specific favorite

**Status & Monitoring (5 endpoints):**
- `GET /api/v1/status/health` - Health check
- `GET /api/v1/status/info` - Server information
- `GET /api/v1/status/stats` - Usage statistics
- `GET /api/v1/status/guilds` - Guild information
- `GET /api/v1/status/performance` - Performance metrics

**Settings & Configuration (5 endpoints):**
- `GET /api/v1/settings/config` - Get configuration
- `PUT /api/v1/settings/config` - Update configuration
- `GET /api/v1/settings/permissions` - Get permissions
- `PUT /api/v1/settings/permissions` - Update permissions
- `POST /api/v1/settings/reset` - Reset to defaults

### 🔐 **Authentication & Security**

#### JWT Token Authentication
```lsl
// Step 1: Get API token
llHTTPRequest("http://your-server.com/api/v1/auth/token", 
    [HTTP_METHOD, "POST",
     HTTP_BODY, "{\"api_key\":\"your_dev_key\",\"guild_id\":123456}"], "");

// Step 2: Use token in subsequent requests
llHTTPRequest("http://your-server.com/api/v1/streams/play",
    [HTTP_METHOD, "POST",
     HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + token,
     HTTP_BODY, "{\"url\":\"http://stream.com\",\"guild_id\":123456}"], "");
```

#### Security Features
- **JWT Authentication**: Secure token-based access
- **Role-Based Permissions**: Granular access control
- **Rate Limiting**: Prevents API abuse (100 requests/minute default)
- **Guild Isolation**: Users can only access their authorized guilds
- **CORS Support**: Secure web-based integrations

### 📜 **LSL Script Toolkit**

BunBot includes 4 ready-to-use LSL scripts for different Second Life integration scenarios:

#### 1. Basic Controller (`basic_controller.lsl`)
**Purpose**: Simple touch-based radio control object
**Features:**
- Touch to play/stop radio
- Menu-driven station selection
- Volume control dialogs
- Status display with color changes
- Owner and group access modes

**Usage:**
1. Create a prim in Second Life
2. Add the `basic_controller.lsl` script
3. Configure server URL and API key
4. Touch to access radio controls

#### 2. HUD Interface (`hud_interface.lsl`)
**Purpose**: Wearable radio control panel
**Features:**
- Compact HUD design
- Quick-access favorite buttons
- Real-time status display
- Volume slider interface
- Always-accessible radio controls

**Usage:**
1. Create a small prim for HUD
2. Add the `hud_interface.lsl` script
3. Attach to HUD position
4. Configure and enjoy hands-free control

#### 3. Radio Object (`radio_object.lsl`)
**Purpose**: In-world interactive radio with visual feedback
**Features:**
- Animated radio object
- Visual status indicators (colors, particles)
- Sound management
- Multiple user access
- Station preset management

**Usage:**
1. Create detailed radio prim/mesh
2. Add the `radio_object.lsl` script
3. Configure animations and sounds
4. Place in public area for shared use

#### 4. Status Display (`status_display.lsl`)
**Purpose**: Real-time status board for venues
**Features:**
- Large text display
- Now playing information
- Station name and metadata
- Automatic updates via WebSocket
- Custom styling options

**Usage:**
1. Create large display prim
2. Add the `status_display.lsl` script
3. Position for public viewing
4. Configure display format and refresh rate

### ⚙️ **Configuration & Setup**

#### Server Configuration
```bash
# Enable SL Bridge in environment
SL_BRIDGE_ENABLED=true
SL_BRIDGE_HOST=0.0.0.0
SL_BRIDGE_PORT=8000

# Security settings
JWT_SECRET_KEY=your_secret_key_here
JWT_EXPIRY_HOURS=24

# Rate limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

#### LSL Script Configuration
```lsl
// Configure these variables in each script:
string SERVER_URL = "http://your-server.com";
string API_KEY = "your_api_key";
integer GUILD_ID = 123456789;
float UPDATE_INTERVAL = 30.0; // seconds
```

### 🔄 **Real-Time Synchronization**

#### WebSocket Events
BunBot broadcasts real-time events to all connected SL objects:
- **stream_started**: When playback begins
- **stream_stopped**: When playback ends
- **stream_changed**: When station changes
- **volume_changed**: When volume adjusts
- **favorite_added**: When favorites are modified

#### Live Status Updates
All LSL objects automatically receive:
- Current song information
- Stream status changes
- Volume level updates
- Error notifications
- Server health status

### 🎯 **Usage Examples**

#### Playing a Stream from SL
```lsl
// LSL code to start a stream
string json_data = "{\"url\":\"http://stream.radioparadise.com/rp_192m.ogg\",\"guild_id\":" + (string)GUILD_ID + "}";

llHTTPRequest(SERVER_URL + "/api/v1/streams/play",
    [HTTP_METHOD, "POST",
     HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token,
     HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
     HTTP_BODY, json_data], "play_request");
```

#### Adding a Favorite Station
```lsl
// LSL code to add a favorite
string json_data = "{\"url\":\"http://example.com:8000\",\"name\":\"My Station\",\"guild_id\":" + (string)GUILD_ID + "}";

llHTTPRequest(SERVER_URL + "/api/v1/favorites",
    [HTTP_METHOD, "POST",
     HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token,
     HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
     HTTP_BODY, json_data], "add_favorite");
```

#### Volume Control
```lsl
// LSL code to set volume
string json_data = "{\"volume\":0.75,\"guild_id\":" + (string)GUILD_ID + "}";

llHTTPRequest(SERVER_URL + "/api/v1/audio/volume",
    [HTTP_METHOD, "POST",
     HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token,
     HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
     HTTP_BODY, json_data], "set_volume");
```

### 📊 **API Response Format**

All API responses follow a consistent format optimized for LSL parsing:

```json
{
  "success": true,
  "message": "Stream started successfully",
  "data": {
    "guild_id": 123456789,
    "status": "playing",
    "url": "http://stream.example.com",
    "station": "Example Radio",
    "song": "Artist - Song Title"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### 🔧 **Troubleshooting SL Integration**

#### Common Issues

**Authentication Failures:**
- Verify API key is correct in LSL script
- Check JWT token hasn't expired (24-hour default)
- Ensure guild_id matches your Discord server

**Connection Issues:**
- Verify SL Bridge server is running (`SL_BRIDGE_ENABLED=true`)
- Check firewall allows port 8000 (or your configured port)
- Test API endpoints with curl or Postman

**LSL Script Errors:**
- Check script console for HTTP error codes
- Verify JSON format in requests
- Ensure all required headers are included

**Rate Limiting:**
- Default limit is 100 requests per minute
- Space out requests appropriately
- Use WebSocket events for real-time updates instead of polling

#### Debug Mode
Enable debug logging in LSL scripts:
```lsl
integer DEBUG = TRUE; // Set to TRUE for detailed logging
```

This will output detailed information about all HTTP requests and responses to help diagnose issues.

---

## Features

### Auto-Quality Adaptation
- **Feature:** Automatic quality adjustment based on system performance
- **Benefit:** Prevents audio dropouts during high CPU usage
- **Levels:** Low → Medium → High → Ultra
- **Monitoring:** Continuous performance tracking

### Audio Processing Pipeline
1. **Input:** Stream audio data
2. **Normalization:** Volume level standardization (-23 LUFS target)
3. **Auto Gain Control:** Dynamic volume adjustment
4. **EQ Processing:** 3-band equalization
5. **Compression:** Dynamic range optimization
6. **Output:** Enhanced audio to Discord

### Health Monitoring
- **Guild Health Checks:** Stream connectivity, voice client status
- **System Monitoring:** CPU, memory, performance metrics
- **Auto-Recovery:** Automatic issue detection and resolution
- **Performance Alerts:** Proactive issue notification

---

## Utility Commands

### `/support`
**Description:** Get help and support information
- **Usage:** `/support`
- **Shows:** 
  - Support channels
  - Documentation links
  - Bug reporting info
  - Feature request process

### `/debug [page] [per_page] [id]`
**Description:** Show debug information and statistics
- **Usage:** `/debug` or `/debug page:2 per_page:5`
- **Features:**
  - Guild statistics
  - Stream status
  - Performance metrics
  - Shard information
- **Permissions:** Bot owner access for detailed info
- **Cooldown:** 5 seconds

---

## Deployment

BunBot supports multiple deployment options for different use cases.

### 🐳 **Docker Deployment (Recommended)**

#### Docker Compose Setup
Create a `docker-compose.yml` file:

```yaml
version: '3.8'
services:
  bunbot:
    image: bunbot:latest
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - SL_BRIDGE_ENABLED=true
      - LOG_LEVEL=INFO
      - AUDIO_QUALITY=high
    ports:
      - "8000:8000"  # SL Bridge API
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Environment Configuration
Create a `.env` file:

```bash
# Required
BOT_TOKEN=your_discord_bot_token

# Optional Features
SL_BRIDGE_ENABLED=true
SL_BRIDGE_HOST=0.0.0.0
SL_BRIDGE_PORT=8000
JWT_SECRET_KEY=your_random_secret_key

# Audio Settings
AUDIO_QUALITY=high
SAMPLE_RATE=48000
NORMALIZATION_TARGET=-23.0

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=/app/logs

# Performance
CLUSTER_ID=0
TOTAL_CLUSTERS=1
TOTAL_SHARDS=1
```

#### Deployment Commands
```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f bunbot

# Update the bot
docker-compose pull
docker-compose up -d

# Stop the bot
docker-compose down
```

### 🚀 **Production Deployment**

#### Multi-Shard Configuration
For large Discord bots (2500+ guilds):

```yaml
version: '3.8'
services:
  bunbot-shard-0:
    image: bunbot:latest
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - CLUSTER_ID=0
      - TOTAL_CLUSTERS=2
      - TOTAL_SHARDS=4
      - SL_BRIDGE_ENABLED=true
    ports:
      - "8000:8000"
    
  bunbot-shard-1:
    image: bunbot:latest
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - CLUSTER_ID=1
      - TOTAL_CLUSTERS=2
      - TOTAL_SHARDS=4
      - SL_BRIDGE_ENABLED=false  # Only one instance needs SL Bridge
```

#### Load Balancer Configuration
```nginx
upstream bunbot_api {
    server bunbot-shard-0:8000 weight=1;
    server bunbot-shard-1:8001 weight=1;
}

server {
    listen 80;
    server_name api.your-domain.com;
    
    location /api/ {
        proxy_pass http://bunbot_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 📊 **Monitoring & Health Checks**

#### Health Check Endpoint
```bash
# Check bot health
curl http://localhost:8000/health

# Response:
{
  "status": "healthy",
  "timestamp": "2024-12-20T10:30:00Z",
  "services": {
    "discord": "connected",
    "audio": "ready",
    "database": "connected"
  }
}
```

#### Prometheus Metrics
Enable metrics collection:
```bash
# Environment variable
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Access metrics
curl http://localhost:9090/metrics
```

#### Log Monitoring
```bash
# View real-time logs
docker-compose logs -f bunbot

# Check for errors
docker-compose logs bunbot | grep ERROR

# Monitor specific services
docker-compose logs bunbot | grep "sl_bridge"
```

### 🔧 **Manual Installation**

#### System Requirements
- **Python**: 3.9 or higher
- **FFmpeg**: Required for audio processing
- **Memory**: 512MB minimum, 1GB recommended
- **Storage**: 100MB for application, additional for logs/data
- **Network**: Stable internet connection

#### Installation Steps
```bash
# Clone repository
git clone https://github.com/your-repo/bunbot
cd bunbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install FFmpeg (Ubuntu/Debian)
sudo apt update
sudo apt install ffmpeg

# Install FFmpeg (Windows)
# Download from https://ffmpeg.org/download.html
# Add to PATH environment variable

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Run the bot
python bot.py
```

#### Systemd Service (Linux)
Create `/etc/systemd/system/bunbot.service`:

```ini
[Unit]
Description=BunBot Discord Radio Bot
After=network.target

[Service]
Type=simple
User=bunbot
WorkingDirectory=/opt/bunbot
Environment=PATH=/opt/bunbot/venv/bin
ExecStart=/opt/bunbot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable bunbot
sudo systemctl start bunbot

# Check status
sudo systemctl status bunbot

# View logs
sudo journalctl -u bunbot -f
```

### 🛡️ **Security Configuration**

#### Firewall Settings
```bash
# Allow SL Bridge API port
sudo ufw allow 8000

# Allow only specific IPs (optional)
sudo ufw allow from 192.168.1.0/24 to any port 8000
```

#### SSL/TLS Setup (Nginx)
```nginx
server {
    listen 443 ssl;
    server_name api.your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Environment Security
```bash
# Secure environment file
chmod 600 .env
chown bunbot:bunbot .env

# Use strong JWT secret
JWT_SECRET_KEY=$(openssl rand -base64 32)

# Limit API access
SL_BRIDGE_HOST=127.0.0.1  # Local only
# or specific network
SL_BRIDGE_HOST=192.168.1.100
```

### 📈 **Performance Tuning**

#### Resource Limits
```yaml
# Docker Compose with resource limits
services:
  bunbot:
    image: bunbot:latest
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

#### Audio Quality Settings
```bash
# High performance
AUDIO_QUALITY=ultra
SAMPLE_RATE=48000
CHANNELS=2

# Balanced
AUDIO_QUALITY=high
SAMPLE_RATE=44100
CHANNELS=2

# Low resource usage
AUDIO_QUALITY=medium
SAMPLE_RATE=22050
CHANNELS=1
```

#### Database Optimization
```bash
# SQLite optimization
SQLITE_CACHE_SIZE=10000
SQLITE_SYNCHRONOUS=NORMAL
SQLITE_JOURNAL_MODE=WAL
```

### 🔄 **Backup & Recovery**

#### Data Backup
```bash
# Backup favorites database
cp data/bunbot.db backups/bunbot-$(date +%Y%m%d).db

# Backup configuration
cp .env backups/.env-$(date +%Y%m%d)

# Automated backup script
#!/bin/bash
DATE=$(date +%Y%m%d-%H%M%S)
tar -czf backups/bunbot-backup-$DATE.tar.gz data/ .env logs/
```

#### Disaster Recovery
```bash
# Restore from backup
tar -xzf backups/bunbot-backup-20241220.tar.gz

# Restore database only
cp backups/bunbot-20241220.db data/bunbot.db

# Restart services
docker-compose restart bunbot
```

---

## Troubleshooting

### Common Issues

#### Bot Won't Join Voice Channel
- **Check:** Bot has "Connect" and "Speak" permissions
- **Solution:** Ensure proper role permissions in voice channel

#### No Audio Playing
- **Check:** Stream URL is valid and accessible
- **Solution:** Try `/refresh` or use a different stream URL
- **Note:** Some streams may have geographic restrictions

#### Audio Quality Issues
- **Check:** Current `/audio-info` settings
- **Solution:** Adjust `/volume` or try different `/eq` settings
- **Advanced:** System may auto-adjust quality based on performance

#### Bot Stuck in Voice Channel
- **Solution:** Use `/leave force:True` to force disconnect
- **Note:** This clears any stale state and allows fresh connections

#### Favorites Not Working
- **Check:** Use `/list-favorites` to verify favorites exist
- **Solution:** Re-add favorites if list is empty
- **Note:** Favorites are server-specific

### Error Recovery

BunBot includes automatic error recovery for:
- **Stream Disconnections:** Auto-reconnection attempts
- **Voice Client Issues:** Automatic voice client restoration
- **State Desynchronization:** Smart state recovery
- **Performance Issues:** Dynamic quality adjustment

### Getting Help

1. **In-Discord:** Use `/support` command
2. **Documentation:** Check this user guide
3. **Issues:** Report bugs through support channels
4. **Features:** Request new features through proper channels

---

## Performance Tips

### For Best Audio Quality
1. Use high-quality stream URLs (256kbps+ recommended)
2. Adjust EQ settings for your content type
3. Keep volume at reasonable levels (70-85%)
4. Monitor system performance with `/debug`

### For Stable Performance
1. Ensure stable internet connection
2. Use servers with adequate resources
3. Monitor bot performance regularly
4. Keep favorites list manageable (<50 stations)

### For Server Management
1. Set up dedicated bot role with minimal permissions
2. Create dedicated music/radio channel
3. Educate users on proper command usage
4. Regular maintenance and monitoring

---

## Feature Roadmap

Upcoming features in development:
- Playlist support
- Scheduled streaming
- Advanced audio effects
- Multi-guild synchronization
- Enhanced web dashboard
- Custom stream metadata
- Advanced user permissions

---

*Last Updated: December 2024*
*Version: 2.0.0 - Service Architecture Update*

For the most current information, use the `/support` command in Discord.
