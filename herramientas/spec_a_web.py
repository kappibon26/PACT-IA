# -*- coding: utf-8 -*-
"""
Exporta un spec de familia al modelador web PACT MEP (mep-web/).

  python herramientas/spec_a_web.py dynamo/specs/spec_PEL01_CPM7730.py mep-web/js/equipos/PEL01.js

Escribe un modulo JS con la geometria simplificada (prismas sin huecos, igual que preview_spec.py), los
conectores MEP (boquillas) y los conectores electricos del spec, en mm y en el sistema de coordenadas de
la familia.  El modelador lo coloca como un equipo mas, con sus conectores listos para trazar.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preview_spec import AX, SEC, load_spec, loop_pts, prisms  # noqa: E402

DNS = (15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300)

# sistema del modelador web por boquilla: vapor -> VP, el resto de aire/producto -> PR (producto a granel)
SISTEMA_WEB = {'OtherPipe': 'VP', 'OtherAir': 'PR'}


def _r(v):
    return round(v, 1)


def bbox_solido(s):
    """(min, max) en XYZ de un solido del spec."""
    f = s['forma']
    if f == 'caja':
        return [s['x'][0], s['y'][0], s['z'][0]], [s['x'][1], s['y'][1], s['z'][1]]
    if f == 'cilindro':
        lazos = [{'t': 'circ', 'c': s['centro'], 'r': s['r']}]
    elif f == 'ext':
        lazos = s['lazos']
    else:
        raise ValueError('bbox no soportado: ' + f)
    pts = [p for lz in lazos for p in loop_pts(lz)]
    ku, kv = SEC[s['eje']]
    lo, hi = [0.0] * 3, [0.0] * 3
    lo[AX[s['eje']]], hi[AX[s['eje']]] = min(s['rango']), max(s['rango'])
    lo[AX[ku]], hi[AX[ku]] = min(p[0] for p in pts), max(p[0] for p in pts)
    lo[AX[kv]], hi[AX[kv]] = min(p[1] for p in pts), max(p[1] for p in pts)
    return lo, hi


def vector_eje(eje):
    v = [0.0, 0.0, 0.0]
    v[AX[eje[1]]] = -1.0 if eje[0] == '-' else 1.0
    return v


def conectores(spec):
    out = []
    for b in spec.get('boquillas', []):
        d = vector_eje(b['eje'])
        pos = [b['base'][i] + d[i] * b['proyeccion'] for i in range(3)]
        c = {'id': b['id'], 'nombre': b['nombre'], 'pos': [_r(v) for v in pos], 'dir': d,
             'sistema': SISTEMA_WEB.get(b['sistema'], 'PR'), 'flujo': 'entrada' if b['flujo'] == 'In' else 'salida'}
        if b['tipo'] == 'tuberia':
            c.update(tipo='tuberia', dn=min(DNS, key=lambda d: abs(d - b['dn'])))  # 203.2 mm (8") -> DN200
        else:
            c.update(tipo='ducto', ancho=b['abertura'][0], alto=b['abertura'][1])
        out.append(c)
    solidos = {s['id']: s for s in spec['solidos']}
    for e in spec.get('electricos', []):
        lo, hi = bbox_solido(solidos[e['en']])
        d = vector_eje(e['cara'])
        pos = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
        k = AX[e['cara'][1]]
        pos[k] = hi[k] if d[k] > 0 else lo[k]
        out.append({'id': e['id'], 'nombre': e['nombre'], 'tipo': 'electrico', 'sistema': 'FZ',
                    'pos': [_r(v) for v in pos], 'dir': d, 'tension': e['tension'], 'polos': e['polos'],
                    'kw': e['kw'], 'va': e['va']})
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    spec = load_spec(sys.argv[1])
    loi = {k: v for k, _, v in spec['loi']}
    prismas = []
    for eje, a0, a1, poly, col, zona in prisms(spec):
        if zona:
            continue
        prismas.append([eje, _r(a0), _r(a1), col, [[_r(u), _r(v)] for u, v in poly]])
    fam = {
        'id': os.path.splitext(os.path.basename(sys.argv[2]))[0],
        'nombre': spec['familia']['tipo'],
        'categoria': 'Equipo mecánico',
        'fabricante': spec['nativos'].get('ALL_MODEL_MANUFACTURER', ''),
        'tag': loi.get('AM_Tag', ''),
        'descripcion': spec['nativos'].get('ALL_MODEL_DESCRIPTION', ''),
        'peso_kg': loi.get('AM_Peso_kg'),
        'prismas': prismas,
        'conectores': conectores(spec),
    }
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        f.write('// Generado por herramientas/spec_a_web.py desde %s. No editar a mano.\n'
                % os.path.basename(sys.argv[1]).replace('\\', '/'))
        f.write('export default ')
        json.dump(fam, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')
    print('%s: %d prismas, %d conectores' % (sys.argv[2], len(prismas), len(fam['conectores'])))


if __name__ == '__main__':
    main()
