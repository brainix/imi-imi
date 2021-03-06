#------------------------------------------------------------------------------#
#   filters.py                                                                 #
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
"""Custom Django page template filters."""


import datetime
import hashlib
import logging
import math
import urllib
import urlparse

from google.appengine.ext.webapp.template import create_template_register

from config import AUDIO_MIME_TYPES, IMAGE_MIME_TYPES, YOUTUBE_BASE_URLS
from config import TITLE_MAX_WORDS, TITLE_SLICE_POINTS
from config import GRAVATAR_SIZE, GRAVATAR_RATING, GRAVATAR_DEFAULT
import models


_log = logging.getLogger(__name__)
register = create_template_register()


@register.filter
def beautify_title(bookmark, max_words=TITLE_MAX_WORDS,
                   slice_points=TITLE_SLICE_POINTS):
    """Convert a bookmark's title into something presentable."""
    title = bookmark.title or bookmark.url
    if title != bookmark.url:
        # The bookmark's title is different from its URL.  That means that we
        # were able to parse out the title from the HTML when we indexed the
        # bookmark, and that the title is something meaningful.  All that we
        # have to do now is to make sure that the title is short enough.  If
        # it's too long, then lop off some words, preferably splitting at
        # punctuation, so that we're left with something still meaningful.
        words = title.split()
        if len(words) > max_words:
            words = words[:max_words]
            title = ' '.join(words)
            slice_indices = [title.rfind(token) for token in slice_points]
            slice_index = max(slice_indices)
            if slice_index != -1:
                title = title[:slice_index]
        title = title.strip()
    else:
        # The bookmark's title is the same as its URL.  That means that we
        # weren't able to parse out the title from the HTML when we indexed the
        # bookmark.
        if is_image(bookmark) or is_audio(bookmark):
            # The URL points to some non-HTML (image or audio) file.  Strip off
            # the extra gunk and return just the filename as the title.
            title = urlparse.urlparse(title).path.rsplit('/', 1)[-1]
    return title


@register.filter
def beautify_url(url):
    """ """
    scheme, host, path, params, query, fragment = urlparse.urlparse(url)
    return host


@register.filter
def user_to_gravatar(user, size=0):
    """Convert a user object into a Gravatar (globally recognized avatar) URL.

    For more information, see:
        http://en.gravatar.com/site/implement/url
    """
    base_url = 'http://www.gravatar.com/avatar/%s.jpg?%s'
    email_hash = hashlib.md5(user.email().lower()).hexdigest()
    query_dict = {'size': size if size else GRAVATAR_SIZE,
                  'rating': GRAVATAR_RATING, 'default': GRAVATAR_DEFAULT,}
    query_str = urllib.urlencode(query_dict)
    gravatar = base_url % (email_hash, query_str)
    return gravatar


@register.filter
def beautify_datetime(dt1):
    """Convert a Python datetime object into a pleasantly readable string."""
    dt = datetime.datetime
    dt2 = dt.now()
    suffix = 'ago' if dt1 < dt2 else 'from now'
    after, before = (dt1, dt2) if dt1 > dt2 else (dt2, dt1)
    diff = after - before
    diff_minutes = diff.seconds / 60
    diff_hours = diff_minutes / 60
    diff_calendar_days = (dt(after.year, after.month, after.day) -
                          dt(before.year, before.month, before.day)).days

    beautified_datetime = 'a long time ago in a galaxy far, far away'
    if after == before:
        beautified_datetime = 'right now'
    elif diff.days == 0 and diff_hours == 0 and diff_minutes == 0:
        beautified_datetime = 'seconds ' + suffix
    elif diff.days == 0 and diff_hours == 0 and diff_minutes == 1:
        beautified_datetime = '1 minute ' + suffix
    elif diff.days == 0 and diff_hours == 0:
        beautified_datetime = str(diff_minutes) + ' minutes ' + suffix
    elif diff.days == 0 and diff_hours == 1:
        beautified_datetime = '1 hour ' + suffix
    elif diff.days == 0:
        beautified_datetime = str(diff_hours) + ' hours ' + suffix
    elif diff_calendar_days == 1:
        beautified_datetime = 'yesterday' if suffix == 'ago' else 'tomorrow'
    elif diff_calendar_days < 7:
        beautified_datetime = dt1.strftime('on %a')
    else:
        beautified_datetime = dt1.strftime('on %b %d, %y')
    return beautified_datetime


@register.filter
def style_tag(bookmark, word, size_prefix='size', color_prefix='color',
              scale=8):
    """For a bookmark & a word, compute the style (size & color) for the tag."""
    try:
        index = bookmark.words.index(word)
    except ValueError:
        count = 0
    else:
        count = bookmark.counts[index]
    value = str(int(math.ceil(scale * count) - 1))
    return size_prefix + value + ' ' + color_prefix + value


@register.filter
def is_image(bookmark):
    """Return whether or not a bookmark points to an image file."""
    return bookmark.mime_type in IMAGE_MIME_TYPES


@register.filter
def is_audio(bookmark):
    """Return whether or not a bookmark points to an audio file."""
    return bookmark.mime_type in AUDIO_MIME_TYPES


@register.filter
def is_youtube_video(bookmark):
    """Return whether or not a bookmark points to a YouTube video."""
    return bookmark.url.startswith(YOUTUBE_BASE_URLS)


@register.filter
def make_youtube_url(bookmark):
    """For a YouTube vid bookmark, construct a URL corresponding to a player."""
    if is_youtube_video(bookmark):
        if bookmark.url.startswith('http://youtube.com/watch?v='):
            url = bookmark.url.replace('http://youtube.com/watch?v=',
                                       'http://youtube.com/v/')
        elif bookmark.url.startswith('http://www.youtube.com/watch?v='):
            url = bookmark.url.replace('http://www.youtube.com/watch?v=',
                                       'http://www.youtube.com/v/')
        url += '&enablejsapi=1&playerapiid=ytplayer'
    else:
        url = bookmark.url
        _log.error('trying to make a YouTube player URL out of: %s' % url)
    return url


@register.filter
def following(current_user, target_user):
    """Return whether or not the current user is following the target user."""
    current_email = current_user.email()
    current_account_key = models.Account.key_name(current_email)
    current_account = models.Account.get_by_key_name(current_account_key)
    try:
        return_value = target_user in current_account.following
    except AttributeError:
        return_value = False
    return return_value
