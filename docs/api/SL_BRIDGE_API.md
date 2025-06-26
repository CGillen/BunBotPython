# BunBot Second Life Bridge API Reference

Complete API documentation for BunBot's Second Life integration REST API server.

## Overview

The SL Bridge API provides 24 REST endpoints across 5 categories for complete remote control of BunBot from Second Life and other external applications.

**Base URL**: `http://your-server.com/api/v1`  
**Authentication**: JWT Bearer Token  
**Content-Type**: `application/json`  
**Rate Limit**: 100 requests per minute (configurable)

---

## Authentication

### Get Access Token

**Endpoint**: `POST /auth/token`  
**Description**: Obtain JWT access token for API authentication

#### Request
```json
{
  "api_key": "your_development_key",
  "guild_id": 123456789,
  "avatar_name": "SecondLife Resident" // Optional
}
```

#### Response
```json
{
  "success": true,
  "message": "Token generated successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 86400,
    "guild_id": 123456789,
    "permissions": ["stream_control", "audio_control", "favorites_read"]
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

#### Error Responses
- `400 Bad Request`: Invalid API key or guild ID
- `403 Forbidden`: Access denied to specified guild
- `429 Too Many Requests`: Rate limit exceeded

---

## Stream Control API

### Play Stream

**Endpoint**: `POST /streams/play`  
**Permission**: `stream_control`

#### Request
```json
{
  "url": "http://stream.radioparadise.com/rp_192m.ogg",
  "guild_id": 123456789,
  "channel_id": 987654321 // Optional voice channel ID
}
```

#### Response
```json
{
  "success": true,
  "message": "Stream started successfully",
  "data": {
    "guild_id": 123456789,
    "status": "playing",
    "url": "http://stream.radioparadise.com/rp_192m.ogg",
    "station": "Radio Paradise",
    "started_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Stop Stream

**Endpoint**: `POST /streams/stop`  
**Permission**: `stream_control`

#### Request
```json
{
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "Stream stopped successfully",
  "data": {
    "guild_id": 123456789,
    "status": "stopped",
    "stopped_at": "2024-12-20T10:35:00Z"
  },
  "timestamp": "2024-12-20T10:35:00Z"
}
```

### Get Stream Status

**Endpoint**: `GET /streams/status?guild_id=123456789`  
**Permission**: `stream_status`

#### Response
```json
{
  "success": true,
  "message": "Status retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "is_playing": true,
    "stream_url": "http://stream.radioparadise.com/rp_192m.ogg",
    "station_name": "Radio Paradise",
    "current_song": "Artist Name - Song Title",
    "volume": 0.75,
    "started_at": "2024-12-20T10:30:00Z",
    "duration": 300
  },
  "timestamp": "2024-12-20T10:35:00Z"
}
```

### Refresh Stream

**Endpoint**: `POST /streams/refresh`  
**Permission**: `stream_control`

#### Request
```json
{
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "Stream refreshed successfully",
  "data": {
    "guild_id": 123456789,
    "status": "refreshed",
    "refreshed_at": "2024-12-20T10:35:00Z"
  },
  "timestamp": "2024-12-20T10:35:00Z"
}
```

### Get Stream History

**Endpoint**: `GET /streams/history?guild_id=123456789&limit=10`  
**Permission**: `stream_status`

#### Response
```json
{
  "success": true,
  "message": "History retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "history": [
      {
        "url": "http://stream.example.com",
        "name": "Example Radio",
        "time": "2024-12-20T10:30:00"
      }
    ]
  },
  "timestamp": "2024-12-20T10:35:00Z"
}
```

---

## Audio Control API

### Set Volume

**Endpoint**: `POST /audio/volume`  
**Permission**: `audio_control`

#### Request
```json
{
  "volume": 0.75,
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "Volume set successfully",
  "data": {
    "guild_id": 123456789,
    "volume": 0.75,
    "volume_percent": 75
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Adjust Equalizer

**Endpoint**: `POST /audio/eq`  
**Permission**: `audio_control`

#### Request
```json
{
  "bass": 2.0,
  "mid": -1.0,
  "treble": 3.5,
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "Equalizer updated successfully",
  "data": {
    "guild_id": 123456789,
    "eq_settings": {
      "bass": 2.0,
      "mid": -1.0,
      "treble": 3.5
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Apply EQ Preset

**Endpoint**: `POST /audio/preset`  
**Permission**: `audio_control`

#### Request
```json
{
  "preset": "rock",
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "EQ preset applied successfully",
  "data": {
    "guild_id": 123456789,
    "preset": "rock",
    "eq_settings": {
      "bass": 4.0,
      "mid": 0.0,
      "treble": 2.0
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Get Audio Info

**Endpoint**: `GET /audio/info?guild_id=123456789`  
**Permission**: `audio_status`

#### Response
```json
{
  "success": true,
  "message": "Audio info retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "volume": 0.75,
    "eq_settings": {
      "bass": 2.0,
      "mid": -1.0,
      "treble": 3.5
    },
    "quality": "high",
    "sample_rate": 48000,
    "channels": 2,
    "processing": {
      "normalization": true,
      "auto_gain": true,
      "compression": 0.3
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

---

## Favorites Management API

### List Favorites

**Endpoint**: `GET /favorites?guild_id=123456789`  
**Permission**: `favorites_read`

#### Response
```json
{
  "success": true,
  "message": "Favorites retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "favorites": [
      {
        "id": 1,
        "number": 1,
        "name": "Radio Paradise",
        "url": "http://stream.radioparadise.com/rp_192m.ogg",
        "added_by": "User#1234",
        "added_at": "2024-12-20T10:00:00Z"
      }
    ],
    "total": 1
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Add Favorite

**Endpoint**: `POST /favorites`  
**Permission**: `favorites_write`

#### Request
```json
{
  "url": "http://stream.example.com:8000",
  "name": "Example Radio Station",
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "Favorite added successfully",
  "data": {
    "id": 2,
    "number": 2,
    "name": "Example Radio Station",
    "url": "http://stream.example.com:8000",
    "guild_id": 123456789,
    "added_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Update Favorite

**Endpoint**: `PUT /favorites/{id}`  
**Permission**: `favorites_write`

#### Request
```json
{
  "name": "Updated Station Name",
  "url": "http://new-stream.example.com:8000",
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "Favorite updated successfully",
  "data": {
    "id": 2,
    "number": 2,
    "name": "Updated Station Name",
    "url": "http://new-stream.example.com:8000",
    "updated_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Remove Favorite

**Endpoint**: `DELETE /favorites/{id}?guild_id=123456789`  
**Permission**: `favorites_write`

#### Response
```json
{
  "success": true,
  "message": "Favorite removed successfully",
  "data": {
    "id": 2,
    "removed_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Play Favorite

**Endpoint**: `POST /favorites/{id}/play`  
**Permission**: `stream_control`

#### Request
```json
{
  "guild_id": 123456789
}
```

#### Response
```json
{
  "success": true,
  "message": "Favorite playing successfully",
  "data": {
    "favorite_id": 1,
    "favorite_name": "Radio Paradise",
    "guild_id": 123456789,
    "status": "playing",
    "started_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

---

## Status & Monitoring API

### Health Check

**Endpoint**: `GET /status/health`  
**Permission**: None (public)

#### Response
```json
{
  "success": true,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "services": {
      "discord": "connected",
      "audio": "ready",
      "database": "connected",
      "api": "running"
    },
    "uptime": 86400
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Server Information

**Endpoint**: `GET /status/info`  
**Permission**: `server_info`

#### Response
```json
{
  "success": true,
  "message": "Server info retrieved successfully",
  "data": {
    "version": "2.0.0",
    "bot_name": "BunBot",
    "features": {
      "audio_enhancement": true,
      "favorites": true,
      "sl_integration": true,
      "monitoring": true
    },
    "limits": {
      "max_favorites": 50,
      "rate_limit": 100,
      "max_guilds": 1000
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Usage Statistics

**Endpoint**: `GET /status/stats?guild_id=123456789`  
**Permission**: `stats_read`

#### Response
```json
{
  "success": true,
  "message": "Statistics retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "stats": {
      "total_streams": 150,
      "total_playtime": 36000,
      "favorite_count": 12,
      "most_played": "Radio Paradise",
      "last_activity": "2024-12-20T10:00:00Z"
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Guild Information

**Endpoint**: `GET /status/guilds/{guild_id}`  
**Permission**: `admin`

#### Response
```json
{
  "success": true,
  "message": "Guild info retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "guild_name": "Example Discord Server",
    "member_count": 150,
    "voice_channels": 5,
    "current_activity": {
      "is_streaming": true,
      "stream_url": "http://stream.example.com",
      "listeners": 8
    },
    "configuration": {
      "volume": 0.75,
      "auto_disconnect": true,
      "max_favorites": 50
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Performance Metrics

**Endpoint**: `GET /status/performance`  
**Permission**: `admin`

#### Response
```json
{
  "success": true,
  "message": "Performance metrics retrieved successfully",
  "data": {
    "system": {
      "cpu_usage": 15.2,
      "memory_usage": 245,
      "memory_total": 1024,
      "uptime": 86400
    },
    "audio": {
      "quality_level": "high",
      "processing_latency": 45,
      "active_streams": 3,
      "total_processed": 150000
    },
    "api": {
      "requests_per_minute": 25,
      "active_connections": 12,
      "response_time_avg": 120
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

---

## Settings & Configuration API

### Get Configuration

**Endpoint**: `GET /settings/config?guild_id=123456789`  
**Permission**: `config_read`

#### Response
```json
{
  "success": true,
  "message": "Configuration retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "settings": {
      "auto_disconnect_timeout": 300,
      "default_volume": 0.8,
      "max_favorites": 50,
      "eq_presets_enabled": true,
      "notifications_enabled": true,
      "auto_quality_adjustment": true
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Update Configuration

**Endpoint**: `PUT /settings/config`  
**Permission**: `config_write`

#### Request
```json
{
  "guild_id": 123456789,
  "settings": {
    "auto_disconnect_timeout": 600,
    "default_volume": 0.7,
    "max_favorites": 25
  }
}
```

#### Response
```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "data": {
    "guild_id": 123456789,
    "updated_settings": {
      "auto_disconnect_timeout": 600,
      "default_volume": 0.7,
      "max_favorites": 25
    },
    "updated_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Get Permissions

**Endpoint**: `GET /settings/permissions?guild_id=123456789`  
**Permission**: `permissions_read`

#### Response
```json
{
  "success": true,
  "message": "Permissions retrieved successfully",
  "data": {
    "guild_id": 123456789,
    "permissions": {
      "stream_control": ["admin", "moderator", "dj"],
      "audio_control": ["admin", "moderator", "dj"],
      "favorites_write": ["admin", "moderator", "member"],
      "favorites_read": ["admin", "moderator", "member", "guest"],
      "config_write": ["admin"],
      "config_read": ["admin", "moderator"]
    }
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Update Permissions

**Endpoint**: `PUT /settings/permissions`  
**Permission**: `admin`

#### Request
```json
{
  "guild_id": 123456789,
  "permissions": {
    "stream_control": ["admin", "moderator"],
    "audio_control": ["admin", "moderator", "dj"]
  }
}
```

#### Response
```json
{
  "success": true,
  "message": "Permissions updated successfully",
  "data": {
    "guild_id": 123456789,
    "updated_permissions": {
      "stream_control": ["admin", "moderator"],
      "audio_control": ["admin", "moderator", "dj"]
    },
    "updated_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Reset to Defaults

**Endpoint**: `POST /settings/reset`  
**Permission**: `admin`

#### Request
```json
{
  "guild_id": 123456789,
  "reset_type": "all" // Options: "all", "settings", "permissions"
}
```

#### Response
```json
{
  "success": true,
  "message": "Settings reset to defaults successfully",
  "data": {
    "guild_id": 123456789,
    "reset_type": "all",
    "reset_at": "2024-12-20T10:30:00Z"
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

---

## Error Responses

### Standard Error Format

All error responses follow this format:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human readable error message",
  "details": {
    "field": "Additional error details",
    "code": 400
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

### Common Error Codes

| HTTP Code | Error Code | Description |
|-----------|------------|-------------|
| 400 | `BAD_REQUEST` | Invalid request data |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource conflict |
| 422 | `VALIDATION_ERROR` | Request validation failed |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

### API-Specific Error Codes

| Error Code | Description |
|------------|-------------|
| `STREAM_FAILED` | Failed to start/stop stream |
| `INVALID_URL` | Invalid stream URL format |
| `NO_VOICE_CLIENT` | Bot not connected to voice |
| `GUILD_NOT_FOUND` | Discord guild not found |
| `PERMISSION_DENIED` | Insufficient API permissions |
| `FAVORITE_EXISTS` | Favorite already exists |
| `FAVORITE_NOT_FOUND` | Favorite not found |
| `AUDIO_ERROR` | Audio processing error |
| `CONFIG_ERROR` | Configuration error |

---

## Rate Limiting

### Default Limits

- **Global**: 100 requests per minute per API key
- **Per Guild**: 50 requests per minute per guild
- **Authentication**: 10 token requests per minute per IP

### Rate Limit Headers

Response headers include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
X-RateLimit-Window: 60
```

### Rate Limit Response

When rate limit is exceeded:

```json
{
  "success": false,
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Try again in 30 seconds.",
  "details": {
    "limit": 100,
    "window": 60,
    "retry_after": 30
  },
  "timestamp": "2024-12-20T10:30:00Z"
}
```

---

## WebSocket Events

### Connection

**URL**: `ws://your-server.com/ws/{guild_id}`  
**Authentication**: JWT token as query parameter

```
ws://your-server.com/ws/123456789?token=eyJhbGciOiJIUzI1NiIs...
```

### Event Format

All WebSocket events follow this format:

```json
{
  "event": "stream_started",
  "guild_id": 123456789,
  "timestamp": "2024-12-20T10:30:00Z",
  "data": {
    "url": "http://stream.example.com",
    "station": "Example Radio",
    "user": "SL User"
  }
}
```

### Available Events

| Event | Description | Data |
|-------|-------------|------|
| `stream_started` | Stream playback began | `{url, station, user}` |
| `stream_stopped` | Stream playback ended | `{user, reason}` |
| `stream_changed` | Stream URL changed | `{old_url, new_url, station}` |
| `volume_changed` | Volume level changed | `{volume, user}` |
| `eq_changed` | Equalizer settings changed | `{bass, mid, treble, user}` |
| `favorite_added` | New favorite added | `{id, name, url, user}` |
| `favorite_removed` | Favorite deleted | `{id, name, user}` |
| `error_occurred` | Error event | `{error_code, message}` |
| `status_update` | General status update | `{status, details}` |

---

## LSL Integration Examples

### Basic Stream Control

```lsl
// Configuration
string SERVER_URL = "http://your-server.com/api/v1";
string API_KEY = "your_api_key";
integer GUILD_ID = 123456789;
string auth_token = "";

// Get authentication token
authenticate() {
    string json_data = "{\"api_key\":\"" + API_KEY + "\",\"guild_id\":" + (string)GUILD_ID + "}";
    
    llHTTPRequest(SERVER_URL + "/auth/token",
        [HTTP_METHOD, "POST",
         HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
         HTTP_BODY, json_data], "auth_request");
}

// Play a stream
play_stream(string url) {
    string json_data = "{\"url\":\"" + url + "\",\"guild_id\":" + (string)GUILD_ID + "}";
    
    llHTTPRequest(SERVER_URL + "/streams/play",
        [HTTP_METHOD, "POST",
         HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token,
         HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
         HTTP_BODY, json_data], "play_request");
}

// Stop stream
stop_stream() {
    string json_data = "{\"guild_id\":" + (string)GUILD_ID + "}";
    
    llHTTPRequest(SERVER_URL + "/streams/stop",
        [HTTP_METHOD, "POST",
         HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token,
         HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
         HTTP_BODY, json_data], "stop_request");
}

// HTTP Response handler
http_response(key request_id, integer status, list metadata, string body) {
    if (status == 200) {
        // Parse JSON response and handle success
        llOwnerSay("API call successful: " + body);
    } else {
        // Handle error
        llOwnerSay("API error " + (string)status + ": " + body);
    }
}
```

### Advanced Favorites Management

```lsl
// Get all favorites
get_favorites() {
    llHTTPRequest(SERVER_URL + "/favorites?guild_id=" + (string)GUILD_ID,
        [HTTP_METHOD, "GET",
         HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token], "favorites_request");
}

// Add favorite with validation
add_favorite(string url, string name) {
    string json_data = "{\"url\":\"" + url + "\",\"name\":\"" + name + "\",\"guild_id\":" + (string)GUILD_ID + "}";
    
    llHTTPRequest(SERVER_URL + "/favorites",
        [HTTP_METHOD, "POST",
         HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token,
         HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
         HTTP_BODY, json_data], "add_favorite_request");
}

// Play favorite by ID
play_favorite(integer favorite_id) {
    string json_data = "{\"guild_id\":" + (string)GUILD_ID + "}";
    
    llHTTPRequest(SERVER_URL + "/favorites/" + (string)favorite_id + "/play",
        [HTTP_METHOD, "POST",
         HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + auth_token,
         HTTP_CUSTOM_HEADER, "Content-Type", "application/json",
         HTTP_BODY, json_data], "play_favorite_request");
}
```

---

## Security Best Practices

### API Key Management

1. **Use Environment Variables**: Store API keys securely
2. **Rotate Keys Regularly**: Change API keys periodically
3. **Limit Key Scope**: Use guild-specific keys when possible
4. **Monitor Usage**: Track API key usage for anomalies

### JWT Token Security

1. **Short Expiry**: Use 24-hour token expiry (default)
2. **Secure Storage**: Store tokens securely in LSL scripts
3. **Automatic Refresh**: Implement token refresh logic
4. **Validate Permissions**: Check token permissions before use

### Network Security

1. **HTTPS Only**: Use SSL/TLS for all API communications
2. **Firewall Rules**: Restrict API access to known IPs
3. **Rate Limiting**: Implement request rate limiting
4. **Input Validation**: Validate all input parameters

### LSL Script Security

1. **Owner Access**: Limit script access to object owner
2. **Permission Checks**: Validate user permissions
3. **Error Handling**: Implement comprehensive error handling
4. **Debug Mode**: Use debug mode only for development

---

## SDK & Libraries

### Official LSL Library

BunBot provides an official LSL library for easy integration:

```lsl
#include "bunbot_api.lsl"

// Initialize with your configuration
bunbot_init("http://your-server.com", "your_api_key", 123456789);

// Simple stream control
bunbot_play("http://stream.example.com");
bunbot_stop();
bunbot_volume(75);

// Favorites management
bunbot_add_favorite("http://stream.com", "My Station");
bunbot_play_favorite(1);
```

### Community SDKs

- **Python SDK**: `pip install bunbot-api`
- **JavaScript SDK**: `npm install bunbot-client`
- **PHP SDK**: `composer require bunbot/api-client`

---
