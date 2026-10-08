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
ADJUNTOS = ['ADLB_Plantilla_Familia.xlsx', 'ADLB_Generar_Familia.dyn', 'ADLB_Generar_Familia.py', 'LEEME.txt']


def pagina(titulo, sub, cuerpo, n):
    return (u'<section class="page">\n'
            u'  <div class="top"><b>ADLB<i>.</i></b><span>Anexo técnico</span></div>\n'
            u'  %s\n'
            u'  <h3 style="margin-top:0">%s</h3>\n%s\n'
            u'  <div class="foot"><span>ADLB · Kit gratuito</span><span class="n">%02d</span></div>\n'
            u'</section>\n') % (titulo, sub, cuerpo, n)


def anexo(n0):
    code = io.open(os.path.join(PLANT, 'ADLB_Generar_Familia.py'), encoding='utf-8').read().rstrip('\n').split('\n')
    primera = LINEAS_POR_PAGINA - 18          # la primera pagina lleva titulo e instrucciones
    trozos = [code[:primera]] + [code[i:i + LINEAS_POR_PAGINA] for i in range(primera, len(code), LINEAS_POR_PAGINA)]
    out = []
    for k, t in enumerate(trozos):
        titulo = (u'<div class="kicker">Anexo técnico · no necesitas leerlo</div><h1 style="font-size:22pt">Código del nodo.</h1>'
                  u'<div class="rule"></div><p class="muted">Ya viene dentro de <span class="mono">ADLB_Generar_Familia.dyn</span>. '
                  u'Úsalo solo si tu lector de PDF no muestra los adjuntos: crea un nodo <strong>Python Script</strong> (CPython3) '
                  u'con 7 entradas y pega este código completo.</p>') if k == 0 else u''
        sub = u'ADLB_Generar_Familia.py · %d / %d' % (k + 1, len(trozos))
        out.append(pagina(titulo, sub, u'<pre class="code">%s</pre>' % html.escape(u'\n'.join(t)), n0 + k))
    return u''.join(out)


def main():
    src = io.open(os.path.join(AQUI, 'kit.html'), encoding='utf-8').read()
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
                    '/Subject': 'De tu dibujo a una familia de Revit: Excel + Dynamo'})
    w.page_mode = '/UseAttachments'
    with open(OUT, 'wb') as fh:
        w.write(fh)
    os.remove(raw); os.remove(tmp)
    print('ok ->', OUT, len(w.pages), 'paginas,', len(ADJUNTOS), 'adjuntos')


if __name__ == '__main__':
    sys.exit(main())
