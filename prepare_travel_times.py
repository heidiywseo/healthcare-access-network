"""Compute network travel times (driving and public transit) with R5, OpenStreetMap and SEPTA GTFS.

Usage:
  python prepare_travel_times.py --osm philadelphia.osm.pbf --gtfs google_bus.zip google_rail.zip \
      [--date 2026-11-17] [--window am=07:00 midday=11:00 evening=17:00] [--window-hours 2]

Inputs (download yourself; see docs/GEOGRAPHY.md):
  --osm   OpenStreetMap .osm.pbf covering Philadelphia (Geofabrik Pennsylvania extract, optionally clipped).
  --gtfs  SEPTA GTFS feeds. SEPTA's gtfs_public.zip contains two inner zips; pass both inner files.
  --date  A weekday inside the GTFS service calendar.
  --window  Transit departure windows as key=HH:MM (each lasts --window-hours). The first is the default in the app.

Outputs:
  data/travel_times.csv       one row per (origin tract, destination); destinations are all providers and all
                              tracts (tract-to-tract times are used for hypothetical new clinics placed on the map)
  data/travel_times_meta.json sources and routing settings

Requires Java 21 and r5py (pip install r5py). Only this script needs them; the server does not.
"""
import argparse, datetime as dt, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument('--osm', required=True)
ap.add_argument('--gtfs', nargs='+', required=True)
ap.add_argument('--date', default='2026-11-17')
ap.add_argument('--window', nargs='+', default=['am=07:00', 'midday=11:00', 'evening=17:00'])
ap.add_argument('--window-hours', type=float, default=2)
ap.add_argument('--max-minutes', type=int, default=180)
args = ap.parse_args()

# r5py needs Java 21; select it explicitly in case an older Java is the system default.
if sys.platform == 'darwin' and not os.environ.get('JAVA_HOME', '').count('21'):
    try:
        os.environ['JAVA_HOME'] = subprocess.check_output(['/usr/libexec/java_home', '-v', '21'], text=True).strip()
    except Exception:
        pass

import pandas as pd
import geopandas as gpd
import r5py
from r5py import TransportNetwork, TravelTimeMatrix, TransportMode

for f in [args.osm, *args.gtfs]:
    if not Path(f).exists():
        raise SystemExit(f'Missing input: {f}')

tracts = pd.read_csv(ROOT / 'data' / 'tract_representative_points.csv', dtype={'tract_geoid': str})
providers = pd.read_csv(ROOT / 'data' / 'providers.csv', dtype={'provider_id': str})
origins = gpd.GeoDataFrame({'id': 'T' + tracts.tract_geoid},
                           geometry=gpd.points_from_xy(tracts.longitude, tracts.latitude), crs='EPSG:4326')
dests = pd.concat([
    gpd.GeoDataFrame({'id': 'P' + providers.provider_id},
                     geometry=gpd.points_from_xy(providers.longitude, providers.latitude), crs='EPSG:4326'),
    origins], ignore_index=True)

windows = [w.split('=', 1) for w in args.window]
departures = {k: dt.datetime.fromisoformat(f'{args.date}T{t}') for k, t in windows}
departure = next(iter(departures.values()))
if departure.weekday() >= 5:
    raise SystemExit('Pick a weekday for --date')
window = dt.timedelta(hours=args.window_hours)
print(f'Building network from {Path(args.osm).name} + {", ".join(Path(g).name for g in args.gtfs)} ...', flush=True)
network = TransportNetwork(args.osm, list(args.gtfs))

common = dict(origins=origins, destinations=dests, departure=departure,
              max_time=dt.timedelta(minutes=args.max_minutes))
print('Driving matrix ...', flush=True)
drive = TravelTimeMatrix(network, transport_modes=[TransportMode.CAR], **common)
transit = {}
for key, dep in departures.items():
    print(f'Transit matrix {key} ({dep:%H:%M} + {args.window_hours} h departure window, median) ...', flush=True)
    transit[key] = TravelTimeMatrix(network, transport_modes=[TransportMode.TRANSIT, TransportMode.WALK],
                                    departure_time_window=window, percentiles=[50], **{**common, 'departure': dep})

def tidy(df, name):
    df = pd.DataFrame(df)
    col = [c for c in df.columns if c not in ('from_id', 'to_id')][0]
    return df.rename(columns={col: name})[['from_id', 'to_id', name]]

out = tidy(drive, 'drive_min')
for key, tt in transit.items():
    out = out.merge(tidy(tt, f'transit_{key}_min'), on=['from_id', 'to_id'], how='outer')
tcols = [f'transit_{k}_min' for k in transit]
out['origin_tract'] = out.from_id.str[1:]
out['dest_type'] = out.to_id.str[0].map({'P': 'provider', 'T': 'tract'})
out['dest_id'] = out.to_id.str[1:]
out = out[['origin_tract', 'dest_type', 'dest_id', 'drive_min', *tcols]].sort_values(
    ['origin_tract', 'dest_type', 'dest_id'])
expected = len(origins) * len(dests)
if len(out) != expected:
    raise SystemExit(f'Unexpected matrix size {len(out)} (expected {expected})')
out.to_csv(ROOT / 'data' / 'travel_times.csv', index=False)

prov = out[out.dest_type == 'provider']
meta = {
    'created': dt.datetime.now().isoformat(timespec='seconds'),
    'router': f'R5 via r5py {r5py.__version__}',
    'osm_file': Path(args.osm).name,
    'gtfs_files': [Path(g).name for g in args.gtfs],
    'departure': departure.isoformat(), 'departure_window_hours': args.window_hours,
    'transit_windows': [{'key': k, 'column': f'transit_{k}_min', 'departure': d.isoformat(),
                         'label': f"Weekday {d:%-I:%M %p}".replace(':00 ', ' ') + ' – ' +
                                  f"{d + window:%-I:%M %p}".replace(':00 ', ' ')} for k, d in departures.items()],
    'default_transit_window': next(iter(departures)),
    'transit_statistic': 'median travel time over departures every minute in the window',
    'transit_modes': 'all GTFS transit modes + walking (access, egress, transfers); walk-only used if faster',
    'drive_modes': 'car on OSM road network, free-flow speeds (no congestion)',
    'max_minutes': args.max_minutes,
    'origins': 'Census 2024 Gazetteer tract internal points (data/tract_representative_points.csv)',
    'missing_provider_pairs': {c: int(prov[c].isna().sum()) for c in ['drive_min', *tcols]},
}
(ROOT / 'data' / 'travel_times_meta.json').write_text(json.dumps(meta, indent=2))
print(f'Wrote {len(out):,} rows to data/travel_times.csv')
print('Tract->provider minutes:\n', prov[['drive_min', *tcols]].describe().round(1).to_string())
print('Missing (unreachable within limit):', meta['missing_provider_pairs'])
