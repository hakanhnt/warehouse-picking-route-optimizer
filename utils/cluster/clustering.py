import numpy as np
import pandas as pd
import itertools
from ast import literal_eval
import matplotlib.pyplot as plt
from scipy.cluster.vq import kmeans2, whiten
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import ward, fcluster
from utils.routing.distances import *

def cluster_locations(list_coord, distance_threshold, dist_method, clust_start):
    ''' Step 1: Create clusters of locations'''
    # Create linkage matrix
    if dist_method == 'euclidian':
        Z = ward(pdist(np.stack(list_coord)))
    else:
        Z = ward(pdist(np.stack(list_coord), metric = distance_picking_cluster))
    # Single cluster array
    fclust1 = fcluster(Z, t = distance_threshold, criterion = 'distance')
    return fclust1


def clustering_mapping(df, distance_threshold, dist_method, orders_number, wave_start, clust_start, df_type, max_pcs=0, max_lines=0): # clustering_loc
    '''Step 2: Clustering and mapping'''
    # 1. Create Clusters
    list_coord, list_OrderNumber, clust_id, df = cluster_wave(df, distance_threshold, 'custom', clust_start, df_type)
    clust_idmax = max(clust_id) # Last Cluster ID
    # 2. Mapping Order lines
    dict_map, dict_omap, df, Wave_max = lines_mapping_clst(df, list_coord, list_OrderNumber, clust_id, orders_number, wave_start, max_pcs=max_pcs, max_lines=max_lines)
    return dict_map, dict_omap, df, Wave_max, clust_idmax


def cluster_wave(df, distance_threshold, dist_method, clust_start, df_type):
    '''Step 3: Create waves by clusters'''
    # Create Column for Clustering
    if df_type == 'df_mono':
        df['Coord_Cluster'] = df['Coord'] 
    # Mapping points
    df_map = pd.DataFrame(df.groupby(['OrderNumber', 'Coord_Cluster'])['SKU'].count()).reset_index() 	# Here we use Coord Cluster
    list_coord, list_OrderNumber = np.stack(df_map.Coord_Cluster.apply(lambda t: literal_eval(t)).values), df_map.OrderNumber.values
    # Cluster picking locations
    clust_id = cluster_locations(list_coord, distance_threshold, dist_method, clust_start)
    clust_id = [(i + clust_start) for i in clust_id]
    # List_coord
    list_coord = np.stack(list_coord)
    return list_coord, list_OrderNumber, clust_id, df


def lines_mapping(df, orders_number, wave_start, max_pcs=0, max_lines=0):
    '''Step 4: Mapping Order lines mapping without clustering '''
    df.sort_values(by='DATE', ascending = True, inplace = True)
    # Unique order numbers list
    list_orders = df.OrderNumber.unique()
    # Dictionnary for mapping
    dict_map = dict(zip(list_orders, [i for i in range(1, len(list_orders))]))
    # Order ID mapping
    df['OrderID'] = df['OrderNumber'].map(dict_map)
    
    if max_pcs == 0 and max_lines == 0:
        # Grouping Orders by Wave of orders_number 
        df['WaveID'] = ((df.OrderID%orders_number == 0).shift(1).fillna(0).cumsum() + wave_start).astype(int)
    else:
        df_orders_summary = df.groupby('OrderNumber').agg({
            'DATE': 'first',
            'PCS': 'sum',
            'SKU': 'count'
        }).reset_index()
        df_orders_summary.sort_values(by='DATE', ascending=True, inplace=True)
        
        wave_ids = []
        current_wave_id = wave_start
        current_wave_orders = 0
        current_wave_pcs = 0
        current_wave_lines = 0
        
        for _, row in df_orders_summary.iterrows():
            order_pcs = row['PCS']
            order_lines = row['SKU']
            
            exceeds_orders = current_wave_orders >= orders_number
            exceeds_pcs = (max_pcs > 0) and (current_wave_pcs + order_pcs > max_pcs)
            exceeds_lines = (max_lines > 0) and (current_wave_lines + order_lines > max_lines)
            
            if (exceeds_orders or exceeds_pcs or exceeds_lines) and current_wave_orders > 0:
                current_wave_id += 1
                current_wave_orders = 0
                current_wave_pcs = 0
                current_wave_lines = 0
                
            wave_ids.append(current_wave_id)
            current_wave_orders += 1
            current_wave_pcs += order_pcs
            current_wave_lines += order_lines
            
        df_orders_summary['WaveID'] = wave_ids
        dict_wave_map = dict(zip(df_orders_summary['OrderNumber'], df_orders_summary['WaveID']))
        df['WaveID'] = df['OrderNumber'].map(dict_wave_map)
        
    # Counting number of Waves
    df['WaveID'] = df['WaveID'].astype(int)
    waves_number = int(df.WaveID.max() + 1)
    return df, waves_number


def lines_mapping_clst(df, list_coord, list_OrderNumber, clust_id, orders_number, wave_start, max_pcs=0, max_lines=0):
    '''Step 4: Mapping Order lines mapping with clustering '''
    # Dictionnary for mapping by cluster
    dict_map = dict(zip(list_OrderNumber, clust_id))
    # Dataframe mapping
    df['ClusterID'] = df['OrderNumber'].map(dict_map)
    # Order by ID and mapping
    df = df.sort_values(['ClusterID','OrderNumber'], ascending = True)
    list_orders = list(df.OrderNumber.unique())
    # Dictionnary for order mapping 
    dict_omap = dict(zip(list_orders, [i for i in range(1, len(list_orders))]))
    
    if max_pcs == 0 and max_lines == 0:
        # Order ID mapping
        df['OrderID'] = df['OrderNumber'].map(dict_omap)
        # Create Waves: Increment when reaching orders_number or changing cluster
        df['WaveID'] = (wave_start + ((df.OrderID%orders_number == 0) | (df.ClusterID.diff() != 0)).shift(1).fillna(0).cumsum()).astype(int)
    else:
        # Group and assign wave ID respecting ClusterID change and capacity constraints
        df_orders_summary = df.groupby(['OrderNumber', 'ClusterID']).agg({
            'PCS': 'sum',
            'SKU': 'count'
        }).reset_index()
        df_orders_summary.sort_values(by=['ClusterID', 'OrderNumber'], ascending=True, inplace=True)
        
        wave_ids = []
        current_wave_id = wave_start
        current_wave_orders = 0
        current_wave_pcs = 0
        current_wave_lines = 0
        previous_cluster_id = None
        
        for _, row in df_orders_summary.iterrows():
            order_pcs = row['PCS']
            order_lines = row['SKU']
            cluster_id = row['ClusterID']
            
            exceeds_orders = current_wave_orders >= orders_number
            exceeds_pcs = (max_pcs > 0) and (current_wave_pcs + order_pcs > max_pcs)
            exceeds_lines = (max_lines > 0) and (current_wave_lines + order_lines > max_lines)
            cluster_changed = (previous_cluster_id is not None) and (cluster_id != previous_cluster_id)
            
            if (exceeds_orders or exceeds_pcs or exceeds_lines or cluster_changed) and current_wave_orders > 0:
                current_wave_id += 1
                current_wave_orders = 0
                current_wave_pcs = 0
                current_wave_lines = 0
                
            wave_ids.append(current_wave_id)
            current_wave_orders += 1
            current_wave_pcs += order_pcs
            current_wave_lines += order_lines
            previous_cluster_id = cluster_id
            
        df_orders_summary['WaveID'] = wave_ids
        dict_wave_map = dict(zip(df_orders_summary['OrderNumber'], df_orders_summary['WaveID']))
        df['WaveID'] = df['OrderNumber'].map(dict_wave_map)

    df['WaveID'] = df['WaveID'].astype(int)
    wave_max = int(df.WaveID.max())
    return dict_map, dict_omap, df, wave_max


def locations_listing(df_orderlines, wave_id):
    ''' Step 5: Listing location per Wave of orders'''

    # Filter by wave_id
    df = df_orderlines[df_orderlines.WaveID == wave_id]
    # Create coordinates listing
    list_coord = list(df['Coord'].apply(lambda t: literal_eval(t)).values) 	# Here we use Coord for distance
    list_coord.sort()
    # Get unique Unique coordinates
    list_coord = list(k for k,_ in itertools.groupby(list_coord))
    n_locs = len(list_coord)
    n_lines = len(df)
    n_pcs = df.PCS.sum()

    return list_coord, n_locs, n_lines, n_pcs


def assign_pickers_to_waves(df_waves, routes_col, n_pickers, zone_split_active=False):
    '''Assign waves to N pickers.
    
    When zone_split_active=True and ZoneID column exists, PickerID is assigned
    directly from ZoneID (Zone 1 → Picker 1, Zone 2 → Picker 2, ...) so that
    each picker works exclusively in their own zone with no overlap.
    
    When zone_split_active=False, KMeans clustering on wave centroids is used
    to spatially separate pickers.
    '''
    if n_pickers <= 1 or len(df_waves) == 0:
        df_waves['PickerID'] = 1
        return df_waves

    # ── Zone-based direct assignment ──────────────────────────────────────
    # If zones already exist, map ZoneID → PickerID directly.
    # This guarantees Zone 1 = Picker 1, Zone 2 = Picker 2, etc.
    if zone_split_active and 'ZoneID' in df_waves.columns:
        unique_zones = sorted(df_waves['ZoneID'].unique())
        zone_to_picker = {z: (i + 1) for i, z in enumerate(unique_zones)}
        df_waves['PickerID'] = df_waves['ZoneID'].map(zone_to_picker).fillna(1).astype(int)
        return df_waves

    # ── KMeans spatial clustering (no zone split) ─────────────────────────
    centroids = []
    for idx, row in df_waves.iterrows():
        route = row[routes_col]
        if isinstance(route, list) and len(route) > 0:
            xs = [p[0] for p in route]
            ys = [p[1] for p in route]
            centroids.append([np.mean(xs), np.mean(ys)])
        else:
            centroids.append([0.0, 0.0])

    centroids = np.array(centroids)
    k = min(n_pickers, len(df_waves))

    try:
        whitened = whiten(centroids)
        if np.isnan(whitened).any():
            whitened = centroids
        _, labels = kmeans2(whitened, k, iter=20, minit='points')
    except Exception:
        xs = centroids[:, 0]
        sorted_indices = np.argsort(xs)
        labels = np.zeros(len(df_waves), dtype=int)
        chunk_size = int(np.ceil(len(df_waves) / k))
        for i in range(k):
            labels[sorted_indices[i*chunk_size : (i+1)*chunk_size]] = i

    df_waves['PickerID'] = labels + 1
    return df_waves