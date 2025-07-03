function render_chart() {

    // 1) For now static data
    const data = [
        {year: "2020", Delft: 340, Eindhoven: 40, Twente: 30, Wageningen: 50, Other: 280},
        {year: "2021", Delft: 435, Eindhoven: 45, Twente: 120, Wageningen: 140, Other: 245},
        {year: "2022", Delft: 525, Eindhoven: 42, Twente: 60, Wageningen: 90, Other: 245},
        {year: "2023", Delft: 680, Eindhoven: 78, Twente: 100, Wageningen: 140, Other: 180}
    ];

    // 2) Configuration & dimensions for the chart
    const margin = {top: 40, right: 20, bottom: 100, left: 50};
    const width = 800 - margin.left - margin.right;
    const height = 500 - margin.top - margin.bottom;

    // 3) Keys & color scale
    const keys = Object.keys(data[0]).filter(k => k !== "year");
    const color = d3.scaleOrdinal()
        .domain(keys)
        .range(["#00A6D6", "#C72125", "#1E2328", "#008A00", "#f4c300"]);

    // 4) Scales
    const x0 = d3.scaleBand()
        .domain(data.map(d => d.year))
        .range([0, width])
        .paddingInner(0.1);

    const x1 = d3.scaleBand()
        .domain(keys)
        .range([0, x0.bandwidth()])
        .padding(0.05);

    const y = d3.scaleLinear()
        .domain([0, d3.max(data, d => d3.max(keys, key => d[key]))])
        .nice()
        .range([height, 0]);

    // 5) SVG container
    const svg = d3.select("#chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    // 6) X & Y axes
    svg.append("g")
        .attr("class", "axis")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x0));

    svg.append("g")
        .attr("class", "axis")
        .call(d3.axisLeft(y).ticks(5));

    // 7) Bars
    svg.selectAll("g.year")
        .data(data)
        .join("g")
        .attr("class", "year")
        .attr("transform", d => `translate(${x0(d.year)},0)`)
        .selectAll("rect")
        .data(d => keys.map(key => ({key: key, value: d[key]})))
        .join("rect")
        .attr("x", d => x1(d.key))
        .attr("y", d => y(d.value))
        .attr("width", x1.bandwidth())
        .attr("height", d => height - y(d.value))
        .attr("fill", d => color(d.key))
        .append("title")               // hover tooltip
        .text(d => `${d.key}: ${d.value}`);

    // 8) Chart title
    svg.append("text")
        .attr("x", width / 2)
        .attr("y", -20)
        .attr("text-anchor", "middle")
        .style("font-size", "18px")
        .style("font-weight", "bold")
        .text("Number of datasets");

    // 9) Legend
    const legendY = height + 40;     // Position is 40px below the chart area
    const legend = svg.append("g")
        .attr("class", "legend")
        .attr("transform", `translate(0, ${legendY})`);

    // --- 3) Use a band scale to distribute keys evenly:
    const legendX = d3.scaleBand()
        .domain(keys)              // your array ["Delft","Eindhoven",…]
        .range([0, width])         // full chart width
        .padding(0.2);             // space between items

    legend.selectAll("g")
        .data(keys)
        .join("g")
        .attr("transform", d => `translate(${legendX(d)},0)`)
        .call(g => {
            g.append("rect")
                .attr("width", 15)
                .attr("height", 15)
                .attr("fill", d => color(d));
            g.append("text")
                .attr("x", 20)
                .attr("y", 12)
                .text(d => d);
        });
}

function load_operational_statistics() {

    const url_params = parse_url_params()
    if ("group" in url_params && typeof (url_params["group"]) === "string" && url_params["group"].length > 0) {
        if (url_params["group"] === "all") {
            delete url_params["group"]
        } else {
            url_params["group"] = _split_comma_separated_string(url_params["group"]);
        }
    }

    if ("host" in url_params && typeof (url_params["host"]) === "string" && url_params["host"].length > 0) {
        url_params["host"] = _split_comma_separated_string(url_params["host"]);
    }

    return jQuery.ajax({
        url:         "/v3/admin/operational-statistics",
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(url_params),
        dataType:    "json"
    }).done(function (response) {
        console.log("done", response)
        render_chart();

    }).fail(function (response) {
        console.log("fails", response)
    });
}


// Duplicated with method used in search.js . Need to add it in utils
function parse_url_params() {
    let url_params = new URLSearchParams(window.location.search);
    let params = {};
    for (let [key, value] of url_params) {
        params[key] = value;
    }
    return params;
}
//also duplicated
function _split_comma_separated_string(value) {
    let values = [];
    if (value && value.length > 0) {
        for (let v of value.split(",")) {
            values.push(v);
        }
    }
    return values;
}

function set_filters_values_from_url(groups) {
    let url = new URL(window.location.href);
    let params = new URLSearchParams(url.search);
    params.forEach((value, key) => {
        let input_element
        const checkbox_filter = key === "host"
        const group_filter = key === "group"
        if (checkbox_filter) {
            input_element = document.getElementsByName(key)
            const values = value.split(separator)
            input_element.forEach(checkbox => {
                if (values.includes(checkbox.id)) {
                    checkbox.checked = true
                }
            })
        } else if (group_filter) {
            input_element = document.getElementById(key)
            const options = Array.from(input_element.options);
            const match = options.find(opt => opt.value === value);
            if (match) {
                input_element.value = value;
            }
        } else {
            input_element = document.getElementById(key)
            input_element.value = value
        }
    });
}

function register_event_handlers() {
    jQuery("#apply-filter-button").click(function () {
        let filters = [];
        let checkboxGroups = {};

        jQuery(".filter-content input").each(function () {
            let filter = null;
            // Remove existing filter with this ID
            filters = filters.filter(filter => !filter.hasOwnProperty(this.name));

            if (this.type === "checkbox") {
                if (this.checked) {
                    if (!checkboxGroups[this.name]) {
                        checkboxGroups[this.name] = [];
                    }
                    checkboxGroups[this.name].push(this.value);
                }
            } else if (this.value && this.value.trim().length > 0) {
                filter = {[this.id]: this.value};
            }

            if (filter) {
                filters.push(filter);
            }
        });

        for (const name in checkboxGroups) {
            if (checkboxGroups[name].length > 0) {
                filters.push({[name]: checkboxGroups[name]});
            }
        }

        jQuery(".filter-content select").each(function () {
            let selectId = this.id;
            let selectedValue = this.value;
            if (selectedValue && selectedValue.trim().length > 0) {
                filters.push({[selectId]: selectedValue});
            }
        });

        // Construct new URL from scratch (only origin + pathname, no old params)
        let url = new URL(window.location.href);
        let params = new URLSearchParams(); // START FRESH

        filters.forEach(filterObj => {
            let key = Object.keys(filterObj)[0];
            let value = filterObj[key];

            if (Array.isArray(value)) {
                if (value.length > 0) {
                    params.set(key, value.join(","));
                }
            } else if (typeof value === "string" && value.trim().length > 0) {
                params.set(key, value.trim());
            }
        });

        let new_url = `${url.origin}${url.pathname}?${params.toString()}`;
        window.location.href = new_url;
    });

}

function load_filters() {

    featured_groups(function (featured_groups) {
        featured_groups.forEach(function (item) {
            jQuery('#group').append($('<option>', {
                id: item.id,
                value: item.value.join(","),
                text: item.label
            }));
        });
        set_filters_values_from_url();
    });

    register_event_handlers()
}

jQuery(document).ready(function () {
    load_operational_statistics();
    load_filters();
});
