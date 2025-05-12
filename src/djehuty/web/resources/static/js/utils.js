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

function stop_event_propagation (event) {
    if (event !== null) {
        event.preventDefault();
        event.stopPropagation();
    }
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

function toggle_categories (event=null) {
    stop_event_propagation (event);
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
    stop_event_propagation (event);
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

function add_collaborator_event (event) {
    stop_event_propagation (event);
    fill_collaborator (event.data["email"], event.data["full_name"], event.data["uuid"]);
}

function autocomplete_collaborator (event, item_id) {
    let current_text = jQuery.trim(jQuery("#add_collaborator").val());
    let existing_collaborators = [];
    jQuery(".contributor-uuid").each(function(){existing_collaborators.push(jQuery(this).val()); });
    if (current_text == "") {
        jQuery("#collaborator-ac").remove();
        jQuery("#add_collaborator").removeClass("input-for-ac");
    } else if (current_text.length > 2) {
        jQuery.ajax({
            url:     "/v3/accounts/search",
            type:    "POST",
            contentType: "application/json",
            accept: "application/json",
            data: JSON.stringify({ "search_for": current_text, "exclude": existing_collaborators}),
            }).done(function (data) {
                jQuery("#collaborator-ac").remove();
                let unordered_list = jQuery("<ul/>");
                let html = "<ul>";
                for (let item of data) {
                    let full_name = item["full_name"];
                    let account_text = `${item["full_name"]}, ${item["email"]}`;
                    if (full_name == null) { account_text = `${item["email"]}`; }
                    let list_item = jQuery("<li/>");
                    let anchor = jQuery("<a/>", { "href": "#" });
                    anchor.text (account_text);
                    anchor.on("click",
                              { "email": item["email"], "full_name": item["full_name"], "uuid": item["uuid"] },
                              add_collaborator_event);
                    list_item.html (anchor);
                    unordered_list.append (list_item);
                }
                let wrapper = jQuery("<div/>", { "id": "collaborator-ac", "class": "autocomplete" });
                wrapper.html (unordered_list);
                jQuery("#add_collaborator")
                    .addClass("input-for-ac")
                    .after(wrapper);
            }).fail(function (response, text_status, error_code) { console.log (`Error code: ${error_code} `);
        });
    }
}

function add_author_event (event) {
    stop_event_propagation (event);
    if (event.data && event.data["uuid"]) {
        add_author (event.data["uuid"], event.data["item_id"]);
    } else {
        new_author (event.data["item_id"]);
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
            let unordered_list = jQuery("<ul/>");
            let new_author_text = "Do you want to create a new author record? Then click on the button below.";
            if (data.length == 0) {
                new_author_text = "Seems like the author is not registered in our system. Click on the button below to add a new author.";
            }
            for (let item of data) {
                let list_item = jQuery("<li/>");
                let anchor = jQuery("<a/>", { "href": "#" });
                let name = item["full_name"]
                if (item["orcid_id"] != null && item["orcid_id"] != "") {
                    name += ` (${item["orcid_id"]})`;
                }
                anchor.on("click", { "uuid": item["uuid"], "item_id": item_id }, add_author_event);
                anchor.text (name);
                list_item.html (anchor);
                unordered_list.append(list_item);
            }
            let new_author_description = jQuery("<span/>", { "id": "new-author-description" });
            new_author_description.text(new_author_text);

            let new_author_button = jQuery("<div/>", { "id": "new-author", "class": "a-button" });
            let anchor = jQuery("<a/>", { "href": "#" });
            anchor.on("click", { "item_id": item_id }, add_author_event);
            anchor.text("Create new author record");
            new_author_button.html (anchor);

            let wrapper = jQuery("<div/>", { "id": "authors-ac", "class": "autocomplete" });
            wrapper.html(unordered_list.append(new_author_description.append(new_author_button)));
            jQuery("#authors").addClass("input-for-ac").after(wrapper);
        });
    }
}

function add_funding_event (event) {
    stop_event_propagation (event);
    add_funding (event.data["uuid"], event.data["item_id"]);
}

function new_funding_event (event) {
    stop_event_propagation (event);
    new_funding (event.data["item_id"]);
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
            let html = jQuery("<ul/>");
            for (let item of data) {
                let list_item = jQuery("<li/>");
                let anchor = jQuery("<a/>", { "href": "#" });
                anchor.on ("click", { "uuid": item["uuid"], "item_id": item_id }, add_funding_event);
                anchor.text(item["title"]);
                list_item.append(anchor);
                html.append(list_item);
            }
            let new_funding_button = jQuery("<div/>", { "id": "new-funding", "class": "a-button" });
            let anchor = jQuery("<a/>", { "href": "#" });
            anchor.on ("click", { "item_id": item_id }, new_funding_event);
            anchor.text ("Create funding record");
            new_funding_button.append (anchor);
            html.append (new_funding_button);
            let funding_ac_wrapper = jQuery("<div/>", { "id": "funding-ac", "class": "autocomplete" }).append(html);
            jQuery("#funding").addClass("input-for-ac").after(funding_ac_wrapper);
        });
    }
}

function toggle_cite_collect (event, action) {
    stop_event_propagation (event);
    let other = (action === "collect") ? "cite" : "collect";
    let label = (action === "collect") ? "Collect" : "Citation";
    let item = jQuery(`#${action}`);
    let other_item = jQuery(`#${other}`);
    if (item.is(":visible")) {
        item.slideUp(150, function (){
            jQuery(`#${action}-btn`)
                .removeClass("close")
                .addClass("open")
                .text(label);
        });
        if (!other_item.is(":visible")) {
            jQuery(`#${other}-btn`).removeClass("close").removeClass("secondary");
        }
    } else {
        other_item.slideUp(150, function (){
            jQuery(`#${other}-btn`).removeClass("open").addClass("secondary");
        });
        item.slideDown(150, function (){
            jQuery(`#${action}-btn`)
                .removeClass("open")
                .removeClass("secondary")
                .addClass("close")
                .text(label);
        });
    }
}

function toggle_citation (event) {
    return toggle_cite_collect (event, "cite");
}
function toggle_collect (event) {
    return toggle_cite_collect (event, "collect");
}

function add_tag_event (event) {
    stop_event_propagation (event);
    jQuery('#tag').val(event.data["selected_tag"] + '; ').focus();
    add_tag(event.data["item_id"]);
}

function autocomplete_tags(event, item_id) {
    const current_text = jQuery.trim(jQuery(`#tag`).val());
    if (current_text === "") {
        jQuery("#tag-ac").remove();
        jQuery("#tag").removeClass("input-for-ac");
        return;
    }
    if (current_text.length <= 2) return;
    jQuery.ajax({
        url: '/v3/tags/search',
        type: "POST",
        contentType: "application/json",
        accept: "application/json",
        data: JSON.stringify({"search_for": current_text}),
        dataType: "json"
    }).done(function (data) {
        jQuery("#tag-ac").remove();
        if (data?.length) {
            const unordered_list = jQuery("<ul/>");
            for (let item of data) {
                const anchor = jQuery("<a/>", {href: "#"}).text(item);
                anchor.on("click", {"item_id": item_id, "selected_tag": item}, add_tag_event);
                unordered_list.append(jQuery("<li/>").append(anchor));
            }
            const wrapper = jQuery("<div/>", {id: "tag-ac", class: "autocomplete"}).html(unordered_list);
            jQuery("#tag").addClass("input-for-ac");
            jQuery("#wrap-input-tag").after(wrapper);
        } else {
            jQuery("#tag").removeClass("input-for-ac");
        }
    }).fail(function () {
        jQuery("#tag-ac").remove();
        jQuery("#tag").removeClass("input-for-ac");
    });
}