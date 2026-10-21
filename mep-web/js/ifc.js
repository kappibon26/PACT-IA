// Exportación IFC4 (STEP físico) y empaquetado ZIP sin compresión.
// Tramos -> IfcDuctSegment / IfcPipeSegment / IfcCableCarrierSegment con sólido extruido;
// accesorios -> IfcDuctFitting / IfcPipeFitting / IfcCableCarrierFitting; equipos -> su clase IFC con
// los prismas de la familia; un IfcDistributionSystem por sistema y un Pset_PACT_MEP por elemento.
import { FAMILIAS, SISTEMAS } from './catalogo.js';
import { ejesTramo, longitud, rotulo, seccion } from './modelo.js';

const B64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$';

export function guid() {
  const b = new Uint8Array(16);
  globalThis.crypto.getRandomValues(b);
  // 128 bits -> 22 caracteres: 2 bits + 21 × 6 bits
  let n = 0n;
  for (const x of b) n = (n << 8n) | BigInt(x);
  let s = '';
  for (let i = 0; i < 22; i++) { s = B64[Number(n & 63n)] + s; n >>= 6n; }
  return s;
}

// Cadena STEP: escapa comillas y barras, y codifica lo no ASCII con \X2\...\X0\
export function str(s) {
  if (s === null || s === undefined) return '$';
  let out = '';
  for (const ch of String(s)) {
    const c = ch.codePointAt(0);
    if (ch === "'") out += "''";
    else if (ch === '\\') out += '\\\\';
    else if (c >= 32 && c < 127) out += ch;
    else if (c < 0x10000) out += '\\X2\\' + c.toString(16).toUpperCase().padStart(4, '0') + '\\X0\\';
    else out += '\\X4\\' + c.toString(16).toUpperCase().padStart(8, '0') + '\\X0\\';
  }
  return "'" + out + "'";
}

const num = (v) => { const r = Math.round(v * 1000) / 1000; return Number.isInteger(r) ? r.toFixed(1) : String(r); };
const pt = (p) => '(' + p.map(num).join(',') + ')';

const CLASE_TRAMO = { ducto: ['IfcDuctSegment', 'RIGIDSEGMENT'], tuberia: ['IfcPipeSegment', 'RIGIDSEGMENT'],
  bandeja: ['IfcCableCarrierSegment', 'CABLETRAYSEGMENT'] };
const CLASE_ACC = { ducto: 'IfcDuctFitting', tuberia: 'IfcPipeFitting', bandeja: 'IfcCableCarrierFitting' };
const ENUM_ACC = { codo: 'BEND', tee: 'JUNCTION', cruz: 'JUNCTION', reduccion: 'TRANSITION' };
const ENUM_ACC_BANDEJA = { codo: 'BEND', tee: 'TEE', cruz: 'CROSS', reduccion: 'REDUCER' };

export function exportarIFC(m, an, fecha = new Date()) {
  const L = [];
  let n = 0;
  const e = (s) => { n += 1; L.push(`#${n}=${s};`); return `#${n}`; };

  const origen = e('IFCCARTESIANPOINT((0.,0.,0.))');
  const dz = e('IFCDIRECTION((0.,0.,1.))');
  const dx = e('IFCDIRECTION((1.,0.,0.))');
  const ejesMundo = e(`IFCAXIS2PLACEMENT3D(${origen},${dz},${dx})`);
  const ctx = e(`IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,${ejesMundo},$)`);
  const body = e(`IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,${ctx},$,.MODEL_VIEW.,$)`);
  const unidades = e(`IFCUNITASSIGNMENT((${[
    e('IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)'),
    e('IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)'),
    e('IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.)'),
    e('IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.)'),
  ].join(',')}))`);
  const proyecto = e(`IFCPROJECT('${guid()}',$,${str(m.nombre)},$,$,$,$,(${ctx}),${unidades})`);
  const colocSitio = e(`IFCLOCALPLACEMENT($,${ejesMundo})`);
  const sitio = e(`IFCSITE('${guid()}',$,'Sitio',$,$,${colocSitio},$,$,.ELEMENT.,$,$,$,$,$)`);
  const colocEdif = e(`IFCLOCALPLACEMENT(${colocSitio},${ejesMundo})`);
  const edificio = e(`IFCBUILDING('${guid()}',$,${str(m.nombre)},$,$,${colocEdif},$,$,.ELEMENT.,$,$,$)`);
  e(`IFCRELAGGREGATES('${guid()}',$,$,$,${proyecto},(${sitio}))`);
  e(`IFCRELAGGREGATES('${guid()}',$,$,$,${sitio},(${edificio}))`);

  const niveles = [...m.niveles].sort((a, b) => a.elev - b.elev);
  const pisos = niveles.map((nv) => {
    const pl = e(`IFCLOCALPLACEMENT(${colocEdif},${e(`IFCAXIS2PLACEMENT3D(${e(`IFCCARTESIANPOINT((0.,0.,${num(nv.elev)}))`)},$,$)`)})`);
    return { nv, pl, id: e(`IFCBUILDINGSTOREY('${guid()}',$,${str(nv.nombre)},$,$,${pl},$,$,.ELEMENT.,${num(nv.elev)})`), hijos: [] };
  });
  e(`IFCRELAGGREGATES('${guid()}',$,$,$,${edificio},(${pisos.map((p) => p.id).join(',')}))`);
  const pisoDe = (z) => { let r = pisos[0]; for (const p of pisos) if (z >= p.nv.elev - 1) r = p; return r; };

  // estilos por color
  const estilos = {};
  const estilo = (hex) => {
    if (!estilos[hex]) {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
      const col = e(`IFCCOLOURRGB($,${num(r)},${num(g)},${num(b)})`);
      estilos[hex] = e(`IFCSURFACESTYLE($,.BOTH.,(${e(`IFCSURFACESTYLESHADING(${col},0.)`)}))`);
    }
    return estilos[hex];
  };
  const solido = (perfil, pos, prof, hex) => {
    const s = e(`IFCEXTRUDEDAREASOLID(${perfil},${pos},${dz},${num(Math.max(prof, 0.1))})`);
    e(`IFCSTYLEDITEM(${s},(${estilo(hex)}),$)`);
    return s;
  };
  const forma = (items) => e(`IFCPRODUCTDEFINITIONSHAPE($,$,(${e(`IFCSHAPEREPRESENTATION(${body},'Body','SweptSolid',(${items.join(',')}))`)}))`);
  const ax3 = (p, z, x) => e(`IFCAXIS2PLACEMENT3D(${e(`IFCCARTESIANPOINT(${pt(p)})`)},${e(`IFCDIRECTION(${pt(z)})`)},${e(`IFCDIRECTION(${pt(x)})`)})`);
  const coloc = (piso, p, z = [0, 0, 1], x = [1, 0, 0]) => e(`IFCLOCALPLACEMENT(${piso.pl},${ax3([p[0], p[1], p[2] - piso.nv.elev], z, x)})`);

  const psets = [];
  const porSistema = {};
  const meter = (k, id) => { (porSistema[k] = porSistema[k] || []).push(id); };

  for (const t of an.tramos) {
    const piso = pisoDe(Math.min(t.a[2], t.b[2]));
    const { d, s } = ejesTramo(t.a, t.b);
    const sc = seccion(t);
    const perfil = sc.redondo ? e(`IFCCIRCLEPROFILEDEF(.AREA.,$,$,${num(sc.w / 2)})`)
      : e(`IFCRECTANGLEPROFILEDEF(.AREA.,$,$,${num(sc.w)},${num(sc.h)})`);
    const geo = forma([solido(perfil, ax3([0, 0, 0], [0, 0, 1], [1, 0, 0]), longitud(t), SISTEMAS[t.sistema].color)]);
    const [cls, pre] = CLASE_TRAMO[t.tipo];
    // el eje Z local es la dirección del tramo y el X local es el lado: el ancho del perfil queda horizontal
    const id = e(`${cls.toUpperCase()}('${guid()}',$,${str(`${SISTEMAS[t.sistema].nombre} ${rotulo(t)}`)},$,${str(rotulo(t))},${coloc(piso, t.a, d, s)},${geo},${str(t.id)},.${pre}.)`);
    piso.hijos.push(id); meter(t.sistema, id);
    psets.push([id, { Sistema: SISTEMAS[t.sistema].nombre, Tamano: rotulo(t), Longitud_mm: Math.round(longitud(t)),
      Caudal: an.caudal[t.id] ? `${+an.caudal[t.id].toFixed(2)} ${t.tipo === 'ducto' ? 'm3/h' : 'L/s'}` : null }]);
  }

  for (const a of an.accesorios) {
    const piso = pisoDe(a.p[2]);
    const sc = seccion(a.t);
    const lado = Math.max(sc.w, sc.h) * 1.1;
    const perfil = e(`IFCRECTANGLEPROFILEDEF(.AREA.,$,$,${num(lado)},${num(lado)})`);
    const geo = forma([solido(perfil, ax3([0, 0, -lado / 2], [0, 0, 1], [1, 0, 0]), lado, SISTEMAS[a.sistema].color)]);
    const id = e(`${CLASE_ACC[a.clase].toUpperCase()}('${guid()}',$,${str(`${a.tipo} ${rotulo(a.t)}`)},$,${str(a.tipo)},${coloc(piso, a.p)},${geo},${str(a.id)},.${(a.clase === 'bandeja' ? ENUM_ACC_BANDEJA : ENUM_ACC)[a.tipo]}.)`);
    piso.hijos.push(id); meter(a.sistema, id);
  }

  for (const eq of m.elementos.filter((x) => x.tipo === 'equipo')) {
    const f = FAMILIAS[eq.familia];
    const piso = pisoDe(eq.pos[2]);
    const items = f.prismas.map(([eje, a0, a1, col, poly]) => {
      // ejes locales del perfil (u, v) según el eje de extrusión, igual que en el spec. Con eje Y la
      // normal +Y y RefDirection X dejan el v local en -Z: se invierte v.
      const sv = eje === 'Y' ? -1 : 1;
      const pts = poly.map((p) => e(`IFCCARTESIANPOINT((${num(p[0])},${num(sv * p[1])}))`));
      const perfil = e(`IFCARBITRARYCLOSEDPROFILEDEF(.AREA.,$,${e(`IFCPOLYLINE((${[...pts, pts[0]].join(',')}))`)})`);
      const pos = eje === 'Z' ? ax3([0, 0, a0], [0, 0, 1], [1, 0, 0])
        : eje === 'X' ? ax3([a0, 0, 0], [1, 0, 0], [0, 1, 0]) : ax3([0, a0, 0], [0, 1, 0], [1, 0, 0]);
      return solido(perfil, pos, a1 - a0, col);
    });
    const a = ((eq.rot || 0) * Math.PI) / 180;
    const [cls, pre] = f.ifc;
    const id = e(`${cls.toUpperCase()}('${guid()}',$,${str(eq.tag)},${str(f.nombre)},${str(f.nombre)},${coloc(piso, eq.pos, [0, 0, 1], [Math.cos(a), Math.sin(a), 0])},${forma(items)},${str(eq.tag)},.${pre}.)`);
    piso.hijos.push(id);
    psets.push([id, { Familia: f.nombre, Fabricante: f.fabricante || null, Tag: eq.tag, Tablero: eq.tablero || null }]);
  }

  for (const p of pisos) {
    if (p.hijos.length) e(`IFCRELCONTAINEDINSPATIALSTRUCTURE('${guid()}',$,$,$,(${p.hijos.join(',')}),${p.id})`);
  }
  for (const [k, ids] of Object.entries(porSistema)) {
    const s = SISTEMAS[k];
    const sys = e(`IFCDISTRIBUTIONSYSTEM('${guid()}',$,${str(s.nombre)},$,${s.ifc === 'USERDEFINED' ? str(s.nombre) : '$'},${str(k)},.${s.ifc}.)`);
    e(`IFCRELASSIGNSTOGROUP('${guid()}',$,$,$,(${ids.join(',')}),$,${sys})`);
    e(`IFCRELSERVICESBUILDINGS('${guid()}',$,$,$,${sys},(${edificio}))`);
  }
  for (const [id, props] of psets) {
    const ps = Object.entries(props).filter(([, v]) => v !== null && v !== undefined && v !== '')
      .map(([k, v]) => e(`IFCPROPERTYSINGLEVALUE(${str(k)},$,${typeof v === 'number' ? `IFCREAL(${num(v)})` : `IFCLABEL(${str(v)})`},$)`));
    if (!ps.length) continue;
    const set = e(`IFCPROPERTYSET('${guid()}',$,'Pset_PACT_MEP',$,(${ps.join(',')}))`);
    e(`IFCRELDEFINESBYPROPERTIES('${guid()}',$,$,$,(${id}),${set})`);
  }

  const nombre = (m.nombre || 'modelo').replace(/[^\w-]+/g, '_') + '.ifc';
  const cab = [
    'ISO-10303-21;', 'HEADER;',
    "FILE_DESCRIPTION(('ViewDefinition [ReferenceView_V1.2]'),'2;1');",
    `FILE_NAME(${str(nombre)},'${fecha.toISOString().slice(0, 19)}',(''),(''),'PACT MEP','PACT MEP','');`,
    "FILE_SCHEMA(('IFC4'));", 'ENDSEC;', 'DATA;',
  ];
  return { nombre, texto: [...cab, ...L, 'ENDSEC;', 'END-ISO-10303-21;', ''].join('\n') };
}

// ---------------------------------------------------------------- ZIP (método 0: almacenado)
const CRC = (() => {
  const t = new Uint32Array(256);
  for (let i = 0; i < 256; i++) { let c = i; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[i] = c >>> 0; }
  return t;
})();
function crc32(b) { let c = 0xffffffff; for (const x of b) c = CRC[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }

export function zip(archivos) {
  const enc = new TextEncoder();
  const partes = [], central = [];
  let off = 0;
  for (const { nombre, datos } of archivos) {
    const nb = enc.encode(nombre);
    const d = typeof datos === 'string' ? enc.encode(datos) : datos;
    const crc = crc32(d);
    const h = new DataView(new ArrayBuffer(30));
    h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true);
    h.setUint32(14, crc, true); h.setUint32(18, d.length, true); h.setUint32(22, d.length, true); h.setUint16(26, nb.length, true);
    partes.push(new Uint8Array(h.buffer), nb, d);
    const c = new DataView(new ArrayBuffer(46));
    c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true);
    c.setUint32(16, crc, true); c.setUint32(20, d.length, true); c.setUint32(24, d.length, true); c.setUint16(28, nb.length, true);
    c.setUint32(42, off, true);
    central.push(new Uint8Array(c.buffer), nb);
    off += 30 + nb.length + d.length;
  }
  const tam = central.reduce((s, x) => s + x.length, 0);
  const fin = new DataView(new ArrayBuffer(22));
  fin.setUint32(0, 0x06054b50, true); fin.setUint16(8, archivos.length, true); fin.setUint16(10, archivos.length, true);
  fin.setUint32(12, tam, true); fin.setUint32(16, off, true);
  const todo = [...partes, ...central, new Uint8Array(fin.buffer)];
  const out = new Uint8Array(todo.reduce((s, x) => s + x.length, 0));
  let p = 0;
  for (const x of todo) { out.set(x, p); p += x.length; }
  return out;
}
