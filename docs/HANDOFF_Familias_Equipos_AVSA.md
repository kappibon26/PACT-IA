# HANDOFF · Familias de equipos AVSA-MACPOLLO (Revit 2024 + Dynamo)

> **Para la sesión local de Claude.** Este documento resume todo lo hecho en la sesión en la nube y lo que falta.
> Léelo completo antes de actuar. El objetivo es **generar el resto de familias de equipos** con el mismo flujo
> y el mismo script de Dynamo que ya produjo la peletizadora PEL-01. Para cada equipo cambia solo la
> especificación (`spec_<TAG>.py`) y, si hace falta, se extiende la librería.

---

## 1. Contexto del proyecto

| Ítem | Valor |
|---|---|
| Proyecto | AVSA · MACPOLLO, Planta de Pienso Horizonte: redes de vapor (VAP) y condensado (CON) |
| Modelo | `AVSA-MACPOLLO_ad_Vapor-Condensado_V01.rvt` (Revit 2024.3, colaborativo, worksets AM) |
| Estándares | ad-STD-AVSA-001 Nomenclatura · **ad-STD-AVSA-003 LOI de familias** · ad-STD-AVSA-004 Línea gráfica |
| Herramientas | AutoCAD LT · Revit 2024.3 + *mcp-servers-for-revit* · Dynamo 2.17 (CPython3) · Python con ezdxf, numpy, matplotlib |
| Usuario de Windows | `C:\Users\Administrador\` |

### Rutas locales (confirmadas por el usuario)

| Qué | Ruta |
|---|---|
| **DWG de los equipos (pendientes)** | `G:\.shortcut-targets-by-id\1AOo7ITbnYdnTNoCkpHBUSMuhi9R32zJX\.55\06_ASVA_MACPOLLO\AVSA-MACPOLLO\03_SHARED\Dibujos DWG` |
| Carpeta de trabajo Dynamo | `C:\Users\Administrador\Dynamo_BIM_Claude\` |
| Parámetros compartidos | `C:\Users\Administrador\Dynamo_BIM_Claude\AVSA_Parametros_Compartidos.txt` (UTF-16) |
| Generador (copia local del repo) | `C:\Users\Administrador\Dynamo_BIM_Claude\PACT-IA\dynamo\` |
| Salida de familias | `C:\Users\Administrador\Dynamo_BIM_Claude\familias\Equipos\` |
| Familias de anotación existentes | `C:\Users\Administrador\Dynamo_BIM_Claude\familias\anotacion\` |

### Repositorio

- GitHub `kappibon26/pact-ia`, rama **`claude/focused-allen-1b59qw`**.
- Si la carpeta local no está al día: `git clone -b claude/focused-allen-1b59qw https://github.com/kappibon26/pact-ia.git`, o descargar el ZIP de la rama.

```
dynamo/
  AVSA_Generar_Familia_Equipo.dyn   gráfico (entradas → 1 nodo Python → Watch)
  AVSA_Generar_Familia_Equipo.py    código del nodo (fuente del .dyn; regenerar con herramientas/build_dyn.py)
  lib/ad_family_builder.py          librería: plantilla, LOI, geometría, boquillas, conectores, zonas, guardar/cargar
  specs/spec_PEL01_CPM7730.py       especificación de referencia (peletizadora CPM 7730-8 + 30LTC13HS + INF12)
herramientas/
  preview_spec.py                   vista previa 3D + superposición sobre el DXF (control de calidad)
  build_dyn.py                      regenera el .dyn desde el .py del nodo
docs/
  PEL-01_CPM-7730-8.md              ficha de la peletizadora (piezas, conexiones, LOI, pendientes)
lead-magnet/                        (otro tema: kit ADLB; no tocar para las familias AVSA)
```

---

## 2. Estado actual

| Equipo | Estado | Notas |
|---|---|---|
| **PEL-01** Peletizadora CPM 7730-8 | Generada y cargada (v1). **v2 detallada** subida: bridas con pernos, motores con aletas, juntas B-B/C-C/D-D, canaleta U | Confirmar que la v2 corre limpia en Revit (pedir `familias\Equipos\spec_PEL01_CPM7730_registro.txt`) |
| Resto de equipos | **Pendiente** | DWG en la carpeta `Dibujos DWG` (sección 1) |

**Pendientes abiertos de PEL-01**
- En la primera corrida real hubo **1 ERROR en la línea 10 del registro**, justo antes de "Geometría". Probablemente eran los planos de referencia horizontales; ya se cambiaron a `NewReferencePlane2`. Verificar con el registro de la v2.
- Potencia del motor principal: 300 HP según el catálogo CPM 7700; confirmar con la placa.
- Clase de la brida de vapor (8" ASME 150# supuesta).
- Lubricación y patas del acondicionador ubicadas `aprox`, porque no están acotadas en el plano.
- Orientación ancho/alto de los conectores rectangulares: revisar en el editor de familias.

---

## 3. Cómo funciona el generador (resumen técnico)

**Gráfico `AVSA_Generar_Familia_Equipo.dyn`** (abrirlo **desde el proyecto**, no desde una familia):

| Puerto | Nodo | Valor |
|---|---|---|
| IN[0] | File Path | `...\PACT-IA\dynamo\specs\spec_<TAG>.py` (**debe estar en `specs\`**, junto a `lib\`) |
| IN[1] | Directory Path | `...\Dynamo_BIM_Claude\familias\Equipos` |
| IN[2] | File Path | `...\AVSA_Parametros_Compartidos.txt` |
| IN[3] | Boolean | cargar en el proyecto (True) |
| IN[4] | Boolean | EJECUTAR (False mientras se editan entradas) |
| IN[5] | String | plantilla .rft (vacío = automática; el usuario usó `C:\ProgramData\Autodesk\RVT 2024\Family Templates\English\Metric Generic Model.rft`, que también sirve) |

**Qué hace la librería** (`FamilyBuilder.run`):
1. `NewFamilyDocument` y categoría Equipos mecánicos, más el tipo.
2. Materiales y subcategorías `AM_*`.
3. Parámetros:
   - LOI compartidos del grupo `AVSA_LOI_Equipos` (instancia: AM_Tag y AM_Sistema).
   - Datos nativos (fabricante, modelo, descripción, comentarios de tipo).
   - Materiales por parámetro.
   - Parámetros de boquilla, eléctricos y de zonas.
4. Planos de referencia con nombre (anclajes y ejes).
5. Geometría: `caja`, `cilindro`, `ext` (lazos `rect / rrect / circ / hex / poly / u`), `transicion` y vacíos de anclaje.
6. Boquillas paramétricas:
   - Piezas: tubo hueco, cuello, brida con agujeros, cara RF, espárragos y tuercas.
   - Todo cuelga de `<CX>_Proyeccion`, y el conector queda sobre la cara de la brida.
   - El tamaño se liga a `<CX>_DN` o a `_Ancho`/`_Alto`.
7. Conectores eléctricos sobre las cajas de bornes (tensión, polos y carga ligados a parámetros).
8. Zonas de servicio con largo paramétrico y el Sí/No `Mostrar_Zonas_Servicio`.
9. Guarda el `.rfa`, lo carga en el proyecto con sobrescritura y deja el registro en `<spec>_registro.txt`.

**Formato del spec** (ver docstring y helpers en `spec_PEL01_CPM7730.py`):
- Sistema de coordenadas de la familia en mm: el origen es un punto útil en obra (borde de base o eje) sobre el NPT. Documentar la conversión CAD → familia en el docstring.
- Helpers: `caja()`, `cil()`, `ext()`, `R/RR/C/H/U`, `aletas()`, `perimetro()`, `paso()`, `circulo_pernos()`, `junta_bridada()`, `pernos_boquilla()` y la tabla `PERNO` (M10, M12, M24, 3/4").
- `'nivel': 'fino'` oculta la pieza en nivel de detalle Bajo. `'aprox': True` marca piezas sin cota en el CAD.
- Bloques del `SPEC`: `familia`, `nativos`, `loi`, `materiales`, `subcategorias`, `solidos`, `vacios`, `boquillas`, `electricos`, `planos_referencia`, `zonas`.

**Parámetros compartidos disponibles** (grupo `AVSA_LOI_Equipos`):
- AM_Tag, AM_Sistema, AM_Fuente_Geometria, AM_Confianza_Dimensional, AM_Peso_kg, AM_LOD, AM_Fecha_Modelado.
- AM_Capacidad, AM_Presion_Diseno, AM_Presion_Trabajo, AM_Temperatura_Operacion, AM_Tipo_Combustible.
- AM_Material_Construccion, AM_Dimensiones_Generales.
- AM_Conexion_Entrada / _Salida / _Retorno / _Purga / _Producto.
- Fuera de este grupo están AM_Codigo (grupo AVSA_Familias) y los de anotación (grupo AVSA_Anotacion).
- Valores de texto (no hay listas en Revit 2024):
  - Sistema: Vapor / Condensado / Aceite / Líquidos especiales.
  - Fuente: Ficha técnica / Archivo proveedor / Plano CAD.
  - Confianza: Alta / Media.
- AM_LOD = `350` para el alcance OC-001.
- Lo que no venga en el plano se escribe **POR CONFIRMAR** o queda vacío; nunca se inventa.

---

## 4. Procedimiento por equipo (repetir para cada DWG)

1. **Inventario.** Listar `Dibujos DWG\*.dwg` y armar la tabla de la sección 6: tag, equipo, archivo, proveedor y prioridad. Pedir al usuario los **tags oficiales** (CAL-01, COC-04…) o el P&ID.
2. **DWG → DXF.**
   - Opción recomendada: ODA File Converter por lotes (DXF 2018).
   - Opción manual: `DXFOUT` en AutoCAD LT, abriendo el maestro **solo lectura** y cerrando **sin guardar**.
   - `accoreconsole` **no funciona** con AutoCAD LT Educación.
   - Los DXF grandes se leen en streaming con `ezdxf.addons.iterdxf`.
3. **Análisis del DXF** con Python y ezdxf:
   - Listar capas, textos, `DIMENSION` (`get_measurement()`), líneas largas por vista, círculos y arcos.
   - Identificar vistas y proyección (1.er o 3.er ángulo), escala y unidades.
   - En la peletizadora las **vistas de detalle no estaban a escala**: usar el texto de las cotas.
   - Renderizar recortes con cuadrícula (`ezdxf.addons.drawing` + matplotlib) para entender la geometría.
4. **Escribir `dynamo/specs/spec_<TAG>_<MODELO>.py`**, copiando la estructura de `spec_PEL01_CPM7730.py`:
   - Origen y conversión CAD → familia (`X = x_cad − ox`, `Y = oy − x_cad_frontal`, `Z = y_cad − z0`) documentados en el docstring.
   - Boquillas con brida real según la norma (B16.5 para tuberías en pulgadas) y pernos según el patrón del plano.
   - LOI completo, con `AM_Sistema` según el servicio del equipo.
5. **Validar fuera de Revit:**
   - `python herramientas/preview_spec.py dynamo/specs/spec_X.py out.png --dxf PLANO.dxf --lateral ox oz --frontal ox oz` y revisar que el modelo calce con el CAD en ambas vistas.
   - Revisar que **ningún lazo de una misma extrusión se toque** con otro: Revit los rechaza. Ya pasó con `puerta_nervios`.
   - `python -m py_compile` sobre el spec.
6. **Generar en Revit:** en el gráfico solo cambia IN[0]. Leer el registro, corregir el spec y volver a generar. **Nunca editar la familia a mano.**
7. **Documentar:** crear `docs/<TAG>_<MODELO>.md` con la misma estructura que `PEL-01_CPM-7730-8.md`, actualizar la tabla de la sección 6 y hacer commit en la rama.

---

## 5. Mejoras de librería probablemente necesarias

| Mejora | Para qué | Dónde |
|---|---|---|
| **Modo lote** | IN[0] = carpeta `specs\`: genera todas las familias y deja un registro por familia | `AVSA_Generar_Familia_Equipo.py` (loop sobre `spec_*.py`) |
| **Boquillas en ángulo** | Boquillas radiales de tanques y calderas (hoy solo ±X, ±Y, ±Z) | `_nozzle_layer`: aceptar vector de eje arbitrario y construir `u, v` ortonormales |
| **Cascos de revolución** | Cabezales torisféricos o elípticos de tanques y calderas | Nueva forma `revolucion` con `NewRevolution` (perfil en un plano que contiene el eje) |
| Silletas, faldón, patas | Recipientes horizontales y verticales | Helpers en el spec: `silleta()`, `faldon()`, `patas_tubo()` |
| Manhole y mirillas | Tanques y cocedoras | Helper sobre `pernos_boquilla` con tapa ciega |

**Arquetipos esperados** (por las descripciones de los parámetros compartidos):
- Calderas (vapor, agua, purga, combustible).
- Cocedoras (vapor de entrada, condensado, producto).
- Tanques distribuidores (entrada, salida, retorno).
- Higienizer (producto, caudal, temperatura).
- Equipos en skid.

**Prioridad:** primero los equipos con conexiones **VAP/CON**, porque destraban el modelado de la red de tuberías.

---

## 6. Tabla de seguimiento (completar con el inventario)

| # | Tag | Equipo | DWG | Proveedor / modelo | Spec | Estado | Por confirmar |
|---|---|---|---|---|---|---|---|
| 1 | PEL-01 | Peletizadora | PELLET_MAGDALENA.dxf | CPM 7730-8 + 30LTC13HS + INF12 | spec_PEL01_CPM7730.py | Generada, v2 por validar | Potencia motor, clase de brida, capacidad |
| 2 | | | | | | | |

---

## 7. Reglas operativas (aprendidas; no repetir errores)

**Revit y Dynamo**
- Dynamo queda ligado al documento desde el que se abrió. Si el usuario abre un `.rfa` o cambia de proyecto, aparece **"Dynamo no señala al documento actual"**: volver a la vista del proyecto o reabrir Dynamo desde él.
- IN[0] debe ser el `spec_*.py` dentro de `dynamo\specs\`, no el `.md` de `docs\` (pasó una vez).
- Si el usuario pega el código del nodo, debe pegarlo **completo**. Un fragmento da `NameError: spec_path`.
- Correr en modo **Manual** con el interruptor EJECUTAR.
- Código compatible con CPython3 e IronPython: sin f-strings ni operadores sobre `XYZ` (usar `.Add/.Subtract/.Multiply`).
- `send_code_to_revit` (MCP) corre dentro de una transacción: para familias usar `NewFamilyDocument`/`OpenDocumentFile`, no `EditFamily`.
- Si la API da *timeout*, casi siempre hay un diálogo modal abierto en Revit (guardar, avisos de CAD o de conectividad).
- No usar `open_application` con Revit ni AutoCAD: abre otra instancia.

**CAD**
- Abrir el maestro **solo lectura** y cerrar **sin guardar**.
- Coordenadas reales a más de 33 km del origen: Revit las rechaza, hay que llevarlas a coordenadas locales.
- En AutoCAD LT por computer-use, escribir rutas en tramos de 15 caracteres o menos.

**Confidencialidad**
- **No subir DWG/DXF de proveedores al repositorio**: el plano CPM tiene aviso de confidencialidad, y el `.gitignore` excluye `*.dwg` y `*.dxf`.

---

## 8. Primeras acciones para la sesión local

1. `git pull` de la rama `claude/focused-allen-1b59qw` en `Dynamo_BIM_Claude\PACT-IA`.
2. Listar `Dibujos DWG` y llenar la tabla de la sección 6, preguntando al usuario los tags oficiales.
3. Pedir el registro de la corrida de PEL-01 v2 y cerrar sus pendientes.
4. Convertir los DWG a DXF en una carpeta fuera del repositorio, por ejemplo `Dynamo_BIM_Claude\dxf_equipos\`.
5. Implementar el **modo lote** y las **boquillas en ángulo** antes del primer tanque o caldera.
6. Seguir el procedimiento de la sección 4, equipo por equipo y en orden de prioridad. Hacer commit al terminar cada uno.
