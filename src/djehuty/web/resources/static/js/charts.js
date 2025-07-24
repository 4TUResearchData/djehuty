const dataModel = [
    {
        label: "Delft",
        datasets: [
            {
            "year": "2020",
            "new": 200,
            "revisions": 20
            },
            {
            "year": "2021",
            "new": 210,
            "revisions": 21
            },
            {
            "year": "2022",
            "new": 220,
            "revisions": 22
            },
            {
            "year": "2023",
            "new": 300,
            "revisions": 3
            },
            {
            "year": "2024",
            "new": 400,
            "revisions": 40
            },
            {
            "year": "2025",
            "new": 250,
            "revisions": 50
            },
        ]
    }
];

// Chart 1: Donut Chart
function createDonutChart() {
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = ((data["Updated Versions"] / total) * 100).toFixed(1)

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const width = 400
    const height = 300
    const radius = Math.min(width, height) / 2 - 20

    const svg = d3.select("#donut-chart").append("svg").attr("width", width).attr("height", height)

    const g = svg.append("g").attr("transform", `translate(${width / 2}, ${height / 2})`)

    const color = d3.scaleOrdinal().range(["#3b82f6", "#ef4444"])

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
        {label: "Updated Versions", value: data["Updated Versions"]},
        {label: "First Versions", value: data["First Versions"]},
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
            $("#center-text").text(`${d.data.label}: ${d.data.value}`)
        })
        .on("mouseout", function (event, d) {
            d3.select(this).transition().duration(200).attr("d", arc)
            $("#center-text").text(`Total: ${total}`)
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
        .attr("font-size", "24px")
        .attr("font-weight", "bold")
        .attr("fill", "#1f2937")
        .text(`Total: ${total}`)
}

// Chart 2: Bar Chart
function createBarChart() {
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = ((data["Updated Versions"] / total) * 100).toFixed(1)

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const margin = {top: 20, right: 30, bottom: 40, left: 60}
    const width = 400 - margin.left - margin.right
    const height = 300 - margin.bottom - margin.top

    const svg = d3
        .select("#bar-chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

    const chartData = [
        {category: "Updated", value: data["Updated Versions"]},
        {category: "First", value: data["First Versions"]},
    ]

    const x = d3
        .scaleBand()
        .rangeRound([0, width])
        .padding(0.3)
        .domain(chartData.map((d) => d.category))

    const y = d3
        .scaleLinear()
        .rangeRound([height, 0])
        .domain([0, d3.max(chartData, (d) => d.value)])

    const color = d3.scaleOrdinal().range(["#3b82f6", "#ef4444"])

    g.append("g").attr("class", "axis").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x))

    g.append("g").attr("class", "axis").call(d3.axisLeft(y))

    g.selectAll(".bar")
        .data(chartData)
        .enter()
        .append("rect")
        .attr("class", "bar")
        .attr("x", (d) => x(d.category))
        .attr("width", x.bandwidth())
        .attr("y", height)
        .attr("height", 0)
        .attr("fill", (d, i) => color(i))
        .style("cursor", "pointer")
        .on("mouseover", (event, d) => {
            tooltip.transition().duration(200).style("opacity", 0.9)
            tooltip
                .html(`${d.category} Versions: ${d.value}`)
                .style("left", event.pageX + 10 + "px")
                .style("top", event.pageY - 28 + "px")
        })
        .on("mouseout", (d) => {
            tooltip.transition().duration(500).style("opacity", 0)
        })
        .transition()
        .duration(800)
        .attr("y", (d) => y(d.value))
        .attr("height", (d) => height - y(d.value))

    // Add value labels on bars
    g.selectAll(".label")
        .data(chartData)
        .enter()
        .append("text")
        .attr("class", "label")
        .attr("x", (d) => x(d.category) + x.bandwidth() / 2)
        .attr("y", (d) => y(d.value) - 5)
        .attr("text-anchor", "middle")
        .attr("font-size", "12px")
        .attr("font-weight", "bold")
        .attr("fill", "#374151")
        .text((d) => d.value)
}

// Chart 3: Stacked Bar Chart
function createStackedChart() {
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = ((data["Updated Versions"] / total) * 100).toFixed(1)

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const margin = {top: 20, right: 30, bottom: 40, left: 60}
    const width = 400 - margin.left - margin.right
    const height = 300 - margin.bottom - margin.top

    const svg = d3
        .select("#stacked-chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

    const stackData = [
        {
            category: data["Label"],
            "Updated Versions": data["Updated Versions"],
            "First Versions": data["First Versions"],
        },
    ]

    const keys = ["First Versions", "Updated Versions"]
    const stack = d3.stack().keys(keys)
    const series = stack(stackData)

    const x = d3
        .scaleBand()
        .rangeRound([0, width])
        .padding(0.3)
        .domain(stackData.map((d) => d.category))

    const y = d3.scaleLinear().rangeRound([height, 0]).domain([0, total])

    const color = d3.scaleOrdinal().domain(keys).range(["#ef4444", "#3b82f6"])

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
        .attr("x", (d) => x(d.data.category))
        .attr("width", x.bandwidth())
        .attr("y", height)
        .attr("height", 0)
        .style("cursor", "pointer")
        .on("mouseover", function (event, d) {
            const key = d3.select(this.parentNode).datum().key
            const value = d.data[key]
            tooltip.transition().duration(200).style("opacity", 0.9)
            tooltip
                .html(`${key}: ${value}`)
                .style("left", event.pageX + 10 + "px")
                .style("top", event.pageY - 28 + "px")
        })
        .on("mouseout", (d) => {
            tooltip.transition().duration(500).style("opacity", 0)
        })
        .transition()
        .duration(800)
        .attr("y", (d) => y(d[1]))
        .attr("height", (d) => y(d[0]) - y(d[1]))
}

// Chart 4: Progress Chart
function createProgressChart() {
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = ((data["Updated Versions"] / total) * 100).toFixed(1)

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const container = d3.select("#progress-chart")

    // Stats grid
    const statsGrid = container.append("div").attr("class", "stats-grid")

    statsGrid
        .append("div")
        .attr("class", "stat-item")
        .html(`<div class="stat-value">${data["Updated Versions"]}</div><div class="stat-label">Updated</div>`)

    statsGrid
        .append("div")
        .attr("class", "stat-item")
        .html(`<div class="stat-value">${data["First Versions"]}</div><div class="stat-label">First Versions</div>`)

    // statsGrid
    //     .append("div")
    //     .attr("class", "stat-item")
    //     .html(`<div class="stat-value">${total}</div><div class="stat-label">Total</div>`)

    // // Progress bar
    // const progressContainer = container.append("div").style("margin-top", "2rem")
    //
    // progressContainer
    //     .append("h3")
    //     .style("text-align", "center")
    //     .style("margin-bottom", "1rem")
    //     .style("color", "#374151")
    //     .text(`Update Rate: ${updateRate}%`)
    //
    // const progressBar = progressContainer.append("div").attr("class", "progress-bar")
    //
    // const progressFill = progressBar
    //     .append("div")
    //     .attr("class", "progress-fill")
    //     .style("width", "0%")
    //     .text(`${updateRate}%`)

    // Animate progress bar
    setTimeout(() => {
        progressFill.transition().duration(1500).style("width", `${updateRate}%`)
    }, 500)
}

// Chart 5: Gauge Chart
function createGaugeChart() {

    // Sample data based on your structure
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = (data["Updated Versions"] / total) * 100

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const width = 400
    const height = 300
    const radius = Math.min(width, height) / 2 - 40

    const svg = d3.select("#gauge-chart").append("svg").attr("width", width).attr("height", height)

    const g = svg.append("g").attr("transform", `translate(${width / 2}, ${height / 2 + 20})`)

    // Create gauge background
    const arc = d3
        .arc()
        .innerRadius(radius - 20)
        .outerRadius(radius)
        .startAngle(-Math.PI / 2)
        .endAngle(Math.PI / 2)

    g.append("path").attr("d", arc).attr("fill", "#e2e8f0")

    // Create gauge fill
    const fillArc = d3
        .arc()
        .innerRadius(radius - 20)
        .outerRadius(radius)
        .startAngle(-Math.PI / 2)
        .endAngle(-Math.PI / 2 + (Math.PI * updateRate) / 100)

    g.append("path").attr("d", fillArc).attr("fill", "#3b82f6")

    // Add needle
    const needleAngle = -Math.PI / 2 + (Math.PI * updateRate) / 100
    const needleLength = radius - 30

    g.append("line")
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", needleLength * Math.cos(needleAngle))
        .attr("y2", needleLength * Math.sin(needleAngle))
        .attr("stroke", "#1f2937")
        .attr("stroke-width", 3)

    g.append("circle").attr("r", 5).attr("fill", "#1f2937")

    // Add text
    g.append("text")
        .attr("class", "gauge-text")
        .attr("y", 30)
        .text(`${updateRate.toFixed(1)}%`)

    g.append("text").attr("class", "gauge-label").attr("y", 50).text("Update Rate")

    // Add scale labels
    for (let i = 0; i <= 100; i += 25) {
        const angle = -Math.PI / 2 + (Math.PI * i) / 100
        const x1 = (radius - 15) * Math.cos(angle)
        const y1 = (radius - 15) * Math.sin(angle)
        const x2 = (radius - 5) * Math.cos(angle)
        const y2 = (radius - 5) * Math.sin(angle)

        g.append("line").attr("x1", x1).attr("y1", y1).attr("x2", x2).attr("y2", y2).attr("stroke", "#64748b")

        g.append("text")
            .attr("x", (radius + 10) * Math.cos(angle))
            .attr("y", (radius + 10) * Math.sin(angle))
            .attr("text-anchor", "middle")
            .attr("font-size", "10px")
            .attr("fill", "#64748b")
            .text(`${i}%`)
    }
}

// Chart 6: Horizontal Bar Chart
function createHorizontalBarChart() {

    // Sample data based on your structure
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = (data["Updated Versions"] / total) * 100

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const margin = {top: 20, right: 30, bottom: 40, left: 120}
    const width = 400 - margin.left - margin.right
    const height = 300 - margin.bottom - margin.top

    const svg = d3
        .select("#horizontal-bar-chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

    const chartData = [
        {category: "Updated Versions", value: data["Updated Versions"]},
        {category: "First Versions", value: data["First Versions"]},
    ]

    const x = d3
        .scaleLinear()
        .rangeRound([0, width])
        .domain([0, d3.max(chartData, (d) => d.value)])

    const y = d3
        .scaleBand()
        .rangeRound([0, height])
        .padding(0.3)
        .domain(chartData.map((d) => d.category))

    const color = d3.scaleOrdinal().range(["#3b82f6", "#ef4444"])

    g.append("g").attr("class", "axis").call(d3.axisLeft(y))

    g.append("g").attr("class", "axis").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x))

    g.selectAll(".bar")
        .data(chartData)
        .enter()
        .append("rect")
        .attr("class", "bar")
        .attr("y", (d) => y(d.category))
        .attr("height", y.bandwidth())
        .attr("x", 0)
        .attr("width", 0)
        .attr("fill", (d, i) => color(i))
        .style("cursor", "pointer")
        .on("mouseover", (event, d) => {
            tooltip.transition().duration(200).style("opacity", 0.9)
            tooltip
                .html(`${d.category}: ${d.value}`)
                .style("left", event.pageX + 10 + "px")
                .style("top", event.pageY - 28 + "px")
        })
        .on("mouseout", () => {
            tooltip.transition().duration(500).style("opacity", 0)
        })
        .transition()
        .duration(800)
        .attr("width", (d) => x(d.value))

    // Add value labels
    g.selectAll(".label")
        .data(chartData)
        .enter()
        .append("text")
        .attr("class", "label")
        .attr("x", (d) => x(d.value) + 5)
        .attr("y", (d) => y(d.category) + y.bandwidth() / 2)
        .attr("dy", "0.35em")
        .attr("font-size", "12px")
        .attr("font-weight", "bold")
        .attr("fill", "#374151")
        .text((d) => d.value)
}

// Chart 7: Area Chart
function createAreaChart() {

    // Sample data based on your structure
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = (data["Updated Versions"] / total) * 100

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const margin = {top: 20, right: 30, bottom: 40, left: 60}
    const width = 400 - margin.left - margin.right
    const height = 300 - margin.bottom - margin.top

    const svg = d3
        .select("#area-chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

    const chartData = [
        {category: "First", value: data["First Versions"], x: 0},
        {category: "Updated", value: data["Updated Versions"], x: 1},
    ]

    const x = d3.scaleLinear().rangeRound([0, width]).domain([0, 1])

    const y = d3
        .scaleLinear()
        .rangeRound([height, 0])
        .domain([0, d3.max(chartData, (d) => d.value)])

    const area = d3
        .area()
        .x((d) => x(d.x))
        .y0(height)
        .y1((d) => y(d.value))
        .curve(d3.curveCardinal)

    const line = d3
        .line()
        .x((d) => x(d.x))
        .y((d) => y(d.value))
        .curve(d3.curveCardinal)

    g.append("g")
        .attr("class", "axis")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).tickFormat((d) => (d === 0 ? "First" : "Updated")))

    g.append("g").attr("class", "axis").call(d3.axisLeft(y))

    g.append("path").datum(chartData).attr("class", "area").attr("fill", "#3b82f6").attr("opacity", 0.6).attr("d", area)

    g.append("path")
        .datum(chartData)
        .attr("fill", "none")
        .attr("stroke", "#1d4ed8")
        .attr("stroke-width", 2)
        .attr("d", line)

    // Add dots
    g.selectAll(".dot")
        .data(chartData)
        .enter()
        .append("circle")
        .attr("class", "dot")
        .attr("cx", (d) => x(d.x))
        .attr("cy", (d) => y(d.value))
        .attr("r", 5)
        .attr("fill", "#1d4ed8")
        .style("cursor", "pointer")
        .on("mouseover", (event, d) => {
            tooltip.transition().duration(200).style("opacity", 0.9)
            tooltip
                .html(`${d.category} Versions: ${d.value}`)
                .style("left", event.pageX + 10 + "px")
                .style("top", event.pageY - 28 + "px")
        })
        .on("mouseout", (d) => {
            tooltip.transition().duration(500).style("opacity", 0)
        })
}

// Chart 8: Radial Bar Chart
function createRadialChart() {

    // Sample data based on your structure
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = (data["Updated Versions"] / total) * 100

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const width = 400
    const height = 300
    const radius = Math.min(width, height) / 2 - 40

    const svg = d3.select("#radial-chart").append("svg").attr("width", width).attr("height", height)

    const g = svg.append("g").attr("transform", `translate(${width / 2}, ${height / 2})`)

    const chartData = [
        {category: "Updated", value: data["Updated Versions"]},
        {category: "First", value: data["First Versions"]},
    ]

    const angleScale = d3
        .scaleBand()
        .domain(chartData.map((d) => d.category))
        .range([0, Math.PI])
        .padding(0.1)

    const radiusScale = d3
        .scaleLinear()
        .domain([0, d3.max(chartData, (d) => d.value)])
        .range([20, radius])

    const color = d3.scaleOrdinal().range(["#3b82f6", "#ef4444"])

    chartData.forEach((d, i) => {
        const startAngle = angleScale(d.category)
        const endAngle = startAngle + angleScale.bandwidth()
        const innerRadius = 20
        const outerRadius = radiusScale(d.value)

        const arc = d3.arc().innerRadius(innerRadius).outerRadius(outerRadius).startAngle(startAngle).endAngle(endAngle)

        g.append("path")
            .attr("class", "radial-bar")
            .attr("d", arc)
            .attr("fill", color(i))
            .style("cursor", "pointer")
            .on("mouseover", (event) => {
                tooltip.transition().duration(200).style("opacity", 0.9)
                tooltip
                    .html(`${d.category} Versions: ${d.value}`)
                    .style("left", event.pageX + 10 + "px")
                    .style("top", event.pageY - 28 + "px")
            })
            .on("mouseout", () => {
                tooltip.transition().duration(500).style("opacity", 0)
            })

        // Add labels
        const labelAngle = startAngle + angleScale.bandwidth() / 2
        const labelRadius = outerRadius + 15

        g.append("text")
            .attr("x", labelRadius * Math.cos(labelAngle - Math.PI / 2))
            .attr("y", labelRadius * Math.sin(labelAngle - Math.PI / 2))
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .attr("fill", "#374151")
            .text(d.category)

        g.append("text")
            .attr("x", labelRadius * Math.cos(labelAngle - Math.PI / 2))
            .attr("y", labelRadius * Math.sin(labelAngle - Math.PI / 2) + 15)
            .attr("text-anchor", "middle")
            .attr("font-size", "10px")
            .attr("font-weight", "bold")
            .attr("fill", "#1f2937")
            .text(d.value)
    })
}

// Chart 9: Waterfall Chart
function createWaterfallChart() {

    // Sample data based on your structure
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = (data["Updated Versions"] / total) * 100

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const margin = {top: 20, right: 30, bottom: 40, left: 60}
    const width = 400 - margin.left - margin.right
    const height = 300 - margin.bottom - margin.top

    const svg = d3
        .select("#waterfall-chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`)

    const waterfallData = [
        {
            category: "First Versions",
            value: data["First Versions"],
            cumulative: data["First Versions"],
            type: "positive",
        },
        {
            category: "Updated",
            value: -data["Updated Versions"],
            cumulative: data["First Versions"] - data["Updated Versions"],
            type: "negative",
        },
        {
            category: "Remaining",
            value: data["First Versions"] - data["Updated Versions"],
            cumulative: data["First Versions"] - data["Updated Versions"],
            type: "total",
        },
    ]

    const x = d3
        .scaleBand()
        .rangeRound([0, width])
        .padding(0.3)
        .domain(waterfallData.map((d) => d.category))

    const y = d3
        .scaleLinear()
        .rangeRound([height, 0])
        .domain([0, d3.max(waterfallData, (d) => Math.max(d.value, d.cumulative))])

    const color = d3.scaleOrdinal().domain(["positive", "negative", "total"]).range(["#3b82f6", "#ef4444", "#10b981"])

    g.append("g").attr("class", "axis").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x))

    g.append("g").attr("class", "axis").call(d3.axisLeft(y))

    let cumulative = 0

    waterfallData.forEach((d, i) => {
        let barHeight, barY

        if (d.type === "positive") {
            barHeight = y(0) - y(d.value)
            barY = y(d.value)
            cumulative = d.value
        } else if (d.type === "negative") {
            barHeight = y(0) - y(Math.abs(d.value))
            barY = y(cumulative)
            cumulative += d.value
        } else {
            barHeight = y(0) - y(d.cumulative)
            barY = y(d.cumulative)
        }

        g.append("rect")
            .attr("class", "waterfall-bar")
            .attr("x", x(d.category))
            .attr("width", x.bandwidth())
            .attr("y", barY)
            .attr("height", barHeight)
            .attr("fill", color(d.type))
            .style("cursor", "pointer")
            .on("mouseover", (event) => {
                tooltip.transition().duration(200).style("opacity", 0.9)
                tooltip
                    .html(`${d.category}: ${Math.abs(d.value)}`)
                    .style("left", event.pageX + 10 + "px")
                    .style("top", event.pageY - 28 + "px")
            })
            .on("mouseout", () => {
                tooltip.transition().duration(500).style("opacity", 0)
            })

        // Add value labels
        g.append("text")
            .attr("x", x(d.category) + x.bandwidth() / 2)
            .attr("y", barY - 5)
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .attr("font-weight", "bold")
            .attr("fill", "#374151")
            .text(Math.abs(d.value))
    })
}

// Chart 10: Treemap Chart
function createTreemapChart() {

    // Sample data based on your structure
    const data = {
        "Updated Versions": 183,
        "First Versions": 1224,
        Label: "Other Institutions",
        From: "2023-07-09",
        To: "2025-07-09",
    }

    const total = data["Updated Versions"] + data["First Versions"]
    const updateRate = (data["Updated Versions"] / total) * 100

    // Create tooltip
    const tooltip = d3.select("body").append("div").attr("class", "tooltip")
    const width = 400
    const height = 300

    const svg = d3.select("#treemap-chart").append("svg").attr("width", width).attr("height", height)

    const treemapData = {
        name: "root",
        children: [
            {name: "Updated Versions", value: data["Updated Versions"]},
            {name: "First Versions", value: data["First Versions"]},
        ],
    }

    const root = d3.hierarchy(treemapData).sum((d) => d.value)

    const treemap = d3.treemap().size([width, height]).padding(2)

    treemap(root)

    const color = d3.scaleOrdinal().range(["#3b82f6", "#ef4444"])

    const leaf = svg
        .selectAll("g")
        .data(root.leaves())
        .enter()
        .append("g")
        .attr("transform", (d) => `translate(${d.x0},${d.y0})`)

    leaf
        .append("rect")
        .attr("class", "treemap-rect")
        .attr("width", (d) => d.x1 - d.x0)
        .attr("height", (d) => d.y1 - d.y0)
        .attr("fill", (d, i) => color(i))
        .style("cursor", "pointer")
        .on("mouseover", (event, d) => {
            tooltip.transition().duration(200).style("opacity", 0.9)
            tooltip
                .html(`${d.data.name}: ${d.data.value}`)
                .style("left", event.pageX + 10 + "px")
                .style("top", event.pageY - 28 + "px")
        })
        .on("mouseout", () => {
            tooltip.transition().duration(500).style("opacity", 0)
        })

    leaf
        .append("text")
        .attr("class", "treemap-text")
        .attr("x", (d) => (d.x1 - d.x0) / 2)
        .attr("y", (d) => (d.y1 - d.y0) / 2 - 10)
        .text((d) => d.data.name)

    leaf
        .append("text")
        .attr("class", "treemap-text")
        .attr("x", (d) => (d.x1 - d.x0) / 2)
        .attr("y", (d) => (d.y1 - d.y0) / 2 + 10)
        .attr("font-size", "16px")
        .text((d) => d.data.value)
}

