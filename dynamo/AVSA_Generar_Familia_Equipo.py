# -*- coding: utf-8 -*-
"""
Nodo Python de Dynamo (CPython3 o IronPython2) - AVSA: generar familia de equipo desde un spec.

Entradas:
  IN[0]  ruta del spec            p.ej. ...\\PACT-IA\\dynamo\\specs\\spec_PEL01_CPM7730.py
  IN[1]  carpeta de salida .rfa   p.ej. ...\\Dynamo_BIM_Claude\\familias\\equipos
  IN[2]  archivo de parametros compartidos  ...\\Dynamo_BIM_Claude\\AVSA_Parametros_Compartidos.txt
  IN[3]  cargar en el proyecto abierto (bool)
  IN[4]  ejecutar (bool)  -> poner en False para que Dynamo no regenere la familia en cada cambio
  IN[5]  (opcional) ruta de la plantilla .rft si no se encuentra automaticamente
Salida:
  OUT    lista de lineas de registro (OK / AVISO / ERROR) + ruta del .rfa
"""
import sys
import os
import clr

clr.AddReference('RevitServices')
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

spec_path = IN[0]
out_dir = IN[1]
shared_params = IN[2]
load_into_project = bool(IN[3])
run = bool(IN[4])
template = IN[5] if len(IN) > 5 else None

if not str(spec_path).lower().endswith('.py'):
    raise Exception(u'IN[0] debe ser el spec .py (...\\dynamo\\specs\\spec_*.py), no: %s' % spec_path)
lib_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(spec_path))), 'lib')
if not os.path.exists(os.path.join(lib_dir, 'ad_family_builder.py')):
    raise Exception(u'No se encontro %s\\ad_family_builder.py. El spec debe estar en ...\\dynamo\\specs\\ '
                    u'junto a la carpeta ...\\dynamo\\lib\\' % lib_dir)
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

import ad_family_builder as afb
try:                                   # recargar la libreria si se edito con Dynamo abierto
    import importlib
    afb = importlib.reload(afb)
except Exception:
    afb = reload(afb)                  # noqa: F821  (IronPython)

if not run:
    OUT = ['Ejecutar = False. Revise las entradas y ponga Ejecutar = True.']
else:
    doc = DocumentManager.Instance.CurrentDBDocument
    app = DocumentManager.Instance.CurrentUIApplication.Application
    log = afb.Log()
    rfa = None
    try:
        spec = afb.load_spec(spec_path)
        TransactionManager.Instance.ForceCloseTransaction()
        builder = afb.FamilyBuilder(app, spec, shared_params, template, log)
        rfa = builder.run(out_dir, doc if load_into_project else None)
    except Exception as ex:
        log.err(u'Ejecucion detenida', ex)
    resumen = u'RESUMEN: %d errores, %d avisos' % (log.errores, log.avisos)
    OUT = [resumen, rfa] + log.lines
    try:                               # copia del registro junto al .rfa
        import io
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with io.open(os.path.join(out_dir, os.path.splitext(os.path.basename(spec_path))[0] + '_registro.txt'),
                     'w', encoding='utf-8') as f:
            f.write(u'\n'.join([u'%s' % x for x in OUT]))
    except Exception:
        pass
