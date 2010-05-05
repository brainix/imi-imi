/*----------------------------------------------------------------------------*\
 |  search.js                                                                 |
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


const DEFAULT_QUERY_TEXT = "search bookmarks";

const KEY_BACKSPACE = 8;
const KEY_ESCAPE = 27;
const KEY_SPACE = 32;
const KEY_LEFT = 37;
const KEY_UP = 38;
const KEY_RIGHT = 39;
const KEY_DOWN = 40;
const KEY_DELETE = 46;
const KEY_0 = 48;
const KEY_9 = 57;
const KEY_A = 65;
const KEY_Z = 90;


var currentLiveSearchRequest = null; // The current live search's XMLHttpRequest object.
var liveResultsFetched = false;      // Whether live results have been fetched.
var liveResultsShown = false;        // Whether live results are shown.
var liveResultSelected = -1;         // Which live result is selected.


/*----------------------------------------------------------------------------*\
 |                               $.initSearch()                               |
\*----------------------------------------------------------------------------*/

(function($) {
    $.initSearch = function() {
        // Hooray, a page has been loaded!

        // Go through the DOM and modify the behavior of every element that we
        // want to bless with AJAX.
        $("#query").focus(focusSearch);
        $("#query").blur(blurSearch);
        $("#query").keyup(fetchLiveResults);
        $("#query").keydown(scrollLiveResults);

        // Make sure that the search bar displays the default explanatory text.
        $("#query").val(DEFAULT_QUERY_TEXT);
    }
})(jQuery)


/*----------------------------------------------------------------------------*\
 |                               focusSearch()                                |
\*----------------------------------------------------------------------------*/

function focusSearch() {
    // The user has clicked or tabbed into the search bar.  If the bar contains
    // the default explanatory text, then clear it out to contain no text.
    // Otherwise, if the user previously entered a search query and we
    // successfully fetched some live search results, then show those results.

    if ($("#query").val() == DEFAULT_QUERY_TEXT) {
        $("#query").val("");
    }
    else {
        if (liveResultsFetched && !liveResultsShown) {
            showLiveResults();
        }
    }
}


/*----------------------------------------------------------------------------*\
 |                                blurSearch()                                |
\*----------------------------------------------------------------------------*/

function blurSearch() {
    // The user has clicked or tabbed out of the search bar.  If the bar
    // contains no text, then populate it with the default explanatory text.
    // Otherwise, if the user previously entered a search query and we
    // successfully fetched some live search results, then hide those results.

    if ($("#query").val() == "") {
        $("#query").val(DEFAULT_QUERY_TEXT);
    }
    else {
        if (liveResultsShown) {
            hideLiveResults();
        }
    }
}


/*----------------------------------------------------------------------------*\
 |                             fetchLiveResults()                             |
\*----------------------------------------------------------------------------*/

function fetchLiveResults(event) {
    // The user has pressed a key in the search bar.  Try to fetch some live
    // search results.  If we succeed, then display the live results.  If we
    // fail for any reason, then hide the live results.

    var keyCode = event.keyCode || event.which || window.event.keyCode;
    if (keyCode == KEY_BACKSPACE || keyCode == KEY_SPACE || keyCode == KEY_DELETE ||
        keyCode >= KEY_0 && keyCode <= KEY_9 ||
        keyCode >= KEY_A && keyCode <= KEY_Z) {

        // The user has somehow modified the search query.  If we're currently
        // waiting on live results, then abort that request (in favor of the
        // request that we're about to make).
        if (currentLiveSearchRequest != null) {
            currentLiveSearchRequest.abort()
            currentLiveSearchRequest = null;
        }

        var queryString = $("#query").val();
        if (queryString) {
            // OK, the search query string isn't empty.  Make an AJAX request
            // for live results for this particular search query string.
            currentLiveSearchRequest = $.ajax({
                type: "GET",
                url: "/live_search",
                data: "query=" + queryString,
                success: function(data, textStatus, xmlHttpRequest) {
                    if (data.length > 1) {
                        // Hooray!  The AJAX call succeeded and returned some
                        // live results.  Display them.
                        liveResultsFetched = true;
                        liveResultSelected = -1;
                        $("#live_search").html(data);
                        showLiveResults();
                    }
                    else {
                        // Oops.  The AJAX call succeeded but didn't return any
                        // live results.  Hide any previously fetched live
                        // results.
                        liveResultsFetched = false;
                        hideLiveResults();
                    }
                },
                error: function(request, textStatus, errorThrown) {
                    // Oops.  The AJAX call failed.  Hide any previously
                    // fetched live results.
                    liveResultsFetched = false;
                    hideLiveResults();
                },
                complete: function(request, textStatus) {
                    // This function gets called whether the AJAX call succeeds
                    // or fails.  In either case, the AJAX call has completed,
                    // so set the the current live search's XMLHttpRequest
                    // object to null.
                    currentLiveSearchRequest = null;
                },
            });
        }

        else {
            // Oops.  The search query string is empty - there's nothing to
            // fetch.  Hide any previously fetched live results.
            liveResultsFetched = false;
            hideLiveResults();
        }
    }

    if (keyCode == KEY_ESCAPE) {
        // The user pressed the escape key.  If we're currently waiting on live
        // results, then abort that request.  Also, clear out the search query
        // string and hide any previously fetched live results.
        if (currentLiveSearchRequest != null) {
            currentLiveSearchRequest.abort()
            currentLiveSearchRequest = null;
        }
        liveResultsFetched = false;
        $("#query").val("");
        hideLiveResults();
    }

    // Subtle:  Here, the default behavior is to display newly typed characters
    // as part of the search query, or (in the case of the enter key) to submit
    // the search query, or (in the case of the backspace key) to delete
    // characters from the search query, etc.  We don't want to cancel out this
    // behavior, so we don't return false.
}


/*----------------------------------------------------------------------------*\
 |                             showLiveResults()                              |
\*----------------------------------------------------------------------------*/

function showLiveResults() {
    // Fade in the previously fetched live search results.

    if (!liveResultsShown) {
        liveResultsShown = true;
        $("#query").addClass("query_with_live_search_shown");
        $("#live_search").fadeIn("slow");
        $("#heading h2").fadeTo("slow", 0);
        $("#right").fadeTo("slow", 0);
    }
}


/*----------------------------------------------------------------------------*\
 |                             hideLiveResults()                              |
\*----------------------------------------------------------------------------*/

function hideLiveResults() {
    // Fade out the previously fetched live search results.

    if (liveResultsShown) {
        liveResultsShown = false;
        $("#query").removeClass("query_with_live_search_shown");
        $("#live_search").fadeOut("slow");
        $("#heading h2").fadeTo("slow", 1);
        $("#right").fadeTo("slow", 1);
    }
}


/*----------------------------------------------------------------------------*\
 |                            scrollLiveResults()                             |
\*----------------------------------------------------------------------------*/

function scrollLiveResults(event) {
    // The user has released a key in the search bar.  If the user hit the up
    // or down arrow key, and if any live search results have been fetched and
    // displayed, then scroll up or down through the live search results.

    var keyCode = event.keyCode || event.which || window.event.keyCode;
    if (keyCode == KEY_UP || keyCode == KEY_DOWN) {
        if (liveResultsShown) {
            var liveResults = $("#live_search ul li a");
            if (liveResults.length > 0) {
                if (liveResultSelected != -1) {
                    id = "#live_search_result_" + liveResultSelected;
                    $(id).removeClass("live_search_result_selected");
                }
                liveResultSelected += keyCode == KEY_UP ? -1 : 1;
                if (liveResultSelected < 0) {
                    liveResultSelected = liveResults.length - 1;
                }
                if (liveResultSelected > liveResults.length - 1) {
                    liveResultSelected = 0;
                }
                id = "#live_search_result_" + liveResultSelected;
                $("#query").val($(id).html());
                $(id).addClass("live_search_result_selected");
            }

            // Here, the default behavior of the up/down arrow keys is to
            // position the cursor at the beginning/end of the search query
            // field.  Prevent this behavior.
            event.preventDefault();
        }
    }
}
