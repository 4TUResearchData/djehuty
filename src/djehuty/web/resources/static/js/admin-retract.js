jQuery(document).ready(function () {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");

    var selected_dataset = null;
    var versions         = [];
    var plan             = null;

    function show_step (step) {
        jQuery("#retract-step-1, #retract-step-2, #retract-step-3").addClass("retract-hidden");
        jQuery("#retract-step-" + step).removeClass("retract-hidden");
        jQuery("#retract-steps-indicator span").removeClass("active");
        jQuery("#retract-step-indicator-" + step).addClass("active");
    }

    function selected_uuids () {
        return jQuery("#retract-versions-body input:checked").map(function () {
            return jQuery(this).val();
        }).get();
    }

    function plan_lines (plan) {
        var lines = [];
        lines.push("Remove " + plan.retracted.map(function (n) { return "v" + n; }).join(", ") +
                   " from the public record (their public pages will show " +
                   "<em>\"CONTENT WAS REMOVED\"</em>). Version numbers are not reused.");
        lines.push("Delete the Review records of those versions (if any).");
        if (plan.draft_version !== null) {
            lines.push("<strong>v" + plan.draft_version + " (latest)</strong> becomes a draft " +
                       "the owner can edit again.");
        }
        if (plan.new_latest !== null) {
            lines.push("<strong>v" + plan.new_latest + "</strong> stays public as the " +
                       "latest published version.");
        } else {
            lines.push("No published versions remain, so first_online_date is cleared as well.");
        }
        return lines;
    }

    function refresh_selection () {
        var button = jQuery("#retract-preview-button");
        jQuery("#retract-selection-error").addClass("retract-hidden");
        if (selected_uuids ().length === 0) {
            button.addClass("disabled");
        } else {
            button.removeClass("disabled");
        }
    }

    function render_versions (rows) {
        var body = jQuery("#retract-versions-body").empty();
        jQuery("#retract-select-all").prop("checked", false);
        for (var i = 0; i < rows.length; i++) {
            var v = rows[i];
            body.append(jQuery("<tr>")
                .append(jQuery("<td>").append(
                    jQuery("<input type='checkbox'>").val(v.dataset_uuid)))
                .append(jQuery("<td>").text(v.version))
                .append(jQuery("<td>").text(v.posted_date || "-"))
                .append(jQuery("<td>").text(v.doi || "-"))
                .append(jQuery("<td>").text(v.is_latest ? "latest" : "")));
        }
        refresh_selection ();
    }

    function load_versions (dataset) {
        versions = [];
        render_versions (versions);
        jQuery.ajax({
            url:  "/admin/update-published-dataset/remove-files/versions",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ container_uuid: dataset.container_uuid })
        }).done(function (data) {
            versions = (typeof data === "string") ? JSON.parse(data) : data;
            versions.sort(function (a, b) { return a.version - b.version; });
            render_versions (versions);
        }).fail(function () {
            show_message ("failure", "<p>Could not load the versions.</p>");
        });
    }

    function populate_step_2 (d) {
        jQuery("#retract-detail-title").text(d.title || "-");
        jQuery("#retract-detail-doi").text(d.container_doi || "-");
        jQuery("#retract-detail-container-uuid").text(d.container_uuid || "-");
        load_versions (d);
    }

    function populate_step_3 (d, plan) {
        var lines = plan_lines (plan);

        jQuery("#retract-confirm-title").text(d.title || "-");
        jQuery("#retract-confirm-doi").text(d.container_doi || "-");
        jQuery("#retract-confirm-versions").text(plan.retracted.map(function (n) { return "v" + n; }).join(", "));
        jQuery("#retract-summary-list").empty();
        for (var i = 0; i < lines.length; i++) {
            jQuery("#retract-summary-list").append(jQuery("<li>").html(lines[i]));
        }
        jQuery("#retract-expected-doi-hint").text(d.container_doi || "");
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
            url:  "/admin/update-published-dataset/search",
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
                    .append(jQuery("<td>").text(d.container_doi || "-"))
                    .append(jQuery("<td>").text(d.version_count || "-"))
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

    jQuery("#retract-versions-body").on("change", "input", refresh_selection);
    jQuery("#retract-select-all").on("change", function () {
        jQuery("#retract-versions-body input").prop("checked", jQuery(this).prop("checked"));
        refresh_selection ();
    });

    jQuery("#retract-back-to-search-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (1);
    });

    jQuery("#retract-preview-button").on("click", function (event) {
        stop_event_propagation (event);
        if (!selected_dataset || jQuery(this).hasClass("disabled")) { return; }
        jQuery.ajax({
            url:  "/admin/update-published-dataset/retract/preview",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                container_uuid: selected_dataset.container_uuid,
                version_uuids:  selected_uuids ()
            })
        }).done(function (data) {
            plan = (typeof data === "string") ? JSON.parse(data) : data;
            populate_step_3 (selected_dataset, plan);
            show_step (3);
        }).fail(function (xhr) {
            var msg = "Could not preview the retraction.";
            if (xhr && xhr.responseJSON && xhr.responseJSON.message) {
                msg = xhr.responseJSON.message;
            }
            jQuery("#retract-selection-error").text(msg).removeClass("retract-hidden");
        });
    });

    jQuery("#retract-back-to-detail-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (2);
    });

    jQuery("#retract-doi-confirm-input").on("input", function () {
        if (!selected_dataset) { return; }
        var typed    = jQuery(this).val().trim();
        var expected = (selected_dataset.container_doi || "").trim();
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

        var typed         = jQuery("#retract-doi-confirm-input").val().trim();
        var uuids         = selected_uuids ();
        var retract_count = uuids.length;
        var has_draft     = plan.draft_version !== null;

        jQuery.ajax({
            url:  "/admin/update-published-dataset/retract/execute",
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify({
                container_uuid:     selected_dataset.container_uuid,
                version_uuids:      uuids,
                owner_account_uuid: selected_dataset.account_uuid,
                confirm_doi:        typed,
                expected_doi:       selected_dataset.container_doi
            })
        }).done(function (data) {
            var message = "<p>Retracted " + retract_count + " version(s).";
            if (has_draft) {
                message += " The owner now has an editable draft.";
            }
            message += "</p>";
            var warnings = (data && data.warnings) || [];
            if (warnings.length > 0) {
                message += "<p>DataCite was not fully updated:</p><ul><li>" +
                           warnings.join ("</li><li>") + "</li></ul>";
            }
            show_message (warnings.length > 0 ? "failure" : "success", message);
            jQuery("#retract-results-body").empty();
            jQuery("#retract-results").addClass("retract-hidden");
            jQuery("#retract-search-input").val("");
            selected_dataset = null;
            versions         = [];
            plan             = null;
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
