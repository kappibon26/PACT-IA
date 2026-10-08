# -*- coding: utf-8 -*-
"""Genera ADLB_Kit_Automatiza_Familias_Revit.pdf: HTML (+ anexo de codigo) -> Chromium -> adjuntos.

  python lead-magnet/fuente/build_pdf.py
"""
import glob, html, io, os, subprocess, sys
from pypdf import PdfReader, PdfWriter

AQUI = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(AQUI)
PLANT = os.path.join(KIT, 'plantilla_dynamo')
OUT = os.path.join(KIT, 'ADLB_Kit_Automatiza_Familias_Revit.pdf')
LINEAS_POR_PAGINA = 74
ADJUNTOS = ['ADLB_Parametros_desde_CSV.dyn', 'ADLB_Parametros_desde_CSV.py',
            'ADLB_Parametros_ejemplo.csv', 'LEEME.txt']


def pagina(titulo, sub, cuerpo, n):
    return (u'<section class="page">\n'
            u'  <div class="top"><b>ADLB<i>.</i></b><span>Anexo · Plantilla Dynamo</span></div>\n'
            u'  %s\n'
            u'  <h3 style="margin-top:0">%s</h3>\n%s\n'
            u'  <div class="foot"><span>ADLB · Kit gratuito</span><span class="n">%02d</span></div>\n'
            u'</section>\n') % (titulo, sub, cuerpo, n)


def anexo(n0):
    code = io.open(os.path.join(PLANT, 'ADLB_Parametros_desde_CSV.py'), encoding='utf-8').read().rstrip('\n').split('\n')
    csv = io.open(os.path.join(PLANT, 'ADLB_Parametros_ejemplo.csv'), encoding='utf-8').read().rstrip('\n')
    primera = LINEAS_POR_PAGINA - 16          # la primera pagina lleva titulo e instrucciones
    trozos = [code[:primera]] + [code[i:i + LINEAS_POR_PAGINA] for i in range(primera, len(code), LINEAS_POR_PAGINA)]
    out = []
    for k, t in enumerate(trozos):
        titulo = (u'<div class="kicker">Anexo</div><h1 style="font-size:22pt">Código de la plantilla.</h1>'
                  u'<div class="rule"></div><p class="muted">Copia todo el bloque en un nodo <strong>Python Script</strong> '
                  u'(motor CPython3) con 4 entradas: CSV, compartidos, SIMULAR y EJECUTAR.</p>') if k == 0 else u''
        sub = u'ADLB_Parametros_desde_CSV.py · %d / %d' % (k + 1, len(trozos))
        cuerpo = u'<pre class="code">%s</pre>' % html.escape(u'\n'.join(t))
        out.append(pagina(titulo, sub, cuerpo, n0 + k))
    cuerpo = (u'<pre class="code">%s</pre>'
              u'<div class="tip"><span class="kicker">Para usarlo</span>Copia el texto en el Bloc de notas y guárdalo como '
              u'<span class="mono">.csv</span> con codificación UTF-8, o ábrelo en Excel y usa <em>Guardar como › CSV UTF-8</em>.</div>'
              ) % html.escape(csv)
    out.append(pagina(u'', u'ADLB_Parametros_ejemplo.csv', cuerpo, n0 + len(trozos)))
    return u''.join(out)


def main():
    src = io.open(os.path.join(AQUI, 'kit.html'), encoding='utf-8').read()
    css = u'pre.code { font-size: 6.55pt; line-height: 1.36; padding: 3.5mm 4mm; }\n</style>'
    src = src.replace(u'</style>', css, 1).replace(u'<!--ANEXO-->', anexo(10))
    tmp = os.path.join(AQUI, '_kit_build.html')
    io.open(tmp, 'w', encoding='utf-8').write(src)
    chrome = sorted(glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome'))[-1]
    raw = OUT + '.tmp.pdf'
    subprocess.run([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
                    '--print-to-pdf=' + raw, 'file://' + tmp], check=True, capture_output=True)
    w = PdfWriter(clone_from=PdfReader(raw))
    for f in ADJUNTOS:
        w.add_attachment(f, open(os.path.join(PLANT, f), 'rb').read())
    w.add_metadata({'/Title': 'Automatiza tus familias de Revit · Lead Magnet Kit', '/Author': 'ADLB',
                    '/Subject': 'Guía, plantilla Dynamo y checklist para automatizar familias de Revit'})
    w.page_mode = '/UseAttachments'
    with open(OUT, 'wb') as fh:
        w.write(fh)
    os.remove(raw); os.remove(tmp)
    print('ok ->', OUT, len(w.pages), 'paginas,', len(ADJUNTOS), 'adjuntos')


if __name__ == '__main__':
    sys.exit(main())
