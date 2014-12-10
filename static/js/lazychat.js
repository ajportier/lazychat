function chatListener ( jQuery ) {
    console.log( "READY!" );

    // Global Variables
    var token = "";
    var chat_update_timeout = 2000;
    var user_update_timeout = 5000;
    var last_update = 0; // Starts at epoch so we get everything

    // Start callback listeners
    getNewChats();
    getCurrentUsers();

    $( "#sendbutton" ).click( function ( e ) {
        var content = $( "#textinput" ).val();
        if (content[0] === '@'){
            string_array = content.split(" ");
            p_user = string_array.shift().replace('@',''); 
            new_content = string_array.join(" ");
            sendPrivateChat( new_content, p_user );
        } else {
            sendNewChat( content );
        }
        e.preventDefault();
    });

    $( "#loginbutton" ).click( function ( e ) {
        var username = $( "#username" ).val();
        var password = $( "#password" ).val();
        getLoginToken( username, password );
        e.preventDefault();
    });

    function getLoginToken( username, password ){

        // Send username and password and set global token variable
        $.ajax({
            type: "GET",
            url: "/user/login",
            beforeSend: function (xhr) {
                xhr.setRequestHeader("Authorization", 
                    "Basic " + btoa(username + ":" + password));
            },
            success: function ( data ) {
                token = String(data[ 'token' ]);
            },
            error: function ( textStatus, jqXHR, errorThrown ) {
                console.log("Error:" + errorThrown);
            }
        });
    }

    function sendNewChat( content ){
        
        // Ignore request if user is not signed in
        if ( token !== "" ) {
            $.ajaxSetup({
                contentType: "application/json"
            });

            $.ajax({
                type: "POST",
                url: "/chat/add",
                data: JSON.stringify({content: content}),
                dataType: "json",
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("Authorization", 
                        "Basic " + btoa(token + ":"));
                },
                success: function ( data ) {
                    content = $( "#textinput" ).val( '' );
                },
                error: function ( textStatus, jqXHR, errorThrown ) {
                    console.log("Error:" + errorThrown);
                }
            });
        }
    }

    function sendPrivateChat( content, p_user ){
        
        // Ignore request if user is not signed in
        if ( token !== "" ) {
            $.ajaxSetup({
                contentType: "application/json"
            });

            $.ajax({
                type: "POST",
                url: "/chat/add",
                data: JSON.stringify({content: content, private_user: p_user}),
                dataType: "json",
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("Authorization", 
                        "Basic " + btoa(token + ":"));
                },
                success: function ( data ) {
                    content = $( "#textinput" ).val( '' );
                },
                error: function ( textStatus, jqXHR, errorThrown ) {
                    console.log("Error:" + errorThrown);
                }
            });
        }
    }

    function getNewChats(){

        // If there is no valid login token, try again after timeout
        if ( token !== "" ) {
            $.ajaxSetup({
                contentType: "application/json"
            });

            $.ajax({
                type: "POST",
                url: "/chat/get",
                data: JSON.stringify({start_time: last_update}),
                dataType: "json",
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("Authorization", 
                        "Basic " + btoa(token + ":"));
                },
                success: function ( data ) {

                    // For each chat object returned, update the feedback div
                    $.each( data, function(i,chat) {
                        var new_chat = '<p>';

                        // If this is a "private" chat update the class
                        if ( 'private_user' in chat ) {
                            new_chat = '<p class="private">';
                        }
                        var new_chat = new_chat + chat.username + ': '
                            + chat.content + '</p>';
                        last_update = chat.created;
                        $('#feedback').append(new_chat);

                        // Scrolls the feedback div to the bottom of new content
                        $('#feedback').animate({
                            scrollTop: $('#feedback').prop('scrollHeight')
                        }, 300);
                    });

                    
                },
                error: function ( textStatus, jqXHR, errorThrown ) {
                    console.log("Error:" + errorThrown);
                }
            });
        }

        setTimeout(getNewChats, chat_update_timeout);
    }

    function getCurrentUsers() {
        if ( token !== "" ) {

            $.ajax({
                type: "GET",
                url: "/user/list_current",
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("Authorization", 
                        "Basic " + btoa(token + ":"));
                },
                success: function ( data ) {

                    // Empty the current list of users
                    $('#userlist').empty();
                    $.each( data, function(i,user) {
                        // Add a new user for each seen
                        var new_user = '<p>' + user.username + '</p>';
                        $('#userlist').append(new_user);
                    });
                },
                error: function ( textStatus, jqXHR, errorThrown ) {
                    console.log("Error:" + errorThrown);
                }
            });
        }
        setTimeout(getCurrentUsers, user_update_timeout);
    }
}
