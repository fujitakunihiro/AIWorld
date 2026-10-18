"""Historic facade surface from real colour/depth samples; provisional registration.

Density tiles retain the central portal's sampling while extending to the
other portals. A sparse upper candidate is evaluated and rejected by the
support gate. Adopted tiles share one Nanite mesh and a <=4096px atlas.
Missing observations remain an authored fallback. Original GIS is read only.
"""
import hashlib
import json
from pathlib import Path
import struct
import zlib
import numpy as np
from inspect_notredame_facade import load_points, FOLDER, ROOT

DATA=ROOT/'unreal/AIWorld/Content/Data'
STEP=.0125
STRIDE=6
FILL_DISTANCE=.4
WIDTH=43.5
ATLAS_GUTTER=8
TILES=[dict(id='lower',bottom_m=0.,top_m=45.,step_m=STEP,stride=STRIDE,fill_distance_m=FILL_DISTANCE),
       dict(id='upper',bottom_m=45.,top_m=69.,step_m=.05,stride=3,fill_distance_m=.20)]


def png(path, pixels):
    pixels=np.ascontiguousarray(pixels);h,w=pixels.shape[:2]
    channels=1 if pixels.ndim==2 else pixels.shape[2]
    def chunk(kind,b):return struct.pack('>I',len(b))+kind+b+struct.pack('>I',zlib.crc32(kind+b)&0xffffffff)
    raw=b''.join(b'\x00'+row.tobytes() for row in pixels)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,0 if channels==1 else 2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b''))


def fill_small(depth, colour, valid, iterations=2, min_neighbors=3, max_depth_range=np.inf, region=None):
    for _ in range(iterations):
        count=np.zeros(valid.shape,np.uint8);sums=np.zeros_like(depth);rgb=np.zeros_like(colour)
        minimum=np.full_like(depth,np.inf);maximum=np.full_like(depth,-np.inf)
        for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
            ok=np.roll(valid,(dy,dx),(0,1));d=np.roll(depth,(dy,dx),(0,1));c=np.roll(colour,(dy,dx),(0,1))
            if dy==1:ok[0]=False
            if dy==-1:ok[-1]=False
            if dx==1:ok[:,0]=False
            if dx==-1:ok[:,-1]=False
            count+=ok;sums+=np.where(ok,d,0);rgb+=c*ok[:,:,None]
            minimum=np.minimum(minimum,np.where(ok,d,np.inf));maximum=np.maximum(maximum,np.where(ok,d,-np.inf))
        accept=(~valid)&(count>=min_neighbors)&((maximum-minimum)<=max_depth_range)
        if region is not None:accept&=region
        depth[accept]=sums[accept]/count[accept];colour[accept]=rgb[accept]/count[accept,None];valid|=accept
    return depth,colour,valid


def median_depth(depth,valid):
    """Bounded-memory 3x3 filter; image edges are never adjacent to each other."""
    padded=np.pad(np.where(valid,depth,np.nan),1,constant_values=np.nan)
    h,w=depth.shape
    for start in range(0,h,128):
        count=min(128,h-start);mask=valid[start:start+count]
        if not mask.any():continue
        neighbors=np.stack([padded[start+dy:start+dy+count,dx:dx+w] for dy in range(3) for dx in range(3)])
        block=depth[start:start+count]
        block[mask]=np.nanmedian(neighbors[:,mask],axis=0)
    return depth


def box_sum(values,radius):
    """Stable normalized filtering without a full image stack per neighbour."""
    h,w=values.shape;y=np.arange(h);x=np.arange(w)
    y0=np.maximum(0,y-radius);y1=np.minimum(h,y+radius+1)
    x0=np.maximum(0,x-radius);x1=np.minimum(w,x+radius+1)
    integral=np.pad(values,((1,0),(1,0))).cumsum(0,dtype=np.float64).cumsum(1,dtype=np.float64)
    total=integral[y1[:,None],x1]
    total-=integral[y0[:,None],x1];total-=integral[y1[:,None],x0];total+=integral[y0[:,None],x0]
    return total.astype(np.float32)


def smooth_sparse(depth,colour,valid,observed,radius):
    # Sparse depth/color interpolation produces diamond-shaped plateaus and
    # false sharp relief. Smooth these estimates; retain dense observations.
    h,w=depth.shape
    area=np.minimum(h,np.arange(h)+radius+1)-np.maximum(0,np.arange(h)-radius)
    span=np.minimum(w,np.arange(w)+radius+1)-np.maximum(0,np.arange(w)-radius)
    density=box_sum(observed,radius)/(area[:,None]*span)
    blend=np.clip((.4-density)/.4,0,1).astype(np.float32)
    support=np.maximum(box_sum(valid,radius),1)
    target=box_sum(np.where(valid,depth,0),radius)/support
    depth[valid]=((1-blend)*depth+blend*target)[valid]
    for channel in range(3):
        target=box_sum(np.where(valid,colour[:,:,channel],0),radius)/support
        estimate=valid&~observed
        colour[:,:,channel][estimate]=target[estimate]
    return depth,colour


def registered_points():
    points,colours,extras=load_points();sample=points[::31]
    # Registration is an explicit art calibration, not a recovered survey CRS.
    ground=float(np.percentile(sample[:,1],.01));crown=float(np.percentile(sample[:,1],99.999))
    vertical_scale=69/(crown-ground)
    middle=sample[(sample[:,1]>6000)&(sample[:,1]<11000)]
    _,basis=np.linalg.eigh(np.cov(middle[:,[0,2]].T));across=basis[:,1];normal=basis[:,0]
    if across[1]<0:across=-across
    if normal[0]>0:normal=-normal
    horizontal=points[:,[0,2]]@across;distance=points[:,[0,2]]@normal
    left,right=np.percentile(horizontal[::31],[.1,99.9]);horizontal_scale=43.5/(right-left)
    x=(horizontal-(left+right)/2)*horizontal_scale;z=(points[:,1]-ground)*vertical_scale
    wall=(z>14.5)&(z<16)&(abs(x)<18)
    bins=np.rint(distance[wall]/10).astype(int);values,n=np.unique(bins,return_counts=True);mode=values[n.argmax()]*10
    plane=float(np.median(distance[wall&(abs(distance-mode)<15)]))
    y=(plane-distance)*vertical_scale-.8
    registration=dict(method='Provisional independent width/height calibration to official 43.5m / 69m; depth uses vertical scale. Not survey georegistration.',
        source_ground=ground,source_crown=crown,source_across_limits=[float(left),float(right)],source_wall_depth=plane,
        horizontal_scale_m=horizontal_scale,vertical_scale_m=vertical_scale,depth_scale_m=vertical_scale)
    return x,y,z,colours,registration


def allowed_region(gridx,gridz,tile):
    region=np.ones(gridx.shape,dtype=bool)
    if tile['id']=='lower':
        # Quality comes before area. The sparse upper arcade and outer piers
        # produced unsupported ragged relief in native comparison renders.
        # Retain v9's dense patches and add the two documented side portals.
        region=((abs(gridx)<6.8)&(gridz<16.2))|((abs(gridx)<6)&(gridz>22)&(gridz<34.8))|((abs(gridx)<20.7)&(gridz>17)&(gridz<22.2))
        # Stay above the authored wooden doors (4.87m) and stone lintel
        # (5.17m). The lower side-door observations are too incomplete to
        # register coherently; do not clip a wooden panel halfway up.
        for centre in [-14.,14.]:region|=(abs(gridx-centre)<6.4)&(gridz>=5.2)&(gridz<15.8)
    if tile['id']=='upper':
        # Preserve the real open sky between the two towers and the authored
        # recessed belfry louvres. Never bridge these voids by interpolation.
        region&=abs(gridx)>8.75
        rise=6.7;half=2.3;offset=(rise*rise-half*half)/(2*half);radius=half+offset
        for centre in [-17.95,-12.55,12.55,17.95]:
            a=abs(gridx-centre)
            inside=(a<half+.001)&(gridz>=48-.001)&(gridz<58+np.sqrt(np.maximum(0,radius*radius-(offset+a)**2))+.001)
            region&=~inside
    return region


def raster_tile(x,y,z,colours,tile):
    step=tile['step_m'];stride=tile['stride'];bottom=tile['bottom_m'];top=tile['top_m']
    select=(abs(x)<WIDTH/2)&(z>=bottom)&(z<=top)&(y>-4)&(y<4)
    x=x[select];y=y[select];z=z[select];colours=colours[select]
    w=round(WIDTH/step)+1;h=round((top-bottom)/step)+1
    assert (w-1)%stride==0 and (h-1)%stride==0,'Tiles must have complete mesh cells'
    u=np.clip(np.rint((x+WIDTH/2)/step).astype(int),0,w-1);v=np.clip(np.rint((z-bottom)/step).astype(int),0,h-1);ids=v*w+u
    # Use the median surface cluster. A single foreground outlier must not pull
    # a whole cell away from its neighbours and create floating shards.
    order=np.lexsort((y,ids));ordered=ids[order]
    starts=np.r_[0,np.flatnonzero(ordered[1:]!=ordered[:-1])+1]
    lengths=np.diff(np.r_[starts,len(order)])
    median=np.full(w*h,np.inf,np.float32)
    median[ordered[starts]]=y[order[starts+(lengths-1)//2]]
    keep=abs(y-median[ids])<=.05;ids=ids[keep];yy=y[keep];cc=colours[keep]
    count=np.bincount(ids,minlength=w*h);valid=(count>=2).reshape(h,w)
    depth=(np.bincount(ids,weights=yy,minlength=w*h)/np.maximum(count,1)).reshape(h,w).astype(np.float32)
    colour=np.column_stack([np.bincount(ids,weights=cc[:,i],minlength=w*h)/np.maximum(count,1) for i in range(3)]).reshape(h,w,3).astype(np.float32)
    gridx,gridz=np.meshgrid(np.arange(w)*step-WIDTH/2,bottom+np.arange(h)*step)
    region=allowed_region(gridx,gridz,tile)
    valid&=region
    original=valid.copy()
    depth,colour,valid=fill_small(depth,colour,valid,round(tile['fill_distance_m']/step),1,max_depth_range=.60,region=region)
    valid&=region
    observed=int((original&valid).sum());filled=int((valid&~original).sum())
    # One 3x3 median removes isolated depth spikes without flattening a whole
    # sculptural band. The filtering and completion remain explicitly inferred.
    depth=median_depth(depth,valid)
    depth,colour=smooth_sparse(depth,colour,valid,original,8 if tile['id']=='lower' else 3)
    # Fine normal details come from measured depth, not an invented image.
    gx=np.zeros_like(depth);gz=np.zeros_like(depth)
    ok=valid[:,2:]&valid[:,:-2];gx[:,1:-1]=np.where(ok,(depth[:,2:]-depth[:,:-2])/(2*step),0)
    ok=valid[2:]&valid[:-2];gz[1:-1]=np.where(ok,(depth[2:]-depth[:-2])/(2*step),0)
    nrm=np.dstack((gx,-gz,np.ones_like(depth)));nrm/=np.linalg.norm(nrm,axis=2,keepdims=True)
    rows=np.arange(0,h,stride);cols=np.arange(0,w,stride);xx,zz=np.meshgrid(cols*step-WIDTH/2,bottom+rows*step)
    dd=depth[np.ix_(rows,cols)];vv=valid[np.ix_(rows,cols)];ny,nx=vv.shape
    index=np.arange(nx*ny,dtype=np.uint32).reshape(ny,nx)
    a=index[:-1,:-1];b=index[:-1,1:];c=index[1:,:-1];d=index[1:,1:]
    t0=np.stack((a,b,c),axis=-1).reshape(-1,3);t1=np.stack((b,d,c),axis=-1).reshape(-1,3)
    flat=dd.ravel();good=vv.ravel()
    def accept(t):
        keep=np.all(good[t],axis=1)&(np.ptp(flat[t],axis=1)<1.2)
        if tile['id']=='upper':
            # A triangle can cross a concave opening even with all three
            # vertices outside. Reject these faces before deriving coverage.
            keep&=allowed_region(xx.ravel()[t].mean(1),zz.ravel()[t].mean(1),tile)
        return keep
    m0=accept(t0).reshape(ny-1,nx-1);m1=accept(t1).reshape(ny-1,nx-1)
    triangles=np.concatenate([t0[m0.ravel()],t1[m1.ravel()]])
    coverage=np.zeros((h,w),np.uint8)
    for iz in range(stride):
        for ix in range(stride):
            present=m0 if ix+iz+1<=stride else m1
            coverage[iz:(ny-1)*stride+iz:stride,ix:(nx-1)*stride+ix:stride]=present*255
    _,padded,_=fill_small(depth.copy(),colour.copy(),valid.copy(),2)
    return dict(depth=depth,normal=nrm,colour=padded,coverage=coverage,triangles=triangles,
        local=np.column_stack((xx.ravel(),dd.ravel(),zz.ravel())),sampled_normal=nrm[np.ix_(rows,cols)].reshape(-1,3),
        observed_cells=observed,filled_cells=filled,width=w,height=h,eligible_cells=int(region.sum()),
        projected_area_m2=len(triangles)*.5*(step*stride)**2)


def generate():
    x,y,z,colours,registration=registered_points()
    frame=json.loads((DATA/'paris-photo-architecture.json').read_text(encoding='utf-8'))['local_frame']
    tiles=[];rasters=[];rejected=[];row=0
    for spec in TILES:
        raster=raster_tile(x,y,z,colours,spec)
        direct_fraction=raster['observed_cells']/max(raster['eligible_cells'],1)
        if spec['id']=='upper' and direct_fraction<.60:
            rejected.append(dict(id=spec['id'],reason='Insufficient direct support for a coherent upper surface; native comparison showed ragged depth and registration mismatch. Authored upper facade retained.',
                observed_fraction=direct_fraction,required_fraction=.60,observed_cells=raster['observed_cells'],eligible_cells=raster['eligible_cells'],candidate_triangles=len(raster['triangles'])))
            continue
        tiles.append(dict(spec,row=row,width=raster['width'],height=raster['height'],observed_cells=raster['observed_cells'],
            filled_cells=raster['filled_cells'],observed_fraction=direct_fraction,triangles=len(raster['triangles']),projected_area_m2=raster['projected_area_m2']))
        rasters.append(raster);row+=raster['height']+ATLAS_GUTTER
    w=max(r['width'] for r in rasters);h=row-ATLAS_GUTTER
    assert max(w,h)<=4096,'Do not silently downsample the existing portal texture'
    colourmap=np.zeros((h,w,3),np.float32);normalmap=np.zeros((h,w,3),np.float32);normalmap[:,:,2]=1;coverage=np.zeros((h,w),np.uint8)
    vertices=[];normals=[];uvs=[];indices=[];offset=0
    for tile,raster in zip(tiles,rasters):
        yy=tile['row'];tw=tile['width'];th=tile['height']
        colourmap[yy:yy+th,:tw]=raster['colour'];normalmap[yy:yy+th,:tw]=raster['normal'];coverage[yy:yy+th,:tw]=raster['coverage']
        # Duplicate edge colour/normal into the atlas gutter, but never expand
        # the coverage mask. Filtering cannot claim unobserved source surfaces.
        if tw<w:
            colourmap[yy:yy+th,tw:tw+ATLAS_GUTTER]=raster['colour'][:,-1:]
            normalmap[yy:yy+th,tw:tw+ATLAS_GUTTER]=raster['normal'][:,-1:]
        if yy:
            colourmap[yy-ATLAS_GUTTER//2:yy,:tw]=raster['colour'][:1]
            normalmap[yy-ATLAS_GUTTER//2:yy,:tw]=raster['normal'][:1]
        if yy+th<h:
            colourmap[yy+th:yy+th+ATLAS_GUTTER//2,:tw]=raster['colour'][-1:]
            normalmap[yy+th:yy+th+ATLAS_GUTTER//2,:tw]=raster['normal'][-1:]
        local=raster['local'];sampled=raster['sampled_normal']
        vertices.append(local);normals.append(sampled)
        uvs.append(np.column_stack(((local[:,0]+WIDTH/2)/tile['step_m']/(w-1),1-(yy+(local[:,2]-tile['bottom_m'])/tile['step_m'])/(h-1))))
        indices.append(raster['triangles']+offset);offset+=len(local)
    local=np.concatenate(vertices);sampled=np.concatenate(normals);uv=np.concatenate(uvs).astype('<f4');triangles=np.concatenate(indices)
    if len(triangles)<200000:raise ValueError('Insufficient observed facade surface; do not replace the cathedral')
    world=(np.array(frame['front_cm'])+100*(local[:,0,None]*frame['across']+local[:,1,None]*frame['depth']+local[:,2,None]*np.array([0,0,1]))).astype('<f4')
    normals=(sampled[:,0,None]*frame['across']-sampled[:,2,None]*frame['depth']-sampled[:,1,None]*np.array([0,0,1])).astype('<f4')
    # Keep only used vertices, removing unsupported observations entirely.
    used,inverse=np.unique(triangles.ravel(),return_inverse=True)
    world=world[used];normals=normals[used];uv=uv[used];triangles=inverse.reshape(-1,3).astype('<u4')
    # Unreal front faces have the opposite index winding to right-handed GIS.
    p=world[triangles];cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);nn=normals[triangles].mean(1)
    flip=(cross*nn).sum(1)>0;triangles[flip]=triangles[flip][:,[0,2,1]]
    binary=struct.pack('<8sII',b'NDSCAN01',len(world),len(triangles))+world.tobytes()+normals.tobytes()+uv.tobytes()+triangles.tobytes()
    digest=hashlib.sha256(binary).hexdigest();file=FOLDER/'facade-surface.bin';file.write_bytes(binary)
    png(FOLDER/'facade-colour.png',np.flipud(np.uint8(np.clip(colourmap,0,1)**(1/2.2)*255)))
    png(FOLDER/'facade-normal.png',np.flipud(np.uint8(np.clip(normalmap*.5+.5,0,1)*255)))
    png(FOLDER/'facade-coverage.png',np.flipud(coverage))
    source=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    display_height=max(t['top_m'] for t in tiles)
    result=dict(format='paris_historic_scanned_facade_v1',source_id='osm/way/201611261',source=source,
        local_frame=frame,origin_wgs84=[2.3471,48.8547],origin_elevation_ngf_m=35.38,
        asset='/Game/ParisPhotoreal/NotreDameScan/SM_NotreDameScan_'+digest[:12],geometry_sha256=digest,
        binary=file.relative_to(ROOT).as_posix(),vertices=len(world),triangles=len(triangles),
        dimensions_reference='https://www.notredamedeparis.fr/comprendre/architecture/plans/',
        registration=registration,
        surface=dict(revision=10,texture_step_m=STEP,mesh_step_m=STEP*STRIDE,max_fill_distance_m=FILL_DISTANCE,albedo_border_padding_m=STEP*2,
            observed_cells=sum(t['observed_cells'] for t in tiles),filled_cells=sum(t['filled_cells'] for t in tiles),
            selection='Central portal, side-portal sculpture above 5.2m, western rose and kings gallery; side doors, sparse upper facade and tower candidates retain the authored fallback',side_portal_min_height_m=5.2,
            depth_filter='3x3 median; inferred completion <=0.4m lower / <=0.2m upper; neighbor depth range <=0.6m',texture_width=w,texture_height=h,
            sparse_smoothing=dict(lower_radius_m=.10,upper_radius_m=.15,fully_preserved_density=.4,
                note='Confidence-weighted depth regularization in sparse areas; inferred colour interpolation is smoothed, dense observations retained'),
            mesh_coverage_fraction=sum(t['projected_area_m2'] for t in tiles)/(WIDTH*display_height),depth_jump_limit_m=1.2,lower_height_m=45,full_height_m=display_height,width_m=WIDTH,rejected_tiles=rejected,
            atlas=dict(width=w,height=h,gutter_pixels=ATLAS_GUTTER,tiles=tiles)),
        provenance='Historic photo-derived colour and filtered 2.5D depth; bounded inferred completion up to 0.4m distance and provisional art registration. Roughness is estimated, photographed lighting is not fully removed. Not a finished surveyed L4/L5 or a complete cathedral exterior.',
        textures={name:dict(file=(FOLDER/('facade-'+name+'.png')).relative_to(ROOT).as_posix(),sha256=hashlib.sha256((FOLDER/('facade-'+name+'.png')).read_bytes()).hexdigest()) for name in ['colour','normal','coverage']})
    (DATA/'paris-notredame-scan-source.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['vertices','triangles','registration','surface']}),flush=True)


if __name__=='__main__':generate()
