//
// BunBot Basic Controller Script
// Simple Second Life script for controlling Discord radio bot
//
// Place this script in any object to control BunBot from Second Life
// Configure the settings below and touch the object to use
//

// ===========================================
// CONFIGURATION - EDIT THESE SETTINGS
// ===========================================

// Your BunBot server configuration
string BOT_API_URL = "http://your-BunBot-server.com:8080/api/v1";
string API_KEY = "dev_key_123";  // Replace with your actual API key
integer GUILD_ID = 123456789;    // Replace with your Discord guild ID

// Default stream URL (optional - can be changed via touch menu)
string DEFAULT_STREAM = "http://stream.radioparadise.com/rp_192m.ogg";

// ===========================================
// SCRIPT VARIABLES
// ===========================================

string jwt_token = "";
integer token_expires = 0;
integer listen_handle = 0;
integer menu_channel;
list menu_options = ["Play Stream", "Stop Stream", "Get Status", "Set Volume", "Configure"];

// Current state
integer is_playing = FALSE;
string current_song = "Unknown";
float current_volume = 0.8;

// ===========================================
// UTILITY FUNCTIONS
// ===========================================

// Generate random channel for menu dialogs
integer random_channel()
{
    return (integer)(llFrand(9999999) + 1000000) * -1;
}

// Display status to user
show_status(key user)
{
    string status_text = "🎵 BunBot Status 🎵\n\n";
    status_text += "Playing: " + (string)is_playing + "\n";
    status_text += "Song: " + current_song + "\n";
    status_text += "Volume: " + (string)((integer)(current_volume * 100)) + "%\n";
    status_text += "Guild ID: " + (string)GUILD_ID;
    
    llSay(0, status_text);
}

// ===========================================
// AUTHENTICATION FUNCTIONS
// ===========================================

// Get JWT token from API
get_auth_token()
{
    llOwnerSay("🔐 Getting authentication token...");
    
    string auth_url = BOT_API_URL + "/auth/token";
    string post_data = "{\"api_key\":\"" + API_KEY + "\"}";
    
    key request_id = llHTTPRequest(auth_url, [
        HTTP_METHOD, "POST",
        HTTP_MIMETYPE, "application/json",
        HTTP_BODY_MAXLENGTH, 16384
    ], post_data);
    
    llOwnerSay("📡 Authentication request sent...");
}

// Parse JWT token from response
parse_auth_response(string body)
{
    // Simple JSON parsing for token
    list json_parts = llParseString2List(body, ["\""], []);
    integer token_index = llListFindList(json_parts, ["access_token"]);
    
    if (token_index != -1 && token_index + 2 < llGetListLength(json_parts))
    {
        jwt_token = llList2String(json_parts, token_index + 2);
        token_expires = llGetUnixTime() + 3600; // Token expires in 1 hour
        llOwnerSay("✅ Authentication successful!");
        return;
    }
    
    llOwnerSay("❌ Authentication failed - check your API key");
}

// Check if token is valid
integer is_token_valid()
{
    return (jwt_token != "" && llGetUnixTime() < token_expires);
}

// ===========================================
// API FUNCTIONS
// ===========================================

// Play stream via API
play_stream(string stream_url)
{
    if (!is_token_valid())
    {
        get_auth_token();
        return;
    }
    
    llOwnerSay("▶️ Starting stream: " + stream_url);
    
    string play_url = BOT_API_URL + "/streams/play";
    string post_data = "{\"url\":\"" + stream_url + "\",\"guild_id\":" + (string)GUILD_ID + "}";
    
    key request_id = llHTTPRequest(play_url, [
        HTTP_METHOD, "POST",
        HTTP_MIMETYPE, "application/json",
        HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + jwt_token,
        HTTP_BODY_MAXLENGTH, 16384
    ], post_data);
}

// Stop stream via API
stop_stream()
{
    if (!is_token_valid())
    {
        get_auth_token();
        return;
    }
    
    llOwnerSay("⏹️ Stopping stream...");
    
    string stop_url = BOT_API_URL + "/streams/stop";
    string post_data = "{\"guild_id\":" + (string)GUILD_ID + "}";
    
    key request_id = llHTTPRequest(stop_url, [
        HTTP_METHOD, "POST",
        HTTP_MIMETYPE, "application/json",
        HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + jwt_token,
        HTTP_BODY_MAXLENGTH, 16384
    ], post_data);
}

// Get current status via API
get_status()
{
    if (!is_token_valid())
    {
        get_auth_token();
        return;
    }
    
    llOwnerSay("📊 Getting current status...");
    
    string status_url = BOT_API_URL + "/streams/status?guild_id=" + (string)GUILD_ID;
    
    key request_id = llHTTPRequest(status_url, [
        HTTP_METHOD, "GET",
        HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + jwt_token,
        HTTP_BODY_MAXLENGTH, 16384
    ], "");
}

// Set volume via API
set_volume(float volume)
{
    if (!is_token_valid())
    {
        get_auth_token();
        return;
    }
    
    llOwnerSay("🔊 Setting volume to " + (string)((integer)(volume * 100)) + "%");
    
    string volume_url = BOT_API_URL + "/audio/volume";
    string post_data = "{\"guild_id\":" + (string)GUILD_ID + ",\"volume\":" + (string)volume + "}";
    
    key request_id = llHTTPRequest(volume_url, [
        HTTP_METHOD, "POST",
        HTTP_MIMETYPE, "application/json",
        HTTP_CUSTOM_HEADER, "Authorization", "Bearer " + jwt_token,
        HTTP_BODY_MAXLENGTH, 16384
    ], post_data);
}

// ===========================================
// MENU FUNCTIONS
// ===========================================

// Show main menu
show_menu(key user)
{
    menu_channel = random_channel();
    
    if (listen_handle != 0)
        llListenRemove(listen_handle);
    
    listen_handle = llListen(menu_channel, "", user, "");
    llSetTimerEvent(30.0); // Menu timeout
    
    string menu_text = "🎵 BunBot Controller 🎵\n\n";
    menu_text += "Choose an action:";
    
    llDialog(user, menu_text, menu_options, menu_channel);
}

// Show volume menu
show_volume_menu(key user)
{
    menu_channel = random_channel();
    
    if (listen_handle != 0)
        llListenRemove(listen_handle);
    
    listen_handle = llListen(menu_channel, "", user, "");
    llSetTimerEvent(30.0);
    
    list volume_options = ["10%", "25%", "50%", "75%", "100%", "Cancel"];
    
    llDialog(user, "🔊 Select Volume Level:", volume_options, menu_channel);
}

// ===========================================
// EVENT HANDLERS
// ===========================================

default
{
    state_entry()
    {
        llOwnerSay("🎵 BunBot Basic Controller Ready!");
        llOwnerSay("📝 Edit script to configure API_KEY and GUILD_ID");
        llOwnerSay("👆 Touch to start controlling your Discord bot");
        
        // Set object text for easy identification
        llSetText("🎵 BunBot Controller\nTouch to Control", <1,1,1>, 1.0);
    }
    
    touch_start(integer total_number)
    {
        key user = llDetectedKey(0);
        
        // Only allow owner to use the controller
        if (user != llGetOwner())
        {
            llSay(0, "❌ Only the owner can use this controller");
            return;
        }
        
        show_menu(user);
    }
    
    listen(integer channel, string name, key id, string message)
    {
        if (channel != menu_channel) return;
        
        llListenRemove(listen_handle);
        listen_handle = 0;
        llSetTimerEvent(0.0);
        
        // Handle main menu options
        if (message == "Play Stream")
        {
            play_stream(DEFAULT_STREAM);
        }
        else if (message == "Stop Stream")
        {
            stop_stream();
        }
        else if (message == "Get Status")
        {
            get_status();
        }
        else if (message == "Set Volume")
        {
            show_volume_menu(id);
            return; // Don't close menu yet
        }
        else if (message == "Configure")
        {
            llOwnerSay("⚙️ Configuration:");
            llOwnerSay("API URL: " + BOT_API_URL);
            llOwnerSay("Guild ID: " + (string)GUILD_ID);
            llOwnerSay("Edit script to change settings");
        }
        // Handle volume menu options
        else if (message == "10%")
        {
            set_volume(0.1);
        }
        else if (message == "25%")
        {
            set_volume(0.25);
        }
        else if (message == "50%")
        {
            set_volume(0.5);
        }
        else if (message == "75%")
        {
            set_volume(0.75);
        }
        else if (message == "100%")
        {
            set_volume(1.0);
        }
        else if (message == "Cancel")
        {
            llOwnerSay("Volume change cancelled");
        }
    }
    
    http_response(key request_id, integer status, list metadata, string body)
    {
        if (status == 200)
        {
            // Check if this is an auth response
            if (llSubStringIndex(body, "access_token") != -1)
            {
                parse_auth_response(body);
                return;
            }
            
            // Parse successful API responses
            if (llSubStringIndex(body, "success") != -1)
            {
                if (llSubStringIndex(body, "true") != -1)
                {
                    llOwnerSay("✅ Command successful!");
                    
                    // Update local state based on response
                    if (llSubStringIndex(body, "playing") != -1)
                    {
                        is_playing = TRUE;
                    }
                    else if (llSubStringIndex(body, "stopped") != -1)
                    {
                        is_playing = FALSE;
                        current_song = "Stopped";
                    }
                }
                else
                {
                    llOwnerSay("❌ Command failed: " + body);
                }
            }
            
            // Parse status response
            if (llSubStringIndex(body, "is_playing") != -1)
            {
                // Simple status parsing
                is_playing = (llSubStringIndex(body, "\"is_playing\":true") != -1);
                
                // Try to extract current song
                list parts = llParseString2List(body, ["\"current_song\":\""], []);
                if (llGetListLength(parts) > 1)
                {
                    string song_part = llList2String(parts, 1);
                    list song_parts = llParseString2List(song_part, ["\""], []);
                    if (llGetListLength(song_parts) > 0)
                    {
                        current_song = llList2String(song_parts, 0);
                    }
                }
                
                show_status(llGetOwner());
            }
        }
        else if (status == 401)
        {
            llOwnerSay("🔐 Authentication expired, getting new token...");
            jwt_token = "";
            get_auth_token();
        }
        else
        {
            llOwnerSay("❌ HTTP Error " + (string)status + ": " + body);
        }
    }
    
    timer()
    {
        // Clean up menu timeout
        if (listen_handle != 0)
        {
            llListenRemove(listen_handle);
            listen_handle = 0;
        }
        llSetTimerEvent(0.0);
        llOwnerSay("⏰ Menu timeout");
    }
    
    on_rez(integer start_param)
    {
        llResetScript();
    }
}
