import urllib.request
import http
import ssl

# let this being a warning to any future maintainers:
## time wasted here: < 4 hours

# global opener used when no explicit SSL context is passed to
# ``urlopen``; mimics the private ``_opener`` that the stdlib uses.
_opener = None


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


def _patched_urlopen(url, data=None, timeout=urllib.request.socket._GLOBAL_DEFAULT_TIMEOUT, *, context=None):
    """Opener-friendly version of :func:`urllib.request.urlopen`.

    ``urllib.request.urlopen`` normally builds a temporary opener that
    contains nothing but a plain ``HTTPSHandler`` when *context* is
    provided. This behavior was added in urllib 3 
    
    callers in this project (and the ``streamscrobbler``
    library) always pass a context, which bypassed the icy‑status
    conversions we install. This is partly my bad lmao 

    when I changed streamscrobbler to use a context
    I didn't realize that it would break the icy‑status handling
    so this is a workaround to make sure that the custom handlers are always used
    

    This function mirrors the standard logic
    but *always* attaches our custom handlers and forwards the context
    object.
    """
    global _opener
    if context is not None:
        https_handler = IcylessHTTPSHandler(context=context)
        opener = urllib.request.build_opener(IcylessHTTPHandler(), https_handler)
    else:
        if _opener is None:
            _opener = urllib.request.build_opener(IcylessHTTPHandler(), IcylessHTTPSHandler())
        opener = _opener
    return opener.open(url, data, timeout)


def init_urllib_hack(tls_verify: bool):

  # Create SSL context for HTTPS connections
  ctx = ssl.create_default_context()
  if not tls_verify:
    ctx = ssl._create_unverified_context()
    ctx.check_hostname = False
    ctx.set_ciphers('DEFAULT:@SECLEVEL=1')

  # Create an opener with both HTTP and HTTPS handlers
  opener = urllib.request.build_opener(
    IcylessHTTPHandler(),              # For HTTP URLs
    IcylessHTTPSHandler(context=ctx)   # For HTTPS URLs
  )

  # Install opener as default opener
  urllib.request.install_opener(opener)

  # sanity check: ensure urlopen is patched only once
  if urllib.request.urlopen is not _patched_urlopen:
      urllib.request.urlopen = _patched_urlopen
