function assign_reviewer (event) {

    let event_local = this;
    let identifiers = this.value.split(":");
    let dataset_uuid = identifiers[0];
    let reviewer_uuid = identifiers[1];

    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/assign-reviewer/${reviewer_uuid}`,
        type:        "PUT",
        accept:      "application/json"
    }).fail(function (response) {
        show_message ("failure", "<p>Failed to assign reviewer.</p>");
    });
}

function activate () {
    jQuery(".reviewer-selector").change(assign_reviewer);
}
