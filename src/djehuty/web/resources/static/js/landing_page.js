function add_dataset_to_collection (dataset_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "articles": [dataset_id] }),
    }).done(function () {
        show_message ("success", "<p>Dataset succesfully added to collection.</p>");
    }).fail(function () {
        show_message ("failure", "<p>Failed to add dataset to collection.</p>");
    });
}

function toggle_access_request (event) {
    stop_event_propagation (event);
    let access_request_div = jQuery("#access-request-wrapper");
    if (access_request_div.is(":visible")) {
        jQuery("#access-request-wrapper").slideUp(150, function (){
            jQuery("#access-request")
                .removeClass("close")
                .addClass("open")
                .text("Request access to data");
        });
    } else {
       jQuery("#access-request-wrapper").slideDown(150, function (){
           jQuery("#access-request")
                .removeClass("open")
                .addClass("close")
               .text("Cancel access request");
        });
    }
}

function submit_access_request (event) {
    stop_event_propagation (event);
    let data = {
        "email":      or_null(jQuery("#access-request-email").val()),
        "name" :      or_null(jQuery("#access-request-name").val()),
        "dataset_id": or_null(jQuery("#access-request-dataset-id").val()),
        "version":    or_null(jQuery("#access-request-version").val()),
        "reason":     or_null(jQuery("#access-request-reason .ql-editor").html())
    };
    jQuery.ajax({
        url:         `/data_access_request`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(data),
        dataType:    "json"
    }).done(function () {
        show_message ("success", "<p>Access request has been sent.</p>");
        toggle_access_request(null);
    }).fail(function () {
        show_message ("failure", "<p>Access request could not be sent.</p>");
    });
}

function prompt_download_all_request (event) {
    jQuery("#download-all-files-message")
        .addClass("success")
        .append("<p>Your download is being prepared. This may take a while.</p>")
        .fadeIn(250);
    setTimeout(function() {
        jQuery("#download-all-files-message").fadeOut(500, function() {
            jQuery("#message")
                .removeClass("success")
                .addClass("transparent")
                .html("<p>&nbsp;</p>")
                .show();
        });
    }, 120000);

    show_message ("success", );
}

function toggle_versions (event) {
    stop_event_propagation (event);
    let versions = jQuery("#versions");
    if (versions.is(":visible")) {
        versions.slideUp(150, function () {
            jQuery("#versions-arrow").removeClass("fa-angle-up").addClass("fa-angle-down");
        });
    } else {
        versions.slideDown(150, function () {
            jQuery("#versions-arrow").removeClass("fa-angle-down").addClass("fa-angle-up");
        });
    }
}

function render_draft_collections () {
    if (dataset_uuid == null) { return; }
    jQuery.ajax({
        url:         "/v2/account/collections",
        type:        "GET",
        accept:      "application/json",
        dataType:    "json"
    }).done(function (records) {
        jQuery("#collect ul").remove();
        jQuery("#collect").append("<ul></ul>");
        for (collection of records) {
            let item = jQuery("<a/>", { "href": "#", "class": "corporate-identity" })
                .text(collection.title)
                .on("click", function (event) {
                    add_dataset_to_collection (dataset_uuid, collection.uuid);
                    stop_event_propagation (event);
                });
            jQuery("#collect ul").append(item);
        }
    }).fail(function (jqXHR, textStatus, errorThrown) {
        if (jqXHR.status == 403) {
            show_message ("failure", "<p>No permission to list collections.</p>");
        } else {
            show_message ("failure", "<p>Failed to list collections for your account.</p>");
        }
    });
}

jQuery(document).ready(function (){
    if (document.getElementById ("access-request-reason") !== null) {
        new Quill("#access-request-reason", { theme: "4tu" });
    }
    jQuery("#access-request").on("click", toggle_access_request);
    jQuery("#submit-access-request").on("click", submit_access_request);
    jQuery("#download-all-files").on("click", prompt_download_all_request);
    jQuery("#cite-btn").on("click", toggle_citation);
    jQuery("#collect-btn").on("click", function (event) {
        toggle_collect (event);
        render_draft_collections ();
        stop_event_propagation (event);
    });
    jQuery("#versions-btn").on("click", toggle_versions);
});
