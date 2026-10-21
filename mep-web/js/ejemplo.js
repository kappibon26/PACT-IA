// Proyecto de ejemplo: sala de peletizado (PEL-01 de AVSA, caldera, bomba y tanque) y oficinas con UMA.
// Las rutas se dan por puntos; un punto puede ser un conector de equipo { eq: 'TAG', c: 'ID' }.
import { analizarRedes, dimensionar } from './calculos.js';
import { FAMILIAS } from './catalogo.js';
import { conectoresEquipo, modeloVacio, nuevoId } from './modelo.js';

export function crearEjemplo() {
  const m = modeloVacio('Planta de pienso · sala de peletizado');
  m.niveles = [
    { id: 'N1', nombre: 'Nivel 1 · NPT ±0.00', elev: 0 },
    { id: 'N2', nombre: 'Nivel 2 · mezanine +6.00', elev: 6000 },
  ];
  const tags = {};
  const equipo = (familia, tag, pos, rot = 0, extra = {}) => {
    const e = { id: nuevoId(m, 'E'), tipo: 'equipo', familia, tag, pos, rot, param: { ...(FAMILIAS[familia].param || {}) }, ...extra };
    m.elementos.push(e);
    tags[tag] = e;
    return e;
  };
  const punto = (p) => {
    if (!p.eq) return p;
    return conectoresEquipo(tags[p.eq]).find((c) => c.id === p.c).pos.map((v) => Math.round(v * 10) / 10);
  };
  const ruta = (props, pts) => {
    const ps = pts.map(punto);
    for (let i = 0; i < ps.length - 1; i++) {
      m.elementos.push({ id: nuevoId(m, props.tipo[0].toUpperCase()), ...props, a: [...ps[i]], b: [...ps[i + 1]] });
    }
  };

  // ------------------------------------------------ sala de peletizado
  equipo('PEL01', 'PEL-01', [0, 0, 0], 0, { param: { caudal_vapor: 0 } });
  equipo('CAL', 'CAL-01', [-2000, -7000, 0]);
  equipo('BOM', 'B-01', [-6000, -9000, 0], 0, { param: { sistema: 'AF' } });
  equipo('TAN', 'TK-01', [-9000, -9000, 0]);
  equipo('TAB', 'TD-01', [-4000, 3000, 0]);

  const vapor = { tipo: 'tuberia', sistema: 'VP', dn: 200 };
  ruta(vapor, [{ eq: 'CAL-01', c: 'VP' }, [1800, -7000, 4000], [3224, -7000, 4000], [3224, -2500, 4000],
    [3224, -2500, 1805.2], { eq: 'PEL-01', c: 'CX01' }]);

  const af = { tipo: 'tuberia', sistema: 'AF', dn: 65 };
  ruta({ ...af, dn: 80, caudal: 1.3 }, [{ eq: 'TK-01', c: 'OUT' }, [-7000, -9000, 200], [-7000, -9000, 450], { eq: 'B-01', c: 'IN' }]);
  ruta(af, [{ eq: 'B-01', c: 'OUT' }, [-6150, -9000, 2000], [-1200, -9000, 2000], [-1200, -9000, 900], { eq: 'CAL-01', c: 'AF' }]);

  ruta({ tipo: 'bandeja', sistema: 'FZ', ancho: 300, alto: 100 },
    [{ eq: 'TD-01', c: 'FZ' }, [-4000, 3000, 4200], [1600, 3000, 4200], [1600, -1500, 4200]]);

  // ------------------------------------------------ oficinas
  equipo('UMA', 'UMA-01', [10500, 4000, 0]);
  equipo('EXT', 'EXT-01', [19000, 5200, 0]);
  const difusores = [];
  for (const x of [15000, 18000, 21000]) {
    for (const y of [-2500, 2500]) difusores.push(equipo('DIF', 'DIF-' + String(difusores.length + 1).padStart(2, '0'), [x, y, 2900]));
  }
  equipo('REJ', 'REJ-01', [11500, -2000, 2900], 0, { param: { caudal: 3600 } });

  const sa = { tipo: 'ducto', sistema: 'SA', forma: 'rect', ancho: 600, alto: 400 };
  ruta(sa, [{ eq: 'UMA-01', c: 'SA' }, [13150, 4000, 3400], [13150, 0, 3400], [15000, 0, 3400], [18000, 0, 3400], [21000, 0, 3400]]);
  for (const x of [15000, 18000, 21000]) {
    for (const y of [-2500, 2500]) ruta({ ...sa, ancho: 300, alto: 300 }, [[x, 0, 3400], [x, y, 3400], [x, y, 3130]]);
  }
  ruta({ ...sa, sistema: 'RA', ancho: 500, alto: 400 },
    [{ eq: 'UMA-01', c: 'RA' }, [10000, 4000, 950], [10000, 4000, 3400], [10000, -2000, 3400], [11500, -2000, 3400], [11500, -2000, 3130]]);

  // agua helada hacia el chiller (pendiente de modelar): cruza el retorno a la misma cota -> interferencia
  ruta({ tipo: 'tuberia', sistema: 'AHS', dn: 65, caudal: 4.8 }, [{ eq: 'UMA-01', c: 'AHS' }, [12000, 2500, 500], [12000, 2500, 3400], [8000, 2500, 3400]]);
  ruta({ tipo: 'tuberia', sistema: 'AHR', dn: 65, caudal: 4.8 }, [{ eq: 'UMA-01', c: 'AHR' }, [12300, 2200, 500], [12300, 2200, 3700], [8000, 2200, 3700]]);
  // condensados de la UMA al sifón de piso, con 1 % de pendiente
  ruta({ tipo: 'tuberia', sistema: 'DS', dn: 32 }, [{ eq: 'UMA-01', c: 'DS' }, [11800, 2800, 245.5], [11800, -3500, 182.5]]);

  // circuitos: todo al TD-01 salvo el extractor (queda como advertencia)
  for (const e of m.elementos) if (e.tipo === 'equipo' && e.familia !== 'TAB' && e.familia !== 'EXT') e.tablero = tags['TD-01'].id;

  // dimensionar ductos de aire con los caudales de la red
  const an = analizarRedes(m);
  for (const t of m.elementos) {
    if (t.tipo === 'ducto' && (t.sistema === 'SA' || t.sistema === 'RA') && an.caudal[t.id] > 0) {
      Object.assign(t, dimensionar(t, an.caudal[t.id]));
    }
  }
  return m;
}
