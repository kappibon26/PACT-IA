# -*- coding: utf-8 -*-
"""
ADLB · Generar familia de Revit desde Excel
Revit 2022+ · Dynamo 2.x · un solo nodo Python (CPython3 o IronPython 2.7) · sin paquetes externos

Entradas del nodo
  IN[0]  Excel ADLB_Plantilla_Familia.xlsx (llenado)
  IN[1]  carpeta donde se guarda el .rfa
  IN[2]  plano de PLANTA (.dwg / .dxf, opcional)  -> se importa en la vista de planta de la familia
  IN[3]  plano de ALZADO FRONTAL (.dwg / .dxf, opcional) -> se importa en el alzado frontal
  IN[4]  cargar la familia en el proyecto abierto (True / False)
  IN[5]  SOLO VALIDAR (True = revisa el Excel y no crea nada)
  IN[6]  EJECUTAR (False mientras llenas las entradas)

Convenciones (las mismas del Excel)
  - Unidades: mm.  Origen (0,0,0) = el origen de tus dibujos, sobre el piso.
  - X = a lo largo en la planta, Y = a lo ancho en la planta, Z = altura (alzado).
  - Cada pieza se describe por su caja envolvente: X desde/hasta, Y desde/hasta, Z desde/hasta.
"""
import io
import os
import re
import math
import time
import zipfile
import datetime
import xml.etree.ElementTree as ET

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')
from Autodesk.Revit.DB import (
    Arc, BuiltInCategory, BuiltInParameter, Category, Color, ConnectorElement, ConnectorProfileType,
    CurveArray, CurveArrArray, DWGImportOptions, FamilyElementVisibility, FamilyElementVisibilityType,
    FamilySource, FilteredElementCollector, FlowDirectionType, GroupTypeId, IFamilyLoadOptions,
    ImportColorMode, ImportPlacement, ImportUnit, Line, Material, Options, PlanarFace, Plane,
    SaveAsOptions, SketchPlane, Solid, SpecTypeId, Transaction, UnitTypeId, UnitUtils, View,
    ViewDetailLevel, ViewPlan, ViewType, XYZ,
)
from Autodesk.Revit.DB.Plumbing import PipeSystemType
from Autodesk.Revit.DB.Mechanical import DuctSystemType
from Autodesk.Revit.DB.Electrical import ElectricalSystemType
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

MM = 1.0 / 304.8
SEC = {'X': ('Y', 'Z'), 'Y': ('X', 'Z'), 'Z': ('X', 'Y')}
UNIT = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}
SI = ('si', 's', 'yes', 'y', 'true', '1', 'x', 'verdadero')

CATEGORIAS = {
    'equipomecanico': ('OST_MechanicalEquipment', [u'Equipo mecánico métrico.rft', 'Metric Mechanical Equipment.rft', 'M_Mechanical Equipment.rft']),
    'equipoelectrico': ('OST_ElectricalEquipment', [u'Equipo eléctrico métrico.rft', 'Metric Electrical Equipment.rft', 'M_Electrical Equipment.rft']),
    'aparatosanitario': ('OST_PlumbingFixtures', [u'Aparato sanitario métrico.rft', 'Metric Plumbing Fixture.rft', 'M_Plumbing Fixture.rft']),
    'accesoriodetuberia': ('OST_PipeAccessory', [u'Accesorio de tubería métrico.rft', 'Metric Pipe Accessory.rft', 'M_Pipe Accessory.rft']),
    'modelogenerico': ('OST_GenericModel', [u'Modelo genérico métrico.rft', 'Metric Generic Model.rft', 'M_Generic Model.rft']),
}
GENERICAS = [u'Modelo genérico métrico.rft', 'Metric Generic Model.rft', 'M_Generic Model.rft']
TIPOS_DATO = {
    'longitud': ('Length', 'mm'), 'texto': ('String.Text', 'txt'), 'url': ('String.Url', 'txt'),
    'numero': ('Number', 'num'), 'entero': ('Int.Integer', 'int'), 'sino': ('Boolean.YesNo', 'bool'),
    'angulo': ('Angle', 'deg'), 'area': ('Area', 'm2'), 'volumen': ('Volume', 'm3'),
    'material': ('Reference.Material', 'mat'),
}
GRUPOS = {
    'dimensiones': 'Geometry', 'restricciones': 'Constraints', 'datos': 'Data', 'identidad': 'IdentityData',
    'materiales': 'Materials', 'texto': 'Text', 'graficos': 'Graphics', 'mecanico': 'Mechanical',
    'electrico': 'Electrical', 'fontaneria': 'Plumbing', 'estructural': 'Structural', 'general': 'General',
}
SIS_TUBERIA = {
    'aguafria': 'DomesticColdWater', 'aguacaliente': 'DomesticHotWater', 'sanitario': 'Sanitary',
    'ventilacion': 'Vent', 'pluvial': 'Storm', 'incendio': 'FireProtectWet',
    'suministrohidronico': 'SupplyHydronic', 'retornohidronico': 'ReturnHydronic', 'otro': 'OtherPipe',
}
SIS_DUCTO = {'suministroaire': 'SupplyAir', 'retornoaire': 'ReturnAir', 'extraccion': 'ExhaustAir',
             'otro': 'OtherAir'}


# ============================================================================ utilidades
def norm(t):
    t = (u'%s' % ('' if t is None else t)).strip().lower()
    for a, b in ((u'á', u'a'), (u'é', u'e'), (u'í', u'i'), (u'ó', u'o'), (u'ú', u'u'), (u'ñ', u'n'),
                 (u' ', u''), (u'_', u''), (u'-', u''), (u'.', u'')):
        t = t.replace(a, b)
    return t


def num(v, defecto=None):
    if v is None or (u'%s' % v).strip() == u'':
        return defecto
    return float((u'%s' % v).strip().replace(u',', u'.'))


def nombre_param(*partes):
    """Une partes en un nombre de parametro valido: sin espacios, tildes ni simbolos."""
    out = []
    for p in partes:
        p = (u'%s' % p).strip()
        if not p:
            continue
        for a, b in ((u'á', u'a'), (u'é', u'e'), (u'í', u'i'), (u'ó', u'o'), (u'ú', u'u'), (u'ñ', u'n'),
                     (u'Á', u'A'), (u'É', u'E'), (u'Í', u'I'), (u'Ó', u'O'), (u'Ú', u'U'), (u'Ñ', u'N')):
            p = p.replace(a, b)
        p = re.sub(u'[^A-Za-z0-9]+', u'_', p).strip(u'_')
        out.append(p)
    return u'_'.join(out)


def xyz(x, y, z):
    return XYZ(x * MM, y * MM, z * MM)


def vec(eje):
    s = -1.0 if eje.startswith('-') else 1.0
    u = UNIT[eje[-1]]
    return XYZ(s * u[0], s * u[1], s * u[2])


def pt(d):
    return xyz(d['X'], d['Y'], d['Z'])


def spec_id(path):
    obj = SpecTypeId
    for part in path.split('.'):
        obj = getattr(obj, part)
    return obj


def grupo_id(nombre, defecto='Data'):
    return getattr(GroupTypeId, GRUPOS.get(norm(nombre), defecto), GroupTypeId.Data)


def txt_error(ex):
    return (u'%s' % ex).replace(u'\r', u' ').replace(u'\n', u' | ')


# ============================================================================ lector de Excel (.xlsx sin dependencias)
_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_NSR = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def leer_excel(ruta):
    """Devuelve {nombre_hoja: [ {encabezado_normalizado: valor} ]} usando la fila 1 como encabezados."""
    z = zipfile.ZipFile(ruta)
    comunes = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('{%s}si' % _NS):
            comunes.append(u''.join(t.text or u'' for t in si.iter('{%s}t' % _NS)))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    destino = dict((r.get('Id'), r.get('Target')) for r in rels)
    libro = ET.fromstring(z.read('xl/workbook.xml'))
    hojas = {}
    for s in libro.find('{%s}sheets' % _NS):
        t = destino[s.get('{%s}id' % _NSR)].lstrip('/')
        t = t if t.startswith('xl/') else 'xl/' + t
        hojas[norm(s.get('name'))] = _tabla(ET.fromstring(z.read(t)), comunes)
    return hojas


def _tabla(raiz, comunes):
    celdas = {}
    for c in raiz.iter('{%s}c' % _NS):
        ref = c.get('r')
        col = re.match('[A-Z]+', ref).group(0)
        fila = int(ref[len(col):])
        tipo = c.get('t')
        v = c.find('{%s}v' % _NS)
        if tipo == 's':
            val = comunes[int(v.text)]
        elif tipo == 'inlineStr':
            val = u''.join(x.text or u'' for x in c.iter('{%s}t' % _NS))
        elif tipo == 'b':
            val = u'Si' if (v is not None and v.text == '1') else u'No'
        else:
            val = v.text if v is not None else u''
        celdas.setdefault(fila, {})[col] = val
    if 1 not in celdas:
        return []
    enc = dict((col, norm(v)) for col, v in celdas[1].items() if v)
    out = []
    for fila in sorted(celdas):
        if fila == 1:
            continue
        d = dict((enc[c], v) for c, v in celdas[fila].items() if c in enc)
        primero = (u'%s' % d.get(enc[sorted(enc, key=lambda k: (len(k), k))[0]], u'')).strip()
        if not primero or primero.startswith(u'#'):
            continue
        d['_fila'] = fila
        out.append(d)
    return out


# ============================================================================ validacion
def validar(t, log):
    errores = 0
    fam = t['familia']
    if not fam.get('nombrearchivo'):
        log.append(u'ERROR  1_Familia: falta Nombre_Archivo'); errores += 1
    if norm(fam.get('categoria')) not in CATEGORIAS:
        log.append(u'AVISO  1_Familia: categoria "%s" no reconocida, se usa Modelo generico' % fam.get('categoria'))
    for p in t['piezas']:
        ref = u'2_Piezas fila %d (%s)' % (p['_fila'], p.get('pieza'))
        try:
            c = [num(p.get(k)) for k in ('xdesde', 'xhasta', 'ydesde', 'yhasta', 'zdesde', 'zhasta')]
            if None in c:
                raise Exception(u'faltan coordenadas')
            if c[1] <= c[0] or c[3] <= c[2] or c[5] <= c[4]:
                raise Exception(u'cada "hasta" debe ser mayor que su "desde"')
            if norm(p.get('forma')) not in ('caja', 'cilindro'):
                raise Exception(u'Forma debe ser Caja o Cilindro')
            if norm(p.get('forma')) == 'cilindro':
                eje = (p.get('eje') or u'Z').strip().upper()
                if eje not in ('X', 'Y', 'Z'):
                    raise Exception(u'Eje debe ser X, Y o Z')
                d = {'X': (c[3] - c[2], c[5] - c[4]), 'Y': (c[1] - c[0], c[5] - c[4]), 'Z': (c[1] - c[0], c[3] - c[2])}[eje]
                if abs(d[0] - d[1]) > 1.0:
                    log.append(u'AVISO  %s: la seccion no es cuadrada (%.0f x %.0f), se usa el diametro menor' % (ref, d[0], d[1]))
        except Exception as ex:
            log.append(u'ERROR  %s: %s' % (ref, txt_error(ex))); errores += 1
    for cx in t['conexiones']:
        ref = u'3_Conexiones fila %d (%s)' % (cx['_fila'], cx.get('conexion'))
        try:
            if None in [num(cx.get(k)) for k in ('x', 'y', 'z')]:
                raise Exception(u'faltan X, Y o Z')
            d = (cx.get('direccion') or u'').strip().upper()
            if d not in ('+X', '-X', '+Y', '-Y', '+Z', '-Z'):
                raise Exception(u'Direccion debe ser +X, -X, +Y, -Y, +Z o -Z')
            tipo = norm(cx.get('tipo'))
            if tipo not in ('tuberia', 'ducto', 'electrico'):
                raise Exception(u'Tipo debe ser Tuberia, Ducto o Electrico')
            if tipo == 'tuberia' and not num(cx.get('diametro')):
                raise Exception(u'una tuberia necesita Diametro')
            if tipo == 'ducto' and norm(cx.get('forma')) == 'redonda' and not num(cx.get('diametro')):
                raise Exception(u'un ducto redondo necesita Diametro')
            if tipo == 'ducto' and norm(cx.get('forma')) != 'redonda' and not (num(cx.get('ancho')) and num(cx.get('alto'))):
                raise Exception(u'un ducto rectangular necesita Ancho y Alto')
        except Exception as ex:
            log.append(u'ERROR  %s: %s' % (ref, txt_error(ex))); errores += 1
    for p in t['parametros']:
        if norm(p.get('tipodato')) not in TIPOS_DATO:
            log.append(u'ERROR  4_Parametros fila %d (%s): TipoDato "%s" no reconocido' % (
                p['_fila'], p.get('nombre'), p.get('tipodato'))); errores += 1
    return errores


# ============================================================================ generador
class Generador(object):

    def __init__(self, app, tablas, log):
        self.app = app
        self.t = tablas
        self.f = tablas['familia']
        self.log = log
        self.prefijo = nombre_param(self.f.get('prefijo', u''))
        self.doc = None
        self.fm = None
        self.mats, self.subs, self.params = {}, {}, {}

    # ---------------------------------------------------------------- documento
    def plantilla(self):
        propia = (self.f.get('plantillarft') or u'').strip()
        if propia and os.path.exists(propia):
            return propia
        cat = CATEGORIAS.get(norm(self.f.get('categoria')), CATEGORIAS['modelogenerico'])
        raices = [self.app.FamilyTemplatePath,
                  u'C:\\ProgramData\\Autodesk\\RVT %s\\Family Templates' % self.app.VersionNumber]
        for nombres in (cat[1], GENERICAS):
            for raiz in raices:
                if not raiz or not os.path.isdir(raiz):
                    continue
                for dp, _d, fs in os.walk(raiz):
                    for f in fs:
                        if f.lower() in [n.lower() for n in nombres]:
                            return os.path.join(dp, f)
        raise Exception(u'No se encontro plantilla .rft. Escribe la ruta en 1_Familia > Plantilla_RFT')

    def tx(self, nombre):
        t = Transaction(self.doc, nombre)
        t.Start()
        return t

    def paso(self, nombre, funcion):
        t = self.tx(u'ADLB - ' + nombre)
        try:
            funcion()
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'%s: %s' % (nombre, txt_error(ex)))

    # ---------------------------------------------------------------- 1. familia, tipo, materiales
    def base(self):
        cat = CATEGORIAS.get(norm(self.f.get('categoria')), CATEGORIAS['modelogenerico'])
        c = Category.GetCategory(self.doc, getattr(BuiltInCategory, cat[0]))
        fam = self.doc.OwnerFamily
        if fam.FamilyCategory is None or fam.FamilyCategory.Id.IntegerValue != c.Id.IntegerValue:
            fam.FamilyCategory = c
        tipo = (self.f.get('nombretipo') or u'Tipo 1').strip()
        existentes = [x for x in self.fm.Types if x.Name == tipo]
        self.fm.CurrentType = existentes[0] if existentes else self.fm.NewType(tipo)
        famcat = fam.FamilyCategory
        actuales = dict((s.Name, s) for s in famcat.SubCategories)
        for p in self.t['piezas']:
            grupo = (p.get('grupo') or u'Cuerpo').strip()
            if grupo not in self.subs:
                sc = actuales.get(grupo) or self.doc.Settings.Categories.NewSubcategory(famcat, grupo)
                self.subs[grupo] = sc
            mat = (p.get('material') or u'').strip()
            if mat and mat not in self.mats:
                self.mats[mat] = self.material(mat, p.get('color'))
        if 'Conexiones' not in self.subs:
            self.subs['Conexiones'] = actuales.get('Conexiones') or self.doc.Settings.Categories.NewSubcategory(famcat, 'Conexiones')
        self.log.append(u'OK     categoria %s, tipo "%s", %d grupos, %d materiales' % (
            famcat.Name, tipo, len(self.subs), len(self.mats)))

    def material(self, nombre, color):
        for m in FilteredElementCollector(self.doc).OfClass(Material):
            if m.Name == nombre:
                return m.Id
        mid = Material.Create(self.doc, nombre)
        m = self.doc.GetElement(mid)
        h = (u'%s' % (color or u'')).strip().lstrip(u'#')
        if len(h) == 6:
            m.Color = Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return mid

    # ---------------------------------------------------------------- 2. parametros
    def nuevo_param(self, nombre, spec, grupo, instancia=False, valor=None, formula=None):
        fp = self.fm.get_Parameter(nombre)
        if fp is None:
            fp = self.fm.AddParameter(nombre, grupo, spec_id(spec), instancia)
        self.params[nombre] = fp
        if valor is not None:
            self.fm.Set(fp, valor)
        if formula:
            self.fm.SetFormula(fp, formula)
        return fp

    def parametros(self):
        for bip, clave in (('ALL_MODEL_MANUFACTURER', 'fabricante'), ('ALL_MODEL_MODEL', 'modelo'),
                           ('ALL_MODEL_DESCRIPTION', 'descripcion'), ('ALL_MODEL_URL', 'url')):
            v = (self.f.get(clave) or u'').strip()
            if v:
                try:
                    self.fm.Set(self.fm.get_Parameter(getattr(BuiltInParameter, bip)), v)
                except Exception as ex:
                    self.log.append(u'AVISO  %s: %s' % (bip, txt_error(ex)))
        for nombre, mid in self.mats.items():
            self.nuevo_param(nombre_param(u'Mat', nombre), 'Reference.Material', GroupTypeId.Materials, False, mid)
        compartidos = self.compartidos()
        tipos = list(self.fm.Types)
        n = 0
        for p in self.t['parametros']:
            nombre = nombre_param(p.get('nombre'))
            try:
                td = TIPOS_DATO[norm(p.get('tipodato'))]
                inst = norm(p.get('instancia')) in SI
                fp = self.fm.get_Parameter(nombre)
                if fp is None:
                    if norm(p.get('compartido')) in SI:
                        d = compartidos.get(nombre)
                        if d is None:
                            raise Exception(u'no esta en el archivo de parametros compartidos')
                        fp = self.fm.AddParameter(d, grupo_id(p.get('grupo')), inst)
                    else:
                        fp = self.fm.AddParameter(nombre, grupo_id(p.get('grupo')), spec_id(td[0]), inst)
                self.params[nombre] = fp
                if (p.get('formula') or u'').strip():
                    self.fm.SetFormula(fp, p.get('formula').strip())
                elif (u'%s' % (p.get('valor') or u'')).strip():
                    v = self.convertir(p.get('valor'), td[1])
                    for ty in tipos:
                        self.fm.CurrentType = ty
                        self.fm.Set(fp, v)
                n += 1
            except Exception as ex:
                self.log.append(u'ERROR  4_Parametros fila %d (%s): %s' % (p['_fila'], nombre, txt_error(ex)))
        self.log.append(u'OK     %d parametros de la hoja 4_Parametros' % n)

    def compartidos(self):
        ruta = (self.f.get('archivocompartidos') or u'').strip()
        if not ruta:
            return {}
        if not os.path.exists(ruta):
            self.log.append(u'AVISO  no existe el archivo de compartidos: %s' % ruta)
            return {}
        previo = self.app.SharedParametersFilename
        try:
            self.app.SharedParametersFilename = ruta
            archivo = self.app.OpenSharedParameterFile()
            return dict((d.Name, d) for g in archivo.Groups for d in g.Definitions)
        finally:
            if previo:
                self.app.SharedParametersFilename = previo

    def convertir(self, valor, modo):
        v = (u'%s' % valor).strip()
        if modo == 'txt':
            return datetime.date.today().isoformat() if v.upper() == u'HOY' else v
        if modo == 'bool':
            return 1 if norm(v) in SI else 0
        if modo == 'mat':
            mid = self.mats.get(v)
            if mid is None:
                for m in FilteredElementCollector(self.doc).OfClass(Material):
                    if norm(m.Name) == norm(v):
                        mid = m.Id
            if mid is None:
                raise Exception(u'material "%s" no existe' % v)
            return mid
        n = num(v)
        if modo == 'int':
            return int(round(n))
        if modo == 'num':
            return n
        u = {'mm': UnitTypeId.Millimeters, 'deg': UnitTypeId.Degrees, 'm2': UnitTypeId.SquareMeters,
             'm3': UnitTypeId.CubicMeters}[modo]
        return UnitUtils.ConvertToInternalUnits(n, u)

    # ---------------------------------------------------------------- 3. planos
    def planos(self, planta, alzado):
        vistas_planta = [v for v in FilteredElementCollector(self.doc).OfClass(ViewPlan) if not v.IsTemplate]
        frontales = [v for v in FilteredElementCollector(self.doc).OfClass(View)
                     if not v.IsTemplate and v.ViewType == ViewType.Elevation and v.ViewDirection.Y < -0.9]
        for ruta, vistas, nombre in ((planta, vistas_planta, u'planta'), (alzado, frontales, u'alzado frontal')):
            if not ruta:
                continue
            if not os.path.exists(ruta):
                self.log.append(u'AVISO  no existe el plano de %s: %s' % (nombre, ruta))
                continue
            if not vistas:
                self.log.append(u'AVISO  la plantilla no tiene vista de %s' % nombre)
                continue
            op = DWGImportOptions()
            op.Placement = ImportPlacement.Origin
            op.Unit = ImportUnit.Millimeter
            op.ThisViewOnly = True
            op.ColorMode = ImportColorMode.Preserved
            res = self.doc.Import(ruta, op, vistas[0])
            eid = res[1] if isinstance(res, tuple) else None
            if eid is not None:
                try:
                    self.doc.GetElement(eid).Pinned = True
                except Exception:
                    pass
            self.log.append(u'OK     plano de %s importado en "%s" (origen a origen, mm)' % (nombre, vistas[0].Name))

    # ---------------------------------------------------------------- 4. piezas
    def lazo_rect(self, eje, coord, cu, cv, du, dv):
        ku, kv = SEC[eje]
        u, v = vec(ku), vec(kv)
        c = pt({eje: coord, ku: cu, kv: cv})
        p = [c.Add(u.Multiply(su * du / 2.0 * MM)).Add(v.Multiply(sv * dv / 2.0 * MM))
             for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        ca = CurveArray()
        for i in range(4):
            ca.Append(Line.CreateBound(p[i], p[(i + 1) % 4]))
        return ca

    def lazo_circ(self, eje, coord, cu, cv, r):
        ku, kv = SEC[eje]
        u, v = vec(ku), vec(kv)
        c = pt({eje: coord, ku: cu, kv: cv})
        a, b = c.Add(u.Multiply(r * MM)), c.Subtract(u.Multiply(r * MM))
        ca = CurveArray()
        ca.Append(Arc.Create(a, b, c.Add(v.Multiply(r * MM))))
        ca.Append(Arc.Create(b, a, c.Subtract(v.Multiply(r * MM))))
        return ca

    def extruir(self, lazos, normal, origen, fin, inicio=0.0):
        caa = CurveArrArray()
        for l in lazos:
            caa.Append(l)
        sp = SketchPlane.Create(self.doc, Plane.CreateByNormalAndOrigin(normal, origen))
        el = self.doc.FamilyCreate.NewExtrusion(True, caa, sp, fin * MM)
        if inicio:
            el.get_Parameter(BuiltInParameter.EXTRUSION_START_PARAM).Set(inicio * MM)
        return el

    def estilo(self, el, grupo, material, detalle=u''):
        sc = self.subs.get(grupo)
        if sc is not None:
            el.Subcategory = sc
        if material:
            fp = self.params.get(nombre_param(u'Mat', material))
            if fp is not None:
                self.fm.AssociateElementParameterToFamilyParameter(
                    el.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM), fp)
        if norm(detalle).startswith('medio') or norm(detalle).startswith('solo'):
            vis = FamilyElementVisibility(FamilyElementVisibilityType.Model)
            vis.IsShownInCoarse = False
            el.SetVisibility(vis)

    def piezas(self):
        n = 0
        for p in self.t['piezas']:
            try:
                x0, x1, y0, y1, z0, z1 = [num(p.get(k)) for k in ('xdesde', 'xhasta', 'ydesde', 'yhasta', 'zdesde', 'zhasta')]
                cx, cy, cz = (x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0
                if norm(p.get('forma')) == 'cilindro':
                    eje = (p.get('eje') or u'Z').strip().upper()
                    if eje == 'X':
                        lz, a0, a1 = self.lazo_circ('X', x0, cy, cz, min(y1 - y0, z1 - z0) / 2.0), x0, x1
                    elif eje == 'Y':
                        lz, a0, a1 = self.lazo_circ('Y', y0, cx, cz, min(x1 - x0, z1 - z0) / 2.0), y0, y1
                    else:
                        lz, a0, a1 = self.lazo_circ('Z', z0, cx, cy, min(x1 - x0, y1 - y0) / 2.0), z0, z1
                    origen = pt({eje: a0, SEC[eje][0]: 0.0, SEC[eje][1]: 0.0})
                    el = self.extruir([lz], vec(eje), origen, a1 - a0)
                else:
                    el = self.extruir([self.lazo_rect('Z', z0, cx, cy, x1 - x0, y1 - y0)], XYZ.BasisZ,
                                      xyz(0, 0, z0), z1 - z0)
                self.estilo(el, (p.get('grupo') or u'Cuerpo').strip(), (p.get('material') or u'').strip(), p.get('detalle'))
                n += 1
            except Exception as ex:
                self.log.append(u'ERROR  2_Piezas fila %d (%s): %s' % (p['_fila'], p.get('pieza'), txt_error(ex)))
        self.log.append(u'OK     %d piezas' % n)

    # ---------------------------------------------------------------- 5. conexiones
    def conexiones(self):
        for cx in self.t['conexiones']:
            nombre = nombre_param(cx.get('conexion'))
            try:
                tipo = norm(cx.get('tipo'))
                if tipo == 'electrico':
                    self.electrica(cx, nombre)
                else:
                    self.boquilla(cx, nombre, tipo)
            except Exception as ex:
                self.log.append(u'ERROR  3_Conexiones fila %d (%s): %s' % (cx['_fila'], nombre, txt_error(ex)))

    def cara(self, el, normal, punto):
        self.doc.Regenerate()
        op = Options()
        op.ComputeReferences = True
        op.DetailLevel = ViewDetailLevel.Fine
        mejor = None
        for g in el.get_Geometry(op):
            if isinstance(g, Solid):
                for f in g.Faces:
                    if isinstance(f, PlanarFace) and f.FaceNormal.DotProduct(normal) > 0.999 and \
                            abs(f.Origin.Subtract(punto).DotProduct(normal)) < 0.002:
                        if mejor is None or f.Area > mejor.Area:
                            mejor = f
        if mejor is None:
            raise Exception(u'no se encontro la cara para el conector')
        return mejor

    def ligar(self, el, bip, nombre):
        self.fm.AssociateElementParameterToFamilyParameter(el.get_Parameter(bip), self.params[nombre])

    def boquilla(self, cx, nombre, tipo):
        d = cx.get('direccion').strip().upper()
        n = vec(d)
        eje = d[-1]
        ku, kv = SEC[eje]
        P = dict(zip(('X', 'Y', 'Z'), [num(cx.get(k)) for k in ('x', 'y', 'z')]))
        L = num(cx.get('largoboquilla'), 150.0)
        base = dict(P)
        base[eje] = P[eje] - (L if d.startswith('+') else -L)
        cu, cv = P[ku], P[kv]
        redonda = tipo == 'tuberia' or norm(cx.get('forma')) == 'redonda'
        brida = norm(cx.get('brida')) in SI
        pre = nombre_param(self.prefijo, nombre)
        g = GroupTypeId.Mechanical
        if redonda:
            dn = num(cx.get('diametro'))
            pared = max(3.0, dn * 0.04)
            od = dn * 1.2 + 105.0
            e = round(18.0 + dn * 0.05, 1) if brida else 0.0
            perno = 16.0 if dn <= 150 else 20.0
            pos = []
            if brida:
                nb = 4 if dn <= 50 else (8 if dn <= 200 else 12)
                bc = od - 40.0
                pos = [(cu + bc / 2.0 * math.cos(math.pi / nb + 2 * math.pi * i / nb),
                        cv + bc / 2.0 * math.sin(math.pi / nb + 2 * math.pi * i / nb)) for i in range(nb)]
            hueco = lambda c: self.lazo_circ(eje, c, cu, cv, dn / 2.0)
            cuerpo = lambda c: [self.lazo_circ(eje, c, cu, cv, dn / 2.0 + pared), hueco(c)]
            plato = lambda c: [self.lazo_circ(eje, c, cu, cv, od / 2.0), hueco(c)]
        else:
            if tipo == 'ducto' and norm(cx.get('forma')) != 'redonda':
                w, h = num(cx.get('ancho')), num(cx.get('alto'))
            pared = 3.0
            e = 10.0 if brida else 0.0
            perno = 10.0
            pos = []
            if brida:
                bu, bv = w + 40.0, h + 40.0
                nu, nv = max(2, int(round(bu / 150.0)) + 1), max(2, int(round(bv / 150.0)) + 1)
                us = [-bu / 2.0 + bu * i / (nu - 1) for i in range(nu)]
                vs = [-bv / 2.0 + bv * i / (nv - 1) for i in range(nv)]
                pos = [(cu + a, cv + b) for a in us for b in vs if a in (us[0], us[-1]) or b in (vs[0], vs[-1])]
            hueco = lambda c: self.lazo_rect(eje, c, cu, cv, w, h)
            cuerpo = lambda c: [self.lazo_rect(eje, c, cu, cv, w + 2 * pared, h + 2 * pared), hueco(c)]
            plato = lambda c: [self.lazo_rect(eje, c, cu, cv, w + 80.0, h + 80.0), hueco(c)]

        # parametros: largo de la boquilla (mueve brida, pernos y conector) y tamano del conector
        self.nuevo_param(pre + u'_Largo', 'Length', g, False, L * MM)
        self.nuevo_param(pre + u'_Brida_Espesor', 'Length', g, False, max(e, 0.5) * MM)
        self.nuevo_param(pre + u'_Brida_Inicio', 'Length', g, False, formula=pre + u'_Largo - ' + pre + u'_Brida_Espesor')
        if brida:
            self.nuevo_param(pre + u'_Tuerca_Alto', 'Length', g, False, perno * 0.8 * MM)
            self.nuevo_param(pre + u'_Perno_Saliente', 'Length', g, False, (e + perno * 1.5) * MM)
            self.nuevo_param(pre + u'_Tuerca_Inicio', 'Length', g, False,
                             formula=pre + u'_Brida_Inicio - ' + pre + u'_Tuerca_Alto')
            self.nuevo_param(pre + u'_Perno_Fin', 'Length', g, False,
                             formula=pre + u'_Largo + ' + pre + u'_Perno_Saliente')
        if redonda:
            self.nuevo_param(pre + u'_DN', 'PipeSize' if tipo == 'tuberia' else 'DuctSize', g, False, dn * MM)
            self.nuevo_param(pre + u'_Radio', 'PipeSize' if tipo == 'tuberia' else 'DuctSize', g, False,
                             formula=pre + u'_DN / 2')
        else:
            self.nuevo_param(pre + u'_Ancho', 'DuctSize', g, False, w * MM)
            self.nuevo_param(pre + u'_Alto', 'DuctSize', g, False, h * MM)

        c0 = base[eje]
        origen = pt(base)
        tubo = self.extruir(cuerpo(c0), n, origen, L - e if brida else L)
        self.estilo(tubo, 'Conexiones', u'')
        self.ligar(tubo, BuiltInParameter.EXTRUSION_END_PARAM, pre + (u'_Brida_Inicio' if brida else u'_Largo'))
        cara_el = tubo
        if brida:
            agujeros = [self.lazo_circ(eje, c0, a, b, (perno + 2.0) / 2.0) for a, b in pos]
            pl = self.extruir(plato(c0) + agujeros, n, origen, L, L - e)
            self.estilo(pl, 'Conexiones', u'')
            self.ligar(pl, BuiltInParameter.EXTRUSION_START_PARAM, pre + u'_Brida_Inicio')
            self.ligar(pl, BuiltInParameter.EXTRUSION_END_PARAM, pre + u'_Largo')
            tuercas = []
            for a, b in pos:
                R = perno * 1.6 / math.sqrt(3.0)
                tuercas.append(self.poligono(eje, c0, [(a + R * math.cos(math.pi / 3 * i), b + R * math.sin(math.pi / 3 * i)) for i in range(6)]))
            tu = self.extruir(tuercas, n, origen, L - e, L - e - perno * 0.8)
            self.estilo(tu, 'Conexiones', u'', u'medio')
            self.ligar(tu, BuiltInParameter.EXTRUSION_START_PARAM, pre + u'_Tuerca_Inicio')
            self.ligar(tu, BuiltInParameter.EXTRUSION_END_PARAM, pre + u'_Brida_Inicio')
            varillas = [self.lazo_circ(eje, c0, a, b, perno / 2.0) for a, b in pos]
            es = self.extruir(varillas, n, origen, L + e + perno * 1.5, L - e - perno * 0.8)
            self.estilo(es, 'Conexiones', u'', u'medio')
            self.ligar(es, BuiltInParameter.EXTRUSION_START_PARAM, pre + u'_Tuerca_Inicio')
            self.ligar(es, BuiltInParameter.EXTRUSION_END_PARAM, pre + u'_Perno_Fin')
            cara_el = pl
        punto = pt(P)
        f = self.cara(cara_el, n, punto)
        if tipo == 'tuberia':
            sis = getattr(PipeSystemType, SIS_TUBERIA.get(norm(cx.get('sistema')), 'OtherPipe'), PipeSystemType.OtherPipe)
            ce = ConnectorElement.CreatePipeConnector(self.doc, sis, f.Reference)
            try:
                self.ligar(ce, BuiltInParameter.CONNECTOR_RADIUS, pre + u'_Radio')
            except Exception:
                self.ligar(ce, BuiltInParameter.CONNECTOR_DIAMETER, pre + u'_DN')
            flujo_bip = BuiltInParameter.RBS_PIPE_FLOW_DIRECTION_PARAM
        else:
            sis = getattr(DuctSystemType, SIS_DUCTO.get(norm(cx.get('sistema')), 'OtherAir'), None) or DuctSystemType.SupplyAir
            perfil = ConnectorProfileType.Round if redonda else ConnectorProfileType.Rectangular
            ce = ConnectorElement.CreateDuctConnector(self.doc, sis, perfil, f.Reference)
            if redonda:
                try:
                    self.ligar(ce, BuiltInParameter.CONNECTOR_RADIUS, pre + u'_Radio')
                except Exception:
                    self.ligar(ce, BuiltInParameter.CONNECTOR_DIAMETER, pre + u'_DN')
            else:
                self.ligar(ce, BuiltInParameter.CONNECTOR_WIDTH, pre + u'_Ancho')
                self.ligar(ce, BuiltInParameter.CONNECTOR_HEIGHT, pre + u'_Alto')
            flujo_bip = BuiltInParameter.RBS_DUCT_FLOW_DIRECTION_PARAM
        self.flujo(ce, flujo_bip, cx.get('flujo'))
        self.descripcion(ce, u'%s %s' % (nombre, cx.get('sistema') or u''))
        self.log.append(u'OK     conexion %s (%s%s, %d pernos)' % (nombre, cx.get('tipo'), u' con brida' if brida else u'', len(pos)))

    def poligono(self, eje, coord, pts):
        ku, kv = SEC[eje]
        p = [pt({eje: coord, ku: a, kv: b}) for a, b in pts]
        ca = CurveArray()
        for i in range(len(p)):
            ca.Append(Line.CreateBound(p[i], p[(i + 1) % len(p)]))
        return ca

    def electrica(self, cx, nombre):
        d = cx.get('direccion').strip().upper()
        n = vec(d)
        eje = d[-1]
        ku, kv = SEC[eje]
        P = dict(zip(('X', 'Y', 'Z'), [num(cx.get(k)) for k in ('x', 'y', 'z')]))
        L = num(cx.get('largoboquilla'), 40.0) or 40.0
        base = dict(P)
        base[eje] = P[eje] - (L if d.startswith('+') else -L)
        caja = self.extruir([self.lazo_rect(eje, base[eje], P[ku], P[kv], 100.0, 100.0)], n, pt(base), L)
        self.estilo(caja, 'Conexiones', u'')
        pre = nombre_param(self.prefijo, nombre)
        g = getattr(GroupTypeId, 'ElectricalLoads', GroupTypeId.Electrical)
        v = num(cx.get('tensionv'), 220.0)
        kw = num(cx.get('potenciakw'), 0.0)
        self.nuevo_param(pre + u'_Tension', 'ElectricalPotential', g, False,
                         UnitUtils.ConvertToInternalUnits(v, UnitTypeId.Volts))
        self.nuevo_param(pre + u'_Polos', 'Int.NumberOfPoles', g, False, 3 if v >= 380 else 1)
        self.nuevo_param(pre + u'_Carga_VA', 'ApparentPower', g, False,
                         UnitUtils.ConvertToInternalUnits(kw * 1000.0 / 0.8, UnitTypeId.VoltAmperes))
        f = self.cara(caja, n, pt(P))
        ce = ConnectorElement.CreateElectricalConnector(self.doc, ElectricalSystemType.PowerBalanced, f.Reference)
        self.ligar(ce, BuiltInParameter.RBS_ELEC_VOLTAGE, pre + u'_Tension')
        self.ligar(ce, BuiltInParameter.RBS_ELEC_NUMBER_OF_POLES, pre + u'_Polos')
        self.ligar(ce, BuiltInParameter.RBS_ELEC_APPARENT_LOAD, pre + u'_Carga_VA')
        self.descripcion(ce, u'%s %.0f V %.1f kW' % (nombre, v, kw))
        self.log.append(u'OK     conexion electrica %s (%.0f V, %.1f kW)' % (nombre, v, kw))

    def flujo(self, ce, bip, valor):
        m = {'entra': 1, 'entrada': 1, 'sale': 2, 'salida': 2, 'ambos': 0}
        if norm(valor) in m:
            try:
                ce.get_Parameter(bip).Set(m[norm(valor)])
            except Exception:
                pass

    def descripcion(self, ce, texto):
        try:
            ce.get_Parameter(BuiltInParameter.RBS_CONNECTOR_DESCRIPTION).Set(texto)
        except Exception:
            pass

    # ---------------------------------------------------------------- guardar y cargar
    def guardar(self, carpeta):
        if not os.path.isdir(carpeta):
            os.makedirs(carpeta)
        ruta = os.path.join(carpeta, nombre_param(self.f.get('nombrearchivo')) + u'.rfa')
        op = SaveAsOptions()
        op.OverwriteExistingFile = True
        op.MaximumBackups = 1
        self.doc.SaveAs(ruta, op)
        self.log.append(u'OK     guardado: %s' % ruta)
        return ruta

    def cargar(self, proyecto):
        try:
            fam = self.doc.LoadFamily(proyecto, opciones_carga())
            self.log.append(u'OK     cargada en el proyecto: %s' % fam.Name)
        except Exception as ex:
            self.log.append(u'AVISO  no se pudo cargar (%s). Cargala a mano: Insertar > Cargar familia.' % txt_error(ex))

    def ejecutar(self, carpeta, planta, alzado, proyecto):
        self.doc = self.app.NewFamilyDocument(self.plantilla())
        self.fm = self.doc.FamilyManager
        try:
            self.paso(u'familia', self.base)
            self.paso(u'parametros', self.parametros)
            if planta or alzado:
                try:
                    self.paso(u'planos', lambda: self.planos(planta, alzado))
                except Exception as ex:
                    self.log.append(u'AVISO  planos: %s' % txt_error(ex))
            self.paso(u'piezas', self.piezas)
            self.paso(u'conexiones', self.conexiones)
            ruta = self.guardar(carpeta)
            if proyecto is not None:
                self.cargar(proyecto)
            return ruta
        finally:
            try:
                self.doc.Close(False)
            except Exception:
                pass


def opciones_carga():
    def encontrada(self, enUso, sobrescribir):
        try:
            sobrescribir.Value = True
            return True
        except Exception:
            return (True, True)

    def compartida(self, compartida, enUso, origen, sobrescribir):
        try:
            origen.Value = FamilySource.Family
            sobrescribir.Value = True
            return True
        except Exception:
            return (True, FamilySource.Family, True)
    cls = type('AdlbOpcionesCarga', (IFamilyLoadOptions,),
               {'OnFamilyFound': encontrada, 'OnSharedFamilyFound': compartida,
                '__namespace__': 'ADLB_%d' % int(time.time() * 1000)})
    return cls()


def leer_tablas(ruta):
    h = leer_excel(ruta)

    def hoja(*claves):
        for k in claves:
            if k in h:
                return h[k]
        return []
    familia = {}
    for fila in hoja('1familia', 'familia'):
        familia[norm(fila.get('campo'))] = fila.get('valor')
    return {'familia': familia, 'piezas': hoja('2piezas', 'piezas'),
            'conexiones': hoja('3conexiones', 'conexiones'), 'parametros': hoja('4parametros', 'parametros')}


# ============================================================================ nodo
ruta_excel = IN[0]
carpeta = IN[1]
planta = IN[2] if len(IN) > 2 and IN[2] else None
alzado = IN[3] if len(IN) > 3 and IN[3] else None
cargar_proyecto = bool(IN[4]) if len(IN) > 4 else True
solo_validar = bool(IN[5]) if len(IN) > 5 else True
ejecutar = bool(IN[6]) if len(IN) > 6 else False

if not ejecutar:
    OUT = [u'EJECUTAR = False. Revisa las entradas y ponlo en True.']
elif not ruta_excel or not os.path.exists(u'%s' % ruta_excel):
    OUT = [u'ERROR  No se encuentra el Excel: %s' % ruta_excel]
else:
    log = []
    tablas = leer_tablas(u'%s' % ruta_excel)
    log.append(u'Excel: %d piezas, %d conexiones, %d parametros' % (
        len(tablas['piezas']), len(tablas['conexiones']), len(tablas['parametros'])))
    errores = validar(tablas, log)
    ruta = None
    if solo_validar:
        resumen = u'VALIDACION: %d errores. %s' % (errores, u'Listo para generar: pon SOLO VALIDAR = False.'
                                                   if errores == 0 else u'Corrige el Excel y vuelve a validar.')
    elif errores:
        resumen = u'NO SE GENERO: el Excel tiene %d errores. Revisa las lineas ERROR.' % errores
    else:
        doc = DocumentManager.Instance.CurrentDBDocument
        app = DocumentManager.Instance.CurrentUIApplication.Application
        TransactionManager.Instance.ForceCloseTransaction()
        try:
            ruta = Generador(app, tablas, log).ejecutar(u'%s' % carpeta, planta, alzado,
                                                        doc if (cargar_proyecto and not doc.IsFamilyDocument) else None)
        except Exception as ex:
            log.append(u'ERROR  %s' % txt_error(ex))
        n_err = len([l for l in log if l.startswith(u'ERROR')])
        resumen = u'FAMILIA GENERADA con %d errores' % n_err if ruta else u'NO SE GENERO la familia'
    OUT = [resumen, ruta] + log
    try:
        if carpeta and os.path.isdir(u'%s' % carpeta):
            with io.open(os.path.join(u'%s' % carpeta, u'ADLB_registro.txt'), 'w', encoding='utf-8') as fh:
                fh.write(u'\n'.join([u'%s' % x for x in OUT]))
    except Exception:
        pass
