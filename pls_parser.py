import asyncio
import logging
import os
import subprocess
import validators
from typing import Optional

logger = logging.getLogger('discord')

def url_valid(url: str) -> bool:
    return validators.url(url)

async def parse_pls(url: str) -> Optional[str]:
    """
    parse a .pls playlist file using curl, Returns the first 
    valid stream URL found as a string.
    
    Args:
        url: URL to the .pls file
    
    Returns:
        The first valid stream URL found in the playlist, or None if no valid URLs found
    """
    try:
        # Use curl to stream the playlist file line by line
        # iTunes user-agent to mimic a media player (safest bet for servers that block curl)
        proc_args = {
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE,
        }
        # Hide the console window on Windows
        if os.name == 'nt':
            proc_args['creationflags'] = subprocess.CREATE_NO_WINDOW

        # Remove extra quoting around the user-agent argument; pass url directly
        curl = await asyncio.create_subprocess_exec(
            'curl', '-L', '-N', '-A', 'iTunes/9.1.1', '--silent', url,
            **proc_args
        )
        # check if we have a valid stdout, if not stop early 
        while True:
            output = await curl.stdout.readline()
            if not output:
                break
            # look for "file1=" if we have data   
            try:
                string = output.decode('utf-8').strip()
                if string.lower().startswith('file1='):
                    stream_url = string.split('=', 1)[1].strip()                        
                    try:
                        curl.kill()  # we got it, die now
                        await curl.wait()  # Wait for it to die
                    except:
                        pass  # closed by itself
                    logger.debug("Verifying New URL is safe")
                    if not url_valid(stream_url):
                        logger.error("We Found a stream url but it was tainted, so we skipped it!")
                        return None
                    logger.debug(f"All checks Passed! Found Stream Link to be: {stream_url}")
                    return stream_url
            except UnicodeDecodeError:
                continue

        # Was unsuccessful, let's try to clean up
        try:
            curl.kill()  
            await curl.wait()  
        except:
            pass  # closed by itself
        logger.warning(f"No valid stream URL found in playlist: {url}")
        return None
        
    except Exception as e:
        # we tried our best
        logger.error(f"Error parsing playlist stream: {url} - {str(e)}")
        return None
