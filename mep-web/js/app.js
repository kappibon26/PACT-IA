// Interfaz: herramientas de trazado, selección, propiedades, navegador, tablas y archivo.
import { advertencias, analizarRedes, cargasElectricas, dimensionar, hidraulica, interferencias, pendiente } from './calculos.js';
import { BANDEJA_ALTOS, BANDEJA_ANCHOS, DIAM_DUCTO, DNS, FAMILIAS, LADOS_DUCTO, SISTEMAS, TIPOS, sistemasDe } from './catalogo.js';
import { crearEjemplo } from './ejemplo.js';
import { Escena } from './escena.js';
import { exportarIFC, zip } from './ifc.js';
import {
  add, cajaTotalEquipo, conectoresEquipo, dist, esLineal, familia, longitud, modeloVacio, mul, nivelDe, norm, nuevoId,
  partirTramo, proyectar, rotulo, seccion, siguienteTag, sub,
} from './modelo.js';

const $ = (s) => document.querySelector(s);
const h = (tag, attrs = {}, ...hijos) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, '');
    else if (v !== false && v !== null && v !== undefined) el.setAttribute(k, v);
  }
  for (const c of hijos.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
};
const f1 = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d }));
const CLAVE = 'pact-mep-modelo-v1';

// ------------------------------------------------------------------ estado
let m;
try { const g = localStorage.getItem(CLAVE); m = g ? JSON.parse(g) : null; } catch { m = null; }
if (!m || !m.elementos) m = crearEjemplo();

const est = {
  herr: 'seleccionar',
  vista: '3d',
  nivel: m.niveles[0].id,
  sel: null,
  ruta: null,         // { pts: [[x,y,z]...], props } mientras se traza
  snap: null,
  paso: 100,
  etiquetas: false,
  conectores: false,
  ocultos: new Set(),
  tabla: 'ductos',
  op: {
    ducto: { sistema: 'SA', forma: 'rect', ancho: 400, alto: 300, diam: 300, desfase: 3400 },
    tuberia: { sistema: 'AF', dn: 50, desfase: 3000, pendiente: 0 },
    bandeja: { sistema: 'FZ', ancho: 300, alto: 100, desfase: 4200 },
    equipo: { familia: 'UMA', rot: 0, desfase: null },
  },
};
const pilaDeshacer = [], pilaRehacer = [];
let an, avisos, choques, electrico;

const escena = new Escena($('#lienzo'));

function nivelActivo() { return m.niveles.find((n) => n.id === est.nivel) || m.niveles[0]; }
function techoNivel(n) {
  const sup = m.niveles.filter((x) => x.elev > n.elev).sort((a, b) => a.elev - b.elev)[0];
  return sup ? sup.elev : n.elev + 8000;
}
function zTrabajo() {
  const n = nivelActivo();
  if (est.herr === 'equipo') {
    const d = est.op.equipo.desfase ?? FAMILIAS[est.op.equipo.familia].desfase;
    return n.elev + d;
  }
  return n.elev + (est.op[est.herr] ? est.op[est.herr].desfase : 0);
}
const elemento = (id) => m.elementos.find((e) => e.id === id);

// ------------------------------------------------------------------ cambios con deshacer
function guardarPaso() {
  pilaDeshacer.push(JSON.stringify(m));
  if (pilaDeshacer.length > 120) pilaDeshacer.shift();
  pilaRehacer.length = 0;
}
function cambiar(fn) { guardarPaso(); fn(); refrescar(); }
function deshacer() {
  if (!pilaDeshacer.length) return;
  terminarRuta();
  pilaRehacer.push(JSON.stringify(m));
  m = JSON.parse(pilaDeshacer.pop());
  if (est.sel && !elemento(est.sel)) est.sel = null;
  refrescar();
  toast('Deshecho');
}
function rehacer() {
  if (!pilaRehacer.length) return;
  pilaDeshacer.push(JSON.stringify(m));
  m = JSON.parse(pilaRehacer.pop());
  refrescar();
  toast('Rehecho');
}

function refrescar({ redibujar = true } = {}) {
  an = analizarRedes(m);
  avisos = advertencias(m, an);
  choques = interferencias(m, an);
  electrico = cargasElectricas(m);
  try { localStorage.setItem(CLAVE, JSON.stringify(m)); } catch { /* sin almacenamiento: se trabaja en memoria */ }
  if (redibujar) dibujar();
  pintarNavegador();
  pintarPropiedades();
  pintarOpciones();
  pintarTablas();
  pintarHud();
  $('#proyecto-nombre').textContent = m.nombre;
  $('#b-deshacer').disabled = !pilaDeshacer.length;
  $('#b-rehacer').disabled = !pilaRehacer.length;
  $('#b-borrar').disabled = !est.sel;
}

function dibujar() {
  const marcas = [
    ...choques.map((c) => ({ p: c.p, r: 420, color: '#e0262f' })),
    ...an.abiertos.filter((a) => a.t.tipo !== 'bandeja').map((a) => ({ p: a.nudo.p, r: Math.max(seccion(a.t).w, seccion(a.t).h) * 0.75, color: '#f0a020' })),
  ];
  escena.dibujar(m, an, { sel: est.sel, ocultos: est.ocultos, conectores: est.conectores || est.herr !== 'seleccionar', etiquetas: est.etiquetas, marcas });
}

// ------------------------------------------------------------------ tema
function aplicarTema() {
  const cs = getComputedStyle(document.documentElement);
  const v = (k) => cs.getPropertyValue(k).trim();
  escena.setTema({ fondo: v('--canvas'), grilla: v('--grid'), grillaFuerte: v('--grid-strong'), acento: v('--accent') });
  escena.mats.clear();
  dibujar();
}
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', aplicarTema);
new MutationObserver(aplicarTema).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

// ------------------------------------------------------------------ herramientas
const HINTS = {
  seleccionar: 'Clic para seleccionar · arrastrar para orbitar (planta: desplazar) · rueda para zoom · Supr elimina',
  ducto: 'Clic en un conector, un extremo, un tramo (crea una tee) o el plano de trabajo · Mayús: ángulo libre · Esc termina',
  tuberia: 'Clic para trazar · con pendiente > 0 el tramo baja al avanzar · Esc termina · cambiar el desfase crea un montante',
  bandeja: 'Clic para trazar bandeja portacables desde el tablero o el plano de trabajo · Esc termina',
  equipo: 'Clic para colocar · R gira 90° · Esc vuelve a Seleccionar',
};

function setHerr(hr) {
  terminarRuta();
  est.herr = hr;
  document.querySelectorAll('[data-herr]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.herr === hr)));
  $('#hint').textContent = HINTS[hr];
  escena.grilla(zTrabajo(), 1000);
  escena.ponerCursor(null);
  escena.limpiarPreview();
  $('#snap').hidden = true;
  pintarOpciones();
  dibujar();
}

function setVista(v) {
  est.vista = v;
  const n = nivelActivo();
  escena.setVista(v, n.elev, techoNivel(n));
  document.querySelectorAll('[data-vista]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.vista === v)));
  pintarNavegador();
  pintarHud();
}

function setNivel(id) {
  est.nivel = id;
  terminarRuta();
  escena.grilla(zTrabajo(), 1000);
  setVista(est.vista);
}

function terminarRuta() {
  est.ruta = null;
  escena.limpiarPreview();
}

// --- captura de puntos
const PX = 14;
function buscarSnap(ev) {
  const ndc = escena.ndc(ev);
  const r = escena.renderer.domElement.getBoundingClientRect();
  const mx = ev.clientX - r.left, my = ev.clientY - r.top;
  const tipo = est.herr;
  let mejor = null;
  const probar = (p, cand, extra = 0) => {
    const s = escena.aPantalla(p);
    if (s.z > 1) return;
    const d = Math.hypot(s.x - mx, s.y - my) - extra;
    if (d < PX && (!mejor || d < mejor.d)) mejor = { ...cand, p, d };
  };
  if (esLineal({ tipo })) {
    for (const c of an.conectores) {
      if (c.tipo !== tipo) continue;
      if (an.nudos[c._nudo] && an.nudos[c._nudo].tramos.length) continue; // conector ya ocupado
      const eq = elemento(c.equipo);
      probar(c.pos, { clase: 'conector', c, txt: `${eq.tag} · ${c.id} ${c.nombre} · ${SISTEMAS[c.sistema].nombre} ${c.dn ? 'DN' + c.dn : c.ancho + '×' + c.alto}` }, 4);
    }
    for (const n of an.nudos) {
      const t = n.tramos.find((x) => x.t.tipo === tipo);
      if (t && !est.ocultos.has(t.t.sistema)) probar(n.p, { clase: 'extremo', t: t.t, txt: `Extremo · ${SISTEMAS[t.t.sistema].nombre} ${rotulo(t.t)}` }, 2);
    }
    if (!mejor) {
      for (const t of an.tramos) {
        if (t.tipo !== tipo || est.ocultos.has(t.sistema)) continue;
        const A = escena.aPantalla(t.a), B = escena.aPantalla(t.b);
        if (A.z > 1 || B.z > 1) continue;
        const dx = B.x - A.x, dy = B.y - A.y, L2 = dx * dx + dy * dy;
        if (L2 < 100) continue;
        const k = ((mx - A.x) * dx + (my - A.y) * dy) / L2;
        if (k < 0.04 || k > 0.96) continue;
        const d = Math.hypot(A.x + k * dx - mx, A.y + k * dy - my);
        if (d < PX && (!mejor || d < mejor.d)) {
          // punto real sobre el tramo, redondeado a la cuadrícula a lo largo del eje
          let p = add(t.a, mul(sub(t.b, t.a), k));
          p = p.map((v, i) => (Math.abs(t.b[i] - t.a[i]) > 1 ? Math.round(v / est.paso) * est.paso : t.a[i]));
          p = proyectar(t, p).p;
          // trazando: si el pie de la perpendicular desde el último punto cae cerca, la tee va ahí (llegada recta)
          const ult = est.ruta && est.ruta.pts[est.ruta.pts.length - 1];
          if (ult) {
            const pie = proyectar(t, ult);
            const sp = escena.aPantalla(pie.p);
            if (pie.k > 0.02 && pie.k < 0.98 && Math.hypot(sp.x - mx, sp.y - my) < 40) p = pie.p;
          }
          mejor = { clase: 'tramo', t, p, d, txt: `Sobre ${TIPOS[t.tipo].nombre.toLowerCase()} ${rotulo(t)} · crea tee` };
        }
      }
    }
  }
  if (mejor) return mejor;

  // plano de trabajo (o montante si se mantiene Alt sobre el último punto)
  const ult = est.ruta && est.ruta.pts[est.ruta.pts.length - 1];
  let z = zTrabajo();
  if (ult && tipo === 'tuberia' && est.op.tuberia.pendiente > 0) z = ult[2];
  if (ult && ev.altKey) {
    const p = escena.rayoVertical(ndc, ult[0], ult[1]);
    if (p) return { clase: 'montante', p: [ult[0], ult[1], Math.round(p[2] / est.paso) * est.paso], txt: 'Montante' };
  }
  const p = escena.rayoPlano(ndc, z);
  if (!p) return null;
  const q = [Math.round(p[0] / est.paso) * est.paso, Math.round(p[1] / est.paso) * est.paso, z];
  if (ult && !ev.shiftKey) {
    // ortogonal: el eje dominante desde el último punto
    if (Math.abs(q[0] - ult[0]) >= Math.abs(q[1] - ult[1])) q[1] = ult[1]; else q[0] = ult[0];
  }
  if (ult && tipo === 'tuberia' && est.op.tuberia.pendiente > 0) {
    q[2] = Math.round((ult[2] - (Math.hypot(q[0] - ult[0], q[1] - ult[1]) * est.op.tuberia.pendiente) / 100) * 10) / 10;
  }
  return { clase: 'plano', p: q, txt: null };
}

// Camino ortogonal desde el último punto hasta el objetivo
function camino(ult, s) {
  const out = [];
  const pushU = (p) => { const prev = out.length ? out[out.length - 1] : ult; if (dist(prev, p) > 0.5) out.push(p); };
  if (s.clase === 'plano' || s.clase === 'montante') {
    if (Math.abs(s.p[2] - ult[2]) > 0.5 && !(est.herr === 'tuberia' && est.op.tuberia.pendiente > 0)) pushU([ult[0], ult[1], s.p[2]]);
    pushU(s.p);
    return out;
  }
  // a un conector se llega por su eje: punto de aproximación delante de la boquilla
  let obj = s.p;
  if (s.clase === 'conector') {
    const lado = s.c.dn ? 300 : Math.max(s.c.ancho || 0, s.c.alto || 0, 300);
    obj = add(s.c.pos, mul(s.c.dir, lado));
  }
  const pend = est.herr === 'tuberia' && est.op.tuberia.pendiente > 0;
  if (Math.abs(obj[0] - ult[0]) > 0.5 && Math.abs(obj[1] - ult[1]) > 0.5) pushU([obj[0], ult[1], ult[2]]);
  if (!pend) pushU([obj[0], obj[1], ult[2]]);
  pushU(obj);
  if (obj !== s.p) pushU(s.p);
  return out;
}

function propsRuta() {
  const t = est.herr, o = est.op[t];
  if (t === 'ducto') return o.forma === 'redondo' ? { tipo: t, sistema: o.sistema, forma: 'redondo', diam: o.diam } : { tipo: t, sistema: o.sistema, forma: 'rect', ancho: o.ancho, alto: o.alto };
  if (t === 'tuberia') return { tipo: t, sistema: o.sistema, dn: o.dn };
  return { tipo: t, sistema: o.sistema, ancho: o.ancho, alto: o.alto };
}

// adopta sistema y tamaño del objeto en el que empieza el trazado
function adoptar(s) {
  const o = est.op[est.herr];
  const src = s.clase === 'conector' ? s.c : s.t;
  if (src.sistema && SISTEMAS[src.sistema] && SISTEMAS[src.sistema].tipo === est.herr) o.sistema = src.sistema;
  if (est.herr === 'tuberia' && src.dn) o.dn = src.dn;
  if (est.herr === 'ducto') {
    if (src.forma === 'redondo') { o.forma = 'redondo'; o.diam = src.diam; } else if (src.ancho) { o.forma = 'rect'; o.ancho = src.ancho; o.alto = src.alto; }
  }
  if (est.herr === 'bandeja' && src.ancho) { o.ancho = src.ancho; o.alto = src.alto; }
  if (s.clase !== 'conector') o.desfase = Math.round(s.p[2] - nivelActivo().elev);
}

function clicTrazado(s) {
  if (!s) return;
  if (!est.ruta) {
    guardarPaso();
    if (s.clase !== 'plano' && s.clase !== 'montante') adoptar(s);
    if (s.clase === 'tramo') partirTramo(m, s.t, s.p);
    est.ruta = { pts: [s.p.map((v) => Math.round(v * 10) / 10)] };
    if (s.clase === 'conector') {
      const lado = s.c.dn ? 300 : Math.max(s.c.ancho || 0, s.c.alto || 0, 300);
      const a = add(s.c.pos, mul(s.c.dir, lado)).map((v) => Math.round(v * 10) / 10);
      m.elementos.push({ id: nuevoId(m, est.herr[0].toUpperCase()), ...propsRuta(), a: [...est.ruta.pts[0]], b: a });
      est.ruta.pts.push(a);
    }
    refrescar();
    return;
  }
  const ult = est.ruta.pts[est.ruta.pts.length - 1];
  const pts = camino(ult, s);
  if (!pts.length) return;
  if (s.clase === 'tramo') partirTramo(m, s.t, s.p);
  let prev = ult;
  for (const p of pts) {
    const q = p.map((v) => Math.round(v * 10) / 10);
    m.elementos.push({ id: nuevoId(m, est.herr[0].toUpperCase()), ...propsRuta(), a: [...prev], b: q });
    prev = q;
  }
  est.ruta.pts.push(...pts.map((p) => p.map((v) => Math.round(v * 10) / 10)));
  const fin = s.clase === 'conector' || s.clase === 'extremo' || s.clase === 'tramo';
  if (fin) terminarRuta();
  refrescar();
  if (fin) toast('Conectado');
}

function clicEquipo(s) {
  if (!s) return;
  const o = est.op.equipo;
  cambiar(() => {
    const eq = { id: nuevoId(m, 'E'), tipo: 'equipo', familia: o.familia, tag: siguienteTag(m, o.familia), pos: s.p, rot: o.rot,
      param: { ...(FAMILIAS[o.familia].param || {}) } };
    const tb = m.elementos.find((e) => e.tipo === 'equipo' && FAMILIAS[e.familia].tablero);
    if (tb && FAMILIAS[o.familia].conectores.some((c) => c.tipo === 'electrico')) eq.tablero = tb.id;
    m.elementos.push(eq);
    est.sel = eq.id;
  });
  toast(`${elemento(est.sel).tag} colocado`);
}

// ------------------------------------------------------------------ eventos del lienzo
const cv = escena.renderer.domElement;
let abajo = null;
cv.addEventListener('pointerdown', (ev) => { abajo = { x: ev.clientX, y: ev.clientY, b: ev.button }; });
cv.addEventListener('pointerup', (ev) => {
  if (!abajo || abajo.b !== 0 || Math.hypot(ev.clientX - abajo.x, ev.clientY - abajo.y) > 5) { abajo = null; return; }
  abajo = null;
  if (est.herr === 'seleccionar') {
    const hit = escena.elegir(escena.ndc(ev));
    seleccionar(hit ? hit.id : null);
  } else if (est.herr === 'equipo') {
    clicEquipo(est.snap);
  } else {
    clicTrazado(buscarSnap(ev));
  }
});
cv.addEventListener('dblclick', () => { if (est.ruta) { terminarRuta(); refrescar(); } });
cv.addEventListener('pointermove', (ev) => {
  const nd = escena.ndc(ev);
  const z = zTrabajo();
  const p = escena.rayoPlano(nd, z);
  if (p) $('#coord').textContent = `X ${f1(p[0] / 1000, 2)}  Y ${f1(p[1] / 1000, 2)}  Z ${f1(z / 1000, 2)} m`;
  if (est.herr === 'seleccionar') return;
  if (est.herr === 'equipo') {
    if (!p) return;
    const q = [Math.round(p[0] / est.paso) * est.paso, Math.round(p[1] / est.paso) * est.paso, z];
    est.snap = { p: q };
    escena.mostrarFantasma(est.op.equipo.familia, q, est.op.equipo.rot);
    return;
  }
  const s = buscarSnap(ev);
  est.snap = s;
  const tip = $('#snap');
  if (s && s.txt) {
    tip.hidden = false;
    tip.textContent = s.txt;
    const r = cv.getBoundingClientRect();
    tip.style.left = ev.clientX - r.left + 'px';
    tip.style.top = ev.clientY - r.top + 'px';
  } else tip.hidden = true;
  escena.ponerCursor(s && s.p);
  if (est.ruta && s) {
    const ult = est.ruta.pts[est.ruta.pts.length - 1];
    const pts = [ult, ...camino(ult, s)];
    const props = propsRuta();
    escena.mostrarPreview(pts.slice(1).map((b, i) => ({ ...props, a: pts[i], b })), SISTEMAS[props.sistema].color);
    const L = pts.slice(1).reduce((acc, b, i) => acc + dist(pts[i], b), 0);
    $('#coord').textContent += `   ·  tramo ${f1(L / 1000, 2)} m`;
  }
});
cv.addEventListener('pointerleave', () => { $('#snap').hidden = true; });
cv.addEventListener('contextmenu', (ev) => { if (est.ruta) { ev.preventDefault(); terminarRuta(); refrescar(); } });

function seleccionar(id) {
  est.sel = id;
  dibujar();
  pintarPropiedades();
  pintarTablas();
  pintarNavegador();
  $('#b-borrar').disabled = !id;
}

function eliminarSel() {
  if (!est.sel) return;
  const e = elemento(est.sel);
  cambiar(() => {
    m.elementos = m.elementos.filter((x) => x.id !== est.sel);
    if (e.tipo === 'equipo') for (const x of m.elementos) if (x.tablero === e.id) delete x.tablero;
    est.sel = null;
  });
  toast(`${e.tag || e.id} eliminado`);
}

document.addEventListener('keydown', (ev) => {
  const enCampo = ev.target.closest('input, select, textarea');
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'z') { if (!enCampo) { ev.preventDefault(); ev.shiftKey ? rehacer() : deshacer(); } return; }
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'y') { if (!enCampo) { ev.preventDefault(); rehacer(); } return; }
  if (enCampo || ev.ctrlKey || ev.metaKey || ev.altKey) return;
  const k = ev.key.toLowerCase();
  if (k === 'escape') {
    if (est.ruta) { terminarRuta(); refrescar(); } else if (est.herr !== 'seleccionar') setHerr('seleccionar'); else seleccionar(null);
  } else if (k === 'v') setHerr('seleccionar');
  else if (k === 'd') setHerr('ducto');
  else if (k === 'p') setHerr('tuberia');
  else if (k === 'b') setHerr('bandeja');
  else if (k === 'e') setHerr('equipo');
  else if (k === 'r' && est.herr === 'equipo') { est.op.equipo.rot = (est.op.equipo.rot + 90) % 360; pintarOpciones(); if (est.snap) escena.mostrarFantasma(est.op.equipo.familia, est.snap.p, est.op.equipo.rot); }
  else if (k === 'r' && est.sel && elemento(est.sel).tipo === 'equipo') cambiar(() => { const e = elemento(est.sel); e.rot = ((e.rot || 0) + 90) % 360; });
  else if (k === 'delete' || k === 'backspace' || k === 'supr') eliminarSel();
  else if (k === 'f') encuadrar();
  else if (k === '3') setVista('3d');
  else if (k === '2') setVista('planta');
  else if (k.startsWith('arrow') && est.sel && elemento(est.sel).tipo === 'equipo') {
    ev.preventDefault();
    const d = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, 1], arrowdown: [0, -1] }[k];
    cambiar(() => { const e = elemento(est.sel); e.pos = [e.pos[0] + d[0] * est.paso, e.pos[1] + d[1] * est.paso, e.pos[2]]; });
  }
});

function encuadrar(el) {
  const pts = [];
  const lista = el ? [el] : m.elementos;
  for (const e of lista) {
    if (esLineal(e)) pts.push(e.a, e.b);
    else if (e.tipo === 'equipo') { const b = cajaTotalEquipo(e); pts.push(b.min, b.max); }
  }
  if (!pts.length) pts.push([-5000, -5000, 0], [5000, 5000, 3000]);
  const min = [0, 1, 2].map((k) => Math.min(...pts.map((p) => p[k])));
  const max = [0, 1, 2].map((k) => Math.max(...pts.map((p) => p[k])));
  escena.encuadrar(min, max);
}

// ------------------------------------------------------------------ barra de opciones
function selectNum(id, valores, actual, fmt = (v) => v) {
  return h('select', { id }, valores.map((v) => h('option', { value: v, selected: Number(v) === Number(actual) }, fmt(v))));
}
function selectSistema(id, tipo, actual) {
  return h('select', { id }, sistemasDe(tipo).map((k) => h('option', { value: k, selected: k === actual }, `${k} · ${SISTEMAS[k].nombre}`)));
}

function pintarOpciones() {
  const box = $('#opciones');
  box.replaceChildren();
  const t = est.herr;
  const o = est.op[t];
  const nv = nivelActivo();
  const al = (fn) => (ev) => { fn(ev.target.value); pintarOpciones(); escena.grilla(zTrabajo(), 1000); };
  if (t === 'seleccionar') {
    box.append(h('span', { class: 'titulo' }, 'Modificar'),
      h('span', {}, est.sel ? `Seleccionado: ${(elemento(est.sel).tag || elemento(est.sel).id)}` : 'Nada seleccionado'),
      h('span', { class: 'chip' }, `Nivel activo · ${nv.nombre}`));
    return;
  }
  if (t === 'equipo') {
    const f = FAMILIAS[o.familia];
    box.append(h('span', { class: 'titulo' }, 'Colocar equipo'),
      h('label', {}, 'Familia', h('select', { id: 'op-fam', onchange: al((v) => { o.familia = v; o.desfase = null; $('#sel-familia').value = v; }) },
        Object.values(FAMILIAS).map((x) => h('option', { value: x.id, selected: x.id === o.familia }, x.nombre)))),
      h('label', {}, 'Rotación', h('select', { id: 'op-rot', onchange: al((v) => { o.rot = Number(v); }) }, [0, 90, 180, 270].map((r) => h('option', { value: r, selected: r === o.rot }, r + '°')))),
      h('label', {}, 'Desfase', h('input', { id: 'op-desf', type: 'number', step: 50, value: o.desfase ?? f.desfase, onchange: al((v) => { o.desfase = Number(v); }) }), 'mm'),
      h('span', { class: 'chip' }, `${f.conectores.length} conectores`));
    return;
  }
  box.append(h('span', { class: 'titulo' }, TIPOS[t].nombre),
    h('label', {}, 'Sistema', h('span', { class: 'sw', style: `background:${SISTEMAS[o.sistema].color}` }), selectSistema('op-sis', t, o.sistema)));
  box.querySelector('#op-sis').addEventListener('change', al((v) => { o.sistema = v; }));
  if (t === 'ducto') {
    box.append(h('label', {}, 'Forma', h('select', { id: 'op-forma', onchange: al((v) => { o.forma = v; }) },
      h('option', { value: 'rect', selected: o.forma === 'rect' }, 'Rectangular'), h('option', { value: 'redondo', selected: o.forma === 'redondo' }, 'Redondo'))));
    if (o.forma === 'rect') {
      box.append(h('label', {}, 'Ancho', selectNum('op-ancho', LADOS_DUCTO, o.ancho)), h('label', {}, 'Alto', selectNum('op-alto', LADOS_DUCTO, o.alto)));
      box.querySelector('#op-ancho').addEventListener('change', al((v) => { o.ancho = Number(v); }));
      box.querySelector('#op-alto').addEventListener('change', al((v) => { o.alto = Number(v); }));
    } else {
      box.append(h('label', {}, 'Diámetro', selectNum('op-diam', DIAM_DUCTO, o.diam)));
      box.querySelector('#op-diam').addEventListener('change', al((v) => { o.diam = Number(v); }));
    }
  } else if (t === 'tuberia') {
    box.append(h('label', {}, 'Diámetro', selectNum('op-dn', DNS, o.dn, (v) => 'DN' + v)));
    box.querySelector('#op-dn').addEventListener('change', al((v) => { o.dn = Number(v); }));
    box.append(h('label', {}, 'Pendiente', h('select', { id: 'op-pend', onchange: al((v) => { o.pendiente = Number(v); }) },
      [0, 0.5, 1, 1.5, 2, 3].map((p) => h('option', { value: p, selected: p === o.pendiente }, p ? p + ' %' : 'Sin pendiente')))));
  } else {
    box.append(h('label', {}, 'Ancho', selectNum('op-ancho', BANDEJA_ANCHOS, o.ancho)), h('label', {}, 'Alto', selectNum('op-alto', BANDEJA_ALTOS, o.alto)));
    box.querySelector('#op-ancho').addEventListener('change', al((v) => { o.ancho = Number(v); }));
    box.querySelector('#op-alto').addEventListener('change', al((v) => { o.alto = Number(v); }));
  }
  const desf = h('input', { id: 'op-desf', type: 'number', step: 50, value: o.desfase });
  desf.addEventListener('change', () => {
    const nuevo = Number(desf.value);
    // cambiar el desfase en mitad del trazado crea un montante desde el último punto
    if (est.ruta && !(t === 'tuberia' && o.pendiente > 0)) {
      const ult = est.ruta.pts[est.ruta.pts.length - 1];
      const z = nv.elev + nuevo;
      if (Math.abs(z - ult[2]) > 0.5) {
        const b = [ult[0], ult[1], z];
        m.elementos.push({ id: nuevoId(m, t[0].toUpperCase()), ...propsRuta(), a: [...ult], b });
        est.ruta.pts.push(b);
        o.desfase = nuevo;
        refrescar();
      }
    }
    o.desfase = nuevo;
    escena.grilla(zTrabajo(), 1000);
  });
  box.append(h('label', {}, 'Desfase', desf, 'mm'), h('span', { class: 'chip' }, `Plano a ${f1(zTrabajo() / 1000, 2)} m`));
  if (est.ruta) box.append(h('button', { class: 'btn', onclick: () => { terminarRuta(); refrescar(); } }, 'Terminar (Esc)'));
}

// ------------------------------------------------------------------ propiedades
function fila(k, v) { return [h('span', { class: 'k' }, k), v instanceof Node ? v : h('span', { class: 'v' }, v)]; }

function pintarPropiedades() {
  const box = $('#propiedades');
  box.replaceChildren();
  const e = est.sel && elemento(est.sel);
  if (!e) { pintarResumen(box); return; }
  if (esLineal(e)) propTramo(box, e); else propEquipo(box, e);
}

function pintarResumen(box) {
  const n = (tipo) => an.tramos.filter((t) => t.tipo === tipo).reduce((s, t) => s + longitud(t), 0) / 1000;
  const errores = avisos.filter((a) => a.nivel === 'error').length;
  const carga = electrico.resumen.reduce((s, r) => s + r.va, 0) / 1000;
  box.append(
    h('h2', {}, 'Proyecto'),
    h('div', { class: 'prop' }, fila('Nombre', h('input', { id: 'p-nombre', type: 'text', value: m.nombre, onchange: (ev) => cambiar(() => { m.nombre = ev.target.value; }) }))),
    h('div', { class: 'resumen' },
      h('div', {}, h('b', {}, f1(n('ducto'), 1)), h('span', {}, 'm de ducto')),
      h('div', {}, h('b', {}, f1(n('tuberia'), 1)), h('span', {}, 'm de tubería')),
      h('div', {}, h('b', {}, f1(n('bandeja'), 1)), h('span', {}, 'm de bandeja')),
      h('div', {}, h('b', {}, an.accesorios.length), h('span', {}, 'accesorios')),
      h('div', { class: choques.length ? 'mal' : '' }, h('b', {}, choques.length), h('span', {}, 'interferencias')),
      h('div', { class: errores ? 'mal' : avisos.length ? 'alerta' : '' }, h('b', {}, avisos.length), h('span', {}, 'advertencias')),
      h('div', {}, h('b', {}, m.elementos.filter((x) => x.tipo === 'equipo').length), h('span', {}, 'equipos')),
      h('div', {}, h('b', {}, f1(carga, 1)), h('span', {}, 'kVA conectados'))),
    h('p', { class: 'nota' }, 'Selecciona un tramo o un equipo para ver y cambiar sus propiedades. Los accesorios (codos, tees, reducciones) se generan solos donde se unen los tramos.'),
  );
}

function propTramo(box, t) {
  const sis = SISTEMAS[t.sistema];
  const q = an.caudal[t.id];
  const hid = hidraulica(t, q);
  const uq = t.tipo === 'ducto' ? 'm³/h' : 'L/s';
  const set = (fn) => (ev) => cambiar(() => fn(ev.target.value));
  const tam = [];
  if (t.tipo === 'tuberia') tam.push(...fila('Diámetro', selectNum('p-dn', DNS, t.dn, (v) => 'DN' + v)));
  else if (t.tipo === 'ducto' && t.forma === 'redondo') tam.push(...fila('Diámetro', selectNum('p-diam', DIAM_DUCTO, t.diam)));
  else {
    const anchos = t.tipo === 'bandeja' ? BANDEJA_ANCHOS : LADOS_DUCTO, altos = t.tipo === 'bandeja' ? BANDEJA_ALTOS : LADOS_DUCTO;
    tam.push(...fila('Ancho', selectNum('p-ancho', anchos, t.ancho)), ...fila('Alto', selectNum('p-alto', altos, t.alto)));
  }
  const nv = nivelDe(m, Math.min(t.a[2], t.b[2]));
  const prop = h('div', { class: 'prop' },
    ...fila('Sistema', selectSistema('p-sis', t.tipo, t.sistema)),
    ...tam,
    h('div', { class: 'sep' }),
    ...fila('Longitud', `${f1(longitud(t) / 1000, 2)} m`),
    ...fila('Nivel', nv.nombre),
    ...fila('Desfase inicio', `${f1(t.a[2] - nv.elev, 0)} mm`),
    ...fila('Desfase fin', `${f1(t.b[2] - nv.elev, 0)} mm`),
    ...(sis.calc === 'gravedad' ? fila('Pendiente', `${f1(pendiente(t), 2)} %`) : []),
    ...(t.tipo !== 'bandeja' ? [h('div', { class: 'sep' }),
      ...fila(`Caudal (${uq})`, h('input', { id: 'p-caudal', type: 'number', step: t.tipo === 'ducto' ? 50 : 0.1, value: t.caudal > 0 ? t.caudal : '', placeholder: q ? f1(q, t.tipo === 'ducto' ? 0 : 2) + ' (calc.)' : 'sin dato' })),
      ...fila('Velocidad', hid ? `${f1(hid.v, 2)} m/s` : '—'),
      ...fila('Pérdida', hid ? `${f1(hid.dp, t.tipo === 'ducto' ? 2 : 0)} Pa/m` : '—'),
      ...fila('ΔP del tramo', an.perdida[t.id] ? `${f1(an.perdida[t.id], 1)} Pa` : '—')] : []),
  );
  prop.querySelector('#p-sis').addEventListener('change', set((v) => { t.sistema = v; }));
  for (const [id, k] of [['p-dn', 'dn'], ['p-diam', 'diam'], ['p-ancho', 'ancho'], ['p-alto', 'alto']]) {
    const el = prop.querySelector('#' + id);
    if (el) el.addEventListener('change', set((v) => { t[k] = Number(v); }));
  }
  const ic = prop.querySelector('#p-caudal');
  if (ic) ic.addEventListener('change', set((v) => { if (Number(v) > 0) t.caudal = Number(v); else delete t.caudal; }));
  const sug = sis.calc && sis.calc !== 'gravedad' && q > 0 ? dimensionar(t, q) : null;
  const sugTxt = sug ? rotulo({ ...t, ...sug }) : null;
  box.append(
    h('div', { class: 'tipo-sel' }, h('div', { class: 'ic' }, h('span', { class: 'sw', style: `background:${sis.color};width:18px;height:18px` })),
      h('div', {}, h('strong', {}, `${TIPOS[t.tipo].nombre} ${rotulo(t)}`), h('span', {}, `${t.id} · ${sis.nombre}`))),
    prop,
    h('div', { class: 'acciones' },
      sug && sugTxt !== rotulo(t) ? h('button', { class: 'btn pri', onclick: () => cambiar(() => Object.assign(t, sug)) }, `Dimensionar a ${sugTxt}`) : null,
      h('button', { class: 'btn', onclick: () => encuadrar(t) }, 'Acercar'),
      h('button', { class: 'btn peligro', onclick: eliminarSel }, 'Eliminar')),
    sug && sugTxt === rotulo(t) ? h('p', { class: 'nota' }, 'El tamaño cumple el criterio de velocidad y pérdida por fricción.') : null,
  );
}

function propEquipo(box, e) {
  const f = familia(e);
  const nv = nivelDe(m, e.pos[2]);
  const tableros = m.elementos.filter((x) => x.tipo === 'equipo' && FAMILIAS[x.familia].tablero);
  const conns = conectoresEquipo(e);
  const tieneEl = conns.some((c) => c.tipo === 'electrico');
  const num = (id, v, step = 50) => h('input', { id, type: 'number', step, value: Math.round(v) });
  const prop = h('div', { class: 'prop' },
    ...fila('Marca (tag)', h('input', { id: 'p-tag', type: 'text', value: e.tag })),
    ...fila('Familia', f.nombre),
    ...(f.fabricante ? fila('Fabricante', f.fabricante) : []),
    ...(f.peso_kg ? fila('Peso', `${f1(f.peso_kg, 0)} kg`) : []),
    h('div', { class: 'sep' }),
    ...fila('X (mm)', num('p-x', e.pos[0])),
    ...fila('Y (mm)', num('p-y', e.pos[1])),
    ...fila(`Desfase (mm)`, num('p-z', e.pos[2] - nv.elev)),
    ...fila('Rotación', h('select', { id: 'p-rot' }, [0, 90, 180, 270].map((r) => h('option', { value: r, selected: r === (e.rot || 0) }, r + '°')))),
    ...fila('Nivel', nv.nombre),
    ...(e.param && 'sistema' in e.param ? fila('Sistema', selectSistema('p-psis', 'tuberia', e.param.sistema)) : []),
    ...(e.param && 'caudal' in e.param ? fila('Caudal (m³/h)', num('p-pcaudal', e.param.caudal, 50)) : []),
    ...(tieneEl ? fila('Tablero', h('select', { id: 'p-tab' }, h('option', { value: '' }, '— sin asignar —'),
      tableros.filter((t) => t.id !== e.id).map((t) => h('option', { value: t.id, selected: t.id === e.tablero }, t.tag)))) : []),
  );
  const set = (id, fn) => { const el = prop.querySelector('#' + id); if (el) el.addEventListener('change', (ev) => cambiar(() => fn(ev.target.value))); };
  set('p-tag', (v) => { e.tag = v.trim() || e.tag; });
  set('p-x', (v) => { e.pos = [Number(v), e.pos[1], e.pos[2]]; });
  set('p-y', (v) => { e.pos = [e.pos[0], Number(v), e.pos[2]]; });
  set('p-z', (v) => { e.pos = [e.pos[0], e.pos[1], nv.elev + Number(v)]; });
  set('p-rot', (v) => { e.rot = Number(v); });
  set('p-psis', (v) => { e.param.sistema = v; });
  set('p-pcaudal', (v) => { e.param.caudal = Number(v); });
  set('p-tab', (v) => { if (v) e.tablero = v; else delete e.tablero; });

  const lista = h('ul', { class: 'conectores' }, conns.map((c) => {
    const conectado = c.tipo === 'electrico' ? Boolean(e.tablero) : an.conectores.some((x) => x.equipo === e.id && x.id === c.id && an.nudos[x._nudo] && an.nudos[x._nudo].tramos.length);
    const tam = c.tipo === 'electrico' ? `${c.kw} kW · ${c.tension} V` : c.dn ? 'DN' + c.dn : `${c.ancho}×${c.alto}`;
    return h('li', {}, h('span', { class: 'sw', style: `background:${c.tipo === 'electrico' ? '#e5b400' : SISTEMAS[c.sistema].color}` }),
      h('span', {}, `${c.id} ${c.nombre}`), h('span', { class: 'v', style: 'color:var(--muted)' }, tam),
      h('span', { class: 'est ' + (conectado ? 'ok' : 'no') }, conectado ? (c.tipo === 'electrico' ? 'circuito' : 'conectado') : 'libre'));
  }));
  box.append(
    h('div', { class: 'tipo-sel' }, h('div', { class: 'ic', style: 'font-family:var(--font-num);font-size:11px;font-weight:600' }, f.prefijo),
      h('div', {}, h('strong', {}, e.tag), h('span', {}, f.categoria))),
    prop,
    h('h2', {}, 'Conectores'),
    lista,
    f.descripcion ? h('p', { class: 'nota' }, f.descripcion) : null,
    h('div', { class: 'acciones' },
      h('button', { class: 'btn', onclick: () => cambiar(() => { e.rot = ((e.rot || 0) + 90) % 360; }) }, 'Girar 90°'),
      h('button', { class: 'btn', onclick: () => encuadrar(e) }, 'Acercar'),
      h('button', { class: 'btn peligro', onclick: eliminarSel }, 'Eliminar')),
  );
}

// ------------------------------------------------------------------ navegador
function pintarNavegador() {
  const vistas = $('#arbol-vistas');
  vistas.replaceChildren(
    h('li', {}, h('button', { 'aria-current': String(est.vista === '3d'), onclick: () => setVista('3d') }, 'Vista 3D')),
    ...m.niveles.slice().sort((a, b) => a.elev - b.elev).map((n) => h('li', {}, h('button', {
      'aria-current': String(est.vista === 'planta' && est.nivel === n.id), onclick: () => { setNivel(n.id); setVista('planta'); },
    }, `Planta · ${n.nombre.split('·')[0].trim()}`))),
  );
  $('#arbol-niveles').replaceChildren(...m.niveles.slice().sort((a, b) => b.elev - a.elev).map((n) => h('li', {}, h('button', {
    'aria-current': String(est.nivel === n.id), onclick: () => setNivel(n.id), title: 'Activar como plano de trabajo',
  }, n.nombre, h('span', { class: 'n' }, `${n.elev >= 0 ? '+' : ''}${f1(n.elev / 1000, 2)}`)))));
  const cuenta = {};
  for (const t of an.tramos) cuenta[t.sistema] = (cuenta[t.sistema] || 0) + 1;
  $('#arbol-sistemas').replaceChildren(...Object.keys(SISTEMAS).filter((k) => cuenta[k]).map((k) => h('li', {}, h('label', {},
    h('input', { type: 'checkbox', id: 'vis-' + k, checked: !est.ocultos.has(k), onchange: (ev) => { ev.target.checked ? est.ocultos.delete(k) : est.ocultos.add(k); dibujar(); } }),
    h('span', { class: 'sw', style: `background:${SISTEMAS[k].color}` }), SISTEMAS[k].nombre, h('span', { class: 'n' }, cuenta[k])))));
  $('#arbol-equipos').replaceChildren(...m.elementos.filter((e) => e.tipo === 'equipo').sort((a, b) => a.tag.localeCompare(b.tag)).map((e) => h('li', {},
    h('button', { 'aria-current': String(est.sel === e.id), onclick: () => seleccionar(e.id), ondblclick: () => encuadrar(e) }, e.tag,
      h('span', { class: 'n' }, FAMILIAS[e.familia].prefijo)))));
}

$('#b-nivel').addEventListener('click', () => { const f = $('#form-nivel'); f.hidden = !f.hidden; if (!f.hidden) $('#nivel-nombre').focus(); });
$('#form-nivel').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const nombre = $('#nivel-nombre').value.trim(), elev = Number($('#nivel-elev').value);
  if (!nombre || Number.isNaN(elev) || $('#nivel-elev').value === '') { toast('Escribe un nombre y una elevación en mm'); return; }
  cambiar(() => { const id = nuevoId(m, 'N'); m.niveles.push({ id, nombre, elev }); est.nivel = id; });
  $('#form-nivel').hidden = true;
  $('#nivel-nombre').value = ''; $('#nivel-elev').value = '';
  setNivel(est.nivel);
});

// ------------------------------------------------------------------ tablas
const TABLAS = [
  ['ductos', 'Ductos'], ['tuberias', 'Tuberías'], ['bandejas', 'Bandejas'], ['accesorios', 'Accesorios'], ['equipos', 'Equipos'],
  ['redes', 'Redes'], ['cargas', 'Cargas eléctricas'], ['interf', 'Interferencias'], ['avisos', 'Advertencias'],
];
let tablaActual = { cab: [], filas: [] };

function datosTabla(k) {
  const sw = (s) => h('span', { style: 'display:inline-flex;gap:6px;align-items:center' }, h('span', { class: 'sw', style: `background:${SISTEMAS[s].color}` }), SISTEMAS[s].nombre);
  if (k === 'ductos' || k === 'tuberias' || k === 'bandejas') {
    const tipo = { ductos: 'ducto', tuberias: 'tuberia', bandejas: 'bandeja' }[k];
    const ts = an.tramos.filter((t) => t.tipo === tipo).sort((a, b) => a.sistema.localeCompare(b.sistema) || rotulo(a).localeCompare(rotulo(b), 'es', { numeric: true }));
    const uq = tipo === 'ducto' ? 'm³/h' : 'L/s';
    const cab = ['ID', 'Sistema', 'Tamaño', 'Longitud m', ...(tipo === 'bandeja' ? [] : [`Caudal ${uq}`, 'Velocidad m/s', 'Pérdida Pa/m', 'ΔP tramo Pa']), ...(tipo === 'tuberia' ? ['Pendiente %'] : [])];
    const filas = ts.map((t) => {
      const hd = hidraulica(t, an.caudal[t.id]);
      const vmal = hd && hd.v > hd.fl.vmax;
      return { id: t.id, celdas: [t.id, sw(t.sistema), rotulo(t), f1(longitud(t) / 1000, 2),
        ...(tipo === 'bandeja' ? [] : [an.caudal[t.id] ? f1(an.caudal[t.id], tipo === 'ducto' ? 0 : 2) : '—',
          hd ? (vmal ? h('span', { class: 'pill aviso' }, f1(hd.v, 2)) : f1(hd.v, 2)) : '—', hd ? f1(hd.dp, tipo === 'ducto' ? 2 : 0) : '—',
          an.perdida[t.id] ? f1(an.perdida[t.id], 1) : '—']),
        ...(tipo === 'tuberia' ? [SISTEMAS[t.sistema].calc === 'gravedad' ? f1(pendiente(t), 2) : '—'] : [])],
        csv: [t.id, t.sistema, rotulo(t), (longitud(t) / 1000).toFixed(3), ...(tipo === 'bandeja' ? [] : [an.caudal[t.id] || '', hd ? hd.v.toFixed(2) : '', hd ? hd.dp.toFixed(3) : '', (an.perdida[t.id] || 0).toFixed(2)])] };
    });
    const total = ts.reduce((s, t) => s + longitud(t), 0) / 1000;
    return { cab, filas, num: [3, 4, 5, 6, 7, 8], pie: ['Total', `${ts.length} tramos`, '', f1(total, 2)] };
  }
  if (k === 'accesorios') {
    const g = new Map();
    for (const a of an.accesorios) {
      const key = [a.clase, a.tipo, a.sistema, rotulo(a.t), a.angulo ?? ''].join('|');
      if (!g.has(key)) g.set(key, { a, n: 0, ids: [] });
      g.get(key).n++; g.get(key).ids.push(a.t.id);
    }
    const NOM = { codo: 'Codo', tee: 'Tee', cruz: 'Cruz', reduccion: 'Reducción' };
    const filas = [...g.values()].sort((x, y) => x.a.clase.localeCompare(y.a.clase) || x.a.tipo.localeCompare(y.a.tipo)).map(({ a, n, ids }) => ({
      id: ids[0], celdas: [TIPOS[a.clase].nombre, NOM[a.tipo] + (a.angulo && a.tipo === 'codo' ? ` ${a.angulo}°` : ''), sw(a.sistema), rotulo(a.t), n],
      csv: [a.clase, a.tipo, a.angulo ?? '', a.sistema, rotulo(a.t), n],
    }));
    return { cab: ['Clase', 'Accesorio', 'Sistema', 'Tamaño mayor', 'Cantidad'], filas, num: [4], pie: ['Total', '', '', '', an.accesorios.length] };
  }
  if (k === 'equipos') {
    const es = m.elementos.filter((e) => e.tipo === 'equipo').sort((a, b) => a.tag.localeCompare(b.tag));
    const filas = es.map((e) => {
      const cs = conectoresEquipo(e).filter((c) => c.tipo !== 'electrico');
      const ok = cs.filter((c) => an.conectores.some((x) => x.equipo === e.id && x.id === c.id && an.nudos[x._nudo] && an.nudos[x._nudo].tramos.length)).length;
      const tb = e.tablero && elemento(e.tablero);
      const kw = conectoresEquipo(e).filter((c) => c.tipo === 'electrico').reduce((s, c) => s + c.kw, 0);
      return { id: e.id, celdas: [e.tag, FAMILIAS[e.familia].nombre, nivelDe(m, e.pos[2]).nombre, f1(e.pos[0] / 1000, 2), f1(e.pos[1] / 1000, 2), f1(e.pos[2] / 1000, 2),
        cs.length ? h('span', { class: 'pill ' + (ok === cs.length ? 'ok' : 'aviso') }, `${ok}/${cs.length}`) : '—', kw ? f1(kw, 1) : '—', tb ? tb.tag : '—'],
        csv: [e.tag, FAMILIAS[e.familia].nombre, e.pos[0], e.pos[1], e.pos[2], `${ok}/${cs.length}`, kw, tb ? tb.tag : ''] };
    });
    return { cab: ['Tag', 'Familia', 'Nivel', 'X m', 'Y m', 'Z m', 'Conexiones', 'kW', 'Tablero'], filas, num: [3, 4, 5, 7] };
  }
  if (k === 'redes') {
    const filas = an.redes.filter((r) => r.tipo !== 'bandeja').sort((a, b) => a.sistema.localeCompare(b.sistema)).map((r) => {
      const fuente = r.fuente ? `${elemento(r.fuente.equipo).tag} · ${r.fuente.id}` : 'sin fuente';
      const uq = r.tipo === 'ducto' ? 'm³/h' : 'L/s';
      return { id: r.tramos[0].id, celdas: [sw(r.sistema), fuente, r.tramos.length, f1(r.longitud / 1000, 1), r.caudalTotal ? `${f1(r.caudalTotal, r.tipo === 'ducto' ? 0 : 2)} ${uq}` : '—',
        r.terminales, r.dpCritico ? f1(r.dpCritico, 0) : '—'],
        csv: [r.sistema, fuente, r.tramos.length, (r.longitud / 1000).toFixed(2), r.caudalTotal, r.terminales, r.dpCritico.toFixed(1)] };
    });
    return { cab: ['Sistema', 'Fuente', 'Tramos', 'Longitud m', 'Caudal', 'Terminales', 'ΔP ruta crítica Pa'], filas, num: [2, 3, 4, 5, 6] };
  }
  if (k === 'cargas') {
    const filas = [];
    for (const r of electrico.resumen) {
      r.circuitos.forEach((c, i) => filas.push({ id: c.equipo.id, celdas: [r.tablero.tag, i + 1, c.equipo.tag, c.conector.nombre, f1(c.conector.kw, 1), f1(c.conector.va / 1000, 1),
        `${c.conector.tension} V ${c.conector.polos}F`, f1(c.i, 1), c.breaker ? `${c.breaker} A` : '—'],
        csv: [r.tablero.tag, i + 1, c.equipo.tag, c.conector.nombre, c.conector.kw, c.conector.va, c.conector.tension, c.conector.polos, c.i.toFixed(1), c.breaker] }));
      filas.push({ id: r.tablero.id, total: true, celdas: [h('b', {}, `${r.tablero.tag} total`), '', '', 'Principal', h('b', {}, f1(r.kw, 1)), h('b', {}, f1(r.va / 1000, 1)), `${r.tension} V 3F`, h('b', {}, f1(r.i, 1)), r.principal ? h('b', {}, `${r.principal} A`) : '—'],
        csv: [r.tablero.tag, 'total', '', '', r.kw, r.va, r.tension, 3, r.i.toFixed(1), r.principal] });
    }
    for (const c of electrico.sinTablero) filas.push({ id: c.equipo.id, celdas: [h('span', { class: 'pill aviso' }, 'sin tablero'), '', c.equipo.tag, c.conector.nombre, f1(c.conector.kw, 1), f1(c.conector.va / 1000, 1), `${c.conector.tension} V`, f1(c.i, 1), '—'], csv: ['', '', c.equipo.tag, c.conector.nombre, c.conector.kw, c.conector.va, c.conector.tension, c.conector.polos, c.i.toFixed(1), ''] });
    return { cab: ['Tablero', 'Circ.', 'Equipo', 'Carga', 'kW', 'kVA', 'Tensión', 'I (A)', 'Protección'], filas, num: [1, 4, 5, 7] };
  }
  if (k === 'interf') {
    const nom = (e) => (e.tipo === 'equipo' ? e.tag : `${e.id} ${SISTEMAS[e.sistema].nombre} ${rotulo(e)}`);
    const filas = choques.map((c, i) => ({ id: c.a.id, foco: c, celdas: [i + 1, nom(c.a), nom(c.b), `${f1(c.p[0] / 1000, 2)}, ${f1(c.p[1] / 1000, 2)}, ${f1(c.p[2] / 1000, 2)}`],
      csv: [i + 1, nom(c.a), nom(c.b), ...c.p.map((v) => (v / 1000).toFixed(3))] }));
    return { cab: ['#', 'Elemento A', 'Elemento B', 'Ubicación X, Y, Z (m)'], filas, num: [0] };
  }
  const filas = avisos.map((a) => ({ id: a.el && a.el.id, celdas: [h('span', { class: 'pill ' + a.nivel }, a.nivel), a.txt], csv: [a.nivel, a.txt] }));
  return { cab: ['Nivel', 'Descripción'], filas };
}

function pintarTablas() {
  const cab = $('#tablas-cab');
  const n = { interf: choques.length, avisos: avisos.length };
  cab.replaceChildren(...TABLAS.map(([k, nombre]) => h('button', {
    class: 't', role: 'tab', 'aria-selected': String(est.tabla === k), onclick: () => { est.tabla = k; $('#tablas').classList.remove('cerrado'); pintarTablas(); },
  }, nombre, n[k] !== undefined ? h('span', { class: 'badge ' + (n[k] ? (k === 'interf' || avisos.some((a) => a.nivel === 'error') ? 'err' : 'warn') : '') }, n[k]) : null)),
  h('div', { class: 'der' }, h('button', { class: 'btn', onclick: () => $('#tablas').classList.toggle('cerrado') }, 'Ocultar / mostrar')));
  const d = datosTabla(est.tabla);
  tablaActual = d;
  const box = $('#contenido-tabla');
  if (!d.filas.length) {
    const vacio = { interf: 'Sin interferencias entre tramos ni con equipos.', avisos: 'Sin advertencias.', cargas: 'Coloca un tablero (familia TD) y asígnalo a los equipos para ver sus cargas.' }[est.tabla]
      || 'No hay elementos de este tipo todavía. Usa las herramientas de la pestaña Sistemas para trazarlos.';
    box.replaceChildren(h('p', { class: 'vacio' }, vacio));
    return;
  }
  const num = new Set(d.num || []);
  box.replaceChildren(h('table', {},
    h('thead', {}, h('tr', {}, d.cab.map((c, i) => h('th', { class: num.has(i) ? 'num' : null }, c)))),
    h('tbody', {}, d.filas.map((f) => h('tr', {
      'aria-selected': String(Boolean(f.id) && f.id === est.sel),
      onclick: () => { if (!f.id) return; seleccionar(f.id); const el = elemento(f.id); if (f.foco) escena.encuadrar(f.foco.p.map((v) => v - 2500), f.foco.p.map((v) => v + 2500)); else if (el) encuadrar(el); },
    }, f.celdas.map((c, i) => h('td', { class: num.has(i) ? 'num' : null }, c))))),
    d.pie ? h('tfoot', {}, h('tr', {}, d.pie.map((c, i) => h('td', { class: num.has(i) ? 'num' : null }, c)), ...Array(Math.max(0, d.cab.length - d.pie.length)).fill(0).map(() => h('td', {})))) : null,
  ));
}

function pintarHud() {
  const n = nivelActivo();
  $('#hud').replaceChildren(
    h('span', { class: 'chip' }, est.vista === '3d' ? 'Vista 3D' : `Planta · ${n.nombre}`),
    choques.length ? h('span', { class: 'chip', style: 'color:var(--err)' }, `${choques.length} interferencia${choques.length > 1 ? 's' : ''}`) : null,
    an.abiertos.filter((a) => a.t.tipo !== 'bandeja').length ? h('span', { class: 'chip', style: 'color:var(--warn)' }, `${an.abiertos.filter((a) => a.t.tipo !== 'bandeja').length} extremos abiertos`) : null,
  );
  $('#estado-der').textContent = `${an.tramos.length} tramos · ${an.accesorios.length} accesorios · ${m.elementos.filter((e) => e.tipo === 'equipo').length} equipos`;
}

// ------------------------------------------------------------------ archivo
async function descargar(nombre, datos, tipo) {
  try {
    const cl = window.claude && (await window.claude.use('downloads'));
    if (cl) {
      await cl.save({ filename: nombre, data: datos instanceof Uint8Array ? new Blob([datos], { type: tipo }) : new Blob([datos], { type: tipo }) });
      toast(`${nombre} listo`);
      return;
    }
  } catch (err) {
    if (err && err.code === 'declined') return;
    if (err && err.code && err.code !== 'unavailable' && err.code !== 'not_granted') { toast(`No se pudo guardar ${nombre}: ${err.message || err.code}`); return; }
  }
  const url = URL.createObjectURL(new Blob([datos], { type: tipo }));
  const a = h('a', { href: url, download: nombre });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  toast(`${nombre} descargado`);
}
const base = () => (m.nombre || 'modelo').replace(/[^\w-]+/g, '_');

$('#b-guardar').addEventListener('click', () => descargar(base() + '.pactmep.json', JSON.stringify(m, null, 1), 'application/json'));
$('#b-ifc').addEventListener('click', () => {
  const ifc = exportarIFC(m, an);
  descargar(base() + '.ifc.zip', zip([{ nombre: ifc.nombre, datos: ifc.texto }]), 'application/zip');
});
$('#b-csv').addEventListener('click', () => {
  const esc = (v) => { const s = String(v ?? ''); return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const txt = [tablaActual.cab, ...tablaActual.filas.map((f) => f.csv || [])].map((r) => r.map(esc).join(';')).join('\n');
  descargar(`${base()}_${est.tabla}.csv`, '﻿' + txt, 'text/csv');
});
$('#b-png').addEventListener('click', async () => {
  const b = await (await fetch(escena.captura())).blob();
  descargar(base() + '.png', new Uint8Array(await b.arrayBuffer()), 'image/png');
});
$('#b-abrir').addEventListener('click', () => $('#f-abrir').click());
$('#f-abrir').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  try {
    const d = JSON.parse(await f.text());
    if (!d.elementos || !d.niveles) throw new Error('faltan niveles o elementos');
    const desconocida = d.elementos.find((e) => e.tipo === 'equipo' && !FAMILIAS[e.familia]);
    if (desconocida) throw new Error(`la familia ${desconocida.familia} no está en el catálogo`);
    cambiar(() => { m = d; est.sel = null; est.nivel = m.niveles[0].id; });
    encuadrar();
    toast(`${f.name} abierto`);
  } catch (err) { toast(`No se pudo abrir ${f.name}: ${err.message}`); }
  ev.target.value = '';
});

function confirmar(texto, accion, etiqueta) {
  const prev = document.querySelector('.aviso-barra');
  if (prev) prev.remove();
  const bar = h('div', { class: 'aviso-barra', role: 'alertdialog' }, texto,
    h('button', { class: 'btn', onclick: () => { bar.remove(); accion(); } }, etiqueta),
    h('button', { class: 'btn', onclick: () => bar.remove() }, 'Cancelar'));
  $('#lienzo').append(bar);
}
$('#b-nuevo').addEventListener('click', () => confirmar('Se vacía el modelo actual (Deshacer lo recupera).', () => {
  cambiar(() => { m = modeloVacio(); est.sel = null; est.nivel = 'N1'; });
  setNivel('N1');
  encuadrar();
}, 'Vaciar modelo'));
$('#b-ejemplo').addEventListener('click', () => confirmar('Se reemplaza el modelo por el ejemplo de la sala de peletizado.', () => {
  cambiar(() => { m = crearEjemplo(); est.sel = null; est.nivel = 'N1'; });
  setNivel('N1');
  encuadrar();
}, 'Cargar ejemplo'));

// ------------------------------------------------------------------ análisis
$('#b-dimensionar').addEventListener('click', () => {
  const sel = est.sel && elemento(est.sel);
  const sistema = sel && esLineal(sel) ? sel.sistema : null;
  let n = 0;
  cambiar(() => {
    for (const t of m.elementos.filter(esLineal)) {
      if (sistema && t.sistema !== sistema) continue;
      const q = an.caudal[t.id];
      const r = q > 0 ? dimensionar(t, q) : null;
      if (r && rotulo({ ...t, ...r }) !== rotulo(t)) { Object.assign(t, r); n++; }
    }
  });
  toast(n ? `${n} tramos redimensionados${sistema ? ' en ' + SISTEMAS[sistema].nombre : ''}` : 'Todos los tramos con caudal ya cumplen el criterio');
});
const verTabla = (k) => () => { est.tabla = k; $('#tablas').classList.remove('cerrado'); pintarTablas(); };
$('#b-interf').addEventListener('click', verTabla('interf'));
$('#b-avisos').addEventListener('click', verTabla('avisos'));
$('#b-sistemas').addEventListener('click', verTabla('redes'));
$('#b-cargas').addEventListener('click', verTabla('cargas'));

// ------------------------------------------------------------------ cinta
document.querySelectorAll('.pestanas [role="tab"]').forEach((b) => b.addEventListener('click', () => {
  document.querySelectorAll('.pestanas [role="tab"]').forEach((x) => {
    x.setAttribute('aria-selected', String(x === b));
    $('#' + x.getAttribute('aria-controls')).hidden = x !== b;
  });
}));
document.querySelectorAll('[data-herr]').forEach((b) => b.addEventListener('click', () => setHerr(b.dataset.herr)));
document.querySelectorAll('[data-vista]').forEach((b) => b.addEventListener('click', () => setVista(b.dataset.vista)));
$('#b-deshacer').addEventListener('click', deshacer);
$('#b-rehacer').addEventListener('click', rehacer);
$('#b-borrar').addEventListener('click', eliminarSel);
$('#b-encuadrar').addEventListener('click', () => encuadrar());
$('#b-etiquetas').addEventListener('click', (ev) => { est.etiquetas = !est.etiquetas; ev.currentTarget.setAttribute('aria-pressed', String(est.etiquetas)); dibujar(); });
$('#b-conectores').addEventListener('click', (ev) => { est.conectores = !est.conectores; ev.currentTarget.setAttribute('aria-pressed', String(est.conectores)); dibujar(); });
$('#sel-paso').addEventListener('change', (ev) => { est.paso = Number(ev.target.value); });
const selFam = $('#sel-familia');
selFam.replaceChildren(...Object.values(FAMILIAS).map((f) => h('option', { value: f.id }, f.nombre)));
selFam.value = est.op.equipo.familia;
selFam.addEventListener('change', () => { est.op.equipo.familia = selFam.value; est.op.equipo.desfase = null; setHerr('equipo'); });

// brújula: el norte (+Y del proyecto) proyectado en pantalla
(function brujula() {
  const t = est.vista === '3d' ? escena.ctrl3d.target : escena.ctrlPlanta.target;
  const o = [t.x * 1000, t.y * 1000, t.z * 1000];
  const a = escena.aPantalla(o), b = escena.aPantalla([o[0], o[1] + 1000, o[2]]);
  const ang = Math.atan2(b.x - a.x, a.y - b.y);
  $('#brujula-n').setAttribute('transform', `rotate(${(ang * 180) / Math.PI} 23 23)`);
  requestAnimationFrame(brujula);
}());

let toastT;
function toast(txt) {
  let t = document.querySelector('.toast');
  if (!t) { t = h('div', { class: 'toast', role: 'status' }); $('#lienzo').append(t); }
  t.textContent = txt;
  clearTimeout(toastT);
  toastT = setTimeout(() => t.remove(), 2600);
}

// ------------------------------------------------------------------ arranque
refrescar({ redibujar: false });
aplicarTema();
setHerr('seleccionar');
setVista('3d');
encuadrar();

// acceso para pruebas automáticas y depuración desde la consola
window.pactMep = { escena, est, get modelo() { return m; }, get analisis() { return an; } };
