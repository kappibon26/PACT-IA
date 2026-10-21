// Modelo del proyecto: niveles, elementos lineales (ducto, tubería, bandeja) y equipos.
// Todo en mm. Los accesorios (codos, tees, reducciones) no se guardan: se deducen de la red.
import { FAMILIAS, SISTEMAS, TUBO } from './catalogo.js';

export const TOL = 2; // mm: dos extremos a menos de esto son el mismo nudo

export function modeloVacio(nombre = 'Proyecto sin nombre') {
  return {
    version: 1,
    nombre,
    niveles: [{ id: 'N1', nombre: 'Nivel 1', elev: 0 }],
    elementos: [],
    contador: 0,
  };
}

export function nuevoId(m, pref) {
  m.contador = (m.contador || 0) + 1;
  return pref + m.contador;
}

export const esLineal = (e) => e.tipo === 'ducto' || e.tipo === 'tuberia' || e.tipo === 'bandeja';

// ---------------------------------------------------------------- vectores
export const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
export const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
export const len = (a) => Math.hypot(a[0], a[1], a[2]);
export const norm = (a) => { const l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
export const dist = (a, b) => len(sub(a, b));

// Ejes locales de un tramo: d = dirección, s = lado (horizontal), u = arriba
export function ejesTramo(a, b) {
  const d = norm(sub(b, a));
  const s = Math.abs(d[2]) > 0.999 ? [1, 0, 0] : norm(cross([0, 0, 1], d));
  return { d, s, u: cross(d, s) };
}

// Sección transversal (ancho horizontal, alto vertical) y radio envolvente de un tramo
export function seccion(e) {
  if (e.tipo === 'tuberia') { const od = TUBO[e.dn][0]; return { w: od, h: od, redondo: true }; }
  if (e.tipo === 'ducto' && e.forma === 'redondo') return { w: e.diam, h: e.diam, redondo: true };
  return { w: e.ancho, h: e.alto, redondo: false };
}

export function rotulo(e) {
  if (e.tipo === 'tuberia') return 'DN' + e.dn;
  if (e.tipo === 'ducto' && e.forma === 'redondo') return 'Ø' + e.diam;
  return e.ancho + '×' + e.alto;
}

// ---------------------------------------------------------------- equipos
export function familia(e) { return FAMILIAS[e.familia]; }

function rotZ(p, grados) {
  const a = (grados * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  return [p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2]];
}

export function aMundo(eq, p) { return add(rotZ(p, eq.rot || 0), eq.pos); }

// Conectores de un equipo en coordenadas del proyecto, con sistema y caudal ya resueltos
export function conectoresEquipo(eq) {
  const f = familia(eq);
  return f.conectores.map((c) => {
    const w = { ...c, equipo: eq.id, pos: aMundo(eq, c.pos), dir: rotZ(c.dir, eq.rot || 0) };
    if (c.sistema === '*') w.sistema = (eq.param && eq.param.sistema) || 'AF';
    if (c.caudal === 'param') w.caudal = Number(eq.param && eq.param.caudal) || 0;
    if (c.id === 'CX01' && eq.param && eq.param.caudal_vapor) w.caudal = Number(eq.param.caudal_vapor);
    return w;
  });
}

// Caja envolvente (mm) de cada prisma de un equipo, en coordenadas del proyecto
export function cajasEquipo(eq) {
  const f = familia(eq);
  if (!f._cajasLocales) {
    f._cajasLocales = f.prismas.map(([eje, a0, a1, , poly]) => {
      const us = poly.map((p) => p[0]), vs = poly.map((p) => p[1]);
      const u = [Math.min(...us), Math.max(...us)], v = [Math.min(...vs), Math.max(...vs)], a = [a0, a1];
      if (eje === 'X') return [a, u, v];
      if (eje === 'Y') return [u, a, v];
      return [u, v, a];
    });
  }
  return f._cajasLocales.map(([x, y, z]) => {
    const pts = [];
    for (const px of x) for (const py of y) for (const pz of z) pts.push(aMundo(eq, [px, py, pz]));
    return {
      min: [0, 1, 2].map((k) => Math.min(...pts.map((p) => p[k]))),
      max: [0, 1, 2].map((k) => Math.max(...pts.map((p) => p[k]))),
    };
  });
}

export function cajaTotalEquipo(eq) {
  const cs = cajasEquipo(eq);
  return {
    min: [0, 1, 2].map((k) => Math.min(...cs.map((c) => c.min[k]))),
    max: [0, 1, 2].map((k) => Math.max(...cs.map((c) => c.max[k]))),
  };
}

export function siguienteTag(m, fam) {
  const pref = FAMILIAS[fam].prefijo;
  let n = 1;
  const usados = new Set(m.elementos.filter((e) => e.tipo === 'equipo').map((e) => e.tag));
  while (usados.has(pref + '-' + String(n).padStart(2, '0'))) n++;
  return pref + '-' + String(n).padStart(2, '0');
}

export function nivelDe(m, z) {
  const ns = [...m.niveles].sort((a, b) => a.elev - b.elev);
  let r = ns[0];
  for (const n of ns) if (z >= n.elev - 1) r = n;
  return r;
}

// ---------------------------------------------------------------- red
// Nudos = extremos de tramos y conectores de equipo. Devuelve el grafo y los accesorios deducidos.
export function construirRed(m) {
  const nudos = [];
  const buscar = (p) => {
    for (const n of nudos) if (Math.abs(n.p[0] - p[0]) < TOL && Math.abs(n.p[1] - p[1]) < TOL && Math.abs(n.p[2] - p[2]) < TOL) return n;
    const n = { id: nudos.length, p: [...p], tramos: [], conectores: [] };
    nudos.push(n);
    return n;
  };
  const tramos = m.elementos.filter(esLineal);
  for (const t of tramos) {
    const na = buscar(t.a), nb = buscar(t.b);
    na.tramos.push({ t, extremo: 'a' });
    nb.tramos.push({ t, extremo: 'b' });
    t._na = na.id; t._nb = nb.id;
  }
  const conectores = [];
  for (const eq of m.elementos.filter((e) => e.tipo === 'equipo')) {
    for (const c of conectoresEquipo(eq)) {
      conectores.push(c);
      if (c.tipo === 'electrico') continue;
      const n = buscar(c.pos);
      n.conectores.push(c);
      c._nudo = n.id;
    }
  }

  const accesorios = [];
  const abiertos = [];
  for (const n of nudos) {
    const k = n.tramos.length;
    if (k === 0) continue;
    if (k === 1 && n.conectores.length === 0) { abiertos.push({ nudo: n, t: n.tramos[0].t }); continue; }
    if (k === 1) continue;
    // dirección saliente de cada tramo desde el nudo
    const dirs = n.tramos.map(({ t, extremo }) => norm(extremo === 'a' ? sub(t.b, t.a) : sub(t.a, t.b)));
    const base = n.tramos[0].t;
    let tipo;
    if (k === 2) {
      const colineal = dot(dirs[0], dirs[1]) < -0.999;
      const mismo = rotulo(n.tramos[0].t) === rotulo(n.tramos[1].t);
      if (colineal && mismo) continue; // unión recta: no genera accesorio
      tipo = colineal ? 'reduccion' : 'codo';
    } else if (k === 3) tipo = 'tee';
    else tipo = 'cruz';
    const mayor = n.tramos.map((x) => x.t).sort((a, b) => seccion(b).w * seccion(b).h - seccion(a).w * seccion(a).h)[0];
    accesorios.push({ id: 'F' + n.id, nudo: n.id, p: n.p, tipo, clase: base.tipo, sistema: base.sistema, t: mayor, dirs,
      angulo: k === 2 ? Math.round((Math.acos(Math.max(-1, Math.min(1, -dot(dirs[0], dirs[1])))) * 180) / Math.PI) : null });
  }
  return { nudos, tramos, conectores, accesorios, abiertos };
}

// Partir un tramo en un punto interior (para crear una tee). Devuelve el nuevo tramo.
export function partirTramo(m, t, p) {
  const nuevo = { ...t, id: nuevoId(m, t.tipo[0].toUpperCase()), a: [...p], b: [...t.b] };
  t.b = [...p];
  m.elementos.push(nuevo);
  return nuevo;
}

// Punto más cercano del tramo a p y su parámetro (0..1)
export function proyectar(t, p) {
  const ab = sub(t.b, t.a);
  const k = Math.max(0, Math.min(1, dot(sub(p, t.a), ab) / (dot(ab, ab) || 1)));
  return { k, p: add(t.a, mul(ab, k)) };
}

export function longitud(t) { return dist(t.a, t.b); }

export function colorSistema(k) { return (SISTEMAS[k] || { color: '#888888' }).color; }
