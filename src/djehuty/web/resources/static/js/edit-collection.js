function render_in_form (text) { return [text].join(''); }
function or_null (value) { return (value == "" || value == "<p><br></p>") ? null : value; }

function render_categories_for_collection (dataset_uuid, categories) {
    for (category of categories) {
        jQuery(`#category_${category["uuid"]}`).prop("checked", true);
        jQuery(`#category_${category["parent_uuid"]}`).prop("checked", true);
        jQuery(`#subcategories_${category["parent_uuid"]}`).show();
    }
}

function render_datasets_for_collection (collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (datasets) {
        jQuery("#articles-list tbody").empty();
        for (dataset of datasets) {
            row = `<tr><td><a href="#">${dataset.title}`;
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
        console.log("Failed to retrieve dataset details.");
    });
}

function render_authors_for_collection (collection_id, authors = null) {

    function draw_authors_for_collection (collection_id, authors) {
        jQuery("#authors-list tbody").empty();
        for (author of authors) {
            row = `<tr><td><a href="#">${author.full_name}`;
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
            console.log("Failed to retrieve author details.");
        });
    } else {
        draw_authors_for_collection (collection_id, authors);
    }
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
    }).fail(function () { console.log (`Failed to add ${author_id}`); });
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
    }).fail(function () { console.log (`Failed to add ${dataset_id}`); });
}

function remove_author (author_id, collection_id) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/authors/${author_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (authors) { render_authors_for_collection (collection_id); })
      .fail(function () { console.log (`Failed to remove ${author_id}`); });
}

function remove_dataset (dataset_id, collection_id) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles/${dataset_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (datasets) {
        console.log (`Removed dataset ${dataset_id}.`);
        render_datasets_for_collection (collection_id);
    })
      .fail(function () { console.log (`Failed to remove ${dataset_id}`); });
}

function delete_collection (collection_id) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm("Deleting this draft collection is unrecoverable. "+
                "Do you want to continue?"))
    {
        let jqxhr = jQuery.ajax({
            url:         `/v2/account/collections/${collection_id}`,
            type:        "DELETE",
        }).done(function () { window.location.pathname = '/my/collections' })
          .fail(function () { console.log("Failed to delete collection."); });
    }
}

function save_collection (collection_id) {
    event.preventDefault();
    event.stopPropagation();

    categories   = jQuery("input[name='categories']:checked");
    category_ids = []
    for (category of categories) {
        category_ids.push(jQuery(category).val());
    }

    let group_id = jQuery("input[name='groups']:checked")[0]
    if (group_id !== undefined) { group_id = group_id["value"]; }
    else { group_id = null; }

    form_data = {
        "title":          or_null(jQuery("#title").val()),
        "description":    or_null(jQuery("#description .ql-editor").html()),
        "resource_title": or_null(jQuery("#resource_title").val()),
        "resource_doi":   or_null(jQuery("#resource_doi").val()),
        "geolocation":    or_null(jQuery("#geolocation").val()),
        "longitude":      or_null(jQuery("#longitude").val()),
        "latitude":       or_null(jQuery("#latitude").val()),
        "organizations":  or_null(jQuery("#organizations").val()),
        "publisher":      or_null(jQuery("#publisher").val()),
        "group_id":       group_id,
        "categories":     category_ids
    }
    
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}`,
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        jQuery("#message")
            .addClass("success")
            .append("<p>Saved changed.</p>")
            .fadeIn(250);
        setTimeout(function() {
            jQuery("#message").fadeOut(500, function() {
                jQuery("#message").removeClass("success").empty();
            });
        }, 5000);
        console.log("Form was saved.");
    }).fail(function () { console.log("Failed to save form."); });
}

function autocomplete_dataset (event, collection_id) {
    let current_text = jQuery.trim(jQuery("#article-search").val());
    if (current_text == "") {
        jQuery("#articles-ac").remove();
        jQuery("#article-search").removeClass("input-for-ac");
    } else if (current_text.length > 2) {
        console.log(`Triggered datasets autocomplete with ${current_text}.`);
        jQuery.ajax({
            url:         `/v2/articles/search`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "search_for": current_text }),
            dataType:    "json"
        }).done(function (data) {
            jQuery("#articles-ac").remove();
            html = "<ul>";
            for (item of data) {
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
            html = "<ul>";
            for (item of data) {
                html += `<li><a href="#" `;
                html += `onclick="javascript:add_author('${item["uuid"]}', `;
                html += `'${collection_id}'); return false;">${item["full_name"]}`;
                if (item["orcid_id"] != null && item["orcid_id"] != "") {
                    html += ` (${item["orcid_id"]})`;
                }
                html += "</a>";
            }
            html += "</ul>";

            html += `<div id="new-author" class="a-button"><a href="#" `
            html += `onclick="javascript:new_author('${collection_id}'); `
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

function submit_new_author (collection_id) {
    first_name = jQuery("#author_first_name").val();
    last_name  = jQuery("#author_last_name").val();
    email      = jQuery("#author_email").val();
    orcid      = jQuery("#author_orcid").val();

    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/authors`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({
            "authors": [{
                "name":       `${first_name} ${last_name}`,
                "first_name": first_name,
                "last_name":  last_name,
                "email":      email,
                "orcid":      orcid
            }]
        }),
    }).done(function () {
        jQuery("#authors-ac").remove();
        jQuery("#authors").removeClass("input-for-ac");
        render_authors_for_collection (collection_id);
    }).fail(function () { console.log (`Failed to add author.`); });
}

function activate (collection_id) {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");
    jQuery("#delete").on("click", function (event) { delete_collection (collection_id); });
    jQuery("#save").on("click", function (event)   { save_collection (collection_id); });
    let quill = new Quill('#description', { theme: '4tu' });

    var submenu_offset = jQuery("#submenu").offset().top;
    jQuery(window).on('resize scroll', function() {
        let scroll_offset  = jQuery(window).scrollTop();
        if (submenu_offset <= scroll_offset) {
            jQuery("#submenu").addClass("sticky");
            jQuery("#message").addClass("sticky-message");
            jQuery("#message").width(jQuery("#content-wrapper").width());
        } else {
            jQuery("#submenu").removeClass("sticky");
            jQuery("#message").removeClass("sticky-message");
        }
    });

    jQuery(".help-icon").on("click", function () {
        let selector = jQuery(this).find(".help-text");
        if (selector.is(":visible") ||
            selector.css("display") != "none") {
            jQuery(this).removeClass("help-icon-clicked");
        } else {
            jQuery(this).addClass("help-icon-clicked");
        }
    });

    jQuery("#authors").on("input", function (event) {
        return autocomplete_author (event, collection_id);
    });
    jQuery("#article-search").on("input", function (event) {
        return autocomplete_dataset (event, collection_id);
    });

    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        render_categories_for_collection (collection_id, categories = data["categories"]);
        render_authors_for_collection (collection_id, authors = data["authors"]);
        render_datasets_for_collection (collection_id);

        if (data["group_id"] != null) {
            jQuery(`#group_${data["group_id"]}`).prop("checked", true);
        }        
    }).fail(function () {
        console.log("Failed to retrieve collection.");
    });
}
