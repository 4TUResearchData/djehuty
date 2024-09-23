function delete_physical_object (container_uuid, event) {
    event.preventDefault();
    event.stopPropagation();
    if (confirm("Deleting this draft is unrecoverable. "+
                "Do you want to continue?")) {
        window.location.replace(`/my/physical-objects/${container_uuid}/delete`);
    }
}

function gather_form_data (container_uuid) {
    let form_data = {
        "title":                  or_null(jQuery("#title").val()),
        "abstract":               or_null(jQuery("#abstract .ql-editor").html()),
        "methods":                or_null(jQuery("#methods .ql-editor").html()),
        "publisher":              or_null(jQuery("#publisher").val()),
        "resource_type":          or_null(jQuery("#resource_type").val()),
        "subject":                or_null(jQuery("#subject").val()),
        "alternate_identifier":   or_null(jQuery("#alternate_identifier").val()),
        "related_identifier":     or_null(jQuery("#related_identifier").val()),
        "doi":                    or_null(jQuery("#doi").val()),
    };
    return form_data;
}

function save_physical_object (container_uuid, event, notify=true) {
    event.preventDefault();
    event.stopPropagation();

    let form_data = gather_form_data();
    jQuery.ajax({
        url:         `/v3/physical-objects/${container_uuid}`,
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        if (notify) {
            show_message ("success", "<p>Saved changes.</p>");
        }
    }).fail(function () {
        if (notify) {
            show_message ("failure", "<p>Failed to save draft. Please try again at a later time.</p>");
        }
    });
}

function cancel_edit_author (author_uuid, container_uuid) {
    jQuery("#author-inline-edit-form").remove();
    jQuery(`#edit-author-${author_uuid}`).attr("onclick",
      `javascript:edit_author('${author_uuid}', ` +
      `'${container_uuid}'); return false`)
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
        html += `<input type="text" id="edit_author_first_name" name="author_first_name" value="${or_empty (author.first_name)}">`;
        html += `<label for="author_last_name">Last name</label>`;
        html += `<input type="text" id="edit_author_last_name" name="author_last_name" value="${or_empty (author.last_name)}">`;
        html += `<label for="author_email">E-mail address</label>`;
        html += `<input type="text" id="edit_author_email" name="author_email" value="${or_empty (author.email)}">`;
        html += `<label for="author_orcid">ORCID</label>`;
        html += `<input type="text" id="edit_author_orcid" name="author_orcid" value="${or_empty (author.orcid)}">`;
        html += `<div id="update-author" class="a-button">`;
        html += `<a href="#" onclick="javascript:update_author(`;
        html += `'${author_uuid}', '${container_uuid}'); `;
        html += `return false;">Update author</a></div>`;
        html += `</td></tr>`;

        jQuery(`#author-${author_uuid}`).after(html);
        jQuery(`#edit-author-${author_uuid}`)
            .removeClass("fa-pen")
            .addClass("fa-times")
            .addClass("fa-lg")
            .attr("onclick",
              `javascript:cancel_edit_author('${author_uuid}', ` +
              `'${container_uuid}'); return false;`);
    });
}

function add_author (author_uuid, container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-objects/${container_uuid}/creators`,
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

function render_authors (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-objects/${container_uuid}/creators`,
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (authors) {
        jQuery("#authors-list tbody").empty();
        for (let author of authors) {
            let row = `<tr id="author-${author.uuid}"><td>${author.full_name}`;
            let orcid = null;
            if (author.orcid_id && author.orcid_id != "") {
                orcid = author.orcid_id;
            } else
            if (author.orcid && author.orcid != "") {
                orcid = author.orcid;
            }
            if (orcid !== null) {
                row += ` <a href="https://orcid.org/${orcid}" `;
                row += `target="_blank" rel="noopener noreferrer"><img `;
                row += `src="/static/images/orcid.svg" style="height: 15px" `;
                row += `alt="ORCID" title="ORCID profile (new window)" /></a>`;
            }
            if (author.is_editable) {
                row += `</td><td><a id="edit-author-${author.uuid}" href="#" onclick="javascript:edit_author('${author.uuid}', `;
                row += `'${container_uuid}'); return false" class="fas fa-pen" title="Edit"></a>`;
            } else {
                row += "</td><td>";
            }
            row += `</td><td><a href="#" onclick="javascript:remove_author('${author.uuid}', `;
            row += `'${container_uuid}'); return false;" class="fas fa-trash-can" `;
            row += `title="Remove"></a></td></tr>`;
            jQuery("#authors-list tbody").append(row);
        }
        jQuery("#authors-list").show();
    }).fail(function () {
        show_message ("failure", "<p>Failed to retrieve author details.</p>");
    });
}

function add_event (container_uuid) {
    let data = {
        "date": or_null(jQuery("#date").val()),
        "type": or_null(jQuery("#dateType").val())
    };

    jQuery.ajax({
        url:         `/v3/physical-objects/${container_uuid}/events`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify([data]),
    }).done(function () {
        render_events (container_uuid);
    }).fail(function () {
        show_message ("failure", `<p>Failed to add event. Try again later.</p>`);
    });
}

function render_events (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-objects/${container_uuid}/events`,
        data:        { "limit": 10000, "order": "created_date", "order_direction": "desc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (events) {
        jQuery("#physical-object-events tbody").empty();

        let row = '<tr><td><input type="date" name="date" id="date" /></td>';
        row += '<td><select name="dateType" id="dateType">';
        row += '<option value="" disabled="disabled" selected="selected">Event type</option>';
        row += '<option value="collected">Collected</option>';
        row += '<option value="destroyed">Destroyed</option>';
        row += '<option value="issued">Issued</option>';
        row += '<option value="other">Other</option>';
        row += '</select></td>';
        row += '<td><a id="add-event-button" class="fas fa-plus" href="#" ';
        row += 'title="Add event" onclick="javascript:';
        row += `add_event('${container_uuid}'); return false;"></a></td></tr>`;
        jQuery("#physical-object-events tbody").append(row);

        for (let event of events) {
            let row = `<tr><td>${event.date}</td><td>${event.type}</td><td></td></tr>`;
            jQuery("#physical-object-events tbody").append(row);
        }
    }).fail(function() {
        show_message ("failure", "<p>Failed to retrieve events.</p>");
    });
}

function add_related_identifier (container_uuid) {
    let data = {
        "identifier": or_null(jQuery("#related-identifier").val()),
        "identifier-type": or_null(jQuery("#identifierType").val()),
        "relation-type": or_null(jQuery("#relationType").val())
    };
    jQuery.ajax({
        url:         `/v3/physical-objects/${container_uuid}/related-identifiers`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify([data]),
    }).done(function () {
        render_related_identifiers (container_uuid);
    }).fail(function () {
        show_message ("failure", `<p>Failed to add event. Try again later.</p>`);
    });
}

function render_related_identifiers (container_uuid) {
    jQuery.ajax({
        url:         `/v3/physical-objects/${container_uuid}/related-identifiers`,
        data:        { "limit": 10000, "order": "created_date", "order_direction": "desc" },
        type:        "GET",
        accept:      "application/json",
    }).done(function (records) {
        jQuery("#related-identifiers tbody").empty();

        let row = '<tr><td><input type="text" name="identifier" id="related-identifier" /></td>';
        row += '<td><select name="identifierType" id="identifierType">';
        row += '<option value="" disabled="disabled" selected="selected">Identifier type</option>';
        row += '<option value="IGSNDOI">IGSN DOI</option>';
        row += '<option value="OtherDOI">Other DOI</option>';
        row += '<option value="URL">URL</option>';
        row += '</select></td>';
        row += '<td><select name="relationType" id="relationType">';
        row += '<option value="" disabled="disabled" selected="selected">Relationship type</option>';
        row += '<option value="IsPartOf">Is part of</option>';
        row += '<option value="IsDerivedFrom">Is derived from</option>';
        row += '<option value="HasPart">Has part</option>';
        row += '<option value="IsSourceOf">Is source of</option>';
        row += '</select></td>';
        row += '<td><a id="add-event-button" class="fas fa-plus" href="#" ';
        row += 'title="Add event" onclick="javascript:';
        row += `add_related_identifier('${container_uuid}'); return false;"></a></td></tr>`;
        jQuery("#related-identifiers tbody").append(row);

        for (let identifier of records) {
            let row = `<tr><td>${identifier.url}</td><td>${identifier.type}</td><td>${identifier.relation}</td><td></td></tr>`;
            jQuery("#related-identifiers tbody").append(row);
        }
    }).fail(function() {
        show_message ("failure", "<p>Failed to retrieve events.</p>");
    });

}

function activate (container_uuid, callback=jQuery.noop) {
    new Quill('#abstract', { theme: '4tu' });
    new Quill('#methods', { theme: '4tu' });
    jQuery("#delete").on("click", function (event) { delete_physical_object (container_uuid, event); });
    jQuery("#save").on("click", function (event)   { save_physical_object (container_uuid, event); });
    jQuery("#authors").on("input", function (event) {
        return autocomplete_author (event, container_uuid);
    });
    render_authors (container_uuid);
    render_related_identifiers (container_uuid);
    render_events (container_uuid);
    callback();
}
