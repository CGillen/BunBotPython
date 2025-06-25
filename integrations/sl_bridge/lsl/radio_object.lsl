//
// BunBot Radio Object Script
// In-world clickable radio for Second Life
//
// Place this script in a radio object for easy public access
// Configure the settings below before use
//

// ===========================================
// CONFIGURATION - EDIT THESE SETTINGS
// ===========================================

// Your BunBot server configuration
string BOT_API_URL = "http://your-BunBot-server.com:8080/api/v1";
string API_KEY = "dev_key_123";  // Replace with your actual API key
integer GUILD_ID = 123456789;    // Replace with your Discord guild ID

// Radio object configuration
string RADIO_NAME = "BunBot Radio";
vector IDLE_COLOR = <0.5, 0.5, 1.0>;    // Blue when idle
vector PLAYING_COLOR = <0.0, 1.0, 0.0>; // Green when playing
vector ERROR_COLOR = <1.0, 0.0, 0.0>;   // Red when error

// Default stations (users can cycle through these)
list DEFAULT_STATIONS = [
    "Radio Paradise|http://stream.radioparadise.com/rp_192m.ogg",
    "Soma FM Groove Salad|http://ice1.somafm.com/groovesalad-256-mp3",
    "BBC Radio 1|http://stream.live.vc.bbcmedia.co.uk/bbc_radio_one",
    "Jazz24|http://live.str3am.com:2430/jazz24"
];

// Access control
integer PUBLIC_ACCESS = TRUE;       // Allow anyone to use the radio
list AUTHORIZED_USERS = [];         // Specific users (if PUBLIC_ACCESS = FALSE)

// Display settings
integer SHOW_CURRENT_SONG = TRUE;   // Display current song above radio
float DISPLAY_HEIGHT = 2.0;         // Height of text display above radio

// ===========================================
// SCRIPT VARIABLES
// ===========================================

string jwt_token = "";
integer token_expires = 0;
integer listen_handle = 0;
integer menu_channel;

// Current state
integer is_playing = FALSE;
string current_song = "No Song Playing";
string current_station = "None";
integer current_station_index = 0;
float current_volume = 0.8;

// Display management
integer display_link = LINK_UNSET;

// Update intervals
float STATUS_UPDATE_INTERVAL = 15.0; // Check status every 15 seconds
float DISPLAY_UPDATE_INTERVAL = 5.0; // Update display every 5 seconds

// ===========================================
// UTILITY FUNCTIONS
// ===========================================

// Generate random channel for menus
integer random_channel()
{
    return (integer)(llFrand(9999999) + 1000000) * -1;
}

// Check if user is authorized to use the radio
integer is_authorized(key user)
{
    if (PUBLIC_ACCESS)
        return TRUE;
    
    if (user == llGetOwner())
        return TRUE;
    
    return (llListFindList(AUTHORIZED_USERS, [user]) != -1);
}

// Update radio visual state
update_radio_display()
{
    vector color;
    string status_text;
    
    if (is_playing)
    {
        color = PLAYING_COLOR;
        status_text = "🎵 PLAYING\n" + current_station + "\n" + llGetSubString(current_song, 0, 30);
        if (llStringLength(current_song) > 30) status_text += "...";
    }
    else
    {
        color = IDLE_COLOR;
        status_text = "📻 " + RADIO_NAME + "\nTouch to Play\nClick for Menu";
    }
    
    // Set radio color
    llSetColor(color, ALL_SIDES);
    
    // Update text display
    if (SHOW_CURRENT_SONG)
    {
        vector pos = llGetPos();
        pos.z += DISPLAY_HEIGHT;
        llSetText(status_text, <1,1,1>, 1.0);
    }
    
    // Update object name
    if (is_playing)
    {
        llSetObjectName(RADIO_NAME + " - Playing: " + current_station);
    }
    else
    {
        llSetObjectName(RADIO_NAME + " - Touch to Play");
    }
}

// Get station info from index
list get_station_info(integer index)
{
    if (index < 0 || index >= llGetListLength(DEFAULT_STATIONS))
        return [];
    
    string station_data = llList2String(DEFAULT_STATIONS, index);
    return llParseString2List(station_data, ["|"], []);
}

// ===========================================
// AUTHENTICATION FUNCTIONS
// ===========================================

// Get JWT token from API
get_auth_token()
{
    llOwnerSay("🔐 Radio: Getting authentication token...");
    
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
        llOwnerSay("✅ Radio: Authentication successful!");
        
        // Get initial status
        get_status();
        return;
    }
    
    llOwnerSay("❌ Radio: Authentication failed");
    llSetColor(ERROR_COLOR, ALL_SIDES);
    llSetText("❌ Authentication Failed\nCheck Configuration", <1,0,0>, 1.0);
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
    
    llOwnerSay("▶️ Radio: Starting stream: " + current_station);
    
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
    
    llOwnerSay("⏹️ Radio: Stopping stream...");
    
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

// Show main radio menu
show_main_menu(key user)
{
    menu_channel = random_channel();
    
    if (listen_handle != 0)
        llListenRemove(listen_handle);
    
    listen_handle = llListen(menu_channel, "", user, "");
    llSetTimerEvent(30.0);
    
    list menu_options = [];
    
    if (is_playing)
    {
        menu_options += ["⏹️ Stop", "⏭️ Next Station", "🔊 Volume"];
    }
    else
    {
        menu_options += ["▶️ Play", "📻 Stations", "🔊 Volume"];
    }
    
    menu_options += ["📊 Status", "⚙️ Settings", "❌ Cancel"];
    
    string menu_text = "🎵 " + RADIO_NAME + " Control\n\n";
    if (is_playing)
    {
        menu_text += "Currently Playing: " + current_station + "\n";
        menu_text += "Song: " + llGetSubString(current_song, 0, 40);
        if (llStringLength(current_song) > 40) menu_text += "...";
    }
    else
    {
        menu_text += "Radio is currently stopped.\nChoose an action:";
    }
    
    llDialog(user, menu_text, menu_options, menu_channel);
}

// Show station selection menu
show_stations_menu(key user)
{
    menu_channel = random_channel();
    
    if (listen_handle != 0)
        llListenRemove(listen_handle);
    
    listen_handle = llListen(menu_channel, "", user, "");
    llSetTimerEvent(30.0);
    
    list menu_options = [];
    integer i;
    for (i = 0; i < llGetListLength(DEFAULT_STATIONS) && i < 9; i++)
    {
        list station_info = get_station_info(i);
        if (llGetListLength(station_info) >= 1)
        {
            string name = llList2String(station_info, 0);
            menu_options += [llGetSubString(name, 0, 23)]; // Limit length for dialog
        }
    }
    menu_options += ["🔙 Back", "❌ Cancel"];
    
    llDialog(user, "📻 Select a radio station:", menu_options, menu_channel);
}

// Show volume menu
show_volume_menu(key user)
{
    menu_channel = random_channel();
    
    if (listen_handle != 0)
        llListenRemove(listen_handle);
    
    listen_handle = llListen(menu_channel, "", user, "");
    llSetTimerEvent(30.0);
    
    list volume_options = ["🔇 10%", "🔉 25%", "🔊 50%", "📢 75%", "🎵 100%", 
                          "🔙 Back", "❌ Cancel"];
    
    string volume_text = "🔊 Current Volume: " + (string)((integer)(current_volume * 100)) + "%\n";
    volume_text += "Select new volume level:";
    
    llDialog(user, volume_text, volume_options, menu_channel);
}

// ===========================================
// EVENT HANDLERS
// ===========================================

default
{
    state_entry()
    {
        llOwnerSay("🎵 BunBot Radio Object Ready!");
        llOwnerSay("📝 Edit script to configure API_KEY and GUILD_ID");
        
        // Initialize display
        update_radio_display();
        
        // Get authentication token
        get_auth_token();
        
        // Start status updates
        llSetTimerEvent(STATUS_UPDATE_INTERVAL);
    }
    
    touch_start(integer total_number)
    {
        key user = llDetectedKey(0);
        
        // Check authorization
        if (!is_authorized(user))
        {
            llSay(0, "❌ You are not authorized to use this radio.");
            return;
        }
        
        // Simple click behavior
        if (is_playing)
        {
            // Quick stop on click when playing
            stop_stream();
        }
        else
        {
            // Quick play with current/first station
            if (current_station == "None")
            {
                // Start with first station
                current_station_index = 0;
                list station_info = get_station_info(current_station_index);
                if (llGetListLength(station_info) >= 2)
                {
                    current_station = llList2String(station_info, 0);
                    string url = llList2String(station_info, 1);
                    play_stream(url);
                }
            }
            else
            {
                // Resume last station
                get_status(); // Will trigger play if needed
            }
        }
        
        // Show menu for advanced options
        llSetTimerEvent(3.0); // Short delay then show menu
    }
    
    touch_end(integer total_number)
    {
        key user = llDetectedKey(0);
        
        // Check for long press (show full menu)
        if (!is_authorized(user))
            return;
        
        show_main_menu(user);
    }
    
    listen(integer channel, string name, key id, string message)
    {
        if (channel != menu_channel) return;
        
        llListenRemove(listen_handle);
        listen_handle = 0;
        llSetTimerEvent(STATUS_UPDATE_INTERVAL); // Resume normal updates
        
        // Handle main menu
        if (message == "▶️ Play")
        {
            if (current_station == "None")
            {
                show_stations_menu(id);
                return;
            }
            else
            {
                get_status(); // Resume
            }
        }
        else if (message == "⏹️ Stop")
        {
            stop_stream();
        }
        else if (message == "⏭️ Next Station")
        {
            // Cycle to next station
            current_station_index = (current_station_index + 1) % llGetListLength(DEFAULT_STATIONS);
            list station_info = get_station_info(current_station_index);
            if (llGetListLength(station_info) >= 2)
            {
                current_station = llList2String(station_info, 0);
                string url = llList2String(station_info, 1);
                play_stream(url);
            }
        }
        else if (message == "📻 Stations")
        {
            show_stations_menu(id);
            return;
        }
        else if (message == "🔊 Volume")
        {
            show_volume_menu(id);
            return;
        }
        else if (message == "📊 Status")
        {
            get_status();
            llSay(0, "🔄 Status updated");
        }
        else if (message == "⚙️ Settings")
        {
            llSay(0, "⚙️ Radio Settings:\nAPI: " + BOT_API_URL + "\nGuild: " + (string)GUILD_ID);
        }
        // Handle station selection
        else
        {
            integer i;
            for (i = 0; i < llGetListLength(DEFAULT_STATIONS); i++)
            {
                list station_info = get_station_info(i);
                if (llGetListLength(station_info) >= 2)
                {
                    string name = llList2String(station_info, 0);
                    if (llSubStringIndex(name, message) == 0) // Partial match for truncated names
                    {
                        current_station_index = i;
                        current_station = name;
                        string url = llList2String(station_info, 1);
                        play_stream(url);
                        return;
                    }
                }
            }
            
            // Handle volume selection
            if (message == "🔇 10%") set_volume(0.1);
            else if (message == "🔉 25%") set_volume(0.25);
            else if (message == "🔊 50%") set_volume(0.5);
            else if (message == "📢 75%") set_volume(0.75);
            else if (message == "🎵 100%") set_volume(1.0);
            else if (message == "🔙 Back") show_main_menu(id);
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
                        llSay(0, "✅ " + current_station + " started!");
                    }
                    else if (llSubStringIndex(body, "stopped") != -1)
                    {
                        is_playing = FALSE;
                        current_song = "Stopped";
                        llSay(0, "⏹️ Radio stopped");
                    }
                    
                    update_radio_display();
                }
                else
                {
                    llSay(0, "❌ Command failed");
                    llSetColor(ERROR_COLOR, ALL_SIDES);
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
                
                update_radio_display();
            }
        }
        else if (status == 401)
        {
            llOwnerSay("🔐 Radio: Authentication expired, refreshing...");
            jwt_token = "";
            get_auth_token();
        }
        else
        {
            llSay(0, "❌ Radio Error " + (string)status);
            llSetColor(ERROR_COLOR, ALL_SIDES);
            llSetText("❌ Connection Error\nCheck Server Status", <1,0,0>, 1.0);
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
        
        // Regular status updates
        if (is_token_valid())
        {
            get_status();
        }
        else
        {
            get_auth_token();
        }
        
        llSetTimerEvent(STATUS_UPDATE_INTERVAL);
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
    }
}
