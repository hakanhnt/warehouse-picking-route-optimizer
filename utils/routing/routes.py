import pandas as pd
import numpy as np 
import itertools
from ast import literal_eval
from utils.routing.distances import *
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def create_picking_route(origin_loc, list_locs, y_low, y_high):
    '''Calculate total distance to cover for a list of locations (Greedy Next Closest Location)'''
    # Total distance variable
    wave_distance = 0
    # Current location variable 
    start_loc = origin_loc
    # Store routes
    list_chemin = []
    list_chemin.append(start_loc)
    
    while len(list_locs) > 0: # Looping until all locations are picked
        # Going to next location
        list_locs, start_loc, next_loc, distance_next = next_location(start_loc, list_locs, y_low, y_high)
        # Update start_loc 
        start_loc = next_loc
        list_chemin.append(start_loc)
        # Update distance
        wave_distance = wave_distance + distance_next 

    # Final distance from last storage location to origin
    wave_distance = wave_distance + distance_picking(start_loc, origin_loc, y_low, y_high)
    list_chemin.append(origin_loc)

    return wave_distance, list_chemin

# Calculate total distance to cover for a list of locations
def create_picking_route_cluster(origin_loc, list_locs, y_low, y_high):
    # Total distance variable
    wave_distance = 0
    # Distance max
    distance_max = 0
    # Current location variable 
    start_loc = origin_loc
    # Store routes
    list_chemin = []
    list_chemin.append(start_loc)
    while len(list_locs) > 0: # Looping until all locations are picked
        # Going to next location
        list_locs, start_loc, next_loc, distance_next = next_location(start_loc, list_locs, y_low, y_high)
        # Update start_loc 
        start_loc = next_loc
        list_chemin.append(start_loc)
        if distance_next > distance_max:
            distance_max = distance_next
        # Update distance
        wave_distance = wave_distance + distance_next 
    # Final distance from last storage location to origin
    wave_distance = wave_distance + distance_picking(start_loc, origin_loc, y_low, y_high)
    list_chemin.append(origin_loc)
    return wave_distance, list_chemin, distance_max

def create_picking_route_ortools(origin_loc, list_locs, y_low, y_high):
    """Calculate picker route using Google OR-Tools (TSP Solver)"""
    clean_locs = [loc for loc in list_locs if loc != origin_loc]
    if len(clean_locs) == 0:
        return 0, [origin_loc, origin_loc]
        
    chemin = [origin_loc] + clean_locs
    
    # Calculate distance matrix
    distance_matrix = []
    for i in range(len(chemin)):
        row = []
        for j in range(len(chemin)):
            row.append(int(distance_picking(chemin[i], chemin[j], y_low, y_high)))
        distance_matrix.append(row)
        
    # OR-Tools TSP setup
    manager = pywrapcp.RoutingIndexManager(len(chemin), 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]
        
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    
    solution = routing.SolveWithParameters(search_parameters)
    
    if solution:
        index = routing.Start(0)
        plan_output = []
        route_distance = 0
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            plan_output.append(chemin[node_index])
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(previous_index, index, 0)
        plan_output.append(chemin[manager.IndexToNode(index)])
        return route_distance, plan_output
    else:
        # Fallback to greedy (NCL)
        return create_picking_route(origin_loc, list_locs, y_low, y_high)

def create_picking_route_cluster_ortools(origin_loc, list_locs, y_low, y_high):
    """Calculates route using Google OR-Tools and tracks maximum step distance"""
    dist, plan = create_picking_route_ortools(origin_loc, list_locs, y_low, y_high)
    
    # Calculate max distance step
    distance_max = 0
    for i in range(len(plan) - 1):
        step_dist = distance_picking(plan[i], plan[i+1], y_low, y_high)
        if step_dist > distance_max:
            distance_max = step_dist
            
    return dist, plan, distance_max