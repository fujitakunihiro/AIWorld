"""Capture/compare all non-facade geometry and source metadata across art edits."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCENE=ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin.json'


def capture():
    scene=json.loads(SCENE.read_text(encoding='utf-8-sig'))
    result={k:scene[k] for k in ('georeference','pick_features','landmarks','coordinate_checks')}
    result['objects']=[x for x in scene['objects'] if not x['kind'].startswith('facade_')]
    return dict(sha256=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                buildings=sum(x['kind']=='building' for x in scene['pick_features']),
                source_features=len(scene['pick_features']),core_meshes=len(result['objects']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['capture','verify']);parser.add_argument('report',type=Path)
    args=parser.parse_args();result=capture()
    if args.mode=='capture':args.report.write_text(json.dumps(result,indent=2)+'\n')
    else:
        old=json.loads(args.report.read_text())
        if old!=result:raise SystemExit('Core geometry/source metadata changed: '+str(result))
    print(json.dumps(result))
