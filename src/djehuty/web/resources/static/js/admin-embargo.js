jQuery(document).ready(function () {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");

    var selected_dataset = null;
    var pending_new_date = null;

    function show_step (step) {
        jQuery("#embargo-step-1, #embargo-step-2, #embargo-step-3").addClass("embargo-hidden");
        jQuery("#embargo-step-" + step).removeClass("embargo-hidden");
        jQuery("#embargo-steps-indicator span").removeClass("active");
        jQuery("#step-indicator-" + step).addClass("active");
    }

    function populate_step_2 (d) {
        jQuery("#detail-title").text(d.title || "-");
        jQuery("#detail-doi").text(d.doi || "-");
        jQuery("#detail-embargo-type").text(d.embargo_type || "-");
        jQuery("#detail-embargo-title").text(d.embargo_title || "-");
        jQuery("#detail-embargo-reason").text(d.embargo_reason || "-");
        jQuery("#detail-embargo-date").text(d.embargo_until_date || "Not set");
        jQuery("#embargo-date-input").val(d.embargo_until_date || "");
    }

    function populate_step_3 (d, new_date) {
        jQuery("#confirm-title").text(d.title || "-");
        jQuery("#confirm-doi").text(d.doi || "-");
        jQuery("#confirm-embargo-type").text(d.embargo_type || "-");
        jQuery("#confirm-from-date").text(d.embargo_until_date || "Not set");
        jQuery("#confirm-to-date").text(new_date);
    }

    jQuery("#embargo-search-button").on("click", function (event) {
        stop_event_propagation (event);
        var search_for = jQuery("#embargo-search-input").val().trim();
        if (search_for === "") { return; }

        jQuery("#embargo-results-body").empty();
        jQuery("#embargo-results").addClass("embargo-hidden");

        jQuery.ajax({
            url:  "/admin/update-published-dataset/embargos/search",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ search_for: search_for })
        }).done(function (data) {
            var datasets = (typeof data === "string") ? JSON.parse(data) : data;
            if (datasets.length === 0) {
                show_message ("failure", "<p>No datasets found.</p>");
                return;
            }
            for (var i = 0; i < datasets.length; i++) {
                var d = datasets[i];
                var row = jQuery("<tr>")
                    .data("dataset", d)
                    .append(jQuery("<td>").text(d.title || "-"))
                    .append(jQuery("<td>").text(d.doi || "-"))
                    .append(jQuery("<td>").text(d.embargo_until_date || "-"))
                    .append(jQuery("<td>").text(d.embargo_type || "-"));
                jQuery("#embargo-results-body").append(row);
            }
            jQuery("#embargo-results").removeClass("embargo-hidden");
        }).fail(function () {
            show_message ("failure", "<p>Search failed.</p>");
        });
    });

    jQuery("#embargo-search-input").on("keypress", function (event) {
        if (event.which === 13) {
            stop_event_propagation (event);
            jQuery("#embargo-search-button").click();
        }
    });

    jQuery("#embargo-results-body").on("click", "tr", function () {
        selected_dataset = jQuery(this).data("dataset");
        jQuery("#embargo-results-body tr").removeClass("selected-row");
        jQuery(this).addClass("selected-row");
        populate_step_2 (selected_dataset);
        show_step (2);
    });

    jQuery("#embargo-back-to-search-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (1);
    });

    jQuery("#embargo-preview-button").on("click", function (event) {
        stop_event_propagation (event);
        var new_date = jQuery("#embargo-date-input").val();
        if (!new_date) {
            show_message ("failure", "<p>Please select a date.</p>");
            return;
        }
        pending_new_date = new_date;
        populate_step_3 (selected_dataset, pending_new_date);
        show_step (3);
    });

    jQuery("#embargo-back-to-edit-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (2);
    });

    jQuery("#embargo-confirm-button").on("click", function (event) {
        stop_event_propagation (event);
        if (!selected_dataset || !pending_new_date) { return; }

        jQuery.ajax({
            url:  "/admin/update-published-dataset/embargos/update",
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify({
                dataset_uuid: selected_dataset.uuid,
                embargo_until_date: pending_new_date
            })
        }).done(function () {
            show_message ("success", "<p>Embargo date updated to " + pending_new_date + ".</p>");
            selected_dataset.embargo_until_date = pending_new_date;
            var selected = jQuery("#embargo-results-body tr.selected-row");
            selected.find("td:eq(2)").text(pending_new_date);
            selected.data("dataset").embargo_until_date = pending_new_date;
            populate_step_2 (selected_dataset);
            show_step (1);
        }).fail(function () {
            show_message ("failure", "<p>Failed to update embargo date.</p>");
        });
    });
});
