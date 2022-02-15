var article_data = null;

jQuery(function () {

    // Drag and drop handling for the entire window.
    jQuery("html").on("dragover", function (event) {
        event.preventDefault();
        event.stopPropagation();
        jQuery(".upload-container").css("background", "#eeeeee")
        jQuery("#file-upload h2").text("Drag here");
    });
    jQuery("html").on("drop", function (event) {
        event.preventDefault();
        event.stopPropagation();
    });

    // Drag and drop handling for the upload area.
    jQuery('#file-upload').on('dragenter', function (event) {
        event.stopPropagation();
        event.preventDefault();
        jQuery("#file-upload h2").text("Drop here");
    });
    jQuery('#file-upload').on('dragover', function (event) {
        event.stopPropagation();
        event.preventDefault();
        jQuery("#file-upload h2").text("Drop here");
    });
    jQuery('#file-upload').on('dragleave', function (event) {
        jQuery(".upload-container").css("background", "#f9f9f9");
        jQuery("#file-upload h2").text("Drag files here");
    });
    jQuery('#file-upload').on('drop', function (event) {
        event.stopPropagation();
        event.preventDefault();

        jQuery("#file-upload h2").text("Uploading ...");

        var file = event.originalEvent.dataTransfer.files;
        var data = new FormData();
        data.append('file', file[0], file[0].name);
        perform_upload(data, file[0].name);
    });

    // Open file selector on div click
    jQuery("#file-upload").click(function () {
        jQuery("#file").click();
    });

    // file selected
    jQuery("#file").change(function () {
        var file = jQuery('#file')[0].files;
        var data = new FormData();
        data.append('file', file[0], file[0].name);
        perform_upload(data, file[0].name);
    });
});

function create_article (title, on_success, on_failure) {
    if (article_data != null) {
        on_success (article_data);
    } else {
        var jqxhr = jQuery.ajax({
            url:         "/v2/account/articles",
            type:        "POST",
            data:        JSON.stringify({ "title": title }),
            contentType: "application/json",
            dataType:    "json"
        }).done(function (data) { article_data = data; on_success (data); })
            .fail(function ()     { on_failure(); });
    }
}

function perform_upload (form_data, filename) {
    create_article (filename, function (response) {
        article_id = response.location.split("/").pop();
        jQuery.ajax({
            xhr: function () {
                var xhr = new window.XMLHttpRequest();
                xhr.upload.addEventListener("progress", function (evt) {
                    if (evt.lengthComputable) {
                        var completed = parseInt(evt.loaded / evt.total * 100);
                        jQuery("#file-upload h2").text("Uploading at " + completed + "%");
                        if (completed === 100) {
                            jQuery("#file-upload h2").text("Computing MD5 ...");
                        }
                    }
                }, false);
                return xhr;
            },
            url:         "/v3/articles/"+ article_id +"/upload",
            type:        "POST",
            data:        form_data,
            processData: false,
            contentType: false,
            success: function (data, textStatus, request) {
                jQuery("#file-upload h2").text("Drag files here");
                add_uploaded_file_record (data["location"]);
            }
        });
    }, function () {
        jQuery("#file-upload").css("background", "#990000");
    })
}

function add_uploaded_file_record (location) {
    var jqxhr = jQuery.ajax({
        url:         location,
        type:        "GET"
    }).done(function (data) {
        jQuery("#files tbody").append('<tr><td>'+ data["name"] +' ('+
                                      prettify_size(data["size"]) +
                                      ')</td><td>'+ data["computed_md5"] +
                                      '</td><td></td></tr>');
        jQuery("#files").show();
    }).fail(function () {
        console.log("Failed to retrieve file details.");
    });
}

function prettify_size (size) {
    var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (size == 0 || size == null) return '0 Byte';
    var i = parseInt(Math.floor(Math.log(size) / Math.log(1000)));
    return Math.round(size / Math.pow(1000, i), 2) + ' ' + sizes[i];
}
