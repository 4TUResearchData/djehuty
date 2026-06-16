jQuery(document).ready(function () {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");

    var selected_dataset = null;

    function show_step (step) {
        jQuery("#retract-step-1, #retract-step-2, #retract-step-3").addClass("retract-hidden");
        jQuery("#retract-step-" + step).removeClass("retract-hidden");
        jQuery("#retract-steps-indicator span").removeClass("active");
        jQuery("#retract-step-indicator-" + step).addClass("active");
    }

    function populate_step_2 (d) {
        jQuery("#retract-detail-title").text(d.title || "-");
        jQuery("#retract-detail-doi").text(d.doi || "-");
        jQuery("#retract-detail-version").text(d.version || "-");
        jQuery("#retract-detail-published").text(d.published_date || "-");
        jQuery("#retract-detail-container-uuid").text(d.container_uuid || "-");
        jQuery("#retract-detail-dataset-uuid").text(d.uuid || "-");
    }

    function populate_step_3 (d) {
        jQuery("#retract-confirm-title").text(d.title || "-");
        jQuery("#retract-confirm-doi").text(d.doi || "-");
        jQuery("#retract-confirm-version").text(d.version || "-");
        jQuery("#retract-expected-doi-hint").text(d.doi || "");
        jQuery("#retract-doi-confirm-input").val("");
        jQuery("#retract-confirm-button").addClass("disabled");
    }

    jQuery("#retract-search-button").on("click", function (event) {
        stop_event_propagation (event);
        var search_for = jQuery("#retract-search-input").val().trim();
        if (search_for === "") { return; }

        jQuery("#retract-results-body").empty();
        jQuery("#retract-results").addClass("retract-hidden");

        jQuery.ajax({
            url:  "/admin/update-published-dataset/retract/search",
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
                    .append(jQuery("<td>").text(d.published_date || "-"));
                jQuery("#retract-results-body").append(row);
            }
            jQuery("#retract-results").removeClass("retract-hidden");
        }).fail(function () {
            show_message ("failure", "<p>Search failed.</p>");
        });
    });

    jQuery("#retract-search-input").on("keypress", function (event) {
        if (event.which === 13) {
            stop_event_propagation (event);
            jQuery("#retract-search-button").click();
        }
    });

    jQuery("#retract-results-body").on("click", "tr", function () {
        selected_dataset = jQuery(this).data("dataset");
        jQuery("#retract-results-body tr").removeClass("selected-row");
        jQuery(this).addClass("selected-row");
        populate_step_2 (selected_dataset);
        show_step (2);
    });

    jQuery("#retract-back-to-search-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (1);
    });

    jQuery("#retract-preview-button").on("click", function (event) {
        stop_event_propagation (event);
        if (!selected_dataset) { return; }
        populate_step_3 (selected_dataset);
        show_step (3);
    });

    jQuery("#retract-back-to-detail-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (2);
    });

    jQuery("#retract-doi-confirm-input").on("input", function () {
        if (!selected_dataset) { return; }
        var typed    = jQuery(this).val().trim();
        var expected = (selected_dataset.doi || "").trim();
        if (typed && typed === expected) {
            jQuery("#retract-confirm-button").removeClass("disabled");
        } else {
            jQuery("#retract-confirm-button").addClass("disabled");
        }
    });

    jQuery("#retract-confirm-button").on("click", function (event) {
        stop_event_propagation (event);
        if (jQuery(this).hasClass("disabled")) { return; }
        if (!selected_dataset) { return; }

        var typed = jQuery("#retract-doi-confirm-input").val().trim();

        jQuery.ajax({
            url:  "/admin/update-published-dataset/retract/execute",
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify({
                container_uuid:     selected_dataset.container_uuid,
                dataset_uuid:       selected_dataset.uuid,
                owner_account_uuid: selected_dataset.account_uuid,
                confirm_doi:        typed,
                expected_doi:       selected_dataset.doi
            })
        }).done(function () {
            show_message ("success",
                "<p>Dataset retracted. The owner now has an editable draft.</p>");
            jQuery("#retract-results-body").empty();
            jQuery("#retract-results").addClass("retract-hidden");
            jQuery("#retract-search-input").val("");
            selected_dataset = null;
            show_step (1);
        }).fail(function (xhr) {
            var msg = "Retraction failed.";
            if (xhr && xhr.responseJSON && xhr.responseJSON.message) {
                msg = xhr.responseJSON.message;
            }
            show_message ("failure", "<p>" + msg + "</p>");
        });
    });
});
