const capitalize = (i) => (i[0].toUpperCase() + i.substring(1))

function parameters_for_api_calls (order) {
    let parameters = {
        "limit": 10,
        "order_direction": "desc",
        "order": order
    }

    // This procedure is used by both institutional pages which filter by 'group_ids'
    // and category pages which filter by 'categories'.  So one of these variables
    // won't be defined, but that's expected.
    try {
        if (categories !== "") { jQuery.extend(parameters, { "categories": categories }); }
    } catch (error) {}

    try {
        if (group_ids !== "") { jQuery.extend(parameters, { "group_ids": group_ids }); }
    } catch (error) {}

    return parameters;
}

function latest_datasets () {
    const parameters = parameters_for_api_calls ("published_date");
    jQuery.get("/v3/datasets", parameters, function() {
    }).done(function(data) {
        let output = '<ul class="latest-datasets">';
        let num_items = 0;
        jQuery.each (data, function(index) {
            if (jQuery.isEmptyObject(data[index])) { return; }
            output += '<li><a class="corporate-identity" href="/datasets/'+ data[index].uuid +'">';
            output += data[index].title + '</a></li>';

            num_items += 1;
        });

        output += "</ul>";
        jQuery("#latest-datasets-loader").hide();
        jQuery("#latest-datasets").append(output);
    }).fail(function() {
        jQuery("#latest-datasets-loader").hide();
        jQuery("#latest-datasets").append("<p>Could not load the latest datasets.</p>");
    });
}

function top_datasets (item_type) {
    jQuery("#top-datasets-wrapper").addClass("loader");
    jQuery("#top-datasets tbody tr").css('opacity', '0.15');
    jQuery("#top-buttons .active").removeClass("active");
    jQuery(".top-" + item_type).addClass("active");

    const parameters = parameters_for_api_calls (item_type);
    jQuery.get("/v3/datasets/top/" + item_type, parameters, function() {
    }).done(function(data) {
        let output = '<table id="top-datasets"><thead>';
        output += '<tr class="corporate-identity-background"><th>Dataset</th><th># '+ capitalize(item_type) +'</th></tr>';
        output += '</thead><tbody>';
        jQuery.each (data, function(index) {
            if (jQuery.isEmptyObject(data[index])) { return; }
            output += '<tr><td>';
            output += '<a href="/datasets/'+ data[index].container_uuid +'">';
            output += data[index].title + '</a>';
            output += '</td>';
            output += '<td>' + data[index][item_type] + '</td></tr>';
        });

        output += "</tbody></table>";
        jQuery("#top-datasets").remove()
        jQuery("#top-datasets-wrapper").removeClass("loader");
        jQuery("#top-datasets-wrapper").append(output);
    }).fail(function() {
        jQuery("#top-datasets-wrapper").append("<p>Could not load the top datasets.</p>");
    });
}

jQuery(document).ready(function() {
    top_datasets("downloads");
    latest_datasets();
});
