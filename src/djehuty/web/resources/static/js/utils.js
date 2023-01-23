function render_in_form (text) { return [text].join(''); }

function or_null (value) { return (value == "" || value == "<p><br></p>") ? null : value; }

function show_message (type, message) {
    jQuery("#message")
        .addClass(type)
        .append(message)
        .fadeIn(250);
    setTimeout(function() {
        jQuery("#message").fadeOut(500, function() {
            jQuery("#message").removeClass(type).empty();
        });
    }, 5000);
}

function install_sticky_header () {
    var submenu_offset = jQuery("#submenu").offset().top;
    jQuery(window).on('resize scroll', function() {
        let scroll_offset  = jQuery(window).scrollTop();
        if (submenu_offset <= scroll_offset) {
            jQuery("#submenu").addClass("sticky");
            jQuery("#message").addClass("sticky-message");
            jQuery("h1").addClass("sticky-margin");
            jQuery("#message").width(jQuery("#content-wrapper").width());
        } else {
            jQuery("#submenu").removeClass("sticky");
            jQuery("#message").removeClass("sticky-message");
            jQuery("h1").removeClass("sticky-margin");
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

            html += `<div id="new-author" class="a-button"><a href="#" `
            html += `onclick="javascript:new_author('${item_id}'); `
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

            html += `<div id="new-funding" class="a-button"><a href="#" `
            html += `onclick="javascript:new_funding('${item_id}'); `
            html += `return false;">Create funding record</a></div>`;
            jQuery("#funding")
                .addClass("input-for-ac")
                .after(`<div id="funding-ac" class="autocomplete">${html}</div>`);
        });
    }
}
