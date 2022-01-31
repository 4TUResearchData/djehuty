const categories    = "13376,13377,13378,13379,13381,13382,13383,13384,13380";
const cumulativeSum = (sum => value => sum += value)(0); // https://stackoverflow.com/a/55261098
const capitalize    = (i) => (i[0].toUpperCase() + i.substring(1));

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

            jQuery("#intro-text-loader").hide();
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
        "limit":           31,
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

function timeline_graph (item_type) {
    var wrapper = document.getElementById("timeline-wrapper");
    var width   = document.getElementById("content-wrapper").offsetWidth;
    var height  = document.getElementById("content-wrapper").offsetHeight;
    jQuery("#timeline-wrapper").addClass('loader');
    jQuery("#timeline-wrapper svg").css('opacity', '0.15');
    jQuery("#timeline-buttons .active").removeClass("active")
    jQuery(".timeline-" + item_type).addClass("active")
    var jqxhr   = jQuery.get("/v3/articles/timeline/" + item_type, {
        "order_direction": "asc",
        "order":           "date",
        "categories":      categories
    }, function() {})
        .done(function(data) {
            // Convert date strings to JS timestamps.
            data = data.map((record) => {
                record["date"] = Date.parse(record["date"]);
                return record;
            });
            // Sort by article ID, and then by date.
            data.sort((a,b) => (a.article_id - (b.article_id) || a.date - b.date));
            // Extract article ids.
            const articles = data.map(record => record["article_id"]);
            // Strip duplicates.
            const ids      = [...new Set(articles)];
            // Assign a color to each article id.
            var colors = {}
            for (index in ids) {
                colors[ids[index]] = "#" + Math.floor(Math.random() * 0xFFFFFF).toString(16);
            }
            // Generate the plot.
            var plot = LineChartMultiSeries(data, {
                x:       d => d.date,
                y:       d => d[item_type],
                z:       d => d.article_id,
                color:   id => colors[id],
                yDomain: [0, 150],
                yLabel:  "↑ " + capitalize(item_type),
                width:   (width - 30),
                height:  400,
            });
            // Add the SVG to the wrapper and update the tab bar.
            jQuery("#timeline-wrapper svg").remove()
            jQuery("#timeline-wrapper").removeClass('loader');
            wrapper.append(plot);
        })
        .fail(function() {
            wrapper.append("<p>Could not load the timeline graph.</p>");
        });
}

jQuery(document).ready(function() {
    intro_text();
    top_datasets("downloads");
    latest_datasets();
    timeline_graph("downloads");
});
