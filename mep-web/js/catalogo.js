// Catálogo: sistemas MEP, tamaños normalizados y familias de equipos.
// Unidades: mm. Ejes: X este, Y norte, Z arriba. Caudales: ductos en m³/h, tuberías en L/s.
import PEL01 from './equipos/PEL01.js';

// tipo = clase de elemento lineal que admite el sistema
export const SISTEMAS = {
  SA:  { nombre: 'Suministro de aire',        tipo: 'ducto',   color: '#2f78c4', calc: 'aire', ifc: 'AIRCONDITIONING' },
  RA:  { nombre: 'Retorno de aire',           tipo: 'ducto',   color: '#7a55b8', calc: 'aire', ifc: 'AIRCONDITIONING' },
  EA:  { nombre: 'Extracción',                tipo: 'ducto',   color: '#8a6d3b', calc: 'aire', ifc: 'EXHAUST' },
  PR:  { nombre: 'Producto a granel',         tipo: 'ducto',   color: '#9aa1a6', calc: null,   ifc: 'CONVEYING' },
  AF:  { nombre: 'Agua fría',                 tipo: 'tuberia', color: '#1f9fd6', calc: 'agua', ifc: 'DOMESTICCOLDWATER' },
  AC:  { nombre: 'Agua caliente',             tipo: 'tuberia', color: '#d9502f', calc: 'agua_caliente', ifc: 'DOMESTICHOTWATER' },
  AHS: { nombre: 'Agua helada suministro',    tipo: 'tuberia', color: '#1aa79a', calc: 'agua', ifc: 'CHILLEDWATER' },
  AHR: { nombre: 'Agua helada retorno',       tipo: 'tuberia', color: '#5fbf8f', calc: 'agua', ifc: 'CHILLEDWATER' },
  DS:  { nombre: 'Desagüe sanitario',         tipo: 'tuberia', color: '#6b5a48', calc: 'gravedad', ifc: 'DRAINAGE' },
  VP:  { nombre: 'Vapor',                     tipo: 'tuberia', color: '#c0263a', calc: null,   ifc: 'USERDEFINED' },
  CD:  { nombre: 'Condensado',                tipo: 'tuberia', color: '#e08a3c', calc: null,   ifc: 'USERDEFINED' },
  AI:  { nombre: 'Aire comprimido',           tipo: 'tuberia', color: '#4b8fb0', calc: null,   ifc: 'COMPRESSEDAIR' },
  FZ:  { nombre: 'Fuerza',                    tipo: 'bandeja', color: '#c9a227', calc: null,   ifc: 'ELECTRICAL' },
  CT:  { nombre: 'Control y datos',           tipo: 'bandeja', color: '#3d9a5a', calc: null,   ifc: 'CONTROL' },
};

export const TIPOS = {
  ducto:   { nombre: 'Ducto',   plural: 'Ductos',   tecla: 'D' },
  tuberia: { nombre: 'Tubería', plural: 'Tuberías', tecla: 'P' },
  bandeja: { nombre: 'Bandeja', plural: 'Bandejas', tecla: 'B' },
};

export function sistemasDe(tipo) {
  return Object.entries(SISTEMAS).filter(([, s]) => s.tipo === tipo).map(([k]) => k);
}

// Lados de ducto rectangular y diámetros de ducto redondo (mm)
export const LADOS_DUCTO = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900, 1000,
  1100, 1200, 1300, 1400, 1500, 1600, 1800, 2000];
export const DIAM_DUCTO = [100, 125, 150, 175, 200, 250, 300, 350, 400, 450, 500, 550, 600, 700, 800, 900, 1000, 1200];

// Tubería de acero ASTM A53 Sch 40: DN -> diámetro exterior / interior (mm)
export const TUBO = {
  15: [21.3, 15.8], 20: [26.7, 20.9], 25: [33.4, 26.6], 32: [42.2, 35.1], 40: [48.3, 40.9], 50: [60.3, 52.5],
  65: [73.0, 62.7], 80: [88.9, 77.9], 100: [114.3, 102.3], 125: [141.3, 128.2], 150: [168.3, 154.1],
  200: [219.1, 202.7], 250: [273.0, 254.5], 300: [323.8, 303.2],
};
export const DNS = Object.keys(TUBO).map(Number);

export function dnCercano(d) {
  return DNS.reduce((a, b) => (Math.abs(b - d) < Math.abs(a - d) ? b : a));
}

export const BANDEJA_ANCHOS = [100, 150, 200, 300, 400, 450, 600, 750, 900];
export const BANDEJA_ALTOS = [50, 75, 100, 150];

// ---------------------------------------------------------------- familias genéricas
// prisma = [eje, desde, hasta, color, [[u, v], ...]] (mismo formato que herramientas/spec_a_web.py)
function caja(x0, x1, y0, y1, z0, z1, col) {
  return ['Z', z0, z1, col, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]];
}
function cil(eje, cu, cv, r, a0, a1, col, n = 24) {
  const p = [];
  for (let i = 0; i < n; i++) p.push([cu + r * Math.cos(2 * Math.PI * i / n), cv + r * Math.sin(2 * Math.PI * i / n)]);
  return [eje, a0, a1, col, p];
}

const GRIS = '#d6d9d6', OSCURO = '#3b3f42', METAL = '#a9adb0', BLANCO = '#f2f2ef';

const FAMILIAS_GENERICAS = [
  {
    id: 'UMA', nombre: 'Unidad manejadora de aire 10 000 m³/h', categoria: 'Equipo mecánico', prefijo: 'UMA',
    fabricante: 'Genérico', desfase: 0, ifc: ['IfcUnitaryEquipment', 'AIRHANDLER'],
    prismas: [
      caja(0, 3200, -750, 750, 0, 150, OSCURO),
      caja(0, 3200, -750, 750, 150, 1750, GRIS),
      caja(1000, 1050, -755, 755, 150, 1750, METAL),
      caja(2100, 2150, -755, 755, 150, 1750, METAL),
      caja(2400, 2900, -770, -750, 400, 1500, METAL),
      caja(2400, 2900, -300, 300, 1750, 1800, METAL),
      caja(-40, 0, -500, 500, 600, 1300, METAL),
    ],
    conectores: [
      { id: 'SA', nombre: 'Descarga suministro', tipo: 'ducto', sistema: 'SA', flujo: 'salida', fuente: true,
        pos: [2650, 0, 1800], dir: [0, 0, 1], ancho: 1000, alto: 600 },
      { id: 'RA', nombre: 'Toma retorno', tipo: 'ducto', sistema: 'RA', flujo: 'entrada', fuente: true,
        pos: [-40, 0, 950], dir: [-1, 0, 0], ancho: 1000, alto: 700 },
      { id: 'AHS', nombre: 'Serpentín entrada', tipo: 'tuberia', sistema: 'AHS', flujo: 'entrada', caudal: 4.8,
        pos: [1500, -750, 500], dir: [0, -1, 0], dn: 65 },
      { id: 'AHR', nombre: 'Serpentín salida', tipo: 'tuberia', sistema: 'AHR', flujo: 'salida', caudal: 4.8,
        pos: [1800, -750, 500], dir: [0, -1, 0], dn: 65 },
      { id: 'DS', nombre: 'Bandeja de condensados', tipo: 'tuberia', sistema: 'DS', flujo: 'salida', caudal: 0.1,
        pos: [1300, -750, 250], dir: [0, -1, 0], dn: 32 },
      { id: 'EL', nombre: 'Ventilador', tipo: 'electrico', sistema: 'FZ', pos: [2650, 750, 900], dir: [0, 1, 0],
        tension: 460, polos: 3, kw: 15, va: 18750 },
    ],
  },
  {
    id: 'DIF', nombre: 'Difusor de suministro 600×600', categoria: 'Terminal de aire', prefijo: 'DIF',
    fabricante: 'Genérico', desfase: 2900, ifc: ['IfcAirTerminal', 'DIFFUSER'], param: { caudal: 600 },
    prismas: [
      caja(-300, 300, -300, 300, 0, 30, BLANCO),
      caja(-200, 200, -200, 200, 30, 230, METAL),
    ],
    conectores: [
      { id: 'SA', nombre: 'Cuello', tipo: 'ducto', sistema: 'SA', flujo: 'entrada', caudal: 'param',
        pos: [0, 0, 230], dir: [0, 0, 1], ancho: 300, alto: 300 },
    ],
  },
  {
    id: 'REJ', nombre: 'Rejilla de retorno 600×300', categoria: 'Terminal de aire', prefijo: 'REJ',
    fabricante: 'Genérico', desfase: 2900, ifc: ['IfcAirTerminal', 'GRILLE'], param: { caudal: 800 },
    prismas: [
      caja(-300, 300, -150, 150, 0, 30, BLANCO),
      caja(-250, 250, -125, 125, 30, 230, METAL),
    ],
    conectores: [
      { id: 'RA', nombre: 'Cuello', tipo: 'ducto', sistema: 'RA', flujo: 'salida', caudal: 'param',
        pos: [0, 0, 230], dir: [0, 0, 1], ancho: 500, alto: 250 },
    ],
  },
  {
    id: 'EXT', nombre: 'Extractor centrífugo 2 000 m³/h', categoria: 'Equipo mecánico', prefijo: 'EXT',
    fabricante: 'Genérico', desfase: 0, ifc: ['IfcFan', 'CENTRIFUGALFORWARDCURVED'], param: { caudal: 2000 },
    prismas: [
      caja(-450, 450, -400, 400, 0, 100, OSCURO),
      cil('Y', 0, 600, 420, -250, 250, GRIS),
      caja(-200, 200, 250, 600, 300, 700, OSCURO),
      caja(-200, 200, -260, 260, 900, 1200, GRIS),
    ],
    conectores: [
      { id: 'EA', nombre: 'Succión', tipo: 'ducto', sistema: 'EA', flujo: 'entrada', fuente: true,
        pos: [0, 0, 1200], dir: [0, 0, 1], ancho: 400, alto: 400 },
      { id: 'EL', nombre: 'Motor', tipo: 'electrico', sistema: 'FZ', pos: [0, 600, 500], dir: [0, 1, 0],
        tension: 460, polos: 3, kw: 1.5, va: 2100 },
    ],
  },
  {
    id: 'BOM', nombre: 'Bomba centrífuga en línea', categoria: 'Equipo mecánico', prefijo: 'B',
    fabricante: 'Genérico', desfase: 0, ifc: ['IfcPump', 'ENDSUCTION'], param: { sistema: 'AF' },
    prismas: [
      caja(-500, 500, -250, 250, 0, 150, OSCURO),
      cil('X', 0, 450, 180, -350, 50, GRIS),
      cil('X', 0, 450, 140, 50, 450, OSCURO),
      caja(150, 330, 130, 230, 480, 600, OSCURO),
      cil('X', 0, 450, 60, -470, -350, METAL),
      cil('Z', -150, 0, 50, 630, 760, METAL),
    ],
    conectores: [
      { id: 'IN', nombre: 'Succión', tipo: 'tuberia', sistema: '*', flujo: 'entrada',
        pos: [-470, 0, 450], dir: [-1, 0, 0], dn: 80 },
      { id: 'OUT', nombre: 'Descarga', tipo: 'tuberia', sistema: '*', flujo: 'salida', fuente: true,
        pos: [-150, 0, 760], dir: [0, 0, 1], dn: 65 },
      { id: 'EL', nombre: 'Motor', tipo: 'electrico', sistema: 'FZ', pos: [240, 230, 540], dir: [0, 1, 0],
        tension: 460, polos: 3, kw: 7.5, va: 9400 },
    ],
  },
  {
    id: 'CAL', nombre: 'Caldera pirotubular de vapor 300 BHP', categoria: 'Equipo mecánico', prefijo: 'CAL',
    fabricante: 'Genérico', desfase: 0, ifc: ['IfcBoiler', 'STEAM'],
    prismas: [
      caja(0, 5200, -900, 900, 0, 250, OSCURO),
      cil('X', 0, 1300, 1050, 300, 5000, GRIS),
      cil('X', 0, 1300, 1100, 4950, 5300, OSCURO),
      caja(5300, 6100, -600, 600, 250, 1900, OSCURO),
      cil('Z', 1200, 0, 300, 2300, 3200, METAL),
      cil('Z', 3800, 0, 120, 2350, 2600, METAL),
    ],
    conectores: [
      { id: 'VP', nombre: 'Salida de vapor', tipo: 'tuberia', sistema: 'VP', flujo: 'salida', fuente: true,
        pos: [3800, 0, 2600], dir: [0, 0, 1], dn: 200 },
      { id: 'AF', nombre: 'Agua de alimentación', tipo: 'tuberia', sistema: 'AF', flujo: 'entrada', caudal: 1.3,
        pos: [800, -1050, 900], dir: [0, -1, 0], dn: 50 },
      { id: 'CD', nombre: 'Retorno de condensado', tipo: 'tuberia', sistema: 'CD', flujo: 'entrada', fuente: true,
        pos: [1600, -1050, 900], dir: [0, -1, 0], dn: 50 },
      { id: 'EL', nombre: 'Quemador y bomba', tipo: 'electrico', sistema: 'FZ', pos: [5700, 600, 1100], dir: [0, 1, 0],
        tension: 460, polos: 3, kw: 11, va: 13800 },
    ],
  },
  {
    id: 'TAN', nombre: 'Tanque de agua 10 m³', categoria: 'Equipo mecánico', prefijo: 'TK',
    fabricante: 'Genérico', desfase: 0, ifc: ['IfcTank', 'STORAGE'],
    prismas: [
      cil('Z', 0, 0, 1250, 0, 2400, '#cfd8dc'),
      cil('Z', 0, 0, 300, 2400, 2500, METAL),
    ],
    conectores: [
      { id: 'OUT', nombre: 'Salida', tipo: 'tuberia', sistema: 'AF', flujo: 'salida',
        pos: [1250, 0, 200], dir: [1, 0, 0], dn: 80 },
      { id: 'IN', nombre: 'Llenado', tipo: 'tuberia', sistema: 'AF', flujo: 'entrada', caudal: 0.5,
        pos: [0, 1250, 2200], dir: [0, 1, 0], dn: 50 },
    ],
  },
  {
    id: 'LAV', nombre: 'Lavamanos de pared', categoria: 'Aparato sanitario', prefijo: 'LV',
    fabricante: 'Genérico', desfase: 0, ifc: ['IfcSanitaryTerminal', 'WASHHANDBASIN'],
    prismas: [
      caja(-275, 275, -230, 230, 780, 860, BLANCO),
      caja(-40, 40, 150, 230, 400, 780, BLANCO),
      caja(-30, 30, 120, 170, 860, 980, METAL),
    ],
    conectores: [
      { id: 'AF', nombre: 'Agua fría', tipo: 'tuberia', sistema: 'AF', flujo: 'entrada', caudal: 0.1,
        pos: [-100, 230, 600], dir: [0, 1, 0], dn: 15 },
      { id: 'AC', nombre: 'Agua caliente', tipo: 'tuberia', sistema: 'AC', flujo: 'entrada', caudal: 0.1,
        pos: [100, 230, 600], dir: [0, 1, 0], dn: 15 },
      { id: 'DS', nombre: 'Desagüe', tipo: 'tuberia', sistema: 'DS', flujo: 'salida', caudal: 0.5,
        pos: [0, 230, 450], dir: [0, 1, 0], dn: 40 },
    ],
  },
  {
    id: 'TAB', nombre: 'Tablero de distribución 460 V', categoria: 'Equipo eléctrico', prefijo: 'TD',
    fabricante: 'Genérico', desfase: 0, ifc: ['IfcElectricDistributionBoard', 'DISTRIBUTIONBOARD'],
    tablero: { tension: 460, polos: 3 },
    prismas: [
      caja(-400, 400, -250, 250, 0, 100, OSCURO),
      caja(-400, 400, -250, 250, 100, 2200, '#9fa8a3'),
      caja(-380, 380, -260, -250, 150, 2150, '#b9c1bc'),
    ],
    conectores: [
      { id: 'FZ', nombre: 'Salida de fuerza', tipo: 'bandeja', sistema: 'FZ', flujo: 'salida',
        pos: [0, 0, 2200], dir: [0, 0, 1], ancho: 300, alto: 100 },
    ],
  },
];

PEL01.prefijo = 'PEL';
PEL01.desfase = 0;
PEL01.ifc = ['IfcBuildingElementProxy', 'NOTDEFINED'];
PEL01.param = { caudal_vapor: 0 };

export const FAMILIAS = Object.fromEntries([...FAMILIAS_GENERICAS, PEL01].map((f) => [f.id, f]));
