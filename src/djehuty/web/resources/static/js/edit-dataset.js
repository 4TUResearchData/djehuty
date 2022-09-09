function render_in_form (text) { return [text].join(''); }
function or_null (value) { return (value == "" || value == "<p><br></p>") ? null : value; }

function delete_dataset (dataset_uuid, event) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm("Deleting this draft dataset is unrecoverable. "+
                "Do you want to continue?"))
    {
        let jqxhr = jQuery.ajax({
            url:         `/v2/account/articles/${dataset_uuid}`,
            type:        "DELETE",
        }).done(function () { window.location.pathname = '/my/datasets' })
          .fail(function () { console.log("Failed to retrieve licenses."); });
    }
}

function save_dataset (dataset_uuid, event, notify=true) {
    event.preventDefault();
    event.stopPropagation();

    categories   = jQuery("input[name='categories']:checked");
    category_ids = []
    for (category of categories) {
        category_ids.push(jQuery(category).val());
    }

    let defined_type_name = null;
    if (jQuery("#upload_software").prop("checked")) {
        defined_type_name = "software";
    } else {
        defined_type_name = "dataset";
    }

    let group_id = jQuery("input[name='groups']:checked")[0]
    if (group_id !== undefined) { group_id = group_id["value"]; }
    else { group_id = null; }

    let is_embargoed  = jQuery("#embargoed_access").prop("checked");
    let is_restricted = jQuery("#restricted_access").prop("checked");
    let is_closed     = jQuery("#closed_access").prop("checked");

    form_data = {
        "title":          or_null(jQuery("#title").val()),
        "description":    or_null(jQuery("#description .ql-editor").html()),
        "license_id":     or_null(jQuery(".license-selector").val()),
        "resource_title": or_null(jQuery("#resource_title").val()),
        "resource_doi":   or_null(jQuery("#resource_doi").val()),
        "geolocation":    or_null(jQuery("#geolocation").val()),
        "longitude":      or_null(jQuery("#longitude").val()),
        "latitude":       or_null(jQuery("#latitude").val()),
        "format":         or_null(jQuery("#format").val()),
        "data_link":      or_null(jQuery("#data_link").val()),
        "derived_from":   or_null(jQuery("#derived_from").val()),
        "same_as":        or_null(jQuery("#same_as").val()),
        "organizations":  or_null(jQuery("#organizations").val()),
        "publisher":      or_null(jQuery("#publisher").val()),
        "time_coverage":  or_null(jQuery("#time_coverage").val()),
        "language":       or_null(jQuery("#language").val()),
        "defined_type_name": defined_type_name,
        "is_embargoed":   is_embargoed || is_restricted || is_closed,
        "group_id":       group_id,
        "categories":     category_ids
    }

    if (is_embargoed) {
        form_data["embargo_until_date"] = or_null(jQuery("#embargo_until_date").val());
        form_data["embargo_title"]  = or_null(jQuery("#embargo_title").val());
        form_data["embargo_reason"] = or_null(jQuery("#embargo_reason .ql-editor").html());

        if (jQuery("#files_only_embargo").prop("checked")) {
            form_data["embargo_type"] = "file";
        } else if (jQuery("#content_embargo").prop("checked")) {
            form_data["embargo_type"] = "article";
        }
    } else if (is_restricted) {
        form_data["embargo_until_date"] = null;
        form_data["embargo_title"]  = "Restricted access";
        form_data["embargo_reason"] = or_null(jQuery("#restricted_access_reason .ql-editor").html());
        form_data["embargo_options"] = [{ "id": 1000, "type": "restricted_access" }]
    } else if (is_closed) {
        form_data["embargo_until_date"] = null;
        form_data["embargo_title"]  = "Closed access";
        form_data["embargo_reason"] = or_null(jQuery("#closed_access_reason .ql-editor").html());
        form_data["embargo_options"] = [{ "id": 1001, "type": "closed_access" }]
    }

    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}`,
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        if (notify) {
            jQuery("#message")
                .addClass("success")
                .append("<p>Saved changed.</p>")
                .fadeIn(250);
            setTimeout(function() {
                jQuery("#message").fadeOut(500, function() {
                    jQuery("#message").removeClass("success").empty();
                });
            }, 5000);
        }
    })
      .fail(function () { console.log("Failed to save form."); });
}

function render_licenses (dataset) {
    chosen_license = null;
    try { chosen_license = dataset.license.value; }
    catch (TypeError) {}

    let jqxhr = jQuery.ajax({
        url:         "/v2/licenses",
        type:        "GET",
        accept:      "application/json",
    }).done(function (licenses) {
        for (license of licenses) {
            selected = "";
            selected = ((chosen_license == license.value) ? " selected" : "");
            html = `<option value="${license.value}"${selected}>${license.name}</option>`;
            jQuery(".license-selector").append(html);
        }
    }).fail(function () {
        console.log("Failed to retrieve licenses.");
    });
}

function render_categories_for_dataset (dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/categories`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (categories) {
        for (category of categories) {
            jQuery(`#category_${category["uuid"]}`).prop("checked", true);
            jQuery(`#category_${category["parent_uuid"]}`).prop("checked", true);
            jQuery(`#subcategories_${category["parent_uuid"]}`).show();
        }
    }).fail(function () {
        console.log("Failed to retrieve article categories.");
    });
}

function render_references_for_dataset (dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/references`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (references) {
        jQuery("#references-list tbody").empty();
        for (url of references) {
            row = `<tr><td><a target="_blank" href="${encodeURIComponent(url)}">`;
            row += `${url}</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_reference('${encodeURIComponent(url)}', `;
            row += `'${dataset_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#references-list tbody").append(row);
        }
        jQuery("#references-list").show();
    }).fail(function () {
        console.log("Failed to retrieve reference details.");
    });
}

function render_authors_for_dataset (dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/authors`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (authors) {
        jQuery("#authors-list tbody").empty();
        for (author of authors) {
            row = `<tr><td>${author.full_name}`;
            if (author.orcid_id != null && author.orcid_id != "") {
                row += ` (${author.orcid_id})`;
            }
            row += `</td><td><a href="#" `;
            row += `onclick="javascript:remove_author('${author.uuid}', `;
            row += `'${dataset_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }).fail(function () {
        console.log("Failed to retrieve author details.");
    });
}

function render_funding_for_dataset (dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/funding`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (funders) {
        jQuery("#funding-list tbody").empty();
        for (funding of funders) {
            row = `<tr><td>${funding.title}</td>`;
            row += `<td><a href="#" `;
            row += `onclick="javascript:remove_funding('${funding.uuid}', `;
            row += `'${dataset_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#funding-list tbody").append(row);
        }
        jQuery("#funding-list").show();
    }).fail(function () {
        console.log("Failed to retrieve funding details.");
    });
}

function render_git_files_for_dataset (dataset_uuid, event) {
    if (event !== null) {
        event.preventDefault();
        event.stopPropagation();
    }
    let jqxhr = jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}.git/files`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (files) {
        jQuery("#git-files").empty();
        for (index in files) {
            jQuery("#git-files").append(`<li>${files[index]}</li>`);
        }
    }).fail(function () {
        console.log("Failed to retrieve Git file details.");
    });
}
function render_files_for_dataset (dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (files) {
        jQuery("#files tbody").empty();
        if (files.length > 0) {
            jQuery("input[name='record_type']").attr('disabled', true);

            for (index in files) {
                file = files[index];
                if (file.name === null) {
                    file.name = file.download_url;
                }
                html = `<tr><td><a href="${file.download_url}">${file.name}</a> (${prettify_size(file.size)})</td>`;
                html += `<td>${render_in_form(file["computed_md5"])}</td>`;
                html += `<td><a href="#" onclick="javascript:remove_file('${file.uuid}',`;
                html += ` '${dataset_uuid}'); return false;" class="fas fa-trash-can" `;
                html += `title="Remove"></a></td></tr>`;
                jQuery("#files tbody").append(html);
            }
            jQuery("#files").show();
        }
        else {
            jQuery("#files").hide();
            jQuery("input[name='record_type']").attr('disabled', false);
        }
    }).fail(function () {
        console.log("Failed to retrieve file details.");
    });
}

function add_author (author_uuid, dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/authors`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "authors": [{ "uuid": author_uuid }] }),
    }).done(function () {
        render_authors_for_dataset (dataset_uuid);
        jQuery("#authors").val("");
        autocomplete_author(null, dataset_uuid);
    }).fail(function () { console.log (`Failed to add ${author_uuid}`); });
}

function add_funding (funding_uuid, dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/funding`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "funders": [{ "uuid": funding_uuid }] }),
    }).done(function () {
        render_funding_for_dataset (dataset_uuid);
        jQuery("#funding").val("");
        autocomplete_funding(null, dataset_uuid);
    }).fail(function () { console.log (`Failed to add ${funding_uuid}`); });
}

function submit_external_link (dataset_uuid) {
    let url = jQuery("#external_url").val();
    if (url == "") {
        jQuery("#external_url").css("background", "#cc0000");
        return false;
    }
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "link": url }),
    }).done(function () {
        jQuery("#external_url").val("");
        jQuery("#external_link_field").hide();
        render_files_for_dataset (dataset_uuid);
    }).fail(function () { console.log (`Failed to add ${url}`); });
}

function add_reference (dataset_uuid) {
    url = jQuery.trim(jQuery("#references").val());
    if (url != "") {
        jQuery.ajax({
            url:         `/v3/datasets/${dataset_uuid}/references`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "references": [{ "url": url }] }),
        }).done(function () {
            render_references_for_dataset (dataset_uuid);
            jQuery("#references").val("");
        }).fail(function () { console.log (`Failed to add ${url}`); });
    }
}

function submit_new_author (dataset_uuid) {
    first_name = jQuery("#author_first_name").val();
    last_name  = jQuery("#author_last_name").val();
    email      = jQuery("#author_email").val();
    orcid      = jQuery("#author_orcid").val();

    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/authors`,
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
        render_authors_for_dataset (dataset_uuid);
    }).fail(function () { console.log (`Failed to add author.`); });
}

function submit_new_funding (dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/funding`,
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
        render_funding_for_dataset (dataset_uuid);
    }).fail(function () { console.log (`Failed to add funding.`); });
}

function new_author (dataset_uuid) {
    let html = `<div id="new-author-form">`;
    html += `<label for="author_first_name">First name</label>`;
    html += `<input type="text" id="author_first_name" name="author_first_name">`;
    html += `<label for="author_last_name">Last name</label>`;
    html += `<input type="text" id="author_last_name" name="author_last_name">`;
    html += `<label for="author_email">E-mail address</label>`;
    html += `<input type="text" id="author_email" name="author_email">`;
    html += `<label for="author_orcid">ORCID</label>`;
    html += `<input type="text" id="author_orcid" name="author_orcid">`;
    html += `<div id="new-author" class="a-button">`;
    html += `<a href="#" onclick="javascript:submit_new_author('${dataset_uuid}'); `;
    html += `return false;">Add author</a></div>`;
    html += `</div>`;
    jQuery("#authors-ac ul").remove();
    jQuery("#new-author").remove();
    jQuery("#authors-ac").append(html);
}

function new_funding (dataset_uuid) {
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
    html += `<a href="#" onclick="javascript:submit_new_funding('${dataset_uuid}'); `;
    html += `return false;">Add funding</a></div>`;
    html += `</div>`;
    jQuery("#funding-ac ul").remove();
    jQuery("#new-funding").remove();
    jQuery("#funding-ac").append(html);
}

function autocomplete_author (event, dataset_uuid) {
    current_text = jQuery.trim(jQuery("#authors").val());
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
                html += `'${dataset_uuid}'); return false;">${item["full_name"]}`;
                if (item["orcid_id"] != null && item["orcid_id"] != "") {
                    html += ` (${item["orcid_id"]})`;
                }
                html += "</a>";
            }
            html += "</ul>";

            html += `<div id="new-author" class="a-button"><a href="#" `
            html += `onclick="javascript:new_author('${dataset_uuid}'); `
            html += `return false;">Create new author record</a></div>`;
            jQuery("#authors")
                .addClass("input-for-ac")
                .after(`<div id="authors-ac" class="autocomplete">${html}</div>`);
        });
    }
}

function autocomplete_funding (event, dataset_uuid) {
    current_text = jQuery.trim(jQuery("#funding").val());
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
            html = "<ul>";
            for (item of data) {
                html += `<li><a href="#" `;
                html += `onclick="javascript:add_funding('${item["uuid"]}', `;
                html += `'${dataset_uuid}'); return false;">${item["title"]}</a>`;
            }
            html += "</ul>";

            html += `<div id="new-funding" class="a-button"><a href="#" `
            html += `onclick="javascript:new_funding('${dataset_uuid}'); `
            html += `return false;">Create funding record</a></div>`;
            jQuery("#funding")
                .addClass("input-for-ac")
                .after(`<div id="funding-ac" class="autocomplete">${html}</div>`);
        });
    }
}

function toggle_record_type (dataset_uuid) {
    if (jQuery("#metadata_record_only").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#metadata_reason_field").show();
    } else if (jQuery("#external_link").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#external_link_field").show();
        jQuery("#files-wrapper").show();
    } else if (jQuery("#upload_files").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#file_upload_field").show();
        jQuery("#files-wrapper").show();
    } else if (jQuery("#upload_software").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#software_upload_field").show();
        jQuery("#file_upload_field").show();
        jQuery("#files-wrapper").show();
    }
}

function toggle_access_level (dataset_uuid) {
    jQuery(".access_level").hide();
    if (jQuery("#open_access").prop("checked")) {
        jQuery("#open_access_form").show();
    } else if (jQuery("#embargoed_access").prop("checked")) {
        if (jQuery("#embargo_reason.ql-container").length === 0) {
            let quill = new Quill('#embargo_reason', { theme: '4tu' });
        }
        jQuery("#embargoed_access_form").show();
    } else if (jQuery("#restricted_access").prop("checked")) {
        if (jQuery("#restricted_access_reason.ql-container").length === 0) {
            let quill = new Quill('#restricted_access_reason', { theme: '4tu' });
        }
        jQuery("#restricted_access_form").show();
    } else if (jQuery("#closed_access").prop("checked")) {
        if (jQuery("#closed_access_reason.ql-container").length === 0) {
            let quill = new Quill('#closed_access_reason', { theme: '4tu' });
        }
        jQuery("#closed_access_form").show();
    }
}

function activate (dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        render_authors_for_dataset (dataset_uuid);
        render_references_for_dataset (dataset_uuid);
        render_funding_for_dataset (dataset_uuid);
        render_categories_for_dataset (dataset_uuid);
        render_licenses (data);
        jQuery("#authors").on("input", function (event) {
            return autocomplete_author (event, dataset_uuid);
        });
        jQuery("#funding").on("input", function (event) {
            return autocomplete_funding (event, dataset_uuid);
        });
        jQuery("#references").on("keypress", function(e){
            if(e.which == 13){
                add_reference(dataset_uuid);
            }
        });
        render_files_for_dataset (dataset_uuid);
        if (data["defined_type_name"] != null) {
            jQuery(`#type-${data["defined_type_name"]}`).prop("checked", true);
        }
        if (data["group_id"] != null) {
            jQuery(`#group_${data["group_id"]}`).prop("checked", true);
        }
        jQuery(`#article_${dataset_uuid}`).removeClass("loader");
        jQuery(`#article_${dataset_uuid}`).show();
        let quill = new Quill('#description', { theme: '4tu' });
        activate_drag_and_drop (dataset_uuid);

        jQuery("input[name='record_type']").change(function () {
            toggle_record_type (dataset_uuid);
        });

        if (data["is_metadata_record"]) {
            jQuery("#metadata_record_only").prop("checked", true);
        } else if (data["has_linked_file"]) {
            jQuery("#external_link").prop("checked", true);
        } else if (data["defined_type_name"] == "software") {
            jQuery("#upload_software").prop("checked", true);
            render_git_files_for_dataset (dataset_uuid, null);
        } else {
            jQuery("#upload_files").prop("checked", true);
        }

        if (data["is_embargoed"]) {
            let access_type = 0;
            try { access_type = data["embargo_options"][0]["id"]; }
            catch (error) { access_type = 0; }

            if (access_type === 1000) {
                jQuery("#restricted_access").prop("checked", true);
            } else if (access_type === 1001) {
                jQuery("#closed_access").prop("checked", true);
            } else {
                jQuery("#embargoed_access").prop("checked", true);
                if (data["embargo_type"] == "file") {
                    jQuery("#files_only_embargo").prop("checked", true);
                } else if (data["embargo_type"] == "article") {
                    jQuery("#content_embargo").prop("checked", true);
                }
            }
        }

        toggle_record_type (dataset_uuid);
        toggle_access_level (dataset_uuid);

        jQuery("#delete").on("click", function (event) { delete_dataset (dataset_uuid, event); });
        jQuery("#save").on("click", function (event)   { save_dataset (dataset_uuid, event); });
        jQuery("#submit").on("click", function (event) { submit_dataset (dataset_uuid, event); });
        jQuery("#refresh-git-files").on("click", function (event) {
            render_git_files_for_dataset (dataset_uuid, event);
        });
        jQuery("input[name=access_type]").on("change", toggle_access_level);
        jQuery("#configure_embargo").on("click", toggle_embargo_options);
        jQuery("#embargo_until_forever").on("change", toggle_embargo_until);
        jQuery("#cancel_embargo").on("click", toggle_embargo_options);
    }).fail(function () { console.log(`Failed to retrieve article ${dataset_uuid}.`); });
}

function toggle_embargo_options (event) {
    event.preventDefault();
    event.stopPropagation();
    if (jQuery("#embargo_options").is(":hidden")) {
        jQuery("#embargo_options").show();
        jQuery("#configure_embargo").hide();
    } else {
        jQuery("#embargo_options").hide();
        jQuery("#configure_embargo").show();
    }
}

function toggle_embargo_until (event) {
    event.preventDefault();
    event.stopPropagation();

    jQuery("#embargo_until_date")
        .prop("disabled",
              jQuery("#embargo_until_forever").prop("checked"));
}

function perform_upload (files, current_file, dataset_uuid) {
    total_files = files.length;
    let index = current_file - 1;
    let data  = new FormData();
    data.append (`file`, files[index], files[index].name);

    jQuery.ajax({
        xhr: function () {
            let xhr = new window.XMLHttpRequest();
            xhr.upload.addEventListener("progress", function (evt) {
                if (evt.lengthComputable) {
                    let completed = parseInt(evt.loaded / evt.total * 100);
                    jQuery("#file-upload h4").text(`Uploading at ${completed}% (${current_file}/${total_files})`);
                    if (completed === 100) {
                        jQuery("#file-upload h4").text(`Computing MD5 ... (${current_file}/${total_files})`);
                    }
                }
            }, false);
            return xhr;
        },
        url:         `/v3/datasets/${dataset_uuid}/upload`,
        type:        "POST",
        data:        data,
        processData: false,
        contentType: false,
        success: function (data, textStatus, request) {
            jQuery("#file-upload h4").text("Drag files here");
            render_files_for_dataset (dataset_uuid);
            if (current_file < total_files) {
                return perform_upload (files, current_file + 1, total_files, dataset_uuid);
            }
        }
    });
}

function remove_file (file_id, dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files/${file_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (files) {
        render_files_for_dataset (dataset_uuid);
        if (jQuery("#external_link").prop("checked")) {
            jQuery("#external_link_field").show();
        }
    }).fail(function () { console.log (`Failed to remove ${file_id}`); });
}

function remove_author (author_id, dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/authors/${author_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (authors) { render_authors_for_dataset (dataset_uuid); })
      .fail(function () { console.log (`Failed to remove ${author_id}`); });
}

function remove_funding (funding_id, dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/funding/${funding_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (funding) { render_funding_for_dataset (dataset_uuid); })
      .fail(function () { console.log (`Failed to remove ${funding_id}`); });
}

function remove_reference (url, dataset_uuid) {
    let jqxhr = jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/references?url=${url}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (authors) { render_references_for_dataset (dataset_uuid); })
      .fail(function () { console.log (`Failed to remove ${url}`); });
}

function prettify_size (size) {
    let sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (size == 0 || size == null) return '0 Byte';
    let i = parseInt(Math.floor(Math.log(size) / Math.log(1000)));
    return Math.round(size / Math.pow(1000, i), 2) + ' ' + sizes[i];
}

function submit_dataset (dataset_uuid, event) {
    event.preventDefault();
    event.stopPropagation();

    save_dataset (dataset_uuid, event, notify=false);

    let jqxhr = jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/submit-for-review`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        window.location.replace("/my/datasets/submitted-for-review");
    }).fail(function () {
        jQuery("#message")
            .addClass("failure")
            .append("<p>Oops! Submitting for review failed.</p>")
            .fadeIn(250);
        setTimeout(function() {
            jQuery("#message").fadeOut(500, function() {
                jQuery("#message").removeClass("failure").empty();
            });
        }, 5000);
    });
}

function activate_drag_and_drop (dataset_uuid) {
    // Drag and drop handling for the entire window.
    jQuery("html").on("dragover", function (event) {
        event.preventDefault();
        event.stopPropagation();
        jQuery(".upload-container").css("background", "#eeeeee")
        jQuery("#file-upload h4").text("Drag here");
    });
    jQuery("html").on("drop", function (event) {
        event.preventDefault();
        event.stopPropagation();
    });

    // Drag and drop handling for the upload area.
    jQuery('#file-upload').on('dragenter', function (event) {
        event.stopPropagation();
        event.preventDefault();
        jQuery("#file-upload h4").text("Drop here");
    });
    jQuery('#file-upload').on('dragover', function (event) {
        event.stopPropagation();
        event.preventDefault();
        jQuery("#file-upload h4").text("Drop here");
    });
    jQuery('#file-upload').on('dragleave', function (event) {
        jQuery(".upload-container").css("background", "#f9f9f9");
        jQuery("#file-upload h4").text("Drag files here");
    });
    jQuery('#file-upload').on('drop', function (event) {
        event.stopPropagation();
        event.preventDefault();

        jQuery("#file-upload h4").text("Uploading ...");

        let files = event.originalEvent.dataTransfer.files;
        perform_upload (files, 1, dataset_uuid);
    });

    // Open file selector on div click
    jQuery("#file-upload").click(function () {
        jQuery("#file").click();
    });

    // file selected
    jQuery("#file").change(function () {
        let files = jQuery('#file')[0].files;
        perform_upload (files, 1, dataset_uuid);
    });
}
