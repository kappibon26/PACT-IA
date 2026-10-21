// node --test mep-web/tests/*.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { analizarRedes, cargasElectricas, dimensionar, diamEquivalente, friccion, hidraulica, interferencias, obbChocan } from '../js/calculos.js';
import { crearEjemplo } from '../js/ejemplo.js';
import { exportarIFC, guid, str, zip } from '../js/ifc.js';
import { construirRed, modeloVacio } from '../js/modelo.js';

const cerca = (a, b, tol) => assert.ok(Math.abs(a - b) <= tol, `${a} != ${b} ± ${tol}`);

test('fricción de Darcy: laminar y Swamee-Jain', () => {
  cerca(friccion(1000, 0), 0.064, 1e-9);
  cerca(friccion(1e5, 1e-4), 0.0185, 5e-4); // diagrama de Moody
});

test('diámetro equivalente de Huebscher', () => {
  cerca(diamEquivalente(400, 400), 437.2, 0.5);
  cerca(diamEquivalente(600, 300), 457.0, 0.5); // tabla ASHRAE: 457
});

test('hidráulica de ducto y tubería', () => {
  const d = hidraulica({ tipo: 'ducto', sistema: 'SA', forma: 'rect', ancho: 450, alto: 400 }, 3600);
  cerca(d.v, 5.56, 0.01);
  cerca(d.dp, 0.79, 0.05); // ~0.8 Pa/m en la carta de fricción ASHRAE
  const p = hidraulica({ tipo: 'tuberia', sistema: 'AF', dn: 50 }, 1.3);
  cerca(p.v, 0.60, 0.01);
  assert.equal(hidraulica({ tipo: 'tuberia', sistema: 'VP', dn: 200 }, 10), null); // vapor: sin cálculo
});

test('dimensionar respeta velocidad y pérdida', () => {
  assert.deepEqual(dimensionar({ tipo: 'tuberia', sistema: 'AF', dn: 15 }, 1.3), { dn: 40 });
  const r = dimensionar({ tipo: 'ducto', sistema: 'SA', forma: 'rect', ancho: 300, alto: 300 }, 600);
  const h = hidraulica({ tipo: 'ducto', sistema: 'SA', forma: 'rect', ...r }, 600);
  assert.ok(h.v <= 8 && h.dp <= 1);
});

test('red del ejemplo: caudales desde la UMA y accesorios', () => {
  const m = crearEjemplo();
  const an = analizarRedes(m);
  const sa = an.redes.find((r) => r.sistema === 'SA');
  assert.equal(sa.caudalTotal, 3600);
  assert.equal(sa.terminales, 6);
  const tipos = an.accesorios.filter((a) => a.clase === 'ducto').map((a) => a.tipo);
  assert.equal(tipos.filter((t) => t === 'cruz').length, 2);
  assert.equal(tipos.filter((t) => t === 'tee').length, 1);
});

test('interferencias: el agua helada cruza el retorno', () => {
  const m = crearEjemplo();
  const c = interferencias(m, construirRed(m));
  assert.equal(c.length, 1);
  assert.deepEqual([c[0].a.sistema, c[0].b.sistema].sort(), ['AHS', 'RA']);
  const caja = (c, e) => ({ c, e, ejes: [[1, 0, 0], [0, 1, 0], [0, 0, 1]] });
  assert.ok(obbChocan(caja([0, 0, 0], [1, 1, 1]), caja([1.5, 0, 0], [1, 1, 1])));
  assert.ok(!obbChocan(caja([0, 0, 0], [1, 1, 1]), caja([2.5, 0, 0], [1, 1, 1])));
});

test('cargas eléctricas por tablero', () => {
  const r = cargasElectricas(crearEjemplo());
  const td = r.resumen[0];
  assert.equal(td.tablero.tag, 'TD-01');
  assert.equal(td.circuitos.length, 6); // 3 motores de PEL-01, caldera, bomba y UMA
  cerca(td.i, 429, 1);
  assert.equal(td.principal, 600);
  assert.equal(r.sinTablero.length, 1); // el extractor queda sin circuito
});

test('IFC4: cabecera, GUID, cadenas y ZIP', () => {
  assert.match(guid(), /^[0-9A-Za-z_$]{22}$/);
  assert.equal(str("Tubería 'A'"), "'Tuber\\X2\\00ED\\X0\\a ''A'''");
  const m = crearEjemplo();
  const { texto, nombre } = exportarIFC(m, analizarRedes(m));
  assert.match(nombre, /\.ifc$/);
  assert.match(texto, /FILE_SCHEMA\(\('IFC4'\)\);/);
  assert.equal((texto.match(/IFCPIPESEGMENT\(/g) || []).length, 20);
  assert.ok(texto.includes('IFCDISTRIBUTIONSYSTEM('));
  const z = zip([{ nombre: 'a.txt', datos: 'hola' }]);
  assert.deepEqual([...z.slice(0, 4)], [0x50, 0x4b, 0x03, 0x04]);
});

test('modelo vacío no rompe el análisis', () => {
  const m = modeloVacio();
  const an = analizarRedes(m);
  assert.equal(an.redes.length, 0);
  assert.ok(exportarIFC(m, an).texto.includes('IFCPROJECT('));
});
