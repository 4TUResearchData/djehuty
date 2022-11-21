function save_profile () {
    event.preventDefault();
    event.stopPropagation();

    let categories   = jQuery("input[name='categories']:checked");
    let category_ids = []
    for (let category of categories) {
        category_ids.push(jQuery(category).val());
    }

    let form_data = {
        "first_name":     or_null(jQuery("#first_name").val()),
        "last_name":      or_null(jQuery("#last_name").val()),
        "job_title":      or_null(jQuery("#job_title").val()),
        "location":       or_null(jQuery("#location").val()),
        "biography":      or_null(jQuery("#biography").val()),
        "categories":     category_ids
    }

    jQuery.ajax({
        url:         "/v3/profile",
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        jQuery("#message")
            .addClass("success")
            .append("<p>Saved changes.</p>")
            .fadeIn(250);
        setTimeout(function() {
            jQuery("#message").fadeOut(500, function() {
                jQuery("#message").removeClass("success").empty();
            });
        }, 5000);
        console.log("Form was saved.");
    }).fail(function () { console.log("Failed to save form."); });
}

function render_categories_for_profile () {
    jQuery.ajax({
        url:         "/v3/profile/categories",
        data:        { "limit": 10000 },
        type:        "GET",
        accept:      "application/json",
    }).done(function (categories) {
        for (let category of categories) {
            jQuery(`#category_${category["uuid"]}`).prop("checked", true);
            jQuery(`#category_${category["parent_uuid"]}`).prop("checked", true);
            jQuery(`#subcategories_${category["parent_uuid"]}`).show();
        }
    }).fail(function () {
        console.log("Failed to retrieve categories.");
    });
}

function activate () {
    render_categories_for_profile ();
    jQuery("#save").on("click", function () { save_profile (); });
}
