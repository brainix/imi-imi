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


var createBookmarkSubmitted = false;
var moreBookmarksClicked = false;


/*----------------------------------------------------------------------------*\
 |                              initBookmarks()                               |
\*----------------------------------------------------------------------------*/

function initBookmarks() {
    // Hooray, a page has been loaded!

    // Go through the DOM and modify the behavior of every element that we
    // want to bless with AJAX.
    var urlToCreate = $("#url_to_create");
    urlToCreate.focus(focusCreateBookmark);
    urlToCreate.blur(blurCreateBookmark);
    $("#create_bookmark").submit(createBookmark);
    $(".update_bookmark").live("submit", updateBookmark);
    $(".delete_bookmark").live("submit", deleteBookmark);
    $("#more_bookmarks").live("submit", moreBookmarks);

    // Make sure that the "save bookmark" bar displays the default
    // explanatory text.
    var defaultSaveBookmarkText = urlToCreate.attr("defaultValue");
    urlToCreate.val(defaultSaveBookmarkText);

    // For some reason, sometimes (particularly when we're clicking
    // back/forward through the pages in the site) our button labels get
    // confused.  Straighten them out.
    $("#create_bookmark .submit").val("save bookmark");
    $(".update_bookmark .submit").val("update");
    $(".delete_bookmark .submit").val("delete");
    $("#more_bookmarks .submit").val("more bookmarks");
}


/*----------------------------------------------------------------------------*\
 |                           focusCreateBookmark()                            |
\*----------------------------------------------------------------------------*/

function focusCreateBookmark() {
    // The user has clicked or tabbed into the "save bookmark" bar.  If the bar
    // contains the default explanatory text, then clear it out to contain no
    // text.

    var urlToCreate = $("#url_to_create");
    var defaultSaveBookmarkText = urlToCreate.attr("defaultValue");

    if (urlToCreate.val() == defaultSaveBookmarkText) {
        urlToCreate.val("");
    }
}


/*----------------------------------------------------------------------------*\
 |                            blurCreateBookmark()                            |
\*----------------------------------------------------------------------------*/

function blurCreateBookmark() {
    // The user has clicked or tabbed out of the "save bookmark" bar.  If the
    // bar contains no text, then populate it with the default explanatory
    // text.

    var urlToCreate = $("#url_to_create");
    var defaultSaveBookmarkText = urlToCreate.attr("defaultValue");

    if (urlToCreate.val() == "") {
        urlToCreate.val(defaultSaveBookmarkText);
    }
}


/*----------------------------------------------------------------------------*\
 |                              createBookmark()                              |
\*----------------------------------------------------------------------------*/

function createBookmark() {
    // Modify the behavior of the create bookmark bar.

    var urlToCreate = $("#url_to_create");

    if (createBookmarkSubmitted) {
        var message = "You've already submitted a request to bookmark: ";
        message += urlToCreate.val() + "  ";
        message += "Please wait for this request to complete ";
        message += "before issuing another request.";
        alert(message);
    }
    else {
        // Don't allow the user to click the "save bookmark" button again,
        // until we're done with this procedure.
        createBookmarkSubmitted = true;

        var createBookmarkThrobber = $("#create_bookmark_throbber");
        var createBookmarkButton = $(".create_bookmark .submit");

        // Transform the "save bookmark" button into a spinner.
        urlToCreate.addClass("url_to_create_with_throbber_shown");
        createBookmarkThrobber.show();
        createBookmarkButton.hide();

        // Make the AJAX request to create the bookmark.  If we succeed, then
        // clear out the URL that the user entered into the "save bookmark" bar
        // and slide down the new bookmark's HTML snippet.  Whether we succeed
        // or fail, transform the spinner back into the "save bookmark" button.
        $.ajax({
            type: "POST",
            url: "/users",
            data: "url_to_create=" + urlToCreate.val(),
            success: function(data, textStatus, xmlHttpRequest) {
                // Hooray, we succeed!  Clear out the URL that the user entered
                // into the "save bookmark" bar and set the input focus on that
                // bar.  (This facilitates the rapid entry of multiple URLs.)
                urlToCreate.val("");
                urlToCreate.focus();
                addBookmarks(data, PREPEND, INCREMENT);
            },
            complete: function(xmlHttpRequest, textStatus) {
                // Transform the spinner back into the "save bookmark" button.
                createBookmarkButton.show();
                createBookmarkThrobber.hide();
                urlToCreate.removeClass("url_to_create_with_throbber_shown");

                // We're done with this procedure.  Allow the user to click the
                // "save bookmark" button again.
                createBookmarkSubmitted = false;
            }
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

    var bookmarkKey = $(this).find("[name='bookmark_key']").val();
    var referenceKey = $(this).find("[name='reference_key_to_update']").val();
    var staleBookmark = $(this).closest("li");
    var elementToScroll = $.browser.safari ? "body" : "html";
    var offset = $("#create_bookmark").offset().top;

    $.ajax({
        type: "POST",
        url: "/users",
        data: {
            "bookmark_key": bookmarkKey,
            "reference_key_to_update": referenceKey
        },
        success: function(data, textStatus, xmlHttpRequest) {
            staleBookmark.slideUp("slow", function() {
                staleBookmark.remove();
                $(elementToScroll).animate({scrollTop: offset}, "slow", "swing", function() {
                    addBookmarks(data, PREPEND, DONT_INCREMENT);
                });
            });
        }
    });

    // Cancel out the default behavior of the update bookmark forms.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                              deleteBookmark()                              |
\*----------------------------------------------------------------------------*/

function deleteBookmark() {
    // Modify the behavior of the "delete bookmark" buttons.

    var confirmed = confirm("Delete bookmark?");

    if (confirmed) {
        // OK.  The user has clicked a "delete bookmark" button and confirmed
        // that that's what he/she meant to do.
        var bookmarkKey = $(this).find("[name='bookmark_key']").val();
        var referenceKey = $(this).find("[name='reference_key_to_delete']").val();
        var bookmark = $(this).closest("li");

        // Make the AJAX request to delete the bookmark.  Whether we succeed or
        // fail, slide up and remove the bookmark's HTML snippet.
        $.ajax({
            type: "POST",
            url: "/users",
            data: {
                "bookmark_key": bookmarkKey,
                "reference_key_to_delete": referenceKey
            },
            complete: function(xmlHttpRequest, textStatus) {
                bookmark.slideUp("slow", function() {
                    bookmark.remove();
                    // Decrement the number of bookmarks.
                    changeNumBookmarks(-1);
                });
            }
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

    if (!moreBookmarksClicked) {
        // Don't allow the user to click the "more bookmarks" button again,
        // until we're done with this procedure.
        moreBookmarksClicked = true;

        // Transform the "more bookmarks" button into a spinner.
        $("#more_bookmarks_throbber").show();
        $("#more_bookmarks .submit").hide();

        var moreUrl = $("#more_url").val();

        // Make the AJAX request to get more bookmarks.  If we succeed, then
        // get rid of the spinner, munge the additional bookmarks' HTML
        // snippet, and slide down the additional bookmarks' HTML snippet.
        // Otherwise, transform the spinner back into the "more bookmarks"
        // button.
        $.ajax({
            type: "GET",
            url: moreUrl,
            success: function(data, textStatus, xmlHttpRequest) {
                // Hooray, we succeeded!  Get rid of the spinner.
                $("#more_bookmarks").remove();

                // Subtle: If there are yet more bookmarks, then this
                // additional bookmarks' HTML snippet will include the code for
                // the new "more bookmarks" button and the new (initially
                // hidden) spinner, so there's nothing more required of us
                // there.
                addBookmarks(data, APPEND, DONT_INCREMENT);
            },
            error: function(xmlHttpRequest, textStatus, errorThrown) {
                // Oops, we failed.  :-(  Transform the spinner back into the
                // "more bookmarks" button to allow the user to click it and
                // try again.
                $("#more_bookmarks .submit").show();
                $("#more_bookmarks_throbber").hide();
            },
            complete: function(xmlHttpRequest, textStatus) {
                // We're done with this procedure.  Allow the user to click the
                // "more bookmarks" button again.
                moreBookmarksClicked = false;
            }
        });
    }

    // Cancel out the default behavior of the more bookmarks form.
    return false;
}


/*----------------------------------------------------------------------------*\
 |                               addBookmarks()                               |
\*----------------------------------------------------------------------------*/

var PREPEND = true;
var APPEND = false;

var INCREMENT = true;
var DONT_INCREMENT = false;

function addBookmarks(htmlSnippet, prepend, increment) {
    // Add some bookmarks' HTML snippet into the DOM, then perform the various
    // necessary operations.  This can happen in a few different situations:
    //     1.  The user creates a bookmark.
    //     2.  The user updates a bookmark.
    //     3.  The user loads more bookmarks.

    // Add the bookmarks' HTML snippet to the DOM.
    $("#bookmark_list")[prepend ? "prepend" : "append"](htmlSnippet);

    // If any of the bookmarks are images, preload the images and bless them
    // with beautiful overlays.
    preloadImagesSelector(".bookmark:hidden");
    $(".bookmark:hidden img.bookmark[rel]").overlay();

    // Slide down the bookmarks' HTML snippet.
    $(".bookmark:hidden").slideDown("slow", function() {
        // If specified, increment the number of bookmarks.
        if (increment) {
            changeNumBookmarks(1);
        }
    });
}


/*----------------------------------------------------------------------------*\
 |                            changeNumBookmarks()                            |
\*----------------------------------------------------------------------------*/

function changeNumBookmarks(addend) {
    var numBookmarksElement = $("#num_bookmarks");
    var numBookmarksStr = numBookmarksElement.html();
    var numBookmarksInt = parseInt(numBookmarksStr, 10);

    if (!isNaN(numBookmarksInt)) {
        numBookmarksInt += addend;
        numBookmarksStr = numBookmarksInt.toString();
        numBookmarksElement.html(numBookmarksStr);
    }
}
