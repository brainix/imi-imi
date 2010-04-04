/*----------------------------------------------------------------------------*\
 |  account.js                                                                |
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


const FOLLOW_TEXT = "follow";
const STOP_FOLLOWING_TEXT = "stop following";

var followClicked = false;


/*----------------------------------------------------------------------------*\
 |                               initAccount()                                |
\*----------------------------------------------------------------------------*/

function initAccount() {
    // Hooray, a page has been loaded!

    // Go through the DOM and modify the behavior of every element that we want
    // to bless with AJAX.
    $("#follow").submit(toggleFollowing);
}


/*----------------------------------------------------------------------------*\
 |                             toggleFollowing()                              |
\*----------------------------------------------------------------------------*/
function toggleFollowing() {
    // Modify the behavior of the "follow" or "stop following" button.  Only
    // one of those buttons is shown at a time, and when it's clicked, it turns
    // into the other one.

    if (!followClicked) {
        // Don't allow the user to click the "follow" or "stop following"
        // button again, until we're done with this procedure.
        followClicked = true;

        var currentUserAcctId = $(this).find("[name='current_user_id']").val();
        var currentUserElemId = "#follower_" + currentUserAcctId;
        var currentlyFollowing = $("#follow .submit").val() == STOP_FOLLOWING_TEXT;
        var confirmed = true;
        var data = new Object;

        if (currentlyFollowing) {
            confirmed = confirm("Stop following " + $(this).find("[name='nickname']").val() + "?");
            data.email_to_unfollow = $(this).find("[name='email']").val();
        } else {
            data.email_to_follow = $(this).find("[name='email']").val();
        }

        if (confirmed) {
            $.ajax({
                type: "POST",
                url: "/users",
                data: data,
                success: function(data, textStatus) {
                    currentlyFollowing = !currentlyFollowing;
                    if (currentlyFollowing) {
                        $("#followers").html($.trim($("#followers").html()));
                        $("#followers").append(data);
                        $(currentUserElemId).fadeIn("slow", function() {
                            $("#follow .submit").val(STOP_FOLLOWING_TEXT);
                        });
                    }
                    else {
                        var currentUserElem = $(currentUserElemId);
                        currentUserElem.fadeOut("slow", function() {
                            currentUserElem.remove();
                            $("#follow .submit").val(FOLLOW_TEXT);
                        });
                    }
                },
                complete: function(xmlHttpRequest, textStatus) {
                    // We're done with this procedure.  Allow the user to click
                    // the "follow" or "stop following" button again.
                    followClicked = false;
                },
            });
        }
    }

    // Cancel out the default behavior of the "follow" or "stop following"
    // button.
    return false;
}
