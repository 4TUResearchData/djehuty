function cleanup_name(name) {
    return name.split("\n").map(function (item){ return item.trim(); }).join(" ").trim();
}

function update_item_count () {
    jQuery("#table-count").text(`${jQuery("#overview-table tbody tr:visible").length} items`);
}
function assign_reviewer (event) {
    let identifiers = this.value.split(":");
    let dataset_uuid = identifiers[0];
    let reviewer_uuid = identifiers[1];

    jQuery.ajax({
        url:         `/v3/datasets/${dataset_uuid}/assign-reviewer/${reviewer_uuid}`,
        type:        "PUT",
        accept:      "application/json"
    }).done(function (response) {
        jQuery(`#${dataset_uuid}_status .fa-hourglass`)
            .replaceWith('<span class="fas fa-glasses" title="Assigned to ' +
                         'reviewer"><span style="font-size:0pt">assigned</span>' +
                         '</span>');
    }).fail(function (response) {
        show_message ("failure", "<p>Failed to assign reviewer.</p>");
    });
}

function apply_filters (event) {
    jQuery('#overview-table tr').each(function(index, element) {
        jQuery(element).show();
    });
    filter_reviewer (event);
    filter_status (event);
    update_item_count ();
}

function filter_reviewer (event) {
    let value = jQuery(".reviewer-filter option:selected").val();
    let name  = cleanup_name(jQuery(".reviewer-filter option:selected").text());
    jQuery('#overview-table tr').each(function(index, element) {
        let reviewer_element = jQuery(element).find(`td .reviewer-selector option:selected`);
        let status = jQuery(element).find(`td:nth-child(6)`).text().trim();
        if (jQuery(element).find("th").length > 0) {} // Skip the header.
        else if (value == "all") {}
        else if (value == "unassigned" && reviewer_element.length > 0 && reviewer_element.val() == "") {}
        else if (reviewer_element.length > 0 && reviewer_element.val().split(":").pop() == value) {}
        else if (status == "approved") {
            let reviewer = jQuery(element).find(`td:nth-child(10)`).text()
            let reviewer_name = cleanup_name(reviewer);
            if (reviewer_name != name) { jQuery(element).hide(); }
        }
        else { jQuery(element).hide(); }
    });
}

function filter_status (event) {
    let value = jQuery(".status-filter option:selected").val();
    jQuery('#overview-table tr').each(function(index, element) {
        let status = jQuery(element).find(`td:nth-child(6)`).text().trim();
        if (jQuery(element).find("th").length > 0) {} // Skip the header.
        else if (value == "all" || value == status) {}
        else { jQuery(element).hide(); }
    });
}

function activate() {
    jQuery(document).ready(function (){
        jQuery("#overview-table").DataTable({
            paging: false,
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Search..."
            },
            columnDefs: [{ orderable: false, targets: 10 }],
            order: [[6, 'desc']],
            orderable: false,
            info: false,
            initComplete: function (settings, json) {
            }
        });

        jQuery(".reviewer-selector").change(assign_reviewer);
        jQuery(".reviewer-filter").change(apply_filters);
        jQuery(".status-filter").change(apply_filters);
        jQuery("#content-wrapper").show();
        update_item_count ();
    });
}

function copy_row (uuid, dataset_uuid, title, version, first_name, last_name,
                   email, group_name, request_date, modified_date, published_date) {
    let escaped_title = title.replaceAll ('"', '""');
    let text = `=HYPERLINK("${window.location.origin}/review/goto-dataset/${dataset_uuid}"; "${escaped_title}")\t${version}\t${first_name} ${last_name}\t${email}\t${group_name}\t\t${request_date}\t${modified_date}\t${published_date}\n`;
    navigator.clipboard.writeText(text);
    jQuery(`#copy-btn-${uuid}`)
        .removeClass("fa-copy")
        .addClass("fa-check-double");
    setTimeout(function() {
        jQuery(`#copy-btn-${uuid}`)
            .removeClass("fa-check-double")
            .addClass("fa-copy");
    }, 3000);
}
