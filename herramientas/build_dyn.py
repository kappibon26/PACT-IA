# -*- coding: utf-8 -*-
"""
Genera dynamo/AVSA_Generar_Familia_Equipo.dyn a partir de dynamo/AVSA_Generar_Familia_Equipo.py
(el codigo del nodo Python vive en el .py; volver a correr esto despues de editarlo).

  python herramientas/build_dyn.py
"""
import io
import json
import os
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'dynamo', 'AVSA_Generar_Familia_Equipo.py')
DST = os.path.join(ROOT, 'dynamo', 'AVSA_Generar_Familia_Equipo.dyn')


def gid():
    return uuid.uuid4().hex


def port(name='', desc=''):
    return {'Id': gid(), 'Name': name, 'Description': desc, 'UsingDefaultValue': False,
            'Level': 2, 'UseLevels': False, 'KeepListStructure': False}


def main():
    code = io.open(SRC, encoding='utf-8').read()
    nodes, views, conns = [], [], []

    def add(node, name, x, y, is_input=False):
        nodes.append(node)
        views.append({'Id': node['Id'], 'Name': name, 'IsSetAsInput': is_input, 'IsSetAsOutput': False,
                      'Excluded': False, 'ShowGeometry': True, 'X': x, 'Y': y})
        return node

    def file_node(value, name, y, directory=False):
        cls = 'Directory' if directory else 'Filename'
        n = {'ConcreteType': 'CoreNodeModels.Input.%s, CoreNodeModels' % cls, 'HintPath': value,
             'InputValue': value, 'NodeType': 'ExtensionNode', 'Id': gid(), 'Inputs': [],
             'Outputs': [port('', 'Ruta')], 'Replication': 'Disabled', 'Description': name}
        return add(n, name, 0, y, True)

    def bool_node(value, name, y):
        n = {'ConcreteType': 'CoreNodeModels.Input.BoolSelector, CoreNodeModels', 'NodeType': 'BooleanInputNode',
             'InputValue': value, 'Id': gid(), 'Inputs': [], 'Outputs': [port('', 'Boolean')],
             'Replication': 'Disabled', 'Description': name}
        return add(n, name, 0, y, True)

    def str_node(value, name, y):
        n = {'ConcreteType': 'CoreNodeModels.Input.StringInput, CoreNodeModels', 'NodeType': 'StringInputNode',
             'InputValue': value, 'Id': gid(), 'Inputs': [], 'Outputs': [port('', 'String')],
             'Replication': 'Disabled', 'Description': name}
        return add(n, name, 0, y, True)

    ins = [
        file_node(r'C:\RUTA\PACT-IA\dynamo\specs\spec_PEL01_CPM7730.py', '1 - Spec del equipo (.py)', 0),
        file_node(r'C:\RUTA\Dynamo_BIM_Claude\familias\equipos', '2 - Carpeta de salida .rfa', 130, True),
        file_node(r'C:\RUTA\Dynamo_BIM_Claude\AVSA_Parametros_Compartidos.txt', '3 - Parametros compartidos', 260),
        bool_node(True, '4 - Cargar en el proyecto', 390),
        bool_node(False, '5 - EJECUTAR', 500),
        str_node('', '6 - Plantilla .rft (vacio = automatica)', 610),
    ]
    py_inputs = [port('IN[%d]' % i, 'Input #%d' % i) for i in range(len(ins))]
    py = {'ConcreteType': 'PythonNodeModels.PythonNode, PythonNodeModels', 'NodeType': 'PythonScriptNode',
          'Code': code, 'Engine': 'CPython3', 'VariableInputPorts': True, 'Id': gid(),
          'Inputs': py_inputs, 'Outputs': [port('OUT', 'Result of the python script')],
          'Replication': 'Disabled', 'Description': 'AVSA - generar familia de equipo'}
    add(py, 'AVSA - Generar familia', 520, 250)
    watch = {'ConcreteType': 'CoreNodeModels.Watch, CoreNodeModels', 'NodeType': 'ExtensionNode',
             'Id': gid(), 'Inputs': [port('', 'Node to show output from')], 'Outputs': [port('', 'Node output')],
             'Replication': 'Disabled', 'Description': 'Registro'}
    add(watch, 'Registro', 900, 250)

    for n, p in zip(ins, py_inputs):
        conns.append({'Start': n['Outputs'][0]['Id'], 'End': p['Id'], 'Id': gid(), 'IsHidden': 'False'})
    conns.append({'Start': py['Outputs'][0]['Id'], 'End': watch['Inputs'][0]['Id'], 'Id': gid(), 'IsHidden': 'False'})

    dyn = {
        'Uuid': str(uuid.UUID(gid())), 'IsCustomNode': False, 'Description': 'AVSA - generador de familias de equipos',
        'Name': 'AVSA_Generar_Familia_Equipo', 'ElementResolver': {'ResolutionMap': {}},
        'Inputs': [], 'Outputs': [], 'Nodes': nodes, 'Connectors': conns, 'Dependencies': [],
        'NodeLibraryDependencies': [], 'Thumbnail': '', 'GraphDocumentationURL': None,
        'ExtensionWorkspaceData': [], 'Author': 'AVSA', 'Linting': {}, 'Bindings': [],
        'View': {
            'Dynamo': {'ScaleFactor': 1.0, 'HasRunWithoutCrash': True, 'IsVisibleInDynamoLibrary': True,
                       'Version': '2.17.0.3472', 'RunType': 'Manual', 'RunPeriod': '1000'},
            'Camera': {'Name': 'Background Preview', 'EyeX': -17.0, 'EyeY': 24.0, 'EyeZ': 50.0,
                       'LookX': 12.0, 'LookY': -13.0, 'LookZ': -58.0, 'UpX': 0.0, 'UpY': 1.0, 'UpZ': 0.0},
            'ConnectorPins': [], 'NodeViews': views, 'Annotations': [], 'X': 40.0, 'Y': 40.0, 'Zoom': 0.8,
        },
    }
    with io.open(DST, 'w', encoding='utf-8') as f:
        f.write(json.dumps(dyn, indent=2, ensure_ascii=False))
    print('ok ->', DST)


if __name__ == '__main__':
    main()
