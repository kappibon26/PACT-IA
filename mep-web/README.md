# PACT MEP · modelador de instalaciones en el navegador

Prototipo de un "Revit orientado a MEP": se trazan ductos, tuberías y bandejas en 3D o en planta, se colocan
equipos con conectores (incluida la peletizadora PEL-01 generada desde el spec AVSA), y el programa deduce
los accesorios, calcula caudales y pérdidas, detecta interferencias, suma cargas eléctricas por tablero y
exporta a IFC4 para abrir el modelo en Revit, Navisworks, Solibri o BIMcollab.

```
mep-web/
  index.html            interfaz (cinta, navegador de proyecto, lienzo, propiedades, tablas)
  js/app.js             herramientas, selección, paneles, archivo
  js/escena.js          vista 3D y planta (three.js 0.160)
  js/modelo.js          datos del proyecto, red de nudos y accesorios deducidos
  js/calculos.js        hidráulica, dimensionamiento, cargas, interferencias, advertencias
  js/ifc.js             exportación IFC4 + ZIP
  js/catalogo.js        sistemas, tamaños normalizados y familias de equipo
  js/ejemplo.js         proyecto de ejemplo (sala de peletizado + oficinas)
  js/equipos/PEL01.js   generado por herramientas/spec_a_web.py desde dynamo/specs/spec_PEL01_CPM7730.py
  tests/                pruebas de cálculo e IFC (node --test mep-web/tests/*.test.mjs)
```

## Cómo abrirlo

Los módulos JS necesitan servirse por HTTP (no abre con doble clic):

```
cd mep-web
python -m http.server 8000
# abrir http://localhost:8000
```

three.js se carga desde jsDelivr, así que la primera vez hace falta internet. El modelo se guarda solo en el
navegador; **Archivo → Guardar .json** lo deja en un archivo.

## Qué hace

| Herramienta | Tecla | Detalle |
|---|---|---|
| Ducto | D | Rectangular o redondo; sistemas suministro, retorno, extracción y producto a granel |
| Tubería | P | DN15–DN300 (acero Sch 40); agua fría/caliente/helada, desagüe con pendiente, vapor, condensado, aire comprimido |
| Bandeja | B | Bandeja portacables de fuerza o control |
| Equipo | E | UMA, difusor, rejilla, extractor, bomba, caldera, tanque, lavamanos, tablero y PEL-01 · R gira 90° |
| Seleccionar | V | Clic para ver propiedades; Supr elimina; flechas mueven equipos un paso de cuadrícula |

Al trazar, el cursor se ajusta a conectores libres, extremos de tramos y al cuerpo de un tramo (ahí parte el
tramo y deja una tee). El recorrido es ortogonal (Mayús lo libera) y, si el destino está a otra cota, se
crea el montante. Cambiar el desfase en mitad del trazado sube o baja la ruta desde el último punto. Al
llegar a un conector, la ruta entra por su eje. Con pendiente > 0 la tubería baja a medida que avanza.

Los codos, tees, cruces y reducciones no se dibujan a mano: salen de cómo se unen los tramos y aparecen en
la tabla de accesorios y en el IFC.

### Cálculos

- **Caudales por red**: desde el conector fuente (UMA, bomba, caldera, extractor) se recorre la red como un
  árbol y cada tramo lleva la suma de los terminales aguas abajo (difusores, rejillas, serpentines,
  aparatos). Un tramo puede llevar caudal manual cuando la red no tiene fuente.
- **Pérdidas**: Darcy-Weisbach con Swamee-Jain; ductos con diámetro equivalente de Huebscher, galvanizado
  0.09 mm; tubería de acero 0.045 mm con agua a 20 °C (60 °C para agua caliente). Accesorios con K fijo.
  La tabla *Redes* da el ΔP de la ruta crítica.
- **Dimensionar**: el menor tamaño con v ≤ 8 m/s y ≤ 1 Pa/m en ductos (relación de aspecto ≤ 4:1), o
  v ≤ 2.4 m/s y ≤ 400 Pa/m en tuberías. Funciona por tramo, por sistema o en todo el modelo.
- **Cargas eléctricas**: cada conector eléctrico de un equipo asignado a un tablero es un circuito; corriente
  trifásica S / (√3·V) y protección al siguiente valor normal ≥ 1.25·I.
- **Interferencias**: cajas orientadas (teorema del eje separador) entre tramos no conectados y entre tramos
  y cada prisma de los equipos.
- **Advertencias**: extremos abiertos, conectores libres, sistema equivocado en un conector, velocidad o
  pérdida altas, desagües con menos de 1 % de pendiente y equipos sin tablero.

Los criterios son de anteproyecto. No reemplazan la memoria de cálculo ni la verificación con la norma que
aplique al proyecto (NTC 1500, RETIE, ASHRAE, SMACNA).

### IFC

**Archivo → IFC4 (.zip)** entrega un IFC4 dentro de un ZIP: `IfcDuctSegment`, `IfcPipeSegment`,
`IfcCableCarrierSegment`, sus *Fitting*, los equipos con su clase (`IfcUnitaryEquipment`, `IfcAirTerminal`,
`IfcPump`, `IfcBoiler`, `IfcTank`, `IfcElectricDistributionBoard`...), un `IfcDistributionSystem` por
sistema, colores por sistema y `Pset_PACT_MEP` con tamaño, longitud y caudal. Se validó con IfcOpenShell
0.9 (sin errores de esquema y con geometría en todos los elementos).

## Equipos AVSA

`herramientas/spec_a_web.py` convierte cualquier spec de `dynamo/specs/` en una familia del modelador, con
la misma geometría que usa `preview_spec.py` y los conectores de las boquillas y motores:

```
python herramientas/spec_a_web.py dynamo/specs/spec_PEL01_CPM7730.py mep-web/js/equipos/PEL01.js
```

Para un equipo nuevo: generar su `.js`, importarlo en `js/catalogo.js` como PEL01 y darle `prefijo`.

## Lo que todavía no hace

Es un prototipo, no un reemplazo de Revit. Faltan, entre otras cosas: mover tramos arrastrando (los equipos se
mueven por propiedades o con las flechas, y sus tramos no los siguen), cortes y alzados, planos con
anotaciones y cotas, aislamiento, cálculo de vapor y de desagüe por unidades de descarga, importar IFC o
RVT, y trabajo colaborativo.
