<h1 align="center"><code>42-eval-graph</code></h1>

<div align="center">
  <sub>Created by <a href="https://github.com/jgengo">Jordane Gengo (Titus)</a></sub>
  <br>
  <sub>Forked by pibouill</sub>
</div>

<h1 align="center">Peer Evaluation Network</h1>

Visualize 42 peer evaluations as an interactive network graph.

![example](.github/docs/image0.png)

## Features

- **Interactive Graph**: Click nodes/links to view detailed information
- **Info Panel**: Shows student stats, cluster, evaluation dates
- **Multiple Views**: All data, Critical evaluations, Clusters
- **Search**: Find students by login
- **Filter**: Show only high-value evaluations
- **Date Support**: First/last evaluation dates

## Requirements

- 42 Intra API credentials
- Python 3.8+

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Copy and configure your API credentials:
```bash
cp config.sample.yml config.yml
# Edit config.yml with your 42 API client/secret
```

## Usage

### Fetch Data

```bash
# Auto-detect current semester (recommended)
python pull.py

# Specific date range
python pull.py --from 2025-09-01 --to 2026-01-15

# By cohort start date
python pull.py --cohort 2025-09-01

# Use dates from config.yml
python pull.py --config

# Generate sample data (no API needed)
python pull.py --sample
```

### Run Web Server

```bash
cd web
python3 -m http.server 8000
```

Open http://localhost:8000 in your browser.

## Views

- `index.html` - All evaluation data
- `critical.html` - High-value evaluations (value > 5)
- `clusters.html` - View by cluster

## Interacting with the Graph

- **Click on node**: Opens info panel with student details
- **Click on link**: Shows evaluation details
- **Click outside**: Closes info panel
- **Drag nodes**: Reposition
- **Scroll/pan**: Zoom and navigate
- **Search box**: Find by login

## Info Panel

Click any node or link to see:
- Login and cluster
- Evaluations given/received
- Total connections
- First/last evaluation dates
- Link to 42 Intra profile

## CLI Options

| Option | Description |
|--------|------------|
| `--from` | Start date (YYYY-MM-DD) |
| `--to` | End date (YYYY-MM-DD) |
| `--cohort` | Fetch users who started on date |
| `--config` | Use date_range from config.yml |
| `--sample` | Generate sample data |
| `--campus` | Campus ID (default: 56) |
| `--cursus` | Cursus ID (default: 21) |

## Data Format

The generated `data.json` includes:
```json
{
  "nodes": [{"id": "login", "group": 1}],
  "links": [
    {"source": "user1", "target": "user2", "value": 3, "first_eval": "2025-09-01", "last_eval": "2025-12-15"}
  ]
}
```

## Potential Ideas

- Cluster Detection and Visualization
- Interactive Info Panel ✓ (Done)
- Time-Based Filtering
- Heatmap Overlay
- Export Graph as Image