# Bunbot - Simple Shoutcast Discord Bot!
Bunbot! was originally a javascript-based bot, but has been rewritten in Python!

It's designed to play Shoutcast and some Icecast streams. It supports the following commands:
- `/play`: Start playing the stream.
- `/leave`: Leave the voice channel.
- `/refresh`: Refresh the stream list.
- `/song`: Display the current song playing.
- `/support`: Learn where you can get help with the bot or how to help.

# Don't want to self-host?
No problem!
you can add the bot to your discord here! [click me!](https://discord.com/oauth2/authorize?client_id=1385627473324019793&permissions=1168649901399936&scope=bot%20applications.commands)

EPIC translation done by: [CGillen](https://github.com/CGillen)!

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/J3J61BNDZO)

# So what's new?
- `Implemented Shoutcast v1! 🎉`
- `Support embed added!🎉`
- `Added some checks for permissions or lack thereof`
- `Added better handling for ~slower~ servers`
- `Added some damage control if Discord were to drop the connection suddenly`
- `Handles things better if the listening server were to crash suddenly`
- `Volume normalization`
- `More robust-er-er error handling`
- `Slash commands`
- `Better streamscrobbler for that sweet sweet metadata!`
- `Changed audio receiver library to Discord integrated`
- `Migrated to Python!`
- `Hac-I mean added ICY support into urllib.py`
- `Advanced 3-band equalizer with 9 built-in presets! 🎵`
- `Real-time audio enhancement with auto-gain control and compression! 🔊`
- `Interactive favorites system with clickable browser and pagination! ⭐`
- `Complete Second Life integration with 24 REST API endpoints! 🌐`
- `4 ready-to-use LSL scripts for in-world radio control! 📜`
- `JWT authentication and role-based permissions! 🔐`
- `Service-oriented architecture with dependency injection! 🏗️`
- `Production-ready Docker deployment with health monitoring! 🐳`
- `Auto-recovery and intelligent state management! 🔄`
- `Performance monitoring with real-time metrics and alerting! 📊`
- `Interactive Discord UI with button-based controls! 📱`
- `Mobile-optimized responsive design for all Discord clients! 📲`
- `Multi-shard clustering support for large Discord bots! ⚡`
- `Adaptive quality adjustment based on system performance! 🎯`
- `Cross-platform synchronization system! 🔗`
- `Enterprise-grade error handling and logging! 📝`
- `WebSocket events for real-time status updates! 🔄`
- `Professional audio processing pipeline with FFmpeg! 🎚️`
- `Comprehensive user guide and API documentation! 📚`
- `Automated backup and disaster recovery systems! 💾`
- `SSL/TLS support for secure API communications! 🛡️`
- `Prometheus metrics and Grafana dashboard integration! 📈`
- `Rate limiting and API abuse prevention! 🚦`
- `Guild-specific settings and permissions management! 👥`
- `Stream validation and metadata extraction! ✅`
- `Custom EQ presets for different music genres! 🎼`
- `Volume control with smooth transitions and persistence! 🔉`
- `Rich embeds with professional visual presentation! 🎨`
- `Command cooldowns and permission checks! ⏱️`
- `Debug mode with detailed system information! 🔍`
- `Force disconnect for handling stuck voice clients! 💪`
- `Automatic stream reconnection and error recovery! 🔧`
- `6 Bugs Squashed! 🎉`

# Advanced Features

## 🎧 Audio Enhancement
- **3-Band Equalizer**: Bass/Mid/Treble control with `/eq` command
- **EQ Presets**: 9 built-in presets (rock, pop, classical, bass-boost, etc.)
- **Volume Control**: Master volume with `/volume` command
- **Audio Processing**: Real-time normalization, auto-gain, and compression
- **Quality Adaptation**: Automatic performance-based quality adjustment

## ⭐ Favorites System
- **Add Favorites**: `/set-favorite` with custom naming
- **Interactive Browser**: `/favorites` with clickable play buttons
- **Quick Play**: `/play-favorite` by number
- **Management**: `/remove-favorite` with confirmation
- **Mobile-Friendly**: `/list-favorites` for simple text display

## 🌐 Second Life Integration
- **24 REST API Endpoints**: Complete remote control from virtual worlds
- **4 LSL Scripts**: Basic controller, HUD interface, radio object, status display
- **JWT Authentication**: Secure token-based access
- **Real-Time Sync**: WebSocket events for live updates
- **Touch Controls**: In-world radio objects and HUD interfaces

## 📱 Interactive UI
- **Button Controls**: Click-to-play favorites and quick actions
- **Rich Embeds**: Professional visual presentation
- **Real-Time Updates**: Live status and song information
- **Mobile Optimized**: Responsive design for all Discord clients

## 🏗️ Enterprise Architecture
- **Service Registry**: Dependency injection container
- **State Management**: Centralized guild state handling
- **Event Bus**: Inter-service communication
- **Error Recovery**: Intelligent auto-recovery mechanisms
- **Health Monitoring**: Real-time system health checks

## 🐳 Production Deployment
- **Docker Support**: Production-ready containerization
- **Multi-Shard**: Horizontal scaling for large bots
- **Load Balancing**: Automatic distribution across shards
- **Health Checks**: Built-in monitoring and alerting
- **SSL/TLS**: Secure API communications

# Quick Setup

## Docker (Recommended)
```bash
# Clone and setup
git clone https://github.com/CGillen/BunBotPython
cd BunBotPython

# Configure environment
cp .env.example .env
# Edit .env with your bot token

# Run with Docker
docker-compose up -d
```

## Manual Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
export BOT_TOKEN="your_discord_bot_token"

# Run the bot
python bot.py
```

# Commands Reference

## Core Commands
- `/play <url>` - Start playing a stream
- `/leave [force]` - Stop and leave voice channel
- `/song` - Show current song info
- `/refresh` - Refresh the stream connection

## Favorites
- `/set-favorite <url> [name]` - Add station to favorites
- `/play-favorite <number>` - Play favorite by number
- `/favorites` - Interactive favorites browser
- `/list-favorites` - Simple text list
- `/remove-favorite <number>` - Remove a favorite

## Audio Enhancement
- `/volume <0-100>` - Set master volume
- `/eq <bass> <mid> <treble>` - Adjust equalizer (-12 to +12 dB)
- `/eq-preset <preset>` - Apply EQ preset
- `/audio-info` - Show current audio settings

## Utility
- `/support` - Get help and support info
- `/debug` - Show system information

# Second Life API

## Stream Control
- `POST /api/v1/streams/play` - Start playback
- `POST /api/v1/streams/stop` - Stop playback
- `GET /api/v1/streams/status` - Get status
- `POST /api/v1/streams/refresh` - Refresh connection

## Audio Control
- `POST /api/v1/audio/volume` - Set volume
- `POST /api/v1/audio/eq` - Adjust equalizer
- `POST /api/v1/audio/preset` - Apply EQ preset
- `GET /api/v1/audio/info` - Get audio settings

## Favorites Management
- `GET /api/v1/favorites` - List favorites
- `POST /api/v1/favorites` - Add favorite
- `DELETE /api/v1/favorites/{id}` - Remove favorite
- `POST /api/v1/favorites/{id}/play` - Play favorite

# LSL Scripts Included
- **basic_controller.lsl** - Touch-based radio control
- **hud_interface.lsl** - Wearable control panel
- **radio_object.lsl** - In-world clickable radio
- **status_display.lsl** - Real-time status board

# Support & Documentation
- Use `/support` command in Discord
- Complete User Guide: [docs/user_guides/COMPLETE_USER_GUIDE.md](docs/user_guides/COMPLETE_USER_GUIDE.md)
- API Documentation: [docs/api/BUN_BRIDGE_API.md](docs/api/BUN_BRIDGE_API.md)
- Issues: [GitHub Issues](https://github.com/CGillen/BunBotPython/issues)

# Contributing
- Development Guide: [DEVELOPMENT.md](docs/development/DEVELOPMENT.md)
- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Architecture: [ARCHITECTURE.md](docs/development/ARCHITECTURE.md)
