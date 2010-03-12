#!/usr/bin/env python

#------------------------------------------------------------------------------#
#   fetch.py                                                                   #
#                                                                              #
#   Copyright (c) 2009-2010, Code A La Mode, original authors.                 #
#                                                                              #
#       This file is part of imi-imi.                                          #
#                                                                              #
#       imi-imi is free software; you can redistribute it and/or modify        #
#       it under the terms of the GNU General Public License as published by   #
#       the Free Software Foundation, either version 3 of the License, or      #
#       (at your option) any later version.                                    #
#                                                                              #
#       imi-imi is distributed in the hope that it will be useful,             #
#       but WITHOUT ANY WARRANTY; without even the implied warranty of         #
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
#       GNU General Public License for more details.                           #
#                                                                              #
#       You should have received a copy of the GNU General Public License      #
#       along with imi-imi.  If not, see <http://www.gnu.org/licenses/>.       #
#------------------------------------------------------------------------------#
"""Utilities for fetching content from the web."""


# Originally, I'd used urllib2, but this package was too fragile on tenuous
# internet connections.  So I switched to urlfetch for more robust HTML
# fetching.  If we can't import urlfetch, then we're not running on Google App
# Engine, so we fall back to urllib2.


import cgi
import logging
import re
import urllib
import urlparse


try:
    # Try to use Google App Engine's urlfetch API.
    from google.appengine.api.urlfetch import fetch
    from google.appengine.api.urlfetch import InvalidURLError
    from google.appengine.api.urlfetch import DownloadError
    from google.appengine.api.urlfetch import ResponseTooLargeError
except ImportError:
    # Oops.  We can't use Google App Engine's urlfetch API.  We mustn't be
    # running on Google App Engine.  That's cool - fall back to Python's
    # urllib2.
    import urllib2
    _on_google_app_engine = False
    _exceptions = (urllib2.URLError,)
else:
    # Awesome.  We can use Google App Engine's urlfetch API.
    _on_google_app_engine = True
    _exceptions = (InvalidURLError, DownloadError, ResponseTooLargeError)

from config import FETCH_GOOD_STATUSES, FETCH_DOCUMENT_INDEXES


_log = logging.getLogger(__name__)


def fetch_content(url, status_codes=FETCH_GOOD_STATUSES):
    """Retrieve content from the web.  Make sure the status code is OK.

    That's "make sure the status code is OK" as in "okay," *not* "0K" as in
    "zero kilobytes."  Just in case there was any confusion.

    Since the following is a doctest, we know that we must be running this
    script in someone's development environment, I.E. not on Google App Engine.
    Make sure that this script properly detected that:
        >>> _on_google_app_engine
        False

    Example usage:
        >>> url = 'http://www.gutenberg.org/files/11/11-h/11-h.htm'
        >>> url, status_code, mime_type, content = fetch_content(url)
        >>> url
        'http://www.gutenberg.org/files/11/11-h/11-h.htm'
        >>> status_code, mime_type, len(content)
        (200, 'text/html', 179982)
    """
    url, status_code, mime_type, content = normalize_url(url), None, '', None
    if not url:
        _log.warning("couldn't fetch %s (couldn't normalize URL)" % url)
    else:
        _log.debug('fetching %s' % url)
        try:
            if _on_google_app_engine:
                response = fetch(url, allow_truncated=True,
                                 follow_redirects=True)
            else:
                response = urllib2.urlopen(url)
        except _exceptions, e:
            # Oops.  Either the URL was invalid, or there was a problem
            # retrieving the data.
            _log.warning("couldn't fetch %s (%s)" % (url, type(e)))
        else:
            url, status_code, mime_type, content = _grok_response(response, url)
            if status_code not in status_codes:
                # Oops.  We retrieved some data, but the server returned an
                # unacceptable status code.
                _log.warning('fetched %s, but status code %s' %
                             (url, status_code))
                status_code, mime_type, content = None, '', None
            _log.debug('fetched %s' % url)
        if ';' in mime_type:
            mime_type = mime_type.split(';', 1)[0]
    return url, status_code, mime_type, content


def _grok_response(response, url):
    """From a response, extract the URL, status code, MIME type, and content."""
    if _on_google_app_engine:
        url = normalize_url(response.headers.get('location', url))
        status_code = response.status_code
        mime_type = response.headers.get('content-type')
        content = response.content
    else:
        url = normalize_url(response.geturl())
        status_code = response.code
        mime_type = response.headers.get('Content-Type')
        content = response.read()
    return url, status_code, mime_type, content


def normalize_url(url):
    """Normalize a URL.
    
    We normalize URLs in order to determine whether or not two syntactically
    different URLs are equivalent.

    Example usage:
        >>> normalize_url('google.com')
        'http://google.com/'
        >>> normalize_url('http://google.com')
        'http://google.com/'
        >>> normalize_url('google.com/')
        'http://google.com/'
        >>> normalize_url('http://google.com/')
        'http://google.com/'
        >>> normalize_url('HTTP://google.com/')
        'http://google.com/'
        >>> normalize_url('http://GOOGLE.COM/')
        'http://google.com/'
        >>> normalize_url('HTTP://GOOGLE.COM/')
        'http://google.com/'
        >>> normalize_url('google.com:80')
        'http://google.com/'
        >>> normalize_url('google.com:8080')
        'http://google.com:8080/'
        >>> normalize_url('https://google.com:443')
        'https://google.com/'
        >>> normalize_url('https://google.com:8443')
        'https://google.com:8443/'
        >>> normalize_url('google.com/../a/b/../c/./d.html')
        'http://google.com/a/c/d.html'
        >>> normalize_url('google.com/index.html')
        'http://google.com/'
        >>> normalize_url('google.com/search?sex=male&first=raj&middle=&last=shah')
        'http://google.com/search?first=raj&last=shah&sex=male'
        >>> normalize_url('google.com/search?sex=male&first=rajiv&middle=bakulesh&last=shah')
        'http://google.com/search?first=rajiv&last=shah&middle=bakulesh&sex=male'
        >>> normalize_url('google.com/search?first=rajiv&last=shah&middle=bakulesh&sex=male')
        'http://google.com/search?first=rajiv&last=shah&middle=bakulesh&sex=male'
        >>> normalize_url('google.com/index.html#location')
        'http://google.com/#location'
        >>> normalize_url('google.com/document.html#location')
        'http://google.com/document.html#location'
        >>> normalize_url('google.com/a%c2%b1b')
        'http://google.com/a%C2%B1b'
        >>> normalize_url('google.com/a%c2%b1%b')
        'http://google.com/a%C2%B1%b'
        >>> normalize_url('google.com/a%c2%b1%b.html')
        'http://google.com/a%C2%B1%b.html'
        >>> normalize_url('google.com/a%c2%b1%b2.html')
        'http://google.com/a%C2%B1%B2.html'
        >>> normalize_url('HTTPS://GOOGLE.COM:8443/../a/%c2/../%b1/./%b.html?sex=male&first=raj&middle=&last=shah')
        'https://google.com:8443/a/%B1/%b.html?first=raj&last=shah&sex=male'
    """
    _log.debug('normalizing %s' % url)

    # Make sure that there's a scheme (http or https).
    url = url.split('://', 1)
    if not url or len(url) == 2 and not url[0].lower() in ('http', 'https',):
        return None
    if len(url) == 1:
        url = 'http://' + url[0]
    else:
        url = url[0] + '://' + url[1]

    # Parse the URL into a scheme, host, path, parameters, query, and fragment.
    # This automatically lowercases the scheme.
    scheme, host, path, params, query, fragment = urlparse.urlparse(url)

    # Lowercase the host.
    host = host.lower()

    # Remove the default port (if specified).
    if scheme == 'http' and host.endswith(':80'):
        host = host[:-3]
    elif scheme == 'https' and host.endswith(':443'):
        host = host[:-4]

    # Remove all of the dot segments from the path.  For more information, see:
    #   http://tools.ietf.org/html/rfc3986#section-5.2.4
    input, output = [c for c in path.split('/') if c], []
    for component in input:
        if component == '..':
            # Raj, the following line doesn't throw an IndexError.  Even if
            # output is an empty list.  You've tested this several times.  Stop
            # wasting your time.  Stop being paranoid.
            output = output[:-1]
        elif component == '.':
            pass
        else:
            output.append(component)
    output = [c for c in output if c]
    path = '/' + '/'.join(output)

    # Remove the default directory index (if specified).
    if path.endswith(FETCH_DOCUMENT_INDEXES):
        path = path.rsplit('/', 1)[0]

    # Add a trailing slash to the URL (if there's no path).
    if not path:
        path = '/'

    # Remove the query variables with no values, and alphabetize the query
    # variables with values.
    query = urllib.urlencode(sorted(cgi.parse_qsl(query)))

    # I used to remove the fragment here, but that's a bad idea, because lots
    # of AJAX-y apps abuse the fragment (or intra-document location) to serve
    # up different content.  Just keep the fragment, I guess, and sigh.

    # Assemble the munged scheme, host, path, parameters, query, and fragment
    # back into a URL.
    url = urlparse.urlunparse((scheme, host, path, params, query, fragment,))

    # Capitalize letters in percent-encoded character escape sequences.
    url = re.sub(r'%[0-9A-Fa-f][0-9A-Fa-f]', lambda m: m.group().upper(), url)

    _log.debug('normalized to %s' % url)
    return url


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=True)