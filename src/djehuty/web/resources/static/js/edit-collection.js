function render_categories_for_collection (dataset_uuid, categories) {
    for (let category of categories) {
        jQuery(`#category_${category["uuid"]}`).prop("checked", true);
        jQuery(`#category_${category["parent_uuid"]}`).prop("checked", true);
        jQuery(`#subcategories_${category["parent_uuid"]}`).show();
    }
}

function remove_reference_event (event) {
    stop_event_propagation (event);
    remove_reference (event.data["encoded_url"],
                      event.data["collection_id"]);
}

function render_references_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v3/collections/${collection_id}/references`,
        data:        { "limit": 10000, "order": "id", "order_direction": "asc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (references) {
        jQuery("#references-list tbody").empty();
        for (let url of references) {
            let encoded_url = encodeURIComponent(url);
            encoded_url = encoded_url.replace(/\'/g, "%27");
            let row = jQuery("<tr/>");
            let column1 = jQuery("<td/>");
            let column2 = jQuery("<td/>");
            column1.html(jQuery("<a/>", { "target": "_blank", "href": url }).text(url));
            let anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-trash-can", "title": "Remove" });
            anchor.on("click",
                      { "encoded_url": encoded_url, "collection_id": collection_id },
                      remove_reference_event);
            column2.html(anchor);
            row.append([column1, column2]);
            jQuery("#references-list tbody").append(row);
        }
        jQuery("#references-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve references.</p>");
    });
}


function remove_dataset_event (event) {
    stop_event_propagation (event);
    remove_dataset (event.data["dataset_uuid"], event.data["collection_id"]);
}

function render_datasets_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles`,
        data:        { "limit": 10000, "order": "id", "order_direction": "asc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (datasets) {
        jQuery("#articles-list tbody").empty();
        for (let dataset of datasets) {
            let row = jQuery("<tr/>");
            let column1 = jQuery("<td/>");
            let column2 = jQuery("<td/>");
            let anchor = jQuery("<a/>", { "href": `/datasets/${dataset.uuid}` }).text(dataset.title);
            if (dataset.doi != null && dataset.doi != "") {
                anchor.text (`${dataset.title} (${dataset.doi})`);
            }
            column1.html(anchor);
            column2.html(jQuery("<a/>", {
                "href": "#",
                "class": "fas fa-trash-can",
                "title": "Remove"
            }).on("click", { "dataset_uuid": dataset.uuid, "collection_id": collection_id },
                  remove_dataset_event));
            row.append([column1, column2]);
            jQuery("#articles-list tbody").append(row);
        }
        jQuery("#articles-list").show();
    }).fail(function () {
        show_message ("failure","<p>Failed to retrieve dataset details.</p>");
    });
}

function reorder_author (collection_id, author_uuid, direction) {
    jQuery.ajax({
        url:  `/v3/collections/${collection_id}/reorder-authors`,
        data: JSON.stringify({ "author":  author_uuid, "direction": direction }),
        type: "POST",
        contentType: "application/json",
        accept: "application/json"
    }).done (function () {
        render_authors_for_collection (collection_id);
    }).fail(function () {
        show_message ("failure", "<p>Failed to change the order of the authors.</p>");
    });
}

function reorder_author_event (event) {
    stop_event_propagation (event);
    reorder_author (event.data["collection_id"],
                    event.data["author_uuid"],
                    event.data["direction"]);
}

function remove_author_event (event) {
    stop_event_propagation (event);
    remove_author (event.data["author_uuid"], event.data["collection_id"]);
}

function render_authors_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/authors`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (authors) {
        jQuery("#authors-list tbody").empty();
        let number_of_items = authors.length;
        for (let index = 0; index < number_of_items; index++) {
            let author = authors[index];
            let row = jQuery("<tr/>", { "id": `author-${author.uuid}` });
            let column1 = jQuery("<td/>").text(author.full_name);
            let column2 = jQuery("<td/>");
            let column3 = jQuery("<td/>");
            let column4 = jQuery("<td/>");
            let column5 = jQuery("<td/>");
            let orcid = null;
            if (author.orcid_id && author.orcid_id != "") { orcid = author.orcid_id; }
            if (orcid !== null) {
                let orcid_anchor = jQuery("<a/>", {
                    "href": `https://orcid.org/${orcid}`,
                    "target": "_blank",
                    "rel": "noopener noreferrer"
                });
                orcid_anchor.html(jQuery("<img/>", {
                    "src": "/static/images/orcid.svg",
                    "class": "author-orcid",
                    "alt": "ORCID",
                    "title": "ORCID profile (new window)" }));
                column1.append([ orcid_anchor ]);
            }
            if (author.is_editable) {
                column2.append(jQuery("<a/>", {
                    "id": `edit-author-${author.uuid}`,
                    "href": "#",
                    "class": "fas fa-pen",
                    "title": "Edit"
                }).on("click", { "author_uuid": author.uuid, "collection_id": collection_id },
                      edit_author_event));
            }
            if (number_of_items == 1) {
            } else if (index == 0) {
                column3.append(jQuery("<a/>", { "class": "fas fa-angle-down"}).on("click", {
                    "author_uuid": author.uuid,
                    "collection_id": collection_id,
                    "direction": "down" }, reorder_author_event));
            } else if (index == number_of_items - 1) {
                column4.append(jQuery("<a/>", { "class": "fas fa-angle-up"}).on("click", {
                    "author_uuid": author.uuid,
                    "collection_id": collection_id,
                    "direction": "up" }, reorder_author_event));
            } else {
                column3.append(jQuery("<a/>", { "class": "fas fa-angle-down"}).on("click", {
                    "author_uuid": author.uuid,
                    "collection_id": collection_id,
                    "direction": "down" }, reorder_author_event));
                column4.append(jQuery("<a/>", { "class": "fas fa-angle-up"}).on("click", {
                    "author_uuid": author.uuid,
                    "collection_id": collection_id,
                    "direction": "up" }, reorder_author_event));
            }
            column5.append(jQuery("<a/>", {
                "href": "#",
                "class": "fas fa-trash-can",
                "title": "Remove" }).on("click", { "author_uuid": author.uuid,
                                                   "collection_id": collection_id },
                                        remove_author_event));

            row.append([column1, column2, column3, column4, column5]);
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve author details.</p>");
    });
}

function render_funding_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/funding`,
        data:        { "limit": 10000, "order": "id", "order_direction": "asc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (funders) {
        jQuery("#funding-list tbody").empty();
        for (let funding of funders) {
            let row = jQuery("<tr/>");
            let column1 = jQuery("<td/>").text(funding.title);
            let column2 = jQuery("<td/>");
            column2.html(jQuery("<a/>", {
                "href": "#",
                "class": "fas fa-trash-can",
                "title": "Remove"
            }).on("click", { "funding_uuid": funding.uuid, "collection_id": collection_id },
                  remove_funding_event));

            row.append([column1, column2]);
            jQuery("#funding-list tbody").append(row);
        }
        jQuery("#funding-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve funding details.</p>");
    });
}

function remove_funding_event (event) {
    stop_event_propagation (event);
    remove_funding (event.data["funding_uuid"], event.data["collection_id"]);
}

function remove_tag_event (event) {
    stop_event_propagation (event);
    remove_tag (encodeURIComponent(event.data["tag"]), event.data["collection_id"]);
}

function render_tags_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v3/collections/${collection_id}/tags`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (tags) {
        jQuery("#tags-list").empty();
        for (let tag of tags) {
            let row = jQuery("<li/>");
            let anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-trash-can" });
            anchor.on("click", { "tag": tag, "collection_id": collection_id },
                      remove_tag_event);
            row.append(jQuery("<span/>").html(`${tag} &nbsp; `)).append(anchor);
            jQuery("#tags-list").append(row);
        }
        jQuery("#tags-list").show();
    }).fail(function () { show_message ("failure", "<p>Failed to retrieve tags.</p>"); });
}

function add_author (author_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/authors`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "authors": [{ "uuid": author_id }] }),
    }).done(function () {
        render_authors_for_collection (collection_id);
        jQuery("#authors").val("");
        autocomplete_author(null, collection_id);
    }).fail(function () {
        show_message ("failure",`<p>Failed to add ${author_id}.</p>`);
    });
}

function add_funding (funding_uuid, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/funding`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "funders": [{ "uuid": funding_uuid }] }),
    }).done(function () {
        render_funding_for_collection (collection_id);
        jQuery("#funding").val("");
        autocomplete_funding(null, collection_id);
    }).fail(function () { show_message ("failure", `<p>Failed to add ${funding_uuid}.</p>`); });
}

function add_dataset (dataset_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "articles": [dataset_id] }),
    }).done(function () {
        render_datasets_for_collection (collection_id);
        jQuery("#article-search").val("");
        autocomplete_dataset(null, collection_id);
    }).fail(function () {
        show_message ("failure",`<p>Failed to add ${dataset_id}.</p>`);
    });
}

function add_reference (collection_id) {
    let url = jQuery.trim(jQuery("#references").val());
    if (url != "") {
        jQuery.ajax({
            url:         `/v3/collections/${collection_id}/references`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "references": [{ "url": url }] }),
        }).done(function () {
            render_references_for_collection (collection_id);
            jQuery("#references").val("");
        }).fail(function () { show_message ("failure", `<p>Failed to add ${url}.</p>`); });
    }
}

function add_tag (collection_id) {
    let tag = jQuery.trim(jQuery("#tag").val());
    if (tag == "") { return 0; }

    let tags = []
    if (tag.indexOf (";") >= 0) {
        let items = tag.split(";");
        for (item of items) {
            if (item != "") { tags.push(jQuery.trim(item)); }
        }
    } else {
        tags = [tag];
    }
    jQuery.ajax({
        url:         `/v3/collections/${collection_id}/tags`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "tags": tags }),
    }).done(function () {
        render_tags_for_collection (collection_id);
        jQuery("#tag").val("");
        autocomplete_tags(null, collection_id);
    }).fail(function () { show_message ("failure", `<p>Failed to add ${tag}.</p>`); });
}

function remove_author (author_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/authors/${author_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_authors_for_collection (collection_id); })
      .fail(function () {
          show_message ("failure",`<p>Failed to remove ${author_id}</p>`);
      });
}

function remove_funding (funding_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/funding/${funding_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_funding_for_collection (collection_id); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${funding_id}.</p>`); });
}

function remove_reference (url, collection_id) {
    jQuery.ajax({
        url:         `/v3/collections/${collection_id}/references?url=${url}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_references_for_collection (collection_id); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${url}</p>`); });
}

function remove_dataset (dataset_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles/${dataset_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () {
        render_datasets_for_collection (collection_id);
    }).fail(function () {
        show_message ("failure",`<p>Failed to remove ${dataset_id}.</p>`);
    });
}

function remove_tag (tag, collection_id) {
    jQuery.ajax({
        url:         `/v3/collections/${collection_id}/tags?tag=${tag}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_tags_for_collection (collection_id); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${tag}.</p>`); });
}

function delete_collection (collection_id, event) {
    stop_event_propagation (event);
    if (confirm("Deleting this draft collection is unrecoverable. "+
                "Do you want to continue?"))
    {
        jQuery.ajax({
            type:        "DELETE",
            url:         `/v2/account/collections/${collection_id}`
        }).done(function () { window.location.pathname = "/my/collections"; })
          .fail(function () {
              show_message ("failure", "<p>Failed to delete collection.</p>");
          });
    }
}

function gather_form_data () {
    let categories   = jQuery("input[name='categories']:checked");
    let category_ids = [];
    for (let category of categories) {
        category_ids.push(jQuery(category).val());
    }

    let group_id = jQuery("input[name='groups']:checked")[0];
    if (group_id !== undefined) { group_id = group_id["value"]; }
    else { group_id = null; }

    let title = or_null(jQuery("#title").val());
    if (title == "" || title == null) { title = "Untitled collection"; }
    let form_data = {
        "title":          title,
        "description":    or_null(jQuery("#description .ql-editor").html()),
        "resource_title": or_null(jQuery("#resource_title").val()),
        "resource_doi":   or_null(jQuery("#resource_doi").val()),
        "geolocation":    or_null(jQuery("#geolocation").val()),
        "longitude":      or_null(jQuery("#longitude").val()),
        "latitude":       or_null(jQuery("#latitude").val()),
        "organizations":  or_null(jQuery("#organizations").val()),
        "publisher":      or_null(jQuery("#publisher").val()),
        "language":       or_null(jQuery("#language").val()),
        "time_coverage":  or_null(jQuery("#time_coverage").val()),
        "group_id":       group_id,
        "categories":     category_ids
    };

    if (form_data["description"] !== null) {
        form_data["description"] = form_data["description"].replaceAll('<p class="ql-align-justify">', '<p>');
    }

    return form_data;
}

function save_collection (collection_id, event, notify=true, on_success=jQuery.noop) {
    stop_event_propagation (event);

    // When keywords were entered but yet submitted, handle those first.
    add_tag (collection_id);
    add_reference (collection_id);

    form_data = gather_form_data();
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}`,
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        if (notify) {
            show_message ("success", "<p>Saved changes.</p>");
        }
        on_success ();
    }).fail(function (jqXHR, textStatus, errorThrown) {
        if (notify) {
            let json = jqXHR.responseJSON;
            let message = "<p>Failed to save draft. Please try again at a later time.</p>";
            if (json) { message = `<p>Failed to save draft: ${json.message}</p>`; }
            show_message ("failure", message);
        }
    });
}

function publish_collection (collection_id, event) {
    stop_event_propagation (event);
    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css('opacity', '0.15');
    save_collection (collection_id, event, false, function() {
        jQuery.ajax({
            url:         `/v3/collections/${collection_id}/publish`,
            type:        "POST",
            accept:      "application/json",
        }).done(function () {
            window.location.replace(`/my/collections/published/${collection_id}`);
        }).fail(function (response, text_status, error_code) {
            jQuery(".missing-required").removeClass("missing-required");
            let error_messages = jQuery.parseJSON (response.responseText);
            let error_message = "<p>Please fill in all required fields.</p>";
            if (error_messages.length > 0) {
                for (let message of error_messages) {
                    if (message.field_name == "license_id") {
                        jQuery("#license_open").addClass("missing-required");
                        jQuery("#license_embargoed").addClass("missing-required");
                    } else if (message.field_name == "group_id") {
                        jQuery("#groups-wrapper").addClass("missing-required");
                    } else if (message.field_name == "categories") {
                        jQuery("#categories-wrapper").addClass("missing-required");
                    } else {
                        jQuery(`#${message.field_name}`).addClass("missing-required");
                    }
                }
            }
            show_message ("failure", `${error_message}`);
            jQuery("#content-wrapper").css('opacity', '1.0');
            jQuery("#content").removeClass("loader-top");
        });
    });
}

function add_dataset_event (event) {
    stop_event_propagation (event);
    add_dataset (event.data["dataset_uuid"], event.data["collection_id"]);
}

function autocomplete_dataset (event, collection_id) {
    let current_text = jQuery.trim(jQuery("#article-search").val());
    if (current_text == "") {
        jQuery("#articles-ac").remove();
        jQuery("#article-search").removeClass("input-for-ac");
    } else if (current_text.length > 2) {
        jQuery.ajax({
            url:         `/v2/articles/search`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "search_for": current_text, "is_latest": true }),
            dataType:    "json"
        }).done(function (data) {
            jQuery("#articles-ac").remove();
            let list = jQuery("<ul/>");
            for (let item of data) {
                let row = jQuery("<li/>");
                let anchor = jQuery("<a/>", {
                    "href": "#" }).on("click", {
                        "dataset_uuid": item["uuid"],
                        "collection_id": collection_id
                    }, add_dataset_event);

                anchor.text (item["title"]);
                if (item["doi"] != null && item["doi"] != "") {
                    anchor.text (`${item["title"]} (${item["doi"]})`);
                }
                row.append(anchor);
                list.append(row);
            }
            jQuery("#article-search")
                .addClass("input-for-ac")
                .after(jQuery("<div/>", {
                    "id": "articles-ac",
                    "class": "autocomplete" }).html(list));
        });
    }
}

function submit_new_author_event (event) {
    stop_event_propagation (event);
    submit_new_author (event.data["collection_id"]);
}

function new_author (dataset_uuid) {
    let banner = `<br><span><i>Enter the details of the author you want to add.</i></span>`;
    jQuery("#new-author-description").after(banner).remove();
    let html = jQuery("<div/>", { "id": "new-author-form" });
    html.append(jQuery ("<label/>", { "for": "author_first_name" }).text("First name"));
    html.append(jQuery ("<span/>", { "class": "required-field" }).text("*"));
    html.append(jQuery ("<input/>", { "type": "text", "id": "author_first_name", "name": "author_first_name" }));
    html.append(jQuery ("<label/>", { "for": "author_last_name" }).text("Last name"));
    html.append(jQuery ("<span/>", { "class": "required-field" }).text("*"));
    html.append(jQuery ("<input/>", { "type": "text", "id": "author_last_name", "name": "author_last_name" }));
    html.append(jQuery ("<label/>", { "for": "author_email" }).text("E-mail address"));
    html.append(jQuery ("<input/>", { "type": "text", "id": "author_email", "name": "author_email" }));
    html.append(jQuery ("<label/>", { "for": "author_orcid" }).text("ORCID"));
    html.append(jQuery ("<input/>", { "type": "text", "id": "author_orcid", "name": "author_orcid" }));

    let button_wrapper = jQuery("<div/>", { "id": "new-author", "class": "a-button" });
    let anchor = jQuery("<a/>", { "href": "#" }).text("Add author");
    anchor.on ("click", { "collection_id": collection_id}, submit_new_author_event);
    button_wrapper.append(anchor);

    html.append(button_wrapper);
    jQuery("#authors-ac ul").remove();
    jQuery("#new-author").remove();
    jQuery("#authors-ac").append(html);
}

function submit_new_funding_event (event) {
    stop_event_propagation (event);
    submit_new_funding (event.data["collection_id"]);
}

function new_funding (collection_id) {
    let html = jQuery("<div/>", { "id": "new-funding-form" });
    html.append (jQuery ("<label/>", { "for": "funding_title" }).text("Title"));
    html.append (jQuery ("<input/>", { "type": "text", "id": "funding_title", "name": "funding_title" }));
    html.append (jQuery ("<label/>", { "for": "funding_grant_code" }).text("Grant code"));
    html.append (jQuery ("<input/>", { "type": "text", "id": "funding_grant_code", "name": "funding_grant_code" }));
    html.append (jQuery ("<label/>", { "for": "funding_funder_name" }).text("Funder name"));
    html.append (jQuery ("<input/>", { "type": "text", "id": "funding_funder_name", "name": "funding_funder_name" }));
    html.append (jQuery ("<label/>", { "for": "funding_url" }).text("URL"));
    html.append (jQuery ("<input/>", { "type": "text", "id": "funding_url", "name": "funding_url" }));

    let new_funding_button = jQuery ("<div/>", { "id": "new-funding", "class": "a-button" });
    let anchor = jQuery("<a/>", { "href": "#" }).text("Add funding");
    anchor.on ("click", { "collection_id": collection_id }, submit_new_funding_event);
    new_funding_button.append (anchor);
    html.append (new_funding_button);

    jQuery("#funding-ac ul").remove();
    jQuery("#new-funding").remove();
    jQuery("#funding-ac").append(html);
}

function submit_new_author (collection_id) {
    let first_name = jQuery("#author_first_name").val();
    let last_name = jQuery("#author_last_name").val();
    let authors = [{
        "name":       `${first_name} ${last_name}`,
        "first_name": first_name,
        "last_name":  last_name,
        "email":      jQuery("#author_email").val(),
        "orcid":      jQuery("#author_orcid").val()
    }];

    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/authors`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "authors": authors }),
    }).done(function () {
        jQuery("#authors-ac").remove();
        jQuery("#authors").removeClass("input-for-ac");
        render_authors_for_collection (collection_id);
    }).fail(function () {
        show_message ("failure", "<p>Failed to add author.</p>");
    });
}

function submit_new_funding (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/funding`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({
            "funders": [{
                "title":       jQuery("#funding_title").val(),
                "grant_code":  jQuery("#funding_grant_code").val(),
                "funder_name": jQuery("#funding_funder_name").val(),
                "url":         jQuery("#funding_url").val()
            }]
        }),
    }).done(function () {
        jQuery("#funding-ac").remove();
        jQuery("#funding").removeClass("input-for-ac");
        render_funding_for_collection (collection_id);
    }).fail(function () { show_message ("failure", `<p>Failed to add funding.</p>`); });
}

function activate (collection_id) {
    install_sticky_header();
    install_touchable_help_icons();

    jQuery(".collection-content").hide();
    jQuery(".collection-content-loader").show();
    jQuery(".collection-content-loader").addClass("loader");
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");

    jQuery("#delete").on("click", function (event) { delete_collection (collection_id, event); });
    jQuery("#save").on("click", function (event)   { save_collection (collection_id, event); });
    jQuery("#publish").on("click", function (event) { publish_collection (collection_id, event); });
    // Initialize Quill to provide the WYSIWYG editor.
    new Quill('#description', { theme: '4tu' });

    jQuery("#authors").on("input", function (event) {
        return autocomplete_author (event, collection_id);
    });
    jQuery("#funding").on("input", function (event) {
        return autocomplete_funding (event, collection_id);
    });
    jQuery("#references").on("keypress", function(e){
        if(e.which == 13){
            add_reference(collection_id);
        }
    });
    jQuery("#add-reference-button").on("click", function(event) {
        stop_event_propagation (event);
        add_reference (collection_id);
    });
    jQuery("#article-search").on("input", function (event) {
        return autocomplete_dataset (event, collection_id);
    });

    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        render_categories_for_collection (collection_id, data["categories"]);
        render_authors_for_collection (collection_id);
        render_references_for_collection (collection_id);
        render_datasets_for_collection (collection_id);
        render_tags_for_collection (collection_id);
        render_funding_for_collection (collection_id);

        if (data["group_id"] != null) {
            jQuery(`#group_${data["group_id"]}`).prop("checked", true);
        }
        jQuery("#add-keyword-button").on("click", function(event) {
            stop_event_propagation (event);
            add_tag (collection_id);
        });
        jQuery("#tag").on("keypress", function(e){
            if(e.which == 13) { add_tag(collection_id); }
        });
        jQuery("#tag").on("input", function (event) {
            return autocomplete_tags(event, collection_id);
        });
        jQuery("#expand-categories-button").on("click", toggle_categories);
        jQuery(".collection-content-loader").hide();
        jQuery(".collection-content").fadeIn(200);
    }).fail(function () {
        show_message ("failure","<p>Failed to retrieve collection.</p>");
    });
}
