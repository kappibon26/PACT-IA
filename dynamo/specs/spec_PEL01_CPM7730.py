# -*- coding: utf-8 -*-
"""
Especificacion de familia: Peletizadora CPM 7730-8 + acondicionador 30LTC13HS + alimentador INF12
Proyecto AVSA - MACPOLLO (Planta de Pienso Horizonte).  Estandar ad-STD-AVSA-003 (LOI de familias).

Fuente: PELLET_MAGDALENA.dxf = CPM "General Dimension Drawing", Joe 2022.12.09,
revisado por Ivan Orejarena 2022-12-16.  Dibujo en mm a escala 1:1, proyeccion en 3er angulo.

SISTEMA DE COORDENADAS DE LA FAMILIA (mm)
  Origen  = borde frontal de la base del molino (lado puerta) / eje longitudinal de la maquina / piso (NPT).
  +X      = a lo largo del acondicionador, desde la puerta del molino hacia los motores.
  +Y      = hacia el lado izquierdo de la vista frontal del CAD (lado de la oreja de izaje / lubricacion).
  +Z      = arriba.
Conversion desde el CAD:
  vista lateral  (derecha):  X = x_cad - 17592.2      Z = y_cad - 274.4
  vista frontal  (puerta):   Y = 14337.3 - x_cad      Z = y_cad - 274.4

Convenciones de este archivo (las lee dynamo/lib/ad_family_builder.py y herramientas/preview_spec.py):
  caja       : x, y, z = (min, max)
  cilindro   : eje 'X'|'Y'|'Z', centro = las otras dos coordenadas en orden (X->(y,z), Y->(x,z), Z->(x,y)),
               r = radio, rango = (min, max) a lo largo del eje
  transicion : z = (z_base, z_tope); base / tope = (cx, cy, dx, dy)  -> rectangulos horizontales
  boquilla   : eje con signo ('+Z', '-Y'...), base = punto (x, y, z) en el eje de la boquilla donde nace,
               proyeccion = distancia de la base a la cara de la brida (parametro de tipo, mueve el conector).
               Ejes de la seccion: eje X -> (Y, Z); eje Y -> (X, Z); eje Z -> (X, Y).
  zona       : normal con signo, plano = coordenada del plano de arranque, u / v = rangos en el plano
               (mismos ejes de seccion que la boquilla), largo = profundidad (parametro de instancia).
  'aprox': True marca piezas cuya posicion no esta acotada en el CAD (AM_Confianza_Dimensional = Media).
"""

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
        'ALL_MODEL_DESCRIPTION': u'Peletizadora con acondicionador de vapor 30LTC13HS (hot start) '
                                 u'y alimentador INF12. Opcional: polipasto eléctrico de dado (no modelado).',
        'ALL_MODEL_TYPE_COMMENTS': u'Fuente: CPM General Dimension Drawing 2022.12.09 (PELLET_MAGDALENA.dxf). '
                                   u'Origen = borde frontal base / eje máquina / NPT.',
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
        ('AM_Conexion_Entrada',      False, u'Vapor: brida 8" (OD 343 mm, ASME 150# por confirmar) - CX01'),
        ('AM_Conexion_Producto',     False, u'Entrada harina: abertura 914 × 483, brida 991 × 559, (20) Ø14 - CX02'),
        ('AM_Conexion_Salida',       False, u'Salida pellet: abertura 470 × 400, brida 520 × 467, (6) Ø11.5 - CX03'),
        # Sin dato en el plano: se crean pero quedan vacios
        ('AM_Presion_Diseno',        False, None),
        ('AM_Presion_Trabajo',       False, None),
        ('AM_Temperatura_Operacion', False, None),
    ],

    # ------------------------------------------------------------------ materiales y subcategorias
    # rgb, transparencia (0-100).  Cada material se expone como parametro de tipo (grupo Materiales).
    'materiales': {
        'cuerpo':     {'nombre': 'AM_Equipo_Acero_Pintado_Gris', 'rgb': (190, 192, 194), 'transp': 0,  'param': 'Mat_Cuerpo'},
        'motores':    {'nombre': 'AM_Equipo_Motor_Azul_Gris',    'rgb': (78, 94, 112),   'transp': 0,  'param': 'Mat_Motores'},
        'estructura': {'nombre': 'AM_Equipo_Acero_Estructural',  'rgb': (70, 70, 70),    'transp': 0,  'param': 'Mat_Estructura'},
        'conexiones': {'nombre': 'AM_Equipo_Conexion_Naranja',   'rgb': (231, 106, 31),  'transp': 0,  'param': 'Mat_Conexiones'},
        'zonas':      {'nombre': 'AM_Zona_Servicio_Transparente','rgb': (231, 106, 31),  'transp': 80, 'param': 'Mat_Zonas_Servicio'},
    },
    'subcategorias': {
        'cuerpo':     {'nombre': 'AM_Cuerpo',          'mat': 'cuerpo'},
        'motores':    {'nombre': 'AM_Motores',         'mat': 'motores'},
        'estructura': {'nombre': 'AM_Estructura',      'mat': 'estructura'},
        'conexiones': {'nombre': 'AM_Conexiones',      'mat': 'conexiones'},
        'zonas':      {'nombre': 'AM_Zonas_Servicio',  'mat': 'zonas'},
    },

    # ------------------------------------------------------------------ geometria solida
    'solidos': [
        # --- base / skid del molino (vista lateral 17592.2-20092.2; frontal 13579.3-14989.3; h 165)
        {'id': 'base', 'forma': 'caja', 'x': (0.0, 2500.0), 'y': (-652.0, 758.0), 'z': (0.0, 165.0),
         'sub': 'estructura', 'mat': 'estructura'},
        {'id': 'pedestal_molino', 'forma': 'caja', 'x': (0.0, 632.0), 'y': (-580.0, 580.0), 'z': (165.0, 240.0),
         'sub': 'estructura', 'mat': 'estructura'},

        # --- molino: camara del dado + puerta (vista frontal: circulo R665 centro z=905)
        {'id': 'camara_dado', 'forma': 'cilindro', 'eje': 'X', 'centro': (0.0, 905.0), 'r': 665.0,
         'rango': (-526.0, 90.0), 'sub': 'cuerpo', 'mat': 'cuerpo'},
        # carcasa de rodamientos / engranajes (caja con logo CPM, lateral 17682-18224)
        {'id': 'carcasa_principal', 'forma': 'caja', 'x': (90.0, 632.0), 'y': (-580.0, 580.0), 'z': (200.0, 1445.0),
         'sub': 'cuerpo', 'mat': 'cuerpo'},
        # alimentador forzado / boca de la puerta (lateral 16820-17066; frontal +-200)
        {'id': 'boca_alimentacion', 'forma': 'caja', 'x': (-772.0, -526.0), 'y': (-200.0, 200.0), 'z': (277.0, 1146.0),
         'sub': 'cuerpo', 'mat': 'cuerpo'},
        # descarga acondicionador -> molino (seccion C-C: abertura 260 x 500, brida 344 x 585)
        {'id': 'ducto_acond_molino', 'forma': 'caja', 'x': (-794.0, -504.0), 'y': (-265.0, 265.0), 'z': (1146.0, 1830.0),
         'sub': 'cuerpo', 'mat': 'cuerpo'},
        {'id': 'brida_C-C', 'forma': 'caja', 'x': (-821.0, -477.0), 'y': (-292.5, 292.5), 'z': (1740.0, 1755.0),
         'sub': 'cuerpo', 'mat': 'cuerpo'},
        # acople / reductor / pasador de corte (lateral 18224-18853)
        {'id': 'acople_reductor', 'forma': 'caja', 'x': (632.0, 1261.6), 'y': (-300.0, 300.0), 'z': (165.0, 860.0),
         'sub': 'motores', 'mat': 'motores'},
        # sistema de lubricacion (frontal 13497-13867, z 263-615) - posicion X no acotada
        {'id': 'lubricacion', 'forma': 'caja', 'x': (-400.0, -100.0), 'y': (470.0, 840.0), 'z': (0.0, 615.2),
         'sub': 'cuerpo', 'mat': 'cuerpo', 'aprox': True},

        # --- motor principal 60 Hz / 460 V (lateral 18853.8-19873.8, z 275-887)
        {'id': 'motor_ppal_patas', 'forma': 'caja', 'x': (1300.0, 2120.0), 'y': (-280.0, 280.0), 'z': (165.0, 290.0),
         'sub': 'motores', 'mat': 'motores'},
        {'id': 'motor_ppal', 'forma': 'cilindro', 'eje': 'X', 'centro': (0.0, 581.0), 'r': 306.0,
         'rango': (1261.6, 2162.9), 'sub': 'motores', 'mat': 'motores'},
        {'id': 'motor_ppal_ventilador', 'forma': 'cilindro', 'eje': 'X', 'centro': (0.0, 581.0), 'r': 290.0,
         'rango': (2162.9, 2281.6), 'sub': 'motores', 'mat': 'motores'},
        {'id': 'motor_ppal_caja_bornes', 'forma': 'caja', 'x': (1508.0, 1708.0), 'y': (-426.0, -290.0), 'z': (526.0, 726.0),
         'sub': 'motores', 'mat': 'motores'},

        # --- acondicionador 30LTC13HS (frontal: circulo D889 centro z=2263.2; lateral 16737.9-20713.0)
        {'id': 'acond_cuerpo', 'forma': 'cilindro', 'eje': 'X', 'centro': (0.0, 2263.2), 'r': 444.5,
         'rango': (-854.3, 3120.8), 'sub': 'cuerpo', 'mat': 'cuerpo'},
        {'id': 'acond_chumacera', 'forma': 'caja', 'x': (-1207.0, -854.3), 'y': (-175.0, 175.0), 'z': (2063.0, 2463.0),
         'sub': 'cuerpo', 'mat': 'cuerpo'},
        {'id': 'acond_viga_soporte', 'forma': 'caja', 'x': (-946.0, 633.0), 'y': (-292.0, 292.0), 'z': (1686.4, 1838.4),
         'sub': 'estructura', 'mat': 'estructura'},
        {'id': 'acond_pata_1', 'forma': 'caja', 'x': (3010.0, 3085.0), 'y': (217.0, 292.0), 'z': (0.0, 1830.0),
         'sub': 'estructura', 'mat': 'estructura', 'aprox': True},
        {'id': 'acond_pata_2', 'forma': 'caja', 'x': (3010.0, 3085.0), 'y': (-292.0, -217.0), 'z': (0.0, 1830.0),
         'sub': 'estructura', 'mat': 'estructura', 'aprox': True},
        # motorreductor SEW FT97 22 kW i=22.12 (lateral 20713-21942.8)
        {'id': 'acond_reductor', 'forma': 'caja', 'x': (3120.8, 3827.8), 'y': (-300.0, 300.0), 'z': (2055.0, 2706.0),
         'sub': 'motores', 'mat': 'motores'},
        {'id': 'acond_motor', 'forma': 'cilindro', 'eje': 'X', 'centro': (0.0, 2456.0), 'r': 220.0,
         'rango': (3827.8, 4350.6), 'sub': 'motores', 'mat': 'motores'},
        {'id': 'acond_motor_caja_bornes', 'forma': 'caja', 'x': (3950.0, 4150.0), 'y': (-330.0, -210.0), 'z': (2400.0, 2560.0),
         'sub': 'motores', 'mat': 'motores'},

        # --- alimentador INF12 (frontal: circulo D393.7 centro z=3187.7; lateral 18396.8-20904.6)
        {'id': 'alim_tubo', 'forma': 'cilindro', 'eje': 'X', 'centro': (0.0, 3187.7), 'r': 196.8,
         'rango': (804.6, 2903.4), 'sub': 'cuerpo', 'mat': 'cuerpo'},
        {'id': 'alim_carcasa', 'forma': 'caja', 'x': (1020.6, 2541.4), 'y': (-279.4, 279.4), 'z': (3020.4, 3340.0),
         'sub': 'cuerpo', 'mat': 'cuerpo'},
        # tolva con magneto alimentador -> acondicionador (B-B en el alimentador, D-D en el acondicionador, 406 x 406)
        {'id': 'tolva_magneto', 'forma': 'transicion', 'z': (2700.0, 2997.7),
         'base': (2903.4, 0.0, 470.0, 470.0), 'tope': (2722.4, 0.0, 470.0, 470.0),
         'sub': 'cuerpo', 'mat': 'cuerpo'},
        # motorreductor SEW FT67 3 kW i=34.01
        {'id': 'alim_reductor', 'forma': 'caja', 'x': (2903.4, 3240.0), 'y': (-150.0, 150.0), 'z': (3050.0, 3330.0),
         'sub': 'motores', 'mat': 'motores'},
        {'id': 'alim_motor', 'forma': 'cilindro', 'eje': 'X', 'centro': (0.0, 3280.6), 'r': 100.0,
         'rango': (3240.0, 3720.0), 'sub': 'motores', 'mat': 'motores'},
        {'id': 'alim_motor_caja_bornes', 'forma': 'caja', 'x': (3420.0, 3540.0), 'y': (-170.0, -100.0), 'z': (3220.0, 3330.0),
         'sub': 'motores', 'mat': 'motores'},
    ],

    # ------------------------------------------------------------------ vacios (cortan un solido)
    # (4) Ø25 anclajes: X = 162 / 1882 (cotas 162-1720-618), Y = +723 / -617 (cotas 720 / 614 del CAD, medidas 723 / 617)
    'vacios': [
        {'id': 'anclaje_1', 'forma': 'cilindro', 'eje': 'Z', 'centro': (162.0, 723.0),   'r': 12.5, 'rango': (-1.0, 166.0), 'corta': 'base'},
        {'id': 'anclaje_2', 'forma': 'cilindro', 'eje': 'Z', 'centro': (162.0, -617.0),  'r': 12.5, 'rango': (-1.0, 166.0), 'corta': 'base'},
        {'id': 'anclaje_3', 'forma': 'cilindro', 'eje': 'Z', 'centro': (1882.0, 723.0),  'r': 12.5, 'rango': (-1.0, 166.0), 'corta': 'base'},
        {'id': 'anclaje_4', 'forma': 'cilindro', 'eje': 'Z', 'centro': (1882.0, -617.0), 'r': 12.5, 'rango': (-1.0, 166.0), 'corta': 'base'},
    ],

    # ------------------------------------------------------------------ conexiones MEP parametrizadas
    # Cada boquilla crea: tubo/cuerpo + brida + conector MEP sobre la cara de la brida.
    # Parametros de tipo creados por boquilla (prefijo = id):
    #   <id>_Proyeccion, <id>_Brida_Espesor, <id>_Brida_Inicio (formula)  -> mueven la brida y el conector
    #   tuberia:     <id>_DN (Tamano de tuberia)          -> diametro del conector
    #   rectangular: <id>_Ancho, <id>_Alto (Tamano de ducto) -> tamano del conector
    'boquillas': [
        {'id': 'CX01', 'nombre': 'Vapor', 'tipo': 'tuberia', 'sistema': 'OtherPipe', 'flujo': 'In',
         'descripcion': u'CX01 Entrada de vapor 8"',
         # 8" STEAM INLET: lateral centro (20816.2, 2079.6); frontal cara de brida x=14862.1 -> Y=-524.8
         'eje': '-Y', 'base': (3224.0, 0.0, 1805.2), 'proyeccion': 524.8,
         'seccion': 'circular', 'd_tubo': 219.1, 'd_brida': 342.9, 'e_brida': 26.9, 'dn': 203.2},
        {'id': 'CX02', 'nombre': 'Entrada harina', 'tipo': 'ducto', 'sistema': 'OtherAir', 'flujo': 'In',
         'descripcion': u'CX02 Entrada producto alimentador 914×483',
         # abertura 914 (X) x 483 (Y), brida 991 x 559, (20) Ø14; centro X=19070-17592.2, cara superior z=3378.2
         'eje': '+Z', 'base': (1477.8, 0.0, 3340.0), 'proyeccion': 38.2,
         'seccion': 'rectangular', 'abertura': (914.0, 483.0), 'brida': (991.0, 559.0),
         'cuerpo': (930.0, 500.0), 'e_brida': 16.0},
        {'id': 'CX03', 'nombre': 'Salida pellet', 'tipo': 'ducto', 'sistema': 'OtherAir', 'flujo': 'Out',
         'descripcion': u'CX03 Descarga pellet 470×400',
         # vista A-A: abertura 470 (X) x 400 (Y), brida 520 x 467, (6) Ø11.5; cara inferior z=194.35 (cota 194.35)
         'eje': '-Z', 'base': (-297.0, 0.0, 240.0), 'proyeccion': 45.65,
         'seccion': 'rectangular', 'abertura': (470.0, 400.0), 'brida': (520.0, 467.0),
         'cuerpo': (482.0, 412.0), 'e_brida': 12.0},
    ],

    # ------------------------------------------------------------------ conectores electricos (sobre caja de bornes)
    # va = carga aparente estimada (P / (eficiencia x FP)), marcar como POR CONFIRMAR con el proveedor.
    'electricos': [
        {'id': 'EL01', 'nombre': 'Motor principal', 'en': 'motor_ppal_caja_bornes', 'cara': '-Y',
         'tension': 460.0, 'polos': 3, 'kw': None, 'va': None,
         'descripcion': u'EL01 Motor principal 60 Hz / 460 V (potencia POR CONFIRMAR)'},
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
        ('Eje_Dado_Molino', 'Z', 905.0),
        ('Eje_Acondicionador', 'Z', 2263.2),
        ('Eje_Alimentador', 'Z', 3187.7),
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
