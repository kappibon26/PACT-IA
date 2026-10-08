# -*- coding: utf-8 -*-
"""
ADLB · Plantilla base · Crear y asignar parametros de familia desde un CSV
Revit 2022+ · Dynamo 2.x · nodo Python (CPython3 o IronPython 2.7)

USO
  1. Abra la FAMILIA (.rfa) en el Editor de familias de Revit.
  2. Desde esa familia abra Dynamo y luego ADLB_Parametros_desde_CSV.dyn.
  3. Entradas:
       IN[0]  ruta del CSV de parametros (ver ADLB_Parametros_ejemplo.csv)
       IN[1]  archivo de parametros compartidos (.txt). Vacio si no usa compartidos.
       IN[2]  SIMULAR (True = solo revisa y reporta, no modifica la familia)
       IN[3]  EJECUTAR (False mientras edita las entradas; True para correr)
  4. Corra el grafico en modo Manual y lea el registro de la salida.

COLUMNAS DEL CSV (separador ; o ,  -  codificacion UTF-8)
  Nombre      nombre del parametro
  TipoDato    Longitud | Texto | Numero | Entero | SiNo | Angulo | Area | Volumen | Material | URL
  Grupo       Dimensiones | Restricciones | Datos | Identidad | Materiales | Texto | Graficos |
              Mecanico | Electrico | Fontaneria | Estructural | General
  Instancia   Si | No
  Compartido  Si | No   (Si = se toma del archivo de parametros compartidos, por nombre)
  Valor       valor para TODOS los tipos (longitudes en mm, angulos en grados, SiNo = Si/No,
              Material = nombre del material de la familia). Vacio = no asigna.
  Formula     formula de Revit (opcional). Si hay formula, se ignora Valor.

QUE HACE
  - Crea el parametro si no existe; si ya existe, solo actualiza valor / formula.
  - Avisa si un parametro existente difiere del CSV (instancia/tipo) en lugar de cambiarlo.
  - Asigna el valor a todos los tipos de la familia.
  - No borra nada.  Todo queda en una sola transaccion: Ctrl+Z la deshace completa.
"""
import io
import os
import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')
from Autodesk.Revit.DB import (FilteredElementCollector, GroupTypeId, Material, SpecTypeId, UnitTypeId,
                               UnitUtils)
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

csv_path = IN[0]
shared_path = IN[1] if len(IN) > 1 else None
simular = bool(IN[2]) if len(IN) > 2 else True
ejecutar = bool(IN[3]) if len(IN) > 3 else False

TIPOS = {   # TipoDato -> (ruta SpecTypeId, conversion del valor)
    'longitud': ('Length', 'mm'),
    'texto': ('String.Text', 'txt'),
    'url': ('String.Url', 'txt'),
    'numero': ('Number', 'num'),
    'entero': ('Int.Integer', 'int'),
    'sino': ('Boolean.YesNo', 'bool'),
    'angulo': ('Angle', 'deg'),
    'area': ('Area', 'm2'),
    'volumen': ('Volume', 'm3'),
    'material': ('Reference.Material', 'mat'),
}
GRUPOS = {
    'dimensiones': 'Geometry', 'restricciones': 'Constraints', 'datos': 'Data',
    'identidad': 'IdentityData', 'materiales': 'Materials', 'texto': 'Text',
    'graficos': 'Graphics', 'mecanico': 'Mechanical', 'electrico': 'Electrical',
    'fontaneria': 'Plumbing', 'estructural': 'Structural', 'general': 'General',
}
SI = ('si', 'sí', 's', 'yes', 'y', 'true', '1', 'x')


def norm(t):
    t = (u'%s' % (t or u'')).strip().lower()
    for a, b in ((u'á', u'a'), (u'é', u'e'), (u'í', u'i'), (u'ó', u'o'), (u'ú', u'u'), (u' ', u'')):
        t = t.replace(a, b)
    return t


def spec_id(path):
    obj = SpecTypeId
    for part in path.split('.'):
        obj = getattr(obj, part)
    return obj


def leer_csv(path):
    with io.open(path, 'r', encoding='utf-8-sig') as f:
        lineas = [l.rstrip('\r\n') for l in f if l.strip() and not l.lstrip().startswith('#')]
    sep = ';' if lineas[0].count(';') >= lineas[0].count(',') else ','
    cab = [norm(c) for c in lineas[0].split(sep)]
    filas = []
    for n, l in enumerate(lineas[1:], 2):
        celdas = [c.strip() for c in l.split(sep)]
        celdas += [u''] * (len(cab) - len(celdas))
        fila = dict(zip(cab, celdas))
        fila['_fila'] = n - 1
        filas.append(fila)
    return filas


def convertir(valor, modo, doc):
    v = (u'%s' % valor).strip()
    if modo == 'txt':
        return v
    if modo == 'bool':
        return 1 if norm(v) in SI else 0
    if modo == 'mat':
        for m in FilteredElementCollector(doc).OfClass(Material):
            if norm(m.Name) == norm(v):
                return m.Id
        raise Exception(u'material "%s" no existe en la familia' % v)
    num = float(v.replace(',', '.'))
    if modo == 'int':
        return int(round(num))
    if modo == 'num':
        return num
    unidad = {'mm': UnitTypeId.Millimeters, 'deg': UnitTypeId.Degrees,
              'm2': UnitTypeId.SquareMeters, 'm3': UnitTypeId.CubicMeters}[modo]
    return UnitUtils.ConvertToInternalUnits(num, unidad)


def definiciones_compartidas(app, path):
    if not path or not os.path.exists(path):
        return {}
    previo = app.SharedParametersFilename
    try:
        app.SharedParametersFilename = path
        archivo = app.OpenSharedParameterFile()
        return dict((d.Name, d) for g in archivo.Groups for d in g.Definitions)
    finally:
        if previo:
            app.SharedParametersFilename = previo


def procesar(doc, app, filas, shared_defs, simular, log):
    fm = doc.FamilyManager
    if fm.CurrentType is None:
        fm.NewType(u'Tipo 1')
        log.append(u'AVISO  la familia no tenia tipos: se creo "Tipo 1"')
    tipos = list(fm.Types)
    creados = actualizados = errores = 0
    for f in filas:
        nombre = f.get('nombre', u'')
        ref = u'fila %d  %s' % (f['_fila'], nombre)
        try:
            if not nombre:
                raise Exception(u'sin nombre')
            tipo = TIPOS.get(norm(f.get('tipodato')))
            if tipo is None:
                raise Exception(u'TipoDato "%s" no reconocido' % f.get('tipodato'))
            grupo = getattr(GroupTypeId, GRUPOS.get(norm(f.get('grupo')), 'Data'), GroupTypeId.Data)
            inst = norm(f.get('instancia')) in SI
            comp = norm(f.get('compartido')) in SI
            fp = fm.get_Parameter(nombre)
            if fp is None:
                if simular:
                    log.append(u'CREAR  %s (%s, %s)' % (ref, f.get('tipodato'), u'instancia' if inst else u'tipo'))
                else:
                    if comp:
                        d = shared_defs.get(nombre)
                        if d is None:
                            raise Exception(u'no esta en el archivo de parametros compartidos')
                        fp = fm.AddParameter(d, grupo, inst)
                    else:
                        fp = fm.AddParameter(nombre, grupo, spec_id(tipo[0]), inst)
                    log.append(u'OK     creado %s' % ref)
                creados += 1
            else:
                if fp.IsInstance != inst:
                    log.append(u'AVISO  %s ya existe como %s (el CSV dice %s): no se cambia' % (
                        ref, u'instancia' if fp.IsInstance else u'tipo', u'instancia' if inst else u'tipo'))
                actualizados += 1
            formula = f.get('formula', u'')
            valor = f.get('valor', u'')
            if simular:
                if formula:
                    log.append(u'       formula: %s' % formula)
                elif valor:
                    convertir(valor, tipo[1], doc)          # valida el valor aunque no lo asigne
                    log.append(u'       valor: %s' % valor)
                continue
            if formula:
                fm.SetFormula(fp, formula)
            elif valor:
                v = convertir(valor, tipo[1], doc)
                for t in tipos:
                    fm.CurrentType = t
                    fm.Set(fp, v)
        except Exception as ex:
            errores += 1
            log.append(u'ERROR  %s -> %s' % (ref, (u'%s' % ex).replace(u'\n', u' | ')))
    return creados, actualizados, errores


if not ejecutar:
    OUT = [u'EJECUTAR = False. Revise las entradas y ponga EJECUTAR = True.']
else:
    doc = DocumentManager.Instance.CurrentDBDocument
    app = DocumentManager.Instance.CurrentUIApplication.Application
    log = []
    if not doc.IsFamilyDocument:
        OUT = [u'ERROR  Abra Dynamo desde una FAMILIA (Editor de familias), no desde un proyecto.']
    elif not csv_path or not os.path.exists(u'%s' % csv_path):
        OUT = [u'ERROR  No se encuentra el CSV: %s' % csv_path]
    else:
        filas = leer_csv(csv_path)
        defs = definiciones_compartidas(app, shared_path)
        if not simular:
            TransactionManager.Instance.EnsureInTransaction(doc)
        c, a, e = procesar(doc, app, filas, defs, simular, log)
        if not simular:
            TransactionManager.Instance.TransactionTaskDone()
        modo = u'SIMULACION (no se modifico nada)' if simular else u'APLICADO'
        OUT = [u'%s: %d filas | %d nuevos | %d existentes | %d errores' % (modo, len(filas), c, a, e)] + log
