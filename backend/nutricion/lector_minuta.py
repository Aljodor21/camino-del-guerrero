"""Lee el PDF del plan de alimentación que entrega la nutricionista.

Del PDF se toma la minuta patrón (porciones por grupo en cada comida), las
calorías, la proteína, el menú de ejemplo y las recomendaciones. Si la tabla no
cuadra (las porciones de las comidas no suman las del día), el PDF se rechaza:
es mejor no cargar nada que cargar una minuta mal leída.
"""
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from pypdf import PdfReader

from core.exceptions import ReglaNegocioError

from .grupos import ORDEN_TIEMPO

MAX_BYTES = 10 * 1024 * 1024

TITULOS = {
    'sustitutos': 'sustitutos', 'lacteos': 'lacteos', 'carnes': 'carnes', 'leguminosas': 'leguminosas',
    'cereales': 'cereales', 'verduras': 'verduras', 'frutas': 'frutas', 'aceites': 'grasas',
    'grasas': 'grasas', 'semillas': 'semillas', 'agua': 'agua',
}
TITULO = re.compile(r'^(' + '|'.join(TITULOS) + r')\b')
COLUMNAS = {'desayuno': 'desayuno', 'onces': 'onces', 'media manana': 'onces', 'almuerzo': 'almuerzo',
            'algo': 'algo', 'cena': 'cena', 'merienda': 'merienda'}
NUMERO = re.compile(r'(?<![\w/])(\d+(?:[.,]\d+)?)(?![\w/])')
ETIQUETA_MENU = re.compile(r'^(desayuno|media manana|onces|almuerzo|algo|cena|merienda)\s*:', re.I)


class MinutaIlegibleError(ReglaNegocioError):
    pass


def _normalizar(texto):
    sin_tildes = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', sin_tildes).strip().lower()


def _decimal(texto):
    try:
        return Decimal(texto.replace(',', '.'))
    except InvalidOperation:
        raise MinutaIlegibleError('Hay un número de la minuta que no pudimos leer.')


def extraer_texto(archivo):
    if archivo.size > MAX_BYTES:
        raise MinutaIlegibleError('El PDF pesa más de 10 MB.')
    if archivo.read(5) != b'%PDF-':
        raise MinutaIlegibleError('El archivo no es un PDF.')
    archivo.seek(0)
    try:
        lector = PdfReader(archivo)
        return '\n'.join(p.extract_text(extraction_mode='layout') for p in lector.pages[:10])
    except Exception:
        raise MinutaIlegibleError('No pudimos abrir el PDF. Revisa que sea el que te envió tu nutricionista.')


def _columnas(encabezado):
    norm = _normalizar(encabezado)
    encontradas = [(norm.find(clave), codigo) for clave, codigo in COLUMNAS.items() if clave in norm]
    return [codigo for _, codigo in sorted(encontradas)]


def _tabla(lineas):
    inicio = next((i for i, l in enumerate(lineas) if 'desayuno' in _normalizar(l) and 'almuerzo' in _normalizar(l)),
                  None)
    if inicio is None:
        raise MinutaIlegibleError('No encontramos la minuta patrón en el PDF.')
    tiempos = _columnas(lineas[inicio])
    if len(tiempos) < 3:
        raise MinutaIlegibleError('No pudimos leer las comidas de la minuta.')

    porciones, titulo = {}, None
    for linea in lineas[inicio + 1:]:
        norm = _normalizar(linea)
        if 'menu sugerido' in norm or 'recomendaciones' in norm:
            break
        coincide = TITULO.match(norm)
        if coincide:
            titulo = TITULOS[coincide.group(1)]
        numeros = NUMERO.findall(linea)
        if not numeros or (titulo is None and len(numeros) != len(tiempos) + 1):
            continue
        if titulo is None:
            raise MinutaIlegibleError('Hay porciones en la minuta sin su grupo de alimentos.')
        if len(numeros) != len(tiempos) + 1:
            raise MinutaIlegibleError('Una fila de la minuta no tiene todas sus porciones.')
        if titulo in porciones:
            raise MinutaIlegibleError('Un grupo de alimentos aparece dos veces en la minuta.')
        dia, *por_comida = (_decimal(n) for n in numeros)
        suma = sum(por_comida)
        if suma and suma != dia:
            raise MinutaIlegibleError('Las porciones de las comidas no suman las del día. Revisa el PDF.')
        porciones[titulo] = {'dia': float(dia), **{t: float(p) for t, p in zip(tiempos, por_comida)}}
        titulo = None

    if len(porciones) < 4 or not any(any(v for k, v in fila.items() if k != 'dia') for fila in porciones.values()):
        raise MinutaIlegibleError('No encontramos las porciones de la minuta patrón en el PDF.')
    return porciones, sorted(set(tiempos), key=ORDEN_TIEMPO.get)


def _seccion(lineas, desde, hasta):
    dentro, salida = False, []
    for linea in lineas:
        norm = _normalizar(linea)
        if not dentro:
            dentro = desde in norm
            continue
        if any(h in norm for h in hasta):
            break
        salida.append(linea.strip())
    return salida


def _menu_ejemplo(lineas):
    menu, actual = {}, None
    for linea in _seccion(lineas, 'menu sugerido', ('recomendaciones',)):
        etiqueta = ETIQUETA_MENU.match(_normalizar(linea))
        if etiqueta:
            actual = COLUMNAS[etiqueta.group(1).lower()]
            linea = linea.split(':', 1)[1]
        elif not linea:
            continue
        if actual:
            menu[actual] = f"{menu.get(actual, '')} {linea}".strip()
    return {t: re.sub(r'\s+', ' ', texto) for t, texto in menu.items()}


def interpretar(texto):
    lineas = texto.splitlines()
    porciones, tiempos = _tabla(lineas)
    kcal = re.search(r'(\d{3,4})\s*kcal', texto, re.I)
    proteina = re.search(r'(\d+(?:[.,]\d+)?)\s*gr?s?\.?\s*de\s*prot', texto, re.I)
    recomendaciones = ' '.join(l for l in _seccion(lineas, 'recomendaciones y restricciones',
                                                   ('medidas antropometricas',)) if l)
    return {
        'porciones': porciones,
        'tiempos': tiempos,
        'kcal': int(kcal.group(1)) if kcal else None,
        'proteina_g_kg': _decimal(proteina.group(1)) if proteina else None,
        'menu_ejemplo': _menu_ejemplo(lineas),
        'recomendaciones': re.sub(r'\s+', ' ', recomendaciones).strip(),
    }


def leer(archivo):
    return interpretar(extraer_texto(archivo))
