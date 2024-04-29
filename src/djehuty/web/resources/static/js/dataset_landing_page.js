function add_dataset_to_collection (dataset_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "articles": [dataset_id] }),
    }).done(function () {
        show_message ("success", "<p>Dataset succesfully added to collection.</p>");
        document.getElementById("collect").style.display = "none";
    }).fail(function () {
        console.log (`Failed to add ${dataset_id}`);
        show_message ("failure", "<p>Failed to add dataset to collection.</p>");
    });
}

function toggle_access_request (event) {
    if (event !== null) {
        event.preventDefault();
        event.stopPropagation();
    }
    let access_request_div = jQuery("#access-request-wrapper");
    if (access_request_div.is(":visible")) {
        jQuery("#access-request-wrapper").slideUp(150, function (){
            jQuery("#access-request").text("Request access to data.");
        });
    } else {
       jQuery("#access-request-wrapper").slideDown(150, function (){
            jQuery("#access-request").text("Cancel access request.");
        });
    }
}

function submit_access_request (event) {
    event.preventDefault();
    event.stopPropagation();
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

jQuery(document).ready(function (){
    if (document.getElementById ("access-request-reason") !== null) {
        new Quill("#access-request-reason", { theme: "4tu" });
    }
    jQuery("#access-request").on("click", toggle_access_request);
    jQuery("#submit-access-request").on("click", submit_access_request);
});
