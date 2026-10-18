"""Shared, dependency-free mapping for observed geometry and coverage underlays."""


def atlas_uv_hlsl(surface):
    atlas=surface.get('atlas')
    if not atlas:return 'return float2((x+21.75)/43.5,1-z/45);'
    lines=['float2 uv=float2(-1,-1);']
    for tile in atlas['tiles']:
        lines.append(f'if(z+0.0001>={tile["bottom_m"]}&&z-0.0001<={tile["top_m"]})uv=float2((x+{surface["width_m"]/2})/{tile["step_m"]}/{atlas["width"]-1},1-({tile["row"]}+(z-{tile["bottom_m"]})/{tile["step_m"]})/{atlas["height"]-1});')
    return ' '.join(lines)+'return uv;'


def atlas_uv(x,z,surface):
    atlas=surface['atlas'];result=(-1.,-1.)
    for tile in atlas['tiles']:
        if tile['bottom_m']-.0001<=z<=tile['top_m']+.0001:
            result=((x+surface['width_m']/2)/tile['step_m']/(atlas['width']-1),
                    1-(tile['row']+(z-tile['bottom_m'])/tile['step_m'])/(atlas['height']-1))
    return result
