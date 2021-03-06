function render_in_form (text) { return [text].join(''); }
function or_null (value) { return (value == "" || value == "<p><br></p>") ? null : value; }

function delete_article (article_uuid, event) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm("Deleting this draft article is unrecoverable. "+
                "Do you want to continue?"))
    {
        var jqxhr = jQuery.ajax({
            url:         `/v2/account/articles/${article_uuid}`,
            type:        "DELETE",
        }).done(function () { window.location.pathname = '/my/datasets' })
          .fail(function () { console.log("Failed to retrieve licenses."); });
    }
}

function save_article (article_uuid, event, notify=true) {
    event.preventDefault();
    event.stopPropagation();

    categories   = jQuery("input[name='categories']:checked");
    category_ids = []
    for (category of categories) {
        category_ids.push(jQuery(category).val());
    }

    var defined_type_name = null;
    if (jQuery("#upload_software").prop("checked")) {
        defined_type_name = "software";
    } else {
        defined_type_name = "dataset";
    }

    var group_id = jQuery("input[name='groups']:checked")[0]
    if (group_id !== undefined) { group_id = group_id["value"]; }
    else { group_id = null; }

    var is_embargoed = jQuery("#embargo_options").is(":visible");

    form_data = {
        "title":          or_null(jQuery("#title").val()),
        "description":    or_null(jQuery("#description .ql-editor").html()),
        "license_id":     or_null(jQuery("#license").val()),
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
        "defined_type_name": defined_type_name,
        "is_embargoed":   is_embargoed,
        "group_id":       group_id,
        "categories":     category_ids
    }

    if (is_embargoed) {
        var embargo_indefinitely = jQuery("#embargo_options").prop("checked");
        if (! embargo_indefinitely) {
            form_data["embargo_until_date"] = or_null(jQuery("#embargo_until_date").val());
        }
        form_data["embargo_title"]  = or_null(jQuery("#embargo_title").val());
        form_data["embargo_reason"] = or_null(jQuery("#embargo_reason .ql-editor").html());
        form_data["embargo_allow_access_requests"] = jQuery("#allow_embargo_access_requests").prop("checked");

        if (jQuery("#files_only_embargo").prop("checked")) {
            form_data["embargo_type"] = "file";
        } else if (jQuery("#content_embargo").prop("checked")) {
            form_data["embargo_type"] = "content";
        }
    }

    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}`,
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

function render_licenses (article) {
    chosen_license = null;
    try { chosen_license = article.license.value; }
    catch (TypeError) {}

    var jqxhr = jQuery.ajax({
        url:         "/v2/licenses",
        type:        "GET",
        accept:      "application/json",
    }).done(function (licenses) {
        for (license of licenses) {
            selected = "";
            selected = ((chosen_license == license.value) ? " selected" : "");
            html = `<option value="${license.value}"${selected}>${license.name}</option>`;
            jQuery("#license").append(html);
        }
    }).fail(function () {
        console.log("Failed to retrieve licenses.");
    });
}

function render_categories_for_article (article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/categories`,
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

function render_references_for_article (article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v3/articles/${article_uuid}/references`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (references) {
        jQuery("#references-list tbody").empty();
        for (url of references) {
            row = `<tr><td><a target="_blank" href="${encodeURIComponent(url)}">`;
            row += `${url}</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_reference('${encodeURIComponent(url)}', `;
            row += `'${article_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#references-list tbody").append(row);
        }
        jQuery("#references-list").show();
    }).fail(function () {
        console.log("Failed to retrieve reference details.");
    });
}

function render_authors_for_article (article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/authors`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (authors) {
        jQuery("#authors-list tbody").empty();
        for (author of authors) {
            row = `<tr><td><a href="#">${author.full_name}`;
            if (author.orcid_id != null && author.orcid_id != "") {
                row += ` (${author.orcid_id})`;
            }
            row += `</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_author('${author.uuid}', `;
            row += `'${article_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }).fail(function () {
        console.log("Failed to retrieve author details.");
    });
}

function render_git_files_for_article (article_uuid, event) {
    if (event !== null) {
        event.preventDefault();
        event.stopPropagation();
    }
    var jqxhr = jQuery.ajax({
        url:         `/v3/articles/${article_uuid}.git/files`,
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
function render_files_for_article (article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/files`,
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
                html += ` '${article_uuid}'); return false;" class="fas fa-trash-can" `;
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

function add_author (author_uuid, article_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/authors`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "authors": [{ "uuid": author_uuid }] }),
    }).done(function () {
        render_authors_for_article (article_uuid);
        jQuery("#authors").val("");
        autocomplete_author(null, article_uuid);
    }).fail(function () { console.log (`Failed to add ${author_uuid}`); });
}

function submit_external_link (article_uuid) {
    var url = jQuery("#external_url").val();
    if (url == "") {
        jQuery("#external_url").css("background", "#cc0000");
        return false;
    }
    jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/files`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "link": url }),
    }).done(function () {
        jQuery("#external_url").val("");
        jQuery("#external_link_field").hide();
        render_files_for_article (article_uuid);
    }).fail(function () { console.log (`Failed to add ${url}`); });
}

function add_reference (article_uuid) {
    url = jQuery.trim(jQuery("#references").val());
    if (url != "") {
        jQuery.ajax({
            url:         `/v3/articles/${article_uuid}/references`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "references": [{ "url": url }] }),
        }).done(function () {
            render_references_for_article (article_uuid);
            jQuery("#references").val("");
        }).fail(function () { console.log (`Failed to add ${url}`); });
    }
}

function submit_new_author (article_uuid) {
    first_name = jQuery("#author_first_name").val();
    last_name  = jQuery("#author_last_name").val();
    email      = jQuery("#author_email").val();
    orcid      = jQuery("#author_orcid").val();

    jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/authors`,
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
        render_authors_for_article (article_uuid);
    }).fail(function () { console.log (`Failed to add author.`); });
}

function new_author (article_uuid) {
    var html = `<div id="new-author-form">`;
    html += `<label for="author_first_name">First name</label>`;
    html += `<input type="text" id="author_first_name" name="author_first_name">`;
    html += `<label for="author_first_name">Last name</label>`;
    html += `<input type="text" id="author_last_name" name="author_last_name">`;
    html += `<label for="author_first_name">E-mail address</label>`;
    html += `<input type="text" id="author_email" name="author_email">`;
    html += `<label for="author_first_name">ORCID</label>`;
    html += `<input type="text" id="author_orcid" name="author_orcid">`;
    html += `<div id="new-author" class="a-button">`;
    html += `<a href="#" onclick="javascript:submit_new_author('${article_uuid}'); `;
    html += `return false;">Add author</a></div>`;
    html += `</div>`;
    jQuery("#authors-ac ul").remove();
    jQuery("#new-author").remove();
    jQuery("#authors-ac").append(html);
}

function autocomplete_author (event, article_uuid) {
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
                html += `'${article_uuid}'); return false;">${item["full_name"]}`;
                if (item["orcid_id"] != null && item["orcid_id"] != "") {
                    html += ` (${item["orcid_id"]})`;
                }
                html += "</a>";
            }
            html += "</ul>";

            html += `<div id="new-author" class="a-button"><a href="#" `
            html += `onclick="javascript:new_author('${article_uuid}'); `
            html += `return false;">Create new author record</a></div>`;
            jQuery("#authors")
                .addClass("input-for-ac")
                .after(`<div id="authors-ac" class="autocomplete">${html}</div>`);
        });
    }
}

function toggle_record_type (article_uuid) {
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

function activate (article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        render_authors_for_article (article_uuid);
        render_references_for_article (article_uuid);
        render_categories_for_article (article_uuid);
        render_licenses (data);
        jQuery("#authors").on("input", function (event) {
            return autocomplete_author (event, article_uuid);
        });
        jQuery("#references").on("keypress", function(e){
            if(e.which == 13){
                add_reference(article_uuid);
            }
        });
        render_files_for_article (article_uuid);
        if (data["defined_type_name"] != null) {
            jQuery(`#type-${data["defined_type_name"]}`).prop("checked", true);
        }
        if (data["group_id"] != null) {
            jQuery(`#group_${data["group_id"]}`).prop("checked", true);
        }
        jQuery(`#article_${article_uuid}`).removeClass("loader");
        jQuery(`#article_${article_uuid}`).show();
        var quill1 = new Quill('#embargo_reason', { theme: '4tu' });
        var quill2 = new Quill('#description', { theme: '4tu' });
        activate_drag_and_drop (article_uuid);

        jQuery("input[name='record_type']").change(function () {
            toggle_record_type (article_uuid);
        });

        if (data["is_metadata_record"]) {
            jQuery("#metadata_record_only").prop("checked", true);
        } else if (data["has_linked_file"]) {
            jQuery("#external_link").prop("checked", true);
        } else if (data["defined_type_name"] == "software") {
            jQuery("#upload_software").prop("checked", true);
            render_git_files_for_article (article_uuid, null);
        } else {
            jQuery("#upload_files").prop("checked", true);
        }

        toggle_record_type (article_uuid);

        jQuery("#delete").on("click", function (event) { delete_article (article_uuid, event); });
        jQuery("#save").on("click", function (event)   { save_article (article_uuid, event); });
        jQuery("#submit").on("click", function (event) { submit_article (article_uuid, event); });
        jQuery("#refresh-git-files").on("click", function (event) {
            render_git_files_for_article (article_uuid, event);
        });
        jQuery("#configure_embargo").on("click", toggle_embargo_options);
        jQuery("#embargo_until_forever").on("change", toggle_embargo_until);
        jQuery("#cancel_embargo").on("click", toggle_embargo_options);
    }).fail(function () { console.log(`Failed to retrieve article ${article_uuid}.`); });
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

function perform_upload (files, current_file, article_uuid) {
    total_files = files.length;
    var index = current_file - 1;
    var data  = new FormData();
    data.append (`file`, files[index], files[index].name);

    jQuery.ajax({
        xhr: function () {
            var xhr = new window.XMLHttpRequest();
            xhr.upload.addEventListener("progress", function (evt) {
                if (evt.lengthComputable) {
                    var completed = parseInt(evt.loaded / evt.total * 100);
                    jQuery("#file-upload h4").text(`Uploading at ${completed}% (${current_file}/${total_files})`);
                    if (completed === 100) {
                        jQuery("#file-upload h4").text(`Computing MD5 ... (${current_file}/${total_files})`);
                    }
                }
            }, false);
            return xhr;
        },
        url:         `/v3/articles/${article_uuid}/upload`,
        type:        "POST",
        data:        data,
        processData: false,
        contentType: false,
        success: function (data, textStatus, request) {
            jQuery("#file-upload h4").text("Drag files here");
            render_files_for_article (article_uuid);
            if (current_file < total_files) {
                return perform_upload (files, current_file + 1, total_files, article_uuid);
            }
        }
    });
}

function remove_file (file_id, article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/files/${file_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (files) {
        render_files_for_article (article_uuid);
        if (jQuery("#external_link").prop("checked")) {
            jQuery("#external_link_field").show();
        }
    }).fail(function () { console.log (`Failed to remove ${file_id}`); });
}

function remove_author (author_id, article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_uuid}/authors/${author_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (authors) { render_authors_for_article (article_uuid); })
      .fail(function () { console.log (`Failed to remove ${author_id}`); });
}

function remove_reference (url, article_uuid) {
    var jqxhr = jQuery.ajax({
        url:         `/v3/articles/${article_uuid}/references?url=${url}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (authors) { render_references_for_article (article_uuid); })
      .fail(function () { console.log (`Failed to remove ${url}`); });
}

function prettify_size (size) {
    var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (size == 0 || size == null) return '0 Byte';
    var i = parseInt(Math.floor(Math.log(size) / Math.log(1000)));
    return Math.round(size / Math.pow(1000, i), 2) + ' ' + sizes[i];
}

function submit_article (article_uuid, event) {
    event.preventDefault();
    event.stopPropagation();

    save_article (article_uuid, event, notify=false);

    var jqxhr = jQuery.ajax({
        url:         `/v3/articles/${article_uuid}/submit-for-review`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        window.location.replace("/my/datasets");
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

function activate_drag_and_drop (article_uuid) {
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

        var files = event.originalEvent.dataTransfer.files;
        perform_upload (files, 1, article_uuid);
    });

    // Open file selector on div click
    jQuery("#file-upload").click(function () {
        jQuery("#file").click();
    });

    // file selected
    jQuery("#file").change(function () {
        var files = jQuery('#file')[0].files;
        perform_upload (files, 1, article_uuid);
    });
}
