// Cálculos de ingeniería: caudales por red, pérdidas de carga, dimensionamiento, cargas eléctricas,
// interferencias y advertencias. Funciones puras sobre el modelo (sin three.js), probadas en tests/.
import { DIAM_DUCTO, DNS, FAMILIAS, LADOS_DUCTO, SISTEMAS, TUBO } from './catalogo.js';
import {
  cajasEquipo, conectoresEquipo, construirRed, dist, dot, ejesTramo, longitud, mul, rotulo, seccion, sub, add,
} from './modelo.js';

export const FLUIDOS = {
  aire:          { rho: 1.2, nu: 1.51e-5, rug: 0.09e-3, vmax: 8.0, dpmax: 1.0 },   // ducto galvanizado
  agua:          { rho: 998, nu: 1.0e-6, rug: 0.045e-3, vmax: 2.4, dpmax: 400 },   // acero Sch 40, 20 °C
  agua_caliente: { rho: 983, nu: 0.47e-6, rug: 0.045e-3, vmax: 2.4, dpmax: 400 },  // 60 °C
};
const K_ACCESORIO = { codo: 0.3, tee: 0.8, cruz: 1.0, reduccion: 0.15 };

// Factor de fricción de Darcy (Swamee-Jain; laminar 64/Re)
export function friccion(re, rugRel) {
  if (re < 2300) return 64 / Math.max(re, 1);
  return 0.25 / Math.log10(rugRel / 3.7 + 5.74 / re ** 0.9) ** 2;
}

// Diámetro equivalente de un ducto rectangular por fricción (Huebscher), mm
export function diamEquivalente(a, b) { return (1.3 * (a * b) ** 0.625) / (a + b) ** 0.25; }

// Hidráulica de un tramo. q: m³/h en ductos, L/s en tuberías. Devuelve v (m/s), dp (Pa/m), area (m²)
export function hidraulica(t, q) {
  const s = SISTEMAS[t.sistema];
  if (!s || !s.calc || !FLUIDOS[s.calc] || !(q > 0)) return null;
  const fl = FLUIDOS[s.calc];
  let Q, D, A;
  if (t.tipo === 'ducto') {
    Q = q / 3600;
    if (t.forma === 'redondo') { D = t.diam / 1000; A = (Math.PI * D * D) / 4; } else {
      A = (t.ancho * t.alto) / 1e6; D = diamEquivalente(t.ancho, t.alto) / 1000;
    }
  } else {
    Q = q / 1000;
    D = TUBO[t.dn][1] / 1000; A = (Math.PI * D * D) / 4;
  }
  const v = Q / A;
  const veq = Q / ((Math.PI * D * D) / 4); // velocidad en el diámetro equivalente (pérdida por fricción)
  const re = (veq * D) / fl.nu;
  const f = friccion(re, fl.rug / D);
  const dp = ((f / D) * fl.rho * veq * veq) / 2;
  return { v, dp, area: A, re, pdin: (fl.rho * v * v) / 2, fl };
}

// ---------------------------------------------------------------- caudales por red
// Cada componente conexa de tramos del mismo tipo forma una red. Si tiene un conector "fuente"
// (UMA, bomba, caldera...) se recorre como árbol desde ahí y cada tramo lleva la suma de los
// caudales de los terminales aguas abajo. Sin fuente, vale el caudal manual del tramo.
export function analizarRedes(m) {
  const red = construirRed(m);
  const { nudos, tramos, accesorios } = red;
  const porNudo = (id) => nudos[id];
  const visto = new Set();
  const redes = [];
  for (const t0 of tramos) {
    if (visto.has(t0.id)) continue;
    const comp = { tramos: [], nudos: new Set(), tipo: t0.tipo, sistemas: new Set() };
    const pila = [t0];
    visto.add(t0.id);
    while (pila.length) {
      const t = pila.pop();
      comp.tramos.push(t);
      comp.sistemas.add(t.sistema);
      for (const nid of [t._na, t._nb]) {
        comp.nudos.add(nid);
        for (const { t: u } of porNudo(nid).tramos) {
          if (!visto.has(u.id) && u.tipo === t.tipo) { visto.add(u.id); pila.push(u); }
        }
      }
    }
    const conns = [...comp.nudos].flatMap((id) => porNudo(id).conectores).filter((c) => c.tipo === comp.tipo);
    comp.conectores = conns;
    comp.fuente = conns.find((c) => c.fuente) || null;
    comp.sistema = comp.fuente ? comp.fuente.sistema : [...comp.sistemas][0];
    redes.push(comp);
  }

  const caudal = {}; // id tramo -> caudal
  const perdida = {}; // id tramo -> ΔP del tramo (Pa)
  const accPorNudo = Object.fromEntries(accesorios.map((a) => [a.nudo, a]));
  for (const r of redes) {
    for (const t of r.tramos) caudal[t.id] = t.caudal > 0 ? Number(t.caudal) : 0;
    r.caudalTotal = 0; r.dpCritico = 0; r.longitud = 0;
    r.terminales = r.conectores.filter((c) => !c.fuente).length;
    for (const t of r.tramos) r.longitud += longitud(t);
    if (!r.fuente) {
      r.caudalTotal = Math.max(0, ...r.tramos.map((t) => caudal[t.id]));
    } else {
      // árbol desde la fuente (los ciclos se rompen por el orden de visita)
      const hijos = new Map();
      const padre = new Map();
      const raiz = r.fuente._nudo;
      const orden = [];
      const vis = new Set([raiz]);
      const cola = [raiz];
      while (cola.length) {
        const nid = cola.shift();
        orden.push(nid);
        for (const { t } of porNudo(nid).tramos) {
          if (t.tipo !== r.tipo) continue;
          const otro = t._na === nid ? t._nb : t._na;
          if (vis.has(otro)) continue;
          vis.add(otro);
          padre.set(otro, { t, desde: nid });
          if (!hijos.has(nid)) hijos.set(nid, []);
          hijos.get(nid).push(otro);
          cola.push(otro);
        }
      }
      const demanda = new Map();
      for (const nid of [...orden].reverse()) {
        let q = porNudo(nid).conectores
          .filter((c) => c !== r.fuente && c.tipo === r.tipo && !c.fuente)
          .reduce((s, c) => s + (Number(c.caudal) || 0), 0);
        for (const h of hijos.get(nid) || []) q += demanda.get(h);
        demanda.set(nid, q);
        const p = padre.get(nid);
        if (p && !(p.t.caudal > 0)) caudal[p.t.id] = q;
      }
      r.caudalTotal = demanda.get(raiz) || 0;
      // pérdida acumulada hasta cada nudo: tramos + accesorios (K · presión dinámica)
      const acum = new Map([[raiz, 0]]);
      for (const nid of orden) {
        if (nid === raiz) continue;
        const { t, desde } = padre.get(nid);
        const h = hidraulica(t, caudal[t.id]);
        let dp = h ? h.dp * (longitud(t) / 1000) : 0;
        const a = accPorNudo[desde];
        if (h && a) dp += (K_ACCESORIO[a.tipo] || 0) * h.pdin;
        perdida[t.id] = dp;
        acum.set(nid, acum.get(desde) + dp);
      }
      r.dpCritico = Math.max(0, ...acum.values());
    }
    for (const t of r.tramos) {
      if (perdida[t.id] === undefined) {
        const h = hidraulica(t, caudal[t.id]);
        perdida[t.id] = h ? h.dp * (longitud(t) / 1000) : 0;
      }
    }
  }
  return { ...red, redes, caudal, perdida };
}

// ---------------------------------------------------------------- dimensionamiento
// Ductos: el menor tamaño con v <= vmax y ΔP <= 1 Pa/m (fricción constante), conservando el alto
// si es rectangular. Tuberías: el menor DN con v <= vmax y ΔP <= 400 Pa/m.
export function dimensionar(t, q) {
  const s = SISTEMAS[t.sistema];
  if (!s || !s.calc || !(q > 0)) return null;
  const fl = FLUIDOS[s.calc];
  const ok = (cand) => { const h = hidraulica(cand, q); return h && h.v <= fl.vmax && h.dp <= fl.dpmax; };
  if (t.tipo === 'tuberia') {
    for (const dn of DNS) if (ok({ ...t, dn })) return { dn };
    return { dn: DNS[DNS.length - 1] };
  }
  if (t.tipo === 'ducto' && t.forma === 'redondo') {
    for (const diam of DIAM_DUCTO) if (ok({ ...t, diam })) return { diam };
    return { diam: DIAM_DUCTO[DIAM_DUCTO.length - 1] };
  }
  // rectangular: relación de aspecto máx. 4:1; si no cabe con el alto actual, sube el alto
  for (const alto of LADOS_DUCTO.filter((h) => h >= t.alto)) {
    for (const ancho of LADOS_DUCTO) {
      if (ancho / alto > 4 || alto / ancho > 4) continue;
      if (ok({ ...t, ancho, alto })) return { ancho, alto };
    }
  }
  return { ancho: 2000, alto: 1000 };
}

// ---------------------------------------------------------------- eléctrico
const BREAKERS = [15, 20, 30, 40, 50, 60, 70, 80, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 600, 700, 800,
  1000, 1200];

export function corriente(va, tension, polos) {
  return polos === 3 ? va / (Math.sqrt(3) * tension) : va / tension;
}

export function breaker(i) { return BREAKERS.find((b) => b >= i * 1.25) || null; }

export function cargasElectricas(m) {
  const tableros = m.elementos.filter((e) => e.tipo === 'equipo' && FAMILIAS[e.familia].tablero);
  const porId = Object.fromEntries(m.elementos.map((e) => [e.id, e]));
  const circuitos = [];
  const sinTablero = [];
  for (const eq of m.elementos.filter((e) => e.tipo === 'equipo')) {
    for (const c of conectoresEquipo(eq).filter((x) => x.tipo === 'electrico')) {
      const i = corriente(c.va, c.tension, c.polos);
      const row = { equipo: eq, conector: c, i, breaker: breaker(i), tablero: porId[eq.tablero] || null };
      if (row.tablero) circuitos.push(row); else sinTablero.push(row);
    }
  }
  const resumen = tableros.map((tb) => {
    const cs = circuitos.filter((c) => c.tablero === tb);
    const va = cs.reduce((s, c) => s + c.conector.va, 0);
    const kw = cs.reduce((s, c) => s + c.conector.kw, 0);
    const v = FAMILIAS[tb.familia].tablero.tension;
    const i = corriente(va, v, 3);
    return { tablero: tb, circuitos: cs, va, kw, i, principal: breaker(i), tension: v };
  });
  return { resumen, circuitos, sinTablero };
}

// ---------------------------------------------------------------- interferencias
// Cajas orientadas (OBB): tramos con su sección real; equipos por prisma (caja alineada).
function obbTramo(t, holgura = 0) {
  const { d, s, u } = ejesTramo(t.a, t.b);
  const sc = seccion(t);
  return { c: mul(add(t.a, t.b), 0.5), ejes: [d, s, u],
    e: [longitud(t) / 2 - 1, sc.w / 2 + holgura - 1, sc.h / 2 + holgura - 1] };
}
function obbCaja(b) {
  return { c: mul(add(b.min, b.max), 0.5), ejes: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    e: [0, 1, 2].map((k) => (b.max[k] - b.min[k]) / 2 - 1) };
}

// Teorema del eje separador para dos OBB
export function obbChocan(A, B) {
  const R = [], AbsR = [];
  for (let i = 0; i < 3; i++) {
    R[i] = []; AbsR[i] = [];
    for (let j = 0; j < 3; j++) { R[i][j] = dot(A.ejes[i], B.ejes[j]); AbsR[i][j] = Math.abs(R[i][j]) + 1e-6; }
  }
  const tw = sub(B.c, A.c);
  const t = [dot(tw, A.ejes[0]), dot(tw, A.ejes[1]), dot(tw, A.ejes[2])];
  const a = A.e, b = B.e;
  for (let i = 0; i < 3; i++) {
    if (Math.abs(t[i]) > a[i] + b[0] * AbsR[i][0] + b[1] * AbsR[i][1] + b[2] * AbsR[i][2]) return false;
  }
  for (let j = 0; j < 3; j++) {
    const tj = t[0] * R[0][j] + t[1] * R[1][j] + t[2] * R[2][j];
    if (Math.abs(tj) > a[0] * AbsR[0][j] + a[1] * AbsR[1][j] + a[2] * AbsR[2][j] + b[j]) return false;
  }
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      const i1 = (i + 1) % 3, i2 = (i + 2) % 3, j1 = (j + 1) % 3, j2 = (j + 2) % 3;
      const ra = a[i1] * AbsR[i2][j] + a[i2] * AbsR[i1][j];
      const rb = b[j1] * AbsR[i][j2] + b[j2] * AbsR[i][j1];
      if (Math.abs(t[i2] * R[i1][j] - t[i1] * R[i2][j]) > ra + rb) return false;
    }
  }
  return true;
}

function cajaDeObb(o) {
  const r = [0, 1, 2].map((k) => o.ejes.reduce((s, ej, i) => s + Math.abs(ej[k]) * o.e[i], 0));
  return { min: o.c.map((v, k) => v - r[k]), max: o.c.map((v, k) => v + r[k]) };
}
const cajasSeTocan = (p, q) => [0, 1, 2].every((k) => p.min[k] <= q.max[k] && q.min[k] <= p.max[k]);

export function interferencias(m, red = construirRed(m)) {
  const tramos = red.tramos.map((t) => { const o = obbTramo(t); return { t, o, caja: cajaDeObb(o) }; });
  const out = [];
  for (let i = 0; i < tramos.length; i++) {
    for (let j = i + 1; j < tramos.length; j++) {
      const A = tramos[i], B = tramos[j];
      if ([A.t._na, A.t._nb].some((n) => n === B.t._na || n === B.t._nb)) continue; // conectados
      if (!cajasSeTocan(A.caja, B.caja)) continue;
      if (obbChocan(A.o, B.o)) out.push({ a: A.t, b: B.t, p: mul(add(A.o.c, B.o.c), 0.5) });
    }
  }
  for (const eq of m.elementos.filter((e) => e.tipo === 'equipo')) {
    const cajas = cajasEquipo(eq);
    const conns = conectoresEquipo(eq);
    for (const T of tramos) {
      // un tramo que llega a un conector del equipo entra en su boquilla: se excluyen los prismas junto al conector
      const llega = conns.filter((c) => dist(c.pos, T.t.a) < 5 || dist(c.pos, T.t.b) < 5);
      for (const cj of cajas) {
        if (!cajasSeTocan(T.caja, cj)) continue;
        if (llega.some((c) => [0, 1, 2].every((k) => c.pos[k] >= cj.min[k] - 60 && c.pos[k] <= cj.max[k] + 60))) continue;
        if (obbChocan(T.o, obbCaja(cj))) { out.push({ a: T.t, b: eq, p: T.o.c }); break; }
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------- advertencias
export function advertencias(m, an) {
  const out = [];
  for (const { t, nudo } of an.abiertos.filter((x) => x.t.tipo !== 'bandeja')) out.push({ nivel: 'aviso', el: t, p: nudo.p, txt: `Extremo abierto en ${t.id} (${SISTEMAS[t.sistema].nombre})` });
  for (const t of an.tramos) {
    const s = SISTEMAS[t.sistema];
    if (s.tipo !== t.tipo) out.push({ nivel: 'error', el: t, txt: `${t.id}: el sistema ${s.nombre} no admite ${t.tipo}` });
    const h = hidraulica(t, an.caudal[t.id]);
    if (h && h.v > h.fl.vmax) out.push({ nivel: 'aviso', el: t, txt: `${t.id} ${rotulo(t)}: velocidad ${h.v.toFixed(1)} m/s > ${h.fl.vmax} m/s` });
    if (h && h.dp > h.fl.dpmax * 1.5) out.push({ nivel: 'aviso', el: t, txt: `${t.id} ${rotulo(t)}: pérdida ${h.dp.toFixed(h.dp < 10 ? 2 : 0)} Pa/m alta` });
    if (s.calc === 'gravedad') {
      const horiz = Math.hypot(t.b[0] - t.a[0], t.b[1] - t.a[1]);
      if (horiz > 1 && Math.abs(t.b[2] - t.a[2]) / horiz < 0.01 && Math.abs(t.b[2] - t.a[2]) < horiz) {
        out.push({ nivel: 'aviso', el: t, txt: `${t.id}: desagüe con pendiente ${pendiente(t).toFixed(2)} % (mín. 1 %)` });
      }
    }
  }
  // conectores sin tramo
  for (const c of an.conectores) {
    if (c.tipo === 'electrico') continue;
    const n = an.nudos[c._nudo];
    if (!n || n.tramos.length === 0) {
      const eq = m.elementos.find((e) => e.id === c.equipo);
      out.push({ nivel: 'info', el: eq, p: c.pos, txt: `${eq.tag}: conector ${c.id} (${c.nombre}) sin conectar` });
    } else if (n.tramos.some(({ t }) => t.tipo === c.tipo && t.sistema !== c.sistema)) {
      const eq = m.elementos.find((e) => e.id === c.equipo);
      out.push({ nivel: 'error', el: eq, p: c.pos, txt: `${eq.tag} ${c.id}: el tramo conectado no es del sistema ${SISTEMAS[c.sistema].nombre}` });
    }
  }
  const el = cargasElectricas(m);
  for (const r of el.sinTablero) out.push({ nivel: 'info', el: r.equipo, txt: `${r.equipo.tag}: ${r.conector.nombre} (${r.conector.kw} kW) sin tablero asignado` });
  return out;
}

export function pendiente(t) {
  const horiz = Math.hypot(t.b[0] - t.a[0], t.b[1] - t.a[1]);
  return horiz > 0 ? (Math.abs(t.b[2] - t.a[2]) / horiz) * 100 : Infinity;
}
