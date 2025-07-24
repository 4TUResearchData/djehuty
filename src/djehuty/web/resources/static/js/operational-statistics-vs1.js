let featured_groups_list = []

// Chart 3: Stacked Bar Chart
//   function createStackedChart() {
//
//       const data = {
//           "Updated Versions": 183,
//           "First Versions": 1224,
//           Label: "Other Institutions",
//           From: "2023-07-09",
//           To: "2025-07-09",
//       }
//
//         const total = data["Updated Versions"] + data["First Versions"]
//   const updateRate = ((data["Updated Versions"] / total) * 100).toFixed(1)
//
//       // Create tooltip
//   const tooltip = d3.select("body").append("div").attr("class", "tooltip")
//
//     const margin = { top: 20, right: 30, bottom: 40, left: 60 }
//     const width = 400 - margin.left - margin.right
//     const height = 300 - margin.bottom - margin.top
//
//     const svg = d3
//       .select("#stacked-chart")
//       .append("svg")
//       .attr("width", width + margin.left + margin.right)
//       .attr("height", height + margin.top + margin.bottom)
//
//     const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)
//
//     const stackData = [
//       {
//         category: data["Label"],
//         "Updated Versions": data["Updated Versions"],
//         "First Versions": data["First Versions"],
//       },
//     ]
//
//     const keys = ["First Versions", "Updated Versions"]
//     const stack = d3.stack().keys(keys)
//     const series = stack(stackData)
//
//     const x = d3
//       .scaleBand()
//       .rangeRound([0, width])
//       .padding(0.3)
//       .domain(stackData.map((d) => d.category))
//
//     const y = d3.scaleLinear().rangeRound([height, 0]).domain([0, total])
//
//     const color = d3.scaleOrdinal().domain(keys).range(["#ef4444", "#3b82f6"])
//
//     g.append("g").attr("class", "axis").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x))
//
//     g.append("g").attr("class", "axis").call(d3.axisLeft(y))
//
//     g.selectAll(".serie")
//       .data(series)
//       .enter()
//       .append("g")
//       .attr("class", "serie")
//       .attr("fill", (d) => color(d.key))
//       .selectAll("rect")
//       .data((d) => d)
//       .enter()
//       .append("rect")
//       .attr("x", (d) => x(d.data.category))
//       .attr("width", x.bandwidth())
//       .attr("y", height)
//       .attr("height", 0)
//       .style("cursor", "pointer")
//       .on("mouseover", function (event, d) {
//         const key = d3.select(this.parentNode).datum().key
//         const value = d.data[key]
//         tooltip.transition().duration(200).style("opacity", 0.9)
//         tooltip
//           .html(`${key}: ${value}`)
//           .style("left", event.pageX + 10 + "px")
//           .style("top", event.pageY - 28 + "px")
//       })
//       .on("mouseout", (d) => {
//         tooltip.transition().duration(500).style("opacity", 0)
//       })
//       .transition()
//       .duration(800)
//       .attr("y", (d) => y(d[1]))
//       .attr("height", (d) => y(d[0]) - y(d[1]))
//   }

// function render_chart_pie(results) {
//
//     console.log(results)
//
//         // Sample data with 2 values
//     const data = [
//         {label: "Category A", value: 65},
//         {label: "Category B", value: 35},
//     ]
//
//     // Calculate sum
//     const sum = data.reduce((acc, d) => acc + d.value, 0)
//
//     // Chart dimensions
//     const width = 400
//     const height = 400
//     const radius = Math.min(width, height) / 2 - 20
//
//
//     // Color scale
//     const color = d3
//         .scaleOrdinal()
//         .domain(data.map((d) => d.label))
//         .range(["#3b82f6", "#ef4444"])
//
//     let updated_version = 0
//     let first_version = 0
//
//     if (results.length > 1) {
//         results.forEach(item => {
//             updated_version += item.updated_version
//             first_version += item.first_version
//         })
//     } else {
//         updated_version = results[0].updated_version
//         first_version = results[0].first_version
//     }
//
//
//     // Create SVG
//     const svg = d3.select("#chart-pie").append("svg").attr("width", width).attr("height", height)
//
//     const g = svg.append("g").attr("transform", `translate(${width / 2}, ${height / 2})`)
//
//     // Create pie generator
//     const pie = d3
//         .pie()
//         .value((d) => d.value)
//         .sort(null)
//
// // Create arc generator for donut chart
//     const arc = d3
//         .arc()
//         .innerRadius(radius * 0.5) // Create hole in center
//         .outerRadius(radius)
//
//
//     // Create hover arc (slightly larger)
//     const arcHover = d3
//         .arc()
//         .innerRadius(radius * 0.5) // Same inner radius
//         .outerRadius(radius + 10)
//
// // Generate pie data
//     const pieData = pie(data)
//
// // Create pie slices
//     const slices = g.selectAll(".slice").data(pieData).enter().append("g").attr("class", "slice")
//
//
//     // Add paths for pie slices
//     slices
//         .append("path")
//         .attr("d", arc)
//         .attr("fill", (d) => color(d.data.label))
//         .attr("stroke", "#ffffff")
//         .attr("stroke-width", 2)
//         .on("mouseover", function (event, d) {
//             d3.select(this).transition().duration(200).attr("d", arcHover)
//
//             // Update center text on hover
//             d3.select("#center-text").text(`${d.data.label}: ${d.data.value}`)
//         })
//         .on("mouseout", function (event, d) {
//             d3.select(this).transition().duration(200).attr("d", arc)
//
//             // Reset center text
//             d3.select("#center-text").text(`Total: ${sum}`)
//         })
//         .on("click", function (event, d) {
//             const currentPath = d3.select(this)
//             const currentD = currentPath.attr("d")
//             const isExpanded = currentD === arcHover(d)
//
//             currentPath
//                 .transition()
//                 .duration(300)
//                 .attr("d", isExpanded ? arc : arcHover)
//         })
//
// // Add labels on slices
//     slices
//         .append("text")
//         .attr("transform", (d) => `translate(${arc.centroid(d)})`)
//         .attr("text-anchor", "middle")
//         .attr("font-size", "14px")
//         .attr("font-weight", "bold")
//         .attr("fill", "white")
//         .text((d) => `${d.data.value}%`)
//
// // Add background circle for center
//     g.append("circle")
//         .attr("r", radius * 0.5)
//         .attr("fill", "white")
//         .attr("stroke", "#e5e7eb")
//         .attr("stroke-width", 2)
//
// // Add center text showing sum
//     g.append("text").attr("id", "center-text").text(`Total: ${sum}`)
//
//     const legend = d3.select("#legend-pie")
//
//
//     data.forEach((d) => {
//         const legendItem = legend.append("div").attr("class", "legend-item")
//
//         legendItem.append("div").attr("class", "legend-color").style("background-color", color(d.label))
//
//         legendItem.append("span").attr("class", "legend-text").text(`${d.label}: ${d.value}%`)
//     })
//
//     // Add some entrance animation
//     slices
//         .select("path")
//         .style("opacity", 0)
//         .transition()
//         .duration(800)
//         .delay((d, i) => i * 200)
//         .style("opacity", 1)
//         .attrTween("d", (d) => {
//             const interpolate = d3.interpolate({startAngle: 0, endAngle: 0}, d)
//             return (t) => arc(interpolate(t))
//         })
//
// // Animate center text
//     d3.select("#center-text").style("opacity", 0).transition().duration(800).delay(600).style("opacity", 1)
//
// }

// function render_chart_sum_bar(results) {
//
//     console.log(results)
//
//     const group_label = jQuery('#group').find(":selected").text()
//
//     let updated_version = 0
//     let first_version = 0
//
//     if (results.length > 1) {
//         results.forEach(item => {
//             updated_version += item.updated_version
//             first_version += item.first_version
//         })
//     } else {
//         updated_version = results[0].updated_version
//         first_version = results[0].first_version
//     }
//
//
// // Parse the Data
//     let data = [
//         {
//             "group": "banana",
//             "updated_version": "12",
//             "first_version": "1",
//         },
//         {
//             "group": "poacee",
//             "updated_version": "6",
//             "first_version": "6",
//         },
//         {
//             "group": "sorgho",
//             "updated_version": "11",
//             "first_version": "28",
//         },
//         {
//             "group": "triticum",
//             "updated_version": "19",
//             "first_version": "6",
//         }
//     ]
//
//
//     let margin = {top: 10, right: 30, bottom: 20, left: 50},
//
//         width = 460 - margin.left - margin.right,
//         height = 400 - margin.top - margin.bottom;
//
//     let svg = d3.select("#chart-sum-bar")
//         .append("svg")
//         .attr("width", width + margin.left + margin.right)
//         .attr("height", height + margin.top + margin.bottom)
//         .append("g")
//         .attr("transform",
//             "translate(" + margin.left + "," + margin.top + ")");
//
//
//     let subgroups = ['updated_version', 'first_version']
//
//     let groups = d3.map(data, function (d) {
//         return (d.group)
//     }).keys()
//
//     let x = d3.scaleBand()
//         .domain(groups)
//         .range([0, width])
//         .padding([0.2])
//     svg.append("g")
//         .attr("transform", "translate(0," + height + ")")
//         .call(d3.axisBottom(x).tickSizeOuter(0));
//
//
//     // Add Y axis
//     let y = d3.scaleLinear()
//         .domain([0, 60])
//         .range([height, 0]);
//     svg.append("g")
//         .call(d3.axisLeft(y));
//
//     // color palette = one color per subgroup
//     let color = d3.scaleOrdinal()
//         .domain(subgroups)
//         .range(['#BDD7EE', '#377eb8'])
//
//     //stack the data? --> stack per subgroup
//     let stackedData = d3.stack()
//         .keys(subgroups)
//         (data)
//
//     // Show the bars
//     svg.append("g")
//         .selectAll("g")
//         // Enter in the stack data = loop key per key = group per group
//         .data(stackedData)
//         .enter().append("g")
//         .attr("fill", function (d) {
//             return color(d.key);
//         })
//         .selectAll("rect")
//         // enter a second time = loop subgroup per subgroup to add all rectangles
//         .data(function (d) {
//             return d;
//         })
//         .enter().append("rect")
//         .attr("x", function (d) {
//             return x(d.data.group);
//         })
//         .attr("y", function (d) {
//             return y(d[1]);
//         })
//         .attr("height", function (d) {
//             return y(d[0]) - y(d[1]);
//         })
//         .attr("width", x.bandwidth())
//
// }

//
// function render_chart(results) {
//
//
//     const group = jQuery('#group').find(":selected").text()
//
//     let updated_version = 0
//     let first_version = 0
//
//     if (results.length > 1){
//         results.forEach(item => {
//             console.log(item)
//             updated_version += item.updated_version
//             first_version += item.first_version
//         })
//     } else {
//             updated_version = results[0].updated_version
//             first_version =  results[0].first_version
//     }
//
//     console.log(updated_version)
//     console.log(first_version)
//
//     // 1) For now static data
//     const data = [
//         // {year: "2020", Delft: 340, Eindhoven: 40, Twente: 30, Wageningen: 50, Other: 280},
//         {year: "2020", "First Version": first_version, "Updated Version": updated_version, },
//         // {year: "2021", Delft: 435, Eindhoven: 45, Twente: 120, Wageningen: 140, Other: 245},
//         // {year: "2022", Delft: 525, Eindhoven: 42, Twente: 60, Wageningen: 90, Other: 245},
//         // {year: "2023", Delft: 680, Eindhoven: 78, Twente: 100, Wageningen: 140, Other: 180}
//     ];
//
//     // 2) Configuration & dimensions for the chart
//     const margin = {top: 40, right: 20, bottom: 100, left: 50};
//     const width = 800 - margin.left - margin.right;
//     const height = 500 - margin.top - margin.bottom;
//
//     // 3) Keys & color scale
//     const keys = Object.keys(data[0]).filter(k => k !== "year");
//     const color = d3.scaleOrdinal()
//         .domain(keys)
//         .range(["#00A6D6", "#C72125", "#1E2328", "#008A00", "#f4c300"]);
//
//     // 4) Scales
//     const x0 = d3.scaleBand()
//         .domain(data.map(d => d.year))
//         .range([0, width])
//         .paddingInner(0.1);
//
//     const x1 = d3.scaleBand()
//         .domain(keys)
//         .range([0, x0.bandwidth()])
//         .padding(0.05);
//
//     const y = d3.scaleLinear()
//         .domain([0, d3.max(data, d => d3.max(keys, key => d[key]))])
//         .nice()
//         .range([height, 0]);
//
//     // 5) SVG container
//     const svg = d3.select("#chart")
//         .append("svg")
//         .attr("width", width + margin.left + margin.right)
//         .attr("height", height + margin.top + margin.bottom)
//         .append("g")
//         .attr("transform", `translate(${margin.left},${margin.top})`);
//
//     // 6) X & Y axes
//     svg.append("g")
//         .attr("class", "axis")
//         .attr("transform", `translate(0,${height})`)
//         .call(d3.axisBottom(x0));
//
//     svg.append("g")
//         .attr("class", "axis")
//         .call(d3.axisLeft(y).ticks(5));
//
//
//     // 7) Bars
//     svg.selectAll("g.year")
//         .data(data)
//         .join("g")
//         .attr("class", "year")
//         .attr("transform", d => `translate(${x0(d.year)},0)`)
//         .selectAll("rect")
//         .data(d => keys.map(key => ({key: key, value: d[key]})))
//         .join("rect")
//         .attr("x", d => x1(d.key))
//         .attr("y", d => y(d.value))
//         .attr("width", x1.bandwidth())
//         .attr("height", d => height - y(d.value))
//         .attr("fill", d => color(d.key))
//         .append("title")               // hover tooltip
//         .text(d => `${d.key}: ${d.value}`);
//
//     // 8) Chart title
//     svg.append("text")
//         .attr("x", width / 2)
//         .attr("y", -20)
//         .attr("text-anchor", "middle")
//         .style("font-size", "18px")
//         .style("font-weight", "bold")
//         .text(`Number of datasets (${group})`);
//
//     // 9) Legend
//     const legendY = height + 40;     // Position is 40px below the chart area
//     const legend = svg.append("g")
//         .attr("class", "legend")
//         .attr("transform", `translate(0, ${legendY})`);
//
//     // --- 3) Use a band scale to distribute keys evenly:
//     const legendX = d3.scaleBand()
//         .domain(keys)              // your array ["Delft","Eindhoven",…]
//         .range([0, width])         // full chart width
//         .padding(0.2);             // space between items
//
//     legend.selectAll("g")
//         .data(keys)
//         .join("g")
//         .attr("transform", d => `translate(${legendX(d)},0)`)
//         .call(g => {
//             g.append("rect")
//                 .attr("width", 15)
//                 .attr("height", 15)
//                 .attr("fill", d => color(d));
//             g.append("text")
//                 .attr("x", 20)
//                 .attr("y", 12)
//                 .text(d => d);
//         });
// }


// function render_chart(results) {
//
//
//     const group = jQuery('#group').find(":selected").text()
//
//     let updated_version = 0
//     let first_version = 0
//
//     if (results.length > 1) {
//         results.forEach(item => {
//             updated_version += item.updated_version
//             first_version += item.first_version
//         })
//     } else {
//         updated_version = results[0].updated_version
//         first_version = results[0].first_version
//     }
//
//     // 1) For now static data
//     const data = [
//         // {year: "2020", Delft: 340, Eindhoven: 40, Twente: 30, Wageningen: 50, Other: 280},
//         {year: "2020", "first_version": first_version, "updated_version": updated_version,},
//         // {year: "2021", Delft: 435, Eindhoven: 45, Twente: 120, Wageningen: 140, Other: 245},
//         // {year: "2022", Delft: 525, Eindhoven: 42, Twente: 60, Wageningen: 90, Other: 245},
//         // {year: "2023", Delft: 680, Eindhoven: 78, Twente: 100, Wageningen: 140, Other: 180}
//     ];
//
//     // 2) Configuration & dimensions for the chart
//     const margin = {top: 40, right: 20, bottom: 100, left: 50};
//     const width = 800 - margin.left - margin.right;
//     const height = 500 - margin.top - margin.bottom;
//
//     // 3) Keys & color scale
//     const keys = Object.keys(data[0]).filter(k => k !== "year");
//     const color = d3.scaleOrdinal()
//         .domain(keys)
//         .range(["#00A6D6", "#C72125", "#1E2328", "#008A00", "#f4c300"]);
//
//     // 4) Scales
//     const x0 = d3.scaleBand()
//         .domain(data.map(d => d.year))
//         .range([0, width])
//         .paddingInner(0.1);
//
//     const x1 = d3.scaleBand()
//         .domain(keys)
//         .range([0, x0.bandwidth()])
//         .padding(0.05);
//
//     const y = d3.scaleLinear()
//         .domain([0, d3.max(data, d => d3.max(keys, key => d[key]))])
//         .nice()
//         .range([height, 0]);
//
//     // 5) SVG container
//     const svg = d3.select("#chart")
//         .append("svg")
//         .attr("width", width + margin.left + margin.right)
//         .attr("height", height + margin.top + margin.bottom)
//         .append("g")
//         .attr("transform", `translate(${margin.left},${margin.top})`);
//
//     // 6) X & Y axes
//     svg.append("g")
//         .attr("class", "axis")
//         .attr("transform", `translate(0,${height})`)
//         .call(d3.axisBottom(x0));
//
//     svg.append("g")
//         .attr("class", "axis")
//         .call(d3.axisLeft(y).ticks(5));
//
//
//     // 7) Bars
//     svg.selectAll("g.year")
//         .data(data)
//         .join("g")
//         .attr("class", "year")
//         .attr("transform", d => `translate(${x0(d.year)},0)`)
//         .selectAll("rect")
//         .data(d => keys.map(key => ({key: key, value: d[key]})))
//         .join("rect")
//         .attr("x", d => x1(d.key))
//         .attr("y", d => y(d.value))
//         .attr("width", x1.bandwidth())
//         .attr("height", d => height - y(d.value))
//         .attr("fill", d => color(d.key))
//         .append("title")               // hover tooltip
//         .text(d => `${d.key}: ${d.value}`);
//
//     // 8) Chart title
//     svg.append("text")
//         .attr("x", width / 2)
//         .attr("y", -20)
//         .attr("text-anchor", "middle")
//         .style("font-size", "18px")
//         .style("font-weight", "bold")
//         .text(`Number of datasets (${group})`);
//
//     // 9) Legend
//     const legendY = height + 40;     // Position is 40px below the chart area
//     const legend = svg.append("g")
//         .attr("class", "legend")
//         .attr("transform", `translate(0, ${legendY})`);
//
//     // --- 3) Use a band scale to distribute keys evenly:
//     const legendX = d3.scaleBand()
//         .domain(keys)              // your array ["Delft","Eindhoven",…]
//         .range([0, width])         // full chart width
//         .padding(0.2);             // space between items
//
//     legend.selectAll("g")
//         .data(keys)
//         .join("g")
//         .attr("transform", d => `translate(${legendX(d)},0)`)
//         .call(g => {
//             g.append("rect")
//                 .attr("width", 15)
//                 .attr("height", 15)
//                 .attr("fill", d => color(d));
//             g.append("text")
//                 .attr("x", 20)
//                 .attr("y", 12)
//                 .text(d => d);
//         });
// }


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

    if ("start_date" in url_params && typeof (url_params["start_date"]) === "string" && url_params["start_date"].length > 0) {
        url_params["start_date"] = new Date(url_params["start_date"]).toISOString();
    }

    if ("end_date" in url_params && typeof (url_params["end_date"]) === "string" && url_params["end_date"].length > 0) {
        url_params["end_date"] = new Date(url_params["end_date"]).toISOString();
    }

    return jQuery.ajax({
        url: "/v3/admin/operational-statistics",
        type: "POST",
        contentType: "application/json",
        accept: "application/json",
        data: JSON.stringify(url_params),
        dataType: "json"
    }).done(function (response) {
        const results = get_results_by_featured_groups(response)
        console.log(response)
        // render_chart(results);
        // render_chart_sum_bar(results)
        // render_chart_pie(results)

        createCharts()

        // createDonutChart()
        // createBarChart()
        // createStackedChart()
        // createProgressChart()
        // createGaugeChart()
        // createHorizontalBarChart()
        // createAreaChart()
        // createRadialChart()
        // createWaterfallChart()
        // createTreemapChart()


    }).fail(function (response) {
        console.log("fails", response)
    });
}

function get_results_by_featured_groups(data) {

    let featured_results = []
    let featured_results_map = new Map()


    data.forEach(item => {
        let f_group, f_group_id

        featured_groups_list.forEach(featured_group => {
            if (featured_group.value.includes(item.group_id)) {
                f_group = featured_group.label
                f_group_id = featured_group.id
            }
        })

        const featured_result = {
            ...item,
            featured_group: {
                id: f_group_id,
                label: f_group,
            },
        }

        if (!featured_results_map.has(f_group_id)) {
            const is_first_version = item.is_first_version === 1
            featured_results_map.set(f_group_id, {
                featured_group_id: f_group_id,
                featured_group_label: f_group,
                results_from_group_ids: [item.group_id],
                first_version: is_first_version ? item.datasets : 0,
                updated_version: !is_first_version ? item.datasets : 0
            });
        } else {
            const is_first_version = item.is_first_version === 1
            const previous = featured_results_map.get(f_group_id)
            featured_results_map.set(f_group_id, {
                ...previous,
                results_from_group_ids: [...previous.results_from_group_ids, item.group_id],
                first_version: is_first_version ? (previous.first_version + item.datasets) : previous.first_version,
                updated_version: !is_first_version ? (previous.updated_version + item.datasets) : previous.updated_version,
            });
        }

        featured_results.push(featured_result)
    })

    const values = Array.from(featured_results_map.values());
    // console.log("final values", values)
    return values

    // return featured_results
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
        featured_groups_list = featured_groups
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
