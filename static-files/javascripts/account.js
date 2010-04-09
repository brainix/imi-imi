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
 |                              $.initAccount()                               |
\*----------------------------------------------------------------------------*/

(function($) {
    $.initAccount = function() {
        // Hooray, a page has been loaded!

        // Go through the DOM and modify the behavior of every element that we
        // want to bless with AJAX.
        $("#follow").submit(toggleFollowing);
    }
})(jQuery)


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

        // If the user has clicked the "follow" button, then we require no
        // additional confirmation.  On the other hand, if the user has clicked
        // the "stop following" button, then seek additional confirmation.
        var confirmed = true;
        if (currentlyFollowing) {
            var targetUserNickname = $(this).find("[name='nickname']").val();
            confirmed = confirm("Stop following " + targetUserNickname + "?");
        }

        if (!confirmed) {
            // The user has clicked the "stop following" button in error.  This
            // aborts; we're done with this procedure.  Allow the user to click
            // the "follow" or "stop following" button again.
            followClicked = false;
        } else {

            // OK, the user has either clicked the "follow" button, or clicked
            // the "stop following" button and provided additional confirmation
            // of intentionality.  From various pre-populated hidden fields in
            // the DOM, figure out who's following or un-following whom.
            var currentUserAcctId = $(this).find("[name='current_user_id']").val();
            var currentUserElemId = "#follower_" + currentUserAcctId;
            var submitButton = $("#follow .submit");
            var currentlyFollowing = submitButton.val() == STOP_FOLLOWING_TEXT;
            var targetUserEmail = $(this).find("[name='email']").val();
            var data = new Object;
            if (currentlyFollowing) {
                data.email_to_unfollow = targetUserEmail;
            } else {
                data.email_to_follow = targetUserEmail;
            }

            $.ajax({
                type: "POST",
                url: "/users",
                data: data,
                success: function(data, textStatus) {
                    currentlyFollowing = !currentlyFollowing;
                    if (currentlyFollowing) {
                        var followersList = $("#followers");
                        followersList.html($.trim(followersList.html()));
                        followersList.append(data);
                        $.preloadImagesSelector(currentUserElemId);
                        $(currentUserElemId).fadeIn("slow", function() {
                            submitButton.val(STOP_FOLLOWING_TEXT);
                        });
                    }
                    else {
                        var currentUserElem = $(currentUserElemId);
                        currentUserElem.fadeOut("slow", function() {
                            currentUserElem.remove();
                            submitButton.val(FOLLOW_TEXT);
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
