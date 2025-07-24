function createCharts() {
    const dataModel = [
        {
            label: "Delft",
            datasets: [
                {
                    year: "2020",
                    new: 200,
                    revisions: 20,
                },
                {
                    year: "2021",
                    new: 210,
                    revisions: 21,
                },
                {
                    year: "2022",
                    new: 220,
                    revisions: 22,
                },
                {
                    year: "2023",
                    new: 300,
                    revisions: 3,
                },
                {
                    year: "2024",
                    new: 400,
                    revisions: 40,
                },
                {
                    year: "2025",
                    new: 250,
                    revisions: 50,
                },
            ],
        },
    ]

    // Extract data for Delft
    const delftData = dataModel[0].datasets

    // Calculate totals
    const totalNew = delftData.reduce((sum, d) => sum + d.new, 0)
    const totalRevisions = delftData.reduce((sum, d) => sum + d.revisions, 0)
    const grandTotal = totalNew + totalRevisions

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")

    // Stats Grid
    function createStatsGrid() {
        const container = d3.select("#stats-grid")

        const statsGrid = container.append("div").attr("class", "stats-grid")

        // New total
        statsGrid
            .append("div")
            .attr("class", "stat-item new")
            .html(`<div class="stat-value">${totalNew.toLocaleString()}</div><div class="stat-label">Total New</div>`)

        // Revisions total
        statsGrid
            .append("div")
            .attr("class", "stat-item revisions")
            .html(
                `<div class="stat-value">${totalRevisions.toLocaleString()}</div><div class="stat-label">Total Revisions</div>`,
            )

        // Grand total
        statsGrid
            .append("div")
            .attr("class", "stat-item total")
            .html(`<div class="stat-value">${grandTotal.toLocaleString()}</div><div class="stat-label">Grand Total</div>`)

        // Add animation
        statsGrid
            .selectAll(".stat-value")
            .style("opacity", 0)
            .transition()
            .duration(800)
            .delay((d, i) => i * 200)
            .style("opacity", 1)
    }

    // Donut Chart - Total of all years
    function createDonutChart() {
        const width = 400
        const height = 300
        const radius = Math.min(width, height) / 2 - 20

        const svg = d3.select("#donut-chart").append("svg").attr("width", width).attr("height", height)

        const g = svg.append("g").attr("transform", `translate(${width / 2}, ${height / 2})`)

        const color = d3.scaleOrdinal().range(["#3b82f6", "#BDD7EE"])

        const pie = d3
            .pie()
            .value((d) => d.value)
            .sort(null)

        const arc = d3
            .arc()
            .innerRadius(radius * 0.5)
            .outerRadius(radius)

        const arcHover = d3
            .arc()
            .innerRadius(radius * 0.5)
            .outerRadius(radius + 10)

        const pieData = pie([
            {label: "New", value: totalNew},
            {label: "Revisions", value: totalRevisions},
        ])

        const slices = g.selectAll(".slice").data(pieData).enter().append("g").attr("class", "slice")

        slices
            .append("path")
            .attr("d", arc)
            .attr("fill", (d, i) => color(i))
            .attr("stroke", "white")
            .attr("stroke-width", 2)
            .style("cursor", "pointer")
            .on("mouseover", function (event, d) {
                d3.select(this).transition().duration(200).attr("d", arcHover)
                d3.select("#center-text").text(`${d.data.label}: ${d.data.value.toLocaleString()}`)
            })
            .on("mouseout", function (event, d) {
                d3.select(this).transition().duration(200).attr("d", arc)
                d3.select("#center-text").text(`Total: ${grandTotal.toLocaleString()}`)
            })

        // Center circle and text
        g.append("circle")
            .attr("r", radius * 0.5)
            .attr("fill", "white")
            .attr("stroke", "#e2e8f0")
            .attr("stroke-width", 2)

        g.append("text")
            .attr("id", "center-text")
            .attr("text-anchor", "middle")
            .attr("dy", "0.35em")
            .attr("font-size", "16px")
            .attr("font-weight", "bold")
            .attr("fill", "#1f2937")
            .text(`Total: ${grandTotal.toLocaleString()}`)

        // Add legend
        const legend = d3.select("#donut-chart").append("div").attr("class", "legend")

        const legendData = [
            {label: "New", color: "#3b82f6", value: totalNew},
            {label: "Revisions", color: "#BDD7EE", value: totalRevisions},
        ]

        legendData.forEach((d) => {
            const legendItem = legend.append("div").attr("class", "legend-item")

            legendItem.append("div").attr("class", "legend-color").style("background-color", d.color)

            legendItem.append("span").text(`${d.label}: ${d.value.toLocaleString()}`)
        })
    }

    // Time Series Line Chart
    function createLineChart() {
        const margin = {top: 20, right: 80, bottom: 40, left: 60}
        const width = 500 - margin.left - margin.right
        const height = 300 - margin.bottom - margin.top

        const svg = d3
            .select("#line-chart")
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)

        const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

        const x = d3
            .scalePoint()
            .domain(delftData.map((d) => d.year))
            .range([0, width])

        const y = d3
            .scaleLinear()
            .domain([0, d3.max(delftData, (d) => Math.max(d.new, d.revisions))])
            .range([height, 0])

        // Create lines
        const newLine = d3
            .line()
            .x((d) => x(d.year))
            .y((d) => y(d.new))
            .curve(d3.curveMonotoneX)

        const revisionsLine = d3
            .line()
            .x((d) => x(d.year))
            .y((d) => y(d.revisions))
            .curve(d3.curveMonotoneX)

        // Add axes
        g.append("g").attr("class", "axis").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x))

        g.append("g").attr("class", "axis").call(d3.axisLeft(y))

        // Add lines
        g.append("path").datum(delftData).attr("class", "line new").attr("d", newLine)

        g.append("path").datum(delftData).attr("class", "line revisions").attr("d", revisionsLine)

        // Add dots for new
        g.selectAll(".dot-new")
            .data(delftData)
            .enter()
            .append("circle")
            .attr("class", "dot")
            .attr("cx", (d) => x(d.year))
            .attr("cy", (d) => y(d.new))
            .attr("r", 4)
            .attr("fill", "#3b82f6")
            .style("cursor", "pointer")
            .on("mouseover", (event, d) => {
                tooltip.transition().duration(200).style("opacity", 0.9)
                tooltip
                    .html(`${d.year}<br/>New: ${d.new.toLocaleString()}`)
                    .style("left", event.pageX + 10 + "px")
                    .style("top", event.pageY - 28 + "px")
            })
            .on("mouseout", () => {
                tooltip.transition().duration(500).style("opacity", 0)
            })

        // Add dots for revisions
        g.selectAll(".dot-revisions")
            .data(delftData)
            .enter()
            .append("circle")
            .attr("class", "dot")
            .attr("cx", (d) => x(d.year))
            .attr("cy", (d) => y(d.revisions))
            .attr("r", 4)
            .attr("fill", "#BDD7EE")
            .style("cursor", "pointer")
            .on("mouseover", (event, d) => {
                tooltip.transition().duration(200).style("opacity", 0.9)
                tooltip
                    .html(`${d.year}<br/>Revisions: ${d.revisions.toLocaleString()}`)
                    .style("left", event.pageX + 10 + "px")
                    .style("top", event.pageY - 28 + "px")
            })
            .on("mouseout", () => {
                tooltip.transition().duration(500).style("opacity", 0)
            })

        // Add legend
        const legend = d3.select("#line-chart").append("div").attr("class", "legend")

        const legendData = [
            {label: "New", color: "#3b82f6"},
            {label: "Revisions", color: "#BDD7EE"},
        ]

        legendData.forEach((d) => {
            const legendItem = legend.append("div").attr("class", "legend-item")

            legendItem.append("div").attr("class", "legend-color").style("background-color", d.color)

            legendItem.append("span").text(d.label)
        })
    }

    // Stacked Bar Chart - Per year
    function createStackedChart() {
        const margin = {top: 20, right: 30, bottom: 40, left: 60}
        const width = 500 - margin.left - margin.right
        const height = 300 - margin.bottom - margin.top

        const svg = d3
            .select("#stacked-chart")
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)

        const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

        const keys = ["new", "revisions"]
        const stack = d3.stack().keys(keys)
        const series = stack(delftData)

        const x = d3
            .scaleBand()
            .domain(delftData.map((d) => d.year))
            .range([0, width])
            .padding(0.3)

        const y = d3
            .scaleLinear()
            .domain([0, d3.max(delftData, (d) => d.new + d.revisions)])
            .range([height, 0])

        const color = d3.scaleOrdinal().domain(keys).range(["#3b82f6", "#BDD7EE"])

        g.append("g").attr("class", "axis").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x))

        g.append("g").attr("class", "axis").call(d3.axisLeft(y))

        g.selectAll(".serie")
            .data(series)
            .enter()
            .append("g")
            .attr("class", "serie")
            .attr("fill", (d) => color(d.key))
            .selectAll("rect")
            .data((d) => d)
            .enter()
            .append("rect")
            .attr("x", (d) => x(d.data.year))
            .attr("width", x.bandwidth())
            .attr("y", height)
            .attr("height", 0)
            .style("cursor", "pointer")
            .on("mouseover", function (event, d) {
                const key = d3.select(this.parentNode).datum().key
                const value = d.data[key]
                tooltip.transition().duration(200).style("opacity", 0.9)
                tooltip
                    .html(`${d.data.year}<br/>${key}: ${value.toLocaleString()}`)
                    .style("left", event.pageX + 10 + "px")
                    .style("top", event.pageY - 28 + "px")
            })
            .on("mouseout", () => {
                tooltip.transition().duration(500).style("opacity", 0)
            })
            .transition()
            .duration(800)
            .attr("y", (d) => y(d[1]))
            .attr("height", (d) => y(d[0]) - y(d[1]))

        // Add legend
        const legend = d3.select("#stacked-chart").append("div").attr("class", "legend")

        const legendData = [
            {label: "New", color: "#3b82f6"},
            {label: "Revisions", color: "#BDD7EE"},
        ]

        legendData.forEach((d) => {
            const legendItem = legend.append("div").attr("class", "legend-item")

            legendItem.append("div").attr("class", "legend-color").style("background-color", d.color)

            legendItem.append("span").text(d.label)
        })
    }

    // Bar Chart - Per year comparison
    function createBarChart() {
        const margin = {top: 20, right: 30, bottom: 40, left: 60}
        const width = 500 - margin.left - margin.right
        const height = 300 - margin.bottom - margin.top

        const svg = d3
            .select("#bar-chart")
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)

        const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

        // Flatten data for grouped bars
        const flatData = []
        delftData.forEach((d) => {
            flatData.push({year: d.year, type: "new", value: d.new})
            flatData.push({year: d.year, type: "revisions", value: d.revisions})
        })

        const x0 = d3
            .scaleBand()
            .domain(delftData.map((d) => d.year))
            .range([0, width])
            .padding(0.2)

        const x1 = d3.scaleBand().domain(["new", "revisions"]).range([0, x0.bandwidth()]).padding(0.1)

        const y = d3
            .scaleLinear()
            .domain([0, d3.max(flatData, (d) => d.value)])
            .range([height, 0])

        const color = d3.scaleOrdinal().domain(["new", "revisions"]).range(["#3b82f6", "#BDD7EE"])

        g.append("g").attr("class", "axis").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x0))

        g.append("g").attr("class", "axis").call(d3.axisLeft(y))

        const yearGroups = g
            .selectAll(".year-group")
            .data(delftData)
            .enter()
            .append("g")
            .attr("class", "year-group")
            .attr("transform", (d) => `translate(${x0(d.year)},0)`)

        yearGroups
            .selectAll("rect")
            .data((d) => [
                {type: "new", value: d.new, year: d.year},
                {type: "revisions", value: d.revisions, year: d.year},
            ])
            .enter()
            .append("rect")
            .attr("class", "bar")
            .attr("x", (d) => x1(d.type))
            .attr("width", x1.bandwidth())
            .attr("y", height)
            .attr("height", 0)
            .attr("fill", (d) => color(d.type))
            .style("cursor", "pointer")
            .on("mouseover", (event, d) => {
                tooltip.transition().duration(200).style("opacity", 0.9)
                tooltip
                    .html(`${d.year}<br/>${d.type}: ${d.value.toLocaleString()}`)
                    .style("left", event.pageX + 10 + "px")
                    .style("top", event.pageY - 28 + "px")
            })
            .on("mouseout", () => {
                tooltip.transition().duration(500).style("opacity", 0)
            })
            .transition()
            .duration(800)
            .delay((d, i) => i * 100)
            .attr("y", (d) => y(d.value))
            .attr("height", (d) => height - y(d.value))

        // Add legend
        const legend = d3.select("#bar-chart").append("div").attr("class", "legend")

        const legendData = [
            {label: "New", color: "#3b82f6"},
            {label: "Revisions", color: "#BDD7EE"},
        ]

        legendData.forEach((d) => {
            const legendItem = legend.append("div").attr("class", "legend-item")

            legendItem.append("div").attr("class", "legend-color").style("background-color", d.color)

            legendItem.append("span").text(d.label)
        })
    }

    // Initialize all charts
    createStatsGrid()
    createDonutChart()
    createLineChart()
    createStackedChart()
    createBarChart()
}

