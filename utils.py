#!/usr/bin/env python

#------------------------------------------------------------------------------#
#   utils.py                                                                   #
#                                                                              #
#   Copyright (c) 2009, Code A La Mode, original authors.                      #
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

"""Utility functions for auto-tagging HTML."""


# Originally, I'd used urllib2 and BeautifulSoup 3.1.0, but those packages were
# too fragile on tenuous internet connections and malformed HTML.  So I switched
# to urlfetch and BeautifulSoup 3.0.7a for more robust HTML fetching and
# parsing.  But if we can't import urlfetch, we're not running on Google App
# Engine, so we fall back to urllib2.


from __future__ import with_statement
import cgi
import hashlib
import logging
import operator
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

import packages
from beautifulsoup.BeautifulSoup import BeautifulSoup
from beautifulsoup.BeautifulSoup import Comment
from beautifulsoup.BeautifulSoup import SGMLParseError
from nltk.stem.porter import PorterStemmer

from config import STOP_WORDS, FETCH_GOOD_STATUSES, FETCH_DOCUMENT_INDEXES
from config import FETCH_BAD_TAGS, FETCH_GOOD_TAGS, FETCH_MIN_COUNT


_log = logging.getLogger(__name__)
stemmer = PorterStemmer()


def tokenize_url(url):
    """Parse web content into a URL, MIME type, title, word list, and hash.

    Example usage:
        >>> url = 'http://www.gutenberg.org/files/11/11-h/11-h.htm'
        >>> url, mime_type, title, words, hash = tokenize_url(url)
        >>> title
        u"\\r\\n    Alice's Adventures in Wonderland,\\r\\n    by Lewis Carroll\\r\\n"
    """
    _log.debug('tokenizing %s' % url)
    url, status_code, mime_type, content = fetch_content(url)
    if content is None:
        _log.warning("couldn't tokenize %s (couldn't fetch content)" % url)
        title, words, hash = url, [], None
    else:
        title, words, hash = tokenize_html(content)
        if (title, words, hash) == (None, None, None):
            title, words, hash = url, [], None
            _log.warning("couldn't tokenize %s (couldn't soupify HTML)" % url)
        else:
            if title is None:
                title = url
            _log.debug('tokenized %s' % url)
    return url, mime_type, title, words, hash


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
        'http://google.com/'
        >>> normalize_url('google.com/document.html#location')
        'http://google.com/document.html'
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

    # Remove the fragment (or intra-document location).
    fragment = ''

    # Assemble the munged scheme, host, path, parameters, query, and fragment
    # back into a URL.
    url = urlparse.urlunparse((scheme, host, path, params, query, fragment,))

    # Capitalize letters in percent-encoded character escape sequences.
    url = re.sub(r'%[0-9A-Fa-f][0-9A-Fa-f]', lambda m: m.group().upper(), url)

    _log.debug('normalized to %s' % url)
    return url


def tokenize_html(html):
    """Parse an HTML document into a title, word list, and hash."""
    try:
        convert_entities = BeautifulSoup.ALL_ENTITIES
        soup = BeautifulSoup(html, convertEntities=convert_entities)
    except (SGMLParseError, TypeError), e:
        title, words, hash = None, None, None
    else:
        soup = _remove_garbage(soup)
        title = _extract_title(soup)
        words = _extract_words_from_soup(soup)
        hash = hashlib.md5(html).hexdigest()
    return title, words, hash


def _remove_garbage(soup, uninteresting_tags=FETCH_BAD_TAGS):
    """Given soup, strip out garbage that wouldn't help us auto-tag."""

    def remove_tags(soup, tag_names):
        """Given soup, strip out all of the tags with the specified names."""
        for tag_name in tag_names:
            [tag.extract() for tag in soup.findAll(tag_name)]
        return soup

    soup = remove_tags(soup, uninteresting_tags)
    comments = soup.findAll(text=lambda text:isinstance(text, Comment))
    [comment.extract() for comment in comments]
    return soup


def _extract_title(soup):
    """Given soup, return its title if specified."""
    _log.debug('extracting title')
    try:
        title = unicode(soup.findAll('title')[0].contents[0])
    except IndexError:
        _log.warning("couldn't extract title (not HTML, invalid markup, or " +
                     "no title specified?)")
    else:
        _log.debug('extracted title')
        return title


def _extract_words_from_soup(soup, interesting_tags=FETCH_GOOD_TAGS):
    """Given soup, return a list of all of its words."""
    tags = soup.findAll(interesting_tags)
    html = [str(tag) for tag in tags]
    html = ' '.join(html)
    if html:
        soup = BeautifulSoup(html)
    words = soup.findAll(text=True)
    words = ' '.join(words)
    return extract_words_from_string(words)


def extract_words_from_string(words):
    """Given a string, return a list of all of its words."""

    def remove_html_entities(s):
        """Remove a string's HTML entities."""
        return re.sub(r'&#?[A-Za-z0-9]+?;', '', s)

    def nonbreaking_char(c):
        """If the specified character shouldn't break a word, return True."""
        nonbreaking_chars = ('\'', u'\u2019',)
        return c.isalnum() or c in nonbreaking_chars

    def remove_extra_spaces(s):
        """Remove a string's extra spaces."""
        def remove_dupe_spaces(s1):
            """Consolidate all space-only sub-strings into single spaces."""
            s2 = s1.replace('  ', ' ')
            return s2 if s2 == s1 else remove_dupe_spaces(s2)
        return remove_dupe_spaces(s.strip())

    words = remove_html_entities(words)
    words = [(c.lower() if c.isalnum() else '' if nonbreaking_char(c) else ' ')
             for c in words]
    words = ''.join(words)
    words = remove_extra_spaces(words)
    words = words.split()
    words = [word for word in words if not word.isdigit()]
    return words


def read_stop_words(filename=STOP_WORDS):
    """Read the stop words - words that are too common to be useful as tags."""
    _log.debug('reading stop words %s' % filename)
    stop_words, hash = [], None
    try:
        with open(filename) as file_obj:
            for word in file_obj:
                stop_words.append(word.strip())
            file_obj.seek(0)
            hash = hashlib.md5(file_obj.read()).hexdigest()
    except IOError:
        _log.critical("couldn't read stop words %s (IOError)" % filename)
    _log.debug('read stop words %s' % filename)
    return stop_words, hash


def auto_tag(words, stop_words, min_count=FETCH_MIN_COUNT):
    """Given lists of words and stop words, return a list of tags."""
    _log.debug('auto tagging')

    # First, go through the word list, convert the words to stems, and make the
    # stems into tags.
    tags, max_count = {}, 0
    for word in [word for word in set(words) if not word in stop_words]:
        tag = {'stem': stemmer.stem(word), 'word': word}
        tag['count'] = float(words.count(word))
        try:
            tags[tag['stem']]['count'] += tag['count']
        except KeyError:
            tags[tag['stem']] = tag
        # Keep track of the largest tag count so we can normalize the tags'
        # counts later.
        if max_count < tags[tag['stem']]['count']:
            max_count = tags[tag['stem']]['count']

    # Next, normalize the tags' counts such that they're all between 0 and 1.
    # Also, strip out and throw away the insignificant tags.
    tmp, tags = tags.values(), []
    for tag in tmp:
        tag['count'] /= max_count
        if tag['count'] >= min_count:
            tags.append(tag)

    # Finally, sort the tags alphabetically and return the tag list.
    tags = sorted(tags, key=operator.itemgetter('word'))
    _log.debug('auto tagged')
    return tags


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=True)
