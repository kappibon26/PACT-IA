# PACT-IA · Familias Revit de equipos AVSA desde Dynamo

Genera familias `.rfa` de equipos (LOD 350 y LOI según ad-STD-AVSA-003) con **Python en Dynamo** (Revit 2024).
Toda la geometría y los datos de un equipo están en un **spec** (`dynamo/specs/spec_*.py`). Una sola
librería (`dynamo/lib/ad_family_builder.py`) convierte cualquier spec en familia. Para un equipo nuevo
(caldera, cocedora, Higienizer…) se copia un spec y se ajusta; el código no cambia.

```
dynamo/
  AVSA_Generar_Familia_Equipo.dyn   gráfico de Dynamo (6 entradas → nodo Python → registro)
  AVSA_Generar_Familia_Equipo.py    código del nodo Python (fuente del .dyn)
  lib/ad_family_builder.py          librería: plantilla, parámetros, geometría, conectores, guardar/cargar
  specs/spec_PEL01_CPM7730.py       peletizadora CPM 7730-8 + 30LTC13HS + INF12
herramientas/
  preview_spec.py                   vista previa / superposición sobre el DXF del proveedor (fuera de Revit)
  build_dyn.py                      regenera el .dyn cuando se edita el .py del nodo
docs/
  PEL-01_CPM-7730-8.md              ficha: origen, piezas, conexiones, LOI, pendientes
```

## Uso

1. Copiar la carpeta `dynamo/` a la máquina con Revit (debe conservar `lib/` y `specs/` juntas).
2. Abrir el proyecto en Revit 2024. Abrir Dynamo y luego `AVSA_Generar_Familia_Equipo.dyn`.
3. Llenar las entradas:
   1. ruta del spec (`specs\spec_PEL01_CPM7730.py`)
   2. carpeta de salida del `.rfa`
   3. `AVSA_Parametros_Compartidos.txt`
   4. cargar en el proyecto (Sí/No)
   5. **EJECUTAR**: dejarlo en *False* mientras se editan las entradas y pasarlo a *True* para correr
   6. plantilla `.rft`: dejar vacío y el script la busca sola (Equipo mecánico métrico / Metric Mechanical Equipment)
4. Correr en modo **Manual** y leer el nodo *Registro*. La primera línea dice cuántos errores y avisos hubo.
   Cada pieza o conector que falle queda en el registro y no detiene el resto.

Motor del nodo: **CPython3** (el que trae Dynamo 2.17 en Revit 2024). El código también corre en IronPython 2.7.

## Qué es paramétrico y qué no

| Paramétrico en Revit (flexiona) | Fijo desde el spec (se regenera con el script) |
|---|---|
| Tamaño de cada conector (`CXnn_DN`, `CXnn_Ancho/Alto`) | Envolventes del molino, acondicionador, alimentador y motores |
| Proyección de la boquilla y espesor de brida (`CXnn_Proyeccion`, `CXnn_Brida_Espesor`): mueven la brida **y el conector** | Posición de los ejes y de los anclajes |
| Datos eléctricos de cada motor (`ELnn_Tension`, `_Polos`, `_Carga_Aparente`) | |
| Largo de las zonas de servicio (instancia) y su visibilidad (`Mostrar_Zonas_Servicio`) | |
| Materiales por grupo (`Mat_Cuerpo`, `Mat_Motores`…) | |
| Todos los LOI (compartidos, agendables y etiquetables) | |

Un equipo de proveedor (un modelo CPM concreto) no cambia de tamaño. Por eso las cotas del cuerpo
salen del spec y no se restringen con cotas etiquetadas: la familia es más liviana y no se rompe al
flexionarla. Si cambia el modelo, se edita el spec y se vuelve a correr.
