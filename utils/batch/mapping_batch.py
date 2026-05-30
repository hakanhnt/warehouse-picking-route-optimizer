import numpy as np
import pandas as pd
import itertools
from ast import literal_eval


def orderlines_mapping(df_orderlines, orders_number, max_pcs=0, max_lines=0, zone_split_x=0.0):
	'''Mapping orders with wave number, trolley capacity constraints, and zone splitting'''
	df_orderlines.sort_values(by='DATE', ascending = True, inplace = True)
	
	# Parse X coordinate
	df_orderlines['X_coord'] = df_orderlines['Coord'].apply(lambda t: literal_eval(t)[0] if isinstance(t, str) else t[0])
	
	# Assign ZoneID (Zone 1: X < zone_split_x, Zone 2: X >= zone_split_x)
	if zone_split_x > 0.0:
		df_orderlines['ZoneID'] = np.where(df_orderlines['X_coord'] < zone_split_x, 1, 2)
	else:
		df_orderlines['ZoneID'] = 1
		
	# Now group by ZoneID and run mapping for each zone
	# WaveID must be globally unique across zones, so we offset WaveIDs of Zone 2 by Zone 1's max WaveID.
	df_orderlines['WaveID'] = 0
	df_orderlines['OrderID'] = 0
	
	wave_offset = 0
	
	for zone_id in sorted(df_orderlines['ZoneID'].unique()):
		df_zone = df_orderlines[df_orderlines['ZoneID'] == zone_id].copy()
		if len(df_zone) == 0:
			continue
			
		list_orders = df_zone.OrderNumber.unique()
		dict_map = dict(zip(list_orders, [i for i in range(1, len(list_orders) + 1)]))
		df_zone['OrderID'] = df_zone['OrderNumber'].map(dict_map)
		
		if max_pcs == 0 and max_lines == 0:
			df_zone['WaveID'] = (df_zone.OrderID%orders_number == 0).shift(1).fillna(0).cumsum() + wave_offset
		else:
			df_orders_summary = df_zone.groupby('OrderNumber').agg({
				'DATE': 'first',
				'PCS': 'sum',
				'SKU': 'count'
			}).reset_index()
			df_orders_summary.sort_values(by='DATE', ascending=True, inplace=True)
			
			wave_ids = []
			current_wave_id = wave_offset
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
			df_zone['WaveID'] = df_zone['OrderNumber'].map(dict_wave_map)
			
		# Update overall dataframe
		df_orderlines.loc[df_orderlines['ZoneID'] == zone_id, 'OrderID'] = df_zone['OrderID'].astype(int).values
		df_orderlines.loc[df_orderlines['ZoneID'] == zone_id, 'WaveID'] = df_zone['WaveID'].astype(int).values
		wave_offset = int(df_zone['WaveID'].max()) + 1
		
	# Counting number of Waves
	df_orderlines['WaveID'] = df_orderlines['WaveID'].astype(int)
	df_orderlines['OrderID'] = df_orderlines['OrderID'].astype(int)
	waves_number = int(df_orderlines.WaveID.max() + 1)
	return df_orderlines, waves_number

def locations_listing(df_orderlines, wave_id):
	'''Getting storage locations to cover for a wave of orders'''
	df = df_orderlines[df_orderlines.WaveID == wave_id]
	# Create coordinates listing
	list_locs = list(df['Coord'].apply(lambda t: literal_eval(t)).values)
	list_locs.sort()
	# List of unique coordinates
	list_locs = list(k for k,_ in itertools.groupby(list_locs))
	n_locs = len(list_locs)
	return list_locs, n_locs