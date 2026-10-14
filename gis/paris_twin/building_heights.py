"""Reconcile OSM footprints with IGN gutter heights, keeping evidence per part."""
import math
from shapely import force_2d
from shapely.geometry import mapping,shape
from shapely.ops import unary_union
from shapely.strtree import STRtree
from .io import read

DOCUMENTATION='https://bdtopoexplorer.ign.fr/batiment'


def polygon_parts(g):
    if g is None or g.is_empty:return []
    if g.geom_type=='Polygon':return [g]
    return [p for child in getattr(g,'geoms',[]) for p in polygon_parts(child)]


def number(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError):return None


def roof_policy(tags,geometry,height,nature=''):
    declared=tags.get('roof:shape')
    supported=['flat','gabled','hipped','mansard','pyramidal']
    small=geometry.area<12
    tower=height>50 and geometry.area<500
    form=declared if declared in supported else 'flat' if small or tower else 'gabled' if tags.get('building') in ['church','cathedral','chapel'] else 'mansard'
    rise=number(tags.get('roof:height'))
    if form=='flat':rise=0
    elif rise is None or not 0<rise<20:rise=min(6.,max(1.2,height*.16))
    return {'form':form,'rise_m':round(rise,3),'form_source':'osm:roof_shape_unverified' if declared in supported else 'estimated:district_style',
            'rise_source':'osm:roof_height_unverified' if number(tags.get('roof:height')) is not None and form!='flat' else 'estimated:roof_profile',
            'orientation_source':'estimated:minimum_rotated_rectangle',
            'reproduction_level':'L1','highest_spire_modelled':False}


def enrich_buildings(config,raw,layers,polygonal):
    file=raw/'heights/buildings.json'
    records=read(file)['features'] if file.exists() else []
    geometries=[];valid_records=[];source_layer=[]
    for record in records:
        g=polygonal(force_2d(shape(record['geometry'])))
        if not g:continue
        p=record['properties'];identifier='ign/bdtopo/'+p['cleabs'];height=number(p.get('hauteur'))
        source_layer.append({'geometry':mapping(g),'properties':{'source_id':identifier,'source_snapshot':'heights/buildings.json',
            'source_url':DOCUMENTATION,'source_license':'Etalab Open Licence 2.0','source':'IGN BD TOPO',
            'height_gutter_m':height,'height_ngf_min_sol_m':p.get('altitude_minimale_sol'),
            'acquisition_method':p.get('methode_d_acquisition_altimetrique'),'vertical_precision_m':p.get('precision_altimetrique'),
            'updated':p.get('date_modification')}})
        ground=number(p.get('altitude_minimale_sol'));precision=number(p.get('precision_altimetrique'))
        if height is None or not .5<height<150 or ground is None or precision is None or not 0<precision<=3 or p.get('methode_d_acquisition_altimetrique')=='Pas de Z':continue
        geometries.append(g);valid_records.append(record)
    tree=STRtree(geometries)
    for feature in layers['buildings']:
        props=feature['properties'];foot=shape(feature['geometry']);tags=props['tags'];parts=[]
        original_fallback=props['height_m'];props['pre_enrichment_height_m']=original_fallback
        candidates=sorted([(foot.intersection(geometries[int(i)]).area,valid_records[int(i)]['properties']['cleabs'],int(i)) for i in tree.query(foot)],key=lambda v:(-v[0],v[1]))
        remaining=foot
        for area,identifier,i in candidates:
            if area<2:continue
            clipped=polygonal(remaining.intersection(geometries[i]))
            if clipped is None or clipped.area<1:continue
            p=valid_records[i]['properties'];height=float(p['hauteur']);ground=float(p['altitude_minimale_sol'])
            segments=[]
            for poly in polygon_parts(shape(valid_records[i]['geometry'])):
                for ring in [poly.exterior,*poly.interiors]:
                    points=list(ring.coords)
                    for a,b in zip(points,points[1:]):
                        if len(a)==3 and len(b)==3 and all(math.isfinite(v) for v in [a[2],b[2]]):
                            # IGN gutter Z is absolute NGF; preview ground is local zero.
                            segments.append([[a[0],a[1],max(.5,a[2]-ground)],[b[0],b[1],max(.5,b[2]-ground)]])
            z_max=max((v[2] for segment in segments for v in segment),default=height)
            if abs(z_max-height)>max(1.,float(p['precision_altimetrique'])*2):segments=[]
            parts.append({'geometry':mapping(clipped),'height_gutter_m':height,'height_kind':'official_topographic',
                'source_id':'ign/bdtopo/'+identifier,'source_snapshot':'heights/buildings.json','source_url':DOCUMENTATION,
                'ground_ngf_m':ground,'vertical_precision_m':p['precision_altimetrique'],'acquisition_method':p['methode_d_acquisition_altimetrique'],
                'source_updated':p['date_modification'],'gutter_segments_m':segments,
                'roof':roof_policy(tags,clipped,height,p.get('nature',''))})
            remaining=polygonal(remaining.difference(clipped))
            if remaining is None:break
        official=list(parts)
        coverage=sum(shape(p['geometry']).area for p in official)/foot.area if foot.area else 0
        if remaining:
            for g in polygon_parts(remaining):
                closest=min(official,key=lambda p:g.representative_point().distance(shape(p['geometry'])),default=None)
                # Small OSM/IGN edge differences should not reintroduce a 75m church wall.
                if closest is not None:
                    height=closest['height_gutter_m'];kind='estimated:neighboring_IGN_part'
                elif tags.get('building') in ['church','cathedral','chapel']:
                    height=config.get('estimated_church_wall_height_m',25);kind='estimated:church_wall_not_spire_tag'
                else:height=original_fallback;kind=props['height_source']
                fallback_kind='source_declared_unverified' if closest is None and kind=='osm:height_tag' else 'estimated'
                parts.append({'geometry':mapping(g),'height_gutter_m':height,'height_kind':fallback_kind,
                    'source_id':props['source_id'],'source_snapshot':'osm.json','source_url':props['source_url'],
                    'height_source':kind,'gutter_segments_m':[], 'roof':roof_policy(tags,g,height)})
        for part in parts:
            part['roof']['rise_m']=min(part['roof']['rise_m'],max(0,150-part['height_gutter_m']))
        props.update(height_parts=parts,official_height_coverage=round(coverage,6),
            height_precision_max_m=max((p['vertical_precision_m'] for p in official),default=None),
            height_data_dates=sorted({p['source_updated'] for p in official if p.get('source_updated')}),
            height_reference_ids=sorted({p['source_id'] for p in official}),
            height_source='ign:BD_TOPO_gutter_with_labelled_gap_estimates' if official else props['height_source'],
            height_kind='official_topographic' if coverage>=.98 else 'mixed' if official else 'source_declared_unverified' if all(p['height_kind']=='source_declared_unverified' for p in parts) else 'estimated',
            height_measured_missing=coverage<.98,
            height_gutter_min_m=min(p['height_gutter_m'] for p in parts),height_gutter_max_m=max(p['height_gutter_m'] for p in parts),
            height_m=max(p['height_gutter_m']+p['roof']['rise_m'] for p in parts),
            height_semantics='gutter heights from topographic data; procedural roof rise is additional, not a surveyed maximum',
            reproduction_level='L1',reproduction_level_body='L2' if coverage>=.98 and not props['clipped_at_context_boundary'] else 'L1',
            roof_form_source='estimated_or_OSM_declared_profiles; no_surveyed_ridge_geometry',facade_source='preview:no_facade_claim')
    layers['ign_buildings']=source_layer
