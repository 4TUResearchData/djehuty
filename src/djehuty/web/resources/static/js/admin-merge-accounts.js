let merge_preview_state = null;

function render_account_summary (account) {
    let name = `${account.first_name || ""} ${account.last_name || ""}`.trim();
    let email = account.email || "(no e-mail)";
    let label = name ? `${name} &lt;${email}&gt;` : email;
    return `${label} <code>${account.uuid}</code>`;
}

function render_containers_table (containers) {
    let tbody = jQuery("#merge-containers-tbody");
    tbody.empty();
    if (containers.length === 0) {
        tbody.append('<tr><td colspan="5"><em>No containers owned by the source account.</em></td></tr>');
        return;
    }
    containers.forEach(function (row) {
        let flags = "";
        if (row.has_published === true || row.has_published === "true") {
            flags += '<span class="flag published">published</span>';
        }
        if (row.has_draft === true || row.has_draft === "true") {
            flags += '<span class="flag draft">draft</span>';
        }
        let doi = row.doi ? `<a href="https://doi.org/${row.doi}" target="_blank" rel="noopener">${row.doi}</a>` : "-";
        let title = row.title ? row.title : "<em>(untitled)</em>";
        tbody.append(`<tr>
            <td class="type-tag">${row.container_type || "-"}</td>
            <td>${title}</td>
            <td>${doi}</td>
            <td>${flags || "-"}</td>
            <td><code>${row.container_uuid}</code></td>
        </tr>`);
    });
}

function load_preview (event) {
    stop_event_propagation (event);
    let from_email = jQuery("#from-email").val();
    let to_email = jQuery("#to-email").val();
    if (!from_email || !to_email) {
        show_message ("failure", "<p>Both e-mail addresses are required.</p>");
        return;
    }
    jQuery("#merge-confirm-button").addClass("disabled");
    jQuery.ajax({
        url:         "/admin/users/merge/preview",
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "from_email": from_email, "to_email": to_email }),
        dataType:    "json"
    }).done(function (data) {
        merge_preview_state = data;
        jQuery("#preview-from").html (render_account_summary (data.from_account));
        jQuery("#preview-to").html (render_account_summary (data.to_account));
        jQuery("#preview-count").text (data.containers.length);
        render_containers_table (data.containers);
        jQuery("#merge-preview").show();
        if (data.containers.length > 0) {
            jQuery("#merge-confirm-button").removeClass("disabled");
        }
    }).fail(function (xhr) {
        merge_preview_state = null;
        jQuery("#merge-preview").hide();
        let message = "Failed to load preview.";
        try {
            let body = JSON.parse (xhr.responseText);
            if (body && body.message) { message = body.message; }
        } catch (e) { /* keep default */ }
        show_message ("failure", `<p>${message}</p>`);
    });
}

function confirm_merge (event) {
    stop_event_propagation (event);
    if (jQuery("#merge-confirm-button").hasClass("disabled")) { return; }
    if (merge_preview_state === null) { return; }
    let count = merge_preview_state.containers.length;
    let from_email = merge_preview_state.from_account.email || merge_preview_state.from_account.uuid;
    let to_email = merge_preview_state.to_account.email || merge_preview_state.to_account.uuid;
    if (!confirm (`Move ${count} container(s) from ${from_email} to ${to_email}? This cannot be undone from the UI.`)) {
        return;
    }
    jQuery("#merge-confirm-button").addClass("disabled");
    jQuery.ajax({
        url:         "/admin/users/merge/execute",
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({
            "from_account_uuid": merge_preview_state.from_account.uuid,
            "to_account_uuid":   merge_preview_state.to_account.uuid
        }),
        dataType:    "json"
    }).done(function (data) {
        show_message ("success", `<p>Moved ${data.moved_containers} container(s).</p>`);
        merge_preview_state = null;
        jQuery("#merge-preview").hide();
        jQuery("#from-email").val("");
        jQuery("#to-email").val("");
    }).fail(function (xhr) {
        let message = "Failed to merge accounts.";
        try {
            let body = JSON.parse (xhr.responseText);
            if (body && body.message) { message = body.message; }
        } catch (e) { /* keep default */ }
        show_message ("failure", `<p>${message}</p>`);
        jQuery("#merge-confirm-button").removeClass("disabled");
    });
}

jQuery(document).ready(function () {
    jQuery("#merge-preview-button").on("click", load_preview);
    jQuery("#merge-confirm-button").on("click", confirm_merge);
});
