# Warehouse Picking Route Optimizer

Enhanced Streamlit dashboard for warehouse order batching, picking route simulation, spatial clustering, zone picking, and multi-picker route inspection.

This project is a fork of Samir Saci's original warehouse order batching and picking route optimisation work. The original project provides the modelling foundation, sample data structure, and methodology. This fork focuses on turning that baseline into a more complete local analytics application.

## What's New In This Fork

- Multi-tab Streamlit dashboard with KPI cards and route inspection workflows.
- CSV upload with schema validation.
- OR-Tools TSP routing and greedy next-closest-location routing.
- Independent wave range controls for batch and clustering simulations.
- Trolley capacity constraints by pieces and order lines.
- Optional X-axis zone picking.
- Multi-picker wave assignment.
- Interactive route inspector with filters for simulation, clustering method, wave size, zone, picker, and wave ID.
- Active dataset manager with summary KPIs and distribution charts.
- Multiprocessing fallback: if `ProcessPoolExecutor` is unavailable, simulations run sequentially instead of failing.

## Application Screenshots

### Batch Size Optimizer

![Batch Size Optimizer dashboard](static/img/readme_app_batch_optimizer.png)

### Clustering Optimizer

![Clustering Optimizer dashboard](static/img/readme_app_clustering_optimizer.png)

### Interactive Route Inspector

![Interactive Route Inspector dashboard](static/img/readme_app_route_inspector.png)

### Data Manager

![Data Manager dashboard](static/img/readme_app_data_manager.png)

## Quick Start

If the included virtual environment is available:

```bash
./.venv/bin/streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

To create a fresh environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

For remote or container usage:

```bash
streamlit run app.py --server.address 0.0.0.0
```

## CSV Input Format

Uploaded CSV files must include these columns:

| Column | Description | Example |
| --- | --- | --- |
| `DATE` | Order date or timestamp for chronological wave mapping | `12/11/2018` |
| `OrderNumber` | Order identifier | `3780678` |
| `SKU` | Item/reference identifier per order line | `399573` |
| `PCS` | Piece quantity per order line | `1` |
| `Coord` | Picking coordinate as a stringified 2D list | `"[19.5, 21.0]"` |

The default sample dataset is:

```text
static/in/df_lines.csv
```

## Dashboard Tabs

### 1. Batch Size Optimizer

Simulates chronological order batching across a configurable range of orders per wave. It reports total walking distance, optimal wave size, and route-level output.

### 2. Clustering Optimizer

Compares three wave creation strategies:

- `normal-normal`: no clustering.
- `clustering-normal`: clustering single-line orders only.
- `clustering-clustering`: clustering single-line orders and multi-line order centroids.

### 3. Interactive Route Inspector

Inspects saved simulation routes by wave size, method, zone, picker, and wave ID. The view supports full route display and step-by-step route playback.

### 4. Data Manager

Shows active dataset health, required-column validation, row/order/SKU/PCS metrics, coordinate distribution, piece distribution, and orders by date.

## Sidebar Controls

- Warehouse aisle boundaries and depot coordinates.
- Clustering distance threshold.
- Trolley limits: max pieces and max order lines per wave.
- Zone picking with configurable X split.
- Number of pickers for disjoint wave assignment.
- Routing algorithm: OR-Tools TSP or greedy route construction.
- CSV upload.

## Project Structure

```text
app.py                         Streamlit application
static/in/df_lines.csv          Sample order-line dataset
static/img/                     README and application images
utils/batch/                    Batch wave mapping and simulation
utils/cluster/                  Clustering, zone, and picker logic
utils/routing/                  Distance and route algorithms
utils/results/                  Plotly route and result visualisations
```

## Attribution

This fork is based on the original warehouse productivity and order batching work by **Samir Saci**.

Original resources:

- Samir Saci's methodology and article series: [samirsaci.com](https://samirsaci.com)
- Original consulting reference: [Logigreen Consulting](https://www.logi-green.com/)

This README intentionally keeps attribution concise while focusing on the enhanced application in this fork.
