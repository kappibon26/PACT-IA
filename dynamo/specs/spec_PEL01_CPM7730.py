# -*- coding: utf-8 -*-
"""
Especificacion de familia: Peletizadora CPM 7730-8 + acondicionador 30LTC13HS + alimentador INF12
Proyecto AVSA - MACPOLLO (Planta de Pienso Horizonte).  Estandar ad-STD-AVSA-003 (LOI de familias).

Fuentes:
  - PELLET_MAGDALENA.dxf = CPM "General Dimension Drawing", Joe 2022.12.09, revisado por Ivan Orejarena
    2022-12-16.  Dibujo en mm a escala 1:1, proyeccion en 3er angulo.  Las vistas de detalle (A-A, B-B,
    C-C, entrada del alimentador) NO estan a escala: se usan las cotas escritas.
  - Catalogo CPM serie 7700 (onecpm.com): 7730-8 = dado 762 mm (30") x 209 mm, 300 HP.
  - Foto de referencia del conjunto (acabado gris claro, base y motor principal negros, alimentador en
    canaleta U, acondicionador por tramos con aros bridados, puerta del dado con bisagras y cierres).
  - Bridas de vapor: ASME B16.5 8" Clase 150 WN-RF (OD 343, espesor 28.4, RF 269.9 x 1.6,
    8 pernos 3/4" en circulo de 298.5, agujeros 22.2).

SISTEMA DE COORDENADAS DE LA FAMILIA (mm)
  Origen  = borde frontal de la base del molino (lado puerta) / eje longitudinal de la maquina / piso (NPT).
  +X      = a lo largo del acondicionador, desde la puerta del molino hacia los motores.
  +Y      = hacia el lado izquierdo de la vista frontal del CAD (lado de las bisagras / lubricacion).
  +Z      = arriba.
Conversion desde el CAD:
  vista lateral  (derecha):  X = x_cad - 17592.2      Z = y_cad - 274.4
  vista frontal  (puerta):   Y = 14337.3 - x_cad      Z = y_cad - 274.4

Formas (las lee dynamo/lib/ad_family_builder.py y herramientas/preview_spec.py):
  caja       : x, y, z = (min, max)
  cilindro   : eje 'X'|'Y'|'Z', centro = las otras dos coordenadas en orden (X->(y,z), Y->(x,z), Z->(x,y)),
               r = radio, rango = (min, max) a lo largo del eje
  ext        : extrusion de varios lazos sobre el plano normal a 'eje' (coordenadas u, v como en cilindro).
               Lazos anidados = huecos; lazos separados = varios solidos en un mismo elemento.
               Tipos de lazo: rect, rrect (redondeado), circ, hex (entre caras), poly, u (canaleta).
  transicion : z = (z_base, z_tope); base / tope = (cx, cy, dx, dy) -> rectangulos horizontales
  'nivel': 'fino' -> se oculta en nivel de detalle Bajo (pernos, manijas, sensores...)
  'aprox': True   -> posicion no acotada en el CAD (AM_Confianza_Dimensional = Media)
"""
import math


# ============================================================================ helpers
def _sol(id_, forma, sub, mat, kw):
    d = {'id': id_, 'forma': forma, 'sub': sub, 'mat': mat or sub}
    d.update(kw)
    return d


def caja(id_, x, y, z, sub='cuerpo', mat=None, **kw):
    kw.update(x=x, y=y, z=z)
    return _sol(id_, 'caja', sub, mat, kw)


def cil(id_, eje, centro, r, rango, sub='cuerpo', mat=None, **kw):
    kw.update(eje=eje, centro=centro, r=r, rango=rango)
    return _sol(id_, 'cilindro', sub, mat, kw)


def ext(id_, eje, rango, lazos, sub='cuerpo', mat=None, **kw):
    kw.update(eje=eje, rango=rango, lazos=lazos)
    return _sol(id_, 'ext', sub, mat, kw)


def R(c, d):
    return {'t': 'rect', 'c': c, 'd': d}


def RR(c, d, r):
    return {'t': 'rrect', 'c': c, 'd': d, 'r': r}


def C(c, r):
    return {'t': 'circ', 'c': c, 'r': r}


def H(c, s):
    return {'t': 'hex', 'c': c, 's': s}


def U(c, r, tope):
    return {'t': 'u', 'c': c, 'r': r, 'tope': tope}


def aletas(c, r, n, h, w):
    """Carcasa de motor TEFC: circulo de radio r con n aletas de alto h y ancho w."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        da = w / 2.0 / r
        for rr, aa in ((r, a - da), (r + h, a - da), (r + h, a + da), (r, a + da)):
            pts.append((round(c[0] + rr * math.cos(aa), 3), round(c[1] + rr * math.sin(aa), 3)))
    return {'t': 'poly', 'pts': pts}


def perimetro(cu, cv, us, vs):
    """Agujeros en el perimetro de una grilla: us / vs = listas de posiciones relativas."""
    out = []
    for a in us:
        for b in vs:
            if a in (us[0], us[-1]) or b in (vs[0], vs[-1]):
                out.append((round(cu + a, 2), round(cv + b, 2)))
    return out


def paso(n, p):
    """n posiciones centradas con paso p."""
    return [round((i - (n - 1) / 2.0) * p, 3) for i in range(n)]


def circulo_pernos(cu, cv, n, dc, a0=None):
    a0 = math.pi / n if a0 is None else a0
    return [(round(cu + dc / 2.0 * math.cos(a0 + 2 * math.pi * i / n), 3),
             round(cv + dc / 2.0 * math.sin(a0 + 2 * math.pi * i / n), 3)) for i in range(n)]


# pernos: d = diametro, s = entre caras de la tuerca, h = alto de tuerca
PERNO = {
    'M10': {'d': 10.0, 's': 16.0, 'h': 8.0},
    'M12': {'d': 12.0, 's': 18.0, 'h': 10.0},
    'M24': {'d': 24.0, 's': 36.0, 'h': 19.0},
    '3/4': {'d': 19.05, 's': 28.6, 'h': 16.7},
}


def junta_bridada(id_, eje, cara, lazo_ext, lazo_abertura, pos, d_ag, perno, e1, e2):
    """Dos bridas enfrentadas en la coordenada 'cara' (brida 1 detras, brida 2 delante), con
    agujeros, esparragos pasantes y tuercas a ambos lados.  Devuelve una lista de solidos."""
    pb = PERNO[perno]
    agujeros = [C(q, d_ag / 2.0) for q in pos]
    sale = pb['h'] + pb['d'] * 0.5
    return [
        ext(id_ + '_brida1', eje, (cara - e1, cara), [lazo_ext, lazo_abertura] + agujeros, 'conexiones'),
        ext(id_ + '_brida2', eje, (cara, cara + e2), [lazo_ext, lazo_abertura] + agujeros, 'conexiones'),
        ext(id_ + '_esparragos', eje, (cara - e1 - sale, cara + e2 + sale), [C(q, pb['d'] / 2.0) for q in pos],
            'conexiones', 'pernos', nivel='fino'),
        ext(id_ + '_tuercas1', eje, (cara - e1 - pb['h'], cara - e1), [H(q, pb['s']) for q in pos],
            'conexiones', 'pernos', nivel='fino'),
        ext(id_ + '_tuercas2', eje, (cara + e2, cara + e2 + pb['h']), [H(q, pb['s']) for q in pos],
            'conexiones', 'pernos', nivel='fino'),
    ]


def pernos_boquilla(perno, pos, d_ag, sale):
    d = dict(PERNO[perno])
    d.update(pos=pos, d_agujero=d_ag, sale=sale)
    return d


# ============================================================================ datos de geometria
Z_ACOND = 2263.2            # eje del acondicionador (circulo D889 de la vista frontal)
R_ACOND = 444.5
Z_ALIM = 3187.7             # eje del alimentador (circulo D393.7)
Z_DADO = 905.0              # eje del dado (circulo R665)
Z_MOTOR = 581.0             # eje del motor principal (cuerpo z 275-887)
Z_MOT_ACOND = 2456.0
Z_MOT_ALIM = 3280.6
PUERTAS_ACOND = [102.0, 953.0, 1804.0, 2655.0]          # centros X de las 4 puertas laterales (722 de ancho)
JUNTAS_ACOND = [527.5, 1378.5, 2229.5]                  # aros bridados entre tramos
ANCLAJES = [(162.0, 723.0), (162.0, -617.0), (1882.0, 723.0), (1882.0, -617.0)]

# --- piezas
SOLIDOS = []

# ---------------------------------------------------------------- base (skid de perfiles, negro)
SOLIDOS += [
    ext('base', 'Z', (0.0, 165.0), [R((1250.0, 53.0), (2500.0, 1410.0)), R((1250.0, 53.0), (2340.0, 1250.0))],
        'estructura'),
    ext('base_travesanos', 'Z', (0.0, 165.0),
        [R((600.0, 53.0), (80.0, 1250.0)), R((1280.0, 53.0), (80.0, 1250.0)), R((2140.0, 53.0), (80.0, 1250.0))],
        'estructura'),
    ext('base_placa_motor', 'Z', (145.0, 165.0), [R((1710.0, 53.0), (940.0, 1250.0))], 'estructura'),
    caja('pedestal_molino', (0.0, 632.0), (-580.0, 580.0), (165.0, 240.0), 'estructura'),
    # pernos de anclaje M24 con arandela y tuerca sobre el perfil de la base
    ext('anclaje_pernos', 'Z', (0.0, 230.0), [C(q, 12.0) for q in ANCLAJES], 'estructura', 'pernos', nivel='fino'),
    ext('anclaje_arandelas', 'Z', (165.0, 170.0), [C(q, 25.0) for q in ANCLAJES], 'estructura', 'pernos', nivel='fino'),
    ext('anclaje_tuercas', 'Z', (170.0, 189.0), [H(q, 36.0) for q in ANCLAJES], 'estructura', 'pernos', nivel='fino'),
]

# ---------------------------------------------------------------- molino 7730-8
SOLIDOS += [
    # camara del dado (circulo R665) y puerta (R635) con aro
    cil('camara_dado', 'X', (0.0, Z_DADO), 665.0, (-490.0, 90.0)),
    ext('puerta_aro', 'X', (-505.0, -490.0), [C((0.0, Z_DADO), 665.0), C((0.0, Z_DADO), 600.0)]),
    cil('puerta', 'X', (0.0, Z_DADO), 635.0, (-526.0, -490.0)),
    ext('puerta_nervios', 'X', (-546.0, -526.0),
        [R((300.0, Z_DADO), (60.0, 1000.0)), R((-300.0, Z_DADO), (60.0, 1000.0)), R((0.0, Z_DADO + 250.0), (520.0, 50.0))]),
    # bisagras (+Y, frontal x=13662-13683, z 635-1175) y cierres (-Y, frontal x=14990-15015)
    ext('puerta_bisagras', 'Z', (635.0, 1175.0), [C((-505.0, 668.0), 24.0)], nivel='fino'),
    ext('puerta_bisagras_placas', 'X', (-540.0, -490.0),
        [R((655.0, 700.0), (60.0, 110.0)), R((655.0, 1110.0), (60.0, 110.0))], nivel='fino'),
    ext('puerta_cierres', 'X', (-560.0, -490.0),
        [R((-665.0, 740.0), (50.0, 90.0)), R((-665.0, 1070.0), (50.0, 90.0))], nivel='fino'),
    ext('puerta_manija', 'Y', (-100.0, 100.0), [R((-580.0, Z_DADO - 300.0), (40.0, 40.0))], nivel='fino'),
    # boca de alimentacion forzada (lateral 16820-17066, frontal +-200)
    ext('boca_alimentacion', 'X', (-772.0, -526.0), [RR((0.0, 711.5), (400.0, 869.0), 40.0)]),
    ext('boca_alimentacion_mirilla', 'X', (-782.0, -772.0), [RR((0.0, 800.0), (240.0, 300.0), 30.0)], nivel='fino'),
    # carcasa principal (caja redondeada con logo CPM, lateral 17682-18224, z 200-1445)
    ext('carcasa_principal', 'Y', (-580.0, 580.0), [RR((361.0, 822.5), (542.0, 1245.0), 80.0)]),
    ext('carcasa_tapa_lateral', 'Y', (-596.0, -580.0), [RR((361.0, 800.0), (470.0, 860.0), 50.0)]),
    ext('carcasa_tapa_tornillos', 'Y', (-604.0, -596.0),
        [H((361.0 + a, 800.0 + b), 16.0) for a in (-205.0, 205.0) for b in (-400.0, -130.0, 130.0, 400.0)],
        'conexiones', 'pernos', nivel='fino'),
    # reductor del molino, guarda del acople y pasador de corte (lateral 18224-18853)
    ext('reductor_molino', 'Y', (-320.0, 320.0), [RR((766.0, 620.0), (268.0, 910.0), 60.0)]),
    ext('guarda_acople', 'Y', (-250.0, 250.0), [RR((1080.8, 560.0), (361.6, 520.0), 120.0)]),
    caja('pasador_corte_interruptor', (640.0, 720.0), (-360.0, -320.0), (820.0, 1080.0), nivel='fino'),
    # ducto acondicionador -> molino (seccion C-C: abertura 260 x 500, brida 344 x 585)
    ext('ducto_acond_molino_inf', 'Z', (1146.0, 1740.0), [R((-649.0, 0.0), (290.0, 530.0)), R((-649.0, 0.0), (260.0, 500.0))]),
    ext('ducto_acond_molino_sup', 'Z', (1770.0, 1830.0), [R((-649.0, 0.0), (290.0, 530.0)), R((-649.0, 0.0), (260.0, 500.0))]),
]
SOLIDOS += junta_bridada('junta_C-C', 'Z', 1755.0, R((-649.0, 0.0), (344.0, 585.0)), R((-649.0, 0.0), (260.0, 500.0)),
                         perimetro(-649.0, 0.0, paso(3, 140.0), paso(4, 180.0)), 12.0, 'M10', 15.0, 15.0)
SOLIDOS += [
    # sistema de lubricacion (frontal 13497-13867) - posicion X no acotada
    caja('lubricacion_tanque', (-400.0, -100.0), (470.0, 840.0), (0.0, 420.0), aprox=True),
    cil('lubricacion_bomba', 'X', (655.0, 500.0), 70.0, (-390.0, -170.0), 'motores', 'reductores', aprox=True),
    cil('lubricacion_filtro', 'Z', (-140.0, 560.0), 45.0, (420.0, 615.0), aprox=True, nivel='fino'),
]

# ---------------------------------------------------------------- motor principal 300 HP 60 Hz / 460 V (TEFC)
SOLIDOS += [
    ext('motor_ppal', 'X', (1300.0, 2120.0), [aletas((0.0, Z_MOTOR), 280.0, 40, 26.0, 10.0)], 'motores'),
    cil('motor_ppal_escudo_lc', 'X', (0.0, Z_MOTOR), 300.0, (1261.6, 1300.0), 'motores'),
    cil('motor_ppal_escudo_lo', 'X', (0.0, Z_MOTOR), 300.0, (2120.0, 2162.9), 'motores'),
    cil('motor_ppal_ventilador', 'X', (0.0, Z_MOTOR), 295.0, (2162.9, 2276.6), 'motores'),
    ext('motor_ppal_rejilla', 'X', (2276.6, 2281.6), [C((0.0, Z_MOTOR), 260.0), C((0.0, Z_MOTOR), 60.0)], 'motores'),
    cil('motor_ppal_eje', 'X', (0.0, Z_MOTOR), 50.0, (1180.0, 1261.6), 'motores', 'pernos'),
    ext('motor_ppal_patas', 'Z', (165.0, 300.0),
        [R((1390.0, 250.0), (120.0, 100.0)), R((1390.0, -250.0), (120.0, 100.0)),
         R((2030.0, 250.0), (120.0, 100.0)), R((2030.0, -250.0), (120.0, 100.0))], 'motores'),
    ext('motor_ppal_patas_pernos', 'Z', (300.0, 318.0),
        [H((x, y), 36.0) for x in (1390.0, 2030.0) for y in (250.0, -250.0)], 'motores', 'pernos', nivel='fino'),
    ext('motor_ppal_ojal_izaje', 'Y', (-15.0, 15.0), [C((1710.0, 900.0), 45.0), C((1710.0, 900.0), 25.0)], 'motores', nivel='fino'),
    caja('motor_ppal_caja_bornes', (1508.0, 1708.0), (-426.0, -290.0), (526.0, 726.0), 'motores'),
    cil('motor_ppal_prensaestopa', 'Z', (1608.0, -358.0), 32.0, (470.0, 526.0), 'motores', nivel='fino'),
]

# ---------------------------------------------------------------- acondicionador 30LTC13HS
SOLIDOS += [
    cil('acond_cuerpo', 'X', (0.0, Z_ACOND), R_ACOND, (-829.3, 3095.8)),
    cil('acond_tapa_izq', 'X', (0.0, Z_ACOND), 480.0, (-854.3, -829.3)),
    cil('acond_tapa_der', 'X', (0.0, Z_ACOND), 480.0, (3095.8, 3120.8)),
]
for i, xj in enumerate(JUNTAS_ACOND):
    pos = circulo_pernos(0.0, Z_ACOND, 20, 924.0)
    SOLIDOS += [
        cil('acond_aro_%d' % (i + 1), 'X', (0.0, Z_ACOND), 480.0, (xj - 12.0, xj + 12.0), 'conexiones'),
        ext('acond_aro_%d_tuercas' % (i + 1), 'X', (xj - 22.0, xj + 22.0), [H(q, 18.0) for q in pos],
            'conexiones', 'pernos', nivel='fino'),
    ]
SOLIDOS += [
    # puertas laterales de inspeccion (lado -Y, 722 x 533, z 2008-2541) con marco, hoja y manijas
    ext('acond_puertas_marco', 'Y', (-452.0, -300.0), [RR((x, 2274.5), (722.0, 533.0), 40.0) for x in PUERTAS_ACOND]),
    ext('acond_puertas_hoja', 'Y', (-462.0, -452.0), [RR((x, 2274.5), (690.0, 500.0), 30.0) for x in PUERTAS_ACOND]),
    ext('acond_puertas_manijas', 'Y', (-490.0, -462.0),
        [R((x + dx, 2274.5), (30.0, 140.0)) for x in PUERTAS_ACOND for dx in (-250.0, 250.0)], nivel='fino'),
    # escotillas superiores (z 2579-2723)
    ext('acond_escotillas', 'Z', (2600.0, 2725.0), [RR((x, 0.0), (722.0, 400.0), 40.0) for x in PUERTAS_ACOND]),
    # eje y chumacera del lado izquierdo (lateral 16385-16737)
    cil('acond_eje', 'X', (0.0, Z_ACOND), 55.0, (-1207.0, -854.3), 'motores', 'pernos'),
    cil('acond_chumacera', 'X', (0.0, Z_ACOND), 115.0, (-1150.0, -1000.0)),
    caja('acond_chumacera_base', (-1180.0, -970.0), (-175.0, 175.0), (2063.0, 2160.0)),
    caja('acond_chumacera_mensula', (-1000.0, -854.3), (-200.0, 200.0), (2050.0, 2160.0)),
    # viga de apoyo sobre el molino (lateral 16646.8-18225.2, z 1686-1838)
    ext('acond_viga_soporte', 'Y', (-292.0, 292.0),
        [R((-156.5, 1762.4), (1579.0, 152.0)), R((-156.5, 1762.4), (1539.0, 112.0))], 'estructura'),
    # patas del lado de los motores: tubo cuadrado 75x75x6 con placa base y travesano
    ext('acond_patas', 'Z', (15.0, 1830.0),
        [R((3047.5, 254.5), (75.0, 75.0)), R((3047.5, 254.5), (63.0, 63.0)),
         R((3047.5, -254.5), (75.0, 75.0)), R((3047.5, -254.5), (63.0, 63.0))], 'estructura', aprox=True),
    ext('acond_patas_placas', 'Z', (0.0, 15.0),
        [R((3047.5, s * 254.5), (180.0, 180.0)) for s in (1, -1)] +
        [C((3047.5 + a, s * 254.5 + b), 9.0) for s in (1, -1) for a in (-60.0, 60.0) for b in (-60.0, 60.0)],
        'estructura', aprox=True),
    caja('acond_patas_travesano', (3010.0, 3085.0), (-217.0, 217.0), (1500.0, 1575.0), 'estructura', aprox=True),
    # sensores de temperatura bajo el cuerpo (lateral x 18466 y 19063)
    ext('acond_sensores_temp', 'Z', (1740.0, 1830.0), [C((874.0, 0.0), 16.0), C((1471.0, 0.0), 16.0)], nivel='fino'),
    ext('acond_sensores_cabezal', 'Z', (1690.0, 1740.0), [C((874.0, 0.0), 32.0), C((1471.0, 0.0), 32.0)], nivel='fino'),
    # cabezal de vapor 8" bajo el acondicionador + inyeccion
    cil('vapor_cabezal', 'X', (0.0, 1805.2), 109.55, (2600.0, 3333.6), 'conexiones', aprox=True),
    cil('vapor_inyeccion', 'Z', (2650.0, 0.0), 30.0, (1805.2, 1850.0), 'conexiones', aprox=True),
    # motorreductor SEW FT97 22 kW i=22.12 (eje hueco, lateral 20713-21942.8)
    ext('acond_reductor', 'Y', (-300.0, 300.0), [RR((3340.4, 2380.5), (439.2, 651.0), 60.0)], 'motores', 'reductores'),
    cil('acond_motor_adaptador', 'X', (0.0, Z_MOT_ACOND), 170.0, (3560.0, 3700.0), 'motores', 'reductores'),
    ext('acond_motor', 'X', (3700.0, 4230.0), [aletas((0.0, Z_MOT_ACOND), 190.0, 28, 18.0, 8.0)], 'motores', 'reductores'),
    cil('acond_motor_ventilador', 'X', (0.0, Z_MOT_ACOND), 205.0, (4230.0, 4350.6), 'motores', 'reductores'),
    caja('acond_motor_caja_bornes', (3950.0, 4150.0), (-330.0, -205.0), (2400.0, 2560.0), 'motores', 'reductores'),
    caja('acond_brazo_torsion', (3085.0, 3125.0), (-40.0, 40.0), (1500.0, 2055.0), 'estructura', aprox=True),
]

# ---------------------------------------------------------------- alimentador INF12 (canaleta U)
SOLIDOS += [
    ext('alim_canaleta', 'X', (820.0, 2887.0), [U((0.0, Z_ALIM), 196.8, 3320.0)]),
    ext('alim_tapa', 'X', (820.0, 2887.0), [R((0.0, 3330.0), (460.0, 20.0))]),
    ext('alim_extremos', 'X', (804.6, 820.0), [U((0.0, Z_ALIM), 216.0, 3340.0)]),
    ext('alim_extremo_der', 'X', (2887.0, 2903.4), [U((0.0, Z_ALIM), 216.0, 3340.0)]),
    caja('alim_carcasa', (1020.6, 2541.4), (-279.4, 279.4), (3020.4, 3340.0)),
    cil('alim_chumacera', 'X', (0.0, Z_ALIM), 85.0, (740.0, 804.6)),
    cil('alim_eje', 'X', (0.0, Z_ALIM), 35.0, (700.0, 740.0), 'motores', 'pernos'),
    caja('alim_poste', (2400.0, 2470.0), (-35.0, 35.0), (2700.0, 2995.0), 'estructura', aprox=True),
    # salida del alimentador -> tolva con magneto -> entrada del acondicionador (B-B y D-D: 406 x 406, (12) Ø12)
    caja('alim_salida_cuello', (2504.4, 2940.4), (-218.0, 218.0), (2997.7, 3060.0)),
    caja('acond_entrada_cuello', (2685.4, 3121.4), (-218.0, 218.0), (2690.0, 2726.6)),
    {'id': 'tolva_magneto', 'forma': 'transicion', 'z': (2758.6, 2965.7),
     'base': (2903.4, 0.0, 436.0, 436.0), 'tope': (2722.4, 0.0, 436.0, 436.0), 'sub': 'cuerpo', 'mat': 'cuerpo'},
    caja('magneto_cajon', (2700.0, 2925.0), (-300.0, -218.0), (2800.0, 2930.0), aprox=True),
    # motorreductor SEW FT67 3 kW i=34.01
    ext('alim_reductor', 'Y', (-150.0, 150.0), [RR((3026.7, 3190.0), (246.6, 280.0), 40.0)], 'motores', 'reductores'),
    cil('alim_motor_adaptador', 'X', (0.0, Z_MOT_ALIM), 90.0, (3150.0, 3240.0), 'motores', 'reductores'),
    ext('alim_motor', 'X', (3240.0, 3600.0), [aletas((0.0, Z_MOT_ALIM), 90.0, 20, 12.0, 6.0)], 'motores', 'reductores'),
    cil('alim_motor_ventilador', 'X', (0.0, Z_MOT_ALIM), 100.0, (3600.0, 3720.0), 'motores', 'reductores'),
    caja('alim_motor_caja_bornes', (3420.0, 3540.0), (-170.0, -95.0), (3220.0, 3330.0), 'motores', 'reductores'),
]
_BB = perimetro(0.0, 0.0, paso(4, 146.0), paso(4, 146.0))
SOLIDOS += junta_bridada('junta_D-D', 'Z', 2742.6, R((2903.4, 0.0), (470.0, 470.0)), R((2903.4, 0.0), (406.0, 406.0)),
                         [(2903.4 + a, b) for a, b in _BB], 12.0, 'M10', 16.0, 16.0)
SOLIDOS += junta_bridada('junta_B-B', 'Z', 2981.7, R((2722.4, 0.0), (470.0, 470.0)), R((2722.4, 0.0), (406.0, 406.0)),
                         [(2722.4 + a, b) for a, b in _BB], 12.0, 'M10', 16.0, 16.0)


SPEC = {
    # ------------------------------------------------------------------ familia
    'familia': {
        'nombre_archivo': 'AM_Peletizadora_CPM-7730-8',
        'tipo': 'CPM 7730-8 + 30LTC13HS + INF12',
        'categoria': 'OST_MechanicalEquipment',
        'plantillas': [  # se busca la primera que exista en la carpeta de plantillas de Revit
            u'Equipo mecánico métrico.rft', u'Equipo mecanico metrico.rft',
            'Metric Mechanical Equipment.rft', 'M_Mechanical Equipment.rft',
            u'Modelo genérico métrico.rft', 'Metric Generic Model.rft',
        ],
    },

    # ------------------------------------------------------------------ datos nativos de Revit
    'nativos': {
        'ALL_MODEL_MANUFACTURER': u'CPM (Roskamp Champion)',
        'ALL_MODEL_MODEL': u'7730-8 / 30LTC13HS / INF12',
        'ALL_MODEL_DESCRIPTION': u'Peletizadora CPM 7730-8 (dado 762 × 209 mm, 300 HP) con acondicionador de vapor '
                                 u'30LTC13HS (hot start) y alimentador INF12. Polipasto de dado opcional: no modelado.',
        'ALL_MODEL_TYPE_COMMENTS': u'Fuente: CPM General Dimension Drawing 2022.12.09 (PELLET_MAGDALENA.dxf) y catálogo '
                                   u'CPM 7700. Origen = borde frontal base / eje máquina / NPT.',
    },

    # ------------------------------------------------------------------ LOI ad-STD-AVSA-003
    # Grupo AVSA_LOI_Equipos del archivo de parametros compartidos.  inst=True -> parametro de instancia.
    'loi': [
        ('AM_Tag',                   True,  u'PEL-01'),
        ('AM_Sistema',               True,  u'Vapor'),
        ('AM_Fuente_Geometria',      False, u'Archivo proveedor'),
        ('AM_Confianza_Dimensional', False, u'Media'),
        ('AM_Peso_kg',               False, 10100.0),   # 7200 molino + 2900 acondicionador y alimentador (nota CPM)
        ('AM_LOD',                   False, u'350'),
        ('AM_Fecha_Modelado',        False, '__HOY__'),
        ('AM_Capacidad',             False, u'POR CONFIRMAR (kg/h)'),
        ('AM_Dimensiones_Generales', False, u'5558 × 1410 × 3378 (L × A × H, mm)'),
        ('AM_Material_Construccion', False, u'POR CONFIRMAR'),
        ('AM_Conexion_Entrada',      False, u'Vapor: brida 8" ASME B16.5 Cl.150 WN-RF, 8 pernos 3/4" (clase por confirmar) - CX01'),
        ('AM_Conexion_Producto',     False, u'Entrada harina: abertura 914 × 483, brida 991 × 559, (20) Ø14 M12 - CX02'),
        ('AM_Conexion_Salida',       False, u'Salida pellet: abertura 470 × 400, brida 520 × 495, (6) Ø11.5 M10 - CX03'),
        # Sin dato en el plano: se crean pero quedan vacios
        ('AM_Presion_Diseno',        False, None),
        ('AM_Presion_Trabajo',       False, None),
        ('AM_Temperatura_Operacion', False, None),
    ],

    # ------------------------------------------------------------------ materiales y subcategorias
    # rgb, transparencia (0-100).  Cada material se expone como parametro de tipo (grupo Materiales).
    'materiales': {
        'cuerpo':     {'nombre': 'AM_Equipo_Acero_Pintado_GrisClaro', 'rgb': (222, 223, 219), 'transp': 0,  'param': 'Mat_Cuerpo'},
        'motores':    {'nombre': 'AM_Equipo_Motor_Negro',             'rgb': (38, 38, 40),    'transp': 0,  'param': 'Mat_Motor_Principal'},
        'reductores': {'nombre': 'AM_Equipo_Motorreductor_Gris',      'rgb': (196, 199, 201), 'transp': 0,  'param': 'Mat_Motorreductores'},
        'estructura': {'nombre': 'AM_Equipo_Acero_Estructural_Negro', 'rgb': (30, 30, 30),    'transp': 0,  'param': 'Mat_Estructura'},
        'conexiones': {'nombre': 'AM_Equipo_Bridas_Gris',             'rgb': (176, 179, 182), 'transp': 0,  'param': 'Mat_Conexiones'},
        'pernos':     {'nombre': 'AM_Equipo_Pernos_Galvanizado',      'rgb': (140, 142, 145), 'transp': 0,  'param': 'Mat_Pernos'},
        'zonas':      {'nombre': 'AM_Zona_Servicio_Transparente',     'rgb': (231, 106, 31),  'transp': 80, 'param': 'Mat_Zonas_Servicio'},
    },
    'subcategorias': {
        'cuerpo':     {'nombre': 'AM_Cuerpo',          'mat': 'cuerpo'},
        'motores':    {'nombre': 'AM_Motores',         'mat': 'motores'},
        'estructura': {'nombre': 'AM_Estructura',      'mat': 'estructura'},
        'conexiones': {'nombre': 'AM_Conexiones',      'mat': 'conexiones'},
        'zonas':      {'nombre': 'AM_Zonas_Servicio',  'mat': 'zonas'},
    },

    # ------------------------------------------------------------------ geometria solida (ver helpers arriba)
    'solidos': SOLIDOS,

    # ------------------------------------------------------------------ vacios (cortan un solido)
    # (4) Ø25 anclajes: X = 162 / 1882 (cotas 162-1720-618), Y = +723 / -617 (cotas 720 / 614 del CAD, medidas 723 / 617)
    'vacios': [
        {'id': 'anclaje_%d' % (i + 1), 'forma': 'cilindro', 'eje': 'Z', 'centro': q, 'r': 12.5,
         'rango': (-1.0, 166.0), 'corta': 'base'} for i, q in enumerate(ANCLAJES)
    ],

    # ------------------------------------------------------------------ conexiones MEP parametricas
    # Cada boquilla crea: tubo hueco + (cuello) + brida con agujeros + (cara RF) + esparragos y tuercas
    # + conector MEP sobre la cara de la brida.  Parametros de tipo por boquilla (prefijo = id):
    #   <id>_Proyeccion (base -> cara de brida), _Brida_Espesor, _RF_Alto, _Cuello_Largo, _Tuerca_Alto,
    #   _Perno_Saliente  + formulas _RF_Inicio, _Brida_Inicio, _Cuello_Inicio, _Tuerca_Inicio, _Perno_Fin
    #   tuberia: _DN (Tamano de tuberia); rectangular: _Ancho / _Alto (Tamano de ducto)
    'boquillas': [
        {'id': 'CX01', 'nombre': 'Vapor', 'tipo': 'tuberia', 'sistema': 'OtherPipe', 'flujo': 'In',
         'descripcion': u'CX01 Entrada de vapor 8" Cl.150 RF',
         # 8" STEAM INLET: lateral centro (20816.2, 2079.6); frontal cara de brida x=14862.1 -> Y=-524.8
         'eje': '-Y', 'base': (3224.0, 0.0, 1805.2), 'proyeccion': 524.8,
         'seccion': 'circular', 'd_tubo': 219.1, 'd_interior': 202.7, 'dn': 203.2,
         'd_brida': 342.9, 'e_brida': 28.4, 'rf': {'d': 269.9, 'h': 1.6}, 'cuello': {'d': 235.0, 'l': 71.6},
         'pernos': pernos_boquilla('3/4', circulo_pernos(3224.0, 1805.2, 8, 298.5), 22.2, 55.0)},
        {'id': 'CX02', 'nombre': 'Entrada harina', 'tipo': 'ducto', 'sistema': 'OtherAir', 'flujo': 'In',
         'descripcion': u'CX02 Entrada producto alimentador 914×483',
         # abertura 914 (X) x 483 (Y), brida 991 x 559, (20) Ø14: 6x158.8=953 / 4x130.25=521
         'eje': '+Z', 'base': (1477.8, 0.0, 3340.0), 'proyeccion': 38.2,
         'seccion': 'rectangular', 'abertura': (914.0, 483.0), 'brida': (991.0, 559.0),
         'cuerpo': (930.0, 499.0), 'e_brida': 16.0,
         'pernos': pernos_boquilla('M12', perimetro(1477.8, 0.0, paso(7, 158.8), paso(5, 130.25)), 14.0, 32.0)},
        {'id': 'CX03', 'nombre': 'Salida pellet', 'tipo': 'ducto', 'sistema': 'OtherAir', 'flujo': 'Out',
         'descripcion': u'CX03 Descarga pellet 470×400',
         # vista A-A: abertura 470 (X) x 400 (Y), agujeros a 200 (X) y 467 (Y), brida 520 x 495, (6) Ø11.5
         'eje': '-Z', 'base': (-297.0, 0.0, 240.0), 'proyeccion': 45.65,
         'seccion': 'rectangular', 'abertura': (470.0, 400.0), 'brida': (520.0, 495.0),
         'cuerpo': (482.0, 412.0), 'e_brida': 12.0,
         'pernos': pernos_boquilla('M10', [(-297.0 + a, b) for a in (-200.0, 0.0, 200.0) for b in (-233.5, 233.5)],
                                   11.5, 24.0)},
    ],

    # ------------------------------------------------------------------ conectores electricos (sobre caja de bornes)
    # va = carga aparente estimada P / (eficiencia x FP).  POR CONFIRMAR con el proveedor.
    'electricos': [
        {'id': 'EL01', 'nombre': 'Motor principal', 'en': 'motor_ppal_caja_bornes', 'cara': '-Y',
         'tension': 460.0, 'polos': 3, 'kw': 224.0, 'va': 268000.0,
         'descripcion': u'EL01 Motor principal 300 HP (catálogo CPM 7700, confirmar) 60 Hz / 460 V'},
        {'id': 'EL02', 'nombre': 'Motor acondicionador', 'en': 'acond_motor_caja_bornes', 'cara': '-Y',
         'tension': 460.0, 'polos': 3, 'kw': 22.0, 'va': 27500.0,
         'descripcion': u'EL02 SEW FT97 22 kW i=22.12 60 Hz / 460 V'},
        {'id': 'EL03', 'nombre': 'Motor alimentador', 'en': 'alim_motor_caja_bornes', 'cara': '-Y',
         'tension': 460.0, 'polos': 3, 'kw': 3.0, 'va': 4400.0,
         'descripcion': u'EL03 SEW FT67 3 kW i=34.01 60 Hz / 460 V'},
    ],

    # ------------------------------------------------------------------ planos de referencia con nombre
    # (nombre, eje normal, coordenada mm).  Sirven para acotar anclajes y ejes desde el proyecto.
    'planos_referencia': [
        ('Anclaje_X1', 'X', 162.0), ('Anclaje_X2', 'X', 1882.0),
        ('Anclaje_Y1', 'Y', 723.0), ('Anclaje_Y2', 'Y', -617.0),
        ('Eje_Descarga_Pellet', 'X', -297.0),
        ('Eje_Entrada_Harina', 'X', 1477.8),
        ('Eje_Entrada_Vapor', 'X', 3224.0),
        ('Eje_Dado_Molino', 'Z', Z_DADO),
        ('Eje_Acondicionador', 'Z', Z_ACOND),
        ('Eje_Alimentador', 'Z', Z_ALIM),
    ],

    # ------------------------------------------------------------------ zonas de servicio (notas ALLOW ... MIN del CAD)
    # Visibles con el Si/No de instancia 'Mostrar_Zonas_Servicio'; largo = parametro de instancia.
    'zonas': [
        {'id': 'ZS1', 'nombre': 'Cambio eje acondicionador', 'param': 'ZS_CambioEje_Largo', 'largo': 5010.0,
         'normal': '-X', 'plano': -883.7, 'u': (-444.5, 444.5), 'v': (1818.7, 2707.7)},
        {'id': 'ZS2', 'nombre': 'Giro puerta frontal', 'param': 'ZS_PuertaFrontal_Largo', 'largo': 1426.0,
         'normal': '-X', 'plano': -883.7, 'u': (-652.0, 758.0), 'v': (0.0, 1570.0)},
        # 2132 = puerta totalmente abierta; 1563 = puerta a 90 grados
        {'id': 'ZS3', 'nombre': 'Giro puerta lateral', 'param': 'ZS_PuertaLateral_Largo', 'largo': 2132.0,
         'normal': '+Y', 'plano': 758.0, 'u': (-883.7, 15.0), 'v': (0.0, 1570.0)},
    ],
}
