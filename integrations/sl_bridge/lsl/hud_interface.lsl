//
// BunBot HUD Interface Script
// Wearable radio control panel for Second Life
//
// Attach this script to a HUD object for convenient radio controls
// Configure the settings below before use
//

// ===========================================
// CONFIGURATION - EDIT THESE SETTINGS
// ===========================================

// Your BunBot server configuration
string BOT_API_URL = "http://your-BunBot-server.com:8080/api/v1";
string API_KEY = "dev_key_123";  // Replace with your actual API key
integer GUILD_ID = 123456789;    // Replace with your Discord guild ID

// HUD Configuration
integer HUD_CHANNEL = -98765;    // Channel for HUD communications
vector HUD_COLOR = <0.2, 0.8, 1.0>; // Cyan color for active state
vector OFF_COLOR = <0.3, 0.3, 0.3>; // Gray color for inactive state

// Preset stream URLs
list PRESET_STREAMS = [
    "Radio Paradise|http://stream.radioparadise.com/rp_192m.ogg",
    "Soma FM|http://ice1.somafm.com/groovesalad-256-mp3",
    "BBC Radio 1|http://stream.live.vc.bbcmedia.co.uk/bbc_radio_one",
    "Custom Stream|"  // User can input custom URL
];

// ===========================================
// SCRIPT VARIABLES
// ===========================================

string jwt_token = "";
integer token_expires = 0;
integer listen_handle = 0;
integer text_input_handle = 0;
integer hud_channel;

// Current state
integer is_playing = FALSE;
string current_song = "No Song";
string current_station = "None";
float current_volume = 0.8;
integer auto_update = TRUE;

// HUD elements
integer face_play_stop = 0;     // Face 0: Play/Stop button
integer face_volume = 1;        // Face 1: Volume display
integer face_status = 2;        // Face 2: Status display
integer face_presets = 3;       // Face 3: Preset stations

// Update timer
float UPDATE_INTERVAL = 10.0;   // Update every 10 seconds

// ===========================================
// UTILITY FUNCTIONS
// ===========================================

// Generate random channel
integer random_channel()
{
    return (integer)(llFrand(9999999) + 1000000) * -1;
}

// Update HUD visual elements
update_hud_display()
{
    // Update play/stop button color
    if (is_playing)
    {
        llSetLinkColor(LINK_THIS, HUD_COLOR, face_play_stop);
        llSetLinkText(LINK_THIS, "⏸️ STOP", <1,1,1>, 1.0, face_play_stop);
    }
    else
    {
        llSetLinkColor(LINK_THIS, OFF_COLOR, face_play_stop);
        llSetLinkText(LINK_THIS, "▶️ PLAY", <1,1,1>, 1.0, face_play_stop);
    }
    
    // Update volume display
    integer volume_percent = (integer)(current_volume * 100);
    string volume_text = "🔊 " + (string)volume_percent + "%";
    llSetLinkText(LINK_THIS, volume_text, <1,1,1>, 1.0, face_volume);
    
    // Update status display
    string status_text = "♪ " + llGetSubString(current_song, 0, 20);
    if (llStringLength(current_song) > 20) status_text += "...";
    llSetLinkText(LINK_THIS, status_text, <1,1,1>, 1.0, face_status);
    
    // Update preset button
    llSetLinkText(LINK_THIS, "📻 PRESETS", <1,1,1>, 1.0, face_presets);
}

// Truncate text to fit HUD display
string truncate_text(string text, integer max_length)
{
    if (llStringLength(text) <= max_length)
        return text;
    return llGetSubString(text, 0, max_length - 3) + "...";
}

// ===========================================
// AUTHENTICATION FUNCTIONS
// ===========================================

// Get JWT token from API
get_auth_token()
{
    llOwnerSay("🔐 HUD: Getting authentication token...");
    
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
        llOwnerSay("✅ HUD: Authentication successful!");
        
        // Get initial status
        get_status();
        return;
    }
    
    llOwnerSay("❌ HUD: Authentication failed");
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

// Show preset stations menu
show_presets_menu(key user)
{
    hud_channel = random_channel();
    
    if (listen_handle != 0)
        llListenRemove(listen_handle);
    
    listen_handle = llListen(hud_channel, "", user, "");
    llSetTimerEvent(30.0);
    
    list menu_options = [];
    integer i;
    for (i = 0; i < llGetListLength(PRESET_STREAMS); i++)
    {
        string preset = llList2String(PRESET_STREAMS, i);
        list parts = llParseString2List(preset, ["|"], []);
        string name = llList2String(parts, 0);
        menu_options += [name];
    }
    menu_options += ["Cancel"];
    
    llDialog(user, "🎵 Select a radio station:", menu_options, hud_channel);
}

// Show volume control menu
show_volume_menu(key user)
{
    hud_channel = random_channel();
    
    if (listen_handle != 0)
        llListenRemove(listen_handle);
    
    listen_handle = llListen(hud_channel, "", user, "");
    llSetTimerEvent(30.0);
    
    list volume_options = ["🔇 Mute", "🔉 25%", "🔊 50%", "📢 75%", "🎵 100%", "Custom", "Cancel"];
    
    llDialog(user, "🔊 Volume Control:", volume_options, hud_channel);
}

// ===========================================
// EVENT HANDLERS
// ===========================================

default
{
    state_entry()
    {
        llOwnerSay("🎵 BunBot HUD Interface Ready!");
        llOwnerSay("📝 Edit script to configure API_KEY and GUILD_ID");
        
        // Initialize HUD display
        update_hud_display();
        
        // Get authentication token
        get_auth_token();
        
        // Start periodic updates
        if (auto_update)
        {
            llSetTimerEvent(UPDATE_INTERVAL);
        }
    }
    
    touch_start(integer total_number)
    {
        key user = llDetectedKey(0);
        integer face = llDetectedTouchFace(0);
        
        // Only allow owner to use the HUD
        if (user != llGetOwner())
        {
            return;
        }
        
        // Handle face clicks
        if (face == face_play_stop)
        {
            if (is_playing)
            {
                stop_stream();
            }
            else
            {
                // If no current station, show presets
                if (current_station == "None")
                {
                    show_presets_menu(user);
                }
                else
                {
                    // Resume last station
                    get_status(); // This will trigger a play if needed
                }
            }
        }
        else if (face == face_volume)
        {
            show_volume_menu(user);
        }
        else if (face == face_status)
        {
            // Manual status update
            get_status();
            llOwnerSay("🔄 Status updated");
        }
        else if (face == face_presets)
        {
            show_presets_menu(user);
        }
    }
    
    listen(integer channel, string name, key id, string message)
    {
        if (channel != hud_channel) return;
        
        llListenRemove(listen_handle);
        listen_handle = 0;
        llSetTimerEvent(0.0);
        
        // Handle preset selection
        integer i;
        for (i = 0; i < llGetListLength(PRESET_STREAMS); i++)
        {
            string preset = llList2String(PRESET_STREAMS, i);
            list parts = llParseString2List(preset, ["|"], []);
            string name = llList2String(parts, 0);
            string url = llList2String(parts, 1);
            
            if (message == name)
            {
                if (url == "")
                {
                    // Custom stream input
                    llTextBox(id, "Enter custom stream URL:", HUD_CHANNEL);
                    text_input_handle = llListen(HUD_CHANNEL, "", id, "");
                    llSetTimerEvent(60.0); // Longer timeout for text input
                    return;
                }
                else
                {
                    current_station = name;
                    play_stream(url);
                    return;
                }
            }
        }
        
        // Handle volume selection
        if (message == "🔇 Mute")
        {
            set_volume(0.0);
        }
        else if (message == "🔉 25%")
        {
            set_volume(0.25);
        }
        else if (message == "🔊 50%")
        {
            set_volume(0.5);
        }
        else if (message == "📢 75%")
        {
            set_volume(0.75);
        }
        else if (message == "🎵 100%")
        {
            set_volume(1.0);
        }
        else if (message == "Custom")
        {
            llTextBox(id, "Enter volume (0.0 to 1.0):", HUD_CHANNEL);
            text_input_handle = llListen(HUD_CHANNEL, "", id, "");
            llSetTimerEvent(60.0);
            return;
        }
        
        // Restart auto-update timer
        if (auto_update)
        {
            llSetTimerEvent(UPDATE_INTERVAL);
        }
    }
    
    listen(integer channel, string name, key id, string message)
    {
        if (channel != HUD_CHANNEL) return;
        
        llListenRemove(text_input_handle);
        text_input_handle = 0;
        
        // Handle custom stream URL
        if (llSubStringIndex(message, "http") == 0)
        {
            current_station = "Custom";
            play_stream(message);
        }
        // Handle custom volume
        else
        {
            float volume = (float)message;
            if (volume >= 0.0 && volume <= 1.0)
            {
                set_volume(volume);
            }
            else
            {
                llOwnerSay("❌ Invalid volume. Use 0.0 to 1.0");
            }
        }
        
        // Restart auto-update timer
        if (auto_update)
        {
            llSetTimerEvent(UPDATE_INTERVAL);
        }
    }
    
    http_response(key request_id, integer status, list metadata, string body)
    {
        if (status == 200)
        {
            // Handle auth response
            if (llSubStringIndex(body, "access_token") != -1)
            {
                parse_auth_response(body);
                return;
            }
            
            // Handle API responses
            if (llSubStringIndex(body, "success") != -1)
            {
                if (llSubStringIndex(body, "true") != -1)
                {
                    // Update local state
                    if (llSubStringIndex(body, "playing") != -1)
                    {
                        is_playing = TRUE;
                    }
                    else if (llSubStringIndex(body, "stopped") != -1)
                    {
                        is_playing = FALSE;
                        current_song = "Stopped";
                    }
                    
                    update_hud_display();
                }
            }
            
            // Handle status response
            if (llSubStringIndex(body, "is_playing") != -1)
            {
                // Parse status
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
                
                update_hud_display();
            }
        }
        else if (status == 401)
        {
            llOwnerSay("🔐 HUD: Authentication expired, refreshing...");
            jwt_token = "";
            get_auth_token();
        }
        else
        {
            llOwnerSay("❌ HUD: HTTP Error " + (string)status);
        }
    }
    
    timer()
    {
        // Clean up listeners
        if (listen_handle != 0)
        {
            llListenRemove(listen_handle);
            listen_handle = 0;
        }
        if (text_input_handle != 0)
        {
            llListenRemove(text_input_handle);
            text_input_handle = 0;
        }
        
        // Auto-update status
        if (auto_update && is_token_valid())
        {
            get_status();
            llSetTimerEvent(UPDATE_INTERVAL);
        }
        else if (auto_update)
        {
            // Need to re-authenticate
            get_auth_token();
            llSetTimerEvent(UPDATE_INTERVAL);
        }
    }
    
    attach(key id)
    {
        if (id != NULL_KEY)
        {
            // Attached to avatar
            llOwnerSay("📱 BunBot HUD attached. Touch faces to control radio.");
            update_hud_display();
            
            if (auto_update)
            {
                llSetTimerEvent(UPDATE_INTERVAL);
            }
        }
        else
        {
            // Detached
            llSetTimerEvent(0.0);
        }
    }
    
    on_rez(integer start_param)
    {
        llResetScript();
    }
}
