const review_assigned   = '<span class="fas fa-glasses" title="Assigned to reviewer"><span class="no-show">assigned</span></span>';
const review_approved   = '<span class="fas fa-check-double" title="Approved by reviewer"><span class="no-show">approved</span></span>';
const review_rejected   = '<span class="fas fa-times fa-lg" title="Declined by reviewer"><span class="no-show">declined</span></span>';
const review_unassigned = '<span class="fas fa-hourglass" title="Unassigned"><span class="no-show">unassigned</span></span>';
const review_modified   = '<span class="fas fa-circle-exclamation" title="Modified after seen by reviewer"><span class="no-show">Modified</span></span>';

function cleanup_name(name) {
    return name.split("\n").map(function (item){ return item.trim(); }).join(" ").trim();
}

function update_item_count () {
    jQuery("#table-count").text(`${jQuery("#overview-table tbody tr:visible").length} items`);
}

function clear_reviews_cache (event) {
    stop_event_propagation (event);
    jQuery.ajax({
        url:         "/v3/admin/reviews/clear-cache",
        type:        "GET",
        accept:      "application/json",
    }).done(function () { location.reload();
    }).fail(function () {
        show_message ("failure", "<p>Failed to clear the reviews cache.</p>");
    });
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
            let reviewer = jQuery(element).find(`td:nth-child(10)`).text();
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

function copy_to_clipboard_event (event) {
    review = event.data["review"];
    published_date = event.data["published_date"];
    version = event.data["version"];
    copy_row (review.uuid, review.dataset_uuid, review.dataset_title,
              version, review.submitter_first_name, review.submitter_last_name,
              review.submitter_email, review.group_name, review.request_date,
                          review.modified_date, published_date);
}

function render_overview_table () {
    jQuery("#overview-table tbody").empty();
    jQuery.ajax({
        url:         "/v3/reviews",
        type:        "GET",
        accept:      "application/json",
    }).done(function (reviews) {
        let published_date = null;
        let version = "new";
        let status = "";
        let reviewer_html = "";
        let title_html = "";
        let table_body = jQuery("#overview-table tbody");
        let copy_button = null;
        let row = null;
        for (review of reviews) {
            published_date = null;
            version = "new";
            reviewer_html = "";
            if (review.status == "approved") {
                status = review_approved;
                published_date = review.published_date;
                title_html = `<a href="/datasets/${review.container_uuid}/${review.dataset_version}">${review.dataset_title}</a>`;
            }
            else {
                title_html = `<a href="/review/goto-dataset/${review.dataset_uuid}">${review.dataset_title}</a>`;
                if (review.status == "assigned") { status = review_assigned; }
                else if (review.status == "rejected") { status = review_rejected; }
                else { status = review_unassigned; }
            }
            if (review.last_seen_by_reviewer != null &&
                review.status == "assigned" &&
                review.modified_date > review.last_seen_by_reviewer) {
                status += review_modified;
            }
            if (review.has_published_version) {
                if (review.status == "approved") { version = review.dataset_version; }
                else { version = "update"; }
            }
            copy_button = jQuery("<a/>", { "id": `copy-btn-${review.uuid}`,
                                           "class": "fas fa-copy" });
            copy_button.on("click", {
                "review": review,
                "version": version,
                "published_date": or_empty (published_date)
            }, copy_to_clipboard_event);
            if (review.status == "approved" || review.status == "rejected") {
                reviewer_html = `${review.reviewer_first_name} ${review.reviewer_last_name}`;
            } else {
                reviewer_html = '<select class="reviewer-selector"><option value="" hidden>Unassigned</option>';
                for (reviewer of reviewers) {
                    reviewer_html += `<option value="${review.dataset_uuid}:${reviewer.uuid}"`;
                    if (review.reviewer_email == reviewer.email) { reviewer_html += "selected"; }
                    reviewer_html += `>${reviewer.first_name} ${reviewer.last_name}</option>`;
                }
                reviewer_html += '</select>';
            }
            row = jQuery("<tr/>");
            if (published_date != null) { published_date = published_date.substring(0, 10); }
            row.append (jQuery ("<td/>").html (title_html))
                .append (jQuery ("<td/>").text (or_empty (version)))
                .append (jQuery ("<td/>").text (`${review.submitter_first_name} ${review.submitter_last_name}`))
                .append (jQuery ("<td/>").text (or_empty (review.submitter_email)))
                .append (jQuery ("<td/>").text (or_empty (review.group_name)))
                .append (jQuery ("<td/>").html (status))
                .append (jQuery ("<td/>").text (or_empty (review.request_date)))
                .append (jQuery ("<td/>").text (or_empty (review.modified_date)))
                .append (jQuery ("<td/>").text (or_empty (published_date)))
                .append (jQuery ("<td/>").html (reviewer_html))
                .append (jQuery ("<td/>").html (copy_button));
            table_body.append (row);
        }
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
                jQuery("#overview-h1").show();
                jQuery("#overview-table").show();
                jQuery("#reviews-loader").hide();
                update_item_count ();
                jQuery(".reviewer-selector").change(assign_reviewer);
                jQuery(".reviewer-filter").change(apply_filters);
                jQuery(".status-filter").change(apply_filters);
            }
        });
    }).fail(function (jqXHR, textStatus, errorThrown) {
        show_message ("failure", "<p>Failed to render the overview table.</p>");
    });
}

jQuery(document).ready(function (){
    render_overview_table ();
    jQuery("#remove-cache").on("click", function (event) {
        clear_reviews_cache (event);
    });
});
