jQuery(document).ready(function () {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");

    jQuery("#embargo-search-button").on("click", function (event) {
        stop_event_propagation (event);
        var search_for = jQuery("#embargo-search-input").val().trim();
        if (search_for === "") { return; }

        jQuery("#embargo-results-body").empty();
        jQuery("#embargo-detail").addClass("embargo-hidden");
        jQuery("#embargo-results").addClass("embargo-hidden");

        jQuery.ajax({
            url:  "/admin/embargo/search",
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
        var d = jQuery(this).data("dataset");
        jQuery("#embargo-results-body tr").removeClass("selected-row");
        jQuery(this).addClass("selected-row");
        jQuery("#detail-title").text(d.title || "-");
        jQuery("#detail-doi").text(d.doi || "-");
        jQuery("#detail-embargo-type").text(d.embargo_type || "-");
        jQuery("#detail-embargo-title").text(d.embargo_title || "-");
        jQuery("#detail-embargo-reason").text(d.embargo_reason || "-");
        jQuery("#detail-embargo-date").text(d.embargo_until_date || "Not set");
        jQuery("#embargo-date-input").val(d.embargo_until_date || "");
        jQuery("#embargo-detail").data("dataset-uri", d.uri);
        jQuery("#embargo-detail").removeClass("embargo-hidden");
    });

    jQuery("#embargo-update-button").on("click", function (event) {
        stop_event_propagation (event);
        var dataset_uri = jQuery("#embargo-detail").data("dataset-uri");
        var new_date = jQuery("#embargo-date-input").val();
        if (!new_date) {
            show_message ("failure", "<p>Please select a date.</p>");
            return;
        }

        jQuery.ajax({
            url:  "/admin/embargo/update",
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify({ dataset_uri: dataset_uri, embargo_until_date: new_date })
        }).done(function () {
            show_message ("success", "<p>Embargo date updated to " + new_date + ".</p>");
            jQuery("#detail-embargo-date").text(new_date);
            var selected = jQuery("#embargo-results-body tr.selected-row");
            selected.find("td:eq(2)").text(new_date);
            selected.data("dataset").embargo_until_date = new_date;
        }).fail(function () {
            show_message ("failure", "<p>Failed to update embargo date.</p>");
        });
    });
});
