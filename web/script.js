const svg = d3.select("svg"),
	  width = window.innerWidth,
	  height = window.innerHeight;

// Add a container for zooming
const container = svg.append("g");

const tooltip = d3.select("body").append("div")
	.attr("class", "tooltip");

// Info panel elements
const infoPanel = d3.select("#info-panel");
const panelTitle = d3.select("#panel-title");
const panelContent = d3.select("#panel-content");

const color = d3.scaleOrdinal(d3.schemePastel2);

let criticalThreshold = 5;
let originalData = null;

const simulation = d3.forceSimulation()
	.force("link", d3.forceLink().id(d => d.id))
	.force("charge", d3.forceManyBody().strength(-300))
	.force("center", d3.forceCenter(width / 2, height / 2));

// Helper functions for info panel
function closeInfoPanel() {
	infoPanel.classed("visible", false);
}

// Make info panel draggable
let isDragging = false;
let dragStartX, dragStartY, panelStartX, panelStartY;

infoPanel
	.attr("draggable", true)
	.on("mousedown", function(event) {
		if (event.target.classList.contains("close-btn") || event.target.tagName === "A") return;
		isDragging = true;
		infoPanel.classed("dragging", true);
		dragStartX = event.clientX;
		dragStartY = event.clientY;
		const transform = infoPanel.style("transform") || "translate(0, 0)";
		const match = transform.match(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/);
		panelStartX = match ? parseFloat(match[1]) : 0;
		panelStartY = match ? parseFloat(match[2]) : 0;
		event.preventDefault();
	})
	.on("mousemove", function(event) {
		if (!isDragging) return;
		const dx = event.clientX - dragStartX;
		const dy = event.clientY - dragStartY;
		infoPanel.style("transform", `translate(${panelStartX + dx}px, ${panelStartY + dy}px)`);
	})
	.on("mouseup mouseout", function() {
		if (isDragging) {
			isDragging = false;
			infoPanel.classed("dragging", false);
		}
	});

function showNodeInfo(d, allData) {
	const login = d.id;
	const group = d.group || 0;
	
	// Count evaluations given and received
	let evalsGiven = 0;
	let evalsReceived = 0;
	let connections = 0;
	
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
		}
	});
	
	panelTitle.html(`
		<div style="display: flex; align-items: center; gap: 12px;">
			<div style="width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 18px; border: 2px solid #667eea;">${login.charAt(0).toUpperCase()}</div>
			<a href="https://profile.intra.42.fr/users/${login}" target="_blank">${login}</a>
		</div>
	`);
	panelContent.html(`
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
		<div class="info-section">
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

function updateGraph(data) {
	if (!data || !data.links) {
		console.error("Invalid data structure: 'links' property is missing", data);
		return;
	}
	container.selectAll("*").remove();
	simulation.nodes([]);

	const threshold = getCriticalThreshold();

	const link = container.append("g")
		.attr("class", "links")
		.selectAll("line")
		.data(data.links)
		.enter().append("line")
		.attr("class", (d) => `link ${d.value > threshold ? "alert" : "ok"}`)
		.attr("stroke-width", d => Math.sqrt(d.value))
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
		.data(data.nodes)
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

	node.call(d3.drag()
		.on("start", dragstarted)
		.on("drag", dragged)
		.on("end", dragended));

	simulation
		.nodes(data.nodes)
		.on("tick", ticked);

	simulation.force("link")
		.links(data.links);

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

	function filterNodes() {
		const isChecked = d3.select("#filterCheckbox").property("checked");
		const threshold = getCriticalThreshold();

		if (isChecked) {
			node.style("opacity", function(d) {
				const hasHighValueLink = data.links.some(link =>
					(link.source.id === d.id || link.target.id === d.id) && link.value > threshold
				);
				return hasHighValueLink ? 1 : 0;
			});

			link.style("opacity", d => d.value > threshold ? 1 : 0);
		} else {
			node.style("opacity", 1);
			link.style("opacity", 1);
		}
	}

	d3.select("#filterCheckbox").on("change", filterNodes);

	function searchNode() {
		const searchValue = d3.select("#searchBox").property("value").toLowerCase();
		const foundNode = data.nodes.find(node => node.id.toLowerCase() === searchValue);

		if (foundNode) {
			node.select("circle")
				.attr("r", 5)
				.attr("fill", d => color(d.group));

			const highlightedNode = d3.select(node.nodes().find(n => n.__data__.id === foundNode.id))
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

	d3.select("#searchBox").on("keyup", function(event) {
		if (event.key === "Enter") {
			searchNode();
		}
	});
}

function getCriticalThreshold() {
	const input = document.getElementById("criticalValue");
	return input ? parseInt(input.value) || 5 : 5;
}

function reloadData() {
	criticalThreshold = getCriticalThreshold();
	if (originalData) {
		const freshData = JSON.parse(JSON.stringify(originalData));
		updateGraph(freshData);
	}
}

window.reloadData = reloadData;

	d3.json("./data.json")
		.then(function(data) {
			if (!data) throw new Error("JSON file is empty"); 
			originalData = JSON.parse(JSON.stringify(data));
			updateGraph(data);
		})
	.catch(err => {
		console.error("Failed to load data:", err);
		container.append("text")
			.attr("x", width / 2)
			.attr("y", height / 2)
			.attr("text-anchor", "middle")
			.attr("fill", "red")
			.text("Failed to load data. Check console for errors.");
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
