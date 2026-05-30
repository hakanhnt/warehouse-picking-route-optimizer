import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils.routing.distances import distance_picking

def plot_simulation1(df_results, lines_number):
    ''' Plot simulation of batch size'''
    fig = px.bar(data_frame=df_results,
        x='order_per_wave',
        y='distance',
        labels={ 
            'order_per_wave': 'Wave size (Orders/Wave)',
            'distance': 'Total Picking Walking Distance (m)'
        },
        color_discrete_sequence=['#3b82f6']  # Modern blue
    )
    fig.update_traces(marker_line_width=1, marker_line_color="#1e3a8a")
    fig.update_layout(
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family="Inter, sans-serif", size=11, color="#1e293b"),
        xaxis=dict(
            gridcolor='#f1f5f9',
            title=dict(font=dict(color='#1e293b', size=12)),
            tickfont=dict(color='#1e293b', size=11)
        ),
        yaxis=dict(
            gridcolor='#f1f5f9',
            title=dict(font=dict(color='#1e293b', size=12)),
            tickfont=dict(color='#1e293b', size=11)
        ),
        margin=dict(l=50, r=40, t=40, b=50)
    )
    st.plotly_chart(fig, use_container_width=True, theme=None)

def plot_simulation2(df_reswave, lines_number, distance_threshold):
    fig = px.bar(data_frame=df_reswave.reset_index(),
        x='orders_number',
        y=['distance_method_1', 'distance_method_2', 'distance_method_3'],
        labels={ 
            'orders_number': 'Wave size (Orders/Wave)',
            'value': 'Total Distance (m)',
            'variable': 'Strategy'
        },
        color_discrete_sequence=['#64748b', '#0ea5e9', '#2563eb'],  # Grey, Cyan, Dark Blue
        barmode="group"
    )
    
    # Rename legend labels for clarity
    strategy_names = {
        'distance_method_1': 'No Clustering',
        'distance_method_2': 'Clustering (Single-Line Orders Only)',
        'distance_method_3': 'Clustering (Single & Multi-Line Orders)'
    }
    fig.for_each_trace(lambda t: t.update(name=strategy_names.get(t.name, t.name)))
    
    fig.update_traces(marker_line_width=1, marker_line_color="#0f172a")
    fig.update_layout(
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family="Inter, sans-serif", size=11, color="#1e293b"),
        xaxis=dict(
            gridcolor='#f1f5f9',
            title=dict(font=dict(color='#1e293b', size=12)),
            tickfont=dict(color='#1e293b', size=11)
        ),
        yaxis=dict(
            gridcolor='#f1f5f9',
            title=dict(font=dict(color='#1e293b', size=12)),
            tickfont=dict(color='#1e293b', size=11)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#1e293b", size=11)
        ),
        margin=dict(l=50, r=40, t=40, b=50)
    )
    st.plotly_chart(fig, use_container_width=True, theme=None)

def plot_picking_route(list_chemin, y_low, y_high, step_limit=None, zone_split_x=0.0):
    import pandas as pd
    import plotly.colors
    
    # helper function to get aisle name
    def get_aisle_name(x):
        x_coords = [15.25, 19.5, 20.75, 22.75, 24.0, 26.0, 28.0, 29.25, 31.25, 32.5, 34.5, 35.75, 37.75, 39.0, 41.0, 42.25, 44.25, 45.5, 47.5, 48.75, 50.75, 52.0]
        if abs(x - 0.0) < 0.5:
            return "Depot"
        closest_x = min(x_coords, key=lambda val: abs(val - x))
        if abs(closest_x - x) < 0.5:
            idx = x_coords.index(closest_x)
            return f"Aisle A{idx+1:02d}"
        return f"X={x:.2f}"

    # Limit path if step_limit is provided
    if step_limit is not None:
        list_chemin_limited = list_chemin[:step_limit]
    else:
        list_chemin_limited = list_chemin

    # Construct full path coordinates
    path = []
    if len(list_chemin_limited) > 0:
        path.append(list_chemin_limited[0])
        for i in range(len(list_chemin_limited) - 1):
            p1 = list_chemin_limited[i]
            p2 = list_chemin_limited[i + 1]
            x1, y1 = p1[0], p1[1]
            x2, y2 = p2[0], p2[1]
            
            if x1 == x2:
                path.append(p2)
            else:
                path_high = (y_high - y1) + (y_high - y2)
                path_low = (y1 - y_low) + (y2 - y_low)
                if path_high < path_low:
                    path.append([x1, y_high])
                    path.append([x2, y_high])
                else:
                    path.append([x1, y_low])
                    path.append([x2, y_low])
                path.append(p2)
                
    # Separate pick locations
    depot = list_chemin[0]
    all_picks = [p for p in list_chemin if p != depot]
    
    visited_picks = [p for p in list_chemin_limited if p != depot]
    unvisited_picks = [p for p in all_picks if p not in visited_picks]
    
    # Create Plotly figure
    fig = go.Figure()
    
    # --- PHYSICAL WAREHOUSE LAYOUT DRAWING ---
    # 1. Horizontal cross-aisle corridors (top and bottom)
    fig.add_shape(
        type="rect",
        x0=-5, x1=58,
        y0=y_low - 1.5, y1=y_low,
        fillcolor="rgba(243, 244, 246, 0.8)",
        line=dict(color="rgba(209, 213, 219, 0.5)", width=1),
        layer="below"
    )
    fig.add_shape(
        type="rect",
        x0=-5, x1=58,
        y0=y_high, y1=y_high + 1.5,
        fillcolor="rgba(243, 244, 246, 0.8)",
        line=dict(color="rgba(209, 213, 219, 0.5)", width=1),
        layer="below"
    )
    
    # 2. Shelving Racks (vertical grey columns between aisles)
    racks = [
        (19.5, 20.75),
        (22.75, 24.0),
        (26.0, 28.0),
        (28.0, 29.25),
        (31.25, 32.5),
        (34.5, 35.75),
        (37.75, 39.0),
        (41.0, 42.25),
        (44.25, 45.5),
        (47.5, 48.75),
        (50.75, 52.0)
    ]
    for x_min, x_max in racks:
        fig.add_shape(
            type="rect",
            x0=x_min, x1=x_max,
            y0=y_low, y1=y_high,
            fillcolor="rgba(156, 163, 175, 0.25)",  # Semi-transparent rack color
            line=dict(color="rgba(107, 114, 128, 0.5)", width=1),
            layer="below"
        )
        
    # 3. Aisle picking guidelines and labels
    x_coords = [15.25, 19.5, 20.75, 22.75, 24.0, 26.0, 28.0, 29.25, 31.25, 32.5, 34.5, 35.75, 37.75, 39.0, 41.0, 42.25, 44.25, 45.5, 47.5, 48.75, 50.75, 52.0]
    for idx, x in enumerate(x_coords):
        # Aisle path dashed line
        fig.add_shape(
            type="line",
            x0=x, x1=x,
            y0=y_low, y1=y_high,
            line=dict(color="rgba(156, 163, 175, 0.15)", width=1, dash="dash"),
            layer="below"
        )
        # Aisle label at the top
        fig.add_annotation(
            x=x, y=y_high + 3,
            text=f"A{idx+1:02d}",
            showarrow=False,
            font=dict(size=9, color="#4b5563", family="Courier New, monospace", weight="bold"),
            align="center"
        )

    # 3.5. Zone boundary vertical line
    if zone_split_x > 0.0:
        fig.add_shape(
            type="line",
            x0=zone_split_x, x1=zone_split_x,
            y0=y_low - 1.5, y1=y_high + 1.5,
            line=dict(color="#ef4444", width=2.5, dash="dot"),
            layer="above"
        )
        fig.add_annotation(
            x=zone_split_x - 3, y=y_high + 3,
            text="<b>ZONE 1</b>",
            showarrow=False,
            font=dict(size=10, color="#ef4444", family="Inter, sans-serif"),
            align="center"
        )
        fig.add_annotation(
            x=zone_split_x + 3, y=y_high + 3,
            text="<b>ZONE 2</b>",
            showarrow=False,
            font=dict(size=10, color="#ef4444", family="Inter, sans-serif"),
            align="center"
        )

    # 4. Plot picker path using a single uniform color and numbered badges
    if len(list_chemin_limited) > 1:
        # Legend placeholder
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='lines',
            name='Picking Route (Step Numbered)',
            line=dict(color='#2563eb', width=3),
            showlegend=True
        ))
        
        # Draw each leg of the walk with uniform color and step number badge
        for i in range(len(list_chemin_limited) - 1):
            p1 = list_chemin_limited[i]
            p2 = list_chemin_limited[i + 1]
            x1, y1 = p1[0], p1[1]
            x2, y2 = p2[0], p2[1]
            
            leg_segments = []
            if x1 == x2:
                leg_segments.append((p1, p2))
            else:
                path_high = (y_high - y1) + (y_high - y2)
                path_low = (y1 - y_low) + (y2 - y_low)
                if path_high < path_low:
                    leg_segments.append((p1, [x1, y_high]))
                    leg_segments.append(([x1, y_high], [x2, y_high]))
                    leg_segments.append(([x2, y_high], p2))
                else:
                    leg_segments.append((p1, [x1, y_low]))
                    leg_segments.append(([x1, y_low], [x2, y_low]))
                    leg_segments.append(([x2, y_low], p2))
                    
            # Draw the sub-segments of this leg
            for seg in leg_segments:
                sx1, sy1 = seg[0][0], seg[0][1]
                sx2, sy2 = seg[1][0], seg[1][1]
                
                fig.add_trace(go.Scatter(
                    x=[sx1, sx2], y=[sy1, sy2],
                    mode='lines+markers',
                    line=dict(color='#2563eb', width=3),
                    marker=dict(size=4, color='#2563eb'),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                # Directional Arrow at midpoint of this sub-segment
                dx = sx2 - sx1
                dy = sy2 - sy1
                dist = (dx**2 + dy**2)**0.5
                if dist > 0.5:
                    x_mid = (sx1 + sx2) / 2
                    y_mid = (sy1 + sy2) / 2
                    ux = dx / dist
                    uy = dy / dist
                    arrow_len = min(1.2, dist * 0.4)
                    
                    fig.add_annotation(
                        x=x_mid + ux * (arrow_len / 2),
                        y=y_mid + uy * (arrow_len / 2),
                        ax=x_mid - ux * (arrow_len / 2),
                        ay=y_mid - uy * (arrow_len / 2),
                        xref="x", yref="y",
                        axref="x", ayref="y",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1.2,
                        arrowwidth=2.5,
                        arrowcolor='#2563eb',
                        text="",
                    )
            
            # Place the step number badge for this leg on its longest sub-segment
            longest_seg = None
            max_len = -1
            for seg in leg_segments:
                seg_len = ((seg[1][0] - seg[0][0])**2 + (seg[1][1] - seg[0][1])**2)**0.5
                if seg_len > max_len:
                    max_len = seg_len
                    longest_seg = seg
                    
            if longest_seg is not None:
                bx1, by1 = longest_seg[0][0], longest_seg[0][1]
                bx2, by2 = longest_seg[1][0], longest_seg[1][1]
                bx_mid = (bx1 + bx2) / 2
                by_mid = (by1 + by2) / 2
                
                fig.add_annotation(
                    x=bx_mid, y=by_mid,
                    text=f"<b>{i+1}</b>",
                    showarrow=False,
                    xref="x", yref="y",
                    font=dict(color="#ffffff", size=9, family="Arial", weight="bold"),
                    bgcolor="#1e3a8a",  # Dark Blue badge for leg sequence
                    bordercolor="#ffffff",
                    borderpad=3,
                    borderwidth=1,
                    align="center"
                )
    
    # 5. Plot Visited Pick Locations
    if visited_picks:
        visited_x = [p[0] for p in visited_picks]
        visited_y = [p[1] for p in visited_picks]
        fig.add_trace(go.Scatter(
            x=visited_x, y=visited_y,
            mode='markers',
            name='Picked Items (Completed)',
            marker=dict(size=13, color='#dc2626', symbol='circle'),
            hovertemplate='Pick Location: (%{x}, %{y})<extra></extra>'
        ))
        
    # 6. Plot Unvisited Pick Locations (Pending)
    if unvisited_picks:
        unvisited_x = [p[0] for p in unvisited_picks]
        unvisited_y = [p[1] for p in unvisited_picks]
        fig.add_trace(go.Scatter(
            x=unvisited_x, y=unvisited_y,
            mode='markers',
            name='Items to Pick (Pending)',
            marker=dict(size=12, color='rgba(156, 163, 175, 0.4)', symbol='circle-open', line=dict(color='#9ca3af', width=2)),
            hovertemplate='Pending Location: (%{x}, %{y})<extra></extra>'
        ))
    
    # 7. Plot Depot (Start/End)
    fig.add_trace(go.Scatter(
        x=[depot[0]], y=[depot[1]],
        mode='markers',
        name='Depot (Start/End)',
        marker=dict(size=18, color='#10b981', symbol='square'),
        hovertemplate='Depot Location: (%{x}, %{y})<extra></extra>'
    ))
    
    # 8. Draw picker's current position if step_limit is active
    if step_limit is not None and len(path) > 0:
        current_pos = path[-1]
        fig.add_trace(go.Scatter(
            x=[current_pos[0]], y=[current_pos[1]],
            mode='markers',
            name='Picker Position',
            marker=dict(size=15, color='#f97316', symbol='hexagram', line=dict(color='#ffffff', width=2)),
            hovertemplate='Picker is currently here: (%{x}, %{y})<extra></extra>'
        ))
    
    # 9. Add annotations for sequence numbers on visited items
    for idx, loc in enumerate(list_chemin_limited):
        if loc != depot:
            fig.add_annotation(
                x=loc[0], y=loc[1],
                text=str(idx),
                showarrow=True,
                arrowhead=1,
                ax=0, ay=-18,
                bgcolor="#dc2626",
                bordercolor="#ffffff",
                borderpad=3,
                font=dict(color="#ffffff", size=9, family="Arial", weight="bold")
            )
            
    fig.update_layout(
        title=dict(
            text='Warehouse Order Picking Route Visualization (Realistic Layout)',
            font=dict(color="#1e293b", size=14, family="Inter, sans-serif")
        ),
        width=1000,
        height=650,
        xaxis=dict(
            title=dict(text='X Coordinate (Aisles and Racks)', font=dict(color='#1e293b', size=12)),
            tickfont=dict(color='#1e293b', size=11),
            gridcolor='#f3f4f6',
            range=[-5, 58]
        ),
        yaxis=dict(
            title=dict(text='Y Coordinate (Aisle Height)', font=dict(color='#1e293b', size=12)),
            tickfont=dict(color='#1e293b', size=11),
            gridcolor='#f3f4f6',
            range=[y_low - 5, y_high + 7]
        ),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        font=dict(family="Inter, sans-serif", size=11, color="#1e293b"),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255, 255, 255, 0.8)",
            font=dict(color="#1e293b", size=10)
        )
    )
    
    st.plotly_chart(fig, use_container_width=True, theme=None)

    # 10. Render Detailed Route Execution Steps Table
    st.markdown("### Detailed Route Steps Table")
    table_rows = []
    accumulated_dist = 0
    for idx, loc in enumerate(list_chemin_limited):
        x, y = loc[0], loc[1]
        if idx == 0:
            desc = "Depot (Start)"
            step_dist = 0
        elif idx == len(list_chemin) - 1 and loc == list_chemin[0]:
            desc = "Depot (End)"
            step_dist = distance_picking(list_chemin_limited[idx-1], loc, y_low, y_high)
        else:
            aisle = get_aisle_name(x)
            desc = f"{aisle} (Pick Item)"
            step_dist = distance_picking(list_chemin_limited[idx-1], loc, y_low, y_high)
            
        accumulated_dist += step_dist
        table_rows.append({
            "Visit Sequence": idx,
            "Operation / Location Type": desc,
            "Coordinates (X, Y)": f"({x}, {y})",
            "Step Distance": f"{step_dist} m" if idx > 0 else "-",
            "Cumulative Distance": f"{accumulated_dist} m"
        })
    
    df_table = pd.DataFrame(table_rows)
    st.dataframe(df_table, use_container_width=True, hide_index=True)


def plot_all_picker_routes(df_waves_subset, routes_col, y_low, y_high, zone_split_x=0.0):
    """Render all picker routes simultaneously on a single warehouse map.
    Each picker gets a distinct color. Uses None-separated single traces for performance.
    """
    PICKER_COLORS = [
        '#2563eb',  # Picker 1 — blue
        '#dc2626',  # Picker 2 — red
        '#16a34a',  # Picker 3 — green
        '#d97706',  # Picker 4 — amber
        '#7c3aed',  # Picker 5 — purple
    ]

    fig = go.Figure()

    # ── Warehouse layout ───────────────────────────────────────────────────
    fig.add_shape(type="rect", x0=-5, x1=58, y0=y_low - 1.5, y1=y_low,
                  fillcolor="rgba(243,244,246,0.8)",
                  line=dict(color="rgba(209,213,219,0.5)", width=1), layer="below")
    fig.add_shape(type="rect", x0=-5, x1=58, y0=y_high, y1=y_high + 1.5,
                  fillcolor="rgba(243,244,246,0.8)",
                  line=dict(color="rgba(209,213,219,0.5)", width=1), layer="below")

    racks = [(19.5,20.75),(22.75,24.0),(26.0,28.0),(28.0,29.25),(31.25,32.5),
             (34.5,35.75),(37.75,39.0),(41.0,42.25),(44.25,45.5),(47.5,48.75),(50.75,52.0)]
    for x_min, x_max in racks:
        fig.add_shape(type="rect", x0=x_min, x1=x_max, y0=y_low, y1=y_high,
                      fillcolor="rgba(156,163,175,0.20)",
                      line=dict(color="rgba(107,114,128,0.4)", width=1), layer="below")

    x_aisle_coords = [15.25,19.5,20.75,22.75,24.0,26.0,28.0,29.25,31.25,32.5,
                      34.5,35.75,37.75,39.0,41.0,42.25,44.25,45.5,47.5,48.75,50.75,52.0]
    for idx, x in enumerate(x_aisle_coords):
        fig.add_shape(type="line", x0=x, x1=x, y0=y_low, y1=y_high,
                      line=dict(color="rgba(156,163,175,0.12)", width=1, dash="dash"), layer="below")
        fig.add_annotation(x=x, y=y_high + 3, text=f"A{idx+1:02d}", showarrow=False,
                           font=dict(size=9, color="#4b5563", family="Courier New, monospace"))

    if zone_split_x > 0.0:
        fig.add_shape(type="line", x0=zone_split_x, x1=zone_split_x,
                      y0=y_low - 1.5, y1=y_high + 1.5,
                      line=dict(color="#ef4444", width=2.5, dash="dot"), layer="above")
        fig.add_annotation(x=zone_split_x - 3, y=y_high + 3, text="<b>ZONE 1</b>",
                           showarrow=False, font=dict(size=10, color="#ef4444"))
        fig.add_annotation(x=zone_split_x + 3, y=y_high + 3, text="<b>ZONE 2</b>",
                           showarrow=False, font=dict(size=10, color="#ef4444"))

    # ── Draw each picker — one trace per picker (None-separated segments) ──
    picker_ids = sorted(df_waves_subset['PickerID'].unique()) if 'PickerID' in df_waves_subset.columns else [1]
    total_waves = len(df_waves_subset)

    # Decide render mode: if many waves → scatter-only (fast); few waves → full route lines
    MAX_ROUTE_WAVES = 60  # above this threshold draw pick points only (no route lines)
    draw_lines = total_waves <= MAX_ROUTE_WAVES

    if not draw_lines:
        import streamlit as _st
        _st.info(
            f"ℹ️ **{total_waves} waves** across all pickers — showing pick locations only "
            f"(route lines hidden for performance). Select a specific Picker to see full route lines."
        )

    for picker_id in picker_ids:
        color = PICKER_COLORS[(picker_id - 1) % len(PICKER_COLORS)]
        df_picker = (df_waves_subset[df_waves_subset['PickerID'] == picker_id]
                     if 'PickerID' in df_waves_subset.columns else df_waves_subset)

        # Collect all route x/y coords with None separators (one trace per picker)
        route_x, route_y = [], []
        all_pick_x, all_pick_y = [], []

        for _, row in df_picker.iterrows():
            chemin = row[routes_col]
            if not isinstance(chemin, list) or len(chemin) < 2:
                continue

            depot = chemin[0]

            if draw_lines:
                # Build full path with aisle traversal logic
                for i in range(len(chemin) - 1):
                    p1, p2 = chemin[i], chemin[i + 1]
                    x1, y1 = p1[0], p1[1]
                    x2, y2 = p2[0], p2[1]

                    if x1 == x2:
                        segs = [(p1, p2)]
                    else:
                        ph = (y_high - y1) + (y_high - y2)
                        pl = (y1 - y_low) + (y2 - y_low)
                        if ph < pl:
                            segs = [(p1,[x1,y_high]),([x1,y_high],[x2,y_high]),([x2,y_high],p2)]
                        else:
                            segs = [(p1,[x1,y_low]),([x1,y_low],[x2,y_low]),([x2,y_low],p2)]

                    for seg in segs:
                        route_x += [seg[0][0], seg[1][0], None]
                        route_y += [seg[0][1], seg[1][1], None]

            # Pick locations (always shown)
            picks = [p for p in chemin if p != depot]
            all_pick_x += [p[0] for p in picks]
            all_pick_y += [p[1] for p in picks]

        # Route lines trace (one trace per picker — very efficient)
        if draw_lines and route_x:
            fig.add_trace(go.Scatter(
                x=route_x, y=route_y,
                mode='lines',
                name=f'Picker {picker_id} Route',
                line=dict(color=color, width=2),
                opacity=0.75,
                showlegend=True,
                hoverinfo='skip'
            ))

        # Pick locations scatter (always shown, one trace per picker)
        if all_pick_x:
            fig.add_trace(go.Scatter(
                x=all_pick_x, y=all_pick_y,
                mode='markers',
                name=f'Picker {picker_id} Picks',
                marker=dict(size=7 if draw_lines else 5,
                            color=color, symbol='circle',
                            opacity=0.7 if draw_lines else 0.5,
                            line=dict(color='white', width=1)),
                showlegend=not draw_lines,  # only show in legend when no lines
                hovertemplate=f'Picker {picker_id}: (%{{x}}, %{{y}})<extra></extra>'
            ))

        # Depot marker
        if len(df_picker) > 0:
            first_chemin = df_picker.iloc[0][routes_col]
            if isinstance(first_chemin, list) and len(first_chemin) > 0:
                depot = first_chemin[0]
                fig.add_trace(go.Scatter(
                    x=[depot[0]], y=[depot[1]], mode='markers',
                    name=f'Picker {picker_id} Depot',
                    marker=dict(size=15, color=color, symbol='square',
                                line=dict(color='white', width=2)),
                    showlegend=True,
                    hovertemplate=f'Picker {picker_id} Depot: (%{{x}}, %{{y}})<extra></extra>'
                ))

    fig.update_layout(
        title=dict(
            text=f'All Picker Routes — Warehouse Overview ({total_waves} waves total)',
            font=dict(color="#1e293b", size=14, family="Inter, sans-serif")
        ),
        width=1000, height=650,
        xaxis=dict(title='X Coordinate (Aisles and Racks)',
                   tickfont=dict(color='#1e293b', size=11),
                   gridcolor='#f3f4f6', range=[-5, 58]),
        yaxis=dict(title='Y Coordinate (Aisle Height)',
                   tickfont=dict(color='#1e293b', size=11),
                   gridcolor='#f3f4f6', range=[y_low - 5, y_high + 7]),
        plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
        font=dict(family="Inter, sans-serif", size=11, color="#1e293b"),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01,
                    bgcolor="rgba(255,255,255,0.85)",
                    font=dict(color="#1e293b", size=10))
    )
    st.plotly_chart(fig, use_container_width=True, theme=None)
