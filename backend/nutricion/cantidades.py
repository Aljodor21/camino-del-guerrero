"""Convierte porciones de la lista de intercambios en cantidades caseras.

"1 unidad pequeña" × 3 porciones → "3 unidades pequeñas"; "6 cucharadas" × 2 → "12 cucharadas".
Si la medida no se puede multiplicar limpio (ej. "1/5 libra" × 2), se dice cuántas veces va.
"""
import re
from decimal import Decimal
from fractions import Fraction

UNICODE = {'½': '1/2', '¼': '1/4', '¾': '3/4', '⅓': '1/3', '⅔': '2/3'}
CANTIDAD = re.compile(r'^\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)\s*(.*)$')
NO_PLURAL = {'de', 'del', 'o', 'y', 'con', 'sin'}


def _fraccion(texto):
    partes = texto.split()
    if len(partes) == 2:
        return Fraction(int(partes[0])) + Fraction(partes[1])
    return Fraction(texto.replace(',', '.'))


def _texto_fraccion(valor):
    enteros, resto = divmod(valor.numerator, valor.denominator)
    simbolo = {Fraction(1, 2): '½', Fraction(1, 4): '¼', Fraction(3, 4): '¾',
               Fraction(1, 3): '⅓', Fraction(2, 3): '⅔'}.get(Fraction(resto, valor.denominator), '')
    if not resto:
        return str(enteros)
    return f'{enteros} {simbolo}' if enteros else simbolo


def _plural(palabra):
    if not palabra or not palabra[0].isalpha() or palabra in NO_PLURAL or palabra.endswith('s'):
        return palabra
    if palabra.endswith('ón'):
        return palabra[:-2] + 'ones'
    if palabra[-1] in 'aeiouáéó':
        return palabra + 's'
    return palabra + 'es'


def _pluralizar(resto):
    """Pone en plural el sustantivo y sus adjetivos hasta el primer 'de'."""
    palabras = resto.split()
    for i, palabra in enumerate(palabras):
        if palabra in ('de', 'del', 'o', '('):
            break
        palabras[i] = _plural(palabra)
    return ' '.join(palabras)


def _escalar_una(medida, porciones):
    texto = medida
    for simbolo, fraccion in UNICODE.items():
        texto = texto.replace(simbolo, fraccion)
    coincide = CANTIDAD.match(texto)
    if not coincide:
        return None
    base, resto = _fraccion(coincide.group(1)), coincide.group(2)
    total = base * porciones
    if total.denominator not in (1, 2, 3, 4):
        return None
    if base <= 1 < total:
        resto = _pluralizar(resto)
    return f'{_texto_fraccion(total)} {resto}'.strip()


def escalar(medida, porciones, gramos_porcion=None):
    """Medida casera de varias porciones. Si no se puede decir limpio en la medida
    casera, se dice en gramos (o cuántas veces va la medida)."""
    porciones = Fraction(Decimal(str(porciones)))
    # "8 cucharadas o 2/3 de pocillo": se multiplica cada alternativa.
    alternativas = [_escalar_una(parte, porciones) for parte in re.split(r' o (?=\d|½|¼|¾)', medida)]
    if all(alternativas):
        return ' o '.join(alternativas)
    if porciones == 1:
        return medida
    if gramos_porcion:
        return f'{gramos(gramos_porcion, porciones)} g'
    return f'{_texto_fraccion(porciones)} × {medida}'


def gramos(gramos_porcion, porciones):
    if not gramos_porcion:
        return None
    return int(round(gramos_porcion * Decimal(str(float(porciones)))))


# La lista de intercambios nombra algunos alimentos por cómo se pesan (crudos). La minuta
# dice "huevos": así se le muestran al usuario, sin cambiar de qué alimento se trata.
NOMBRE_EN_MINUTA = {
    'Huevo de gallina crudo': 'Huevo',
    'Huevo de codorniz crudo': 'Huevo de codorniz',
}


def nombre_visible(alimento):
    return NOMBRE_EN_MINUTA.get(alimento.nombre, alimento.nombre)
