import concurrent.futures
import os
from concurrent.futures.process import BrokenProcessPool

import pandas as pd

from utils.batch.mapping_batch import orderlines_mapping
from utils.routing.routes import create_picking_route, create_picking_route_ortools
from utils.cluster.clustering import assign_pickers_to_waves, locations_listing


def run_tasks_with_fallback(worker, tasks):
	'''Run tasks in a process pool, falling back to sequential execution when processes are unavailable.'''
	if not tasks:
		return []

	max_workers = min(len(tasks), os.cpu_count() or 1, 4)
	try:
		with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
			return list(executor.map(worker, tasks))
	except (PermissionError, OSError, BrokenProcessPool) as exc:
		print(f"Parallel execution unavailable ({exc}); running sequentially.")
		return [worker(task) for task in tasks]

def simulation_wave(y_low, y_high, origin_loc, orders_number, df_orderlines, list_wid, list_dst, list_route, list_ord, list_zone, use_ortools=True, max_pcs=0, max_lines=0, zone_split_x=0.0):
	''' Simulate of total picking distance with n orders per wave'''
	distance_route = 0 
	# Create waves
	df_orderlines, waves_number = orderlines_mapping(df_orderlines, orders_number, max_pcs=max_pcs, max_lines=max_lines, zone_split_x=zone_split_x)
	for wave_id in range(waves_number):
		# Listing of all locations for this wave 
		list_locs, n_locs, n_lines, n_pcs = locations_listing(df_orderlines, wave_id)
		
		# Get ZoneID for this wave
		df_wave = df_orderlines[df_orderlines.WaveID == wave_id]
		zone_id = df_wave['ZoneID'].iloc[0] if 'ZoneID' in df_wave.columns else 1
		
		# Results
		if use_ortools:
			wave_distance, list_chemin = create_picking_route_ortools(origin_loc, list_locs, y_low, y_high)
		else:
			wave_distance, list_chemin = create_picking_route(origin_loc, list_locs, y_low, y_high)
		distance_route = distance_route + wave_distance
		list_wid.append(wave_id)
		list_dst.append(wave_distance)
		list_route.append(list_chemin)
		list_ord.append(orders_number)
		list_zone.append(zone_id)
	return list_wid, list_dst, list_route, list_ord, list_zone, distance_route

def simulate_batch_worker(args):
	y_low, y_high, origin_loc, orders_number, df_orderlines, use_ortools, max_pcs, max_lines, zone_split_x = args
	list_wid, list_dst, list_route, list_ord, list_zone = [], [], [], [], []
	list_wid, list_dst, list_route, list_ord, list_zone, distance_route = simulation_wave(
		y_low, y_high, origin_loc, orders_number, df_orderlines, 
		list_wid, list_dst, list_route, list_ord, list_zone, use_ortools=use_ortools,
		max_pcs=max_pcs, max_lines=max_lines, zone_split_x=zone_split_x
	)
	return list_wid, list_dst, list_route, list_ord, list_zone, distance_route

def simulate_batch(n1, n2, y_low, y_high, origin_loc, orders_number, df_orderlines, use_ortools=True, max_pcs=0, max_lines=0, zone_split_x=0.0, n_pickers=1):
	''' Loop with several scenarios of n orders per wave, parallelized '''
	tasks = [
		(y_low, y_high, origin_loc, o_num, df_orderlines.copy(), use_ortools, max_pcs, max_lines, zone_split_x)
		for o_num in range(n1, n2 + 1)
	]
	
	list_wid, list_dst, list_route, list_ord, list_zone = [], [], [], [], []
	
	results = run_tasks_with_fallback(simulate_batch_worker, tasks)
		
	# Sort results to ensure chronological ordering of wave sizes
	results = sorted(results, key=lambda x: x[3][0] if x[3] else 0)
	
	for res_wid, res_dst, res_route, res_ord, res_zone, distance_route in results:
		list_wid.extend(res_wid)
		list_dst.extend(res_dst)
		list_route.extend(res_route)
		list_ord.extend(res_ord)
		list_zone.extend(res_zone)
		print("Total distance covered for {} orders/wave: {:,} m".format(res_ord[0] if res_ord else 0, distance_route))

	# By Wave
	df_waves = pd.DataFrame({'wave': list_wid,
				'distance': list_dst,
				'routes': list_route,
				'order_per_wave': list_ord,
				'ZoneID': list_zone})
				
	# Assign pickers to waves per order_per_wave scenario
	df_list = []
	for opw in sorted(df_waves['order_per_wave'].unique()):
		df_opw = df_waves[df_waves['order_per_wave'] == opw].copy()
		df_opw = assign_pickers_to_waves(df_opw, 'routes', n_pickers, zone_split_active=(zone_split_x > 0))
		df_list.append(df_opw)
	df_waves = pd.concat(df_list) if df_list else df_waves

	# Results aggregate
	df_results = pd.DataFrame(df_waves.groupby(['order_per_wave'])['distance'].sum())
	df_results.columns = ['distance']
	return df_waves, df_results.reset_index()
