var current_article_id = null;

function render_in_form (text) { return [text].join(''); }
function or_null (value) { return (value == "" || value == "<p><br></p>") ? null : value; }

function delete_article (article_id) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm("Deleting this draft article is unrecoverable. "+
                "Do you want to continue?"))
    {
        var jqxhr = jQuery.ajax({
            url:         `/v2/account/articles/${article_id}`,
            type:        "DELETE",
        }).done(function () { window.location.pathname = '/my/datasets' })
          .fail(function () { console.log("Failed to retrieve licenses."); });
    }
}

function save_article (article_id) {
    event.preventDefault();
    event.stopPropagation();

    categories   = jQuery("input[name='categories']:checked");
    category_ids = []
    for (category of categories) {
        category_ids.push(jQuery(category).val());
    }

    var defined_type_name = jQuery("input[name='type']:checked")[0]
    if (defined_type_name !== undefined) { defined_type_name = defined_type_name["value"]; }
    else { defined_type_name = null; }

    var group_id = jQuery("input[name='groups']:checked")[0]
    if (group_id !== undefined) { group_id = group_id["value"]; }
    else { group_id = null; }

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
        "group_id":       group_id,
        "categories":     category_ids
    }
    
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_id}`,
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
    })
      .fail(function () { console.log("Failed to save form."); });
}

function render_licenses (article) {
    chosen_license = article.license.value;
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

function render_categories_for_article (article_id) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/categories`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (categories) {
        for (category of categories) {
            jQuery(`#category_${category["id"]}`).prop("checked", true);
            jQuery(`#subcategories_${category["parent_id"]}`).show();
        }
        for (category_id of root_categories) {
            if (jQuery(`#category_${category_id}`).prop("checked")) {
                jQuery(`#subcategories_${category_id}`).show();
            }
        }
    }).fail(function () {
        console.log("Failed to retrieve article categories.");
    });
}

function render_references_for_article (article_id) {
    var jqxhr = jQuery.ajax({
        url:         `/v3/articles/${article_id}/references`,
        data:        { "limit": 10000, "order": "asc", "order_direction": "id" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (references) {
        jQuery("#references-list tbody").empty();
        for (url of references) {
            row = `<tr><td><a target="_blank" href="${encodeURI(url)}">`;
            row += `${url}</a></td><td><a href="#" `;
            row += `onclick="javascript:remove_reference('${encodeURI(url)}', `;
            row += `${article_id}); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#references-list tbody").append(row);
        }
        jQuery("#references-list").show();
    }).fail(function () {
        console.log("Failed to retrieve reference details.");
    });
}

function render_authors_for_article (article_id) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/authors`,
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
            row += `onclick="javascript:remove_author(${author.id}, `;
            row += `${article_id}); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }).fail(function () {
        console.log("Failed to retrieve author details.");
    });
}

function render_files_for_article (article_id) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/files`,
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
                html += `<td><a href="#" onclick="javascript:remove_file(${file.id},`;
                html += ` ${article_id}); return false;" class="fas fa-trash-can" `;
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

function add_author (author_id, article_id) {
    jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/authors`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "authors": [{ "id": author_id }] }),
    }).done(function () {
        render_authors_for_article (article_id);
        jQuery("#authors").val("");
        autocomplete_author(null, article_id);
    }).fail(function () { console.log (`Failed to add ${author_id}`); });
}

function submit_external_link (article_id) {
    var url = jQuery("#external_url").val();
    if (url == "") {
        jQuery("#external_url").css("background", "#cc0000");
        return false;
    }
    jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/files`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "link": url }),
    }).done(function () {
        jQuery("#external_url").val("");
        jQuery("#external_link_field").hide();
        render_files_for_article (article_id);
    }).fail(function () { console.log (`Failed to add ${url}`); });
}

function add_reference (article_id) {
    url = jQuery.trim(jQuery("#references").val());
    if (url != "") {
        jQuery.ajax({
            url:         `/v3/articles/${article_id}/references`,
            type:        "POST",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify({ "references": [{ "url": url }] }),
        }).done(function () {
            render_references_for_article (article_id);
            jQuery("#references").val("");
        }).fail(function () { console.log (`Failed to add ${url}`); });
    }
}

function submit_new_author (article_id) {
    first_name = jQuery("#author_first_name").val();
    last_name  = jQuery("#author_last_name").val();
    email      = jQuery("#author_email").val();
    orcid      = jQuery("#author_orcid").val();

    jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/authors`,
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
        render_authors_for_article (article_id);
    }).fail(function () { console.log (`Failed to add author.`); });
}

function new_author (article_id) {
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
    html += `<a href="#" onclick="javascript:submit_new_author(${article_id}); `;
    html += `return false;">Add author</a></div>`;
    html += `</div>`;
    jQuery("#authors-ac ul").remove();
    jQuery("#new-author").remove();
    jQuery("#authors-ac").append(html);
}

function autocomplete_author (event, article_id) {
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
                html += `onclick="javascript:add_author(${item["id"]}, `;
                html += `${article_id}); return false;">${item["full_name"]}`;
                if (item["orcid_id"] != null && item["orcid_id"] != "") {
                    html += ` (${item["orcid_id"]})`;
                }
                html += "</a>";
            }
            html += "</ul>";

            html += `<div id="new-author" class="a-button"><a href="#" `
            html += `onclick="javascript:new_author(${article_id}); `
            html += `return false;">Create new author record</a></div>`;
            jQuery("#authors")
                .addClass("input-for-ac")
                .after(`<div id="authors-ac" class="autocomplete">${html}</div>`);
        });
    }
}

function toggle_record_type (article_id) {
    if (jQuery("#metadata_record_only").prop("checked")) {
        jQuery("#metadata_reason_field").show();
        jQuery("#external_link_field").hide();
        jQuery("#file_upload_field").hide();
    } else if (jQuery("#external_link").prop("checked")) {
        jQuery("#metadata_reason_field").hide();
        jQuery("#external_link_field").show();
        jQuery("#file_upload_field").hide();
    } else if (jQuery("#upload_files").prop("checked")) {
        jQuery("#metadata_reason_field").hide();
        jQuery("#external_link_field").hide();
        jQuery("#file_upload_field").show();
    }
}

function activate (article_id) {
    current_article_id = article_id;
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${current_article_id}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        render_authors_for_article (article_id);
        render_references_for_article (article_id);
        render_categories_for_article (article_id);
        render_licenses (data);
        jQuery("#authors").on("input", function (event) {
            return autocomplete_author (event, article_id);
        });
        jQuery("#references").on("keypress", function(e){
            if(e.which == 13){
                add_reference(article_id);
            }
        });
        render_files_for_article (article_id);
        if (data["defined_type_name"] != null) {
            jQuery(`#type-${data["defined_type_name"]}`).prop("checked", true);
        }
        if (data["group_id"] != null) {
            jQuery(`#group_${data["group_id"]}`).prop("checked", true);
        }
        jQuery(`#article_${article_id}`).removeClass("loader");
        jQuery(`#article_${article_id}`).show();
        var quill = new Quill('#description', { theme: '4tu' });
        activate_drag_and_drop ();

        jQuery("input[name='record_type']").change(function () {
            toggle_record_type (article_id);
        });

        if (data["is_metadata_record"]) {
            jQuery("#metadata_record_only").prop("checked", true);
        } else if (data["has_linked_file"]) {
            jQuery("#external_link").prop("checked", true);
        } else {
            jQuery("#upload_files").prop("checked", true);
        }

        jQuery("#delete").on("click", function (event) { delete_article (article_id); });
        jQuery("#save").on("click", function (event)   { save_article (article_id); });
    }).fail(function () { console.log(`Failed to retrieve article ${current_article_id}.`); });
}

function create_article (title, on_success, on_failure) {
    if (current_article_id != null) {
        on_success (current_article_id);
    } else {
        var jqxhr = jQuery.ajax({
            url:         "/v2/account/articles",
            type:        "POST",
            data:        JSON.stringify({ "title": title }),
            contentType: "application/json",
            dataType:    "json"
        }).done(function (data) {
            current_article_id = data.location.split("/").pop();
            on_success (current_article_id);
        }).fail(function ()     { on_failure(); });
    }
}

function perform_upload (files, current_file) {
    total_files = files.length;
    create_article ("Untitled article", function (article_id) {
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
            url:         `/v3/articles/${article_id}/upload`,
            type:        "POST",
            data:        data,
            processData: false,
            contentType: false,
            success: function (data, textStatus, request) {
                jQuery("#file-upload h4").text("Drag files here");
                render_files_for_article (article_id);
                if (current_file < total_files) {
                    return perform_upload (files, current_file + 1, total_files);
                }
            }
        });
    }, function () {
        jQuery("#file-upload").css("background", "#990000");
    });
}

function remove_file (file_id, article_id) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/files/${file_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (files) {
        render_files_for_article (article_id);
        if (jQuery("#external_link").prop("checked")) {
            jQuery("#external_link_field").show();
        }
    }).fail(function () { console.log (`Failed to remove ${file_id}`); });
}

function remove_author (author_id, article_id) {
    var jqxhr = jQuery.ajax({
        url:         `/v2/account/articles/${article_id}/authors/${author_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (authors) { render_authors_for_article (article_id); })
      .fail(function () { console.log (`Failed to remove ${author_id}`); });
}

function remove_reference (url, article_id) {
    var jqxhr = jQuery.ajax({
        url:         `/v3/articles/${article_id}/references?url=${url}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function (authors) { render_references_for_article (article_id); })
      .fail(function () { console.log (`Failed to remove ${url}`); });
}

function prettify_size (size) {
    var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (size == 0 || size == null) return '0 Byte';
    var i = parseInt(Math.floor(Math.log(size) / Math.log(1000)));
    return Math.round(size / Math.pow(1000, i), 2) + ' ' + sizes[i];
}

function activate_drag_and_drop () {
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
        perform_upload (files, 1);
    });

    // Open file selector on div click
    jQuery("#file-upload").click(function () {
        jQuery("#file").click();
    });

    // file selected
    jQuery("#file").change(function () {
        var files = jQuery('#file')[0].files;
        perform_upload (files, 1);
    });
}
