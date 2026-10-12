"""Qué dispositivo es, a partir del User-Agent y de lo que la app informa."""
import re

# Lo que NO se guarda de la consulta (valor tapado).
SECRETOS = re.compile(r'token|clave|password|secret|firma|auth|key', re.I)

_ANDROID = re.compile(r'Android\s+([\d.]+)(?:;\s*([^;)]+?))?(?:\s+Build/[^;)]*)?\s*[;)]')
_IOS = re.compile(r'(iPhone|iPad).*?OS\s+([\d_]+)')
_NAVEGADORES = [
    ('Edge', re.compile(r'Edg(?:e|A|iOS)?/([\d.]+)')),
    ('Opera', re.compile(r'OPR/([\d.]+)')),
    ('Firefox', re.compile(r'(?:Firefox|FxiOS)/([\d.]+)')),
    ('Chrome', re.compile(r'(?:Chrome|CriOS)/([\d.]+)')),
    ('Safari', re.compile(r'Version/([\d.]+).*Safari/')),
]


def _mayor(version):
    return version.split('.')[0]


def interpretar(agente, cliente_declarado=''):
    """{cliente, sistema, dispositivo, navegador} de un User-Agent.

    La app instalada se reconoce porque la propia app lo dice (`X-Cliente: app`) o porque es
    un WebView de Android (`; wv)`)."""
    agente = agente or ''
    es_app = cliente_declarado == 'app' or ('; wv)' in agente and 'Android' in agente)
    info = {'cliente': 'app' if es_app else 'web', 'sistema': '', 'dispositivo': '', 'navegador': ''}

    if m := _ANDROID.search(agente):
        info['sistema'] = f'Android {_mayor(m.group(1))}'
        modelo = (m.group(2) or '').strip()
        info['dispositivo'] = modelo if modelo and modelo != 'K' else 'Celular Android'
    elif m := _IOS.search(agente):
        info['sistema'] = f'iOS {_mayor(m.group(2).replace("_", "."))}'
        info['dispositivo'] = m.group(1)
    elif 'Windows' in agente:
        info['sistema'], info['dispositivo'] = 'Windows', 'Computador'
    elif 'Mac OS X' in agente or 'Macintosh' in agente:
        info['sistema'], info['dispositivo'] = 'macOS', 'Computador'
    elif 'Linux' in agente or 'X11' in agente:
        info['sistema'], info['dispositivo'] = 'Linux', 'Computador'

    if es_app:
        info['navegador'] = 'App'
    else:
        for nombre, patron in _NAVEGADORES:
            if m := patron.search(agente):
                info['navegador'] = f'{nombre} {_mayor(m.group(1))}'
                break
    return info


def consulta_limpia(query_string, limite=300):
    """La consulta sin valores sensibles y sin pasarse de largo."""
    partes = []
    for trozo in (query_string or '').split('&'):
        if not trozo:
            continue
        clave, _, valor = trozo.partition('=')
        partes.append(f'{clave}=***' if SECRETOS.search(clave) else trozo)
    return '&'.join(partes)[:limite]
