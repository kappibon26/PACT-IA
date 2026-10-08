# -*- coding: utf-8 -*-
"""
ad_family_builder - generador de familias de equipos AVSA desde Dynamo (Revit 2024).

Lee un SPEC (dynamo/specs/spec_*.py) y crea un .rfa nuevo en segundo plano:
  1. plantilla de Equipos mecanicos (o generico + cambio de categoria)
  2. materiales, subcategorias y parametros (LOI compartidos ad-STD-AVSA-003 + parametros de la familia)
  3. geometria LOD 350: extrusiones con perfiles compuestos (rectangulos, redondeados, circulos,
     hexagonos, poligonos, canaletas en U, motores con aletas), huecos, transiciones y vacios
  4. boquillas parametricas: tubo hueco, cuello, brida con agujeros, cara realzada, esparragos y tuercas;
     proyeccion / espesores / tamano del conector ligados a parametros de tipo
  5. conectores MEP de tuberia, ducto y electricos sobre las caras de la geometria
  6. zonas de servicio con largo parametrico y Si/No de visibilidad
  7. guardar .rfa y (opcional) cargar en el proyecto abierto

Compatible con CPython3 (PythonNet) e IronPython 2.7: sin f-strings, sin operadores sobre XYZ.
Unidades del spec: mm.  Unidades internas de Revit: pies.
"""
import os
import math
import datetime
import time

import clr
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import (
    Arc, BuiltInCategory, BuiltInParameter, Category, Color, ConnectorElement, ConnectorProfileType,
    CurveArray, CurveArrArray, ElementId, FamilyElementVisibility, FamilyElementVisibilityType,
    FamilyInstanceReferenceType, FilteredElementCollector,
    FlowDirectionType, GroupTypeId, IFamilyLoadOptions, FamilySource, Line, Material, Options,
    PlanarFace, Plane, SaveAsOptions, SketchPlane, Solid, SolidSolidCutUtils, SpecTypeId,
    Transaction, UnitTypeId, UnitUtils, ViewDetailLevel, ViewPlan, ViewType, View, XYZ,
)
from Autodesk.Revit.DB.Plumbing import PipeSystemType
from Autodesk.Revit.DB.Mechanical import DuctSystemType
from Autodesk.Revit.DB.Electrical import ElectricalSystemType

MM = 1.0 / 304.8
AXIS = {'X': 0, 'Y': 1, 'Z': 2}
SEC = {'X': ('Y', 'Z'), 'Y': ('X', 'Z'), 'Z': ('X', 'Y')}   # ejes (u, v) de la seccion normal a cada eje
UNIT = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}


# ============================================================================ utilidades
class Log(object):
    def __init__(self):
        self.lines = []
        self.errores = 0
        self.avisos = 0

    def ok(self, msg):
        self.lines.append(u'OK    ' + msg)

    def warn(self, msg):
        self.avisos += 1
        self.lines.append(u'AVISO ' + msg)

    def err(self, msg, ex=None):
        self.errores += 1
        self.lines.append(u'ERROR ' + msg + ((u' -> ' + _txt(ex)) if ex is not None else u''))


def _txt(x):
    try:
        t = u'%s' % x
    except Exception:
        t = repr(x)
    if isinstance(x, Exception) or hasattr(x, 'Message'):
        t = u'[%s] %s' % (x.__class__.__name__, t)
    return t.replace(u'\r', u' ').replace(u'\n', u' | ')


def xyz(p):
    return XYZ(p[0] * MM, p[1] * MM, p[2] * MM)


def vec(axis_signed):
    """'+X' / '-Y' / 'Z' -> XYZ unitario."""
    s = -1.0 if axis_signed.startswith('-') else 1.0
    u = UNIT[axis_signed[-1]]
    return XYZ(s * u[0], s * u[1], s * u[2])


def pt(axis_vals):
    """dict {'X':..,'Y':..,'Z':..} en mm -> XYZ."""
    return xyz((axis_vals['X'], axis_vals['Y'], axis_vals['Z']))


def _gid(*names):
    for n in names:
        g = getattr(GroupTypeId, n, None)
        if g is not None:
            return g
    return GroupTypeId.Data


def _spec(path):
    """'Length' / 'Int.NumberOfPoles' / 'Boolean.YesNo' -> ForgeTypeId."""
    obj = SpecTypeId
    for part in path.split('.'):
        obj = getattr(obj, part)
    return obj


def _enum_int(e, fallback):
    try:
        return int(e)
    except Exception:
        try:
            import System
            return System.Convert.ToInt32(e)
        except Exception:
            return fallback


# ============================================================================ constructor
class FamilyBuilder(object):

    def __init__(self, app, spec, shared_param_file=None, template_path=None, log=None):
        self.app = app
        self.spec = spec
        self.spf = shared_param_file
        self.template_path = template_path
        self.log = log or Log()
        self.doc = None
        self.fm = None
        self.mats = {}        # clave -> ElementId material
        self.subs = {}        # clave -> Category subcategoria
        self.elems = {}       # id spec -> GenericForm
        self.params = {}      # nombre -> FamilyParameter

    # ------------------------------------------------------------------ plantilla / documento
    def find_template(self):
        if self.template_path and os.path.exists(self.template_path):
            return self.template_path
        names = self.spec['familia'].get('plantillas', [])
        roots = [self.app.FamilyTemplatePath,
                 r'C:\ProgramData\Autodesk\RVT %s\Family Templates' % self.app.VersionNumber]
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for want in names:
                for dirpath, _dirs, files in os.walk(root):
                    for f in files:
                        if f.lower() == want.lower():
                            return os.path.join(dirpath, f)
        return None

    def create_document(self):
        tpl = self.find_template()
        if not tpl:
            raise Exception(u'No se encontro plantilla de familia. Pase la ruta del .rft en la entrada "plantilla".')
        self.log.ok(u'Plantilla: ' + tpl)
        self.doc = self.app.NewFamilyDocument(tpl)
        self.fm = self.doc.FamilyManager
        return self.doc

    def _tx(self, name):
        t = Transaction(self.doc, name)
        t.Start()
        return t

    # ------------------------------------------------------------------ categoria, tipo, materiales, subcategorias
    def setup_family(self):
        t = self._tx(u'AVSA - categoria, tipo, materiales')
        try:
            bic = getattr(BuiltInCategory, self.spec['familia'].get('categoria', 'OST_MechanicalEquipment'))
            fam = self.doc.OwnerFamily
            cat = Category.GetCategory(self.doc, bic)
            if fam.FamilyCategory is None or fam.FamilyCategory.Id.IntegerValue != cat.Id.IntegerValue:
                fam.FamilyCategory = cat
                self.log.ok(u'Categoria cambiada a ' + cat.Name)
            tname = self.spec['familia']['tipo']
            existing = [ft for ft in self.fm.Types if ft.Name == tname]
            self.fm.CurrentType = existing[0] if existing else self.fm.NewType(tname)
            self.log.ok(u'Tipo: ' + tname)

            for key, m in self.spec.get('materiales', {}).items():
                mid = self._material(m['nombre'], m['rgb'], m.get('transp', 0))
                self.mats[key] = mid
            famcat = fam.FamilyCategory
            current = {}
            for sc in famcat.SubCategories:
                current[sc.Name] = sc
            for key, s in self.spec.get('subcategorias', {}).items():
                sc = current.get(s['nombre'])
                if sc is None:
                    sc = self.doc.Settings.Categories.NewSubcategory(famcat, s['nombre'])
                if s.get('mat') in self.mats:
                    sc.Material = self.doc.GetElement(self.mats[s['mat']])
                self.subs[key] = sc
            self.log.ok(u'%d materiales, %d subcategorias' % (len(self.mats), len(self.subs)))
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'setup_family: %s' % ex)

    def _material(self, name, rgb, transp):
        for m in FilteredElementCollector(self.doc).OfClass(Material):
            if m.Name == name:
                return m.Id
        mid = Material.Create(self.doc, name)
        m = self.doc.GetElement(mid)
        m.Color = Color(rgb[0], rgb[1], rgb[2])
        m.Transparency = int(transp)
        try:
            m.UseRenderAppearanceForShading = False
        except Exception:
            pass
        return mid

    # ------------------------------------------------------------------ parametros
    def param(self, name, spec_path, group, instance=False, value=None, formula=None):
        fp = self.fm.get_Parameter(name)
        if fp is None:
            fp = self.fm.AddParameter(name, group, _spec(spec_path), instance)
        self.params[name] = fp
        if value is not None:
            self._set(fp, value)
        if formula:
            self.fm.SetFormula(fp, formula)
        return fp

    def _set(self, fp, value):
        self.fm.Set(fp, value)

    def setup_parameters(self):
        t = self._tx(u'AVSA - parametros')
        try:
            self._shared_loi()
            self._builtin_data()
            self._material_params()
            self._connection_params()
            self._electrical_params()
            self._zone_params()
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'setup_parameters: %s' % ex)

    def _shared_loi(self):
        if not self.spf or not os.path.exists(self.spf):
            self.log.warn(u'Archivo de parametros compartidos no encontrado: %s (LOI omitido)' % self.spf)
            return
        previous = self.app.SharedParametersFilename
        try:
            self.app.SharedParametersFilename = self.spf
            dfile = self.app.OpenSharedParameterFile()
            defs = {}
            for g in dfile.Groups:
                for d in g.Definitions:
                    defs[d.Name] = d
            hoy = datetime.date.today().isoformat()
            for name, inst, value in self.spec.get('loi', []):
                d = defs.get(name)
                if d is None:
                    self.log.warn(u'LOI: %s no esta en el archivo de parametros compartidos' % name)
                    continue
                fp = self.fm.get_Parameter(name)
                if fp is None:
                    fp = self.fm.AddParameter(d, _gid('IdentityData') if inst else _gid('Data'), inst)
                self.params[name] = fp
                if value == '__HOY__':
                    value = hoy
                if value is None:
                    continue
                try:
                    if isinstance(value, float):
                        self._set(fp, value)
                    else:
                        self._set(fp, u'%s' % value)
                except Exception as ex:
                    self.log.err(u'LOI %s = %s' % (name, value), ex)
            self.log.ok(u'LOI: %d parametros compartidos' % len(self.spec.get('loi', [])))
        finally:
            try:
                if previous:
                    self.app.SharedParametersFilename = previous
            except Exception:
                pass

    def _builtin_data(self):
        for bip_name, value in self.spec.get('nativos', {}).items():
            try:
                fp = self.fm.get_Parameter(getattr(BuiltInParameter, bip_name))
                if fp is not None:
                    self._set(fp, value)
            except Exception as ex:
                self.log.err(u'Parametro nativo %s' % bip_name, ex)

    def _material_params(self):
        for key, m in self.spec.get('materiales', {}).items():
            self.param(m['param'], 'Reference.Material', _gid('Materials'), False, self.mats.get(key))

    def _connection_params(self):
        """Parametros de cada boquilla. Las posiciones se miden desde la base de la boquilla a lo largo
        de su eje; todo cuelga de <id>_Proyeccion (cara de la brida = ubicacion del conector)."""
        g = _gid('Mechanical', 'Plumbing')
        for b in self.spec.get('boquillas', []):
            p = b['id']
            L = lambda n: p + '_' + n
            self.param(L('Proyeccion'), 'Length', g, False, b['proyeccion'] * MM)
            self.param(L('Brida_Espesor'), 'Length', g, False, b['e_brida'] * MM)
            self.param(L('RF_Alto'), 'Length', g, False, (b.get('rf') or {}).get('h', 0.0) * MM)
            self.param(L('Cuello_Largo'), 'Length', g, False, (b.get('cuello') or {}).get('l', 0.0) * MM)
            pr = b.get('pernos') or {}
            self.param(L('Tuerca_Alto'), 'Length', g, False, pr.get('h', 0.0) * MM)
            self.param(L('Perno_Saliente'), 'Length', g, False, pr.get('sale', 0.0) * MM)
            self.param(L('RF_Inicio'), 'Length', g, False, formula=L('Proyeccion') + ' - ' + L('RF_Alto'))
            self.param(L('Brida_Inicio'), 'Length', g, False, formula=L('RF_Inicio') + ' - ' + L('Brida_Espesor'))
            self.param(L('Cuello_Inicio'), 'Length', g, False, formula=L('Brida_Inicio') + ' - ' + L('Cuello_Largo'))
            self.param(L('Tuerca_Inicio'), 'Length', g, False, formula=L('Brida_Inicio') + ' - ' + L('Tuerca_Alto'))
            self.param(L('Perno_Fin'), 'Length', g, False, formula=L('Proyeccion') + ' + ' + L('Perno_Saliente'))
            if b['seccion'] == 'circular':
                self.param(L('DN'), 'PipeSize', g, False, b['dn'] * MM)
                self.param(L('Radio'), 'PipeSize', g, False, formula=L('DN') + ' / 2')
            else:
                self.param(L('Ancho'), 'DuctSize', g, False, b['abertura'][0] * MM)
                self.param(L('Alto'), 'DuctSize', g, False, b['abertura'][1] * MM)

    def _electrical_params(self):
        g = _gid('ElectricalLoads', 'Electrical')
        for e in self.spec.get('electricos', []):
            p = e['id']
            self.param(p + '_Tension', 'ElectricalPotential', g, False,
                       UnitUtils.ConvertToInternalUnits(e['tension'], UnitTypeId.Volts))
            self.param(p + '_Polos', 'Int.NumberOfPoles', g, False, int(e['polos']))
            va = e.get('va') or 0.0
            self.param(p + '_Carga_Aparente', 'ApparentPower', g, False,
                       UnitUtils.ConvertToInternalUnits(va, UnitTypeId.VoltAmperes))
            self.param(p + '_Potencia_kW', 'Number', g, False, float(e['kw']) if e.get('kw') else None)

    def _zone_params(self):
        if not self.spec.get('zonas'):
            return
        self.param('Mostrar_Zonas_Servicio', 'Boolean.YesNo', _gid('Graphics', 'Visibility'), True, 1)
        for z in self.spec['zonas']:
            self.param(z['param'], 'Length', _gid('Constraints', 'Geometry'), True, z['largo'] * MM)

    # ------------------------------------------------------------------ geometria basica
    def _sketch_plane(self, normal, origin):
        return SketchPlane.Create(self.doc, Plane.CreateByNormalAndOrigin(normal, origin))

    @staticmethod
    def _poly(points):
        ca = CurveArray()
        n = len(points)
        for i in range(n):
            ca.Append(Line.CreateBound(points[i], points[(i + 1) % n]))
        return ca

    @staticmethod
    def _rect(c, u, v, hu, hv):
        """Rectangulo centrado en c (XYZ), semilados hu/hv (pies) sobre ejes u/v (XYZ)."""
        p = [c.Add(u.Multiply(su * hu)).Add(v.Multiply(sv * hv)) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        return FamilyBuilder._poly(p)

    @staticmethod
    def _circle(c, u, v, r):
        ca = CurveArray()
        a, b = c.Add(u.Multiply(r)), c.Subtract(u.Multiply(r))
        ca.Append(Arc.Create(a, b, c.Add(v.Multiply(r))))
        ca.Append(Arc.Create(b, a, c.Subtract(v.Multiply(r))))
        return ca

    def _loop(self, lz, axis, coord):
        """Lazo 2D del spec (coordenadas u, v en mm) -> CurveArray en el plano axis = coord."""
        ku, kv = SEC[axis]
        u, v = vec(ku), vec(kv)

        def P(pu, pv):
            return pt({axis: coord, ku: pu, kv: pv})
        t = lz['t']
        if t == 'rect':
            return self._rect(P(*lz['c']), u, v, lz['d'][0] / 2 * MM, lz['d'][1] / 2 * MM)
        if t == 'circ':
            return self._circle(P(*lz['c']), u, v, lz['r'] * MM)
        if t == 'poly':
            return self._poly([P(a, b) for a, b in lz['pts']])
        if t == 'hex':
            cu, cv = lz['c']
            R = lz['s'] / math.sqrt(3.0)
            return self._poly([P(cu + R * math.cos(math.pi / 3 * i), cv + R * math.sin(math.pi / 3 * i))
                               for i in range(6)])
        if t == 'rrect':
            cu, cv = lz['c']
            hu, hv = lz['d'][0] / 2.0, lz['d'][1] / 2.0
            r = min(lz['r'], hu - 0.5, hv - 0.5)
            k = r * (1 - math.sqrt(0.5))
            ca = CurveArray()
            ca.Append(Line.CreateBound(P(cu - hu + r, cv - hv), P(cu + hu - r, cv - hv)))
            ca.Append(Arc.Create(P(cu + hu - r, cv - hv), P(cu + hu, cv - hv + r), P(cu + hu - k, cv - hv + k)))
            ca.Append(Line.CreateBound(P(cu + hu, cv - hv + r), P(cu + hu, cv + hv - r)))
            ca.Append(Arc.Create(P(cu + hu, cv + hv - r), P(cu + hu - r, cv + hv), P(cu + hu - k, cv + hv - k)))
            ca.Append(Line.CreateBound(P(cu + hu - r, cv + hv), P(cu - hu + r, cv + hv)))
            ca.Append(Arc.Create(P(cu - hu + r, cv + hv), P(cu - hu, cv + hv - r), P(cu - hu + k, cv + hv - k)))
            ca.Append(Line.CreateBound(P(cu - hu, cv + hv - r), P(cu - hu, cv - hv + r)))
            ca.Append(Arc.Create(P(cu - hu, cv - hv + r), P(cu - hu + r, cv - hv), P(cu - hu + k, cv - hv + k)))
            return ca
        if t == 'u':
            # canaleta: fondo semicircular de radio r centrado en c, paredes rectas hasta v = tope
            cu, cv = lz['c']
            r, top = lz['r'], lz['tope']
            ca = CurveArray()
            ca.Append(Arc.Create(P(cu - r, cv), P(cu + r, cv), P(cu, cv - r)))
            ca.Append(Line.CreateBound(P(cu + r, cv), P(cu + r, top)))
            ca.Append(Line.CreateBound(P(cu + r, top), P(cu - r, top)))
            ca.Append(Line.CreateBound(P(cu - r, top), P(cu - r, cv)))
            return ca
        raise Exception(u'lazo desconocido: %s' % t)

    def _extrude(self, solid, profile, normal, origin, depth):
        caa = CurveArrArray()
        caa.Append(profile)
        return self.doc.FamilyCreate.NewExtrusion(solid, caa, self._sketch_plane(normal, origin), depth)

    def _extrude_loops(self, solid, loops, axis, rango):
        a0, a1 = rango
        caa = CurveArrArray()
        for lz in loops:
            caa.Append(self._loop(lz, axis, a0))
        ku, kv = SEC[axis]
        sp = self._sketch_plane(vec(axis), pt({axis: a0, ku: 0.0, kv: 0.0}))
        return self.doc.FamilyCreate.NewExtrusion(solid, caa, sp, (a1 - a0) * MM)

    def _finish(self, el, s, sub_default='cuerpo'):
        sub = self.subs.get(s.get('sub', sub_default))
        if sub is not None:
            el.Subcategory = sub
        mkey = s.get('mat', s.get('sub', sub_default))
        mparam = self.spec.get('materiales', {}).get(mkey, {}).get('param')
        if mparam and mparam in self.params:
            self.fm.AssociateElementParameterToFamilyParameter(
                el.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM), self.params[mparam])
        if s.get('nivel') == 'fino':
            # piezas menores (pernos, manijas, sensores): ocultas en nivel de detalle Bajo
            vis = FamilyElementVisibility(FamilyElementVisibilityType.Model)
            vis.IsShownInCoarse = False
            el.SetVisibility(vis)

    def make_solid(self, s, solid=True):
        f = s['forma']
        if f == 'caja':
            (x0, x1), (y0, y1), (z0, z1) = s['x'], s['y'], s['z']
            lz = {'t': 'rect', 'c': ((x0 + x1) / 2.0, (y0 + y1) / 2.0), 'd': (x1 - x0, y1 - y0)}
            return self._extrude_loops(solid, [lz], 'Z', (z0, z1))
        if f == 'cilindro':
            lz = {'t': 'circ', 'c': s['centro'], 'r': s['r']}
            return self._extrude_loops(solid, [lz], s['eje'], s['rango'])
        if f == 'ext':
            return self._extrude_loops(solid, s['lazos'], s['eje'], s['rango'])
        if f == 'transicion':
            z0, z1 = s['z']
            bx, by, bdx, bdy = s['base']
            tx, ty, tdx, tdy = s['tope']
            cb, ct = xyz((bx, by, z0)), xyz((tx, ty, z1))
            base = self._rect(cb, XYZ.BasisX, XYZ.BasisY, bdx / 2 * MM, bdy / 2 * MM)
            top = self._rect(ct, XYZ.BasisX, XYZ.BasisY, tdx / 2 * MM, tdy / 2 * MM)
            sp = self._sketch_plane(XYZ.BasisZ, cb)
            return self.doc.FamilyCreate.NewBlend(solid, top, base, sp)
        raise Exception(u'forma desconocida: %s' % f)

    def build_geometry(self):
        t = self._tx(u'AVSA - geometria LOD 350')
        try:
            for s in self.spec.get('solidos', []):
                try:
                    el = self.make_solid(s, True)
                    self._finish(el, s)
                    self.elems[s['id']] = el
                except Exception as ex:
                    self.log.err(u'Solido %s' % s['id'], ex)
            self.doc.Regenerate()
            for s in self.spec.get('vacios', []):
                try:
                    el = self.make_solid(s, False)
                    self.elems[s['id']] = el
                    target = self.elems.get(s.get('corta'))
                    if target is not None:
                        self.doc.Regenerate()
                        SolidSolidCutUtils.AddCutBetweenSolids(self.doc, target, el)
                except Exception as ex:
                    self.log.err(u'Vacio %s' % s['id'], ex)
            self.log.ok(u'Geometria: %d solidos, %d vacios' % (len(self.spec.get('solidos', [])),
                                                              len(self.spec.get('vacios', []))))
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'build_geometry: %s' % ex)

    # ------------------------------------------------------------------ boquillas + conectores
    def _assoc(self, el, bip, pname):
        p = el.get_Parameter(bip)
        if p is None:
            raise Exception(u'%s no tiene %s' % (el.Id, bip))
        self.fm.AssociateElementParameterToFamilyParameter(p, self.params[pname])

    def _face(self, el, normal, point, tol=0.002):
        opt = Options()
        opt.ComputeReferences = True
        opt.DetailLevel = ViewDetailLevel.Fine
        best = None
        for g in el.get_Geometry(opt):
            if not isinstance(g, Solid):
                continue
            for f in g.Faces:
                if isinstance(f, PlanarFace) and f.FaceNormal.DotProduct(normal) > 0.999:
                    d = abs(f.Origin.Subtract(point).DotProduct(normal))
                    if d < tol and (best is None or f.Area > best.Area):
                        best = f
        return best

    def build_nozzles(self):
        t = self._tx(u'AVSA - boquillas y conectores')
        try:
            for b in self.spec.get('boquillas', []):
                try:
                    self._nozzle(b)
                except Exception as ex:
                    self.log.err(u'Boquilla %s' % b['id'], ex)
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'build_nozzles: %s' % ex)

    def _nozzle_layer(self, b, loops, start_param, end_param, start_mm, end_mm, style):
        """Extrusion a lo largo del eje de la boquilla, con inicio/fin ligados a parametros de tipo."""
        n = vec(b['eje'])
        ax = b['eje'][-1]
        sgn = -1.0 if b['eje'].startswith('-') else 1.0
        ku, kv = SEC[ax]
        base = dict(zip(('X', 'Y', 'Z'), b['base']))
        caa = CurveArrArray()
        for lz in loops:
            caa.Append(self._loop(lz, ax, base[ax]))
        c = xyz(b['base'])
        sp = self._sketch_plane(n, c)
        el = self.doc.FamilyCreate.NewExtrusion(True, caa, sp, end_mm * MM)
        el.get_Parameter(BuiltInParameter.EXTRUSION_START_PARAM).Set(start_mm * MM)
        self._finish(el, style)
        if start_param:
            self._assoc(el, BuiltInParameter.EXTRUSION_START_PARAM, b['id'] + '_' + start_param)
        if end_param:
            self._assoc(el, BuiltInParameter.EXTRUSION_END_PARAM, b['id'] + '_' + end_param)
        return el

    def _nozzle(self, b):
        p = b['id']
        n = vec(b['eje'])
        ax = b['eje'][-1]
        ku, kv = SEC[ax]
        base = dict(zip(('X', 'Y', 'Z'), b['base']))
        cu, cv = base[ku], base[kv]
        circ = b['seccion'] == 'circular'
        L = b['proyeccion']
        e = b['e_brida']
        rf = b.get('rf') or {}
        cuello = b.get('cuello') or {}
        pr = b.get('pernos') or {}
        rf_h = rf.get('h', 0.0)
        f0 = L - rf_h - e                      # inicio de la brida
        cl = cuello.get('l', 0.0)

        if circ:
            hole = {'t': 'circ', 'c': (cu, cv), 'r': b['d_interior'] / 2.0}
            body = [{'t': 'circ', 'c': (cu, cv), 'r': b['d_tubo'] / 2.0}, hole]
            fl = [{'t': 'circ', 'c': (cu, cv), 'r': b['d_brida'] / 2.0}, hole]
        else:
            hole = {'t': 'rect', 'c': (cu, cv), 'd': b['abertura']}
            body = [{'t': 'rect', 'c': (cu, cv), 'd': b['cuerpo']}, hole]
            fl = [{'t': 'rect', 'c': (cu, cv), 'd': b['brida']}, hole]
        holes = [{'t': 'circ', 'c': q, 'r': pr['d_agujero'] / 2.0} for q in pr.get('pos', [])]
        cuerpo = {'sub': 'cuerpo', 'mat': 'cuerpo'}
        conn = {'sub': 'conexiones', 'mat': 'conexiones'}
        perno = {'sub': 'conexiones', 'mat': 'pernos', 'nivel': 'fino'}

        # tubo / ducto hueco desde la base hasta el cuello o la brida
        tube_end = 'Cuello_Inicio' if cl > 0 else 'Brida_Inicio'
        self.elems[p + '_tubo'] = self._nozzle_layer(b, body, None, tube_end, 0.0, f0 - cl, cuerpo)
        if cl > 0:
            neck = [{'t': 'circ', 'c': (cu, cv), 'r': cuello['d'] / 2.0}, hole]
            self.elems[p + '_cuello'] = self._nozzle_layer(b, neck, 'Cuello_Inicio', 'Brida_Inicio',
                                                           f0 - cl, f0, conn)
        # brida con agujeros de pernos
        flange_end = 'RF_Inicio' if rf_h > 0 else 'Proyeccion'
        fl_el = self._nozzle_layer(b, fl + holes, 'Brida_Inicio', flange_end, f0, L - rf_h, conn)
        self.elems[p + '_brida'] = fl_el
        face_el = fl_el
        if rf_h > 0:
            rfl = [{'t': 'circ', 'c': (cu, cv), 'r': rf['d'] / 2.0}, hole]
            face_el = self._nozzle_layer(b, rfl, 'RF_Inicio', 'Proyeccion', L - rf_h, L, conn)
            self.elems[p + '_rf'] = face_el
        # esparragos + tuercas del lado del equipo
        if pr.get('pos'):
            studs = [{'t': 'circ', 'c': q, 'r': pr['d'] / 2.0} for q in pr['pos']]
            nuts = [{'t': 'hex', 'c': q, 's': pr['s']} for q in pr['pos']]
            self.elems[p + '_esparragos'] = self._nozzle_layer(
                b, studs, 'Tuerca_Inicio', 'Perno_Fin', f0 - pr['h'], L + pr['sale'], perno)
            self.elems[p + '_tuercas'] = self._nozzle_layer(
                b, nuts, 'Tuerca_Inicio', 'Brida_Inicio', f0 - pr['h'], f0, perno)
        self.doc.Regenerate()

        face = self._face(face_el, n, xyz(b['base']).Add(n.Multiply(L * MM)))
        if face is None:
            raise Exception(u'no se encontro la cara de la brida')
        if b['tipo'] == 'tuberia':
            st = getattr(PipeSystemType, b.get('sistema', 'OtherPipe'), PipeSystemType.OtherPipe)
            ce = ConnectorElement.CreatePipeConnector(self.doc, st, face.Reference)
            try:
                self._assoc(ce, BuiltInParameter.CONNECTOR_RADIUS, p + '_Radio')
            except Exception:
                self._assoc(ce, BuiltInParameter.CONNECTOR_DIAMETER, p + '_DN')
            self._flow(ce, BuiltInParameter.RBS_PIPE_FLOW_DIRECTION_PARAM, b.get('flujo'))
        else:
            st = getattr(DuctSystemType, b.get('sistema', 'OtherAir'), None)
            if st is None:
                st = DuctSystemType.SupplyAir
                self.log.warn(u'%s: DuctSystemType %s no existe, se usa SupplyAir' % (p, b.get('sistema')))
            ce = ConnectorElement.CreateDuctConnector(self.doc, st, ConnectorProfileType.Rectangular, face.Reference)
            self._assoc(ce, BuiltInParameter.CONNECTOR_WIDTH, p + '_Ancho')
            self._assoc(ce, BuiltInParameter.CONNECTOR_HEIGHT, p + '_Alto')
            self._flow(ce, BuiltInParameter.RBS_DUCT_FLOW_DIRECTION_PARAM, b.get('flujo'))
        self._describe(ce, b.get('descripcion'))
        self.elems[p] = ce
        self.log.ok(u'Conector %s (%s): brida + %d pernos' % (p, b['nombre'], len(pr.get('pos', []))))

    def _flow(self, ce, bip, flujo):
        if not flujo:
            return
        try:
            val = _enum_int(getattr(FlowDirectionType, flujo), {'Bidirectional': 0, 'In': 1, 'Out': 2}[flujo])
            ce.get_Parameter(bip).Set(val)
        except Exception as ex:
            self.log.warn(u'Direccion de flujo no asignada: %s' % _txt(ex))

    def _describe(self, ce, text):
        if not text:
            return
        try:
            ce.get_Parameter(BuiltInParameter.RBS_CONNECTOR_DESCRIPTION).Set(text)
        except Exception:
            pass

    def build_electrical(self):
        if not self.spec.get('electricos'):
            return
        t = self._tx(u'AVSA - conectores electricos')
        try:
            for e in self.spec['electricos']:
                try:
                    host = self.elems[e['en']]
                    s = [x for x in self.spec['solidos'] if x['id'] == e['en']][0]
                    n = vec(e['cara'])
                    ax = AXIS[e['cara'][-1]]
                    rng = (s['x'], s['y'], s['z'])[ax]
                    coord = rng[1] if not e['cara'].startswith('-') else rng[0]
                    p = [(r[0] + r[1]) / 2 for r in (s['x'], s['y'], s['z'])]
                    p[ax] = coord
                    face = self._face(host, n, xyz(p))
                    if face is None:
                        raise Exception(u'cara %s no encontrada en %s' % (e['cara'], e['en']))
                    ce = ConnectorElement.CreateElectricalConnector(self.doc, ElectricalSystemType.PowerBalanced,
                                                                    face.Reference)
                    self._assoc(ce, BuiltInParameter.RBS_ELEC_VOLTAGE, e['id'] + '_Tension')
                    self._assoc(ce, BuiltInParameter.RBS_ELEC_NUMBER_OF_POLES, e['id'] + '_Polos')
                    self._assoc(ce, BuiltInParameter.RBS_ELEC_APPARENT_LOAD, e['id'] + '_Carga_Aparente')
                    self._describe(ce, e.get('descripcion'))
                    self.log.ok(u'Conector electrico %s (%s)' % (e['id'], e['nombre']))
                except Exception as ex:
                    self.log.err(u'Conector electrico %s' % e['id'], ex)
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'build_electrical: %s' % ex)

    # ------------------------------------------------------------------ zonas de servicio
    def build_zones(self):
        if not self.spec.get('zonas'):
            return
        t = self._tx(u'AVSA - zonas de servicio')
        try:
            vis = self.params.get('Mostrar_Zonas_Servicio')
            for z in self.spec['zonas']:
                try:
                    n = vec(z['normal'])
                    ax = z['normal'][-1]
                    ku, kv = SEC[ax]
                    p = {ax: z['plano'], ku: (z['u'][0] + z['u'][1]) / 2, kv: (z['v'][0] + z['v'][1]) / 2}
                    c = pt(p)
                    prof = self._rect(c, vec(ku), vec(kv), (z['u'][1] - z['u'][0]) / 2 * MM,
                                      (z['v'][1] - z['v'][0]) / 2 * MM)
                    el = self._extrude(True, prof, n, c, z['largo'] * MM)
                    self._finish(el, {'sub': 'zonas', 'mat': 'zonas'})
                    self._assoc(el, BuiltInParameter.EXTRUSION_END_PARAM, z['param'])
                    if vis is not None:
                        self.fm.AssociateElementParameterToFamilyParameter(
                            el.get_Parameter(BuiltInParameter.IS_VISIBLE_PARAM), vis)
                    self.elems[z['id']] = el
                    self.log.ok(u'Zona %s (%s) %.0f mm' % (z['id'], z['nombre'], z['largo']))
                except Exception as ex:
                    self.log.err(u'Zona %s' % z['id'], ex)
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'build_zones: %s' % ex)

    # ------------------------------------------------------------------ planos de referencia (anclajes, ejes)
    def build_reference_planes(self):
        rps = self.spec.get('planos_referencia', [])
        if not rps:
            return
        plan = [v for v in FilteredElementCollector(self.doc).OfClass(ViewPlan) if not v.IsTemplate]
        elev = [v for v in FilteredElementCollector(self.doc).OfClass(View)
                if not v.IsTemplate and v.ViewType == ViewType.Elevation]
        t = self._tx(u'AVSA - planos de referencia')
        try:
            big = 2000 * MM
            for name, axis, value in rps:
                try:
                    if axis == 'Z':
                        if not elev:
                            raise Exception(u'sin vista de alzado en la plantilla')
                        o = XYZ(0, 0, value * MM)
                        rp = None
                        for view in elev:
                            try:   # plano horizontal = linea en X + tercer punto en Y
                                rp = self.doc.FamilyCreate.NewReferencePlane2(
                                    o.Subtract(XYZ.BasisX.Multiply(big)), o.Add(XYZ.BasisX.Multiply(big)),
                                    o.Add(XYZ.BasisY.Multiply(big)), view)
                                break
                            except Exception:
                                rp = None
                        if rp is None:
                            raise Exception(u'NewReferencePlane2 fallo en todas las vistas de alzado')
                    else:
                        if not plan:
                            raise Exception(u'sin vista de planta en la plantilla')
                        along = XYZ.BasisY if axis == 'X' else XYZ.BasisX
                        o = XYZ(value * MM, 0, 0) if axis == 'X' else XYZ(0, value * MM, 0)
                        rp = self.doc.FamilyCreate.NewReferencePlane(o.Subtract(along.Multiply(big)),
                                                                     o.Add(along.Multiply(big)), XYZ.BasisZ, plan[0])
                    rp.Name = name
                    try:
                        rp.get_Parameter(BuiltInParameter.ELEM_REFERENCE_NAME).Set(
                            _enum_int(FamilyInstanceReferenceType.WeakReference, 14))
                    except Exception:
                        pass
                except Exception as ex:
                    self.log.err(u'Plano de referencia %s' % name, ex)
            self.log.ok(u'%d planos de referencia' % len(rps))
            t.Commit()
        except Exception as ex:
            t.RollBack()
            raise Exception(u'build_reference_planes: %s' % ex)

    # ------------------------------------------------------------------ guardar / cargar
    def save(self, out_dir):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        path = os.path.join(out_dir, self.spec['familia']['nombre_archivo'] + '.rfa')
        opts = SaveAsOptions()
        opts.OverwriteExistingFile = True
        opts.MaximumBackups = 1
        self.doc.SaveAs(path, opts)
        self.log.ok(u'Guardado: ' + path)
        return path

    def load_into(self, project_doc):
        """Carga/recarga en el proyecto. El proyecto NO debe tener transaccion abierta."""
        try:
            opts = _family_load_options()
            fam = self.doc.LoadFamily(project_doc, opts)
            self.log.ok(u'Familia cargada en el proyecto: %s' % fam.Name)
            return fam
        except Exception as ex:
            self.log.warn(u'No se pudo cargar con LoadFamily (%s). Cargue el .rfa manualmente '
                          u'(Insertar > Cargar familia > Sobrescribir version existente).' % _txt(ex))
            return None

    def close(self):
        try:
            self.doc.Close(False)
        except Exception:
            pass

    # ------------------------------------------------------------------ todo
    def run(self, out_dir, project_doc=None):
        self.create_document()
        try:
            self.setup_family()
            self.setup_parameters()
            self.build_reference_planes()
            self.build_geometry()
            self.build_nozzles()
            self.build_electrical()
            self.build_zones()
            path = self.save(out_dir)
            if project_doc is not None:
                self.load_into(project_doc)
            return path
        finally:
            self.close()


def _family_load_options():
    """IFamilyLoadOptions que sobrescribe la familia y sus valores. Funciona en IronPython y PythonNet."""
    def on_found(self, familyInUse, overwriteParameterValues):
        try:
            overwriteParameterValues.Value = True      # IronPython (StrongBox)
            return True
        except Exception:
            return (True, True)                        # PythonNet (parametros out como tupla)

    def on_shared(self, sharedFamily, familyInUse, source, overwriteParameterValues):
        try:
            source.Value = FamilySource.Family
            overwriteParameterValues.Value = True
            return True
        except Exception:
            return (True, FamilySource.Family, True)

    attrs = {'OnFamilyFound': on_found, 'OnSharedFamilyFound': on_shared,
             '__namespace__': 'AVSA_FamilyBuilder_%d' % int(time.time() * 1000)}
    cls = type('AvsaFamilyLoadOptions', (IFamilyLoadOptions,), attrs)
    return cls()


def load_spec(path):
    """Carga un archivo spec_*.py por ruta (CPython3 e IronPython)."""
    try:
        import importlib.util as ilu
        s = ilu.spec_from_file_location('avsa_spec_%d' % int(time.time() * 1000), path)
        m = ilu.module_from_spec(s)
        s.loader.exec_module(m)
    except ImportError:
        import imp
        m = imp.load_source('avsa_spec_%d' % int(time.time() * 1000), path)
    return m.SPEC
