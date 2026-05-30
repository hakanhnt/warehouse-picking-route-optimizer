import pandas as pd
import numpy as np
import plotly.express as px
from utils.routing.distances import (
	distance_picking,
	next_location
)
from utils.routing.routes import (
	create_picking_route
)
from utils.batch.mapping_batch import (
	orderlines_mapping,
	locations_listing
)
from utils.cluster.mapping_cluster import (
	df_mapping
)
import importlib
import utils.routing.distances
import utils.routing.routes
import utils.batch.mapping_batch
import utils.cluster.clustering
import utils.cluster.mapping_cluster
import utils.batch.simulation_batch
import utils.cluster.simulation_cluster
import utils.results.plot

importlib.reload(utils.routing.distances)
importlib.reload(utils.routing.routes)
importlib.reload(utils.batch.mapping_batch)
importlib.reload(utils.cluster.clustering)
importlib.reload(utils.cluster.mapping_cluster)
importlib.reload(utils.batch.simulation_batch)
importlib.reload(utils.cluster.simulation_cluster)
importlib.reload(utils.results.plot)
from utils.batch.simulation_batch import (
	simulation_wave,
	simulate_batch
)
from utils.cluster.simulation_cluster import(
	loop_wave,
	simulation_cluster,
	create_dataframe,
	process_methods
)
from utils.results.plot import (
	plot_simulation1,
	plot_simulation2,
	plot_picking_route
)
import streamlit as st

# Set page configuration
st.set_page_config(page_title="Warehouse Picking Route Optimizer",
                    initial_sidebar_state="expanded",
                    layout='wide',
                    page_icon=None)

# Inject Custom SaaS CSS Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header styling */
    .app-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .app-header h1 {
        margin: 0;
        font-size: 2.25rem;
        font-weight: 700;
        color: white;
        letter-spacing: -0.025em;
    }
    .app-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1rem;
        opacity: 0.9;
        font-weight: 400;
    }

    /* KPI cards grid */
    .kpi-container {
        display: flex;
        gap: 1.25rem;
        margin-bottom: 1.75rem;
        flex-wrap: wrap;
    }
    .kpi-card {
        flex: 1;
        min-width: 220px;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: all 0.25s ease;
    }
    .kpi-card:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
        border-color: #cbd5e1;
        transform: translateY(-2px);
    }
    .kpi-label {
        font-size: 0.75rem;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.35rem;
    }
    .kpi-value {
        font-size: 1.75rem;
        color: #0f172a;
        font-weight: 700;
        line-height: 1.2;
    }
    .kpi-subtext {
        font-size: 0.75rem;
        color: #94a3b8;
        margin-top: 0.35rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to render KPI Metric Cards
def render_kpis(kpis):
    html_str = "<div class='kpi-container'>"
    for kpi in kpis:
        html_str += f"<div class='kpi-card'><div class='kpi-label'>{kpi['label']}</div><div class='kpi-value'>{kpi['value']}</div><div class='kpi-subtext'>{kpi['subtext']}</div></div>"
    html_str += "</div>"
    st.markdown(html_str, unsafe_allow_html=True)

# App Header Banner
st.markdown("""
<div class='app-header'>
    <h1>Warehouse Order Picking Route Optimizer</h1>
    <p>Simulate and optimize picking waves, spatial clustering, and path sequences to reduce total warehouse walking distance.</p>
</div>
""", unsafe_allow_html=True)

# Set up the page data loader
REQUIRED_COLUMNS = {"DATE", "OrderNumber", "SKU", "PCS", "Coord"}
methods = ["normal-normal", "clustering-normal", "clustering-clustering"]
IN = 'static/in/'

@st.cache_data(show_spinner=True)
def read_csv_cached(filepath):
    return pd.read_csv(filepath)

def load(uploaded_file, filename, n):
    if 'custom_df' in st.session_state:
        return st.session_state['custom_df'].head(n).copy()
    if uploaded_file is not None:
        df_orderlines = pd.read_csv(uploaded_file).head(n)
    else:
        df_orderlines = read_csv_cached(IN + filename).head(n)
    return df_orderlines

def validate_orderlines(df_orderlines):
    missing_columns = sorted(REQUIRED_COLUMNS - set(df_orderlines.columns))
    if missing_columns:
        st.error(
            "CSV file is missing required column(s): "
            + ", ".join(missing_columns)
        )
        st.stop()
    return df_orderlines

# Sidebar Configuration
st.sidebar.header("Warehouse Layout Parameters")

y_low = st.sidebar.number_input("Aisle Lower Boundary (y_low)", min_value=0.0, max_value=100.0, value=5.5, step=0.5)
y_high = st.sidebar.number_input("Aisle Upper Boundary (y_high)", min_value=0.0, max_value=200.0, value=50.0, step=0.5)

depot_x = st.sidebar.number_input("Depot Start X Coordinate", min_value=0.0, value=0.0, step=1.0)
depot_y = st.sidebar.number_input("Depot Start Y Coordinate", min_value=0.0, value=y_low, step=1.0)
origin_loc = [depot_x, depot_y]

distance_threshold = st.sidebar.slider("Clustering Distance Threshold (m)", min_value=5, max_value=100, value=35, step=5)

st.sidebar.markdown("---")
st.sidebar.header("Trolley Capacity Constraints")
max_pcs = st.sidebar.slider("Max Pieces per Wave (Trolley PCS Capacity)", min_value=0, max_value=500, value=0, step=10, help="Set to 0 for unlimited pieces.")
max_lines = st.sidebar.slider("Max Lines per Wave (Trolley Lines Capacity)", min_value=0, max_value=100, value=0, step=5, help="Set to 0 for unlimited order lines.")

st.sidebar.markdown("---")
st.sidebar.header("Multi-Picker & Zoning Options")
enable_zoning = st.sidebar.checkbox("Enable Zone Picking (X-Split)", value=False, help="Split warehouse orderlines into Zone 1 and Zone 2 along X-axis.")
zone_split_x = st.sidebar.slider("Zone Split X Coordinate", min_value=15.0, max_value=55.0, value=35.0, step=1.0) if enable_zoning else 0.0
n_pickers = st.sidebar.slider("Number of Pickers (Disjoint Waves)", min_value=1, max_value=5, value=1, help="Cluster waves spatially so pickers work in separate areas.")

st.sidebar.markdown("---")
st.sidebar.header("Dataset Upload")
uploaded_file = st.sidebar.file_uploader("Upload Order Dataset (CSV)", type=["csv"])

with st.sidebar.expander("Required CSV Format"):
    st.markdown("""
    Your custom CSV file must contain the following columns:
    
    - **DATE**: Order date (e.g., `12/11/2018`)
    - **OrderNumber**: Order ID (e.g., `3780678`)
    - **SKU**: Item or reference ID for each order line
    - **PCS**: Piece quantity for each order line
    - **Coord**: 2D coordinate array as a string (e.g., `"[19.5, 21.0]"`)
    
    *Make sure the coordinates are in the range of your Aisle boundaries.*
    """)

st.sidebar.markdown("---")
st.sidebar.header("Algorithm Settings")
routing_method = st.sidebar.selectbox("Routing Algorithm", ["Google OR-Tools (TSP)", "Next Closest Location (Greedy)"])
use_ortools = (routing_method == "Google OR-Tools (TSP)")

# Sync uploaded file with session state custom_df
if uploaded_file is not None:
    if 'uploaded_file_name' not in st.session_state or st.session_state['uploaded_file_name'] != uploaded_file.name:
        st.session_state['uploaded_file_name'] = uploaded_file.name
        st.session_state['custom_df'] = pd.read_csv(uploaded_file)

# Store Results by WaveID
list_wid, list_dst, list_route, list_ord, list_lines, list_pcs, list_monomult, list_zone = [], [], [], [], [], [], [], []
list_results = [list_wid, list_dst, list_route, list_ord, list_lines, list_pcs, list_monomult, list_zone]	# Group in list
# Store Results by Simulation (Order_number)
list_ordnum , list_dstw = [], []

# Create Dashboard Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Batch Size Optimizer",
    "Clustering Optimizer",
    "Interactive Route Inspector",
    "Data Manager"
])

with tab1:
    st.header("Impact of the Wave Size in Orders")
    st.markdown("Analyze how the number of orders combined per wave affects the total walking distance.")
    
    st.subheader("Simulation Scope")
    col1, col2 = st.columns(2)
    with col1:
        n = st.slider(
            'Simulation 1 Scope (Thousand Orders)', 1, 200 , value = 5, key="scope_slider_1")
    with col2:
        lines_number = 1000 * n 
        st.write(f"**{lines_number:,}** order lines selected")
        
    st.subheader("Wave Parameters")
    col_11 , col_22 = st.columns(2)
    with col_11:
        n1 = st.slider(
            'Simulation 1: N_MIN (Orders/Wave)', 1, 20 , value = 1, key="n_min_1")
        n2 = st.slider(
            'Simulation 1: N_MAX (Orders/Wave)', n1 + 1, 20 , value = int(np.max([n1+1 , 10])), key="n_max_1")
    with col_22:
        st.write(f"Testing wave range: **[{n1}, {n2}]** orders per wave")
        
    # START CALCULATION
    start_1 = False
    if st.checkbox('Start Simulation 1 Calculation', key='show_sim1', value=False):
        start_1 = True
        
    if start_1:
        df_orderlines = validate_orderlines(load(uploaded_file, 'df_lines.csv', lines_number))
        with st.spinner("Running batch size simulation..."):
            df_waves, df_results = simulate_batch(n1, n2, y_low, y_high, origin_loc, lines_number, df_orderlines, use_ortools=use_ortools, max_pcs=max_pcs, max_lines=max_lines, zone_split_x=zone_split_x, n_pickers=n_pickers)
        st.session_state['sim1_waves'] = df_waves
        st.session_state['sim1_results'] = df_results
        st.session_state['sim1_lines'] = lines_number
        st.success("Simulation completed successfully!")
        
    if 'sim1_results' in st.session_state:
        df_res = st.session_state['sim1_results']
        best_row = df_res.loc[df_res['distance'].idxmin()]
        best_size = int(best_row['order_per_wave'])
        min_dist = best_row['distance']
        
        # Render KPIs
        kpis = [
            {"label": "Optimal Wave Size", "value": f"{best_size} Orders", "subtext": "Yields minimal total walk distance"},
            {"label": "Minimum Distance", "value": f"{min_dist:,} m", "subtext": "Across tested wave sizes"},
            {"label": "Routing Algorithm", "value": "OR-Tools (TSP)" if use_ortools else "Greedy (NCL)", "subtext": "Selected path solver"}
        ]
        render_kpis(kpis)
        
        plot_simulation1(st.session_state['sim1_results'], st.session_state['sim1_lines'])

with tab2:
    st.header("Impact of the Order Batching Method")
    st.markdown("Compare spatial clustering vs. default waves to evaluate distance savings.")
    
    st.subheader("Simulation Scope")
    col1, col2 = st.columns(2)
    with col1:
        n_ = st.slider(
            'Simulation 2 Scope (Thousand Orders)', 1, 200 , value = 5, key="scope_slider_2")
    with col2:
        lines_2 = 1000 * n_ 
        st.write(f"**{lines_2:,}** order lines selected")

    st.subheader("Wave Parameters")
    col_21 , col_22 = st.columns(2)
    with col_21:
        n1_cluster = st.slider(
            'Simulation 2: N_MIN (Orders/Wave)', 1, 20 , value = 1, key="n_min_2")
        n2_cluster = st.slider(
            'Simulation 2: N_MAX (Orders/Wave)', n1_cluster + 1, 20 , value = int(np.max([n1_cluster + 1, 10])), key="n_max_2")
    with col_22:
        st.write(f"Testing wave range: **[{n1_cluster}, {n2_cluster}]** orders per wave")
        
    # START CALCULATION
    start_2 = False
    if st.checkbox('Start Simulation 2 Calculation', key='show_sim2', value=False):
        start_2 = True
        
    if start_2:
        df_orderlines = validate_orderlines(load(uploaded_file, 'df_lines.csv', lines_2))
        with st.spinner("Running clustering simulation..."):
            clean_list_results = [[], [], [], [], [], [], [], []]
            df_reswave, df_results = simulation_cluster(y_low, y_high, df_orderlines, clean_list_results, n1_cluster, n2_cluster, 
                    distance_threshold, use_ortools=use_ortools, max_pcs=max_pcs, max_lines=max_lines, zone_split_x=zone_split_x, n_pickers=n_pickers)
        st.session_state['sim2_reswave'] = df_reswave
        st.session_state['sim2_results'] = df_results
        st.session_state['sim2_lines'] = lines_2
        st.success("Simulation completed successfully!")
        
    if 'sim2_results' in st.session_state:
        df_reswave_cached = st.session_state['sim2_reswave']
        df_results_cached = st.session_state['sim2_results']
        
        df_res_reset = df_reswave_cached.reset_index()
        best_row_m3 = df_res_reset.loc[df_res_reset['distance_method_3'].idxmin()]
        best_size_m3 = int(best_row_m3['orders_number'])
        min_dist_m3 = best_row_m3['distance_method_3']
        dist_m1 = best_row_m3['distance_method_1']
        savings = dist_m1 - min_dist_m3
        pct_savings = (savings / dist_m1 * 100) if dist_m1 > 0 else 0.0
        
        # Render KPIs
        kpis = [
            {"label": "Optimal Wave Size (Clustered)", "value": f"{best_size_m3} Orders", "subtext": "For Single & Multi-Line Clustering"},
            {"label": "Minimum Distance (Clustered)", "value": f"{min_dist_m3:,.0f} m", "subtext": f"No Clustering was {dist_m1:,.0f} m"},
            {"label": "Clustering Savings", "value": f"{savings:,.0f} m ({pct_savings:.1f}%)", "subtext": f"Reduction at wave size {best_size_m3}"}
        ]
        render_kpis(kpis)
        
        plot_simulation2(df_reswave_cached, st.session_state['sim2_lines'], distance_threshold)

with tab3:
    st.header("Interactive Route Inspector")
    st.markdown("Select a simulation run to inspect wave-by-wave picker routes, visualize zoning split, and step through picking sequences.")
    
    sim_source = st.radio("Select Simulation Source", ["Simulation 1 (Batch Size)", "Simulation 2 (Clustering)"], horizontal=True, key="t3_sim_source")
    
    if sim_source == "Simulation 1 (Batch Size)":
        if 'sim1_waves' not in st.session_state:
            st.info("Please run Simulation 1 in the first tab to inspect routes.")
        else:
            df = st.session_state['sim1_waves']

            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                wave_sizes = sorted(df['order_per_wave'].unique())
                selected_size = st.selectbox("Wave Size (Orders/Wave)", wave_sizes, key="t3_size_s1")
                df_size_filtered = df[df['order_per_wave'] == selected_size]

            with f_col2:
                zone_options = ["All Zones"] + [f"Zone {z}" for z in sorted(df_size_filtered['ZoneID'].unique())]
                selected_zone_str = st.selectbox("Filter by Zone", zone_options, key="t3_zone_s1")

            with f_col3:
                picker_options = [f"Picker {p}" for p in sorted(df_size_filtered['PickerID'].unique())]
                selected_picker_str = st.selectbox("Select Picker", picker_options, key="t3_picker_s1")

            # Apply filters
            df_filtered = df_size_filtered.copy()
            if selected_zone_str != "All Zones":
                zone_val = int(selected_zone_str.split()[-1])
                df_filtered = df_filtered[df_filtered['ZoneID'] == zone_val]
            picker_val = int(selected_picker_str.split()[-1])
            df_filtered = df_filtered[df_filtered['PickerID'] == picker_val]

            with f_col4:
                wave_ids = sorted(df_filtered['wave'].unique())
                if len(wave_ids) > 0:
                    selected_wave = st.selectbox("Select Wave ID", wave_ids, key="t3_wave_s1")
                    df_wave_selected = df_filtered[df_filtered['wave'] == selected_wave]
                else:
                    selected_wave = None
                    df_wave_selected = pd.DataFrame()

            if len(df_wave_selected) > 0:
                route_row = df_wave_selected.iloc[0]
                chemin_list = route_row['routes']
                n_stops = len(chemin_list)

                kpis = [
                    {"label": f"Wave #{selected_wave}", "value": f"Zone {route_row['ZoneID']}", "subtext": f"Picker assigned: Picker {route_row['PickerID']}"},
                    {"label": "Route Distance", "value": f"{route_row['distance']:,} m", "subtext": "Total walking path length"},
                    {"label": "Pick Locations", "value": f"{max(0, n_stops - 2)} Picks", "subtext": "Excluding depot start/end"}
                ]
                render_kpis(kpis)

                st.markdown("### Route Display Mode")
                view_mode = st.radio("Display Type", ["Full Route (Step Numbered Route)", "Step-by-Step (Interactive Slider)"], horizontal=True, key="t3_view_mode_s1")

                if view_mode == "Step-by-Step (Interactive Slider)":
                    step_limit = st.slider("Route Step (Visit Sequence)", min_value=1, max_value=n_stops, value=n_stops, key="t3_step_s1")
                    plot_picking_route(chemin_list, y_low, y_high, step_limit=step_limit, zone_split_x=zone_split_x)
                else:
                    plot_picking_route(chemin_list, y_low, y_high, zone_split_x=zone_split_x)
            else:
                st.warning("No waves match the selected filters combination.")
                
    else:  # Simulation 2
        if 'sim2_results' not in st.session_state:
            st.info("Please run Simulation 2 in the second tab to inspect routes.")
        else:
            df = st.session_state['sim2_results']

            f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
            with f_col1:
                methods_list = sorted(df['mono_multi'].unique())
                selected_method = st.selectbox("Clustering Method", methods_list, key="t3_method_s2")
                df_method_filtered = df[df['mono_multi'] == selected_method]

            with f_col2:
                wave_sizes = sorted(df_method_filtered['order_per_wave'].unique())
                selected_size = st.selectbox("Wave Size (Orders/Wave)", wave_sizes, key="t3_size_s2")
                df_size_filtered = df_method_filtered[df_method_filtered['order_per_wave'] == selected_size]

            with f_col3:
                zone_options = ["All Zones"] + [f"Zone {z}" for z in sorted(df_size_filtered['ZoneID'].unique())]
                selected_zone_str = st.selectbox("Filter by Zone", zone_options, key="t3_zone_s2")

            with f_col4:
                picker_options = [f"Picker {p}" for p in sorted(df_size_filtered['PickerID'].unique())]
                selected_picker_str = st.selectbox("Select Picker", picker_options, key="t3_picker_s2")

            # Apply filters
            df_filtered = df_size_filtered.copy()
            if selected_zone_str != "All Zones":
                zone_val = int(selected_zone_str.split()[-1])
                df_filtered = df_filtered[df_filtered['ZoneID'] == zone_val]
            picker_val = int(selected_picker_str.split()[-1])
            df_filtered = df_filtered[df_filtered['PickerID'] == picker_val]

            with f_col5:
                wave_ids = sorted(df_filtered['wave_number'].unique())
                if len(wave_ids) > 0:
                    selected_wave = st.selectbox("Select Wave ID", wave_ids, key="t3_wave_s2")
                    df_wave_selected = df_filtered[df_filtered['wave_number'] == selected_wave]
                else:
                    selected_wave = None
                    df_wave_selected = pd.DataFrame()

            if len(df_wave_selected) > 0:
                route_row = df_wave_selected.iloc[0]
                chemin_list = route_row['chemins']
                n_stops = len(chemin_list)

                kpis = [
                    {"label": f"Wave #{selected_wave}", "value": f"Zone {route_row['ZoneID']}", "subtext": f"Picker assigned: Picker {route_row['PickerID']}"},
                    {"label": "Route Distance", "value": f"{route_row['distance']:,} m", "subtext": "Total walking path length"},
                    {"label": "Pick Locations", "value": f"{max(0, n_stops - 2)} Picks", "subtext": "Excluding depot start/end"}
                ]
                render_kpis(kpis)

                st.markdown("### Route Display Mode")
                view_mode = st.radio("Display Type", ["Full Route (Step Numbered Route)", "Step-by-Step (Interactive Slider)"], horizontal=True, key="t3_view_mode_s2")

                if view_mode == "Step-by-Step (Interactive Slider)":
                    step_limit = st.slider("Route Step (Visit Sequence)", min_value=1, max_value=n_stops, value=n_stops, key="t3_step_s2")
                    plot_picking_route(chemin_list, y_low, y_high, step_limit=step_limit, zone_split_x=zone_split_x)
                else:
                    plot_picking_route(chemin_list, y_low, y_high, zone_split_x=zone_split_x)
            else:
                st.warning("No waves match the selected filters combination.")

with tab4:
    st.header("📦 Active Dataset Manager")
    st.markdown("Inspect, filter, and edit the active order lines dataset. Changes will be reflected in all simulator tabs.")

    # Initialize session state dataset if not already done
    if 'custom_df' not in st.session_state:
        if uploaded_file is not None:
            st.session_state['custom_df'] = pd.read_csv(uploaded_file)
        else:
            st.session_state['custom_df'] = pd.read_csv(IN + 'df_lines.csv')

    _df = st.session_state['custom_df']

    # ── Dataset Overview KPIs ──────────────────────────────────────────────
    st.subheader("Dataset Overview")

    _n_rows      = len(_df)
    _n_orders    = _df['OrderNumber'].nunique() if 'OrderNumber' in _df.columns else '—'
    _n_skus      = _df['SKU'].nunique()          if 'SKU'         in _df.columns else '—'
    _total_pcs   = int(_df['PCS'].sum())         if 'PCS'         in _df.columns else '—'
    _missing     = int(_df.isnull().sum().sum())

    _missing_cols = sorted({"DATE","OrderNumber","SKU","PCS","Coord"} - set(_df.columns))
    if _missing_cols:
        st.error(f"⚠️ Missing required columns: **{', '.join(_missing_cols)}**  — Simulations will fail until these columns are present.")
    else:
        st.success("✅ All required columns present — dataset is ready for simulation.")

    kpis_dm = [
        {"label": "Total Order Lines",  "value": f"{_n_rows:,}",      "subtext": "Rows in active dataset"},
        {"label": "Unique Orders",       "value": f"{_n_orders:,}",    "subtext": "Distinct OrderNumber values"},
        {"label": "Unique SKUs",         "value": f"{_n_skus:,}",      "subtext": "Distinct product references"},
        {"label": "Total Pieces (PCS)",  "value": f"{_total_pcs:,}",   "subtext": "Sum of all piece quantities"},
        {"label": "Missing Values",      "value": str(_missing),       "subtext": "Null cells across all columns"},
    ]
    render_kpis(kpis_dm)

    # ── Coordinate Distribution Map ────────────────────────────────────────
    if 'Coord' in _df.columns:
        with st.expander("📍 Coordinate Distribution Heatmap", expanded=True):
            try:
                from ast import literal_eval
                _coords_raw = _df['Coord'].dropna().apply(lambda t: literal_eval(t) if isinstance(t, str) else t)
                _coords_df  = pd.DataFrame(_coords_raw.tolist(), columns=['X', 'Y'])

                _fig_coord = px.density_heatmap(
                    _coords_df, x='X', y='Y',
                    nbinsx=40, nbinsy=30,
                    color_continuous_scale='Blues',
                    labels={'X': 'Aisle X Coordinate', 'Y': 'Shelf Y Coordinate'},
                    title="Pick Location Density — X vs Y Coordinates"
                )
                _fig_coord.update_layout(
                    height=380,
                    plot_bgcolor='#f8fafc',
                    paper_bgcolor='#f8fafc',
                    font=dict(family='Inter, sans-serif'),
                    coloraxis_colorbar=dict(title="Count"),
                )
                if zone_split_x > 0:
                    _fig_coord.add_vline(
                        x=zone_split_x, line_dash="dash", line_color="#ef4444", line_width=2,
                        annotation_text=f"Zone Split x={zone_split_x:.0f}", annotation_position="top right"
                    )
                st.plotly_chart(_fig_coord, use_container_width=True)
            except Exception as e:
                st.warning(f"Could not render coordinate map: {e}")

    # ── PCS Distribution ──────────────────────────────────────────────────
    if 'PCS' in _df.columns:
        with st.expander("📊 Piece Quantity (PCS) Distribution", expanded=False):
            _fig_pcs = px.histogram(
                _df, x='PCS', nbins=50,
                color_discrete_sequence=['#3b82f6'],
                labels={'PCS': 'Pieces per Order Line'},
                title="Distribution of Piece Quantities per Order Line"
            )
            _fig_pcs.update_layout(
                height=300,
                plot_bgcolor='#f8fafc',
                paper_bgcolor='#f8fafc',
                font=dict(family='Inter, sans-serif'),
                bargap=0.05
            )
            st.plotly_chart(_fig_pcs, use_container_width=True)

    # ── Orders per Date ───────────────────────────────────────────────────
    if 'DATE' in _df.columns and 'OrderNumber' in _df.columns:
        with st.expander("📅 Orders per Date", expanded=False):
            try:
                _df_date = _df.groupby('DATE')['OrderNumber'].nunique().reset_index()
                _df_date.columns = ['Date', 'Orders']
                _fig_date = px.bar(
                    _df_date, x='Date', y='Orders',
                    color_discrete_sequence=['#6366f1'],
                    labels={'Date': 'Order Date', 'Orders': 'Unique Orders'},
                    title="Number of Unique Orders per Date"
                )
                _fig_date.update_layout(
                    height=300,
                    plot_bgcolor='#f8fafc',
                    paper_bgcolor='#f8fafc',
                    font=dict(family='Inter, sans-serif'),
                )
                st.plotly_chart(_fig_date, use_container_width=True)
            except Exception as e:
                st.warning(f"Could not render date chart: {e}")

    # ── Interactive Filter & Editor ───────────────────────────────────────
    st.subheader("🔍 Filter & Edit Dataset")

    _filter_col1, _filter_col2, _filter_col3 = st.columns(3)
    with _filter_col1:
        _search_order = st.text_input("Filter by OrderNumber (contains)", value="", placeholder="e.g. 37806", key="dm_filter_order")
    with _filter_col2:
        _search_sku = st.text_input("Filter by SKU (contains)", value="", placeholder="e.g. ABC123", key="dm_filter_sku")
    with _filter_col3:
        if 'DATE' in _df.columns:
            _all_dates = ["All Dates"] + sorted(_df['DATE'].dropna().unique().tolist())
            _selected_date = st.selectbox("Filter by Date", _all_dates, key="dm_filter_date")
        else:
            _selected_date = "All Dates"

    # Apply display filters (non-destructive — only filters view)
    _df_display = _df.copy()
    if _search_order and 'OrderNumber' in _df_display.columns:
        _df_display = _df_display[_df_display['OrderNumber'].astype(str).str.contains(_search_order, case=False, na=False)]
    if _search_sku and 'SKU' in _df_display.columns:
        _df_display = _df_display[_df_display['SKU'].astype(str).str.contains(_search_sku, case=False, na=False)]
    if _selected_date != "All Dates" and 'DATE' in _df_display.columns:
        _df_display = _df_display[_df_display['DATE'] == _selected_date]

    st.caption(f"Showing **{len(_df_display):,}** of **{len(_df):,}** rows")

    edited_df = st.data_editor(
        _df_display,
        num_rows="dynamic",
        use_container_width=True,
        key="dataset_editor_table",
        column_config={
            "OrderNumber": st.column_config.NumberColumn("Order #", help="Unique order identifier"),
            "SKU":         st.column_config.NumberColumn("SKU", help="Product reference code") if pd.api.types.is_integer_dtype(_df_display.get("SKU", pd.Series(dtype=str))) else st.column_config.TextColumn("SKU", help="Product reference code"),
            "PCS":         st.column_config.NumberColumn("PCS", help="Piece quantity", min_value=0),
            "DATE":        st.column_config.TextColumn("Date", help="Order date"),
            "Coord":       st.column_config.TextColumn("Coord", help="Pick location as [X, Y]"),
        }
    )

    # ── Action Buttons ────────────────────────────────────────────────────
    st.markdown("---")
    col_act1, col_act2, col_act3 = st.columns([1, 1, 2])

    def _clear_sim_cache():
        for key in ['sim1_results', 'sim1_waves', 'sim2_results', 'sim2_reswave']:
            if key in st.session_state:
                del st.session_state[key]

    with col_act1:
        if st.button("💾 Save & Apply Changes", use_container_width=True, key="dm_save_btn"):
            # Merge edits back into full dataset
            if len(_df_display) == len(_df):
                st.session_state['custom_df'] = edited_df
            else:
                # Partial filter active — apply edits to filtered rows, keep rest unchanged
                merged = _df.copy()
                merged.update(edited_df)
                # Append any newly added rows from the editor
                new_rows = edited_df.iloc[len(_df_display):]
                if len(new_rows) > 0:
                    merged = pd.concat([merged, new_rows], ignore_index=True)
                st.session_state['custom_df'] = merged
            _clear_sim_cache()
            st.success("✅ Dataset updated! Run simulations in the optimizer tabs to use the new data.")
            st.rerun()

    with col_act2:
        if st.button("🔄 Reset to Default Data", use_container_width=True, key="dm_reset_btn"):
            for key in ['custom_df', 'uploaded_file_name']:
                if key in st.session_state:
                    del st.session_state[key]
            _clear_sim_cache()
            st.info("Dataset reset to default `df_lines.csv`.")
            st.rerun()

    with col_act3:
        _export_df = st.session_state.get('custom_df', _df)
        csv_data = _export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Full Dataset (CSV)",
            data=csv_data,
            file_name="warehouse_dataset_edited.csv",
            mime="text/csv",
            use_container_width=True,
            key="dm_download_btn"
        )
