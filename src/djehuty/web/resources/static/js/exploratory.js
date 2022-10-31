function shorthand_uri (value) {
    return value.replace("https://ontologies.data.4tu.nl/djehuty/0.0.1/", "djht:")
                .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:")
                .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:");
}

function longform_uri (value) {
    return value.replace("djht:", "https://ontologies.data.4tu.nl/djehuty/0.0.1/")
                .replace("rdf:", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
                .replace("rdfs:", "http://www.w3.org/2000/01/rdf-schema#");
}

function draw_grid () {
    explorer    = d3.select("#data-model-explorer");
    width       = parseInt(explorer.style("width"));
    height      = parseInt(explorer.style("height"));

    explorer.select("#grid").remove()
    grid = explorer.append("g").attr("id", "grid")
    grid.lower()
    for (let x = 10; x < width; x += 10) {
        // Vertical lines
        grid.append("line")
            .attr("x1", x)
            .attr("y1", 0)
            .attr("x2", x)
            .attr("y2", height + 1)
            .classed(((x % 290 == 0) ? "highlighted-grid-line" : "grid-line"), true);
        // Horizontal lines
        grid.append("line")
            .attr("x1", 0)
            .attr("y1", x)
            .attr("x2", width + 1)
            .attr("y2", x)
            .classed(((x == 40) ? "highlighted-grid-line" : "grid-line"), true);
    }
}

function draw_column_title (column, value) {
    translate_x = 20 + column * 290;
    explorer    = d3.select("#data-model-explorer");
    explorer.selectAll(`.node-${column}-column-title`).remove()
    title_group = explorer.append("g")
                          .attr("transform", "translate("+ translate_x +",20)")
                          .classed(`node-${column}-column-title`, true);
    title_group
        .append("text").text(value)
        .attr("transform", "translate(0, 11)")
        .classed("node-column-title", true)
}

function resize_svg () {
    explorer      = d3.select("#data-model-explorer");

    // Determine the maximum rows to adjust for.
    column_0_rows = explorer.selectAll(".column-0").size();
    column_1_rows = explorer.selectAll(".column-1").size();
    rows          = ((column_0_rows > column_1_rows) ? column_0_rows : column_1_rows);

    // The formula is: header-padding + number-of-rows * height-of-the-row.
    new_height    = 70 + rows * 40;
    explorer.style("height", `${new_height}px`);
}

function draw_node (row, column, value) {
    translate_x = 20 + column * 290;
    translate_y = 60 + row * 40;
    fill_color  = ((row % 2 == 0) ? "#ffffff" : "#eeeeee");
    explorer    = d3.select("#data-model-explorer");
    node_group  = explorer.append("g").attr("transform", "translate("+ translate_x +","+ translate_y +")");

    // Re-adjust the height so that all rendered nodes are visible.
    current_height = parseInt(explorer.style("height"));
    new_height     = translate_y + 50;
    if (current_height < new_height) {
        explorer.style("height", new_height + "px");
    }
    node_group
        .classed(`node-group`, true)
        .classed(`column-${column}`, true)
        .append("rect")
        .classed("node-item", true)
        .attr("style", `fill:  ${fill_color}`);

    node_group
        .append("text").text(value)
        .attr("transform", "translate(10,21)")
        .attr("style", "font-size: 12pt; font-family: 'FiraMono'");

    node_group
        .on("mouseover", node_mouseover)
        .on("mouseout",  node_mouseout)
        .on("mousedown", node_mousedown)
        .on("mouseup",   node_mouseup);
}

function node_mouseover (event, i) {
    group = d3.select(this);
    rect  = group.select("rect");
    rect.style("fill-opacity", ".5");
}

function node_mouseout (event, i) {
    group = d3.select(this);
    rect  = group.select("rect");
    rect.style("fill-opacity", "1");
}

function node_mouseup (event, i) {
    group = d3.select(this);
    rect  = group.select("rect");
    rect.style("fill-opacity", "1");
}

function node_mousedown (event, i) {
    group = d3.select(this);
    rect  = group.select("rect");
    text  = group.select("text");

    // Reset active node.
    d3.select(".active-node").classed("active-node", false);
    rect.classed("active-node", true);

    // Load the next column
    value = text.text();
    jQuery.ajax({
        url:         "/v3/explore/properties",
        type:        "GET",
        accept:      "application/json",
        data:        { "uri": `${encodeURIComponent(longform_uri(value))}` },
    }).done(function (properties) {
        draw_column_title (1, "Properties");
        d3.selectAll(".column-1").remove();
        for (index in properties) {
            value = shorthand_uri(properties[index]);
            draw_node (index, 1, value);
        }
        resize_svg();
        draw_grid ();
    }).fail(function () {
        console.log ("Failed to gather properties.");
    });
}

jQuery(document).ready(function () {
    jQuery.ajax({
        url:         "/v3/explore/types",
        type:        "GET",
        accept:      "application/json",
    }).done(function (types) {
        draw_column_title (0, "Types");
        d3.selectAll(".column-0").remove();
        for (index in types) {
            value = shorthand_uri(types[index]);
            draw_node (index, 0, value);
        }
        resize_svg();
        draw_grid ();
    }).fail(function () {
        console.log ("Failed to gather types.");
    });
});
