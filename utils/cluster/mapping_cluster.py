from utils.cluster.clustering import *
from utils.process.processing import *
from utils.routing.distances import *


def df_mapping(df_orderlines, orders_number, distance_threshold, mono_method, multi_method, max_pcs=0, max_lines=0, zone_split_x=0.0):
    ''' Mapping Order lines Dataframe using clustering with trolley capacity constraints and zone splitting'''
    # Parse X coordinate
    df_orderlines['X_coord'] = df_orderlines['Coord'].apply(lambda t: literal_eval(t)[0] if isinstance(t, str) else t[0])
    
    # Assign ZoneID (Zone 1: X < zone_split_x, Zone 2: X >= zone_split_x)
    if zone_split_x > 0.0:
        df_orderlines['ZoneID'] = np.where(df_orderlines['X_coord'] < zone_split_x, 1, 2)
    else:
        df_orderlines['ZoneID'] = 1
        
    df_result_list = []
    wave_start = 0
    clust_start = 0
    
    for zone_id in sorted(df_orderlines['ZoneID'].unique()):
        df_zone = df_orderlines[df_orderlines['ZoneID'] == zone_id].copy()
        if len(df_zone) == 0:
            continue
            
        # Filter mono and multi orders within this zone
        df_mono, df_multi = process_lines(df_zone)
        
        # Mapping for single line orders
        if mono_method == 'clustering':		
            df_type = 'df_mono' 	
            dict_map, dict_omap, df_mono, waves_number, clust_idmax = clustering_mapping(df_mono, distance_threshold, 'custom', 
                orders_number, wave_start, clust_start, df_type, max_pcs=max_pcs, max_lines=max_lines)
        else: 
            df_mono, waves_number = lines_mapping(df_mono, orders_number, wave_start, max_pcs=max_pcs, max_lines=max_lines)
            clust_idmax = 0 
            
        wave_start = waves_number
        clust_start = clust_idmax 
    
        # Mapping for multi line orders
        if multi_method == 'clustering':
            df_type = 'df_multi' 	
            df_multi = centroid_mapping(df_multi)
            dict_map, dict_omap, df_multi, waves_number, clust_idmax  = clustering_mapping(df_multi, distance_threshold, 'custom', 
                orders_number, wave_start, clust_start, df_type, max_pcs=max_pcs, max_lines=max_lines)
        else:
            df_multi, waves_number = lines_mapping(df_multi, orders_number, wave_start, max_pcs=max_pcs, max_lines=max_lines)
            
        # Update wave_start and clust_start for the next zone
        wave_start = waves_number
        clust_start = clust_idmax
        
        # Concat mono and multi for this zone
        df_zone_mapped, _ = monomult_concat(df_mono, df_multi)
        df_result_list.append(df_zone_mapped)
        
    # Concatenate all zones
    df_orderlines = pd.concat(df_result_list)
    waves_number = df_orderlines.WaveID.max() + 1
    
    return df_orderlines, waves_number