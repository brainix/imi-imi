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
"""Utilities for fetching content from the web.

Originally, I'd used urllib2, but this package was too fragile on tenuous
internet connections.  So I switched to urlfetch for more robust HTML fetching.
If we can't import urlfetch, then we're not running on Google App Engine, so we
fall back to urllib2.

Since the following is a doctest, we know that we must be running this script
in someone's development environment, i.e. not on Google App Engine.  Make sure
that this script has properly detected that:

    >>> _on_app_engine
    False

We normalize URLs in order to determine whether or not two syntactically
different URLs are equivalent:

    >>> Factory().normalize('HTTPS://GOOGLE.COM:8443/../a/%c2/../%b1/./%b.html?sex=male&first=raj&middle=&last=shah')
    'https://google.com:8443/a/%B1/%b.html?first=raj&last=shah&sex=male'
"""


import cgi
import logging
import re
import urllib
import urllib2
import urlparse

try:
    # Try to use Google App Engine's urlfetch API.
    from google.appengine.api.urlfetch import fetch
    from google.appengine.api.urlfetch import GET
    from google.appengine.api.urlfetch import POST
    from google.appengine.api.urlfetch import InvalidURLError
    from google.appengine.api.urlfetch import DownloadError
    from google.appengine.api.urlfetch import ResponseTooLargeError
except ImportError:
    # Oops.  We can't use Google App Engine's urlfetch API.  We mustn't be
    # running on Google App Engine.  That's cool - fall back to Python's
    # urllib2.
    _on_app_engine = False
else:
    # Awesome.  We can use Google App Engine's urlfetch API.
    _on_app_engine = True

from config import FETCH_GOOD_STATUS_CODES, FETCH_DOCUMENT_INDEXES


_log = logging.getLogger(__name__)


class _BaseFetch(object):
    """ """

    def __init__(self):
        """ """
        self._exceptions = tuple()
        raise NotImplementedError

    def fetch(self, url, headers={}, payload={},
              status_codes=FETCH_GOOD_STATUS_CODES):
        """Retrieve content from the web.  Make sure the status code is OK.

        Example usage:
            >>> url = 'http://www.gutenberg.org/files/11/11-h/11-h.htm'
            >>> url, status_code, mime_type, content = Factory().fetch(url)
            >>> url
            'http://www.gutenberg.org/files/11/11-h/11-h.htm'
            >>> status_code, mime_type, len(content)
            (200, 'text/html', 179982)
        """
        url, payload = self.normalize(url), urllib.urlencode(payload)
        status_code, mime_type, content = None, '', None
        if not url:
            _log.warning("couldn't fetch %s (couldn't normalize URL)" % url)
        else:
            _log.debug('fetching %s' % url)
            try:
                response = self._fetch(url, payload=payload, headers=headers)
            except self._exceptions, e:
                # Oops.  Either the URL was invalid, or there was a problem
                # retrieving the data.
                _log.warning("couldn't fetch %s (%s)" % (url, type(e)))
            else:
                url, status_code, mime_type, content = self._grok(response, url)
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

    def normalize(self, url):
        """Normalize a URL.
        
        We normalize URLs in order to determine whether or not two
        syntactically different URLs are equivalent.

        Example usage:
            >>> Factory().normalize('google.com')
            'http://google.com/'
        """
        _log.debug('normalizing %s' % url)
        url = self._normalize_scheme(url)

        # Parse the URL into a scheme, host, path, parameters, query, and
        # fragment.  This automatically lowercases the scheme.
        scheme, host, path, params, query, fragment = urlparse.urlparse(url)

        host = self._normalize_host(scheme, host)
        path = self._normalize_path(path)
        query = self._normalize_query(query)

        # I used to remove the fragment here, but that's a bad idea, because
        # lots of AJAX-y apps abuse the fragment (or intra-document location)
        # to serve up different content.  Just keep the fragment, I guess, and
        # sigh.

        # Re-assemble the munged scheme, host, path, parameters, query, and
        # fragment back into a URL.
        url = urlparse.urlunparse((scheme, host, path, params, query, fragment))
        url = self._normalize_escape_sequences(url)
        _log.debug('normalized to %s' % url)
        return url

    def _normalize_scheme(self, url):
        """Make sure that the URL specifies a scheme (http or https).

        Examples:
            >>> Factory().normalize('google.com')
            'http://google.com/'
            >>> Factory().normalize('http://google.com')
            'http://google.com/'
            >>> Factory().normalize('google.com/')
            'http://google.com/'
            >>> Factory().normalize('http://google.com/')
            'http://google.com/'
            >>> Factory().normalize('HTTP://google.com/')
            'http://google.com/'
        """
        url = url.split('://', 1)
        if not url or len(url) == 2 and not url[0].lower() in ('http', 'https'):
            return None
        if len(url) == 1:
            url = 'http://' + url[0]
        else:
            url = url[0] + '://' + url[1]
        return url

    def _normalize_host(self, scheme, host):
        """Lowercase the URL's host and remove its default port (if specified).

        Examples:
            >>> Factory().normalize('http://GOOGLE.COM/')
            'http://google.com/'
            >>> Factory().normalize('HTTP://GOOGLE.COM/')
            'http://google.com/'
            >>> Factory().normalize('google.com:80')
            'http://google.com/'
            >>> Factory().normalize('google.com:8080')
            'http://google.com:8080/'
            >>> Factory().normalize('https://google.com:443')
            'https://google.com/'
            >>> Factory().normalize('https://google.com:8443')
            'https://google.com:8443/'
        """
        host = host.lower()
        if scheme == 'http' and host.endswith(':80'):
            host = host[:-3]
        elif scheme == 'https' and host.endswith(':443'):
            host = host[:-4]
        return host

    def _normalize_path(self, path):
        """Remove all of the dot segments from the URL's path.
        
        For more information, see:
            http://tools.ietf.org/html/rfc3986#section-5.2.4

        In addition, remove the path's default directory index (if specified).
        Lastly, if the path is the empty string, set it to a single forward
        slash (which acts as a trailing slash on the URL).

        Examples:
            >>> Factory().normalize('google.com/../a/b/../c/./d.html')
            'http://google.com/a/c/d.html'
            >>> Factory().normalize('google.com/index.html')
            'http://google.com/'
            >>> Factory().normalize('google.com/index.html#location')
            'http://google.com/#location'
            >>> Factory().normalize('google.com/document.html#location')
            'http://google.com/document.html#location'
            >>> Factory().normalize('http://google.com')
            'http://google.com/'
        """
        input, output = [c for c in path.split('/') if c], []
        for component in input:
            if component == '..':
                # Raj, the following line doesn't throw an IndexError.  Even if
                # output is an empty list.  You've tested this several times.
                # Stop wasting your time.  Stop being paranoid.
                output = output[:-1]
            elif component == '.':
                pass
            else:
                output.append(component)
        output = [c for c in output if c]
        path = '/' + '/'.join(output)

        if path.endswith(FETCH_DOCUMENT_INDEXES):
            path = path.rsplit('/', 1)[0]
        if not path:
            path = '/'
        return path

    def _normalize_query(self, query):
        """Remove query parameters with no values, and alphabetize the rest.

        Examples:
            >>> Factory().normalize('google.com/search?sex=male&first=raj&middle=&last=shah')
            'http://google.com/search?first=raj&last=shah&sex=male'
            >>> Factory().normalize('google.com/search?sex=male&first=rajiv&middle=bakulesh&last=shah')
            'http://google.com/search?first=rajiv&last=shah&middle=bakulesh&sex=male'
            >>> Factory().normalize('google.com/search?first=rajiv&last=shah&middle=bakulesh&sex=male')
            'http://google.com/search?first=rajiv&last=shah&middle=bakulesh&sex=male'
        """
        query = urllib.urlencode(sorted(cgi.parse_qsl(query)))
        return query

    def _normalize_escape_sequences(self, url):
        """Capitalize letters in percent-encoded character escape sequences.

        Examples:
            >>> Factory().normalize('google.com/a%c2%b1b')
            'http://google.com/a%C2%B1b'
            >>> Factory().normalize('google.com/a%c2%b1%b')
            'http://google.com/a%C2%B1%b'
            >>> Factory().normalize('google.com/a%c2%b1%b.html')
            'http://google.com/a%C2%B1%b.html'
            >>> Factory().normalize('google.com/a%c2%b1%b2.html')
            'http://google.com/a%C2%B1%B2.html'
        """
        reg_exp = r'%[0-9A-Fa-f][0-9A-Fa-f]'
        url = re.sub(reg_exp, lambda m: m.group().upper(), url)
        return url

    def _fetch(self, url, payload='', headers={}):
        """ """
        raise NotImplementedError

    def _grok(self, response, url):
        """ """
        raise NotImplementedError


class _AppEngineFetch(_BaseFetch):
    """ """

    def __init__(self):
        """ """
        self._exceptions = (InvalidURLError, DownloadError,
                            ResponseTooLargeError)

    def _fetch(self, url, payload='', headers={}):
        """ """
        method = POST if payload else GET
        return fetch(url, payload=payload, method=method, headers=headers,
                     allow_truncated=True, follow_redirects=True)

    def _grok(self, response, url):
        """ """
        url = self.normalize(response.headers.get('location', url))
        status_code = response.status_code
        mime_type = response.headers.get('content-type')
        content = response.content
        return url, status_code, mime_type, content


class _PythonFetch(_BaseFetch):
    """ """

    def __init__(self):
        """ """
        self._exceptions = (urllib2.URLError,)

    def _fetch(self, url, payload='', headers={}):
        """ """
        request = urllib2.Request(url, payload, headers)
        return urllib2.urlopen(request)

    def _grok(self, response, url):
        """ """
        url = self.normalize(response.geturl())
        status_code = response.code
        mime_type = response.headers.get('Content-Type')
        content = response.read()
        return url, status_code, mime_type, content


class Factory(object):
    """ """

    def __new__(Class, *args, **kwds):
        """ """
        if _on_app_engine:
            instance = _AppEngineFetch(*args, **kwds)
        else:
            instance = _PythonFetch(*args, **kwds)
        return instance


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=True)
