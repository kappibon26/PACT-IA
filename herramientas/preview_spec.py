# -*- coding: utf-8 -*-
"""
Vista previa / control de calidad de un spec de familia (fuera de Revit).

  python herramientas/preview_spec.py dynamo/specs/spec_PEL01_CPM7730.py salida.png
  python herramientas/preview_spec.py dynamo/specs/spec_PEL01_CPM7730.py salida.png --dxf PLANO.dxf \
         --lateral 17592.2 274.4 --frontal 14337.3 274.4

Dibuja isometrica + alzado lateral (X-Z) + alzado frontal (Y-Z).  Con --dxf superpone el spec
sobre el plano del proveedor (requiere ezdxf) para verificar cotas.
Los parametros --lateral / --frontal son el origen de la familia en coordenadas del CAD:
  lateral: x_cad = X + ox ; y_cad = Z + oz        frontal: x_cad = ox - Y ; y_cad = Z + oz
"""
import argparse
import importlib.util
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

COL = {'cuerpo': '#9aa0a6', 'motores': '#4e5e70', 'estructura': '#464646',
       'conexiones': '#E76A1F', 'zonas': '#E76A1F'}
AX = {'X': 0, 'Y': 1, 'Z': 2}
SEC = {'X': ('Y', 'Z'), 'Y': ('X', 'Z'), 'Z': ('X', 'Y')}


def load_spec(path):
    s = importlib.util.spec_from_file_location('spec_mod', path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m.SPEC


def boxes(spec):
    """Devuelve una lista (bbox((x0,x1),(y0,y1),(z0,z1)), color, forma, datos) aproximando todo a cajas/cilindros."""
    out = []
    for s in spec['solidos'] + spec.get('vacios', []):
        col = COL.get(s.get('sub'), '#ffffff') if 'corta' not in s else '#ff0000'
        if s['forma'] == 'caja':
            out.append(([s['x'], s['y'], s['z']], col, 'caja', s))
        elif s['forma'] == 'cilindro':
            a = AX[s['eje']]
            u, v = SEC[s['eje']]
            bb = [None] * 3
            bb[a] = s['rango']
            bb[AX[u]] = (s['centro'][0] - s['r'], s['centro'][0] + s['r'])
            bb[AX[v]] = (s['centro'][1] - s['r'], s['centro'][1] + s['r'])
            out.append((bb, col, 'cil', s))
        elif s['forma'] == 'transicion':
            for key, z in (('base', s['z'][0]), ('tope', s['z'][1])):
                cx, cy, dx, dy = s[key]
                out.append(([(cx - dx / 2, cx + dx / 2), (cy - dy / 2, cy + dy / 2), (z - 1, z + 1)], col, 'caja', s))
    for b in spec.get('boquillas', []):
        sgn = -1 if b['eje'][0] == '-' else 1
        e = b['eje'][1]
        a = AX[e]
        u, v = SEC[e]
        p0 = b['base'][a]
        p1 = p0 + sgn * b['proyeccion']
        if b['seccion'] == 'circular':
            hu = hv = b['d_brida'] / 2
        else:
            hu, hv = b['brida'][0] / 2, b['brida'][1] / 2
        bb = [None] * 3
        bb[a] = (min(p0, p1), max(p0, p1))
        bb[AX[u]] = (b['base'][AX[u]] - hu, b['base'][AX[u]] + hu)
        bb[AX[v]] = (b['base'][AX[v]] - hv, b['base'][AX[v]] + hv)
        out.append((bb, COL['conexiones'], 'cil' if b['seccion'] == 'circular' else 'caja', b))
    for z in spec.get('zonas', []):
        sgn = -1 if z['normal'][0] == '-' else 1
        e = z['normal'][1]
        a = AX[e]
        u, v = SEC[e]
        bb = [None] * 3
        p1 = z['plano'] + sgn * z['largo']
        bb[a] = (min(z['plano'], p1), max(z['plano'], p1))
        bb[AX[u]] = z['u']
        bb[AX[v]] = z['v']
        out.append((bb, 'zona', 'caja', z))
    return out


def cube_faces(bb):
    (x0, x1), (y0, y1), (z0, z1) = bb
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    idx = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return [[p[i] for i in f] for f in idx]


def cyl_faces(s, n=24):
    a = AX[s['eje']]
    u, v = AX[SEC[s['eje']][0]], AX[SEC[s['eje']][1]]
    faces = []
    r0, r1 = s['rango']
    ring = []
    for i in range(n):
        t = 2 * math.pi * i / n
        ring.append((s['centro'][0] + s['r'] * math.cos(t), s['centro'][1] + s['r'] * math.sin(t)))

    def P(cu, cv, ca):
        q = [0, 0, 0]
        q[a], q[u], q[v] = ca, cu, cv
        return tuple(q)
    for i in range(n):
        (u0, v0), (u1, v1) = ring[i], ring[(i + 1) % n]
        faces.append([P(u0, v0, r0), P(u1, v1, r0), P(u1, v1, r1), P(u0, v0, r1)])
    faces.append([P(cu, cv, r0) for cu, cv in ring])
    faces.append([P(cu, cv, r1) for cu, cv in ring])
    return faces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('png')
    ap.add_argument('--dxf')
    ap.add_argument('--lateral', nargs=2, type=float, default=(0.0, 0.0))
    ap.add_argument('--frontal', nargs=2, type=float, default=(0.0, 0.0))
    a = ap.parse_args()
    spec = load_spec(a.spec)
    items = boxes(spec)

    fig = plt.figure(figsize=(22, 13))
    ax3 = fig.add_subplot(2, 2, (1, 3), projection='3d')
    for bb, col, kind, s in items:
        if col == 'zona':
            ax3.add_collection3d(Poly3DCollection(cube_faces(bb), facecolor=COL['zonas'], alpha=0.08,
                                                  edgecolor=COL['zonas'], linewidth=0.3))
            continue
        f = cyl_faces(s) if (kind == 'cil' and 'centro' in s) else cube_faces(bb)
        ax3.add_collection3d(Poly3DCollection(f, facecolor=col, edgecolor='k', linewidth=0.15, alpha=0.95))
    ax3.set_xlim(-6000, 4500); ax3.set_ylim(-3000, 3000); ax3.set_zlim(0, 3600)
    ax3.set_box_aspect((10500, 6000, 3600))
    ax3.view_init(elev=22, azim=-58)
    ax3.set_xlabel('X'); ax3.set_ylabel('Y'); ax3.set_zlabel('Z')
    ax3.set_title(spec['familia']['nombre_archivo'] + '  -  ' + spec['familia']['tipo'])

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
    for bb, col, kind, s in items:
        c = COL['zonas'] if col == 'zona' else ('#00e5ff' if col != '#ff0000' else '#ff0000')
        ls = ':' if col == 'zona' else '-'
        (x0, x1), (y0, y1), (z0, z1) = bb
        axL.add_patch(plt.Rectangle((x0 + oxL, z0 + ozL), x1 - x0, z1 - z0, fill=False, ec=c, lw=0.8, ls=ls))
        axF.add_patch(plt.Rectangle((oxF - y1, z0 + ozF), y1 - y0, z1 - z0, fill=False, ec=c, lw=0.8, ls=ls))
    axL.set_xlim(oxL - 1500, oxL + 4600); axL.set_ylim(ozL - 100, ozL + 3600)
    axF.set_xlim(oxF - 1300, oxF + 1300); axF.set_ylim(ozF - 100, ozF + 3600)
    for axx, t in ((axL, 'Alzado lateral X-Z (cian = spec)'), (axF, 'Alzado frontal Y-Z (cian = spec)')):
        axx.set_aspect('equal'); axx.set_title(t)
    fig.tight_layout()
    fig.savefig(a.png, dpi=110)
    print('ok ->', a.png, len(items), 'piezas')


if __name__ == '__main__':
    main()
