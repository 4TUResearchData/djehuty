function toggle_storage_request (event) {
    let storage_request_div = jQuery("#storage-request-wrapper");
    if (storage_request_div.is(":visible")) {
        jQuery("#storage-request-wrapper").slideUp(150, function (){
            jQuery("#request-more-storage").text("Request more storage.");
        });
    } else {
        jQuery("#storage-request-wrapper").slideDown(150, function (){
            jQuery("#request-more-storage").text("Cancel storage request.");
        });
    }

}

function submit_storage_request (event) {
    let data = {
        "new-quota": or_null(jQuery("#new-quota").val()),
        "reason":    or_null(jQuery("#quota-reason .ql-editor").html())
    };
    jQuery.ajax({
        url:         `/v3/profile/quota-request`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(data),
        dataType:    "json"
    }).done(function () {
        show_message ("success", "<p>Quota request has been sent.</p>");
        toggle_storage_request(null);
    }).fail(function () {
        show_message ("failure", "<p>Quota request could not be sent.</p>");
    });
}

jQuery(document).ready(function (){
    new Quill("#quota-reason", { theme: "4tu" });
    jQuery("#request-more-storage").on("click", toggle_storage_request);
    jQuery("#submit-storage-request").on("click", submit_storage_request);
});
