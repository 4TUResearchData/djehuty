var current_article_id = null;

function toggle_article (article_id) {
    if (jQuery("#article_" + article_id).is(":visible")) {
        current_article_id = null;
        jQuery(".h3-article")
            .css("background", "")
            .css("opacity", "1.0");
        jQuery(".article-content").hide();
    } else {
        current_article_id = article_id;
        jQuery("#files tbody").empty();
        jQuery(".article-content").empty().hide();
        jQuery("#article_" + article_id).append('<div class="upload-wrapper"><input type="file" name="file" id="file" aria-label="Upload file"><div class="upload-container" id="file-upload"><h2>Drag files here</h2><p>Or click to open a file dialog.</p></div></div><div id="files-wrapper"><table class="branded-table" id="files"><thead><tr><th>Filename</th><th>Checksum</th><th>Actions</th></tr></thead><tbody></tbody></table></div>');
        jQuery(".h3-article")
            .css("background", "")
            .css("border-radius", ".5em .5em 0em 0em")
            .css("opacity", "0.10");
        jQuery(".h3-article");
        jQuery("#h3_" + article_id).css("opacity", "1.0");
        jQuery("#h3_" + article_id).css("background", "#f49120");
        render_files_for_article (article_id);
        jQuery("#article_" + article_id).show();
        activate_drag_and_drop ();
    }
}

function create_article (title, on_success, on_failure) {
    if (current_article_id != null) {
        on_success (current_article_id);
    } else {
        var jqxhr = jQuery.ajax({
            url:         "/v2/account/articles",
            type:        "POST",
            data:        JSON.stringify({ "title": title }),
            contentType: "application/json",
            dataType:    "json"
        }).done(function (data) {
            current_article_id = data.location.split("/").pop();
            on_success (current_article_id);
        }).fail(function ()     { on_failure(); });
    }
}

function perform_upload (form_data, filename) {
    create_article (filename, function (article_id) {
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
                render_files_for_article (article_id);
                //add_uploaded_file_record (data["location"]);
            }
        });
    }, function () {
        jQuery("#file-upload").css("background", "#990000");
    })
}

function render_files_for_article (article_id) {
    var jqxhr = jQuery.ajax({
        url:         "/v2/account/articles/"+ article_id +"/files",
        type:        "GET",
        accept:      "application/json",
    }).done(function (files) {
        jQuery("#files tbody").empty();
        for (index in files) {
            file = files[index];
            console.log ("Processing: "+ JSON.stringify(file));
            jQuery("#files tbody").append('<tr><td>'+ file.name +' ('+
                                          prettify_size(file["size"]) +
                                          ')</td><td>'+ file["computed_md5"] +
                                          '</td><td></td></tr>');
        }
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

function activate_drag_and_drop () {
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
}
