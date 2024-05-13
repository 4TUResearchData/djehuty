function load_operational_statistics_data() {
    jQuery.ajax({
        url: "/v3/admin/report/operational-statistics",
        type: "GET",
        dataType: "json",
        contentType: "application/json",
        accept: "application/json",
    }).done(function(data) {
        if (data.length == 0) {
            let error_message = `No data...`;
            jQuery("#loading-error").html(error_message);
            jQuery("#loading-error").show();
            return;
        }
        render_operational_statistics(data);
    }).fail(function(jqXHR, textStatus, errorThrown) {
        let error_message = `Error loading data: ${textStatus}`;
        jQuery("#loading-error").html(error_message);
        jQuery("#loading-error").show();
    });
}

function render_operational_statistics(data) {
    jQuery('#operational-statistics-table').DataTable( {
        data: data,
        paging: false,
        searching: false,
        info: false,
        order: [],
        columns: [
            { data: 'institution', orderable: false },
            { data: 'public_size' },
            { data: 'private_size' },
            { data: 'opendap_size' },
            { data: 'new_datasets_count' },
            { data: 'updated_datasets_count' },
            { data: 'new_drafts_count' },
            { data: 'updated_drafts_count' },
        ]
    });
}
