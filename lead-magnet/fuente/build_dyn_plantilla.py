# -*- coding: utf-8 -*-
"""Genera plantilla_dynamo/ADLB_Parametros_desde_CSV.dyn a partir del .py del nodo."""
import io, json, os, uuid
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(AQUI, 'plantilla_dynamo', 'ADLB_Parametros_desde_CSV.py')
DST = os.path.join(AQUI, 'plantilla_dynamo', 'ADLB_Parametros_desde_CSV.dyn')
gid = lambda: uuid.uuid4().hex
def port(name='', desc=''):
    return {'Id': gid(), 'Name': name, 'Description': desc, 'UsingDefaultValue': False,
            'Level': 2, 'UseLevels': False, 'KeepListStructure': False}
nodes, views, conns, groups = [], [], [], []
def add(n, name, x, y, inp=False):
    nodes.append(n); views.append({'Id': n['Id'], 'Name': name, 'IsSetAsInput': inp, 'IsSetAsOutput': False,
                                   'Excluded': False, 'ShowGeometry': True, 'X': x, 'Y': y}); return n
def fnode(v, name, y):
    return add({'ConcreteType': 'CoreNodeModels.Input.Filename, CoreNodeModels', 'HintPath': v, 'InputValue': v,
                'NodeType': 'ExtensionNode', 'Id': gid(), 'Inputs': [], 'Outputs': [port('', 'Ruta')],
                'Replication': 'Disabled', 'Description': name}, name, 0, y, True)
def bnode(v, name, y):
    return add({'ConcreteType': 'CoreNodeModels.Input.BoolSelector, CoreNodeModels', 'NodeType': 'BooleanInputNode',
                'InputValue': v, 'Id': gid(), 'Inputs': [], 'Outputs': [port('', 'Boolean')],
                'Replication': 'Disabled', 'Description': name}, name, 0, y, True)
ins = [fnode(r'C:\RUTA\ADLB_Parametros_ejemplo.csv', '1 - Tabla de parametros (.csv)', 0),
       fnode(r'C:\RUTA\Parametros_Compartidos.txt', '2 - Parametros compartidos (.txt, opcional)', 130),
       bnode(True, '3 - SIMULAR (True = solo revisar)', 260),
       bnode(False, '4 - EJECUTAR', 370)]
pin = [port('IN[%d]' % i, 'Input #%d' % i) for i in range(len(ins))]
py = add({'ConcreteType': 'PythonNodeModels.PythonNode, PythonNodeModels', 'NodeType': 'PythonScriptNode',
          'Code': io.open(SRC, encoding='utf-8').read(), 'Engine': 'CPython3', 'VariableInputPorts': True,
          'Id': gid(), 'Inputs': pin, 'Outputs': [port('OUT', 'Registro')], 'Replication': 'Disabled',
          'Description': 'ADLB - parametros desde CSV'}, 'ADLB - Parametros desde CSV', 520, 160)
w = add({'ConcreteType': 'CoreNodeModels.Watch, CoreNodeModels', 'NodeType': 'ExtensionNode', 'Id': gid(),
         'Inputs': [port('', 'Node to show output from')], 'Outputs': [port('', 'Node output')],
         'Replication': 'Disabled', 'Description': 'Registro'}, 'Registro', 900, 160)
for n, p in zip(ins, pin):
    conns.append({'Start': n['Outputs'][0]['Id'], 'End': p['Id'], 'Id': gid(), 'IsHidden': 'False'})
conns.append({'Start': py['Outputs'][0]['Id'], 'End': w['Inputs'][0]['Id'], 'Id': gid(), 'IsHidden': 'False'})
note = {'Id': gid(), 'Title': 'ADLB · Automatiza tus familias de Revit\n1. Abre la FAMILIA en el Editor de familias y lanza Dynamo desde ahi.\n2. Elige el CSV y (opcional) el archivo de compartidos.\n3. Corre con SIMULAR = True y revisa el registro.\n4. Pasa SIMULAR a False y EJECUTAR a True. Ctrl+Z deshace todo.',
        'DescriptionText': None, 'IsExpanded': True, 'WidthAdjustment': 0.0, 'HeightAdjustment': 0.0,
        'Nodes': [], 'HasNestedGroups': False, 'Left': 0.0, 'Top': -190.0, 'Width': 0.0, 'Height': 0.0,
        'FontSize': 14.0, 'GroupStyleId': '00000000-0000-0000-0000-000000000000', 'InitialTop': 0.0,
        'InitialHeight': 0.0, 'TextblockHeight': 0.0, 'Background': '#FFE76A1F'}
dyn = {'Uuid': str(uuid.uuid4()), 'IsCustomNode': False, 'Description': 'ADLB - crear y asignar parametros de familia desde CSV',
       'Name': 'ADLB_Parametros_desde_CSV', 'ElementResolver': {'ResolutionMap': {}}, 'Inputs': [], 'Outputs': [],
       'Nodes': nodes, 'Connectors': conns, 'Dependencies': [], 'NodeLibraryDependencies': [], 'Thumbnail': '',
       'GraphDocumentationURL': None, 'ExtensionWorkspaceData': [], 'Author': 'ADLB', 'Linting': {}, 'Bindings': [],
       'View': {'Dynamo': {'ScaleFactor': 1.0, 'HasRunWithoutCrash': True, 'IsVisibleInDynamoLibrary': True,
                           'Version': '2.17.0.3472', 'RunType': 'Manual', 'RunPeriod': '1000'},
                'Camera': {'Name': 'Background Preview', 'EyeX': -17.0, 'EyeY': 24.0, 'EyeZ': 50.0, 'LookX': 12.0,
                           'LookY': -13.0, 'LookZ': -58.0, 'UpX': 0.0, 'UpY': 1.0, 'UpZ': 0.0},
                'ConnectorPins': [], 'NodeViews': views, 'Annotations': [note], 'X': 60.0, 'Y': 260.0, 'Zoom': 0.8}}
io.open(DST, 'w', encoding='utf-8').write(json.dumps(dyn, indent=2, ensure_ascii=False))
print('ok ->', DST)
