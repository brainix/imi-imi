var KEY_BACKSPACE=8,KEY_ESCAPE=27,KEY_SPACE=32,KEY_LEFT=37,KEY_UP=38,KEY_RIGHT=39,KEY_DOWN=40,KEY_DELETE=46,KEY_0=48,KEY_9=57,KEY_A=65,KEY_Z=90,queryString="",currentLiveSearchRequest=null,liveResultsFetched=false,liveResultsShown=false,liveResultSelected=-1;(function(a){a.initSearch=function(){var b=a("#query");b.focus(focusSearch);b.blur(blurSearch);b.keyup(fetchLiveResults);b.keydown(scrollLiveResults);var c=b.attr("defaultValue");b.val(c)}})(jQuery);
function focusSearch(){var a=$("#query"),b=a.attr("defaultValue");if(a.val()==b)a.val("");else liveResultsFetched&&!liveResultsShown&&showLiveResults()}function blurSearch(){var a=$("#query");if(a.val()==""){var b=a.attr("defaultValue");a.val(b)}else liveResultsShown&&hideLiveResults()}
function fetchLiveResults(a){a=a.keyCode||a.which||window.event.keyCode;if(a==KEY_BACKSPACE||a==KEY_SPACE||a==KEY_DELETE||a>=KEY_0&&a<=KEY_9||a>=KEY_A&&a<=KEY_Z){if(currentLiveSearchRequest!=null){currentLiveSearchRequest.abort();currentLiveSearchRequest=null}if(queryString=$("#query").val())currentLiveSearchRequest=$.ajax({type:"GET",url:"/live_search",data:"query="+queryString,success:function(b){if(b.length>1){liveResultsFetched=true;liveResultSelected=-1;$("#live_search").html(b);showLiveResults()}else{liveResultsFetched=
false;hideLiveResults()}},error:function(){liveResultsFetched=false;hideLiveResults()},complete:function(){currentLiveSearchRequest=null}});else{liveResultsFetched=false;hideLiveResults()}}if(a==KEY_ESCAPE){if(currentLiveSearchRequest!=null){currentLiveSearchRequest.abort();currentLiveSearchRequest=null}liveResultsFetched=false;$("#query").val("");hideLiveResults()}}
function showLiveResults(){if(!liveResultsShown){liveResultsShown=true;$("#query").addClass("query_with_live_search_shown");$("#live_search").fadeIn("slow");$("#heading h2").fadeTo("slow",0);$("#right").fadeTo("slow",0)}}function hideLiveResults(){if(liveResultsShown){liveResultsShown=false;$("#query").removeClass("query_with_live_search_shown");$("#live_search").fadeOut("slow");$("#heading h2").fadeTo("slow",1);$("#right").fadeTo("slow",1)}}
function scrollLiveResults(a){var b=a.keyCode||a.which||window.event.keyCode;if(b==KEY_UP||b==KEY_DOWN)if(liveResultsShown){var c=$("#live_search ul li a");if(c.length>0){if(liveResultSelected!=-1){var d="#live_search_result_"+liveResultSelected;$(d).removeClass("live_search_result_selected")}liveResultSelected+=b==KEY_UP?-1:1;if(liveResultSelected<-1)liveResultSelected=c.length-1;if(liveResultSelected>c.length-1)liveResultSelected=-1;if(liveResultSelected==-1)$("#query").val(queryString);else{d=
"#live_search_result_"+liveResultSelected;$("#query").val($(d).html());$(d).addClass("live_search_result_selected")}}a.preventDefault()}};var createBookmarkSubmitted=false,moreBookmarksClicked=false;
(function(a){a.initBookmarks=function(){var b=a("#url_to_create");b.focus(focusCreateBookmark);b.blur(blurCreateBookmark);a("#create_bookmark").submit(createBookmark);a(".update_bookmark").submit(updateBookmark);a(".delete_bookmark").submit(deleteBookmark);a("#more_bookmarks").submit(moreBookmarks);var c=b.attr("defaultValue");b.val(c);a("#create_bookmark .submit").val("save bookmark");a(".update_bookmark .submit").val("update");a(".delete_bookmark .submit").val("delete");a("#more_bookmarks .submit").val("more bookmarks")}})(jQuery);
function focusCreateBookmark(){var a=$("#url_to_create"),b=a.attr("defaultValue");a.val()==b&&a.val("")}function blurCreateBookmark(){var a=$("#url_to_create");if(a.val()==""){var b=a.attr("defaultValue");a.val(b)}}
function createBookmark(){if(!createBookmarkSubmitted){createBookmarkSubmitted=true;var a=$("#url_to_create"),b=$("#create_bookmark_throbber"),c=$(".create_bookmark .submit");a.addClass("url_to_create_with_throbber_shown");b.show();c.hide();$.ajax({type:"POST",url:"/users",data:"url_to_create="+a.val(),success:function(d){a.val("");a.focus();$("#bookmark_list").prepend(d);$(".bookmark:hidden .update_bookmark").submit(updateBookmark);$(".bookmark:hidden .delete_bookmark").submit(deleteBookmark);$.preloadImagesSelector(".bookmark:hidden");
$(".bookmark:hidden").slideDown("slow",function(){changeNumBookmarks(1)})},complete:function(){c.show();b.hide();a.removeClass("url_to_create_with_throbber_shown");createBookmarkSubmitted=false}})}return false}
function updateBookmark(){var a=$(this).find("[name='bookmark_key']").val(),b=$(this).find("[name='reference_key_to_update']").val(),c=$(this).closest("li"),d=$.browser.safari?"body":"html",e=$("#create_bookmark").offset().top;$.ajax({type:"POST",url:"/users",data:{bookmark_key:a,reference_key_to_update:b},success:function(f){c.slideUp("slow",function(){c.remove();$(d).animate({scrollTop:e},"slow","swing",function(){$("#bookmark_list").prepend(f);$(".bookmark:hidden .update_bookmark").submit(updateBookmark);
$(".bookmark:hidden .delete_bookmark").submit(deleteBookmark);$.preloadImagesSelector(".bookmark:hidden");$(".bookmark:hidden").slideDown("slow")})})}});return false}
function deleteBookmark(){if(confirm("Delete bookmark?")){var a=$(this).find("[name='bookmark_key']").val(),b=$(this).find("[name='reference_key_to_delete']").val(),c=$(this).closest("li");$.ajax({type:"POST",url:"/users",data:{bookmark_key:a,reference_key_to_delete:b},complete:function(){c.slideUp("slow",function(){c.remove();changeNumBookmarks(-1)})}})}return false}function changeNumBookmarks(a){var b=$("#num_bookmarks"),c=b.html();c=parseInt(c,10);if(!isNaN(c)){c+=a;c=c.toString();b.html(c)}}
function moreBookmarks(){if(!moreBookmarksClicked){moreBookmarksClicked=true;$("#more_bookmarks_throbber").show();$("#more_bookmarks .submit").hide();var a=$("#more_url").val();$.ajax({type:"GET",url:a,success:function(b){$("#more_bookmarks").remove();$("#bookmark_list").append(b);$(".bookmark:hidden .update_bookmark").submit(updateBookmark);$(".bookmark:hidden .delete_bookmark").submit(deleteBookmark);$("#more_bookmarks").submit(moreBookmarks);$.preloadImagesSelector(".bookmark:hidden");$(".bookmark:hidden").slideDown("slow")},
error:function(){$("#more_bookmarks .submit").show();$("#more_bookmarks_throbber").hide()},complete:function(){moreBookmarksClicked=false}})}return false};var FOLLOW_TEXT="follow",STOP_FOLLOWING_TEXT="stop following",followClicked=false;(function(a){a.initAccount=function(){a("#follow").submit(toggleFollowing)}})(jQuery);
function toggleFollowing(){if(!followClicked){followClicked=true;var a=$("#follow .submit"),b=a.val()==STOP_FOLLOWING_TEXT,c=true;if(b){c=$(this).find("[name='nickname']").val();c=confirm("Stop following "+c+"?")}if(c){var d="#follower_"+$(this).find("[name='current_user_id']").val();c=$(this).find("[name='email']").val();var e={};if(b)e.email_to_unfollow=c;else e.email_to_follow=c;$.ajax({type:"POST",url:"/users",data:e,success:function(f){if(b=!b){var g=$("#followers");g.html($.trim(g.html()));
g.append(f);$.preloadImagesSelector(d);$(d).fadeIn("slow",function(){a.val(STOP_FOLLOWING_TEXT)})}else{var h=$(d);h.fadeOut("slow",function(){h.remove();a.val(FOLLOW_TEXT)})}},complete:function(){followClicked=false}})}else followClicked=false}return false};$(function(){$.initSearch();$.initBookmarks();$.initAccount();$.preloadImagesArgs("/static-files/images/favicon.ico","/static-files/images/speech_balloon_tail.png","/static-files/images/throbber.gif")});(function(a){var b=[];a.preloadImagesArgs=function(){if(document.images)for(var c=arguments.length;c--;){var d=document.createElement("img");d.src=arguments[c];b.push(d)}};a.preloadImagesSelector=function(c){a(c+" img").each(function(){a.preloadImagesArgs(a(this).attr("src"))})}})(jQuery);