const cumulativeSum = (sum => value => sum += value)(0); // https://stackoverflow.com/a/55261098
const capitalize    = (i) => (i[0].toUpperCase() + i.substring(1));

function latest_datasets () {
    parameters = {
        limit:           10,
        order_direction: "desc",
        order:           "published_date",
    }

    if (categories !== "") { jQuery.extend(parameters, { "categories": categories }) }

    var jqxhr = jQuery.get("/v3/articles", parameters, function() {
    })
        .done(function(data) {
            output = '<ul class="latest-datasets">';
            num_items = 0;
            jQuery.each (data, function(index) {
                if (num_items < 3) {
                    output += '<li class="datasets-stage datasets-stage-one">';
                } else if (num_items < 8) {
                    output += '<li class="datasets-stage datasets-stage-two">';
                } else if (num_items < 13) {
                    output += '<li class="datasets-stage datasets-stage-three">';
                } else if (num_items < 22) {
                    output += '<li class="datasets-stage datasets-stage-four">';
                } else {
                    output += '<li class="datasets-stage datasets-stage-five">';
                }

                output += '<a target="_blank" href="'+ data[index].url_public_html +'">';
                output += data[index].title + '</a></li>';

                num_items += 1;
            });

            output += "</ul>";
            jQuery("#latest-datasets-loader").hide();
            jQuery("#latest-datasets").append(output);
        })
        .fail(function() {
            jQuery("#latest-datasets-loader").hide();
            jQuery("#latest-datasets").append("<p>Could not load the latest datasets.</p>");
        });
}

function top_datasets (item_type) {
    jQuery("#top-datasets-wrapper").addClass("loader");
    jQuery("#top-datasets tbody tr").css('opacity', '0.15');
    jQuery("#top-buttons .active").removeClass("active")
    jQuery(".top-" + item_type).addClass("active")
    var jqxhr = jQuery.get("/v3/articles/top/" + item_type, {
        "limit":           10,
        "order_direction": "desc",
        "order":           item_type,
        "categories":      categories
    }, function() {
    })
        .done(function(data) {
            var output = '<table id="top-datasets"><thead>';
            output += '<tr><th>Article</th><th># '+ capitalize(item_type) +'</th></tr>';
            output += '</thead><tbody>';
            jQuery.each (data, function(index) {
                output += '<tr><td>';
                output += '<a target="_blank" href="'+ data[index].figshare_url +'">';
                output += data[index].title + '</a>';
                output += '</td>';
                output += '<td>' + data[index][item_type] + '</td></tr>';
            });

            output += "</tbody></table>";
            jQuery("#top-datasets").remove()
            jQuery("#top-datasets-wrapper").removeClass("loader");
            jQuery("#top-datasets-wrapper").append(output);
        })
        .fail(function() {
            jQuery("#top-datasets-wrapper").append("<p>Could not load the top datasets.</p>");
        });
}

jQuery(document).ready(function() {
    top_datasets("downloads");
    latest_datasets();
});
