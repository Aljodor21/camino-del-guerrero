"""Grupos de alimentos y tiempos de comida de la minuta patrón.

Son los de la minuta de la nutricionista: cada grupo agrupa alimentos que se
pueden intercambiar entre sí en la cantidad de una porción.
"""

GRUPOS = [
    ('sustitutos',  'Sustitutos'),
    ('lacteos',     'Lácteos'),
    ('carnes',      'Carnes'),
    ('leguminosas', 'Leguminosas'),
    ('cereales',    'Cereales, raíces, tubérculos y plátanos'),
    ('verduras',    'Verduras'),
    ('frutas',      'Frutas'),
    ('grasas',      'Aceites vegetales y aguacate'),
    ('semillas',    'Semillas y oleaginosas'),
    ('agua',        'Agua'),
]
NOMBRE_GRUPO = dict(GRUPOS)

# Grupos que se cumplen con alimentos de la lista de intercambios (el agua no).
GRUPOS_CON_ALIMENTOS = [g for g, _ in GRUPOS if g != 'agua']

TIEMPOS = [
    ('desayuno', 'Desayuno'),
    ('onces',    'Onces'),
    ('almuerzo', 'Almuerzo'),
    ('algo',     'Algo'),
    ('cena',     'Cena'),
    ('merienda', 'Merienda'),
]
NOMBRE_TIEMPO = dict(TIEMPOS)
# Hora de referencia de cada comida, para los avisos de las tomas.
HORA_TIEMPO = {'desayuno': (7, 0), 'onces': (10, 0), 'almuerzo': (13, 0),
               'algo': (16, 0), 'cena': (19, 0), 'merienda': (21, 0)}
ORDEN_TIEMPO = {t: i for i, (t, _) in enumerate(TIEMPOS)}

# Subgrupos de la lista de intercambios que cuentan para cada grupo de la minuta.
# La minuta dice "Aceites vegetales y aguacate": las grasas saturadas no entran.
SUBGRUPOS_PERMITIDOS = {
    'grasas': ('Poliinsaturadas', 'Monoinsaturadas'),
}
# Y dentro de esos subgrupos solo lo que la minuta nombra: aceites vegetales y aguacate
# (no salsas, mayonesa, margarina, aceitunas ni mantequilla de maní).
PREFIJOS_PERMITIDOS = {
    'grasas': ('Aceite de', 'Aguacate'),
}

# Cuándo se come por fuera de casa una comida.
POR_FUERA = [
    ('entre_semana', 'Entre semana'),
    ('siempre',      'Todos los días'),
]
