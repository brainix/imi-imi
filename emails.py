#------------------------------------------------------------------------------#
#   emails.py                                                                  #
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
"""Email functionality."""


import logging
import os

from google.appengine.api import mail
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from config import DEBUG, TEMPLATES


_log = logging.getLogger(__name__)


class RequestHandler(webapp.RequestHandler):
    """Email request handler, from which other request handlers inherit."""

    def _email_following(self, current_account, other_account):
        """ """
        current_user = current_account.user
        other_user = other_account.user
        current_email = current_user.email()
        other_email = other_user.email()
        current_nickname = current_user.nickname()
        other_nickname = other_user.nickname()
        text_path = os.path.join(TEMPLATES, 'email', 'following.txt')
        html_path = os.path.join(TEMPLATES, 'email', 'following.html')
        body = template.render(text_path, locals(), debug=DEBUG)
        html = template.render(html_path, locals(), debug=DEBUG)
        mail.send_mail(
            sender=current_email,
            to=other_email,
            subject='%s Following Your imi-imi Bookmarks' % current_nickname,
            body=body,
            html=html,
        )

    def _email_rebookmark(self):
        """ """
        pass
