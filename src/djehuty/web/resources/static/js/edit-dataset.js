function delete_dataset (dataset_uuid, event) {
    stop_event_propagation (event);
    if (confirm("Deleting this draft dataset is unrecoverable. "+
                "Do you want to continue?"))
    {
        jQuery.ajax({
            type:        "DELETE",
            url:         `/v2/account/articles/${dataset_uuid}`
        }).done(function () { window.location.pathname = "/my/datasets"; })
          .fail(function (jqXHR, textStatus, errorThrown) {
              if (jqXHR.status == 403) {
                  show_message ("failure", "<p>No permission to remove dataset.</p>");
              } else {
                  show_message ("failure", "<p>Failed to remove dataset.</p>");
              }
          });
    }
}

function decline_dataset (dataset_uuid, event) {
    stop_event_propagation (event);

    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css("opacity", "0.15");
    save_dataset (dataset_uuid, event, false, function() {
        jQuery.ajax({
            accept:      "application/json",
            type:        "POST",
            url:         `/v3/datasets/${dataset_uuid}/decline`
        }).done(function () {
            window.location.replace("/logout");
        }).fail(function (response, text_status, error_code) {
            show_message ("failure",
                          `<p>Could not decline due to error ` +
                          `<code>${error_code}</code>.</p>`);
            jQuery("#content-wrapper").css("opacity", "1.0");
            jQuery("#content").removeClass("loader-top");
        });
    });
}

function preview_dataset (dataset_uuid, event) {
    stop_event_propagation (event);
    let current_date = new Date();
    let year  = current_date.getFullYear();
    let month = current_date.getMonth() + 1; // getMonth is zero-indexed.
    let day   = current_date.getDate() + 1;
    if (month < 10) { month = `0${month}`; }
    if (day < 10) { day = `0${day}`; }

    save_dataset (dataset_uuid, event, false, function() {
        jQuery.ajax({
            accept:      "application/json",
            contentType: "application/json",
            data:        JSON.stringify({ "expires_date": `${year}-${month}-${day}` }),
            type:        "POST",
            url:         `/v2/account/articles/${dataset_uuid}/private_links`
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
    let category_ids = [];
    for (let category of categories) {
        category_ids.push(jQuery(category).val());
    }

    let defined_type_name = null;
    if (jQuery("#upload_software").prop("checked")) {
        defined_type_name = "software";
    } else {
        defined_type_name = "dataset";
    }

    let group_id = jQuery("input[name='groups']:checked")[0];
    if (group_id !== undefined) { group_id = group_id["value"]; }
    else { group_id = null; }

    let is_embargoed  = jQuery("#embargoed_access").prop("checked");
    let is_restricted = jQuery("#restricted_access").prop("checked");
    let agreed_to_da  = jQuery("#deposit_agreement").prop("checked");
    let agreed_to_publish = jQuery("#publish_agreement").prop("checked");
    let is_metadata_record = jQuery("#metadata_record_only").prop("checked");

    let title = or_null(jQuery("#title").val());
    if (title == "" || title == null) { title = "Untitled item"; }
    let form_data = {
        "title":          title,
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
        "git_repository_name": or_null(jQuery("#git-repository-name").val()),
        "git_code_hosting_url": or_null(jQuery("#git-code-hosting-url").val()),
        "is_metadata_record": is_metadata_record,
        "metadata_reason": or_null(jQuery("#metadata_only_reason").val()),
        "defined_type":   defined_type_name,
        "is_embargoed":   is_embargoed || is_restricted,
        "group_id":       group_id,
        "agreed_to_deposit_agreement": agreed_to_da,
        "agreed_to_publish": agreed_to_publish,
        "categories":     category_ids
    };

    if (is_embargoed) {
        form_data["embargo_until_date"] = or_null(jQuery("#embargo_until_date").val());
        form_data["embargo_title"]  = "Under embargo";
        form_data["embargo_reason"] = or_null(jQuery("#embargo_reason .ql-editor").html());
        if (form_data["embargo_reason"] !== null) {
            form_data["embargo_reason"] = form_data["embargo_reason"].replaceAll('<p class="ql-align-justify">', '<p>');
        }
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
        if (form_data["embargo_reason"] !== null) {
            form_data["embargo_reason"] = form_data["embargo_reason"].replaceAll('<p class="ql-align-justify">', '<p>');
        }
        form_data["eula"]           = or_null(jQuery("#restricted_access_eula .ql-editor").html());
        if (form_data["eula"] !== null) {
            form_data["eula"] = form_data["eula"].replaceAll('<p class="ql-align-justify">', '<p>');
        }
        form_data["embargo_options"] = [{ "id": 1000, "type": "restricted_access" }];
    } else {
        form_data["license_id"]     = or_null(jQuery("#license_open").val());
    }

    if (form_data["description"] !== null) {
        form_data["description"] = form_data["description"].replaceAll('<p class="ql-align-justify">', '<p>');
    }
    return form_data;
}

function save_dataset (dataset_uuid, event, notify=true, on_success=jQuery.noop) {
    stop_event_propagation (event);

    // When keywords were entered but yet submitted, handle those first.
    add_tag (dataset_uuid);
    add_reference (dataset_uuid);
    let external_url = jQuery("#external_url").val();
    if (external_url && external_url != "") {
        submit_external_link (dataset_uuid);
    }
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
    }).fail(function (jqXHR, textStatus, errorThrown) {
        if (notify) {
            let json = jqXHR.responseJSON;
            let message = "<p>Failed to save draft. Please try again at a later time.</p>";
            if (json) { message = `<p>Failed to save draft: ${json.message}</p>`; }
            show_message ("failure", message);
        }
    });
}

function delete_all_files (dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files`,
        data:        JSON.stringify({ "remove_all": true }),
        type:        "DELETE",
        accept:      "application/json",
        contentType: "application/json",
    }).done(function () {
        jQuery("#remove-all-files").text(`Remove all files.`);
        render_files_for_dataset (dataset_uuid, null);
        jQuery("#thumbnails-wrapper").hide();
        jQuery("#thumbnail-files-wrapper").hide();
    }).fail(function () {
        show_message ("failure", "<p>Failed to remove files.</p>");
    });
}

function repair_md5_sums (dataset_uuid, event) {
    save_dataset (dataset_uuid, event, false, function() {
        jQuery.ajax({
            url:         `/v3/datasets/${dataset_uuid}/repair_md5s`,
            type:        "GET",
            accept:      "application/json",
        }).done(function (record) {
            location.reload();
        }).fail(function () {
            show_message ("failure", "<p>Failed to repair MD5 checksums.</p>");
        });
    });
}

function render_licenses (dataset) {
    let chosen_license = null;
    // When the dataset hasn't been given a license yet, accessing
    // license.value will throw a TypeError. This is expected.
    try { chosen_license = dataset.license.value; }
    catch (error) {}

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
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve license list.</p>");
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
        show_message ("failure", "<p>Failed to retrieve categories.</p>");
    });
}

function remove_reference_event (event) {
    stop_event_propagation (event);
    remove_reference (event.data["encoded_url"], event.data["dataset_uuid"]);
}

function render_references_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/references`,
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
                      { "encoded_url": encoded_url, "dataset_uuid": dataset_uuid },
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

function remove_collaborator_event (event) {
    stop_event_propagation (event);
    remove_collaborator (event.data["collaborator_uuid"],
                         event.data["dataset_uuid"],
                         event.data["may_edit_metadata"]);
}

function update_collaborator_event (event) {
    stop_event_propagation (event);
    update_collaborator (event.data["collaborator_uuid"],
                         event.data["dataset_uuid"],
                         event.data["may_edit_metadata"]);
}

function render_collaborators_for_dataset (dataset_uuid, may_edit_metadata, callback=jQuery.noop) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/collaborators`,
        data:        { "limit": 10000, "order": "id", "order_direction": "asc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (collaborators) {
        jQuery("#collaborators-form tbody").empty();

        for (let collaborator of collaborators) {
            let row = jQuery("<tr/>", { "id": `row-${encodeURIComponent(collaborator.uuid)}` });
            let column1 = jQuery("<td/>");
            let supervisor_badge = "";
            let group_member_badge = "";
            if (collaborator.is_supervisor) {
                supervisor_badge = '<span class="active-badge">Supervisor</span>';
            }
            if (collaborator.is_inferred) {
                group_member_badge = `<span class="active-badge">${collaborator.group_name}</span>`;
            }
            let input_settings = { "type": "checkbox" };
            if (collaborator.is_supervisor) { input_settings["disabled"] = "disabled" };

            column1.html(`${collaborator.first_name} ${collaborator.last_name} (${collaborator.email})${supervisor_badge}${group_member_badge}`);
            let column2 = jQuery("<td/>", { "class": "type-begin" });
            let column3 = jQuery("<td/>", { "class": "type-end" });
            let column4 = jQuery("<td/>");
            let column5 = jQuery("<td/>");
            let column6 = jQuery("<td/>", { "class": "type-end" });
            let column7 = jQuery("<td/>");
            let column8 = jQuery("<td/>");

            let input1_settings = { ...input_settings, ...{ "class": "subitem-checkbox-metadata", "name": "read" } };
            let input2_settings = { ...input_settings, ...{ "class": "subitem-checkbox-metadata", "name": "edit" } };
            let input3_settings = { ...input_settings, ...{ "class": "subitem-checkbox-data", "name": "read" } };
            let input4_settings = { ...input_settings, ...{ "class": "subitem-checkbox-data", "name": "edit" } };
            let input5_settings = { ...input_settings, ...{ "class": "subitem-checkbox-data", "name": "remove" } };

            if (collaborator.metadata_read) { input1_settings["checked"] = "checked" };
            if (collaborator.metadata_edit) { input2_settings["checked"] = "checked" };
            if (collaborator.data_read) { input3_settings["checked"] = "checked" };
            if (collaborator.data_edit) { input4_settings["checked"] = "checked" };
            if (collaborator.data_remove) { input5_settings["checked"] = "checked" };

            column2.append (jQuery("<input/>", input1_settings));
            column3.append (jQuery("<input/>", input2_settings));
            column4.append (jQuery("<input/>", input3_settings));
            column5.append (jQuery("<input/>", input4_settings));
            column6.append (jQuery("<input/>", input5_settings));

            if (may_edit_metadata && !collaborator.is_inferred && !collaborator.is_supervisor) {
                let anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-trash-can", "title": "Remove" });
                anchor.on("click", {
                    "collaborator_uuid": collaborator.uuid,
                    "dataset_uuid": dataset_uuid,
                    "may_edit_metadata": may_edit_metadata }, remove_collaborator_event);
                column7.append(anchor);
            }
            if (may_edit_metadata && !collaborator.is_supervisor && !collaborator.is_inferred) {
                let anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-sync", "title": "Update" });
                anchor.on("click", {
                    "collaborator_uuid": collaborator.uuid,
                    "dataset_uuid": dataset_uuid,
                    "may_edit_metadata": may_edit_metadata }, update_collaborator_event);
                column8.append(anchor);
            }

            row.append([column1, column2, column3, column4, column5, column6, column7, column8]);
            if (collaborator.is_supervisor) { jQuery("#collaborators-form tbody").prepend(row); }
            else { jQuery("#collaborators-form tbody").append(row); }

        }

        if (may_edit_metadata) {
            let row = "<tr>";
            row += '<td><input type="text" id="add_collaborator" name="add_collaborator" value=""/>';
            row += '<input type="hidden" id="account_uuid" name="account_uuid" value=""/></td>';
            row += '<td class="type-begin"><input class="subitem-checkbox-metadata" name="read" type="checkbox" checked="checked" disabled="disabled"></td>';
            row += '<td class="type-end"><input class="subitem-checkbox-metadata" name="edit" type="checkbox"></td>';
            row += '<td><input class="subitem-checkbox-data" name="read" type="checkbox"></td>';
            row += '<td><input class="subitem-checkbox-data" name="edit" type="checkbox"></td>';
            row += '<td class="type-end"><input class="subitem-checkbox-data" name="remove" type="checkbox"></td>';
            row += '<td><a id="add-collaborator-button" class="fas fa-plus" href="#" ';
            row += 'title="Add collaborator"></a></td>';
            row += '<td></td>';
            row += "</tr>";
            jQuery("#collaborators-form tbody").prepend(row);
            jQuery("#add-collaborator-button").on("click", function(event) {
                stop_event_propagation (event);
                add_collaborator(dataset_uuid, may_edit_metadata);
            });
        }

        jQuery("#add_collaborator").on("input", function (event) {
            return autocomplete_collaborator (event, dataset_uuid);
        });
        jQuery("#collaborators-form").show();
        callback ();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve collaborators.</p>");
    });
}

function update_collaborator (collaborator_uuid, dataset_uuid, may_edit_metadata) {
    if (may_edit_metadata) {
        let update_form_data = {
            "metadata": {
                "read": jQuery(`#row-${collaborator_uuid} input[name='read'].subitem-checkbox-metadata`).prop("checked"),
                "edit": jQuery(`#row-${collaborator_uuid} input[name='edit'].subitem-checkbox-metadata`).prop("checked"),
            },
            "data": {
                "read": jQuery(`#row-${collaborator_uuid} input[name='read'].subitem-checkbox-data`).prop("checked"),
                "edit": jQuery(`#row-${collaborator_uuid} input[name='edit'].subitem-checkbox-data`).prop("checked"),
                "remove": jQuery(`#row-${collaborator_uuid} input[name='remove'].subitem-checkbox-data`).prop("checked"),
            },
            "account": or_null(jQuery("#account_uuid").val())
        };

        jQuery.ajax({
            url: `/v3/datasets/${dataset_uuid}/collaborators/${collaborator_uuid}`,
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify(update_form_data),
        }).done(function () {
            render_collaborators_for_dataset(dataset_uuid, may_edit_metadata);
            jQuery("#update_collaborator").val("");
        })
            .fail(function () {
                show_message("failure", `<p>Failed to update ${collaborator_uuid}</p>`);
            });
    }
}

function add_collaborator (dataset_uuid, may_edit_metadata) {
    let form_data= {
        "metadata": {
            "read": jQuery("input[name='read'].subitem-checkbox-metadata").prop("checked"),
            "edit": jQuery("input[name='edit'].subitem-checkbox-metadata").prop("checked"),
        },
        "data": {
            "read": jQuery("input[name='read'].subitem-checkbox-data").prop("checked"),
            "edit": jQuery("input[name='edit'].subitem-checkbox-data").prop("checked"),
            "remove": jQuery("input[name='remove'].subitem-checkbox-data").prop("checked"),
        },
        "account": or_null(jQuery("#account_uuid").val())
    };

    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/collaborators`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        render_collaborators_for_dataset(dataset_uuid, may_edit_metadata);
        jQuery("#add_collaborator").val("");
    }).fail(function () { show_message ("failure", `<p>Failed to add collaborator.</p>`); });
}

function remove_collaborator (collaborator_uuid, dataset_uuid, may_edit_metadata) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/collaborators/${collaborator_uuid}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_collaborators_for_dataset (dataset_uuid, may_edit_metadata); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${collaborator_uuid}</p>`); });
}

function remove_tag_event (event) {
    stop_event_propagation (event);
    remove_tag (encodeURIComponent(event.data["tag"]), event.data["dataset_uuid"]);
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
            let row = jQuery("<li/>");
            let anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-trash-can" });
            anchor.on("click", { "tag": tag, "dataset_uuid": dataset_uuid }, remove_tag_event);
            row.append(jQuery("<span/>").html(`${tag} &nbsp; `)).append(anchor);
            jQuery("#tags-list").append(row);
        }
        jQuery("#tags-list").show();
    }).fail(function () { show_message ("failure", "<p>Failed to retrieve tags.</p>"); });
}

function cancel_edit_author (author_uuid, dataset_uuid) {
    jQuery("#author-inline-edit-form").remove();
    jQuery(`#edit-author-${author_uuid}`)
        .removeClass("fa-times")
        .removeClass("fa-lg")
        .addClass("fa-pen")
        .on ("click", { "author_uuid": author_uuid, "dataset_uuid": dataset_uuid },
             edit_author_event);
}

function reorder_author (dataset_uuid, author_uuid, direction) {
    jQuery.ajax({
        url:  `/v3/datasets/${dataset_uuid}/reorder-authors`,
        data: JSON.stringify({ "author":  author_uuid, "direction": direction }),
        type: "POST",
        contentType: "application/json",
        accept: "application/json"
    }).done (function () {
        render_authors_for_dataset (dataset_uuid);
    }).fail(function () {
        show_message ("failure", "<p>Failed to change the order of the authors.</p>");
    });
}

function update_author (author_uuid, dataset_uuid) {
    let record = {
        "first_name": jQuery("#edit_author_first_name").val(),
        "last_name": jQuery("#edit_author_last_name").val(),
        "email": jQuery("#edit_author_email").val(),
        "orcid": jQuery("#edit_author_orcid").val()
    };
    jQuery.ajax({
        url:         `/v3/authors/${author_uuid}`,
        data:        JSON.stringify(record),
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
    }).done(function () {
        cancel_edit_author (author_uuid, dataset_uuid);
        render_authors_for_dataset (dataset_uuid);
    }).fail(function () {
        show_message ("failure", "<p>Failed to update author details.</p>");
    });
}

function cancel_edit_author_event (event) {
    stop_event_propagation (event);
    cancel_edit_author (event.data["author_uuid"], event.data["dataset_uuid"]);
}

function edit_author_event (event) {
    stop_event_propagation (event);
    edit_author (event.data["author_uuid"], event.data["dataset_uuid"]);
}

function update_author_event (event) {
    stop_event_propagation (event);
    update_author (event.data["author_uuid"], event.data["dataset_uuid"]);
}

function edit_author (author_uuid, dataset_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/authors/${author_uuid}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (author) {
        let row = jQuery("<tr/>", { "id": "author-inline-edit-form" });
        let column1 = jQuery("<td/>", { "colspan": "5" });
        column1.append (jQuery("<label/>", { "for": "author_first_name" }).text("First name"));
        column1.append (jQuery("<input/>", { "type": "text", "id": "edit_author_first_name", "name": "author_first_name", "value": or_empty (author.first_name) }));
        column1.append (jQuery("<label/>", { "for": "author_last_name" }).text("Last name"));
        column1.append (jQuery("<input/>", { "type": "text", "id": "edit_author_last_name", "name": "author_last_name", "value": or_empty (author.last_name) }));
        column1.append (jQuery("<label/>", { "for": "author_email" }).text("E-mail address"));
        column1.append (jQuery("<input/>", { "type": "text", "id": "edit_author_email", "name": "author_email", "value": or_empty (author.email) }));
        column1.append (jQuery("<label/>", { "for": "author_orcid" }).text("ORCID"));
        column1.append (jQuery("<input/>", { "type": "text", "id": "edit_author_orcid", "name": "author_orcid", "value": or_empty (author.orcid) }));

        let button_wrapper = jQuery("<div/>", { "id": "update-author", "class": "a-button" });
        let anchor = jQuery("<a/>", { "href": "#" }).text("Update author");
        anchor.on("click", { "author_uuid": author_uuid, "dataset_uuid": dataset_uuid }, update_author_event);
        button_wrapper.append (anchor);
        column1.append (button_wrapper);
        row.append(column1);
        jQuery(`#author-${author_uuid}`).after(row);
        jQuery(`#edit-author-${author_uuid}`)
            .removeClass("fa-pen")
            .addClass("fa-times")
            .addClass("fa-lg")
            .on("click", { "author_uuid": author_uuid, "dataset_uuid": dataset_uuid },
                cancel_edit_author_event);
    });
}

function reorder_author_event (event) {
    stop_event_propagation (event);
    reorder_author (event.data["dataset_uuid"],
                    event.data["author_uuid"],
                    event.data["direction"]);
}

function remove_author_event (event) {
    stop_event_propagation (event);
    remove_author (event.data["author_uuid"], event.data["dataset_uuid"]);
}

function render_authors_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/authors`,
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
            if (author.orcid && author.orcid != "") { orcid = author.orcid; }
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
                }).on("click", { "author_uuid": author.uuid, "dataset_uuid": dataset_uuid }, edit_author_event));
            }
            if (number_of_items == 1) {
            } else if (index == 0) {
                column3.append(jQuery("<a/>", { "class": "fas fa-angle-down"}).on("click", {
                    "author_uuid": author.uuid,
                    "dataset_uuid": dataset_uuid,
                    "direction": "down" }, reorder_author_event));
            } else if (index == number_of_items - 1) {
                column4.append(jQuery("<a/>", { "class": "fas fa-angle-up"}).on("click", {
                    "author_uuid": author.uuid,
                    "dataset_uuid": dataset_uuid,
                    "direction": "up" }, reorder_author_event));
            } else {
                column3.append(jQuery("<a/>", { "class": "fas fa-angle-down"}).on("click", {
                    "author_uuid": author.uuid,
                    "dataset_uuid": dataset_uuid,
                    "direction": "down" }, reorder_author_event));
                column4.append(jQuery("<a/>", { "class": "fas fa-angle-up"}).on("click", {
                    "author_uuid": author.uuid,
                    "dataset_uuid": dataset_uuid,
                    "direction": "up" }, reorder_author_event));
            }
            column5.append(jQuery("<a/>", {
                "href": "#",
                "class": "fas fa-trash-can",
                "title": "Remove" }).on("click", { "author_uuid": author.uuid,
                                                   "dataset_uuid": dataset_uuid },
                                        remove_author_event));

            row.append([column1, column2, column3, column4, column5]);
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve author details.</p>");
    });
}

function remove_funding_event (event) {
    stop_event_propagation (event);
    remove_funding (event.data["funding_uuid"], event.data["dataset_uuid"]);
}

function render_funding_for_dataset (dataset_uuid) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/funding`,
        data:        { "limit": 10000, "order": "id", "order_direction": "asc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (funders) {
        jQuery("#funding-list tbody").empty();
        for (let funding of funders) {
            let row = jQuery("<tr/>");
            let column1 = jQuery("<td/>").text(funding.title);
            let column2 = jQuery("<td/>");
            let anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-trash-can", "title": "Remove" });
            anchor.on ("click", { "funding_uuid": funding.uuid, "dataset_uuid": dataset_uuid },
                       remove_funding_event);
            column2.html(anchor);
            row.append([column1, column2]);
            jQuery("#funding-list tbody").append(row);
        }
        jQuery("#funding-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve funding details.</p>");
    });
}

function render_git_branches_for_dataset (dataset_uuid, event) {
    stop_event_propagation (event);
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}.git/branches`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (data) {
        branches = data["branches"];
        jQuery("#git-branches").empty();
        if (branches !== null && branches.length > 0) {
            for (let index in branches) {
                default_branch = data["default-branch"];
                let selected = "";
                if (branches[index] == default_branch) {
                    selected = ' selected="selected"';
                }
                jQuery("#git-branches").append(`<option value="${branches[index]}"${selected}>${branches[index]}</option>`);
            }
        } else {
            jQuery("#git-branches").append('<option value="" disabled="disabled" selected="selected">No branches found</option>');
        }
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve Git branches.</p>");
        jQuery("#git-branches").empty();
        jQuery("#git-branches").append('<option value="" disabled="disabled" selected="selected">No branches found</option>');
    });
}

function set_default_git_branch (dataset_uuid, event) {
    stop_event_propagation (event);
    let branch_name = jQuery("#git-branches").val();
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}.git/set-default-branch`,
        data:        JSON.stringify({ "branch": branch_name }),
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
    }).done(function () {
        show_message ("success", `<p>Default Git branch set to <strong>${branch_name}</strong>.</p>`);
        render_git_files_for_dataset (dataset_uuid, event);
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve Git file details.</p>");
    });
}

function render_git_files_for_dataset (dataset_uuid, event) {
    stop_event_propagation (event);
    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}.git/files`,
        data:        { "limit": 10000, "order": "id", "order_direction": "asc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (files) {
        jQuery("#git-files").empty();
        for (let index in files) {
            jQuery("#git-files").append(`<li>${files[index]}</li>`);
        }
        jQuery("#git-files-label").show();
        jQuery("#git-files-wrapper").show();
    }).fail(function () {
        jQuery("#git-files-label").hide();
        jQuery("#git-files-wrapper").hide();
        show_message ("failure", "<p>Failed to retrieve Git file details.</p>");
    });
}

function remove_file_event (event) {
    stop_event_propagation (event);
    remove_file (event.data["file_uuid"], event.data["dataset_uuid"]);
}

function render_files_for_dataset (dataset_uuid, fileUploader) {
    jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files`,
        data:        { "limit": 10000, "order": "id", "order_direction": "asc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (files) {
        if (fileUploader !== null) {
            fileUploader.removeAllFiles();
        }
        jQuery("#files tbody").empty();
        if (files.length > 0) {
            jQuery("input[name='record_type']").attr('disabled', true);
            jQuery("#upload_software").attr('disabled', false);
            jQuery("#upload_files").attr('disabled', false);

            let number_of_files = 0;
            for (let index in files) {
                let file = files[index];
                if (file.name === null) {
                    file.name = file.download_url;
                }
                let row = jQuery("<tr/>");
                let column1 = jQuery("<td/>");
                let column2 = jQuery("<td/>");
                let column3 = jQuery("<td/>");
                let anchor = jQuery("<a/>", { "href": `/file/${dataset_uuid}/${file.uuid}` }).text(file.name);
                let file_size = jQuery("<span/>", { "class": "file-size" }).text(prettify_size(file.size));
                column1.append([anchor, file_size]);
                if ("is_incomplete" in file && file["is_incomplete"] == true) {
                    column1.append(jQuery("<span/>", { "class": "file-incomplete-warning" }).text("The file upload was not complete!"));
                }
                let file_handle = "";
                if ("handle" in file) {
                    let handle_anchor = jQuery("<a/>", { "href": `https://hdl.handle.net/${file.handle}` });
                    handle_anchor.html(jQuery("<img/>", {
                        "src": "/static/images/handle-logo.png",
                        "class": "handle-icon",
                        "alt": "Handle"
                    }));
                    column1.append(handle_anchor);
                }
                if (file["computed_md5"] === null) {
                    column2.text(`${render_in_form("Unavailable")}`);
                } else {
                    column2.text(`${render_in_form(file["computed_md5"])}`);
                }

                let remove_anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-trash-can", "title": "Remove" });
                remove_anchor.on ("click", { "file_uuid": file.uuid, "dataset_uuid": dataset_uuid }, remove_file_event);
                column3.html(remove_anchor);
                row.append([column1, column2, column3]);
                jQuery("#files tbody").append(row);
                number_of_files += 1;
            }
            jQuery("#remove-all-files").text(`Remove all ${number_of_files} files.`);
            jQuery("#files").show();
            jQuery("#files-table-actions").show();
            render_files_for_thumbnail (dataset_uuid);
        } else {
            jQuery("#files").hide();
            jQuery("#files-table-actions").hide();
            jQuery("input[name='record_type']").attr('disabled', false);
            render_files_for_thumbnail (dataset_uuid);
        }
    }).fail(function (jqXHR, textStatus, errorThrown) {
        if (jqXHR.status == 403) {
            let html = '<tr class="notice-box"><td colspan="2">You do not have permission to view the files.</td><td></td></tr>';
            jQuery("#files tbody").empty().append(html);
        } else {
            show_message ("failure", "<p>Failed to retrieve file details.</p>");
        }
    });
}

function render_files_for_thumbnail (dataset_uuid) {

    function html_for_thumbnail_tile (img_src, file_uuid, title) {
        if (initial_thumbnail_file_uuid == null) { initial_thumbnail_file_uuid = ""; }
        let active = " thumbnail-active";
        if (file_uuid != initial_thumbnail_file_uuid) { active = " thumbnail-inactive"; }
        html  = `<div class="thumbnail-item${active}"><label>`;
        html += `<input type="radio" name="thumbnail" value="${file_uuid}" />`;
        html += '<div class="thumbnail-item-img-wrapper">';
        html += `<img src="${img_src}" aria-hidden="true"/></div>`;
        html += `<div class="thumbnail-item-title"><p>${title}</p></div>`;
        html += '</label></div>';
        return html;
    }

    jQuery.ajax({
        url: `/v3/datasets/${dataset_uuid}/image-files`,
        data: { "limit": 10000 },
        type: "GET",
        accept: "application/json",
    }).done(function (files) {
        jQuery("#thumbnails-wrapper").empty();
        if (files.length > 0) {
            jQuery("#thumbnails-wrapper").show();
            jQuery("#thumbnail-files-wrapper").show();
            let html = "";
            html += html_for_thumbnail_tile ("/static/images/dataset-thumb.svg",
                                             "", "Standard thumbnail");

            for (let index in files) {
                let file = files[index];
                html += html_for_thumbnail_tile (`/file/${dataset_uuid}/${file.uuid}`,
                                                 file.uuid, file.name);
            }

            jQuery("#thumbnails-wrapper").append(html);
            jQuery("#thumbnails-wrapper").show();

            // Add event listener to toggle the blue border on selection
            jQuery('input[name="thumbnail"]').change(function () {
                jQuery(".thumbnail-item")
                    .removeClass("thumbnail-active")
                    .addClass("thumbnail-inactive");

                let selected_thumb = jQuery('input[name="thumbnail"]:checked');
                selected_thumb.closest('.thumbnail-item').addClass("thumbnail-active");
                jQuery.ajax({
                    url: `/v3/datasets/${dataset_uuid}/update-thumbnail`,
                    type: "PUT",
                    contentType: "application/json",
                    accept:      "application/json",
                    data:        JSON.stringify({ "uuid": `${selected_thumb.val()}` })
                }).fail(function () {
                    show_message ("failure", "<p>Failed to set thumbnail.</p>");
                });
            });
        } else {
            jQuery("#thumbnails-wrapper").hide();
            jQuery("#thumbnail-files-wrapper").hide();
        }
    }).fail(function () {
        show_message("failure", "<p>Failed to retrieve thumbnail file details.</p>");
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
        url:         `/v3/datasets/${dataset_uuid}/tags`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "tags": tags }),
    }).done(function () {
        render_tags_for_dataset (dataset_uuid);
        jQuery("#tag").val("");
        autocomplete_tags(null, dataset_uuid);
    }).fail(function () { show_message ("failure", `<p>Failed to add ${tag}.</p>`); });
}

function submit_new_author (dataset_uuid) {
    let first_name = jQuery("#author_first_name").val();
    let last_name = jQuery("#author_last_name").val();
    jQuery("#author_first_name").removeClass("missing-required") ;
    jQuery("#author_last_name").removeClass("missing-required") ;

    if (first_name == "" && last_name == "") {
        let error_message = "<p>You must enter at least one of the first or last names.</p>";
        jQuery("#author_first_name").addClass("missing-required") ;
        show_message ("failure", `${error_message}`);
        return false;
    }

    let authors = [{
        "name":       `${first_name} ${last_name}`,
        "first_name": first_name,
        "last_name":  last_name,
        "email":      jQuery("#author_email").val(),
        "orcid_id":   jQuery("#author_orcid").val()
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
        jQuery("#authors").val("");
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

function submit_new_author_event (event) {
    stop_event_propagation (event);
    submit_new_author (event.data["dataset_uuid"]);
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
    anchor.on ("click", { "dataset_uuid": dataset_uuid}, submit_new_author_event);
    button_wrapper.append(anchor);

    html.append(button_wrapper);
    jQuery("#authors-ac ul").remove();
    jQuery("#new-author").remove();
    jQuery("#authors-ac").append(html);
}

function submit_new_funding_event (event) {
    stop_event_propagation (event);
    submit_new_funding (event.data["dataset_uuid"]);
}

function new_funding (dataset_uuid) {
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
    let anchor = jQuery("<a/>", { "href": "#" });
    anchor.on ("click", { "dataset_uuid": dataset_uuid }, submit_new_funding_event).text("Add funding");
    new_funding_button.append (anchor);
    html.append (new_funding_button);

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

function activate (dataset_uuid, permissions=null, callback=jQuery.noop) {
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
        jQuery("#add-reference-button").on("click", function(event) {
            stop_event_propagation (event);
            add_reference (dataset_uuid);
        });
         jQuery("#collaborators").on("keypress", function(e){
            if (e.which == 13) {
                add_collaborator(dataset_uuid, permissions.metadata_edit);
            }
        });

        jQuery("#collaborators").on("keypress", function(e){
            if (e.which == 13) {
                update_collaborator(dataset_uuid, permissions.metadata_edit);
            }
        });

        if (permissions.data_edit) {
            jQuery("#repair-md5s").on("click", function(event) {
                stop_event_propagation (event);
                repair_md5_sums (dataset_uuid, event);
            });
        }
        if (permissions.data_remove) {
            jQuery("#remove-all-files").on("click", function(event) {
                stop_event_propagation (event);
                delete_all_files (dataset_uuid);
            });
        }
        jQuery("#add-keyword-button").on("click", function(event) {
            stop_event_propagation (event);
            add_tag (dataset_uuid);
        });
        jQuery("#tag").on("keypress", function(e){
            if(e.which == 13){
                add_tag(dataset_uuid);
            }
        });
        jQuery("#tag").on("input", function (event) {
            return autocomplete_tags (event, dataset_uuid);
        });
        jQuery(".subitem-checkbox-metadata").on("change", function (event) {
            if (jQuery(".subitem-checkbox-metadata[name='edit']").prop("checked")) {
                jQuery(".subitem-checkbox-metadata[name='read']").prop("checked", true);
                jQuery(".subitem-checkbox-metadata[name='read']").attr("disabled", true);
            } else {
                jQuery(".subitem-checkbox-metadata[name='read']").attr("disabled", false);
            }
         });

         jQuery(".subitem-checkbox-dataset").on("change", function (event) {
            let edit = jQuery(".subitem-checkbox-dataset[name='edit']").prop("checked");
            let remove = jQuery(".subitem-checkbox-dataset[name='remove']").prop("checked");

            if (remove) {
                jQuery(".subitem-checkbox-dataset[name='edit']").prop("checked", true);
                edit = true;
                jQuery(".subitem-checkbox-dataset[name='read']").prop("checked", true);
            } else if (edit) {
                jQuery(".subitem-checkbox-dataset[name='read']").prop("checked", true);
            }
            if (remove) {
                jQuery(".subitem-checkbox-dataset[name='edit']").attr("disabled", true);
                jQuery(".subitem-checkbox-dataset[name='read']").attr("disabled", true);
            } else {
                jQuery(".subitem-checkbox-dataset[name='edit']").attr("disabled", false);
                jQuery(".subitem-checkbox-dataset[name='read']").attr("disabled", true);
            }
            if (edit) {
                jQuery(".subitem-checkbox-dataset[name='read']").attr("disabled", true);
            } else {
                jQuery(".subitem-checkbox-dataset[name='read']").attr("disabled", false);
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
            parallelUploads:   1,
            autoProcessQueue:  false,
            autoQueue:         true,
            ignoreHiddenFiles: false,
            disablePreviews:   false,
            init: function() {
                $(window).on('beforeunload', function() {
                    if (fileUploader.getUploadingFiles().length > 0 ||
                        fileUploader.getQueuedFiles().length > 0) {
                        // Custom message cannot be used in most browsers
                        // since it was used for scam. Therefore, pop-up message
                        // depends on user's browser.
                        return 1;
                    }
                });
            },
            accept: function(file, done) {
                done();
                fileUploader.processQueue();
            },
            complete: function (file) {
                if (fileUploader.getUploadingFiles().length === 0 &&
                    fileUploader.getQueuedFiles().length === 0) {
                    let rejected_files = fileUploader.getRejectedFiles();
                    for (let rejected of rejected_files) {
                        if (rejected.status == "error") {
                            show_message ("failure", `<p>Failed to upload '${rejected.upload.filename}'.</p>`);
                        }
                    }
                    render_files_for_dataset (dataset_uuid, fileUploader);
                } else {
                    fileUploader.processQueue();
                }
                fileUploader.removeFile(file);
            },
            error: function(file, message) {
                show_message ("failure",
                              (`<p>Failed to upload ${file.upload.filename}:` +
                               ` ${message.message}</p>`));
            }
        });
        if (!permissions.data_edit) { fileUploader.disable(); }

        jQuery("input[name='record_type']").change(function () {
            toggle_record_type ();
        });
        jQuery("#git-branches").on("change", function (event) {
            set_default_git_branch (dataset_uuid, event);
        });
        if (data["is_metadata_record"]) {
            jQuery("#metadata_record_only").prop("checked", true);
        } else if (data["has_linked_file"]) {
            jQuery("#external_link").prop("checked", true);
        } else if (data["defined_type_name"] == "software") {
            jQuery("#upload_software").prop("checked", true);
            render_git_files_for_dataset (dataset_uuid, null);
            render_git_branches_for_dataset (dataset_uuid, null);
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
        jQuery("#save_bottom").on("click", function (event)   { save_dataset (dataset_uuid, event); });
        jQuery("#submit").on("click", function (event) { submit_dataset (dataset_uuid, event); });
        jQuery("#publish").on("click", function (event) { publish_dataset (dataset_uuid, event); });
        jQuery("#decline").on("click", function (event) { decline_dataset (dataset_uuid, event); });
        jQuery("#preview").on("click", function (event) { preview_dataset (dataset_uuid, event); });
        jQuery("#refresh-git-files").on("click", function (event) {
            render_git_files_for_dataset (dataset_uuid, event);
            render_git_branches_for_dataset (dataset_uuid, event);
        });
        jQuery("input[name=access_type]").on("change", toggle_access_level);
        jQuery("#configure_embargo").on("click", toggle_embargo_options);
        jQuery("#embargo_until_forever").on("change", toggle_embargo_until);
        jQuery("#cancel_embargo").on("click", toggle_embargo_options);

        jQuery(".article-content-loader").hide();
        jQuery(".article-content").fadeIn(200);
        jQuery("#thumbnail-files-wrapper").hide();

        jQuery("#api-upload-fold").hide();
        jQuery("#api-upload-toggle").on("click", function (event) { toggle_api_upload_text (event); });
        jQuery("#expand-categories-button").on("click", toggle_categories);
        jQuery("#expand-collaborators-button").on("click", function (event) {
            toggle_collaborators (dataset_uuid, !is_shared_with_me, event)
        });
        callback ();
    }).fail(function () { show_message ("failure", `<p>Failed to retrieve article ${dataset_uuid}.</p>`); });
}

function toggle_api_upload_text (event) {
    stop_event_propagation (event);
    if (jQuery("#api-upload-fold").is(":hidden")) {
        jQuery("#api-upload-fold").slideDown(250);
    } else {
        jQuery("#api-upload-fold").slideUp(250);
    }
}
function toggle_embargo_options (event) {
    stop_event_propagation (event);
    if (jQuery("#embargo_options").is(":hidden")) {
        jQuery("#embargo_options").show();
        jQuery("#configure_embargo").hide();
    } else {
        jQuery("#embargo_options").hide();
        jQuery("#configure_embargo").show();
    }
}

function toggle_embargo_until (event) {
    stop_event_propagation (event);
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
        if (current_file < total_files) {
            return perform_upload (files, current_file + 1, dataset_uuid);
        } else {
            render_files_for_dataset (dataset_uuid, null);
        }
    }).fail(function () {
        show_message ("failure", "<p>Uploading file(s) failed.</p>");
    });
}

function remove_file (file_id, dataset_uuid, rerender=true) {
    return jQuery.ajax({
        url:         `/v2/account/articles/${dataset_uuid}/files/${file_id}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () {
        if (rerender) {
            render_files_for_dataset (dataset_uuid, null);
            if (jQuery("#external_link").prop("checked")) {
                jQuery("#external_link_field").show();
            }
        }
        return true;
    }).fail(function () {
        show_message ("failure", `<p>Failed to remove ${file_id}.</p>`);
        return false;
    });
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
    stop_event_propagation (event);
    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css('opacity', '0.15');
    save_dataset (dataset_uuid, event, false, function() {
        form_data = gather_form_data();
        let is_open_access = jQuery("#open_access").prop("checked");
        if (form_data["license_id"] == "98") {
            jQuery("#license_open").addClass("missing-required");
            jQuery("#license_embargoed").addClass("missing-required");
            show_message ("failure", "<p>The '4TU General Terms Of Use' is deprecated.  We selected 'CC0' instead.  Submit again to accept this change.</p>");
            if (is_open_access) {
                jQuery("#license_open").val("2");
            } else {
                jQuery("#license_embargoed").val("2");
            }
        }
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
    stop_event_propagation (event);
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
