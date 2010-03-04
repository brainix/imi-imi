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

var createBookmarkSubmitted = false;
var moreBookmarksClicked = false;


/*----------------------------------------------------------------------------*\
 |                              initBookmarks()                               |
\*----------------------------------------------------------------------------*/

function initBookmarks() {
    // Hooray, a page has been loaded!

    // Go through the DOM and modify the behavior of every element that we want
    // to bless with AJAX.
    $("input#url_to_create").focus(focusCreateBookmark);
    $("input#url_to_create").blur(blurCreateBookmark);
    $("form#create_bookmark").submit(createBookmark);
    $("div.update_bookmark").submit(updateBookmark);
    $("div.delete_bookmark").submit(deleteBookmark);
    $("li#more_bookmarks form").submit(moreBookmarks);

    if ($("input#url_to_create").length != 0 && $("input#url_to_create").val() != DEFAULT_CREATE_BOOKMARK_TEXT) {
        createBookmark();
    }
    else {
        // Make sure that the "save bookmark" bar displays the default
        // explanatory text.
        $("input#url_to_create").val(DEFAULT_CREATE_BOOKMARK_TEXT);
    }

    // For some reason, sometimes (particularly when we're clicking
    // back/forward through the pages in the site) our button labels get
    // confused.  Straighten them out.
    $("form#create_bookmark input.submit").val("save bookmark");
    $("div.update_bookmark input.submit").val("update");
    $("div.delete_bookmark input.submit").val("delete");
    $("li#more_bookmarks input.submit").val("more bookmarks");
}


/*----------------------------------------------------------------------------*\
 |                           focusCreateBookmark()                            |
\*----------------------------------------------------------------------------*/

function focusCreateBookmark() {
    // The user has clicked or tabbed into the "save bookmark" bar.  If the bar
    // contains the default explanatory text, then clear it out to contain no
    // text.

    if ($("input#url_to_create").val() == DEFAULT_CREATE_BOOKMARK_TEXT) {
        $("input#url_to_create").val("");
    }
}


/*----------------------------------------------------------------------------*\
 |                            blurCreateBookmark()                            |
\*----------------------------------------------------------------------------*/

function blurCreateBookmark() {
    // The user has clicked or tabbed out of the "save bookmark" bar.  If the
    // bar contains no text, then populate it with the default explanatory
    // text.

    if ($("input#url_to_create").val() == "") {
        $("input#url_to_create").val(DEFAULT_CREATE_BOOKMARK_TEXT);
    }
}


/*----------------------------------------------------------------------------*\
 |                              createBookmark()                              |
\*----------------------------------------------------------------------------*/

function createBookmark() {
    // Modify the behavior of the create bookmark bar.

    if (!createBookmarkSubmitted) {
        // Don't allow the user to click the "save bookmark" button again,
        // until we're done with this procedure.
        createBookmarkSubmitted = true;

        // Transform the "save bookmark" button into a spinner.
        $("input#url_to_create").addClass("url_to_create_with_throbber_shown");
        $("#create_bookmark_throbber").show();
        $("#content div.create_bookmark input.submit").hide();

        // Make the AJAX request to create the bookmark.  If we succeed, then
        // clear out the URL that the user entered into the "save bookmark" bar
        // and slide down the new bookmark's HTML snippet.  Whether we succeed
        // or fail, transform the spinner back into the "save bookmark" button.
        $.ajax({
            type: "POST",
            url: "/users",
            data: "url_to_create=" + $("input#url_to_create").val(),
            success: function(data, textStatus) {
                // Hooray, we succeed!  Clear out the URL that the user entered
                // into the "save bookmark" bar and set the input focus on that
                // bar.  This facilitates the rapid entry of multiple URLs.
                $("input#url_to_create").val("");
                $("input#url_to_create").focus();

                // Slide down the new bookmark's HTML snippet.
                $("ul#bookmark_list").prepend(data);
                $("ul#bookmark_list li.bookmark:hidden div.update_bookmark").submit(updateBookmark);
                $("ul#bookmark_list li.bookmark:hidden div.delete_bookmark").submit(deleteBookmark);
                $("ul#bookmark_list li.bookmark:hidden").slideDown("slow");
            },
            complete: function(xmlHttpRequest, textStatus) {
                // Transform the spinner back into the "save bookmark" button.
                $("#content div.create_bookmark input.submit").show();
                $("#create_bookmark_throbber").hide();
                $("input#url_to_create").removeClass("url_to_create_with_throbber_shown");

                // We're done with this procedure.  Allow the user to click the
                // "save bookmark" button again.
                createBookmarkSubmitted = false;
            },
        });
    }

    // Cancel out the default behavior of the create bookmark form.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                              updateBookmark()                              |
\*----------------------------------------------------------------------------*/

function updateBookmark() {
    // Modify the behavior of the "update bookmark" buttons.

    var bookmarkKey = $(this).find("input[name='bookmark_key']").val();
    var referenceKey = $(this).find("input[name='reference_key_to_update']").val();
    var staleBookmark = $(this).closest("li");
    var elementToScroll = $.browser.safari ? "body" : "html";
    var offset = $("form#create_bookmark").offset().top;

    $.ajax({
        type: "POST",
        url: "/users",
        data: {
            "bookmark_key": bookmarkKey,
            "reference_key_to_update": referenceKey,
        },
        success: function(data, textStatus) {
            staleBookmark.slideUp("slow", function() {
                staleBookmark.remove();
                $(elementToScroll).animate({scrollTop: offset}, "slow", "swing", function() {
                    $("ul#bookmark_list").prepend(data);
                    $("ul#bookmark_list li.bookmark:hidden div.update_bookmark").submit(updateBookmark);
                    $("ul#bookmark_list li.bookmark:hidden div.delete_bookmark").submit(deleteBookmark);
                    $("ul#bookmark_list li.bookmark:hidden").slideDown("slow");
                });
            });
        },
    });

    // Cancel out the default behavior of the update bookmark forms.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                              deleteBookmark()                              |
\*----------------------------------------------------------------------------*/

function deleteBookmark() {
    // Modify the behavior of the "delete bookmark" buttons.

    var confirmDelete = confirm("Delete bookmark?");

    if (confirmDelete) {
        // OK.  The user has clicked a "delete bookmark" button and confirmed
        // that that's what he/she meant to do.
        var bookmarkKey = $(this).find("input[name='bookmark_key']").val();
        var referenceKey = $(this).find("input[name='reference_key_to_delete']").val();
        var bookmark = $(this).closest("li");

        // Make the AJAX request to delete the bookmark.  Whether we succeed or
        // fail, slide up and remove the bookmark's HTML snippet.
        $.ajax({
            type: "POST",
            url: "/users",
            data: {
                "bookmark_key": bookmarkKey,
                "reference_key_to_delete": referenceKey,
            },
            complete: function(xmlHttpRequest, textStatus) {
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
 |                              moreBookmarks()                               |
\*----------------------------------------------------------------------------*/

function moreBookmarks() {
    // Modify the behavior of the "more bookmarks" button.

    var moreUrl = $("input#more_url").val();

    if (!moreBookmarksClicked) {
        // Don't allow the user to click the "more bookmarks" button again,
        // until we're done with this procedure.
        moreBookmarksClicked = true;

        // Transform the "more bookmarks" button into a spinner.
        $("div#more_bookmarks_throbber").show();
        $("li#more_bookmarks input.submit").hide();

        // Make the AJAX request to get more bookmarks.  If we succeed, then
        // get rid of the spinner, munge the additional bookmarks' HTML
        // snippet, and slide down the additional bookmarks' HTML snippet.
        // Otherwise, transform the spinner back into the "more bookmarks"
        // button.
        $.ajax({
            type: "GET",
            url: moreUrl,
            success: function(data, textStatus) {
                // Hooray, we succeeded!  Get rid of the spinner.
                $("ul#bookmark_list li#more_bookmarks").remove();

                // Sprinkle some JavaScript magic on the more bookmarks HTML
                // snippet - modify the behavior of the update, delete, and
                // more bookmarks buttons.
                $("ul#bookmark_list").append(data);
                $("ul#bookmark_list li.bookmark:hidden div.update_bookmark").submit(updateBookmark);
                $("ul#bookmark_list li.bookmark:hidden div.delete_bookmark").submit(deleteBookmark);
                $("ul#bookmark_list li#more_bookmarks form").submit(moreBookmarks);

                // Finally, slide down the more bookmarks HTML snippet.
                // Subtle: If there are yet more bookmarks, then this
                // additional bookmarks' HTML snippet will include the code for
                // the new "more bookmarks" button and the new spinner, so
                // there's nothing more required of us there.
                $("ul#bookmark_list li.bookmark:hidden").slideDown("slow");
            },
            error: function(xmlHttpRequest, textStatus, errorThrown) {
                // Oops, we failed.  :-(  Transform the spinner back into the
                // "more bookmarks" button to allow the user to click it and
                // try again.
                $("li#more_bookmarks .submit").show();
                $("div#more_bookmarks_throbber").hide();
            },
            complete: function(xmlHttpRequest, textStatus) {
                // We're done with this procedure.  Allow the user to click the
                // "more bookmark" button again.
                moreBookmarksClicked = false;
            },
        });
    }

    // Cancel out the default behavior of the more bookmarks form.
    return false;
}
