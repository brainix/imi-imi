/*----------------------------------------------------------------------------*\
 |  search.js                                                                 |
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


var current_live_search_request = null; // The current live search's XMLHttpRequest object.
var live_results_fetched = false;       // Whether live results have been fetched.
var live_results_shown = false;         // Whether live results are shown.
var live_result_selected = -1;          // Which live result is selected.


/*----------------------------------------------------------------------------*\
 |                               click_search()                               |
\*----------------------------------------------------------------------------*/

function click_search() {
    // The user has clicked into the search bar.  If the bar contains the
    // default explanatory text, clear it out to contain no text.  Otherwise, if
    // the user previously entered a search query and we successfully fetched
    // some live search results, show those results.

    if ($("#query").val() == DEFAULT_QUERY_TEXT) {
        $("#query").val("");
    }
    else {
        if (live_results_fetched && !live_results_shown) {
            show_live_results();
        }
    }
}


/*----------------------------------------------------------------------------*\
 |                               blur_search()                                |
\*----------------------------------------------------------------------------*/

function blur_search() {
    // The user has clicked out of the search bar.  If the bar contains no text,
    // populate it with the default explanatory text.  Otherwise, if the user
    // previously entered a search query and we successfully fetched some live
    // search results, hide those results.

    if ($("#query").val() == "") {
        $("#query").val(DEFAULT_QUERY_TEXT);
    }
    else {
        if (live_results_shown) {
            hide_live_results();
        }
    }
}


/*----------------------------------------------------------------------------*\
 |                            fetch_live_results()                            |
\*----------------------------------------------------------------------------*/

function fetch_live_results(event) {
    // The user has pressed a key in the search bar.  Try to fetch some live
    // search results.  If we succeed, display the live results.  If we fail
    // for any reason, hide the live results.

    key_code = event.keyCode || event.which || window.event.keyCode;
    if (key_code == KEY_BACKSPACE || key_code == KEY_SPACE || key_code == KEY_DELETE ||
        key_code >= KEY_0 && key_code <= KEY_9 ||
        key_code >= KEY_A && key_code <= KEY_Z) {

        // The user has somehow modified the search query.  If we're currently
        // waiting on live results, abort that request (in favor of the request
        // that we're about to make).
        if (current_live_search_request != null) {
            current_live_search_request.abort()
            current_live_search_request = null;
        }

        query_string = $("#query").val();
        if (query_string) {
            // OK, the search query string isn't empty.  Make an AJAX request
            // for live results for this particular search query string.
            current_live_search_request = $.ajax({
                type: "GET",
                url: "/live_search",
                data: "query=" + query_string,
                success: function(data, text_status) {
                    if (data.length > 1) {
                        // Hooray!  The AJAX call succeeded and returned some
                        // live results.  Display them.
                        live_results_fetched = true;
                        live_result_selected = -1;
                        $("#live_search").html(data);
                        show_live_results();
                    }
                    else {
                        // Oops.  The AJAX call succeeded but didn't return any
                        // live results.  Hide any previously fetched live
                        // results.
                        live_results_fetched = false;
                        hide_live_results();
                    }
                },
                error: function(request, text_status, error_thrown) {
                    // Oops.  The AJAX call failed.  Hide any previously
                    // fetched live results.
                    live_results_fetched = false;
                    hide_live_results();
                },
                complete: function(request, text_status) {
                    // This function gets called whether the AJAX call succeeds
                    // or fails.  In either case, the AJAX call has completed,
                    // so set the the current live search's XMLHttpRequest
                    // object to null.
                    current_live_search_request = null;
                },
            });
        }

        else {
            // Oops.  The search query string is empty - there's nothing to
            // fetch.  Hide any previously fetched live results.
            live_results_fetched = false;
            hide_live_results();
        }
    }

    if (key_code == KEY_ESCAPE) {
        // The user pressed the escape key.  If we're currently waiting on live
        // results, abort that request.  Also, clear out the search query
        // string and hide any previously fetched live results.
        if (current_live_search_request != null) {
            current_live_search_request.abort()
            current_live_search_request = null;
        }
        live_results_fetched = false;
        $("#query").val("");
        hide_live_results();
    }

    // Subtle:  Here, the default behavior is to display newly typed characters
    // as part of the search query, or (in the case of the enter key) to submit
    // the search query, or (in the case of the backspace key) to delete
    // characters from the search query, etc.  We don't want to cancel out this
    // behavior, so we don't return false.
}


/*----------------------------------------------------------------------------*\
 |                            show_live_results()                             |
\*----------------------------------------------------------------------------*/

function show_live_results() {
    // Fade in the previously fetched live search results.

    if (!live_results_shown) {
        live_results_shown = true;
        $("#query").addClass("query_with_live_search_shown");
        $("#live_search").fadeIn("slow");
    }
}


/*----------------------------------------------------------------------------*\
 |                            hide_live_results()                             |
\*----------------------------------------------------------------------------*/

function hide_live_results() {
    // Fade out the previously fetched live search results.

    if (live_results_shown) {
        live_results_shown = false;
        $("#query").removeClass("query_with_live_search_shown");
        $("#live_search").fadeOut("slow");
    }
}


/*----------------------------------------------------------------------------*\
 |                           scroll_live_results()                            |
\*----------------------------------------------------------------------------*/

function scroll_live_results(event) {
    // The user has released a key in the search bar.  If the user hit the up
    // or down arrow key, and if any live search results have been shown, then
    // scroll up or down through the live search results.

    key_code = event.keyCode || event.which || window.event.keyCode;
    if (key_code == KEY_UP || key_code == KEY_DOWN) {
        if (live_results_shown) {
            live_results = $("#live_search ul li a");
            if (live_results.length > 0) {
                if (live_result_selected != -1) {
                    id = "#live_search_result_" + live_result_selected;
                    $(id).removeClass("live_search_result_selected");
                }
                live_result_selected += key_code == KEY_UP ? -1 : 1;
                if (live_result_selected < 0) {
                    live_result_selected = live_results.length - 1;
                }
                if (live_result_selected > live_results.length - 1) {
                    live_result_selected = 0;
                }
                id = "#live_search_result_" + live_result_selected;
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


/*----------------------------------------------------------------------------*\
 |                                  search()                                  |
\*----------------------------------------------------------------------------*/

function search() {
    // Modify the behavior of the search bar - compute and point the browser to
    // the URL corresponding to the entered search query.

    function spaces_to_underscores(s1) {
        // Recursively convert a string's spaces into underscores.
        s2 = s1.replace(" ", "_");
        return s2 == s1 ? s2 : spaces_to_underscores(s2);
    }

    // Compute the URL corresponding to the entered search query.
    //     - Get the entered search query,
    //     - strip out all non-alpha-numeric and non-space characters,
    //     - replace all spaces with underscores, and
    //     - lower case all alphabetic characters.
    var query = $("#query").val();
    query = query.replace("-", " ");
    query = query.replace(/[^ A-Za-z0-9]+/g, "");
    query = spaces_to_underscores(query);
    query = query.toLowerCase();

    // Point the browser to the computed URL and cancel out the default behvaior
    // of the search form.
    window.location = "/search/" + query;
    return false;
}
