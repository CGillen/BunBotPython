# Bunbot - Simple Shoutcast Discord Bot!
Bunbot! was originally a JavaScript-based bot, but has been rewritten in Python!

Bunbot currently supports the following Codecs:
`MP3`, `OPUS`, `VORBIS`, `AAC`, and `AAC+`


It's designed to play Shoutcast and some Icecast streams. It supports the following commands:
- `/play`: Starts playing the stream.
- `/leave`: Leaves the voice channel.
- `/refresh`: Refresh the current playing stream.
- `/song`: Displays the current song playing.
- `/support`: Learn where you can get Support!
###### Maintainer Only Commands:
- `/debug`: Displays Limited Debugging information; can be used by normal members, but displays significantly less!
- `/maint`: used to toggle maint mode on and off, used for maintaining the bot!

<sub>Any command relating to the favorites system is in progress and highly unstable!</sub>

# Requirements
- `ffmpeg` - [Download](https://ffmpeg.org/download.html)

# Don't want to self-host?
No problem!
You can add the bot to your Discord here! [Click Me!](https://discord.com/oauth2/authorize?client_id=1326598970885144637)

EPIC translation done by: [CGillen](https://github.com/CGillen)!

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/J3J61BNDZO)

# So what's new?
- `better maintenance handling!  🎉`
- `clicky links! 🎉`
- `url slicer for shorter URLs!`
- `bitrate added to footers`
- `PLS parser for pls enjoyment 🎉`
- `Maint Embed added to let the audience know when it's time for service! 🎉`
- `More-Better-extra Handling for ~SLOOOOOWERRRR~ servers`
- `Implemented robust state manager for speedy recovery! 🎉`
- `Implemented BunnyDB 🎉`
- `More codecs! 🎉` 
- `Status and health monitoring system to combat desyncs!`
- `Implemented 3 try backoff system`
- `Better handling for leave`
- `Proper state cleanup on stream end 🎉`
- `Sleepy channels`
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
- `21 Bugs Squashed! 🎉`
  
<sub>SHOUTcast is a registered trademark of NULLsoft, Bunbot! is in no way affiliated with Nullsoft and their respective copyright holders.</sub>
