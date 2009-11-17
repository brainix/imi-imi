/*----------------------------------------------------------------------------*\
 |  init.js                                                                   |
 |                                                                            |
 |  Copyright (c) 2009, Code A La Mode, original authors.                     |
 |                                                                            |
 |      This file is part of grab-it.                                         |
 |                                                                            |
 |      grab-it is free software; you can redistribute it and/or modify       |
 |      it under the terms of the GNU General Public License as published by  |
 |      the Free Software Foundation, either version 3 of the License, or     |
 |      (at your option) any later version.                                   |
 |                                                                            |
 |      grab-it is distributed in the hope that it will be useful,            |
 |      but WITHOUT ANY WARRANTY; without even the implied warranty of        |
 |      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         |
 |      GNU General Public License for more details.                          |
 |                                                                            |
 |      You should have received a copy of the GNU General Public License     |
 |      along with grab-it.  If not, see <http://www.gnu.org/licenses/>.      |
\*----------------------------------------------------------------------------*/


const images = new Array(
    "/static-files/images/favicon.ico",
    "/static-files/images/throbber.gif"
);


/*----------------------------------------------------------------------------*\
 |                                    $()                                     |
\*----------------------------------------------------------------------------*/
$(function() {
    // Hooray, a page has been loaded!  Go through the DOM and modify the
    // behavior of every element that we want to bless with AJAX.  :-D

    $("#query").click(click_search);
    $("#query").blur(blur_search);
    $("#query").keyup(fetch_live_results);
    $("#query").keydown(scroll_live_results);
    $("#search").submit(search);

    $("#url_to_create").click(click_bookmark);
    $("#url_to_create").blur(blur_bookmark);
    $("#create_bookmark").submit(create_bookmark);
    $(".update_bookmark").submit(update_bookmark);
    $(".delete_bookmark").submit(delete_bookmark);
    $("#more_bookmarks form").submit(more_bookmarks);

    preload_images(images);
});


/*----------------------------------------------------------------------------*\
 |                              preload_images()                              |
\*----------------------------------------------------------------------------*/
function preload_images(images) {
    if (document.images) {
        for (index in images) {
            image = new Image();
            image.src = images[index];
        }
    }
}
