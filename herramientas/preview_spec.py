# -*- coding: utf-8 -*-
"""
Vista previa / control de calidad de un spec de familia (fuera de Revit).

  python herramientas/preview_spec.py dynamo/specs/spec_PEL01_CPM7730.py salida.png
  python herramientas/preview_spec.py dynamo/specs/spec_PEL01_CPM7730.py salida.png --dxf PLANO.dxf \
         --lateral 17592.2 274.4 --frontal 14337.3 274.4
  python herramientas/preview_spec.py SPEC salida.png --zoom X0 X1 Y0 Y1 Z0 Z1 --vista 25 -60

Dibuja isometrica + alzado lateral (X-Z) + alzado frontal (Y-Z).  Con --dxf superpone el spec sobre el
plano del proveedor (requiere ezdxf).  --lateral / --frontal = origen de la familia en coordenadas CAD:
  lateral: x_cad = X + ox ; y_cad = Z + oz        frontal: x_cad = ox - Y ; y_cad = Z + oz
"""
import argparse
import importlib.util
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

COL = {'cuerpo': '#dedfdb', 'motores': '#262628', 'reductores': '#c4c7c9', 'estructura': '#1e1e1e',
       'conexiones': '#b0b3b6', 'pernos': '#8c8e91', 'zonas': '#E76A1F'}
AX = {'X': 0, 'Y': 1, 'Z': 2}
SEC = {'X': ('Y', 'Z'), 'Y': ('X', 'Z'), 'Z': ('X', 'Y')}


def load_spec(path):
    s = importlib.util.spec_from_file_location('spec_mod', path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m.SPEC


# ------------------------------------------------------------------ lazos -> poligonos 2D
def loop_pts(lz, n=28):
    t = lz['t']
    if t == 'rect':
        (cu, cv), (du, dv) = lz['c'], lz['d']
        return [(cu - du / 2, cv - dv / 2), (cu + du / 2, cv - dv / 2), (cu + du / 2, cv + dv / 2), (cu - du / 2, cv + dv / 2)]
    if t == 'rrect':
        (cu, cv), (du, dv), r = lz['c'], lz['d'], lz['r']
        hu, hv = du / 2, dv / 2
        pts = []
        for (sx, sy, a0) in ((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)):
            ox, oy = cu + sx * (hu - r), cv + sy * (hv - r)
            for k in range(5):
                a = math.radians(a0 + 90 * k / 4)
                pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
        return pts
    if t == 'circ':
        (cu, cv), r = lz['c'], lz['r']
        return [(cu + r * math.cos(2 * math.pi * i / n), cv + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    if t == 'hex':
        (cu, cv), R = lz['c'], lz['s'] / math.sqrt(3)
        return [(cu + R * math.cos(math.pi / 3 * i), cv + R * math.sin(math.pi / 3 * i)) for i in range(6)]
    if t == 'poly':
        return list(lz['pts'])
    if t == 'u':
        (cu, cv), r, top = lz['c'], lz['r'], lz['tope']
        pts = [(cu + r * math.cos(math.pi + math.pi * i / 12), cv + r * math.sin(math.pi + math.pi * i / 12))
               for i in range(13)]
        return pts + [(cu + r, top), (cu - r, top)]
    raise ValueError(t)


def _bb2(p):
    us, vs = [a for a, _ in p], [b for _, b in p]
    return min(us), max(us), min(vs), max(vs)


def outer_loops(loops):
    """Descarta lazos contenidos en otro (huecos)."""
    polys = [loop_pts(l) for l in loops]
    bbs = [_bb2(p) for p in polys]
    out = []
    for i, p in enumerate(polys):
        a = bbs[i]
        inside = any(j != i and b[0] <= a[0] and a[1] <= b[1] and b[2] <= a[2] and a[3] <= b[3] and
                     (b[1] - b[0]) * (b[3] - b[2]) > (a[1] - a[0]) * (a[3] - a[2]) for j, b in enumerate(bbs))
        if not inside:
            out.append(p)
    return out


# ------------------------------------------------------------------ spec -> prismas
def prisms(spec):
    """(eje, a0, a1, poligono(u,v), color, es_zona)"""
    out = []

    def add(axis, a0, a1, loops, col, zona=False):
        for p in outer_loops(loops):
            out.append((axis, min(a0, a1), max(a0, a1), p, col, zona))
    for s in spec['solidos'] + spec.get('vacios', []):
        col = '#ff0000' if 'corta' in s else COL.get(s.get('mat'), COL.get(s.get('sub'), '#ffffff'))
        f = s['forma']
        if f == 'caja':
            (x0, x1), (y0, y1), (z0, z1) = s['x'], s['y'], s['z']
            add('Z', z0, z1, [{'t': 'rect', 'c': ((x0 + x1) / 2, (y0 + y1) / 2), 'd': (x1 - x0, y1 - y0)}], col)
        elif f == 'cilindro':
            add(s['eje'], s['rango'][0], s['rango'][1], [{'t': 'circ', 'c': s['centro'], 'r': s['r']}], col)
        elif f == 'ext':
            add(s['eje'], s['rango'][0], s['rango'][1], s['lazos'], col)
        elif f == 'transicion':
            for key, z in (('base', s['z'][0]), ('tope', s['z'][1])):
                cx, cy, dx, dy = s[key]
                add('Z', z - 1, z + 1, [{'t': 'rect', 'c': (cx, cy), 'd': (dx, dy)}], col)
            (bx, by, _, _), (tx, ty, tdx, tdy) = s['base'], s['tope']
            add('Z', s['z'][0], s['z'][1], [{'t': 'rect', 'c': ((bx + tx) / 2, (by + ty) / 2), 'd': (tdx, tdy)}], col)
    for b in spec.get('boquillas', []):
        sgn = -1 if b['eje'][0] == '-' else 1
        e = b['eje'][1]
        ku, kv = SEC[e]
        base = dict(zip('XYZ', b['base']))
        a = base[e]
        L, ef = b['proyeccion'], b['e_brida']
        rf = (b.get('rf') or {}).get('h', 0.0)
        f0 = L - rf - ef
        c = (base[ku], base[kv])
        if b['seccion'] == 'circular':
            add(e, a, a + sgn * f0, [{'t': 'circ', 'c': c, 'r': b['d_tubo'] / 2}], COL['cuerpo'])
            add(e, a + sgn * f0, a + sgn * (L - rf), [{'t': 'circ', 'c': c, 'r': b['d_brida'] / 2}], COL['conexiones'])
        else:
            add(e, a, a + sgn * f0, [{'t': 'rect', 'c': c, 'd': b['cuerpo']}], COL['cuerpo'])
            add(e, a + sgn * f0, a + sgn * L, [{'t': 'rect', 'c': c, 'd': b['brida']}], COL['conexiones'])
        pr = b.get('pernos') or {}
        if pr.get('pos'):
            add(e, a + sgn * (f0 - pr['h']), a + sgn * (L + pr['sale']),
                [{'t': 'circ', 'c': q, 'r': pr['d'] / 2} for q in pr['pos']], COL['pernos'])
            add(e, a + sgn * (f0 - pr['h']), a + sgn * f0, [{'t': 'hex', 'c': q, 's': pr['s']} for q in pr['pos']],
                COL['pernos'])
    for z in spec.get('zonas', []):
        sgn = -1 if z['normal'][0] == '-' else 1
        e = z['normal'][1]
        add(e, z['plano'], z['plano'] + sgn * z['largo'],
            [{'t': 'rect', 'c': ((z['u'][0] + z['u'][1]) / 2, (z['v'][0] + z['v'][1]) / 2),
              'd': (z['u'][1] - z['u'][0], z['v'][1] - z['v'][0])}], COL['zonas'], True)
    return out


def to3d(axis, a, p):
    ku, kv = SEC[axis]
    q = [0.0, 0.0, 0.0]
    q[AX[axis]], q[AX[ku]], q[AX[kv]] = a, p[0], p[1]
    return tuple(q)


def prism_faces(axis, a0, a1, poly):
    b = [to3d(axis, a0, p) for p in poly]
    t = [to3d(axis, a1, p) for p in poly]
    n = len(poly)
    return [b, t] + [[b[i], b[(i + 1) % n], t[(i + 1) % n], t[i]] for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('png')
    ap.add_argument('--dxf')
    ap.add_argument('--lateral', nargs=2, type=float, default=(0.0, 0.0))
    ap.add_argument('--frontal', nargs=2, type=float, default=(0.0, 0.0))
    ap.add_argument('--zoom', nargs=6, type=float)
    ap.add_argument('--vista', nargs=2, type=float, default=(22.0, -58.0))
    ap.add_argument('--solo3d', action='store_true')
    a = ap.parse_args()
    spec = load_spec(a.spec)
    items = prisms(spec)

    fig = plt.figure(figsize=(22, 13) if not a.solo3d else (18, 13))
    ax3 = fig.add_subplot(1, 1, 1, projection='3d') if a.solo3d else fig.add_subplot(2, 2, (1, 3), projection='3d')
    lim = a.zoom or (-1400, 4500, -1500, 1500, 0, 3500)
    show_zones = a.zoom is None
    for axis, a0, a1, poly, col, zona in items:
        if zona and not show_zones:
            continue
        f = prism_faces(axis, a0, a1, poly)
        if zona:
            ax3.add_collection3d(Poly3DCollection(f, facecolor=col, alpha=0.06, edgecolor=col, linewidth=0.3))
        else:
            ax3.add_collection3d(Poly3DCollection(f, facecolor=col, edgecolor='#555555', linewidth=0.08, alpha=1.0))
    ax3.set_xlim(lim[0], lim[1]); ax3.set_ylim(lim[2], lim[3]); ax3.set_zlim(lim[4], lim[5])
    ax3.set_box_aspect((lim[1] - lim[0], lim[3] - lim[2], lim[5] - lim[4]))
    ax3.view_init(elev=a.vista[0], azim=a.vista[1])
    ax3.set_axis_off()
    ax3.set_title(spec['familia']['nombre_archivo'] + '  -  ' + spec['familia']['tipo'])

    if not a.solo3d:
        axL = fig.add_subplot(2, 2, 2)
        axF = fig.add_subplot(2, 2, 4)
        if a.dxf:
            import ezdxf
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            doc = ezdxf.readfile(a.dxf)
            for axx in (axL, axF):
                Frontend(RenderContext(doc), MatplotlibBackend(axx)).draw_layout(doc.modelspace())
        oxL, ozL = a.lateral
        oxF, ozF = a.frontal
        line = '#00e5ff' if a.dxf else '#333333'
        for axis, a0, a1, poly, col, zona in items:
            pts = [v for f in prism_faces(axis, a0, a1, poly) for v in f]
            c = COL['zonas'] if zona else ('#ff0000' if col == '#ff0000' else line)
            ls = ':' if zona else '-'
            lw = 0.5
            if axis == 'Y':
                xs = [p[0] + oxL for p in poly] + [poly[0][0] + oxL]
                zs = [p[1] + ozL for p in poly] + [poly[0][1] + ozL]
                axL.plot(xs, zs, color=c, lw=lw, ls=ls)
            else:
                x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
                z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
                axL.add_patch(plt.Rectangle((x0 + oxL, z0 + ozL), x1 - x0, z1 - z0, fill=False, ec=c, lw=lw, ls=ls))
            if axis == 'X':
                xs = [oxF - p[0] for p in poly] + [oxF - poly[0][0]]
                zs = [p[1] + ozF for p in poly] + [poly[0][1] + ozF]
                axF.plot(xs, zs, color=c, lw=lw, ls=ls)
            else:
                y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
                z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
                axF.add_patch(plt.Rectangle((oxF - y1, z0 + ozF), y1 - y0, z1 - z0, fill=False, ec=c, lw=lw, ls=ls))
        axL.set_xlim(oxL - 1500, oxL + 4600); axL.set_ylim(ozL - 100, ozL + 3600)
        axF.set_xlim(oxF - 1300, oxF + 1300); axF.set_ylim(ozF - 100, ozF + 3600)
        for axx, t in ((axL, 'Alzado lateral X-Z'), (axF, 'Alzado frontal Y-Z (visto desde la puerta)')):
            axx.set_aspect('equal'); axx.set_title(t)
    fig.tight_layout()
    fig.savefig(a.png, dpi=110)
    print('ok ->', a.png, len(items), 'prismas')


if __name__ == '__main__':
    main()
