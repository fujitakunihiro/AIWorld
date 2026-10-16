"""Historic facade surface from real colour/depth samples; provisional registration.

High-density portal/rose/gallery regions are selected. Bounded inferred fills
extend at most 40cm from observations; larger gaps remain missing. Steep depth
discontinuities over 1.2m are excluded. Original GIS is read only.
"""
import hashlib
import json
from pathlib import Path
import struct
import zlib
import warnings
import numpy as np
from inspect_notredame_facade import load_points, FOLDER, ROOT

DATA=ROOT/'unreal/AIWorld/Content/Data'
STEP=.0125
STRIDE=6
FILL_DISTANCE=.4


def png(path, pixels):
    pixels=np.ascontiguousarray(pixels);h,w=pixels.shape[:2]
    channels=1 if pixels.ndim==2 else pixels.shape[2]
    def chunk(kind,b):return struct.pack('>I',len(b))+kind+b+struct.pack('>I',zlib.crc32(kind+b)&0xffffffff)
    raw=b''.join(b'\x00'+row.tobytes() for row in pixels)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,0 if channels==1 else 2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b''))


def fill_small(depth, colour, valid, iterations=2, min_neighbors=3):
    for _ in range(iterations):
        count=np.zeros(valid.shape,np.uint8);sums=np.zeros_like(depth);rgb=np.zeros_like(colour)
        for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
            ok=np.roll(valid,(dy,dx),(0,1));d=np.roll(depth,(dy,dx),(0,1));c=np.roll(colour,(dy,dx),(0,1))
            if dy==1:ok[0]=False
            if dy==-1:ok[-1]=False
            if dx==1:ok[:,0]=False
            if dx==-1:ok[:,-1]=False
            count+=ok;sums+=np.where(ok,d,0);rgb+=c*ok[:,:,None]
        accept=(~valid)&(count>=min_neighbors)
        depth[accept]=sums[accept]/count[accept];colour[accept]=rgb[accept]/count[accept,None];valid|=accept
    return depth,colour,valid


def generate():
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
    select=(abs(x)<21.75)&(z>=0)&(z<45)&(y>-4)&(y<4)
    x=x[select];y=y[select];z=z[select];colours=colours[select]
    w=round(43.5/STEP)+1;h=round(45/STEP)+1
    u=np.clip(np.rint((x+21.75)/STEP).astype(int),0,w-1);v=np.clip(np.rint(z/STEP).astype(int),0,h-1);ids=v*w+u
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
    gridx,gridz=np.meshgrid(np.arange(w)*STEP-21.75,np.arange(h)*STEP)
    region=((abs(gridx)<6.8)&(gridz<16.2))|((abs(gridx)<6.0)&(gridz>22.0)&(gridz<34.8))|((abs(gridx)<20.7)&(gridz>17)&(gridz<22.2))
    original=valid.copy()
    depth,colour,valid=fill_small(depth,colour,valid,round(FILL_DISTANCE/STEP),1)
    valid&=region
    observed=int((original&valid).sum());filled=int((valid&~original).sum())
    # One 3x3 median removes isolated depth spikes without flattening a whole
    # sculptural band. The filtering and completion remain explicitly inferred.
    neighbors=[]
    for dy in [-1,0,1]:
        for dx in [-1,0,1]:neighbors.append(np.where(np.roll(valid,(dy,dx),(0,1)),np.roll(depth,(dy,dx),(0,1)),np.nan))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        smooth=np.nanmedian(np.stack(neighbors)[:,valid],axis=0)
    depth[valid]=smooth
    # Fine normal details come from measured depth, not an invented image.
    gx=np.zeros_like(depth);gz=np.zeros_like(depth)
    ok=valid[:,2:]&valid[:,:-2];gx[:,1:-1]=np.where(ok,(depth[:,2:]-depth[:,:-2])/(2*STEP),0)
    ok=valid[2:]&valid[:-2];gz[1:-1]=np.where(ok,(depth[2:]-depth[:-2])/(2*STEP),0)
    nrm=np.dstack((gx,-gz,np.ones_like(depth)));nrm/=np.linalg.norm(nrm,axis=2,keepdims=True)
    rows=np.arange(0,h,STRIDE);cols=np.arange(0,w,STRIDE);xx,zz=np.meshgrid(cols*STEP-21.75,rows*STEP)
    dd=depth[np.ix_(rows,cols)];vv=valid[np.ix_(rows,cols)];ny,nx=vv.shape
    index=np.arange(nx*ny,dtype=np.uint32).reshape(ny,nx)
    a=index[:-1,:-1];b=index[:-1,1:];c=index[1:,:-1];d=index[1:,1:]
    t0=np.stack((a,b,c),axis=-1).reshape(-1,3);t1=np.stack((b,d,c),axis=-1).reshape(-1,3)
    flat=dd.ravel();good=vv.ravel()
    def accept(t):return np.all(good[t],axis=1)&(np.ptp(flat[t],axis=1)<1.2)
    m0=accept(t0).reshape(ny-1,nx-1);m1=accept(t1).reshape(ny-1,nx-1)
    triangles=np.concatenate([t0[m0.ravel()],t1[m1.ravel()]])
    if len(triangles)<100000:raise ValueError('Insufficient observed facade surface; do not replace the cathedral')
    coverage=np.zeros((h,w),np.uint8)
    for iz in range(STRIDE):
        for ix in range(STRIDE):
            present=m0 if ix+iz+1<=STRIDE else m1
            coverage[iz:(ny-1)*STRIDE+iz:STRIDE,ix:(nx-1)*STRIDE+ix:STRIDE]=present*255
    frame=json.loads((DATA/'paris-photo-architecture.json').read_text(encoding='utf-8'))['local_frame']
    local=np.column_stack((xx.ravel(),dd.ravel(),zz.ravel()))
    world=(np.array(frame['front_cm'])+100*(local[:,0,None]*frame['across']+local[:,1,None]*frame['depth']+local[:,2,None]*np.array([0,0,1]))).astype('<f4')
    sampled=nrm[np.ix_(rows,cols)].reshape(-1,3)
    normals=(sampled[:,0,None]*frame['across']-sampled[:,2,None]*frame['depth']-sampled[:,1,None]*np.array([0,0,1])).astype('<f4')
    uv=np.column_stack(((xx.ravel()+21.75)/43.5,1-zz.ravel()/45)).astype('<f4')
    # Keep only used vertices, removing unsupported observations entirely.
    used,inverse=np.unique(triangles.ravel(),return_inverse=True)
    world=world[used];normals=normals[used];uv=uv[used];triangles=inverse.reshape(-1,3).astype('<u4')
    # Unreal front faces have the opposite index winding to right-handed GIS.
    p=world[triangles];cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);nn=normals[triangles].mean(1)
    flip=(cross*nn).sum(1)>0;triangles[flip]=triangles[flip][:,[0,2,1]]
    binary=struct.pack('<8sII',b'NDSCAN01',len(world),len(triangles))+world.tobytes()+normals.tobytes()+uv.tobytes()+triangles.tobytes()
    digest=hashlib.sha256(binary).hexdigest();file=FOLDER/'facade-surface.bin';file.write_bytes(binary)
    # Pad albedo at mesh borders only; this does not fill missing geometry.
    _,padded,_=fill_small(depth.copy(),colour.copy(),valid.copy(),2)
    png(FOLDER/'facade-colour.png',np.flipud(np.uint8(np.clip(padded,0,1)**(1/2.2)*255)))
    png(FOLDER/'facade-normal.png',np.flipud(np.uint8(np.clip(nrm*.5+.5,0,1)*255)))
    png(FOLDER/'facade-coverage.png',np.flipud(coverage))
    source=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    result=dict(format='paris_historic_scanned_facade_v1',source_id='osm/way/201611261',source=source,
        local_frame=frame,origin_wgs84=[2.3471,48.8547],origin_elevation_ngf_m=35.38,
        asset='/Game/ParisPhotoreal/NotreDameScan/SM_NotreDameScan_'+digest[:12],geometry_sha256=digest,
        binary=file.relative_to(ROOT).as_posix(),vertices=len(world),triangles=len(triangles),
        dimensions_reference='https://www.notredamedeparis.fr/comprendre/architecture/plans/',
        registration=dict(method='Provisional independent width/height calibration to official 43.5m / 69m; depth uses vertical scale. Not survey georegistration.',
            source_ground=ground,source_crown=crown,source_across_limits=[float(left),float(right)],source_wall_depth=plane,
            horizontal_scale_m=horizontal_scale,vertical_scale_m=vertical_scale,depth_scale_m=vertical_scale),
        surface=dict(texture_step_m=STEP,mesh_step_m=STEP*STRIDE,max_fill_distance_m=FILL_DISTANCE,albedo_border_padding_m=STEP*2,observed_cells=observed,filled_cells=filled,
            selection='Dense central portal, western rose and kings gallery only; other facade areas keep the authored fallback',depth_filter='3x3 median; inferred completion up to 0.4m distance',texture_width=w,texture_height=h,
            mesh_coverage_fraction=float((coverage>0).mean()),depth_jump_limit_m=1.2,lower_height_m=45,width_m=43.5),
        provenance='Historic photo-derived colour and filtered 2.5D depth; bounded inferred completion up to 0.4m distance and provisional art registration. Roughness is estimated, photographed lighting is not fully removed. Not a finished surveyed L4/L5 or a complete cathedral exterior.',
        textures={name:dict(file=(FOLDER/('facade-'+name+'.png')).relative_to(ROOT).as_posix(),sha256=hashlib.sha256((FOLDER/('facade-'+name+'.png')).read_bytes()).hexdigest()) for name in ['colour','normal','coverage']})
    (DATA/'paris-notredame-scan-source.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['vertices','triangles','registration','surface']}),flush=True)


if __name__=='__main__':generate()
