function render_in_form (text) { return [text].join(""); }

function or_null (value) { return (value == "" || value == "<p><br></p>") ? null : value; }
function or_empty (value) { return (value === undefined || value == null || value == "") ? "" : value;}
function show_message (type, message) {
    if (jQuery ("#message.transparent").length > 0) {
        jQuery("#message").removeClass("transparent").empty();
    }
    jQuery("#message")
        .addClass(type)
        .append(message)
        .fadeIn(250);
    setTimeout(function() {
        jQuery("#message").fadeOut(500, function() {
            jQuery("#message").removeClass(type).addClass("transparent").html("<p>&nbsp;</p>").show();
        });
    }, 20000);
}

function install_sticky_header () {
    var submenu_offset = jQuery("#submenu").offset().top;
    jQuery(window).on("resize scroll", function() {
        if (submenu_offset <= jQuery(window).scrollTop()) {
            jQuery("#submenu").addClass("sticky");
            jQuery("#message").addClass("sticky-message");
            jQuery("h1").addClass("sticky-margin");
            jQuery("#message").width(jQuery("#content-wrapper").width());
        } else {
            jQuery("#submenu").removeClass("sticky");
            jQuery("#message").removeClass("sticky-message");
            jQuery("h1").removeClass("sticky-margin");
            if (jQuery ("#message.transparent").length > 0) {
                jQuery("#message").removeClass("transparent").empty().hide();
            }
        }
    });
}

function install_touchable_help_icons () {
    jQuery(".help-icon").on("click", function () {
        let selector = jQuery(this).find(".help-text");
        if (selector.is(":visible") ||
            selector.css("display") != "none") {
            jQuery(this).removeClass("help-icon-clicked");
        } else {
            jQuery(this).addClass("help-icon-clicked");
        }
    });
}

function toggle_categories () {
    let expanded_categories = jQuery("#expanded-categories");
    if (expanded_categories.is(":visible")) {
        jQuery("#expanded-categories").slideUp(250, function() {
            jQuery("#expand-categories-button").text("Select categories");
        });
    } else {
        jQuery("#expanded-categories").slideDown(250, function() {
            jQuery("#expand-categories-button").text("Hide categories");
        });
    }
}

function toggle_collaborators (dataset_uuid, may_edit_metadata, event) {

    function show_collaborators () {
        jQuery("#expanded-collaborators").slideDown(250, function() {
            jQuery("#expand-collaborators-button").text("Hide collaborators");
        });
    }

    let expanded_collaborators = jQuery("#expanded-collaborators");
    if (expanded_collaborators.is(":visible")) {
        jQuery("#expanded-collaborators").slideUp(250, function() {
            let text = "Show collaborators";
            if (may_edit_metadata) { text = "Manage collaborators"; }
            jQuery("#expand-collaborators-button").text(text);
        });
    } else {
        if (jQuery("#add_collaborator").length == 0) {
            render_collaborators_for_dataset (dataset_uuid, may_edit_metadata, function() {
                show_collaborators ();
            });
        } else { show_collaborators (); }
    }
}

function fill_collaborator (email, full_name, account_uuid) {
    let input_text = `${full_name}, (${email})`;
    if (full_name == "null") {
        input_text = `${email}`;
    }
    jQuery("#add_collaborator").val(`${input_text}`);
    jQuery("#account_uuid").val(`${account_uuid}`);
    jQuery("#collaborator-ac").remove();
    jQuery("#add_collaborator").removeClass("input-for-ac");
}

function autocomplete_collaborator (event, item_id) {
    let current_text = jQuery.trim(jQuery("#add_collaborator").val());
    if (current_text == "") {
        jQuery("#collaborator-ac").remove();
        jQuery("#add_collaborator").removeClass("input-for-ac");
    } else if (current_text.length > 2) {
        jQuery.ajax({
            url:     "/v3/accounts/search",
            type:    "POST",
            contentType: "application/json",
            accept: "application/json",
            data: JSON.stringify({ "search_for": current_text}),
            }).done(function (data) {
                jQuery("#collaborator-ac").remove();
                let html = "<ul>";
                for (let item of data) {
                    let full_name = item["full_name"];
                    let account_text = `${item["full_name"]}, ${item["email"]}`;
                    if (full_name == null) {
                        account_text = `${item["email"]}`;
                    }
                    html += `<li><a href="#" `;
                    html += `onclick="javascript:fill_collaborator('${item["email"]}','${item["full_name"]}','${item["uuid"]}'`;
                    html += `); return false;">${account_text}`;
                    html += "</a>";
                }
                html += "</ul>";

                jQuery("#add_collaborator")
                    .addClass("input-for-ac")
                    .after(`<div id="collaborator-ac" class="autocomplete">${html}</div>`);
            }).fail(function (response, text_status, error_code) { console.log (`Error code: ${error_code} `);
        });
    }
}

function autocomplete_author (event, item_id) {
    let current_text = jQuery.trim(jQuery("#authors").val());
    if (current_text == "") {
        jQuery("#authors-ac").remove();
        jQuery("#authors").removeClass("input-for-ac");
    } else if (current_text.length > 2) {
        jQuery.ajax({
            url:         `/v2/account/authors/search`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "search": current_text }),
            dataType:    "json"
        }).done(function (data) {
            jQuery("#authors-ac").remove();
            let html = "<ul>";
            let new_author_description = "";
            if (data.length == 0) {
                new_author_description = "Seems like the author is not registered in our system. Click on the button below to add a new author.";
            } else {
                new_author_description = "Do you want to create a new author record? Then click on the button below.";
            }

            for (let item of data) {
                html += `<li><a href="#" `;
                html += `onclick="javascript:add_author('${item["uuid"]}', `;
                html += `'${item_id}'); return false;">${item["full_name"]}`;
                if (item["orcid_id"] != null && item["orcid_id"] != "") {
                    html += ` (${item["orcid_id"]})`;
                }
                html += "</a>";
            }
            html += "</ul>";

            html += `<span id="new-author-description" style='padding: 1em;'><i><center>${new_author_description}</center></i></span>`;

            html += `<div id="new-author" class="a-button"><a href="#" `;
            html += `onclick="javascript:new_author('${item_id}'); `;
            html += `return false;">Create new author record</a></div>`;
            jQuery("#authors")
                .addClass("input-for-ac")
                .after(`<div id="authors-ac" class="autocomplete">${html}</div>`);
        });
    }
}

function autocomplete_funding (event, item_id) {
    let current_text = jQuery.trim(jQuery("#funding").val());
    if (current_text == "") {
        jQuery("#funding-ac").remove();
        jQuery("#funding").removeClass("input-for-ac");
    } else if (current_text.length > 2) {
        jQuery.ajax({
            url:         `/v2/account/funding/search`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "search": current_text }),
            dataType:    "json"
        }).done(function (data) {
            jQuery("#funding-ac").remove();
            let html = "<ul>";
            for (let item of data) {
                html += `<li><a href="#" `;
                html += `onclick="javascript:add_funding('${item["uuid"]}', `;
                html += `'${item_id}'); return false;">${item["title"]}</a>`;
            }
            html += "</ul>";

            html += `<div id="new-funding" class="a-button"><a href="#" `;
            html += `onclick="javascript:new_funding('${item_id}'); `;
            html += `return false;">Create funding record</a></div>`;
            jQuery("#funding")
                .addClass("input-for-ac")
                .after(`<div id="funding-ac" class="autocomplete">${html}</div>`);
        });
    }
}
