jQuery(document).ready(function () {
    jQuery(".hide-for-javascript").removeClass("hide-for-javascript");
    jQuery("#recalculate-statistics").on("click", function (event) {
        stop_event_propagation (event);
        jQuery.ajax({
            url:  "/admin/maintenance/recalculate-statistics",
            type: "GET"
        }).done(function () {
            show_message ("success", "<p>Recalculated statistics.</p>");
        }).fail(function () {
            show_message ("failure", "<p>Failed recalculate statistics.</p>");
        });
    });
    jQuery("#clear-cache").on("click", function (event) {
        stop_event_propagation (event);
        jQuery.ajax({
            url:  "/admin/maintenance/clear-cache",
            type: "GET",
        }).done(function () {
            show_message ("success", "<p>Cache has been cleared.</p>");
        }).fail(function () {
            show_message ("failure", "<p>Could not clear the cache.</p>");
        });
    });
    jQuery("#clear-website-sessions").on("click", function (event) {
        stop_event_propagation (event);
        jQuery.ajax({
            url:  "/admin/maintenance/remove-website-sessions",
            type: "GET"
        }).done(function () {
            show_message ("success", "<p>Removed old website sessions.</p>");
        }).fail(function () {
            show_message ("failure", "<p>Failed to remove old website sessions.</p>");
        });
    });
        jQuery("#repair-missing-dois").on("click", function (event) {
        stop_event_propagation (event);
        jQuery.ajax({
            url:  "/admin/maintenance/repair-doi-registrations",
            type: "GET"
        }).done(function () {
            show_message ("success", "<p>Repaired DOI registrations..</p>");
        }).fail(function () {
            show_message ("failure", "<p>Failed to repair DOI registrations.</p>");
        });
    });
});
