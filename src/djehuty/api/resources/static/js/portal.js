jQuery(document).ready(function() {
    var jqxhr = jQuery.get( "https://api.figshare.com/v2/articles", {
        "limit":           20,
        "order_direction": "desc",
        "order":           "published_date",
        "item_type":       5 // dataset
    }, function() {
    })
        .done(function(data) {
            output = "<ul>";
            jQuery.each (data, function(index) {
                console.log("Title: " + data[index].title);
                output += '<li><a href="'+ data[index].url_public_html +'">';
                output += data[index].title + '</a></li>';
            });
            jQuery("#latest-datasets").append(output);
            output += "</ul>";
        })
        .fail(function() {
            jQuery("#latest-datasets").append("<p>Could not load the latest datasets.</p>");
        });
    jQuery("#latest-datasets").append("<ul>");
});
