#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Visualization helper for planned roads.
# rostopic echo -b 1218_03_new.bag -p /ublox_driver/receiver_lla > gps_from_121803new.csv
# Run from the repository workspace or the package source directory.
# python -m global_planning.visualize_roads --csv ~/Datasets/gps_from_121801bag.csv --topic_type navsat
"""
Offline visualization and analysis of GlobalPlanner roads and current polyline point.

Usage (example):
    python visualize_roads.py \
        --csv /path/to/gps.csv \
        --topic_type navsat

This script:
  - Reads a CSV exported from rosbag (e.g. `rostopic echo -b bag.bag -p /gps/fix > gps.csv`)
  - Converts it into a sequence of positions (lat, lon)
  - Runs the GlobalPlanner on this sequence, recording:
      * status (which road index)
      * sub_status (which point along that road)
      * current polyline point
      * target azimuth (if needed)
  - Plots:
      * All roads polylines
      * The sequence of “current polyline points” over time
"""

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button

from .global_planner import GlobalPlanner
from .gnss_compute import get_p2pgeodesic
from .gps_transform import wgs842gcj02
def parse_args():
    parser = argparse.ArgumentParser(description="Offline visualization of GlobalPlanner roads and current polyline point.")
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="Path to CSV file exported from rosbag (e.g. gps.csv or odom.csv).",
    )
    parser.add_argument(
        "--topic_type",
        type=str,
        default="navsat",
        choices=["navsat", "odom"],
        help="Type of CSV data: 'navsat' for sensor_msgs/NavSatFix, 'odom' for nav_msgs/Odometry-like x,y.",
    )
    parser.add_argument(
        "--start_lat",
        type=float,
        help="Optional: override start latitude (if CSV does not contain a good start point).",
    )
    parser.add_argument(
        "--start_lon",
        type=float,
        help="Optional: override start longitude.",
    )
    parser.add_argument(
        "--end_lat",
        type=float,
        help="Optional: override end latitude (destination).",
    )
    parser.add_argument(
        "--end_lon",
        type=float,
        help="Optional: override end longitude.",
    )
    return parser.parse_args()

def load_navsat_csv(csv_path: str):
    """
    Load a CSV generated from sensor_msgs/NavSatFix, e.g.:
        rostopic echo -b bag.bag -p /gps/fix > gps.csv

    Expected columns: 'field.latitude', 'field.longitude'
    """
    df = pd.read_csv(csv_path)
    df = df.sort_values("%time")
    lat = df["field.latitude"].values
    lon = df["field.longitude"].values
    mask = np.isfinite(lat) & np.isfinite(lon)
    lat = lat[mask]
    lon = lon[mask]
    locations = [(lat[i], lon[i]) for i in range(len(lat))]
    return locations

def load_odom_csv(csv_path: str, origin_latlon=None):
    """
    Load a CSV generated from nav_msgs/Odometry-like topic, e.g.:
        rostopic echo -b bag.bag -p /odom > odom.csv

    Expected columns: 'field.pose.pose.position.x', 'field.pose.pose.position.y'

    If you want to map x,y back to lat,lon, you can optionally provide an origin_latlon
    and use get_p2pgeodesic inversely. For now, we treat x,y as an abstract local frame.
    """
    df = pd.read_csv(csv_path)
    df = df.sort_values("%time")
    x = df["field.pose.pose.position.x"].values
    y = df["field.pose.pose.position.y"].values
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    # For odom, we just return as (x, y) in a local frame.
    locations = [(x[i], y[i]) for i in range(len(x))]
    return locations

def pick_start_end(locations, args):
    """
    Decide start_point and end_point for GlobalPlanner.

    For navsat mode:
        locations are (lat, lon). Use args.start_lat/lon or first/last point.

    For odom mode:
        locations are (x, y). In that case you must provide start/end lat/lon
        explicitly if you want to call GlobalPlanner which expects gcj02 lat/lon.
    """
    if args.start_lat is not None and args.start_lon is not None:
        start_point = (args.start_lat, args.start_lon)
    else:
        # Default: use first location as start
        start_point = locations[0]

    if args.end_lat is not None and args.end_lon is not None:
        end_point = (args.end_lat, args.end_lon)
    else:
        # Default: use last location as end
        end_point = locations[-1]

    return start_point, end_point

def run_global_planner(locations, start_point, end_point):
    """
    Run GlobalPlanner on a sequence of lat/lon locations.
    Record status, sub_status, and the corresponding polyline point.
    """
    gp = GlobalPlanner(start_point, end_point)

    status_list = []
    sub_status_list = []
    poly_points = []  # current polyline point for each location
    label_list = []  # 'status-sub_status' label for each frame
    target_az_list = []   # target azimuth (deg) per frame
    target_dir_list = []  # target direction as (d_lon, d_lat) per frame in plot coords
    self_dir_list = []  # per-frame self.target_direction as (d_lon, d_lat) for plotting
    is_turn_list = []  # record gp.is_turn per frame

    for p in locations:
        gp.update(p)

        status_list.append(gp.status)
        sub_status_list.append(gp.sub_status)
        label_list.append(f"{gp.status}-{gp.sub_status}")
        is_turn_list.append(getattr(gp, "is_turn", False))

        # Capture self.target_direction if GlobalPlanner provides it
        td = getattr(gp, "target_direction", None)
        if td is not None:
            td_vec = np.array(td, dtype=float).reshape(-1)
            if td_vec.size >= 2:
                td_xy = td_vec[:2]
                td_norm = np.linalg.norm(td_xy)
            else:
                td_norm = 0.0
        else:
            td_norm = 0.0

        if td_norm > 1e-6:
            td_xy = td_xy / td_norm
            lat0 = p[0]
            m_per_deg_lat = 111320.0
            m_per_deg_lon = 111320.0 * np.cos(np.deg2rad(lat0))
            step_m = 10.0
            # td_xy is in local ENU-like meters: x=east, y=north (consistent with azimuth->d_east/d_north)
            d_east = step_m * td_xy[0]
            d_north = step_m * td_xy[1]
            d_lat = d_north / m_per_deg_lat
            d_lon = d_east / m_per_deg_lon if m_per_deg_lon > 1e-6 else 0.0
            self_dir_list.append((d_lon, d_lat))
        else:
            self_dir_list.append((np.nan, np.nan))

        # Compute target azimuth using current logic
        try:
            target_az = gp.get_target_azimuth(p)
        except Exception:
            target_az = np.nan
        target_az_list.append(target_az)

        # Convert azimuth to a small delta in lon/lat for arrow drawing.
        # 0 deg = north, clockwise positive. Plot x=lon, y=lat.
        if np.isfinite(target_az):
            lat0, lon0 = p[0], p[1]
            # meters per degree
            m_per_deg_lat = 111320.0
            m_per_deg_lon = 111320.0 * np.cos(np.deg2rad(lat0))
            step_m = 10.0  # arrow length in meters
            theta = np.deg2rad(target_az)
            d_north = step_m * np.cos(theta)
            d_east = step_m * np.sin(theta)
            d_lat = d_north / m_per_deg_lat
            d_lon = d_east / m_per_deg_lon if m_per_deg_lon > 1e-6 else 0.0
            target_dir_list.append((d_lon, d_lat))
        else:
            target_dir_list.append((np.nan, np.nan))

        # Fallback: if self.target_direction unavailable for this frame, use azimuth-derived direction
        if not (np.isfinite(self_dir_list[-1][0]) and np.isfinite(self_dir_list[-1][1])) and np.isfinite(target_dir_list[-1][0]) and np.isfinite(target_dir_list[-1][1]):
            self_dir_list[-1] = target_dir_list[-1]

        if gp.status >= 0 and 0 <= gp.status < len(gp.roads):
            road = gp.roads[gp.status]
            if len(road["polyline"]) > 0:
                idx = max(0, min(gp.sub_status, len(road["polyline"]) - 1))
                poly_points.append(road["polyline"][idx])
            else:
                poly_points.append((np.nan, np.nan))
        else:
            poly_points.append((np.nan, np.nan))

    return (gp, np.array(status_list), np.array(sub_status_list),
            poly_points, label_list, np.array(target_az_list), target_dir_list,
            self_dir_list, is_turn_list)

def plot_roads_and_poly_points(gp: GlobalPlanner, locations, poly_points, labels,
                               target_az_list, target_dir_list, is_turn_list,
                               max_labels=200, max_static_frames=300):
    """Plot roads, actual GPS, matched polyline points, and per-frame direction.

    If number of frames is small (<= max_static_frames), draw everything on one static figure.
    Otherwise, create an interactive slider to step through frames.
    """
    n_frames = len(locations)

    # --- Common background figure ---
    fig, ax = plt.subplots(figsize=(8, 8))
    plt.subplots_adjust(bottom=0.18)

    scale_factor = 1.2
    def on_scroll(event):
        if event.inaxes != ax:
            return
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        xdata = event.xdata
        ydata = event.ydata
        if event.button == 'up':
            new_xlim = [xdata - (xdata - cur_xlim[0]) / scale_factor,
                        xdata + (cur_xlim[1] - xdata) / scale_factor]
            new_ylim = [ydata - (ydata - cur_ylim[0]) / scale_factor,
                        ydata + (cur_ylim[1] - ydata) / scale_factor]
        elif event.button == 'down':
            new_xlim = [xdata - (xdata - cur_xlim[0]) * scale_factor,
                        xdata + (cur_xlim[1] - xdata) * scale_factor]
            new_ylim = [ydata - (ydata - cur_ylim[0]) * scale_factor,
                        ydata + (cur_ylim[1] - ydata) * scale_factor]
        else:
            return
        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)
        fig.canvas.draw_idle()
    fig.canvas.mpl_connect('scroll_event', on_scroll)

    # Plot all roads
    for ridx, road in enumerate(gp.roads):
        pts = road.get("polyline", [])
        if not pts:
            continue
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        ax.plot(lons, lats, "-", alpha=0.7, label=f"road {ridx}")
        ax.scatter(lons, lats, s=6, alpha=0.6)

    # Plot actual GPS trajectory (blue line)
    loc_lats = [p[0] for p in locations]
    loc_lons = [p[1] for p in locations]
    ax.plot(loc_lons, loc_lats, "b-", alpha=0.5, label="actual GPS")

    # Valid matched points indices
    valid_idx = [i for i, p in enumerate(poly_points)
                 if not (np.isnan(p[0]) or np.isnan(p[1]))]

    # --- Static mode ---
    if n_frames <= max_static_frames:
        # red dots only
        if valid_idx:
            cp_lats = [poly_points[i][0] for i in valid_idx]
            cp_lons = [poly_points[i][1] for i in valid_idx]
            ax.scatter(cp_lons, cp_lats, c='r', s=10, label="matched polyline point")

            # annotate labels (downsample)
            if labels is not None and len(labels) == len(poly_points):
                step = max(1, len(valid_idx) // max_labels)
                for k in range(0, len(valid_idx), step):
                    i = valid_idx[k]
                    ax.text(poly_points[i][1], poly_points[i][0], labels[i],
                            fontsize=6, color='r')

        # draw per-frame arrows sparsely to avoid clutter
        step_arrow = max(1, n_frames // max_labels)
        for i in range(0, n_frames, step_arrow):
            dlon, dlat = target_dir_list[i]
            if not (np.isfinite(dlon) and np.isfinite(dlat)):
                continue
            lat0, lon0 = locations[i][0], locations[i][1]
            ax.arrow(lon0, lat0, dlon, dlat, width=0.0, head_width=1e-5,
                     length_includes_head=True, color='g', alpha=0.8)

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("Static view: roads, GPS, matched points, target_direction")
        ax.axis("equal")
        ax.grid(True)
        ax.legend()
        plt.show()
        return

    # --- Interactive mode ---
    # artists for current frame
    cur_gps_scatter = ax.scatter([], [], c='b', s=30, label="current GPS")
    cur_poly_scatter = ax.scatter([], [], c='r', s=40, label="current polyline point")
    cur_arrow = None
    cur_text = ax.text(0.01, 0.99, "", transform=ax.transAxes,
                       va='top', ha='left', fontsize=10,
                       bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    def draw_frame(i):
        nonlocal cur_arrow
        i = int(i)
        lat0, lon0 = locations[i][0], locations[i][1]
        cur_gps_scatter.set_offsets([[lon0, lat0]])

        if 0 <= i < len(poly_points) and np.isfinite(poly_points[i][0]) and np.isfinite(poly_points[i][1]):
            cur_poly_scatter.set_offsets([[poly_points[i][1], poly_points[i][0]]])
        else:
            cur_poly_scatter.set_offsets(np.empty((0, 2)))

        # remove old arrow
        if cur_arrow is not None:
            cur_arrow.remove()
            cur_arrow = None

        dlon, dlat = target_dir_list[i]
        if np.isfinite(dlon) and np.isfinite(dlat):
            cur_arrow = ax.arrow(lon0, lat0, dlon, dlat, width=0.0, head_width=1e-5,
                                 length_includes_head=True, color='g')

        label = labels[i] if labels is not None and i < len(labels) else "?"
        az = target_az_list[i] if i < len(target_az_list) else np.nan
        turn_flag = is_turn_list[i] if i < len(is_turn_list) else False
        cur_text.set_text(f"frame: {i}\nstatus-sub_status: {label}\ntarget_azimuth: {az:.2f} deg\nis_turn: {turn_flag}")
        fig.canvas.draw_idle()

    # Slider axis
    ax_slider = plt.axes([0.15, 0.05, 0.7, 0.03])
    slider = Slider(ax_slider, 'frame', 0, n_frames - 1, valinit=0, valstep=1)
    slider.on_changed(draw_frame)

    # Initialize first frame
    draw_frame(0)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Interactive view (use slider): roads, current polyline point, target_direction")
    ax.axis("equal")
    ax.grid(True)
    ax.legend()
    plt.show()

def main():
    args = parse_args()

    if args.topic_type == "navsat":
        locations = load_navsat_csv(args.csv)
    else:
        locations = load_odom_csv(args.csv)
    # Convert everything to GCJ02 so the visualization uses a consistent coordinate frame.
    # locations_gcj = []
    # for (lat, lon) in locations:
    #     gcj = wgs842gcj02(lat, lon)
    #     locations_gcj.append((gcj["lat"], gcj["lon"]))
    # locations = locations_gcj

    if len(locations) < 2:
        raise RuntimeError("Not enough locations loaded from CSV to run analysis.")

    start_point, end_point = pick_start_end(locations, args)
    # start_point = (39.98139,116.32492)
    end_point = (39.98096, 116.32709)
    print("[INFO] Using start_point:", start_point)
    print("[INFO] Using end_point  :", end_point)
    print("[INFO] Number of locations:", len(locations))

    gp, status_list, sub_status_list, poly_points, labels, target_az_list, target_dir_list, self_dir_list, is_turn_list = run_global_planner(
        locations, start_point, end_point
    )

    print("[INFO] Roads planned:", len(gp.roads))
    print("[INFO] Status range:", np.min(status_list), "to", np.max(status_list))

    plot_roads_and_poly_points(gp, locations, poly_points, labels, target_az_list, self_dir_list, is_turn_list)
if __name__ == "__main__":
    main()
