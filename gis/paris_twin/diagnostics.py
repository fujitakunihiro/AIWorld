"""Source review overlays. Never repair connectivity by inventing links."""
from collections import defaultdict
from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree


def road_components(roads, geo):
    graph = defaultdict(set)
    segments = []
    for feature in roads:
        p = feature['properties']
        if p['tunnel'] or p['layer'] < 0:
            continue
        coords = p['source_geometry_projected'].get('coordinates', [])
        ids = p.get('osm_node_ids', [])
        if len(coords) != len(ids):
            continue
        for a, b, ca, cb in zip(ids, ids[1:], coords, coords[1:]):
            line = LineString([ca, cb])
            if not line.intersects(geo.extent):
                continue
            graph[a].add(b); graph[b].add(a)
            segments.append((a, b, line.intersection(geo.extent), p['source_id']))
    groups = []
    remaining = set(graph)
    while remaining:
        first = min(remaining); remaining.remove(first)
        todo = [first]; group = {first}
        while todo:
            node = todo.pop()
            for neighbor in sorted(graph[node]):
                if neighbor in remaining:
                    remaining.remove(neighbor); group.add(neighbor); todo.append(neighbor)
        groups.append(group)
    groups.sort(key=lambda g: (-len(g), min(g)))
    membership = {node: i for i, group in enumerate(groups) for node in group}
    grouped_segments = defaultdict(list)
    for a, b, line, identifier in segments:
        grouped_segments[membership[a]].append((line, identifier))
    issues = []
    for i, group in enumerate(groups[1:], 1):
        parts = grouped_segments[i]
        geometry = unary_union([line for line, _ in parts])
        clipped = geometry.distance(geo.extent.boundary) < .01
        issues.append({'id': f'road-component/{min(group)}', 'kind': 'disconnected_road',
                      'source_ids': sorted({identifier for _, identifier in parts}),
                      'node_count': len(group), 'geometry': mapping(geometry),
                      'classification': 'boundary_clipped' if clipped else 'interior_unconnected',
                      'note': 'Shared OSM nodes only. A separate path is not proof of a missing road.'})
    network = {'nodes': len(graph), 'edges': sum(map(len, graph.values())) // 2,
               'component_sizes': [len(g) for g in groups],
               'largest_component_ratio': round(len(groups[0]) / max(1, len(graph)), 4) if groups else 0,
               'method': 'original OSM shared node IDs; underground omitted; disconnected clipped paths reported'}
    return network, issues


def analyse(dataset, geo):
    buildings = dataset['layers']['buildings']
    shapes = [shape(f['geometry']) for f in buildings]
    tree = STRtree(shapes)
    issues = []
    overlaps = []
    for i, geometry in enumerate(shapes):
        for j in sorted(int(v) for v in tree.query(geometry)):
            if j <= i:
                continue
            overlap = geometry.intersection(shapes[j])
            if overlap.area <= .25:
                continue
            a, b = buildings[i]['properties']['source_id'], buildings[j]['properties']['source_id']
            overlaps.append({'a': a, 'b': b, 'area_m2': round(overlap.area, 3)})
            issues.append({'id': f'building-overlap/{a}/{b}', 'kind': 'building_overlap',
                           'source_ids': [a, b], 'area_m2': round(overlap.area, 3),
                           'geometry': mapping(overlap), 'classification': 'source_review_required',
                           'note': 'May represent layered volumes. Both original source IDs are retained.'})
    network, road_issues = road_components(dataset['layers']['roads'], geo)
    return {'format': 1, 'road_network': network, 'building_overlaps': overlaps,
            'issues': issues + road_issues,
            'policy': 'Review source geometry; do not invent connections or silently delete overlaps.'}
