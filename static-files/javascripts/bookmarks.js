/*----------------------------------------------------------------------------*\
 |  bookmarks.js                                                              |
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


const DEFAULT_BOOKMARK_TEXT = "enter a url to bookmark";

var more_bookmarks_clicked = false;


/*----------------------------------------------------------------------------*\
 |                              click_bookmark()                              |
\*----------------------------------------------------------------------------*/

function click_bookmark() {
    // The user has clicked into the "save bookmark" bar.  If the bar contains
    // the default explanatory text, clear it out to contain no text.

    if ($("#url_to_create").val() == DEFAULT_BOOKMARK_TEXT) {
        $("#url_to_create").val("");
    }
}


/*----------------------------------------------------------------------------*\
 |                              blur_bookmark()                               |
\*----------------------------------------------------------------------------*/

function blur_bookmark() {
    // The user has clicked out of the "save bookmark" bar.  If the bar contains
    // no text, populate it with the default explanatory text.

    if ($("#url_to_create").val() == "") {
        $("#url_to_create").val(DEFAULT_BOOKMARK_TEXT);
    }
}


/*----------------------------------------------------------------------------*\
 |                             create_bookmark()                              |
\*----------------------------------------------------------------------------*/

function create_bookmark() {
    // Modify the behavior of the create bookmark bar.

    $.ajax({
        type: "POST",
        url: "/users",
        data: "url_to_create=" + $("#url_to_create").val(),
        success: function(data, text_status) {
            $("#bookmark_list").prepend(data);
            $("#bookmark_list li.bookmark:hidden .update_bookmark").submit(update_bookmark);
            $("#bookmark_list li.bookmark:hidden .delete_bookmark").submit(delete_bookmark);
            $("#bookmark_list li.bookmark:hidden").slideDown("slow");
        },
    });

    // Cancel out the default behavior of the create bookmark form.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                             update_bookmark()                              |
\*----------------------------------------------------------------------------*/

function update_bookmark() {
    // Modify the behavior of the update bookmark buttons.

    var bookmark = $(this).closest("li")
    $.ajax({
        type: "POST",
        url: "/users",
        data: "key_to_update=" + $(this).find("input").val(),
        success: function(data, text_status) {
            bookmark.slideUp("slow", function() {
                bookmark.remove();
                $("#bookmark_list").prepend(data);
                $("#bookmark_list li.bookmark:hidden .update_bookmark").submit(update_bookmark);
                $("#bookmark_list li.bookmark:hidden .delete_bookmark").submit(delete_bookmark);
                $("#bookmark_list li.bookmark:hidden").slideDown("slow");
            });
        },
    });

    // Cancel out the default behavior of the update bookmark forms.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                             delete_bookmark()                              |
\*----------------------------------------------------------------------------*/

function delete_bookmark() {
    // Modify the behavior of the delete bookmark buttons.

    var bookmark = $(this).closest("li")
    $.ajax({
        type: "POST",
        url: "/users",
        data: "key_to_delete=" + $(this).find("input").val(),
        complete: function(xml_http_request, text_status) {
            bookmark.slideUp("slow", function() {
                bookmark.remove();
            });
        },
    });

    // Cancel out the default behavior of the delete bookmark forms.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                              more_bookmarks()                              |
\*----------------------------------------------------------------------------*/

function more_bookmarks() {
    // Modify the behavior of the more bookmarks button.

    if (!more_bookmarks_clicked) {
        more_bookmarks_clicked = true;
        var more_url = $("#more_url").val();
        $.ajax({
            type: "GET",
            url: more_url,
            success: function(data, text_status) {
                $("#bookmark_list #more_bookmarks").remove();
                $("#bookmark_list").append(data);
                $("#bookmark_list li.bookmark:hidden .update_bookmark").submit(update_bookmark);
                $("#bookmark_list li.bookmark:hidden .delete_bookmark").submit(delete_bookmark);
                $("#bookmark_list #more_bookmarks form").submit(more_bookmarks);
                $("#bookmark_list li.bookmark:hidden").slideDown("slow");
            },
        });
        more_bookmarks_clicked = false;
    }

    // Cancel out the default behavior of the more bookmarks form.
    return false;
}
