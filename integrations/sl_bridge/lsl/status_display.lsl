//
// BunBot Status Display Script
// Real-time "Now Playing" display board for Second Life
//
// Place this script in a display object to show current bot status
// Configure the settings below before use
//

// ===========================================
// CONFIGURATION - EDIT THESE SETTINGS
// ===========================================

// Your BunBot server configuration
string BOT_API_URL = "http://your-BunBot-server.com:8080/api/v1";
string API_KEY = "dev_key_123";  // Replace with your actual API key
integer GUILD_ID = 123456789;    // Replace with your Discord guild ID

// Display configuration
string DISPLAY_TITLE = "🎵 BunBot Status 🎵";
vector ACTIVE_COLOR = <0.0, 1.0, 0.5>;  // Green when playing
vector IDLE_COLOR = <0.5, 0.5, 1.0>;    // Blue when idle
vector ERROR_COLOR = <1.0, 0.0, 0.0>;   // Red when error

// Display settings
integer MAX_SONG_LENGTH = 40;       // Maximum characters for song title
integer MAX_STATION_LENGTH = 30;    // Maximum characters for station name
float TEXT_ALPHA = 1.0;             // Text transparency (0.0 to 1.0)
vector TEXT_COLOR = <1,1,1>;        // Text color (white)

// Update intervals
float STATUS_UPDATE_INTERVAL = 10.0;  // Check status every 10 seconds
float DISPLAY_REFRESH_INTERVAL = 2.0; // Refresh display every 2 seconds

// Display modes
integer DISPLAY_MODE = 0;  // 0=Full, 1=Compact, 2=Song Only, 3=Minimal

// ===========================================
// SCRIPT VARIABLES
// ===========================================

string jwt_token = "";
integer token_expires = 0;

// Current status data
integer is_playing = FALSE;
string current_song = "No Song Playing";
string current_station = "Unknown Station";
string stream_url = "";
float current_volume = 0.8;
integer listeners_count = 0;
string last_updated = "";

// Display management
string display_text = "";
integer display_face = ALL_SIDES;
float last_status_update = 0.0;
integer consecutive_errors = 0;

// Animation and effects
integer animate_display = TRUE;
float animation_timer = 0.0;
integer animation_step = 0;

// ===========================================
// UTILITY FUNCTIONS
// ===========================================

// Truncate text to fit display limits
string truncate_text(string text, integer max_length)
{
    if (llStringLength(text) <= max_length)
        return text;
    return llGetSubString(text, 0, max_length - 3) + "...";
}

// Format time ago string
string time_ago(float timestamp)
{
    float now = llGetUnixTime();
    float diff = now - timestamp;
    
    if (diff < 60)
        return (string)((integer)diff) + "s ago";
    else if (diff < 3600)
        return (string)((integer)(diff / 60)) + "m ago";
    else if (diff < 86400)
        return (string)((integer)(diff / 3600)) + "h ago";
    else
        return (string)((integer)(diff / 86400)) + "d ago";
}

// Create animated text effect
string animate_text(string text)
{
    if (!animate_display)
        return text;
    
    // Simple scrolling effect for long text
    if (llStringLength(text) > 50)
    {
        integer offset = animation_step % (llStringLength(text) - 40);
        return llGetSubString(text, offset, offset + 39) + "...";
    }
    
    return text;
}

// Update display based on current mode
update_display()
{
    string status_text;
    vector color;
    
    if (consecutive_errors > 3)
    {
        // Error state
        color = ERROR_COLOR;
        status_text = "❌ CONNECTION ERROR\n";
        status_text += "Check server status\n";
        status_text += "Errors: " + (string)consecutive_errors;
    }
    else if (is_playing)
    {
        // Playing state
        color = ACTIVE_COLOR;
        
        if (DISPLAY_MODE == 0) // Full display
        {
            status_text = DISPLAY_TITLE + "\n\n";
            status_text += "🎵 NOW PLAYING 🎵\n";
            status_text += "Station: " + truncate_text(current_station, MAX_STATION_LENGTH) + "\n";
            status_text += "Song: " + animate_text(truncate_text(current_song, MAX_SONG_LENGTH)) + "\n";
            status_text += "Volume: " + (string)((integer)(current_volume * 100)) + "%\n";
            if (last_updated != "")
                status_text += "Updated: " + last_updated;
        }
        else if (DISPLAY_MODE == 1) // Compact display
        {
            status_text = "🎵 PLAYING\n";
            status_text += truncate_text(current_station, 25) + "\n";
            status_text += animate_text(truncate_text(current_song, 35));
        }
        else if (DISPLAY_MODE == 2) // Song only
        {
            status_text = "♪ " + animate_text(truncate_text(current_song, 45));
        }
        else // Minimal
        {
            status_text = "🎵 ON AIR";
        }
    }
    else
    {
        // Idle state
        color = IDLE_COLOR;
        
        if (DISPLAY_MODE == 0) // Full display
        {
            status_text = DISPLAY_TITLE + "\n\n";
            status_text += "📻 RADIO OFFLINE 📻\n";
            status_text += "No stream currently playing\n";
            if (current_station != "Unknown Station")
                status_text += "Last: " + truncate_text(current_station, MAX_STATION_LENGTH) + "\n";
            if (last_updated != "")
                status_text += "Updated: " + last_updated;
        }
        else if (DISPLAY_MODE == 1) // Compact display
        {
            status_text = "📻 OFFLINE\n";
            status_text += "No stream playing";
        }
        else if (DISPLAY_MODE == 2) // Song only
        {
            status_text = "♪ No song playing";
        }
        else // Minimal
        {
            status_text = "📻 OFF";
        }
    }
    
    // Apply text to object
    llSetText(status_text, TEXT_COLOR, TEXT_ALPHA);
    llSetColor(color, display_face);
    
    display_text = status_text;
}

// ===========================================
// AUTHENTICATION FUNCTIONS
// ===========================================

// Get JWT token from API
get_auth_token()
{
    llOwnerSay("🔐 Display: Getting authentication token...");
    
    string auth_url = BOT_API_URL + "/auth/token";
    string post_data = "{\"api_key\":\"" + API_KEY + "\"}";
    
    key request_id = llHTTPRequest(auth_url, [
        HTTP_METHOD, "POST",
        HTTP_MIMETYPE, "application/json",
        HTTP_BODY_MAXLENGTH, 16384
    ], post_data);
}

// Parse JWT token from response
parse_auth_response(string body)
{
    list json_parts = llParseString2List(body, ["\""], []);
    integer token_index = llListFindList(json_parts, ["access_token"]);
    
    if (token_index != -1 && token_index + 2 < llGetListLength(json_parts))
    {
        jwt_token = llList2String(json_parts, token_index + 2);
        token_expires = llGetUnixTime() + 3600;
        llOwnerSay("✅ Display: Authentication successful!");
        consecutive_errors = 0;
        
        // Get initial status
        get_status();
        return;
    }
    
    llOwnerSay("❌ Display: Authentication failed");
    consecutive_errors++;
    update_display();
}

// Check if token is valid
integer is_token_valid()
{
    return (jwt_token != "" && llGetUnixTime() < token_expires);
}

// ===========================================
// API FUNCTIONS
// ===========================================

// Get current status via API
get_status()
{
    if (!is_token_valid())
    {
        get_auth_token();
        return;
    }
    
    string status_url = BOT_API_URL + "/streams/status?guild_id=" + (string)GUILD_ID;
    
    key request_id = llHTTPRequest(status_url, [
        HTTP_METHOD, "GET",
        HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + jwt_token,
        HTTP_BODY_MAXLENGTH, 16384
    ], "");
    
    last_status_update = llGetUnixTime();
}

// Get additional server info
get_server_info()
{
    if (!is_token_valid())
    {
        get_auth_token();
        return;
    }
    
    string info_url = BOT_API_URL + "/status/health";
    
    key request_id = llHTTPRequest(info_url, [
        HTTP_METHOD, "GET",
        HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + jwt_token,
        HTTP_BODY_MAXLENGTH, 16384
    ], "");
}

// ===========================================
// DISPLAY CONTROL FUNCTIONS
// ===========================================

// Cycle through display modes
cycle_display_mode()
{
    DISPLAY_MODE = (DISPLAY_MODE + 1) % 4;
    string modes[] = ["Full", "Compact", "Song Only", "Minimal"];
    llOwnerSay("Display mode: " + llList2String(modes, DISPLAY_MODE));
    update_display();
}

// Toggle animation
toggle_animation()
{
    animate_display = !animate_display;
    llOwnerSay("Animation: " + (string)(animate_display ? "ON" : "OFF"));
    update_display();
}

// ===========================================
// EVENT HANDLERS
// ===========================================

default
{
    state_entry()
    {
        llOwnerSay("📺 BunBot Status Display Ready!");
        llOwnerSay("📝 Edit script to configure API_KEY and GUILD_ID");
        llOwnerSay("👆 Touch to cycle display modes");
        
        // Initialize display
        update_display();
        
        // Get authentication token
        get_auth_token();
        
        // Start update timers
        llSetTimerEvent(STATUS_UPDATE_INTERVAL);
    }
    
    touch_start(integer total_number)
    {
        key user = llDetectedKey(0);
        
        // Owner controls
        if (user == llGetOwner())
        {
            // Cycle display mode on touch
            cycle_display_mode();
        }
        else
        {
            // Public users get current status
            if (is_playing)
            {
                llSay(0, "🎵 Now Playing: " + current_song + " on " + current_station);
            }
            else
            {
                llSay(0, "📻 Radio is currently offline");
            }
        }
    }
    
    touch_end(integer total_number)
    {
        key user = llDetectedKey(0);
        
        // Long press for owner = toggle animation
        if (user == llGetOwner())
        {
            toggle_animation();
        }
    }
    
    http_response(key request_id, integer status, list metadata, string body)
    {
        if (status == 200)
        {
            consecutive_errors = 0;
            
            // Handle auth response
            if (llSubStringIndex(body, "access_token") != -1)
            {
                parse_auth_response(body);
                return;
            }
            
            // Handle status response
            if (llSubStringIndex(body, "is_playing") != -1)
            {
                // Parse playing status
                is_playing = (llSubStringIndex(body, "\"is_playing\":true") != -1);
                
                // Extract current song
                list parts = llParseString2List(body, ["\"current_song\":\""], []);
                if (llGetListLength(parts) > 1)
                {
                    string song_part = llList2String(parts, 1);
                    list song_parts = llParseString2List(song_part, ["\""], []);
                    if (llGetListLength(song_parts) > 0)
                    {
                        current_song = llList2String(song_parts, 0);
                        if (current_song == "" || current_song == "null")
                            current_song = "Unknown Song";
                    }
                }
                
                // Extract station name from stream URL or status
                list station_parts = llParseString2List(body, ["\"station_name\":\""], []);
                if (llGetListLength(station_parts) > 1)
                {
                    string station_part = llList2String(station_parts, 1);
                    list name_parts = llParseString2List(station_part, ["\""], []);
                    if (llGetListLength(name_parts) > 0)
                    {
                        current_station = llList2String(name_parts, 0);
                    }
                }
                
                // Extract volume if available
                list vol_parts = llParseString2List(body, ["\"volume\":"], []);
                if (llGetListLength(vol_parts) > 1)
                {
                    string vol_part = llList2String(vol_parts, 1);
                    list vol_nums = llParseString2List(vol_part, [",", "}"], []);
                    if (llGetListLength(vol_nums) > 0)
                    {
                        current_volume = (float)llList2String(vol_nums, 0);
                    }
                }
                
                // Update timestamp
                list time_parts = llParseString2List(llGetTimestamp(), ["T"], []);
                if (llGetListLength(time_parts) > 1)
                {
                    string time_str = llList2String(time_parts, 1);
                    time_str = llGetSubString(time_str, 0, 7); // HH:MM:SS
                    last_updated = time_str;
                }
                
                update_display();
            }
            
            // Handle server info response
            if (llSubStringIndex(body, "status") != -1 && llSubStringIndex(body, "healthy") != -1)
            {
                // Server is healthy
                llOwnerSay("✅ Server connection healthy");
            }
        }
        else if (status == 401)
        {
            llOwnerSay("🔐 Display: Authentication expired, refreshing...");
            jwt_token = "";
            get_auth_token();
        }
        else
        {
            consecutive_errors++;
            llOwnerSay("❌ Display: HTTP Error " + (string)status + " (Errors: " + (string)consecutive_errors + ")");
            
            if (consecutive_errors > 5)
            {
                // Too many errors, slow down requests
                llSetTimerEvent(STATUS_UPDATE_INTERVAL * 2);
            }
            
            update_display();
        }
    }
    
    timer()
    {
        // Animation update
        if (animate_display)
        {
            animation_step++;
            animation_timer += DISPLAY_REFRESH_INTERVAL;
            
            if (animation_timer >= DISPLAY_REFRESH_INTERVAL)
            {
                animation_timer = 0.0;
                update_display();
            }
        }
        
        // Status update check
        float time_since_update = llGetUnixTime() - last_status_update;
        if (time_since_update >= STATUS_UPDATE_INTERVAL)
        {
            if (is_token_valid())
            {
                get_status();
            }
            else
            {
                get_auth_token();
            }
        }
        
        // Reset timer
        float next_interval = STATUS_UPDATE_INTERVAL;
        if (consecutive_errors > 5)
        {
            next_interval *= 2; // Slow down on errors
        }
        
        llSetTimerEvent(next_interval);
    }
    
    listen(integer channel, string name, key id, string message)
    {
        // Owner can send commands via chat
        if (id == llGetOwner())
        {
            if (message == "mode")
            {
                cycle_display_mode();
            }
            else if (message == "animate")
            {
                toggle_animation();
            }
            else if (message == "refresh")
            {
                get_status();
                llOwnerSay("🔄 Manual refresh requested");
            }
            else if (message == "reset")
            {
                llResetScript();
            }
        }
    }
    
    on_rez(integer start_param)
    {
        llResetScript();
    }
    
    changed(integer change)
    {
        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
        
        if (change & CHANGED_REGION)
        {
            // Region change - re-authenticate
            jwt_token = "";
            consecutive_errors = 0;
            get_auth_token();
        }
    }
    
    state_exit()
    {
        // Clean up on state change
        llSetTimerEvent(0.0);
        llSetText("", <1,1,1>, 0.0);
    }
}
