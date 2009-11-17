#------------------------------------------------------------------------------#
#   __init__.py                                                                #
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

"""File necessary to identify this directory as a Python package."""


import logging
import os
import sys


_log = logging.getLogger(__name__)


# Subtle:  By importing the "packages" package, we add the "packages" directory
# to the Python path.  This makes other package imports far more sensical.
_path = os.path.dirname(__file__)
if not _path in sys.path:
    sys.path.append(_path)
    _log.debug('added %s to Python path' % _path)
