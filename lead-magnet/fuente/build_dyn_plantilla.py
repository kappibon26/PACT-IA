# -*- coding: utf-8 -*-
"""Genera plantilla_dynamo/ADLB_Generar_Familia.dyn a partir de ADLB_Generar_Familia.py."""
import io, json, os, uuid
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(AQUI, 'plantilla_dynamo', 'ADLB_Generar_Familia.py')
DST = os.path.join(AQUI, 'plantilla_dynamo', 'ADLB_Generar_Familia.dyn')
gid = lambda: uuid.uuid4().hex
def port(name='', desc=''):
    return {'Id': gid(), 'Name': name, 'Description': desc, 'UsingDefaultValue': False,
            'Level': 2, 'UseLevels': False, 'KeepListStructure': False}
nodes, views, conns = [], [], []
def add(n, name, x, y, inp=False):
    nodes.append(n); views.append({'Id': n['Id'], 'Name': name, 'IsSetAsInput': inp, 'IsSetAsOutput': False,
                                   'Excluded': False, 'ShowGeometry': True, 'X': x, 'Y': y}); return n
def path_node(v, name, y, carpeta=False):
    cls = 'Directory' if carpeta else 'Filename'
    return add({'ConcreteType': 'CoreNodeModels.Input.%s, CoreNodeModels' % cls, 'HintPath': v, 'InputValue': v,
                'NodeType': 'ExtensionNode', 'Id': gid(), 'Inputs': [], 'Outputs': [port('', 'Ruta')],
                'Replication': 'Disabled', 'Description': name}, name, 0, y, True)
def bool_node(v, name, y):
    return add({'ConcreteType': 'CoreNodeModels.Input.BoolSelector, CoreNodeModels', 'NodeType': 'BooleanInputNode',
                'InputValue': v, 'Id': gid(), 'Inputs': [], 'Outputs': [port('', 'Boolean')],
                'Replication': 'Disabled', 'Description': name}, name, 0, y, True)
def str_node(v, name, y):
    return add({'ConcreteType': 'CoreNodeModels.Input.StringInput, CoreNodeModels', 'NodeType': 'StringInputNode',
                'InputValue': v, 'Id': gid(), 'Inputs': [], 'Outputs': [port('', 'String')],
                'Replication': 'Disabled', 'Description': name}, name, 0, y, True)
ins = [path_node(r'C:\RUTA\ADLB_Plantilla_Familia.xlsx', '1 - Excel de la familia', 0),
       path_node(r'C:\RUTA\Familias', '2 - Carpeta de salida', 130, True),
       path_node('', '3 - Plano de PLANTA .dwg/.dxf (opcional)', 260),
       path_node('', '4 - Plano de ALZADO frontal .dwg/.dxf (opcional)', 390),
       bool_node(True, '5 - Cargar en el proyecto', 520),
       bool_node(True, '6 - SOLO VALIDAR', 630),
       bool_node(False, '7 - EJECUTAR', 740)]
pin = [port('IN[%d]' % i, 'Input #%d' % i) for i in range(len(ins))]
py = add({'ConcreteType': 'PythonNodeModels.PythonNode, PythonNodeModels', 'NodeType': 'PythonScriptNode',
          'Code': io.open(SRC, encoding='utf-8').read(), 'Engine': 'CPython3', 'VariableInputPorts': True,
          'Id': gid(), 'Inputs': pin, 'Outputs': [port('OUT', 'Registro')], 'Replication': 'Disabled',
          'Description': 'ADLB - generar familia desde Excel'}, 'ADLB - Generar familia', 560, 320)
w = add({'ConcreteType': 'CoreNodeModels.Watch, CoreNodeModels', 'NodeType': 'ExtensionNode', 'Id': gid(),
         'Inputs': [port('', 'Node to show output from')], 'Outputs': [port('', 'Node output')],
         'Replication': 'Disabled', 'Description': 'Registro'}, 'Registro', 940, 320)
for n, p in zip(ins, pin):
    conns.append({'Start': n['Outputs'][0]['Id'], 'End': p['Id'], 'Id': gid(), 'IsHidden': 'False'})
conns.append({'Start': py['Outputs'][0]['Id'], 'End': w['Inputs'][0]['Id'], 'Id': gid(), 'IsHidden': 'False'})
note = {'Id': gid(), 'Title': 'ADLB · Generar familia desde Excel\n1. Abre Dynamo desde tu PROYECTO (no desde una familia).\n2. Elige el Excel y la carpeta de salida. Los planos son opcionales.\n3. SOLO VALIDAR = True y EJECUTAR = True  ->  Ejecutar. Corrige el Excel hasta 0 errores.\n4. SOLO VALIDAR = False  ->  Ejecutar. La familia se guarda y se carga en el proyecto.',
        'DescriptionText': None, 'IsExpanded': True, 'WidthAdjustment': 0.0, 'HeightAdjustment': 0.0, 'Nodes': [],
        'HasNestedGroups': False, 'Left': 0.0, 'Top': -200.0, 'Width': 0.0, 'Height': 0.0, 'FontSize': 14.0,
        'GroupStyleId': '00000000-0000-0000-0000-000000000000', 'InitialTop': 0.0, 'InitialHeight': 0.0,
        'TextblockHeight': 0.0, 'Background': '#FFE76A1F'}
dyn = {'Uuid': str(uuid.uuid4()), 'IsCustomNode': False, 'Description': 'ADLB - generar familia de Revit desde Excel',
       'Name': 'ADLB_Generar_Familia', 'ElementResolver': {'ResolutionMap': {}}, 'Inputs': [], 'Outputs': [],
       'Nodes': nodes, 'Connectors': conns, 'Dependencies': [], 'NodeLibraryDependencies': [], 'Thumbnail': '',
       'GraphDocumentationURL': None, 'ExtensionWorkspaceData': [], 'Author': 'ADLB', 'Linting': {}, 'Bindings': [],
       'View': {'Dynamo': {'ScaleFactor': 1.0, 'HasRunWithoutCrash': True, 'IsVisibleInDynamoLibrary': True,
                           'Version': '2.17.0.3472', 'RunType': 'Manual', 'RunPeriod': '1000'},
                'Camera': {'Name': 'Background Preview', 'EyeX': -17.0, 'EyeY': 24.0, 'EyeZ': 50.0, 'LookX': 12.0,
                           'LookY': -13.0, 'LookZ': -58.0, 'UpX': 0.0, 'UpY': 1.0, 'UpZ': 0.0},
                'ConnectorPins': [], 'NodeViews': views, 'Annotations': [note], 'X': 60.0, 'Y': 260.0, 'Zoom': 0.7}}
io.open(DST, 'w', encoding='utf-8').write(json.dumps(dyn, indent=2, ensure_ascii=False))
print('ok ->', DST)
