/*----------------------------------------------------------------------------*\
 |  init.js                                                                   |
 |                                                                            |
 |  Copyright (c) 2009-2010, Code A La Mode, original authors.                |
 |                                                                            |
 |      This file is part of imi-imi.                                         |
 |                                                                            |
 |      imi-imi is free software; you can redistribute it and/or modify       |
 |      it under the terms of the GNU General Public License as published by  |
 |      the Free Software Foundation, either version 3 of the License, or     |
 |      (at your option) any later version.                                   |
 |                                                                            |
 |      imi-imi is distributed in the hope that it will be useful,            |
 |      but WITHOUT ANY WARRANTY; without even the implied warranty of        |
 |      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         |
 |      GNU General Public License for more details.                          |
 |                                                                            |
 |      You should have received a copy of the GNU General Public License     |
 |      along with imi-imi.  If not, see <http://www.gnu.org/licenses/>.      |
\*----------------------------------------------------------------------------*/


/*----------------------------------------------------------------------------*\
 |                                    $()                                     |
\*----------------------------------------------------------------------------*/

$(function() {
    // Hooray, a page has been loaded!
    $.initSearch();
    $.initBookmarks();
    $.initAccount();
    $.preloadImagesArgs("/static-files/images/favicon.ico",
                        "/static-files/images/speech_balloon_tail.png",
                        "/static-files/images/throbber.gif");
});


/*----------------------------------------------------------------------------*\
 |            $.preloadImagesArgs() and $.preloadImagesSelector()             |
\*----------------------------------------------------------------------------*/

(function($) {
    var imageCache = [];

    $.preloadImagesArgs = function() {
        // Given arguments corresponding to URLs to images, preload those
        // images.
        if (document.images) {
            for (var index = arguments.length; index--;) {
                var cachedImage = document.createElement("img");
                cachedImage.src = arguments[index];
                imageCache.push(cachedImage);
            }
        }
    }

    $.preloadImagesSelector = function(selector) {
        // Given a jQuery selector, preload all of the images within that
        // section of the DOM.
        $(selector + " img").each(function(index) {
            $.preloadImagesArgs($(this).attr("src"));
        });
    }
})(jQuery)
