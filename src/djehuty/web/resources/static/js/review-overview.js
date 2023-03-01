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

function filter_reviewer (event) {
    let value = jQuery(".reviewer-filter option:selected").val();
    jQuery('#overview-table tr').each(function(index, element) {
        if (jQuery(element).find("th").length > 0) {} // Skip the header.
        else if (value == "all") { jQuery(element).show(); }
        else if (value == "unassigned" && jQuery(element).find(`td .reviewer-selector option:selected`).val() == "") {
            jQuery(element).show();
        }
        else if (jQuery(element).find(`td .reviewer-selector option:selected`).val().split(":").pop() == value) {
            jQuery(element).show();
        }
        else {
            jQuery(element).hide();
        }
    });
}

function activate () {
    jQuery(".reviewer-selector").change(assign_reviewer);
    jQuery(".reviewer-filter").change(filter_reviewer);
}
