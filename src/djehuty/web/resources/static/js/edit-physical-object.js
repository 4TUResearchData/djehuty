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
        "description":            or_null(jQuery("#description .ql-editor").html()),
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

function activate (container_uuid, callback=jQuery.noop) {
    new Quill('#description', { theme: '4tu' });
    jQuery("#delete").on("click", function (event) { delete_physical_object (container_uuid, event); });
    jQuery("#save").on("click", function (event)   { save_physical_object (container_uuid, event); });
    callback();
}
