function render_categories_for_collection (dataset_uuid, categories) {
    for (let category of categories) {
        jQuery(`#category_${category["uuid"]}`).prop("checked", true);
        jQuery(`#category_${category["parent_uuid"]}`).prop("checked", true);
        jQuery(`#subcategories_${category["parent_uuid"]}`).show();
    }
}

function render_references_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v3/collections/${collection_id}/references`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (references) {
        jQuery("#references-list tbody").empty();
        for (let url of references) {
            let row = `<tr><td><a target="_blank" href="${encodeURIComponent(url)}">`;
            row += `${url}</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_reference('${encodeURIComponent(url)}', `;
            row += `'${collection_id}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#references-list tbody").append(row);
        }
        jQuery("#references-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve references.</p>");
    });
}

function render_datasets_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (datasets) {
        jQuery("#articles-list tbody").empty();
        for (let dataset of datasets) {
            let row = `<tr><td><a href="/datasets/${dataset.uuid}">${dataset.title}`;
            if (dataset.doi != null && dataset.doi != "") {
                row += ` (${dataset.doi})`;
            }
            row += `</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_dataset('${dataset.uuid}', `;
            row += `'${collection_id}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#articles-list tbody").append(row);
        }
        jQuery("#articles-list").show();
    }).fail(function () {
        show_message ("failure","<p>Failed to retrieve dataset details.</p>");
    });
}

function render_authors_for_collection (collection_id, authors = null) {

    function draw_authors_for_collection (collection_id, authors) {
        jQuery("#authors-list tbody").empty();
        for (let author of authors) {
            let row = `<tr><td><a href="#">${author.full_name}`;
            if (author.orcid_id != null && author.orcid_id != "") {
                row += ` (${author.orcid_id})`;
            }
            row += `</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_author('${author.uuid}', `;
            row += `'${collection_id}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }

    if (authors === null) {
        jQuery.ajax({
            url:         `/v2/account/collections/${collection_id}/authors`,
            data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
            type:        "GET",
            accept:      "application/json",
        }).done(function (authors) {
            draw_authors_for_collection (collection_id, authors);
        }).fail(function () {
            show_message ("failure","<p>Failed to retrieve author details.</p>");
        });
    } else {
        draw_authors_for_collection (collection_id, authors);
    }
}

function render_funding_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/funding`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (funders) {
        jQuery("#funding-list tbody").empty();
        for (let funding of funders) {
            let row = `<tr><td>${funding.title}</td>`;
            row += `<td><a href="#" `;
            row += `onclick="javascript:remove_funding('${funding.uuid}', `;
            row += `'${collection_id}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#funding-list tbody").append(row);
        }
        jQuery("#funding-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve funding details.</p>");
    });
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
            let row = `<li>${tag} &nbsp; <a href="#" class="fas fa-trash-can"`;
            row += ` onclick="javascript:remove_tag('${encodeURIComponent(tag)}', `;
            row += `'${collection_id}'); return false;"></a></li>`;
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

    jQuery.ajax({
        url:         `/v3/collections/${collection_id}/tags`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "tags": [tag] }),
    }).done(function () {
        render_tags_for_collection (collection_id);
        jQuery("#tag").val("");
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
    event.preventDefault();
    event.stopPropagation();
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

    let form_data = {
        "title":          or_null(jQuery("#title").val()),
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

    return form_data;
}

function save_collection (collection_id, event, notify=true, on_success=jQuery.noop) {
    event.preventDefault();
    event.stopPropagation();

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
    }).fail(function () {
        if (notify) {
            show_message ("failure", "<p>Failed to save form.</p>");
        }
    });
}

function publish_collection (collection_id, event) {
    event.preventDefault();
    event.stopPropagation();

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
                error_message = "<p>Please fill in all required fields.</p>";
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

function reserve_doi (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/reserve_doi`,
        type:        "POST",
        accept:      "application/json",
    }).done(function (record) {
        jQuery("#doi-wrapper p").replaceWith(
            `<p>The DOI of your collection will be: <strong>${record["doi"]}</strong></p>`
        );
    }).fail(function () {
        show_message ("failure", "<p>Failed to reserve DOI. Please try again later.</p>");
    });
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
            let html = "<ul>";
            for (let item of data) {
                html += `<li><a href="#" `;
                html += `onclick="javascript:add_dataset('${item["uuid"]}', `;
                html += `'${collection_id}'); return false;">${item["title"]}`;
                if (item["doi"] != null && item["doi"] != "") {
                    html += ` (${item["doi"]})`;
                }
                html += "</a>";
            }
            html += "</ul>";
            jQuery("#article-search")
                .addClass("input-for-ac")
                .after(`<div id="articles-ac" class="autocomplete">${html}</div>`);
        });
    }
}

function autocomplete_author (event, collection_id) {
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
                html += `'${collection_id}'); return false;">${item["full_name"]}`;
                if (item["orcid_id"] != null && item["orcid_id"] != "") {
                    html += ` (${item["orcid_id"]})`;
                }
                html += "</a>";
            }
            html += "</ul>";

            html += `<div id="new-author" class="a-button"><a href="#" `;
            html += `onclick="javascript:new_author('${collection_id}'); `;
            html += `return false;">Create new author record</a></div>`;
            jQuery("#authors")
                .addClass("input-for-ac")
                .after(`<div id="authors-ac" class="autocomplete">${html}</div>`);
        });
    }
}

function new_author (collection_id) {
    let html = `<div id="new-author-form">`;
    html += `<label for="author_first_name">First name</label>`;
    html += `<input type="text" id="author_first_name" name="author_first_name">`;
    html += `<label for="author_first_name">Last name</label>`;
    html += `<input type="text" id="author_last_name" name="author_last_name">`;
    html += `<label for="author_first_name">E-mail address</label>`;
    html += `<input type="text" id="author_email" name="author_email">`;
    html += `<label for="author_first_name">ORCID</label>`;
    html += `<input type="text" id="author_orcid" name="author_orcid">`;
    html += `<div id="new-author" class="a-button">`;
    html += `<a href="#" onclick="javascript:submit_new_author('${collection_id}'); `;
    html += `return false;">Add author</a></div>`;
    html += `</div>`;
    jQuery("#authors-ac ul").remove();
    jQuery("#new-author").remove();
    jQuery("#authors-ac").append(html);
}

function new_funding (collection_id) {
    let html = `<div id="new-funding-form">`;
    html += `<label for="funding_title">Title</label>`;
    html += `<input type="text" id="funding_title" name="funding_title">`;
    html += `<label for="funding_grant_code">Grant code</label>`;
    html += `<input type="text" id="funding_grant_code" name="funding_grant_code">`;
    html += `<label for="funding_funder_name">Funder name</label>`;
    html += `<input type="text" id="funding_funder_name" name="funding_funder_name">`;
    html += `<label for="funding_url">URL</label>`;
    html += `<input type="text" id="funding_url" name="funding_url">`;
    html += `<div id="new-funding" class="a-button">`;
    html += `<a href="#" onclick="javascript:submit_new_funding('${collection_id}'); `;
    html += `return false;">Add funding</a></div>`;
    html += `</div>`;
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
    jQuery("#article-search").on("input", function (event) {
        return autocomplete_dataset (event, collection_id);
    });

    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        render_categories_for_collection (collection_id, data["categories"]);
        render_authors_for_collection (collection_id, data["authors"]);
        render_references_for_collection (collection_id);
        render_datasets_for_collection (collection_id);
        render_tags_for_collection (collection_id);
        render_funding_for_collection (collection_id);

        if (data["group_id"] != null) {
            jQuery(`#group_${data["group_id"]}`).prop("checked", true);
        }
        if (data["doi"]) {
            jQuery("#doi-wrapper p").replaceWith(
                `<p>The DOI of your collection will be: <strong>${data["doi"]}</strong></p>`
            );
        }
        jQuery("#add-keyword-button").on("click", function(event) {
            event.preventDefault();
            event.stopPropagation();
            add_tag (collection_id);
        });
        jQuery("#tag").on("keypress", function(e){
            if(e.which == 13) { add_tag(collection_id); }
        });

        jQuery(".collection-content-loader").hide();
        jQuery(".collection-content").fadeIn(200);
    }).fail(function () {
        show_message ("failure","<p>Failed to retrieve collection.</p>");
    });
}
