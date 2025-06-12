import urllib.request
import http
import ssl

class IcylessHTTPResponse(http.client.HTTPResponse):
  # OVERRIDE _read_status to convert ICY status code to HTTP/1.0
  def _read_status(self):
    line = str(self.fp.readline(http.client._MAXLINE + 1), "iso-8859-1")
    if len(line) > http.client._MAXLINE:
      raise http.client.LineTooLong("status line")
    if self.debuglevel > 0:
      print("reply:", repr(line))
    if not line:
      # Presumably, the server closed the connection before
      # sending a valid response.
      raise http.client.RemoteDisconnected("Remote end closed connection without"
                    " response")
    try:
      version, status, reason = line.split(None, 2)
    except ValueError:
      try:
        version, status = line.split(None, 1)
        reason = ""
      except ValueError:
        # empty version will cause next test to fail.
        version = ""
    # OVERRIDE FROM http.client. Replace ICY with HTTP/1.0 for compatibility with SHOUTCAST v1
    if version.startswith("ICY"):
      version = version.replace("ICY", "HTTP/1.0")

    if not version.startswith("HTTP/"):
      self._close_conn()
      raise http.client.BadStatusLine(line)
    # The status code is a three-digit number
    try:
      status = int(status)
      if status < 100 or status > 999:
        raise http.client.BadStatusLine(line)
    except ValueError:
      raise http.client.BadStatusLine(line)
    return version, status, reason

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
