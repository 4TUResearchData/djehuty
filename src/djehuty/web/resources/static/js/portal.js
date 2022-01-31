jQuery(document).ready(function() {
    var jqxhr = jQuery.get("https://api.figshare.com/v2/articles", {
        "limit":           30,
        "order_direction": "desc",
        "order":           "published_date",
        "institution":     898
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

                output += '<a href="'+ data[index].url_public_html +'">';
                output += data[index].title + '</a></li>';

                num_items += 1;
            });

            output += "</ul>";
            jQuery("#latest-datasets").append(output);
        })
        .fail(function() {
            jQuery("#latest-datasets").append("<p>Could not load the latest datasets.</p>");
        });
});
