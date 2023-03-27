function delete_dataset (dataset_uuid, event) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm("Deleting this draft dataset is unrecoverable. "+
                "Do you want to continue?"))
    {
        jQuery.ajax({
            url:         `/v2/account/articles/${dataset_uuid}`,
            type:        "DELETE",
        }).done(function () { window.location.pathname = '/my/datasets' })
          .fail(function () { show_message ("failure", "<p>Failed to remove dataset.</p>"); });
    }
}

function decline_dataset (dataset_uuid, event) {
    event.preventDefault();
    event.stopPropagation();

    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css('opacity', '0.15');
    save_dataset (dataset_uuid, event, false, function() {
        jQuery.ajax({
            url:         `/v3/datasets/${dataset_uuid}/decline`,
            type:        "POST",
            accept:      "application/json",
        }).done(function () {
            window.location.replace("/logout");
        }).fail(function (response, text_status, error_code) {
            show_message ("failure",
                          `<p>Could not decline due to error ` +
                          `<code>${error_code}</code>.</p>`);
            jQuery("#content-wrapper").css('opacity', '1.0');
            jQuery("#content").removeClass("loader-top");
        });
    });
}

function preview_dataset (dataset_uuid, event) {
    event.preventDefault();
    event.stopPropagation();
    let current_date = new Date();
    let year  = current_date.getFullYear();
    let month = current_date.getMonth();
    let day   = current_date.getDate() + 1;
    if (month < 10) { month = `0${month}`; }
    if (day < 10) { day = `0${day}`; }

    save_dataset (dataset_uuid, event, false, function() {
        jQuery.ajax({
            url:         `/v2/account/articles/${dataset_uuid}/private_links`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "expires_date": `${year}-${month}-${day}` }),
        }).done(function (data) {
            let preview_window = window.open(data["location"], '_blank');
            if (preview_window) { preview_window.focus(); }
            else {
                show_message ("failure",
                              "<p>Cannot open preview window because your " +
                              "browser disabled pop-ups.</p>");
            }
        }).fail(function (response, text_status, error_code) {
            show_message ("failure",
                          `<p>Could not create a private link due to error ` +
                          `<code>${error_code}</code>.</p>`);
        });
    });
}

function gather_form_data () {
    let categories   = jQuery("input[name='categories']:checked");
    let category_ids = []
    for (let category of categories) {
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
    let agreed_to_da  = jQuery("#deposit_agreement").prop("checked");
    let agreed_to_publish = jQuery("#publish_agreement").prop("checked");
    let is_metadata_record = jQuery("#metadata_record_only").prop("checked");

    let form_data = {
        "title":          or_null(jQuery("#title").val()),
        "description":    or_null(jQuery("#description .ql-editor").html()),
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
        "is_metadata_record": is_metadata_record,
        "metadata_reason": or_null(jQuery("#metadata_only_reason").val()),
        "defined_type":   defined_type_name,
        "is_embargoed":   is_embargoed || is_restricted,
        "group_id":       group_id,
        "agreed_to_deposit_agreement": agreed_to_da,
        "agreed_to_publish": agreed_to_publish,
        "categories":     category_ids
    }

    if (is_embargoed) {
        form_data["embargo_until_date"] = or_null(jQuery("#embargo_until_date").val());
        form_data["embargo_title"]  = "Under embargo";
        form_data["embargo_reason"] = or_null(jQuery("#embargo_reason .ql-editor").html());
        form_data["license_id"]     = or_null(jQuery("#license_embargoed").val());
        if (jQuery("#files_only_embargo").prop("checked")) {
            form_data["embargo_type"] = "file";
        } else if (jQuery("#content_embargo").prop("checked")) {
            form_data["embargo_type"] = "article";
        }
    } else if (is_restricted) {
        // 149 is the licence ID of the "Restricted Licence".
        form_data["license_id"]     = 149;
        form_data["embargo_until_date"] = null;
        form_data["embargo_title"]  = "Restricted access";
        form_data["embargo_reason"] = or_null(jQuery("#restricted_access_reason .ql-editor").html());
        form_data["eula"]           = or_null(jQuery("#restricted_access_eula .ql-editor").html());
        form_data["embargo_options"] = [{ "id": 1000, "type": "restricted_access" }]
    } else {
        form_data["license_id"]     = or_null(jQuery("#license_open").val());
    }

    return form_data;
}

function save_dataset (dataset_uuid, event, notify=true, on_success=jQuery.noop) {
    event.preventDefault();
    event.stopPropagation();

    form_data = gather_form_data();
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}`,
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
            show_message ("failure", "<p>Failed to save draft. Please try again at a later time.</p>");
        }
    });
}

function reserve_doi (dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/reserve_doi`,
        type:        "POST",
        accept:      "application/json",
    }).done(function (record) {
        jQuery("#doi-wrapper p").replaceWith(
            `<p>The DOI of your dataset will be: <strong>${record["doi"]}</strong></p>`
        );
    }).fail(function () {
        show_message ("failure", "<p>Failed to reserve DOI. Please try again later.</p>")
    });
}

function render_licenses (dataset) {
    let chosen_license = null;
    // When the dataset hasn't been given a license yet, accessing
    // license.value will throw a TypeError. This is expected.
    try { chosen_license = dataset.license.value; }
    catch (TypeError) {}

    jQuery.ajax({
        url:         "/v2/licenses",
        type:        "GET",
        accept:      "application/json",
    }).done(function (licenses) {
        for (let license of licenses) {
            // Skip legacy licenses; render them last.
            if (license.type == "legacy") { continue; }
            let selected = ((chosen_license == license.value) ? " selected" : "");
            let html = `<option value="${license.value}"${selected}>${license.name}</option>`;
            jQuery(".license-selector").append(html);
        }
        // Render legacy licenses last.
        for (let license of licenses) {
            if (license.type != "legacy") { continue; }
            let selected = ((chosen_license == license.value) ? " selected" : "");
            let html = `<option value="${license.value}"${selected}>${license.name}</option>`;
            jQuery(".license-selector").append(html);
        }
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve license list.</p>")
    });
}

function render_categories_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/categories`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (categories) {
        for (let category of categories) {
            jQuery(`#category_${category["uuid"]}`).prop("checked", true);
            jQuery(`#category_${category["parent_uuid"]}`).prop("checked", true);
            jQuery(`#subcategories_${category["parent_uuid"]}`).show();
        }
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve categories.</p>")
    });
}

function render_references_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/references`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (references) {
        jQuery("#references-list tbody").empty();
        for (let url of references) {
            let row = `<tr><td><a target="_blank" href="${encodeURIComponent(url)}">`;
            row += `${url}</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_reference('${encodeURIComponent(url)}', `;
            row += `'${dataset_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#references-list tbody").append(row);
        }
        jQuery("#references-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve references.</p>");
    });
}

function render_tags_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/tags`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (tags) {
        jQuery("#tags-list").empty();
        for (let tag of tags) {
            let row = `<li>${tag} &nbsp; <a href="#" class="fas fa-trash-can"`;
            row += ` onclick="javascript:remove_tag('${encodeURIComponent(tag)}', `;
            row += `'${dataset_uuid}'); return false;"></a></li>`;
            jQuery("#tags-list").append(row);
        }
        jQuery("#tags-list").show();
    }).fail(function () { show_message ("failure", "<p>Failed to retrieve tags.</p>"); });
}

function render_authors_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/authors`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (authors) {
        jQuery("#authors-list tbody").empty();
        for (let author of authors) {
            let row = `<tr><td>${author.full_name}`;
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
        show_message ("failure", "<p>Failed to retrieve author details.</p>");
    });
}

function render_funding_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/funding`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (funders) {
        jQuery("#funding-list tbody").empty();
        for (let funding of funders) {
            let row = `<tr><td>${funding.title}</td>`;
            row += `<td><a href="#" `;
            row += `onclick="javascript:remove_funding('${funding.uuid}', `;
            row += `'${dataset_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#funding-list tbody").append(row);
        }
        jQuery("#funding-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve funding details.</p>");
    });
}

function render_git_files_for_dataset (dataset_uuid, event) {
    if (event !== null) {
        event.preventDefault();
        event.stopPropagation();
    }
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}.git/files`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (files) {
        jQuery("#git-files").empty();
        for (let index in files) {
            jQuery("#git-files").append(`<li>${files[index]}</li>`);
        }
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve Git file details.</p>");
    });
}
function render_files_for_dataset (dataset_uuid, fileUploader) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (files) {
        if (fileUploader !== null) {
            fileUploader.removeAllFiles();
        }
        jQuery("#files tbody").empty();
        if (files.length > 0) {
            jQuery("input[name='record_type']").attr('disabled', true);

            for (let index in files) {
                let file = files[index];
                if (file.name === null) {
                    file.name = file.download_url;
                }
                let html = `<tr><td><a href="/file/${dataset_uuid}/${file.uuid}">${file.name}</a> (${prettify_size(file.size)})</td>`;
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
        show_message ("failure", "<p>Failed to retrieve file details.</p>");
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
    }).fail(function () { show_message ("failure", `<p>Failed to add ${author_uuid}.</p>`); });
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
    }).fail(function () { show_message ("failure", `<p>Failed to add ${funding_uuid}.</p>`); });
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
        render_files_for_dataset (dataset_uuid, null);
    }).fail(function () { show_message ("failure", `<p>Failed to add ${url}.</p>`); });
}

function add_reference (dataset_uuid) {
    let url = jQuery.trim(jQuery("#references").val());
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
        }).fail(function () { show_message ("failure", `<p>Failed to add ${url}.</p>`); });
    }
}

function add_tag (dataset_uuid) {
    let tag = jQuery.trim(jQuery("#tag").val());
    if (tag == "") { return 0; }

    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/tags`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "tags": [tag] }),
    }).done(function () {
        render_tags_for_dataset (dataset_uuid);
        jQuery("#tag").val("");
    }).fail(function () { show_message ("failure", `<p>Failed to add ${tag}.</p>`); });
}

function submit_new_author (dataset_uuid) {
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
        url:         `/v2/account/articles/${dataset_uuid}/authors`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({
            "authors": authors
        }),
    }).done(function () {
        jQuery("#authors-ac").remove();
        jQuery("#authors").removeClass("input-for-ac");
        render_authors_for_dataset (dataset_uuid);
    }).fail(function () { show_message ("failure", `<p>Failed to add author.</p>`); });
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
    }).fail(function () { show_message ("failure", `<p>Failed to add funding.</p>`); });
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

function toggle_record_type () {
    if (jQuery("#external_link").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#external_link_field").show();
        jQuery("#files-wrapper").show();
    } else if (jQuery("#metadata_record_only").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#metadata_reason_field").show();
    } else if (jQuery("#upload_files").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#file_upload_field").show();
        jQuery("#files-wrapper").show();
    } else if (jQuery("#upload_software").prop("checked")) {
        jQuery(".record-type-field").hide();
        jQuery("#software_upload_field").show();
        jQuery("#file_upload_field").show();
        jQuery("#files-wrapper").show();
    } else {
        jQuery("#upload_files").prop("checked", true);
    }
}

function toggle_access_level () {
    jQuery(".access_level").hide();
    if (jQuery("#open_access").prop("checked")) {
        jQuery("#open_access_form").show();
    } else if (jQuery("#embargoed_access").prop("checked")) {
        if (jQuery("#embargo_reason.ql-container").length === 0) {
            new Quill('#embargo_reason', { theme: '4tu' });
        }
        jQuery("#embargoed_access_form").show();
    } else if (jQuery("#restricted_access").prop("checked")) {
        if (jQuery("#restricted_access_reason.ql-container").length === 0) {
            new Quill('#restricted_access_reason', { theme: '4tu' });
            new Quill('#restricted_access_eula', { theme: '4tu' });
        }
        jQuery("#restricted_access_form").show();
    }
}

function activate (dataset_uuid) {
    var submenu_offset = jQuery("#submenu").offset().top;

    install_sticky_header();
    install_touchable_help_icons();

    jQuery(".article-content").hide();
    jQuery(".article-content-loader").show();
    jQuery(".article-content-loader").addClass("loader");
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        render_authors_for_dataset (dataset_uuid);
        render_references_for_dataset (dataset_uuid);
        render_tags_for_dataset (dataset_uuid);
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
        jQuery("#add-keyword-button").on("click", function(event) {
            event.preventDefault();
            event.stopPropagation();
            add_tag (dataset_uuid);
        });
        jQuery("#tag").on("keypress", function(e){
            if(e.which == 13){
                add_tag(dataset_uuid);
            }
        });
        render_files_for_dataset (dataset_uuid, null);
        if (data["defined_type_name"] != null) {
            jQuery(`#type-${data["defined_type_name"]}`).prop("checked", true);
        }
        if (data["group_id"] != null) {
            jQuery(`#group_${data["group_id"]}`).prop("checked", true);
        }
        jQuery(`#article_${dataset_uuid}`).removeClass("loader");
        jQuery(`#article_${dataset_uuid}`).show();
        new Quill('#description', { theme: '4tu' });

        var fileUploader = new Dropzone("#dropzone-field", {
            url:               `/v3/datasets/${dataset_uuid}/upload`,
            paramName:         "file",
            maxFilesize:       1000000,
            maxFiles:          1000000,
            parallelUploads:   1000000,
            ignoreHiddenFiles: false,
            disablePreviews:   false,
            init: function() {},
            accept: function(file, done) {
                done();
                render_files_for_dataset (dataset_uuid, fileUploader);
            }
        });

        fileUploader.on("complete", function(file) {
            render_files_for_dataset (dataset_uuid, fileUploader);
            fileUploader.removeFile(file);
        });

        jQuery("input[name='record_type']").change(function () {
            toggle_record_type ();
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
            } else {
                jQuery("#embargoed_access").prop("checked", true);
                if (data["embargo_type"] == "file") {
                    jQuery("#files_only_embargo").prop("checked", true);
                } else if (data["embargo_type"] == "article") {
                    jQuery("#content_embargo").prop("checked", true);
                }
            }
        }

        if (data["doi"]) {
            jQuery("#doi-wrapper p").replaceWith(
                `<p>The DOI of your dataset will be: <strong>${data["doi"]}</strong></p>`
            );
        }
        if (data["agreed_to_deposit_agreement"]) {
            jQuery("#deposit_agreement").prop("checked", true);
        }
        if (data["agreed_to_publish"]) {
            jQuery("#publish_agreement").prop("checked", true);
        }

        toggle_record_type ();
        toggle_access_level ();

        jQuery("#delete").on("click", function (event) { delete_dataset (dataset_uuid, event); });
        jQuery("#save").on("click", function (event)   { save_dataset (dataset_uuid, event); });
        jQuery("#submit").on("click", function (event) { submit_dataset (dataset_uuid, event); });
        jQuery("#publish").on("click", function (event) { publish_dataset (dataset_uuid, event); });
        jQuery("#decline").on("click", function (event) { decline_dataset (dataset_uuid, event); });
        jQuery("#preview").on("click", function (event) { preview_dataset (dataset_uuid, event); });
        jQuery("#refresh-git-files").on("click", function (event) {
            render_git_files_for_dataset (dataset_uuid, event);
        });
        jQuery("input[name=access_type]").on("change", toggle_access_level);
        jQuery("#configure_embargo").on("click", toggle_embargo_options);
        jQuery("#embargo_until_forever").on("change", toggle_embargo_until);
        jQuery("#cancel_embargo").on("click", toggle_embargo_options);

        jQuery(".article-content-loader").hide();
        jQuery(".article-content").fadeIn(200);
    }).fail(function () { show_message ("failure", `<p>Failed to retrieve article ${dataset_uuid}.</p>`); });
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
    let total_files = files.length;
    let index = current_file - 1;
    let data  = new FormData();

    if (files[index] === undefined || files[index] == null) {
        show_message ("failure", "<p>Uploading file(s) failed due to a web browser incompatibility.</p>");
        jQuery("#file-upload h4").text("Uploading failed.");
        return;
    } else if (files[index].webkitRelativePath !== undefined &&
               files[index].webkitRelativePath != "") {
        data.append ("file", files[index], files[index].webkitRelativePath);
    } else if (files[index].name !== undefined) {
        data.append ("file", files[index], files[index].name);
    } else {
        jQuery("#file-upload h4").text("Click here to open file dialog");
        jQuery("#file-upload p").text("Because the drag and drop functionality"+
                                      " does not work for your web browser.");
        show_message ("failure", "<p>Uploading file(s). Please try selecting " +
                                 "files with the file chooser instead of " +
                                 "using the drag-and-drop.</p>");
        return;
    }

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
        contentType: false
    }).done(function () {
        jQuery("#file-upload h4").text("Drag files here");
        render_files_for_dataset (dataset_uuid, null);
        if (current_file < total_files) {
            return perform_upload (files, current_file + 1, dataset_uuid);
        }
    }).fail(function () {
        show_message ("failure", "<p>Uploading file(s) failed.</p>");
    });
}

function remove_file (file_id, dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files/${file_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () {
        render_files_for_dataset (dataset_uuid, null);
        if (jQuery("#external_link").prop("checked")) {
            jQuery("#external_link_field").show();
        }
    }).fail(function () { show_message ("failure", `<p>Failed to remove ${file_id}.</p>`); });
}

function remove_author (author_id, dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/authors/${author_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_authors_for_dataset (dataset_uuid); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${author_id}</p>`); });
}

function remove_funding (funding_id, dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/funding/${funding_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_funding_for_dataset (dataset_uuid); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${funding_id}.</p>`); });
}

function remove_reference (url, dataset_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/references?url=${url}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_references_for_dataset (dataset_uuid); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${url}</p>`); });
}

function remove_tag (tag, dataset_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/tags?tag=${tag}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_tags_for_dataset (dataset_uuid); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${tag}.</p>`); });
}

function prettify_size (size) {
    let sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (size == 0 || size == null) return '0 Byte';
    let i = parseInt(Math.floor(Math.log(size) / Math.log(1000)));
    return Math.round(size / Math.pow(1000, i)) + ' ' + sizes[i];
}

function submit_dataset (dataset_uuid, event) {
    event.preventDefault();
    event.stopPropagation();

    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css('opacity', '0.15');
    save_dataset (dataset_uuid, event, false, function() {
        form_data = gather_form_data();
        jQuery.ajax({
            url:         `/v3/datasets/${dataset_uuid}/submit-for-review`,
            type:        "PUT",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify(form_data),
        }).done(function () {
            window.location.replace("/my/datasets/submitted-for-review");
        }).fail(function (response) {
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
                    } else if (message.field_name == "agreed_to_deposit_agreement") {
                        jQuery("label[for='deposit_agreement']").addClass("missing-required");
                    } else if (message.field_name == "agreed_to_publish") {
                        jQuery("label[for='publish_agreement']").addClass("missing-required");
                    } else if (message.field_name == "embargo_type") {
                        jQuery("#record-type-wrapper").addClass("missing-required");
                    } else if (message.field_name == "files") {
                        show_message ("failure", `<p>${message.message}</p>`);
                        jQuery("#dropzone-field").addClass("missing-required");
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

function publish_dataset (dataset_uuid, event) {
    event.preventDefault();
    event.stopPropagation();

    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css('opacity', '0.15');
    save_dataset (dataset_uuid, event, false, function() {
        jQuery.ajax({
            url:         `/v3/datasets/${dataset_uuid}/publish`,
            type:        "POST",
            accept:      "application/json",
        }).done(function () {
            window.location.replace("/logout");
        }).fail(function (response, text_status, error_code) {
            show_message ("failure",
                          `<p>Could not publish due to error ` +
                          `<code>${error_code}</code>.</p>`);
            jQuery("#content-wrapper").css('opacity', '1.0');
            jQuery("#content").removeClass("loader-top");
        });
    });
}
