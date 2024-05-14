function load_operational_statistics() {
    jQuery.when(
        get_operational_statistics_data()
    ).done(function (data) {
        render_data_table(data);
        render_chart_overview(data);
    }).fail(function (jqXHR, textStatus, errorThrown) {
        render_data_table([]);
        show_message ("failure",
            "<p>Failed to load operational statistics data (" +
            textStatus + ": " + errorThrown + ")</p>");
    });
}

function get_operational_statistics_data() {
    return jQuery.ajax({
        url: "/v3/admin/report/operational-statistics",
        type: "GET",
        dataType: "json",
        contentType: "application/json",
        accept: "application/json",
    }).done(function(data) {
        if (data.length == 0) {
            show_message ("failure",
                "<p>The API has returned null data...</p>");
            return;
        }
        return data;
    });
}

function render_data_table(data) {
    jQuery('#operational-statistics-table').DataTable( {
        data: data,
        paging: false,
        searching: false,
        info: false,
        order: [],
        columns: [
            { data: 'institution', orderable: false },
            { data: 'public_size', render: DataTable.render.number(',') },
            { data: 'private_size', render: DataTable.render.number(',') },
            { data: 'opendap_size', render: DataTable.render.number(',') },
            { data: 'new_datasets_count', render: DataTable.render.number(',')},
            { data: 'updated_datasets_count', render: DataTable.render.number(',')},
            { data: 'new_drafts_count', render: DataTable.render.number(',')},
            { data: 'updated_drafts_count', render: DataTable.render.number(',')},
        ]
    });
}

function render_chart_overview() {
}
