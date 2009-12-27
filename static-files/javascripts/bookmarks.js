/*----------------------------------------------------------------------------*\
 |  bookmarks.js                                                              |
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


const DEFAULT_CREATE_BOOKMARK_TEXT = "enter a url to bookmark";

var create_bookmark_submitted = false;
var more_bookmarks_clicked = false;


/*----------------------------------------------------------------------------*\
 |                              init_bookmarks()                              |
\*----------------------------------------------------------------------------*/

function init_bookmarks() {
    // Hooray, a page has been loaded!

    // Go through the DOM and modify the behavior of every element that we want
    // to bless with AJAX.
    $("#url_to_create").focus(focus_create_bookmark);
    $("#url_to_create").blur(blur_create_bookmark);
    $("#create_bookmark").submit(create_bookmark);
    $(".update_bookmark").submit(update_bookmark);
    $(".delete_bookmark").submit(delete_bookmark);
    $("#more_bookmarks form").submit(more_bookmarks);

    // Make sure that the "save bookmark" bar displays the default explanatory
    // text.
    $("#url_to_create").val(DEFAULT_CREATE_BOOKMARK_TEXT);

    // For some reason, sometimes (particularly when we're clicking
    // back/forward through the pages in the site) our button labels get
    // confused.  Straighten them out.
    $("#create_bookmark .submit").val("save bookmark");
    $(".update_bookmark .submit").val("update");
    $(".delete_bookmark .submit").val("delete");
}


/*----------------------------------------------------------------------------*\
 |                          focus_create_bookmark()                           |
\*----------------------------------------------------------------------------*/

function focus_create_bookmark() {
    // The user has clicked or tabbed into the "save bookmark" bar.  If the bar
    // contains the default explanatory text, then clear it out to contain no
    // text.

    if ($("#url_to_create").val() == DEFAULT_CREATE_BOOKMARK_TEXT) {
        $("#url_to_create").val("");
    }
}


/*----------------------------------------------------------------------------*\
 |                           blur_create_bookmark()                           |
\*----------------------------------------------------------------------------*/

function blur_create_bookmark() {
    // The user has clicked or tabbed out of the "save bookmark" bar.  If the
    // bar contains no text, then populate it with the default explanatory
    // text.

    if ($("#url_to_create").val() == "") {
        $("#url_to_create").val(DEFAULT_CREATE_BOOKMARK_TEXT);
    }
}


/*----------------------------------------------------------------------------*\
 |                             create_bookmark()                              |
\*----------------------------------------------------------------------------*/

function create_bookmark() {
    // Modify the behavior of the create bookmark bar.

    if (!create_bookmark_submitted) {
        // Don't allow the user to click the "save bookmark" button again,
        // until we're done with this procedure.
        create_bookmark_submitted = true;

        // Transform the "save bookmark" button into a spinner.
        $("#url_to_create").addClass("url_to_create_with_throbber_shown");
        $("#create_bookmark_throbber").show();
        $("#content .create_bookmark .submit").hide();

        // Make the AJAX request to create the bookmark.  If we succeed, then
        // clear out the URL that the user entered into the "save bookmark" bar
        // and slide down the new bookmark's HTML snippet.  Whether we succeed
        // or fail, transform the spinner back into the "save bookmark" button.
        $.ajax({
            type: "POST",
            url: "/users",
            data: "url_to_create=" + $("#url_to_create").val(),
            success: function(data, text_status) {
                // Hooray, we succeed!  Clear out the URL that the user entered
                // into the "save bookmark" bar.  This facilitates the rapid
                // entry of multiple URLs.
                $("#url_to_create").val("");

                // Slide down the new bookmark's HTML snippet.
                $("#bookmark_list").prepend(data);
                $("#bookmark_list li.bookmark:hidden .update_bookmark").submit(update_bookmark);
                $("#bookmark_list li.bookmark:hidden .delete_bookmark").submit(delete_bookmark);
                $("#bookmark_list li.bookmark:hidden").slideDown("slow");
            },
            complete: function(xml_http_request, text_status) {
                // Transform the spinner back into the "save bookmark" button.
                $("#content .create_bookmark .submit").show();
                $("#create_bookmark_throbber").hide();
                $("#url_to_create").removeClass("url_to_create_with_throbber_shown");

                // We're done with this procedure.  Allow the user to click the
                // "save bookmark" button again.
                create_bookmark_submitted = false;
            },
        });
    }

    // Cancel out the default behavior of the create bookmark form.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                             update_bookmark()                              |
\*----------------------------------------------------------------------------*/

function update_bookmark() {
    // Modify the behavior of the "update bookmark" buttons.

    var bookmark_key = $(this).find("input[name='bookmark_key']").val();
    var reference_key = $(this).find("input[name='reference_key_to_update']").val();
    var stale_bookmark = $(this).closest("li");
    var element_to_scroll = $.browser.safari ? "body" : "html";
    var offset = $("#create_bookmark").offset().top;

    $.ajax({
        type: "POST",
        url: "/users",
        data: {
            "bookmark_key": bookmark_key,
            "reference_key_to_update": reference_key,
        },
        success: function(data, text_status) {
            stale_bookmark.slideUp("slow", function() {
                stale_bookmark.remove();
                $(element_to_scroll).animate({scrollTop: offset}, "slow", "swing", function() {
                    $("#bookmark_list").prepend(data);
                    $("#bookmark_list li.bookmark:hidden .update_bookmark").submit(update_bookmark);
                    $("#bookmark_list li.bookmark:hidden .delete_bookmark").submit(delete_bookmark);
                    $("#bookmark_list li.bookmark:hidden").slideDown("slow");
                });
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
    // Modify the behavior of the "delete bookmark" buttons.

    var confirm_delete = confirm("Delete bookmark?");

    if (confirm_delete) {
        // OK.  The user has clicked a "delete bookmark" button and confirmed
        // that that's what he/she meant to do.
        var bookmark_key = $(this).find("input[name='bookmark_key']").val();
        var reference_key = $(this).find("input[name='reference_key_to_delete']").val();
        var bookmark = $(this).closest("li");

        // Make the AJAX request to delete the bookmark.  Whether we succeed or
        // fail, slide up and remove the bookmark's HTML snippet.
        $.ajax({
            type: "POST",
            url: "/users",
            data: {
                "bookmark_key": bookmark_key,
                "reference_key_to_delete": reference_key,
            },
            complete: function(xml_http_request, text_status) {
                bookmark.slideUp("slow", function() {
                    bookmark.remove();
                });
            },
        });
    }

    // Cancel out the default behavior of the delete bookmark forms.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                              more_bookmarks()                              |
\*----------------------------------------------------------------------------*/

function more_bookmarks() {
    // Modify the behavior of the "more bookmarks" button.

    var more_url = $("#more_url").val();

    if (!more_bookmarks_clicked) {
        // Don't allow the user to click the "more bookmarks" button again,
        // until we're done with this procedure.
        more_bookmarks_clicked = true;

        // Transform the "more bookmarks" button into a spinner.
        $("#more_bookmarks_throbber").show();
        $("#more_bookmarks .more_bookmarks .submit").hide();

        // Make the AJAX request to get more bookmarks.  If we succeed, then
        // get rid of the spinner, munge the additional bookmarks' HTML
        // snippet, and slide down the additional bookmarks' HTML snippet.
        // Otherwise, transform the spinner back into the "more bookmarks"
        // button.
        $.ajax({
            type: "GET",
            url: more_url,
            success: function(data, text_status) {
                // Hooray, we succeeded!  Get rid of the spinner.
                $("#bookmark_list #more_bookmarks").remove();

                // Sprinkle some JavaScript magic on the more bookmarks HTML
                // snippet - modify the behavior of the update, delete, and
                // more bookmarks buttons.
                $("#bookmark_list").append(data);
                $("#bookmark_list li.bookmark:hidden .update_bookmark").submit(update_bookmark);
                $("#bookmark_list li.bookmark:hidden .delete_bookmark").submit(delete_bookmark);
                $("#bookmark_list #more_bookmarks form").submit(more_bookmarks);

                // Finally, slide down the more bookmarks HTML snippet.
                // Subtle: If there are yet more bookmarks, then this
                // additional bookmarks' HTML snippet will include the code for
                // the new "more bookmarks" button and the new spinner, so
                // there's nothing more required of us there.
                $("#bookmark_list li.bookmark:hidden").slideDown("slow");
            },
            error: function(xml_http_request, text_status, error_thrown) {
                // Oops, we failed.  :-(  Transform the spinner back into the
                // "more bookmarks" button to allow the user to click it and
                // try again.
                $("#more_bookmarks .more_bookmarks .submit").show();
                $("#more_bookmarks_throbber").hide();
            },
            complete: function(xml_http_request, text_status) {
                // We're done with this procedure.  Allow the user to click the
                // "more bookmark" button again.
                more_bookmarks_clicked = false;
            },
        });
    }

    // Cancel out the default behavior of the more bookmarks form.
    return false;
}
