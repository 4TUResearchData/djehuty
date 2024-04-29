function save_profile (notify=true, on_success=jQuery.noop) {

    let categories   = jQuery("input[name='categories']:checked");
    let category_ids = [];
    for (let category of categories) {
        category_ids.push(jQuery(category).val());
    }

    let form_data = {
        "first_name":     or_null(jQuery("#first_name").val()),
        "last_name":      or_null(jQuery("#last_name").val()),
        "job_title":      or_null(jQuery("#job_title").val()),
        "location":       or_null(jQuery("#location").val()),
        "biography":      or_null(jQuery("#biography").val()),
        "twitter":        or_null(jQuery("#twitter").val()),
        "linkedin":       or_null(jQuery("#linkedin").val()),
        "website":        or_null(jQuery("#website").val()),
        "categories":     category_ids
    };

    jQuery.ajax({
        url:         "/v3/profile",
        type:        "PUT",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(form_data),
    }).done(function () {
        if (notify) { show_message ("success", "<p>Saved changes.</p>"); }
        on_success ();
    }).fail(function () {
        if (notify) {
            show_message ("failure", "<p>Failed to save your profile. Please try again at a later time.</p>");
        }
    });
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
        show_message ("failure", "Failed to retrieve categories.");
    });
}

function remove_profile_image () {
    event.preventDefault();
    event.stopPropagation();

    jQuery.ajax({
        url:         "/v3/profile/picture",
        type:        "DELETE",
        accept:      "application/json"
    }).done (function () {
        jQuery("#upload-profile-image").removeClass("profile-image");
        jQuery(".dz-button").show();
    }).fail (function () {
        show_message ("failure", "<p>Failed to remove profile image.</p>");
    });
}

function activate () {
    render_categories_for_profile ();
    install_sticky_header();
    install_touchable_help_icons();
    jQuery("#save").on("click", function () { save_profile (); });
    jQuery("#remove-image").on("click", function () { remove_profile_image (); });

    var fileUploader = new Dropzone("#upload-profile-image", {
        url:               "/v3/profile/picture",
        dictDefaultMessage: "Upload your profile picture",
        paramName:         "file",
        maxFilesize:       10000,
        maxFiles:          1,
        parallelUploads:   1,
        ignoreHiddenFiles: false,
        createImageThumbnails: false,
        disablePreviews:   true,
        init: function() {},
        error: function(file, response, xhr) {
            show_message ("failure", `<p>${response.message}</p>`);
        },
        success: function (file, response) {
            save_profile (notify=false, function () { location.reload(); });
        },
        accept: function(file, done) {
            done();
        }
    });

    fileUploader.on("complete", function(file) {
        fileUploader.removeFile(file);
    });

}
