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
    let name  = jQuery(".reviewer-filter option:selected").text();
    jQuery('#overview-table tr').each(function(index, element) {
        let reviewer_element = jQuery(element).find(`td .reviewer-selector option:selected`);
        let status = jQuery(element).find(`td:nth-child(5)`).text();
        if (jQuery(element).find("th").length > 0) {} // Skip the header.
        else if (value == "all") { jQuery(element).show(); }
        else if (value == "unassigned" && reviewer_element.length > 0 && reviewer_element.val() == "") {
            jQuery(element).show();
        }
        else if (reviewer_element.length > 0 && reviewer_element.val().split(":").pop() == value) {
            jQuery(element).show();
        }
        else if (status == "accepted") {
            let reviewer = jQuery(element).find(`td:nth-child(9)`).text();
            let reviewer_name = reviewer.split("\n").map(function (item){ return item.trim(); }).join(" ").trim();
            if (reviewer_name == name) { jQuery(element).show(); }
            else { jQuery(element).hide(); }
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
