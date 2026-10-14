import argparse
import json
from pathlib import Path
from .acquire import download
from .io import ROOT, read


def main():
    parser = argparse.ArgumentParser(description='Paris public GIS snapshot and deterministic Unreal preview')
    parser.add_argument('command',choices=['download','download-buildings','download-terrain','prepare','generate','validate','all','coordinates'])
    parser.add_argument('--config',type=Path,default=ROOT/'gis/config/ile_de_la_cite.json')
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--refresh',action='store_true')
    position=parser.add_mutually_exclusive_group()
    position.add_argument('--wgs84',type=float,nargs=3,metavar=('LON','LAT','HEIGHT_NGF'))
    position.add_argument('--ue-cm',type=float,nargs=3,metavar=('X','Y','Z'))
    parser.add_argument('--origin-elevation',type=float,default=None,help='Shared NGF origin; defaults to the archived terrain origin')
    args = parser.parse_args()
    config = read(args.config)
    if args.command=='prepare':
        from .prepare import prepare
        print(json.dumps(prepare(config)))
    if args.command=='download-terrain':
        from .elevation_source import download_terrain
        result=download_terrain(config,args.offline,args.refresh)
        print(json.dumps({'terrain_samples':(result['grid_steps']+1)**2,'spacing_m':result['grid_spacing_m'],'origin_ngf_m':result['origin_elevation_ngf_m']}))
    if args.command=='download-buildings':
        from .building_source import download_buildings
        result=download_buildings(config,args.offline,args.refresh)
        print(json.dumps({'building_records':result['features'],'source':result['source']}))
    if args.command=='coordinates':
        from .coordinates import Georeference
        geo=Georeference(config)
        if args.origin_elevation is None:
            from .terrain import Terrain
            args.origin_elevation=Terrain(config,geo).origin_ngf
        if args.wgs84:print(json.dumps({'ue_cm':geo.to_ue(*args.wgs84,origin_elevation=args.origin_elevation),'origin_ngf_m':args.origin_elevation}))
        elif args.ue_cm:print(json.dumps({'wgs84_lon_lat_ngf_height':geo.from_ue(*args.ue_cm,origin_elevation=args.origin_elevation),'origin_ngf_m':args.origin_elevation}))
        else:parser.error('coordinates requires --wgs84 or --ue-cm')
    if args.command in ['download','all']:
        manifest = download(config,args.offline,args.refresh)
        print(json.dumps({'downloaded':list(manifest['files']),'cached':args.offline}))
    if args.command in ['generate','all']:
        from .normalize import normalize
        from .mesh import export
        dataset = normalize(config)
        result = export(config,dataset)
        print(json.dumps(result))
    if args.command in ['validate','all']:
        from .validate import validate
        result = validate(config)
        print(json.dumps({k:result[k] for k in ['errors','warnings','buildings','estimated_heights','source_declared_heights','coordinate_roundtrip_max_m','scene_sha256']}))
        if result['errors']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
