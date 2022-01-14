var categories = "13376,13377,13378,13379,13381,13382,13383,13384,13380";

function intro_text () {
    var jqxhr = jQuery.get("/v3/articles", {
        "categories":      categories,
        "return_count":    "true"
    }, function() {
    })
        .done(function(data) {
            output = '<p>The 4TU.ResearchData repository contains '        +
                data["articles"]                                           +
                ' datasets for the agriculture, animal and plant sciences.';

            jQuery("#intro-text").append(output);
        })
        .fail(function() {
        });
}

function latest_datasets () {
    var jqxhr = jQuery.get("/v3/articles", {
        "limit":           30,
        "order_direction": "desc",
        "order":           "published_date",
        "categories":      categories
    }, function() {
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
            jQuery("#latest-datasets").append(output);
        })
        .fail(function() {
            jQuery("#latest-datasets").append("<p>Could not load the latest datasets.</p>");
        });
}

function top_downloaded () {
    var jqxhr = jQuery.get("/v3/articles/top_downloaded", {
        "limit":           31,
        "order_direction": "desc",
        "order":           "downloads",
        "categories":      categories
    }, function() {
    })
        .done(function(data) {
            output = '<table id="top-downloaded"><thead>';
            output += '<tr><th>Article</th><th># Downloads</th></tr>';
            output += '</thead><tbody>';
            jQuery.each (data, function(index) {
                output += '<tr><td>';
                output += '<a target="_blank" href="'+ data[index].figshare_url +'">';
                output += data[index].title + '</a>';
                output += '</td>';
                output += '<td>' + data[index].downloads + '</td></tr>';
            });

            output += "</tbody></table>";
            jQuery("#top-downloaded").append(output);
        })
        .fail(function() {
            jQuery("#top-downloaded").append("<p>Could not load the top downloaded datasets.</p>");
        });
}

jQuery(document).ready(function() {
    intro_text();
    top_downloaded();
    latest_datasets();
});
