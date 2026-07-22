function delete_physical_sample (container_uuid, event) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm("Deleting this draft is unrecoverable. "+
                "Do you want to continue?")) {
        window.location.replace(`/my/physical-samples/${container_uuid}/delete`);
    }
}

function gather_form_data (container_uuid) {
    let categories   = jQuery("input[name='categories']:checked");
    let category_ids = [];
    for (let category of categories) {
        category_ids.push(jQuery(category).val());
    }

    let group_id = jQuery("input[name='groups']:checked")[0];
    if (group_id !== undefined) { group_id = group_id["value"]; }
    else { group_id = null; }

    let form_data = {
        "title":                  or_null(jQuery("#title").val()),
        "abstract":               or_null(jQuery("#abstract .ql-editor").html()),
        "methods":                or_null(jQuery("#methods .ql-editor").html()),
        "publisher":              or_null(jQuery("#publisher").val()),
        "publication_year":       or_null(jQuery("#publication_year").val()),
        "resource_type":          or_null(jQuery("#resource_type").val()),
        "alternate_identifier":   or_null(jQuery("#alternate_identifier").val()),
        "related_resource":       or_null(jQuery("#related_resource").val()),
        "doi":                    or_null(jQuery("#doi").val()),
        "physical_storage_location": or_null(jQuery("#physical_storage_location").val()),
        "organizations":          or_null(jQuery("#organizations").val()),
        "geolocation":            or_null(jQuery("#geolocation").val()),
        "longitude":              or_null(jQuery("#longitude").val()),
        "latitude":               or_null(jQuery("#latitude").val()),
        "sample_owner_name":      or_null(jQuery("#sample_owner_name").val()),
        "sample_owner_email":     or_null(jQuery("#sample_owner_email").val()),
        "group_id":               group_id,
        "categories":             category_ids,
        "agreed_to_deposit_agreement": jQuery("#deposit_agreement").prop("checked"),
        "agreed_to_publish":      jQuery("#publish_agreement").prop("checked"),
    };
    return form_data;
}

function save_physical_sample (container_uuid, event, notify=true, on_success=jQuery.noop) {
    event.preventDefault();
    event.stopPropagation();

    let form_data = gather_form_data();
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}`,
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        if (notify) {
            show_message ("success", "<p>Saved changes.</p>");
        }
        on_success ();
    }).fail(function (jqXHR) {
        if (notify) {
            let json = jqXHR.responseJSON;
            let message = "<p>Failed to save draft. Please try again at a later time.</p>";
            if (json) { message = `<p>Failed to save draft: ${json.message}</p>`; }
            show_message ("failure", message);
        }
    });
}

function submit_physical_sample (container_uuid, event) {
    stop_event_propagation (event);
    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css("opacity", "0.15");
    save_physical_sample (container_uuid, event, false, function () {
        let form_data = gather_form_data();
        form_data["agreed_to_deposit_agreement"] = jQuery("#deposit_agreement").prop("checked");
        form_data["agreed_to_publish"] = jQuery("#publish_agreement").prop("checked");
        jQuery.ajax({
            url:         `/v3/physical-samples/${container_uuid}/submit-for-review`,
            type:        "PUT",
            contentType: "application/json",
            accept:      "application/json",
            data:        JSON.stringify(form_data),
        }).done(function () {
            window.location.replace("/my/physical-samples/submitted-for-review");
        }).fail(function (response) {
            jQuery(".missing-required").removeClass("missing-required");
            let error_messages = jQuery.parseJSON (response.responseText);
            if (error_messages && error_messages.length > 0) {
                let items = "";
                for (let message of error_messages) {
                    if (message.field_name == "group_id") {
                        jQuery("#groups-wrapper").addClass("missing-required");
                    } else if (message.field_name == "categories") {
                        jQuery("#categories-wrapper").addClass("missing-required");
                    } else if (message.field_name == "authors") {
                        jQuery("#authors").addClass("missing-required");
                    } else if (message.field_name == "tag") {
                        jQuery("#tag").addClass("missing-required");
                    } else if (message.field_name == "agreed_to_deposit_agreement") {
                        jQuery("label[for='deposit_agreement']").addClass("missing-required");
                    } else if (message.field_name == "agreed_to_publish") {
                        jQuery("label[for='publish_agreement']").addClass("missing-required");
                    } else {
                        jQuery(`#${message.field_name}`).addClass("missing-required");
                    }
                    if (message.message) {
                        items += `<li>${message.message}</li>`;
                    }
                }
                show_message ("failure",
                              `<p>Please correct the following before submitting:</p>` +
                              `<ul>${items}</ul>`);
            } else {
                show_message ("failure", "<p>Please fill in all required fields.</p>");
            }
            jQuery("#content-wrapper").css("opacity", "1.0");
            jQuery("#content").removeClass("loader-top");
        });
    });
}

function publish_physical_sample (container_uuid, event) {
    stop_event_propagation (event);
    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css("opacity", "0.15");
    save_physical_sample (container_uuid, event, false, function () {
        jQuery.ajax({
            url:         `/v3/physical-samples/${container_uuid}/publish`,
            type:        "POST",
            accept:      "application/json",
        }).done(function () {
            window.location.replace("/logout");
        }).fail(function (response, text_status, error_code) {
            show_message ("failure",
                          `<p>Could not publish due to error ` +
                          `<code>${error_code}</code>.</p>`);
            jQuery("#content-wrapper").css("opacity", "1.0");
            jQuery("#content").removeClass("loader-top");
        });
    });
}

function decline_physical_sample (container_uuid, event) {
    stop_event_propagation (event);
    jQuery("#content").addClass("loader-top");
    jQuery("#content-wrapper").css("opacity", "0.15");
    save_physical_sample (container_uuid, event, false, function () {
        jQuery.ajax({
            accept:      "application/json",
            type:        "POST",
            url:         `/v3/physical-samples/${container_uuid}/decline`
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

function cancel_edit_author (author_uuid, container_uuid) {
    jQuery("#author-inline-edit-form").remove();
    jQuery(`#edit-author-${author_uuid}`)
        .off("click")
        .on("click", { "author_uuid": author_uuid, "container_uuid": container_uuid }, edit_author_event)
        .removeClass("fa-times")
        .removeClass("fa-lg")
        .addClass("fa-pen");
}

function update_author (author_uuid, container_uuid) {
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
        cancel_edit_author (author_uuid, container_uuid);
        render_authors (container_uuid);
    }).fail(function () {
        show_message ("failure", "<p>Failed to update author details.</p>");
    });
}

function edit_author (author_uuid, container_uuid) {
    jQuery.ajax({
        url:         `/v3/datasets/${container_uuid}/authors/${author_uuid}`,
        type:        "GET",
        accept:      "application/json",
    }).done(function (author) {
        let html = `<tr id="author-inline-edit-form"><td colspan="3">`;
        html += `<label for="author_first_name">First name</label>`;
        html += `<input type="text" id="edit_author_first_name" name="author_first_name" value="${or_empty(author.first_name)}">`;
        html += `<label for="author_last_name">Last name</label>`;
        html += `<input type="text" id="edit_author_last_name" name="author_last_name" value="${or_empty(author.last_name)}">`;
        html += `<label for="author_email">E-mail address</label>`;
        html += `<input type="text" id="edit_author_email" name="author_email" value="${or_empty(author.email)}">`;
        html += `<label for="author_orcid">ORCID</label>`;
        html += `<input type="text" id="edit_author_orcid" name="author_orcid" value="${or_empty(author.orcid)}">`;
        html += `<div id="update-author" class="a-button"><a href="#" id="update-author-btn">Update author</a></div>`;
        html += `</td></tr>`;

        jQuery(`#author-${author_uuid}`).after(html);
        jQuery("#update-author-btn").on("click", { "author_uuid": author_uuid, "container_uuid": container_uuid },
            function (event) { stop_event_propagation(event); update_author(event.data["author_uuid"], event.data["container_uuid"]); });
        jQuery(`#edit-author-${author_uuid}`)
            .off("click")
            .on("click", { "author_uuid": author_uuid, "container_uuid": container_uuid },
                function (event) { stop_event_propagation(event); cancel_edit_author(event.data["author_uuid"], event.data["container_uuid"]); })
            .removeClass("fa-pen")
            .addClass("fa-times")
            .addClass("fa-lg");
    });
}

function add_author (author_uuid, container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/creators`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify([author_uuid]),
    }).done(function () {
        render_authors (container_uuid);
        jQuery("#authors").val("");
        autocomplete_author(null, container_uuid);
    }).fail(function () { show_message ("failure", `<p>Failed to add ${author_uuid}.</p>`); });
}

function submit_new_author (container_uuid) {
    let first_name = jQuery("#author_first_name").val();
    let last_name = jQuery("#author_last_name").val();
    jQuery("#author_first_name").removeClass("missing-required");
    jQuery("#author_last_name").removeClass("missing-required");

    if (first_name == "" && last_name == "") {
        let error_message = "<p>You must enter at least one of the first or last names.</p>";
        jQuery("#author_first_name").addClass("missing-required");
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
        url:         `/v3/physical-samples/${container_uuid}/creators`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "authors": authors }),
    }).done(function () {
        jQuery("#authors-ac").remove();
        jQuery("#authors").removeClass("input-for-ac");
        jQuery("#authors").val("");
        render_authors (container_uuid);
    }).fail(function () { show_message ("failure", `<p>Failed to add author.</p>`); });
    return true;
}

function submit_new_author_event (event) {
    stop_event_propagation (event);
    submit_new_author (event.data["item_id"]);
}

function new_author (container_uuid) {
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
    anchor.on ("click", { "item_id": container_uuid }, submit_new_author_event);
    button_wrapper.append(anchor);

    html.append(button_wrapper);
    jQuery("#authors-ac ul").remove();
    jQuery("#new-author").remove();
    jQuery("#authors-ac").append(html);
}

function remove_author_event (event) {
    stop_event_propagation (event);
    remove_author (event.data["author_uuid"], event.data["container_uuid"]);
}

function edit_author_event (event) {
    stop_event_propagation (event);
    edit_author (event.data["author_uuid"], event.data["container_uuid"]);
}

function reorder_creator (container_uuid, author_uuid, direction) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/reorder-creators`,
        data:        JSON.stringify({ "author": author_uuid, "direction": direction }),
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json"
    }).done(function () {
        render_authors (container_uuid);
    }).fail(function () {
        show_message ("failure", "<p>Failed to change the order of the creators.</p>");
    });
}

function reorder_creator_event (event) {
    stop_event_propagation (event);
    reorder_creator (event.data["container_uuid"],
                     event.data["author_uuid"],
                     event.data["direction"]);
}

function render_authors (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/creators`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (authors) {
        jQuery("#authors-list tbody").empty();
        let number_of_items = authors.length;
        for (let index = 0; index < number_of_items; index++) {
            let author  = authors[index];
            let row     = jQuery("<tr/>", { "id": `author-${author.uuid}` });
            let column1 = jQuery("<td/>").text(author.full_name);
            let column2 = jQuery("<td/>");
            let column3 = jQuery("<td/>");
            let column4 = jQuery("<td/>");
            let column5 = jQuery("<td/>");
            let orcid = null;
            if (author.orcid_id && author.orcid_id != "") {
                orcid = author.orcid_id;
            } else if (author.orcid && author.orcid != "") {
                orcid = author.orcid;
            }
            if (orcid !== null) {
                let orcid_anchor = jQuery("<a/>", {
                    "href":   `https://orcid.org/${orcid}`,
                    "target": "_blank",
                    "rel":    "noopener noreferrer"
                });
                orcid_anchor.append(jQuery("<img/>", {
                    "src":   "/static/images/orcid.svg",
                    "class": "author-orcid",
                    "alt":   "ORCID",
                    "title": "ORCID profile (new window)"
                }));
                column1.append(orcid_anchor);
            }
            if (author.is_editable) {
                column2.append(jQuery("<a/>", {
                    "id":    `edit-author-${author.uuid}`,
                    "href":  "#",
                    "class": "fas fa-pen",
                    "title": "Edit"
                }).on("click", { "author_uuid": author.uuid, "container_uuid": container_uuid },
                               edit_author_event));
            }
            if (number_of_items == 1) {
            } else if (index == 0) {
                column3.append(jQuery("<a/>", { "class": "fas fa-angle-down" }).on("click", {
                    "author_uuid":    author.uuid,
                    "container_uuid": container_uuid,
                    "direction":      "down" }, reorder_creator_event));
            } else if (index == number_of_items - 1) {
                column4.append(jQuery("<a/>", { "class": "fas fa-angle-up" }).on("click", {
                    "author_uuid":    author.uuid,
                    "container_uuid": container_uuid,
                    "direction":      "up" }, reorder_creator_event));
            } else {
                column3.append(jQuery("<a/>", { "class": "fas fa-angle-down" }).on("click", {
                    "author_uuid":    author.uuid,
                    "container_uuid": container_uuid,
                    "direction":      "down" }, reorder_creator_event));
                column4.append(jQuery("<a/>", { "class": "fas fa-angle-up" }).on("click", {
                    "author_uuid":    author.uuid,
                    "container_uuid": container_uuid,
                    "direction":      "up" }, reorder_creator_event));
            }
            column5.append(jQuery("<a/>", {
                "href":  "#",
                "class": "fas fa-trash-can",
                "title": "Remove"
            }).on("click", { "author_uuid": author.uuid, "container_uuid": container_uuid },
                           remove_author_event));
            row.append([column1, column2, column3, column4, column5]);
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve author details.</p>");
    });
}

function remove_author (author_uuid, container_uuid) {
    jQuery.ajax({
        url:    `/v3/physical-samples/${container_uuid}/creators/${author_uuid}`,
        type:   "DELETE",
        accept: "application/json",
    }).done(function () { render_authors (container_uuid); })
      .fail(function () { show_message ("failure", "<p>Failed to remove author.</p>"); });
}

function remove_date (date_uuid, container_uuid) {
    jQuery.ajax({
        url:    `/v3/physical-samples/${container_uuid}/dates/${date_uuid}`,
        type:   "DELETE",
        accept: "application/json",
    }).done(function () { render_dates (container_uuid); })
      .fail(function () { show_message ("failure", "<p>Failed to remove date.</p>"); });
}

function set_date_format (format) {
    // Show only the picker for the chosen format and clear the others and update the tip.
    let hints = {
        "year":  "Enter the year only.",
        "month": "Enter the month and year.",
        "day":   "Enter the full calendar date."
    };
    jQuery("#date-year, #date-month, #date-day").hide().val("");
    if (format === "year") { jQuery("#date-year").show(); }
    else if (format === "month") { jQuery("#date-month").show(); }
    else { jQuery("#date-day").show(); }
    jQuery("#date-hint").text (hints[format] || "");
}

function get_new_date_value () {
    let format = jQuery("input[name='dateFormat']:checked").val();
    if (format === "year") { return or_null(jQuery("#date-year").val()); }
    if (format === "month") { return or_null(jQuery("#date-month").val()); }
    return or_null(jQuery("#date-day").val());
}

function auto_format_date (input, format) {
    // Keep only digits and re-insert the "/" separators as the user types
    let digits = input.value.replace(/\D/g, "");
    let out = "";
    if (format === "year") {
        out = digits.slice(0, 4);
    } else if (format === "month") {
        digits = digits.slice(0, 6);
        out = digits.slice(0, 2);
        if (digits.length > 2) { out += "/" + digits.slice(2); }
    } else {
        digits = digits.slice(0, 8);
        out = digits.slice(0, 2);
        if (digits.length > 2) { out += "/" + digits.slice(2, 4); }
        if (digits.length > 4) { out += "/" + digits.slice(4); }
    }
    input.value = out;
}

function to_iso_date (format, raw) {
    // Convert the "user friendly" day first input to ISO (year-first).
    // Returns the ISO string, or false when the value is not a valid date.
    let value = raw.trim();
    if (format === "year") {
        return (/^\d{4}$/.test(value)) ? value : false;
    }

    let parts = value.split("/");
    if (format === "month") {
        if (parts.length !== 2) { return false; }
        let [mm, yyyy] = parts;
        let month = parseInt(mm, 10);
        if (!(/^\d{4}$/.test(yyyy)) || month < 1 || month > 12) { return false; }
        return `${yyyy}-${String(month).padStart(2, "0")}`;
    }

    if (parts.length !== 3) { return false; }
    let [dd, mm, yyyy] = parts;
    let day = parseInt(dd, 10);
    let month = parseInt(mm, 10);
    if (!(/^\d{4}$/.test(yyyy)) || month < 1 || month > 12 || day < 1 || day > 31) {
        return false;
    }
    let iso = `${yyyy}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    // Reject impossible calendar dates such as 31/02/2024.
    let check = new Date(`${iso}T00:00:00Z`);
    if (check.getUTCMonth() + 1 !== month || check.getUTCDate() !== day) { return false; }
    return iso;
}

function format_display_date (iso) {
    if (iso === null || iso === undefined || iso === "") { return ""; }
    let months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"];
    let parts = String(iso).split("-");
    let year = parts[0];
    if (parts.length < 2) { return year; }
    let month_name = months[parseInt(parts[1], 10) - 1] || parts[1];
    if (parts.length < 3) { return `${month_name} ${year}`; }
    return `${parseInt(parts[2], 10)} ${month_name} ${year}`;
}

function add_date (container_uuid) {
    let format  = jQuery("input[name='dateFormat']:checked").val();
    let raw_value  = get_new_date_value ();
    let type_value = or_null(jQuery("#dateType").val());

    if (raw_value === null) {
        show_message ("failure", "<p>Enter a date before adding it.</p>");
        return;
    }
    let iso_value = to_iso_date (format, raw_value);
    if (iso_value === false) {
        let hints = {
            "year":  "yyyy, for example 2024",
            "month": "mm/yyyy, for example 05/2024",
            "day":   "dd/mm/yyyy, for example 17/05/2024"
        };
        show_message ("failure", `<p>Enter the date as ${hints[format]}.</p>`);
        return;
    }
    if (type_value === null) {
        show_message ("failure", "<p>Select a date type before adding it.</p>");
        return;
    }

    let data = { "date": iso_value, "type": type_value };

    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/dates`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify([data]),
    }).done(function () {
        // Reset the entry fields and refresh the list below.
        jQuery("#date-year, #date-month, #date-day").val("");
        jQuery("#dateType").val("");
        render_dates (container_uuid);
    }).fail(function () {
        show_message ("failure", `<p>Failed to add date. Try again later.</p>`);
    });
}

function render_dates (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/dates`,
        data:        { "limit": 10000, "order": "created_date", "order_direction": "desc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (dates) {
        // Render the list of dates already added to the data.
        jQuery("#physical-sample-dates tbody").empty();

        // Sort by the date value chronologically.
        dates.sort (function (a, b) {
            if (a.date < b.date) { return 1; }
            if (a.date > b.date) { return -1; }
            return 0;
        });

        for (let date_entry of dates) {
            // Show dates with the month spelled e.g. "2010", "May 2010" or "17 May 2010".
            let display_date = format_display_date (date_entry.date);
            let row = `<tr><td>${display_date}</td>`;
            row += `<td><span class="resource-badge date-type">${date_entry.type}</span></td>`;
            row += `<td><a href="#" data-uuid="${date_entry.uuid}" `;
            row += `class="remove-date fas fa-trash-can" title="Remove"></a></td></tr>`;
            jQuery("#physical-sample-dates tbody").append(row);
        }
    }).fail(function() {
        show_message ("failure", "<p>Failed to retrieve dates.</p>");
    });
}

function remove_related_resource (resource_uuid, container_uuid) {
    jQuery.ajax({
        url:    `/v3/physical-samples/${container_uuid}/related-resources/${resource_uuid}`,
        type:   "DELETE",
        accept: "application/json",
    }).done(function () { render_related_resources (container_uuid); })
      .fail(function () { show_message ("failure", "<p>Failed to remove related resource.</p>"); });
}

function add_related_resource (container_uuid) {
    let identifier     = or_null(jQuery("#related-resource").val());
    let identifierType = or_null(jQuery("#identifierType").val());
    let relationType   = or_null(jQuery("#relationType").val());

    if (identifier === null) {
        show_message ("failure", "<p>Please fill in an identifier before adding a related resource.</p>");
        return;
    }
    if (identifierType === null) {
        show_message ("failure", "<p>Please select an identifier type before adding a related resource.</p>");
        return;
    }
    if (relationType === null) {
        show_message ("failure", "<p>Please select a relationship type before adding a related resource.</p>");
        return;
    }

    let data = {
        "identifier":      identifier,
        "identifier-type": identifierType,
        "relation-type":   relationType
    };
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/related-resources`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify([data]),
    }).done(function () {
        render_related_resources (container_uuid);
    }).fail(function () {
        show_message ("failure", "<p>Failed to add related resource. Try again later.</p>");
    });
}

function render_related_resources (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/related-resources`,
        data:        { "limit": 10000, "order": "created_date", "order_direction": "desc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (records) {
        jQuery("#related-resources tbody").empty();

        let row = '<tr><td><input type="text" name="identifier" id="related-resource" /></td>';
        row += '<td><select name="identifierType" id="identifierType">';
        row += '<option value="" disabled="disabled" selected="selected">Identifier type</option>';
        row += '<option value="IGSNDOI">IGSN</option>';
        row += '<option value="OtherDOI">DOI</option>';
        row += '<option value="URL">URL</option>';
        row += '</select></td>';
        row += '<td><select name="relationType" id="relationType">';
        row += '<option value="" disabled="disabled" selected="selected">Relationship type</option>';
        row += '<option value="IsPartOf">Is part of</option>';
        row += '<option value="HasPart">Has part</option>';
        row += '<option value="IsDerivedFrom">Is derived from</option>';
        row += '<option value="IsSourceOf">Is source of</option>';
        row += '<option value="IsReferencedBy">Is referenced by</option>';
        row += '<option value="References">References</option>';
        row += '<option value="IsCitedBy">Is cited by</option>';
        row += '<option value="Cites">Cites</option>';
        row += '<option value="IsDescribedBy">Is described by</option>';
        row += '<option value="Describes">Describes</option>';
        row += '</select></td>';
        row += '<td><a class="form-button corporate-identity-standard-button add-related-resource-button" href="#">Add</a></td></tr>';
        jQuery("#related-resources tbody").append(row);

        for (let resource of records) {
            let row = `<tr><td><span class="resource-identifier">${resource.url}</span></td>`;
            row += `<td><span class="resource-badge resource-type">${resource.type}</span></td>`;
            row += `<td><span class="resource-badge resource-relation">${resource.relation}</span></td>`;
            row += `<td><a href="#" data-uuid="${resource.uuid}" `;
            row += `class="remove-related-resource fas fa-trash-can" title="Remove"></a></td></tr>`;
            jQuery("#related-resources tbody").append(row);
        }
    }).fail(function() {
        show_message ("failure", "<p>Failed to retrieve related resources.</p>");
    });

}

function remove_tag_event (event) {
    stop_event_propagation (event);
    remove_tag (encodeURIComponent(event.data["tag"]), event.data["container_uuid"]);
}

function remove_tag (tag, container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/tags?tag=${tag}`,
        type:        "DELETE",
        accept:      "application/json",
    }).done(function () { render_tags (container_uuid); })
      .fail(function () { show_message ("failure", `<p>Failed to remove ${tag}.</p>`); });
}

function render_tags (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/tags`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (tags) {
        jQuery("#tags-list").empty();
        for (let tag of tags) {
            let row = jQuery("<li/>");
            let anchor = jQuery("<a/>", { "href": "#", "class": "fas fa-trash-can" });
            anchor.on("click", { "tag": tag, "container_uuid": container_uuid }, remove_tag_event);
            row.append(jQuery("<span/>").html(`${tag} &nbsp; `)).append(anchor);
            jQuery("#tags-list").append(row);
        }
        jQuery("#tags-list").show();
    }).fail(function () { show_message ("failure", "<p>Failed to retrieve tags.</p>"); });
}

function add_tag (container_uuid) {
    let tag = jQuery.trim(jQuery("#tag").val());
    if (tag == "") { return 0; }

    let tags = [];
    if (tag.indexOf(";") >= 0) {
        let items = tag.split(";");
        for (let item of items) {
            if (item != "") { tags.push(jQuery.trim(item)); }
        }
    } else {
        tags = [tag];
    }
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/tags`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "tags": tags }),
    }).done(function () {
        render_tags (container_uuid);
        jQuery("#tag").val("");
        autocomplete_tags(null, container_uuid);
    }).fail(function () { show_message ("failure", `<p>Failed to add ${tag}.</p>`); });
}

function render_categories_for_physical_sample (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-samples/${container_uuid}/categories`,
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


function preview_physical_sample (container_uuid, event) {
    stop_event_propagation (event);
    let current_date = new Date();
    let year  = current_date.getFullYear();
    let month = current_date.getMonth() + 1; // getMonth is zero-indexed.
    let day   = current_date.getDate() + 1;
    if (month < 10) { month = `0${month}`; }
    if (day < 10) { day = `0${day}`; }


        jQuery.ajax({
            accept:      "application/json",
            contentType: "application/json",
            data:        JSON.stringify({ "expires_date": `${year}-${month}-${day}` }),
            type:        "POST",
            url:         `/v3/physical-samples/${container_uuid}/private_links`
        }).done(function (data) {
            console.log("oi?")
            console.log("data", data)
            let preview_window = window.open(data["location"], '_blank');
            if (preview_window) { preview_window.focus(); }
            else {
                show_message ("failure",
                              "<p>Cannot open preview window because your " +
                              "browser disabled pop-ups.</p>");
            }
        }).fail(function (response, text_status, error_code) {
            console.log("oi2?")
            show_message ("failure",
                          `<p>Could not create a private link due to error ` +
                          `<code>${error_code}</code>.</p>`);
        });

}

function activate (container_uuid, callback=jQuery.noop) {
    new Quill('#abstract', { theme: '4tu' });
    new Quill('#methods', { theme: '4tu' });
    jQuery("#delete").on("click", function (event) { delete_physical_sample (container_uuid, event); });
    jQuery("#save").on("click", function (event)   { save_physical_sample (container_uuid, event); });
    jQuery("#save_bottom").on("click", function (event)   { save_physical_sample (container_uuid, event); });
    jQuery("#submit").on("click", function (event) { submit_physical_sample (container_uuid, event); });
    jQuery("#publish").on("click", function (event) { publish_physical_sample (container_uuid, event); });
    jQuery("#decline").on("click", function (event) { decline_physical_sample (container_uuid, event); });
    jQuery("#preview").on("click", function (event) { preview_physical_sample (container_uuid, event); });
    jQuery("#authors").on("input", function (event) {
        return autocomplete_author (event, container_uuid);
    });
    render_authors (container_uuid);
    render_related_resources (container_uuid);
    render_dates (container_uuid);
    jQuery("#related-resources").on("click", ".add-related-resource-button", function (event) {
        event.preventDefault();
        add_related_resource (container_uuid);
    });
    jQuery("#related-resources").on("click", ".remove-related-resource", function (event) {
        event.preventDefault();
        remove_related_resource (jQuery(this).data("uuid"), container_uuid);
    });
    jQuery("#physical-sample-dates-wrapper").on("change", "input[name='dateFormat']", function () {
        set_date_format (jQuery(this).val());
    });
    jQuery("#physical-sample-dates-wrapper").on("input", ".date-input", function () {
        auto_format_date (this, jQuery("input[name='dateFormat']:checked").val());
    });
    jQuery("#physical-sample-dates-wrapper").on("click", ".add-date-button", function (event) {
        event.preventDefault();
        add_date (container_uuid);
    });
    jQuery("#physical-sample-dates-wrapper").on("click", ".remove-date", function (event) {
        event.preventDefault();
        remove_date (jQuery(this).data("uuid"), container_uuid);
    });
    // Set the initial format date (Full date) once the static markup exists.
    set_date_format (jQuery("input[name='dateFormat']:checked").val());
    render_tags (container_uuid);
    render_categories_for_physical_sample (container_uuid);
    jQuery("#expand-categories-button").on("click", toggle_categories);
    jQuery("#add-keyword-button").on("click", function (event) {
        stop_event_propagation (event);
        add_tag (container_uuid);
    });
    jQuery("#tag").on("keypress", function (e) {
        if (e.which == 13) { add_tag (container_uuid); }
    });
    jQuery("#tag").on("input", function (event) {
        return autocomplete_tags (event, container_uuid);
    });
    callback();
}
