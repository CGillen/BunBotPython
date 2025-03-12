import urllib.request
import http

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

class IcylessHTTPConnection(http.client.HTTPConnection):
  response_class = IcylessHTTPResponse

class IcylessHTTPHandler(urllib.request.HTTPHandler):
  def http_open(self, req):
    return self.do_open(IcylessHTTPConnection, req)

def init_urllib_hack():
  # Create an opener with the custom handler
  opener = urllib.request.build_opener(IcylessHTTPHandler(), urllib.request.HTTPHandler)
  # Install opener as default opener
  urllib.request.install_opener(opener)
