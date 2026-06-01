jQuery(document).ready(function () {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");

    var selected_dataset = null;
    var pending_license_url = null;
    var pending_license_name = null;

    function show_step (step) {
        jQuery("#license-step-1, #license-step-2, #license-step-3").addClass("license-hidden");
        jQuery("#license-step-" + step).removeClass("license-hidden");
        jQuery("#license-steps-indicator span").removeClass("active");
        jQuery("#license-step-indicator-" + step).addClass("active");
    }

    function populate_step_2 (d) {
        jQuery("#license-detail-title").text(d.title || "-");
        jQuery("#license-detail-doi").text(d.doi || "-");
        jQuery("#license-detail-version").text(d.version || "-");
        jQuery("#license-detail-current-name").text(d.license_name || "Not set");
        jQuery("#license-detail-current-url").text(d.license_url || "-");
        jQuery("#license-detail-container-uri").text(d.container_uri || "-");
        jQuery("#license-detail-dataset-uri").text(d.uri || "-");
        // Pre-select current license in the dropdown if it matches.
        if (d.license_url) {
            jQuery("#license-select").val(d.license_url);
        } else {
            jQuery("#license-select").val("");
        }
    }

    function populate_step_3 (d, new_url, new_name) {
        jQuery("#license-confirm-title").text(d.title || "-");
        jQuery("#license-confirm-doi").text(d.doi || "-");
        jQuery("#license-confirm-version").text(d.version || "-");
        jQuery("#license-confirm-from-name").text(d.license_name || "Not set");
        jQuery("#license-confirm-from-url").text(d.license_url || "");
        jQuery("#license-confirm-to-name").text(new_name);
        jQuery("#license-confirm-to-url").text(new_url);
    }

    jQuery("#license-search-button").on("click", function (event) {
        stop_event_propagation (event);
        var search_for = jQuery("#license-search-input").val().trim();
        if (search_for === "") { return; }

        jQuery("#license-results-body").empty();
        jQuery("#license-results").addClass("license-hidden");

        jQuery.ajax({
            url:  "/admin/update-published-dataset/license/search",
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
                    .append(jQuery("<td>").text(d.version || "-"))
                    .append(jQuery("<td>").text(d.license_name || "Not set"));
                jQuery("#license-results-body").append(row);
            }
            jQuery("#license-results").removeClass("license-hidden");
        }).fail(function () {
            show_message ("failure", "<p>Search failed.</p>");
        });
    });

    jQuery("#license-search-input").on("keypress", function (event) {
        if (event.which === 13) {
            stop_event_propagation (event);
            jQuery("#license-search-button").click();
        }
    });

    jQuery("#license-results-body").on("click", "tr", function () {
        selected_dataset = jQuery(this).data("dataset");
        jQuery("#license-results-body tr").removeClass("selected-row");
        jQuery(this).addClass("selected-row");
        populate_step_2 (selected_dataset);
        show_step (2);
    });

    jQuery("#license-back-to-search-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (1);
    });

    jQuery("#license-preview-button").on("click", function (event) {
        stop_event_propagation (event);
        if (!selected_dataset) { return; }
        var url = jQuery("#license-select").val();
        if (!url) {
            show_message ("failure", "<p>Please pick a license.</p>");
            return;
        }
        if (url === selected_dataset.license_url) {
            show_message ("failure",
                "<p>That is already the current license. Pick a different one.</p>");
            return;
        }
        var name = jQuery("#license-select option:selected").data("name") || url;
        pending_license_url  = url;
        pending_license_name = name;
        populate_step_3 (selected_dataset, pending_license_url, pending_license_name);
        show_step (3);
    });

    jQuery("#license-back-to-pick-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (2);
    });

    jQuery("#license-confirm-button").on("click", function (event) {
        stop_event_propagation (event);
        if (!selected_dataset || !pending_license_url) { return; }

        jQuery.ajax({
            url:  "/admin/update-published-dataset/license/update",
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify({
                container_uri:      selected_dataset.container_uri,
                dataset_uri:        selected_dataset.uri,
                owner_account_uuid: selected_dataset.account_uuid,
                new_license_url:    pending_license_url
            })
        }).done(function () {
            show_message ("success",
                "<p>License changed to <strong>" + pending_license_name + "</strong>.</p>");
            selected_dataset.license_url  = pending_license_url;
            selected_dataset.license_name = pending_license_name;
            var selected = jQuery("#license-results-body tr.selected-row");
            selected.find("td:eq(3)").text(pending_license_name);
            selected.data("dataset").license_url  = pending_license_url;
            selected.data("dataset").license_name = pending_license_name;
            populate_step_2 (selected_dataset);
            show_step (1);
        }).fail(function (xhr) {
            var msg = "License change failed.";
            if (xhr && xhr.responseJSON && xhr.responseJSON.message) {
                msg = xhr.responseJSON.message;
            }
            show_message ("failure", "<p>" + msg + "</p>");
        });
    });
});
