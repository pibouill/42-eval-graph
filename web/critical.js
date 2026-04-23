const svg = d3.select("svg"),
      width = window.innerWidth,
      height = window.innerHeight;

// Add a container for zooming
const container = svg.append("g");

const tooltip = d3.select("body").append("div")
    .attr("class", "tooltip")
    .attr("id", "tooltip");

// Info panel elements
const infoPanel = d3.select("#info-panel");
const panelTitle = d3.select("#panel-title");
const panelContent = d3.select("#panel-content");

const color = d3.scaleOrdinal(d3.schemePastel2);

const simulation = d3.forceSimulation()
    .force("link", d3.forceLink().id(d => d.id).distance(50))
    .force("charge", d3.forceManyBody().strength(-100))
    .force("center", d3.forceCenter(width / 2, height / 2))
	.force("collide", d3.forceCollide().radius(20).iterations(2));

// Helper functions for info panel
function closeInfoPanel() {
	infoPanel.classed("visible", false);
}

function showNodeInfo(d, allData) {
	const login = d.id;
	const group = d.group || 0;
	
	let evalsGiven = 0;
	let evalsReceived = 0;
	let connections = 0;
	let firstEval = null;
	let lastEval = null;
	
	allData.links.forEach(link => {
		const source = link.source.id || link.source;
		const target = link.target.id || link.target;
		if (source === login || target === login) {
			connections++;
			if (source === login) {
				evalsGiven += link.value;
			} else {
				evalsReceived += link.value;
			}
			if (link.first_eval) {
				if (!firstEval || link.first_eval < firstEval) firstEval = link.first_eval;
			}
			if (link.last_eval) {
				if (!lastEval || link.last_eval > lastEval) lastEval = link.last_eval;
			}
		}
	});
	
	panelTitle.text(login);
	panelContent.html(`
		<div class="info-section">
			<div class="info-label">Cluster</div>
			<div class="info-value">Group ${group}</div>
		</div>
		<div class="stats-grid">
			<div class="stat-box">
				<div class="stat-number">${evalsGiven}</div>
				<div class="stat-label">Given</div>
			</div>
			<div class="stat-box">
				<div class="stat-number">${evalsReceived}</div>
				<div class="stat-label">Received</div>
			</div>
			<div class="stat-box">
				<div class="stat-number">${connections}</div>
				<div class="stat-label">Connections</div>
			</div>
		</div>
		${firstEval ? `
		<div class="info-section" style="margin-top: 15px;">
			<div class="info-label">First Evaluation</div>
			<div class="info-value">${firstEval}</div>
		</div>
		` : ''}
		${lastEval ? `
		<div class="info-section">
			<div class="info-label">Last Evaluation</div>
			<div class="info-value">${lastEval}</div>
		</div>
		` : ''}
		<div class="info-section" style="margin-top: 15px;">
			<div class="info-value">
				<a href="https://profile.intra.42.fr/users/${login}" target="_blank">
					View 42 Intra Profile
				</a>
			</div>
		</div>
	`);
	infoPanel.classed("visible", true);
}

function showLinkInfo(d) {
	const source = d.source.id || d.source;
	const target = d.target.id || d.target;
	const value = d.value;
	const firstEval = d.first_eval || 'N/A';
	const lastEval = d.last_eval || 'N/A';
	
	panelTitle.text("Evaluation Link");
	panelContent.html(`
		<div class="info-section">
			<div class="info-label">From</div>
			<div class="info-value">
				<a href="https://profile.intra.42.fr/users/${source}" target="_blank">${source}</a>
			</div>
		</div>
		<div class="info-section">
			<div class="info-label">To</div>
			<div class="info-value">
				<a href="https://profile.intra.42.fr/users/${target}" target="_blank">${target}</a>
			</div>
		</div>
		<div class="stats-grid">
			<div class="stat-box">
				<div class="stat-number">${value}</div>
				<div class="stat-label">Evaluations</div>
			</div>
		</div>
		${firstEval !== 'N/A' ? `
		<div class="info-section" style="margin-top: 15px;">
			<div class="info-label">First Evaluation</div>
			<div class="info-value">${firstEval}</div>
		</div>
		` : ''}
		${lastEval !== 'N/A' ? `
		<div class="info-section">
			<div class="info-label">Last Evaluation</div>
			<div class="info-value">${lastEval}</div>
		</div>
		` : ''}
	`);
	infoPanel.classed("visible", true);
}

// Close panel when clicking on SVG background
svg.on("click", function(event) {
	if (event.target === svg.node()) {
		closeInfoPanel();
	}
});

// Make closeInfoPanel available globally
window.closeInfoPanel = closeInfoPanel;

d3.json("./data.json").then(function(data) {
    // Filter the links and nodes
    const filteredLinks = data.links.filter(d => d.value > 5);

    // Get a unique set of node IDs from the filtered links
    const filteredNodeIds = new Set();
    filteredLinks.forEach(link => {
        filteredNodeIds.add(link.source.id || link.source);
        filteredNodeIds.add(link.target.id || link.target);
    });

    // Filter the nodes to only include those in filteredNodeIds
    const filteredNodes = data.nodes.filter(node => filteredNodeIds.has(node.id));

    // Define a color scale for the links based on their value
    const colorScale = d3.scaleLinear()
        .domain([5, d3.max(filteredLinks, d => d.value)]) // From 5 to the max value
        .range(["#ffcccc", "#ff0000"]); // Light red to intense red

	const opacityScale = d3.scaleLinear()
		.domain([5, d3.max(filteredLinks, d => d.value)])
		.range([0.1, 1]);

    const link = container.append("g")
        .attr("class", "links")
        .selectAll("line")
        .data(filteredLinks)
        .enter().append("line")
        .attr("class", (d) => `link`)
        .attr("stroke-width", d => Math.sqrt(d.value))
        .attr("stroke", d => colorScale(d.value))
		.attr("stroke-opacity", d => opacityScale(d.value))
        .on("mouseover", function(event, d) {
            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(`${d.source.id} ↔ ${d.target.id}<br/>${d.value} evaluations`)
                .style("left", (event.pageX + 5) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        })
        .on("click", function(event, d) {
            event.stopPropagation();
            showLinkInfo(d);
        });

    const node = container.append("g")
        .attr("class", "nodes")
        .selectAll("g")
        .data(filteredNodes)
        .enter().append("g")
        .attr("class", "node")
        .on("mouseover", function(event, d) {
            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(`${d.id}`)
                .style("left", (event.pageX + 5) + "px")
                .style("top", (event.pageY - 28) + "px");
            d3.select(this).select(".label").style("visibility", "visible");
        })
        .on("mouseout", function() {
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
            d3.select(this).select(".label").style("visibility", "hidden");
        })
        .on("click", function(event, d) {
            event.stopPropagation();
            showNodeInfo(d, data);
        });

    node.append("circle")
        .attr("r", 5)
        .attr("fill", d => color(d.group));

    node.append("text")
        .attr("class", "label")
        .attr("x", 8)
        .attr("y", 3)
        .text(d => d.id);

    node.call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    simulation
        .nodes(filteredNodes)
        .on("tick", ticked);

    simulation.force("link")
        .links(filteredLinks);

    function ticked() {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node
            .attr("transform", d => `translate(${d.x},${d.y})`);
    }

    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = d.x;
        d.fy = d.y;
    }

    // Function to filter and highlight nodes and links
    function filterNodes() {
        const isChecked = d3.select("#filterCheckbox").property("checked");

        if (isChecked) {
            // Hide nodes without any link with value > 5
            node.style("opacity", function(d) {
                const hasHighValueLink = filteredLinks.some(link =>
                    (link.source.id === d.id || link.target.id === d.id) && link.value > 5
                );
                return hasHighValueLink ? 1 : 0;
            });

            // Hide links with value <= 5
            link.style("opacity", d => d.value > 5 ? 1 : 0);
        } else {
            // Show all nodes and links
            node.style("opacity", 1);
            link.style("opacity", 1);
        }
    }

    function searchNode() {
        const searchValue = d3.select("#searchBox").property("value").toLowerCase();
        const foundNode = filteredNodes.find(node => node.id.toLowerCase() === searchValue);

        if (foundNode) {
            node.select("circle")
                .attr("r", 5)
                .attr("fill", d => color(d.group));

            d3.select(node.nodes().find(n => n.__data__.id === foundNode.id))
                .select("circle")
                .attr("r", 10)
                .attr("fill", "orange");

            const scale = 2;
            const translate = [width / 2 - scale * foundNode.x, height / 2 - scale * foundNode.y];
            container.transition()
                .duration(750)
                .attr("transform", `translate(${translate})scale(${scale})`);
        } else {
            alert("Student not found");
        }
    }

    // Add event listener to the filter checkbox
    d3.select("#filterCheckbox").on("change", filterNodes);

    // Add event listener to the search box
    d3.select("#searchBox").on("keyup", function(event) {
        if (event.key === "Enter") {
            searchNode();
        }
    });
});

// Apply zoom and pan behavior
svg.call(d3.zoom()
    .extent([[0, 0], [width, height]])
    .scaleExtent([0.1, 8])
    .on("zoom", zoomed));

function zoomed(event) {
    container.attr("transform", event.transform);
}

// Resize SVG when window is resized
window.addEventListener('resize', function() {
    svg.attr('width', window.innerWidth)
       .attr('height', window.innerHeight);
    simulation.force("center", d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2));
    simulation.alpha(1).restart();
});

