import urllib.request
import http
import ssl
import socket
import logging
import time
from typing import Optional

logger = logging.getLogger('urllib_hack')

class NetworkTimeoutError(Exception):
    """Custom exception for network timeout operations"""
    pass

class IcylessHTTPResponse(http.client.HTTPResponse):
    """HTTP response handler with timeout protection and ICY protocol support"""
    
    def __init__(self, sock, debuglevel=0, method="GET", url=None):
        super().__init__(sock, debuglevel, method, url)
        self._timeout = getattr(sock, 'gettimeout', lambda: 10.0)() or 10.0
        self._start_time = time.time()
    
    def _read_status(self):
        """
        _read_status with timeout protection and proper error handling.
        
        Overrides http.client.HTTPResponse._read_status to:
        1. Add socket-level timeout protection
        2. Convert ICY status codes to HTTP/1.0 for compatibility
        3. Provide proper error classification and logging
        4. Implement connection health monitoring
        """
        try:
            # Set socket timeout if available
            if hasattr(self.fp, '_sock') and self.fp._sock:
                original_timeout = self.fp._sock.gettimeout()
                self.fp._sock.settimeout(self._timeout)
                logger.debug(f"Set socket timeout to {self._timeout}s")
            
            # Read status line with timeout protection
            start_time = time.time()
            try:
                line = str(self.fp.readline(http.client._MAXLINE + 1), "iso-8859-1")
                read_time = time.time() - start_time
                logger.debug(f"Status line read in {read_time:.3f}s: {repr(line[:50])}")
                
            except socket.timeout as e:
                elapsed = time.time() - self._start_time
                logger.error(f"Socket timeout after {elapsed:.3f}s reading status line")
                self._close_conn()
                raise NetworkTimeoutError(f"Timeout reading status line after {elapsed:.3f}s") from e
                
            except (socket.error, OSError) as e:
                elapsed = time.time() - self._start_time
                logger.error(f"Socket error after {elapsed:.3f}s: {e}")
                self._close_conn()
                raise http.client.RemoteDisconnected(f"Socket error reading status: {e}") from e
            
            # Restore original timeout
            if hasattr(self.fp, '_sock') and self.fp._sock and 'original_timeout' in locals():
                self.fp._sock.settimeout(original_timeout)
            
            # Validate line length
            if len(line) > http.client._MAXLINE:
                logger.error(f"Status line too long: {len(line)} bytes")
                raise http.client.LineTooLong("status line")
            
            # Debug logging
            if self.debuglevel > 0:
                print("reply:", repr(line))
            
            # Check for empty response
            if not line:
                logger.warning("Empty status line received")
                raise http.client.RemoteDisconnected(
                    "Remote end closed connection without response"
                )
            
            # Parse status line
            try:
                version, status, reason = line.split(None, 2)
            except ValueError:
                try:
                    version, status = line.split(None, 1)
                    reason = ""
                except ValueError:
                    # empty version will cause next test to fail.
                    version = ""
                    status = ""
                    reason = ""
            
            # CRITICAL: ICY protocol conversion for Icecast/Shoutcast compatibility
            if version.startswith("ICY"):
                logger.debug(f"Converting ICY response to HTTP/1.0: {version}")
                version = version.replace("ICY", "HTTP/1.0")
            
            # Validate HTTP version
            if not version.startswith("HTTP/"):
                logger.error(f"Invalid HTTP version: {version}")
                self._close_conn()
                raise http.client.BadStatusLine(line)
            
            # Validate and parse status code
            try:
                status_code = int(status)
                if status_code < 100 or status_code > 999:
                    logger.error(f"Invalid status code: {status_code}")
                    raise http.client.BadStatusLine(line)
                
                logger.debug(f"Parsed status: {version} {status_code} {reason}")
                return version, status_code, reason
                
            except ValueError as e:
                logger.error(f"Invalid status code format: {status}")
                raise http.client.BadStatusLine(line) from e
                
        except NetworkTimeoutError:
            # Re-raise our custom timeout errors
            raise
        except (http.client.HTTPException, socket.error):
            # Re-raise known HTTP and socket errors
            raise
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error in _read_status: {e}")
            self._close_conn()
            raise http.client.RemoteDisconnected(f"Unexpected error reading status: {e}") from e

# HTTP(S) Handler code by Harp0030 on GH
# HTTP Connection (for plain HTTP URLs)
class IcylessHTTPConnection(http.client.HTTPConnection):
  response_class = IcylessHTTPResponse

# HTTPS Connection (for HTTPS URLs)
class IcylessHTTPSConnection(http.client.HTTPSConnection):
  response_class = IcylessHTTPResponse

# HTTP Handler (for plain HTTP URLs)
class IcylessHTTPHandler(urllib.request.HTTPHandler):
  def http_open(self, req):
    return self.do_open(IcylessHTTPConnection, req)

# HTTPS Handler (for HTTPS URLs)
class IcylessHTTPSHandler(urllib.request.HTTPSHandler):
  def https_open(self, req):
    return self.do_open(IcylessHTTPSConnection, req)

def init_urllib_hack(tls_verify: bool):
  # Create SSL context for HTTPS connections
  ctx = ssl._create_unverified_context()
  if not tls_verify:
    ctx.set_ciphers('DEFAULT:@SECLEVEL=1')

  # Create an opener with both HTTP and HTTPS handlers
  opener = urllib.request.build_opener(
    IcylessHTTPHandler(),              # For HTTP URLs
    IcylessHTTPSHandler(context=ctx)   # For HTTPS URLs
  )

  # Install opener as default opener
  urllib.request.install_opener(opener)
