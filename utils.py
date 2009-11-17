#!/usr/bin/env python

#------------------------------------------------------------------------------#
#   utils.py                                                                   #
#                                                                              #
#   Copyright (c) 2009, Code A La Mode, original authors.                      #
#                                                                              #
#       This file is part of grab-it.                                          #
#                                                                              #
#       grab-it is free software; you can redistribute it and/or modify        #
#       it under the terms of the GNU General Public License as published by   #
#       the Free Software Foundation, either version 3 of the License, or      #
#       (at your option) any later version.                                    #
#                                                                              #
#       grab-it is distributed in the hope that it will be useful,             #
#       but WITHOUT ANY WARRANTY; without even the implied warranty of         #
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
#       GNU General Public License for more details.                           #
#                                                                              #
#       You should have received a copy of the GNU General Public License      #
#       along with grab-it.  If not, see <http://www.gnu.org/licenses/>.       #
#------------------------------------------------------------------------------#

"""Bookmark index logic - utility functions for auto-tagging HTML."""


# Originally, I'd used urllib2 and BeautifulSoup 3.1.0, but those packages were
# too fragile on tenuous internet connections and malformed HTML.  So I switched
# to urlfetch and BeautifulSoup 3.0.7a for more robust HTML fetching and
# parsing.  But if we can't import urlfetch, we're not running on Google App
# Engine, so we fall back to urllib2.


from __future__ import with_statement
import hashlib
import logging
import operator
import re

try:
    from google.appengine.api.urlfetch import fetch
    from google.appengine.api.urlfetch import InvalidURLError
    from google.appengine.api.urlfetch import DownloadError
    from google.appengine.api.urlfetch import ResponseTooLargeError
    _exceptions = (InvalidURLError, DownloadError, ResponseTooLargeError)
except ImportError:
    import urllib2
    _exceptions = (urllib2.URLError,)

import packages
from beautifulsoup.BeautifulSoup import BeautifulSoup
from beautifulsoup.BeautifulSoup import Comment
from beautifulsoup.BeautifulSoup import SGMLParseError
from nltk.stem.porter import PorterStemmer

from config import STOP_WORDS, FETCH_DEFAULT_URL, FETCH_GOOD_STATUSES
from config import FETCH_BAD_TAGS, FETCH_GOOD_TAGS, FETCH_MIN_COUNT


_log = logging.getLogger(__name__)
stemmer = PorterStemmer()


def tokenize_url(url=FETCH_DEFAULT_URL):
    """Fetch web content and parse it into a title, word list, and hash.

    Example usage:
        >>> url = 'http://www.gutenberg.org/files/11/11-h/11-h.htm'
        >>> mime_type, title, words, hash = tokenize_url(url)
        u"Alice's Adventures in Wonderland,\\r\\n by Lewis Carroll"
    """
    _log.debug('tokenizing %s' % url)
    status_code, mime_type, content = fetch_content(url=url)
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
    return mime_type, title, words, hash


def fetch_content(url=FETCH_DEFAULT_URL, status_codes=FETCH_GOOD_STATUSES):
    """Retrieve content from the web.  Make sure the status code is OK.

    That's "make sure the status code is OK" as in "okay," *not* "0K" as in
    "zero kilobytes."  Just in case there was any confusion.
    """
    _log.debug('fetching %s' % url)
    try:
        try:
            response = fetch(url, allow_truncated=True)
        except NameError:
            response = urllib2.urlopen(url)
    except _exceptions, e:
        # Oops.  Either the URL wasn't valid (probably wasn't fully qualified -
        # didn't begin with http:// or https://), or there was a problem
        # retrieving the data.
        _log.warning("couldn't fetch %s (%s)" % (url, type(e)))
        status_code, mime_type, content = None, '', None
    else:
        try:
            status_code = response.status_code
            mime_type = response.headers.get('content-type')
            content = response.content
        except AttributeError:
            status_code = response.code
            mime_type = response.headers.get('Content-Type')
            content = response.read()
        if status_code not in status_codes:
            # Oops.  We retrieved some data, but the server returned an
            # unacceptable status code.
            _log.warning('fetched %s, but status code %s' % (url, status_code))
            status_code, mime_type, content = None, '', None
    if ';' in mime_type:
        mime_type = mime_type.split(';', 1)[0]
    _log.debug('fetched %s' % url)
    return status_code, mime_type, content


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
        """Remove a string's HTML entitites."""
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


def auto_tag(words=tuple(), stop_words=tuple(), min_count=FETCH_MIN_COUNT):
    """Given lists of words and stop words, return a list of tags."""
    _log.debug('auto tagging')

    # First, go through the word list, convert the words to stems, and make the
    # stems into tags.
    tags, max_count = {}, 0
    for word in [word for word in set(words) if not word in stop_words]:
        tag = {}
        tag['stem'], tag['word'] = stemmer.stem(word), word
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
    doctest.testmod()
