jQuery(document).ready(function () {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");

    var selected_dataset = null;   // container-level record from the search step
    var selected_version = null;   // version record from the versions step
    var version_files    = [];     // files of the selected version

    function show_step (step) {
        jQuery("#rmf-step-1, #rmf-step-2, #rmf-step-3, #rmf-step-4").addClass("rmf-hidden");
        jQuery("#rmf-step-" + step).removeClass("rmf-hidden");
        jQuery("#rmf-steps-indicator span").removeClass("active");
        jQuery("#rmf-step-indicator-" + step).addClass("active");
    }

    function human_size (bytes) {
        if (bytes === null || bytes === undefined || isNaN(bytes)) { return "-"; }
        var units = ["bytes", "KB", "MB", "GB", "TB"];
        var value = Number(bytes);
        var unit  = 0;
        while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
        var rounded = (unit === 0) ? value : value.toFixed(1);
        return rounded + " " + units[unit];
    }

    function selected_file_uuids () {
        var uuids = [];
        jQuery("#rmf-files-body input.rmf-file-checkbox:checked").each(function () {
            uuids.push(jQuery(this).val());
        });
        return uuids;
    }

    function update_continue_state () {
        if (selected_file_uuids().length > 0) {
            jQuery("#rmf-continue-button").removeClass("disabled");
        } else {
            jQuery("#rmf-continue-button").addClass("disabled");
        }
    }

    /* Step 1 — search & select dataset. */
    jQuery("#rmf-search-button").on("click", function (event) {
        stop_event_propagation (event);
        var search_for = jQuery("#rmf-search-input").val().trim();
        if (search_for === "") { return; }

        jQuery("#rmf-results-body").empty();
        jQuery("#rmf-results").addClass("rmf-hidden");

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
                    .append(jQuery("<td>").text(d.doi || "-"))
                    .append(jQuery("<td>").text(d.version || "-"))
                    .append(jQuery("<td>").text(d.version_count || "-"));
                jQuery("#rmf-results-body").append(row);
            }
            jQuery("#rmf-results").removeClass("rmf-hidden");
        }).fail(function () {
            show_message ("failure", "<p>Search failed.</p>");
        });
    });

    jQuery("#rmf-search-input").on("keypress", function (event) {
        if (event.which === 13) {
            stop_event_propagation (event);
            jQuery("#rmf-search-button").click();
        }
    });

    jQuery("#rmf-results-body").on("click", "tr", function () {
        selected_dataset = jQuery(this).data("dataset");
        selected_version = null;
        jQuery("#rmf-results-body tr").removeClass("selected-row");
        jQuery(this).addClass("selected-row");
        jQuery("#rmf-dataset-title").text(selected_dataset.title || "-");
        load_versions();
    });

    /* Step 2 — list versions. */
    function load_versions () {
        jQuery("#rmf-versions-body").empty();
        jQuery.ajax({
            url:  "/admin/update-published-dataset/remove-files/versions",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ container_uuid: selected_dataset.container_uuid })
        }).done(function (data) {
            var versions = (typeof data === "string") ? JSON.parse(data) : data;
            for (var i = 0; i < versions.length; i++) {
                var v = versions[i];
                var version_cell = jQuery("<td>").text("v" + (v.version || "-"));
                if (v.is_latest) {
                    version_cell.append(jQuery("<span>").addClass("rmf-latest-badge").text("latest"));
                }
                var row = jQuery("<tr>")
                    .data("version", v)
                    .append(version_cell)
                    .append(jQuery("<td>").text(v.doi || "-"))
                    .append(jQuery("<td>").text(v.posted_date || "-"))
                    .append(jQuery("<td>").text(v.file_count));
                jQuery("#rmf-versions-body").append(row);
            }
            show_step (2);
        }).fail(function () {
            show_message ("failure", "<p>Could not load versions.</p>");
        });
    }

    jQuery("#rmf-versions-body").on("click", "tr", function () {
        selected_version = jQuery(this).data("version");
        jQuery("#rmf-versions-body tr").removeClass("selected-row");
        jQuery(this).addClass("selected-row");
        load_files();
    });

    jQuery("#rmf-back-to-search-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (1);
    });

    /* Step 3 — list & select files. */
    function load_files () {
        jQuery("#rmf-files-body").empty();
        jQuery("#rmf-select-all").prop("checked", false);
        jQuery("#rmf-continue-button").addClass("disabled");
        jQuery("#rmf-files-version").text("v" + (selected_version.version || "-"));
        jQuery("#rmf-files-doi").text(selected_version.doi || "-");

        jQuery.ajax({
            url:  "/admin/update-published-dataset/remove-files/files",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                container_uuid: selected_dataset.container_uuid,
                dataset_uuid:   selected_version.dataset_uuid
            })
        }).done(function (data) {
            version_files = (typeof data === "string") ? JSON.parse(data) : data;
            if (version_files.length === 0) {
                show_message ("failure", "<p>This version has no files.</p>");
                return;
            }
            for (var i = 0; i < version_files.length; i++) {
                var f = version_files[i];
                var checkbox = jQuery("<input>")
                    .attr("type", "checkbox")
                    .addClass("rmf-file-checkbox")
                    .val(f.uuid);
                var shared_text = "-";
                if (f.also_in_versions && f.also_in_versions.length > 0) {
                    shared_text = "also in v" + f.also_in_versions.join(", v");
                }
                var shared_cell = jQuery("<td>").text(shared_text);
                if (f.also_in_versions && f.also_in_versions.length > 0) {
                    shared_cell.addClass("rmf-shared");
                }
                var row = jQuery("<tr>")
                    .append(jQuery("<td>").append(checkbox))
                    .append(jQuery("<td>").text(f.name || "-"))
                    .append(jQuery("<td>").text(human_size(f.size)))
                    .append(shared_cell);
                jQuery("#rmf-files-body").append(row);
            }
            show_step (3);
        }).fail(function () {
            show_message ("failure", "<p>Could not load files.</p>");
        });
    }

    jQuery("#rmf-select-all").on("change", function () {
        jQuery("#rmf-files-body input.rmf-file-checkbox").prop("checked", jQuery(this).is(":checked"));
        update_continue_state();
    });

    jQuery("#rmf-files-body").on("change", "input.rmf-file-checkbox", function () {
        var all = jQuery("#rmf-files-body input.rmf-file-checkbox").length;
        var checked = jQuery("#rmf-files-body input.rmf-file-checkbox:checked").length;
        jQuery("#rmf-select-all").prop("checked", all > 0 && all === checked);
        update_continue_state();
    });

    jQuery("#rmf-back-to-versions-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (2);
    });

    /* Step 4 — review & confirm. */
    jQuery("#rmf-continue-button").on("click", function (event) {
        stop_event_propagation (event);
        if (jQuery(this).hasClass("disabled")) { return; }
        var uuids = selected_file_uuids();
        if (uuids.length === 0) { return; }

        jQuery("#rmf-confirm-title").text(selected_version.title || "-");
        jQuery("#rmf-confirm-version").text("v" + (selected_version.version || "-"));
        jQuery("#rmf-confirm-doi").text(selected_version.doi || "-");
        jQuery("#rmf-expected-doi-hint").text(selected_version.doi || "");
        jQuery("#rmf-doi-confirm-input").val("");
        jQuery("#rmf-confirm-button").addClass("disabled");

        if (selected_version.is_latest) {
            jQuery("#rmf-latest-warning").removeClass("rmf-hidden");
        } else {
            jQuery("#rmf-latest-warning").addClass("rmf-hidden");
        }

        jQuery("#rmf-confirm-file-list").empty();
        for (var i = 0; i < version_files.length; i++) {
            var f = version_files[i];
            if (uuids.indexOf(f.uuid) === -1) { continue; }
            var label = f.name || f.uuid;
            if (f.also_in_versions && f.also_in_versions.length > 0) {
                label += " (also in v" + f.also_in_versions.join(", v") + ")";
            }
            jQuery("#rmf-confirm-file-list").append(jQuery("<li>").text(label));
        }
        show_step (4);
    });

    jQuery("#rmf-back-to-files-button").on("click", function (event) {
        stop_event_propagation (event);
        show_step (3);
    });

    jQuery("#rmf-doi-confirm-input").on("input", function () {
        if (!selected_version) { return; }
        var typed    = jQuery(this).val().trim();
        var expected = (selected_version.doi || "").trim();
        if (typed && typed === expected) {
            jQuery("#rmf-confirm-button").removeClass("disabled");
        } else {
            jQuery("#rmf-confirm-button").addClass("disabled");
        }
    });

    jQuery("#rmf-confirm-button").on("click", function (event) {
        stop_event_propagation (event);
        if (jQuery(this).hasClass("disabled")) { return; }
        if (!selected_dataset || !selected_version) { return; }

        var uuids = selected_file_uuids();
        if (uuids.length === 0) { return; }

        jQuery.ajax({
            url:  "/admin/update-published-dataset/remove-files/execute",
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify({
                container_uuid:     selected_dataset.container_uuid,
                dataset_uuid:       selected_version.dataset_uuid,
                owner_account_uuid: selected_version.account_uuid,
                file_uuids:         uuids,
                confirm_doi:        jQuery("#rmf-doi-confirm-input").val().trim(),
                expected_doi:       selected_version.doi
            })
        }).done(function () {
            show_message ("success",
                "<p>" + uuids.length + " file(s) removed from the version. " +
                "Clear the cache (Maintenance &rarr; Clear cache) for the public page to update.</p>");
            jQuery("#rmf-results-body").empty();
            jQuery("#rmf-results").addClass("rmf-hidden");
            jQuery("#rmf-search-input").val("");
            selected_dataset = null;
            selected_version = null;
            version_files = [];
            show_step (1);
        }).fail(function (xhr) {
            var msg = "Removing files failed.";
            if (xhr && xhr.responseJSON && xhr.responseJSON.message) {
                msg = xhr.responseJSON.message;
            }
            show_message ("failure", "<p>" + msg + "</p>");
        });
    });
});
