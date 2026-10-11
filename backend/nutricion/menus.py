"""Menú semanal armado solo con la minuta de la nutricionista y su lista de intercambios.

Cada comida debe cubrir exactamente las porciones que la minuta indica para ese
momento del día, con alimentos de la lista de intercambios del grupo que toca.
Si un suplemento se toma en esa comida, cubre las porciones que reemplaza.

La IA propone los platos, pero no decide qué es válido: cada comida que propone
se revisa aquí y, si usa un alimento que no está en la lista o no cuadra con las
porciones, esa comida se arma aquí con los intercambios, sin IA.
"""
import logging
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.ai_service import AIService
from core.exceptions import ReglaNegocioError

from . import cantidades, minutas
from .grupos import GRUPOS_CON_ALIMENTOS, NOMBRE_GRUPO, NOMBRE_TIEMPO, PREFIJOS_PERMITIDOS, SUBGRUPOS_PERMITIDOS
from .minutas import lunes
from .models import AlimentoIntercambio, ComidaMenu, ComponenteComida, MenuSemanal, PreferenciasComida

log = logging.getLogger(__name__)

PASO = Decimal('0.5')
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MOTIVOS = {
    'tiempo':       'No tiene tiempo de cocinar: algo que se arme en menos de 10 minutos o sin cocción.',
    'ingredientes': 'No tiene los ingredientes de la comida actual: usa otros alimentos, comunes en una tienda de barrio.',
    'antojo':       'Quiere comer algo distinto a la comida actual.',
}
# La lista los permite, pero no se proponen solos al armar una comida sin IA.
NO_PROPONER = ('chocolate', 'choco', 'froot', 'azucarad', 'wafer', 'cucas', 'sandwich', 'crispetas',
               'palitos', 'pepperoni', 'pancake', 'mayonesa', 'ranch', 'pesto', 'harina', 'maicena',
               'sabor a queso', 'codorniz', 'vinagreta')
# Palabras del menú de ejemplo que nombran alimentos de la lista con otro nombre.
SINONIMOS = {'pollo': ('pechu', 'muslo', 'contr'), 'pescad': ('pargo', 'salmo', 'truch', 'atun', 'bagre')}
VACIAS = {'con', 'sin', 'del', 'los', 'las', 'una', 'uno', 'para', 'tipo', 'porcio', 'grasa', 'plato', 'bebid',
          'agua', 'azuca'}


def _raices(texto):
    """Raíces de las palabras: 'Papas cocidas' → ['papa', 'cocid']."""
    plano = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode().lower()
    return [r for r in (p.rstrip('s')[:5] for p in re.findall(r'[a-z]{3,}', plano)) if r not in VACIAS]


def _sustantivo(nombre):
    """Raíz de la palabra con que empieza el nombre: 'Arroz blanco, cocido' → 'arroz'."""
    raices = _raices(nombre)
    return raices[0] if raices else nombre


def _en_ejemplo(nombre, ejemplo):
    """El alimento aparece en el menú de ejemplo de la nutricionista."""
    return _sustantivo(nombre) in ejemplo


def _palabras_ejemplo(texto):
    palabras = set(_raices(texto))
    for palabra in list(palabras):
        palabras.update(SINONIMOS.get(palabra, ()))
    return palabras


def _del_ejemplo(candidatos, texto):
    """Los alimentos que ese texto de la minuta nombra. Entre los que comparten el nombre,
    quedan los que repiten más palabras: "yogur griego" gana sobre "yogur dietético"."""
    palabras = _palabras_ejemplo(texto)
    nombrados = [a for a in candidatos if _en_ejemplo(a.nombre, palabras)]
    if not nombrados:
        return []

    def parecido(a):
        return len(set(_raices(a.nombre)) & palabras)

    mejor = max(parecido(a) for a in nombrados)
    return [a for a in nombrados if parecido(a) == mejor]


class Catalogo:
    """Alimentos de la lista de intercambios que valen para cada grupo de la minuta."""

    def __init__(self):
        self.por_grupo, self.por_id = defaultdict(list), {}
        for alimento in AlimentoIntercambio.objects.filter(grupo__in=GRUPOS_CON_ALIMENTOS + ['libres']):
            permitidos = SUBGRUPOS_PERMITIDOS.get(alimento.grupo)
            if permitidos and alimento.subgrupo not in permitidos:
                continue
            prefijos = PREFIJOS_PERMITIDOS.get(alimento.grupo)
            if prefijos and not alimento.nombre.startswith(prefijos):
                continue
            self.por_grupo[alimento.grupo].append(alimento)
            self.por_id[alimento.id] = alimento

    def de_la_minuta(self, minuta):
        """Solo los alimentos que la minuta nombra en su menú de ejemplo. Un grupo que la
        minuta no nombra (por ejemplo "1 porción de fruta") conserva toda su lista."""
        ejemplos = list(minuta.menu_ejemplo.values())
        recortado = object.__new__(Catalogo)
        recortado.por_grupo, recortado.por_id = {}, {}
        for grupo, alimentos in self.por_grupo.items():
            nombrados = {a.id for texto in ejemplos for a in _del_ejemplo(alimentos, texto)}
            if nombrados and grupo == 'grasas':
                # La minuta pide "una porción de grasa para cocción": los aceites vegetales valen.
                nombrados |= {a.id for a in alimentos if a.nombre.startswith('Aceite')}
            elegidos = [a for a in alimentos if not nombrados or a.id in nombrados]
            recortado.por_grupo[grupo] = elegidos
            recortado.por_id.update({a.id: a for a in elegidos})
        return recortado

    def del_grupo(self, alimento_id, grupo):
        alimento = self.por_id.get(alimento_id)
        return alimento if alimento and alimento.grupo == grupo else None


class Contexto:
    """Todo lo que define qué debe llevar cada comida de un usuario."""

    def __init__(self, usuario, minuta):
        self.usuario, self.minuta = usuario, minuta
        self.catalogo = Catalogo()
        # Lo que se puede ofrecer o proponer: lo que la minuta nombra (y lo que no nombra, su grupo).
        self.permitidos = self.catalogo.de_la_minuta(minuta)
        self.suplementos = list(minuta.proceso.suplementos.select_related('proceso'))
        self.preferencias = (PreferenciasComida.objects.filter(usuario=usuario).first()
                             or PreferenciasComida(usuario=usuario))

    def tomas_en(self, fecha, tiempo):
        """[(suplemento, toma)] de lo que se toma en esa comida ese día."""
        return [(s, toma) for s in self.suplementos if s.activo_en(fecha)
                if (toma := s.toma_en(tiempo)) is not None]

    def requerido(self, fecha, tiempo):
        """{grupo: porciones} que la comida debe cubrir con alimentos."""
        requerido = self.minuta.porciones_en(tiempo)
        for _, toma in self.tomas_en(fecha, tiempo):
            for grupo, porciones in toma['reemplaza'].items():
                if grupo in requerido:
                    requerido[grupo] = max(Decimal(0), requerido[grupo] - Decimal(str(porciones)))
        return {g: p for g, p in requerido.items() if p > 0}


class Elector:
    """Arma comidas con los intercambios, sin IA. Prefiere lo que la nutricionista
    puso en su menú de ejemplo para ese momento del día y rota para no repetir."""

    def __init__(self, contexto, semilla):
        self.contexto = contexto
        self.azar = random.Random(semilla)
        self.usos = Counter()
        # Uno solo para toda la semana: es lo que se compra.
        aceites = [a for a in contexto.permitidos.por_grupo['grasas'] if a.nombre.startswith('Aceite')]
        comunes = [a for a in aceites if a.nombre in ('Aceite de canola', 'Aceite de girasol')] or aceites
        self.aceite = self.azar.choice(comunes) if comunes else None

    def opciones_para(self, grupo, tiempo, sin_aceites=False):
        candidatos = [a for a in self.contexto.permitidos.por_grupo.get(grupo, [])
                      if not any(p in a.nombre.lower() for p in NO_PROPONER)
                      and not (sin_aceites and a.nombre.startswith('Aceite'))]
        # Primero lo que la minuta nombra para esa comida; si no nombra nada de este grupo,
        # lo que nombra en otras comidas; solo al final, la lista de intercambios del grupo.
        ejemplos = self.contexto.minuta.menu_ejemplo
        for texto in [ejemplos.get(tiempo, '')] + [t for k, t in ejemplos.items() if k != tiempo]:
            nombrados = _del_ejemplo(candidatos, texto)
            if nombrados:
                return nombrados
        return candidatos

    def nombra(self, grupo):
        """La minuta nombra alimentos de este grupo en su menú de ejemplo (no solo "una fruta")."""
        alimentos = [a for a in self.contexto.catalogo.por_grupo.get(grupo, [])
                     if not (grupo == 'grasas' and a.nombre.startswith('Aceite'))]
        return any(_del_ejemplo(alimentos, t) for t in self.contexto.minuta.menu_ejemplo.values())

    def elegir(self, grupo, tiempo, evitar=(), opciones=None):
        """`evitar`: ids ya usados en la comida; tampoco se repite su sustantivo (dos arroces)."""
        opciones = opciones or self.opciones_para(grupo, tiempo)
        por_id = self.contexto.permitidos.por_id
        vistos = {_sustantivo(por_id[i].nombre) for i in evitar if i in por_id}
        libres = ([a for a in opciones if a.id not in evitar and _sustantivo(a.nombre) not in vistos]
                  or [a for a in opciones if a.id not in evitar] or opciones)
        menor = min(self.usos[a.id] for a in libres)
        alimento = self.azar.choice([a for a in libres if self.usos[a.id] == menor])
        self.usos[alimento.id] += 1
        return alimento

    def componentes(self, requerido, tiempo, evitar=()):
        salida, usados = [], set(evitar)
        for grupo, porciones in requerido.items():
            partes = [porciones]
            if grupo == 'grasas' and porciones >= 2:
                # Una porción para cocinar y el resto, por ejemplo, en aguacate.
                if self.aceite:
                    salida.append((self.aceite, Decimal(1)))
                    resto = self.elegir(grupo, tiempo, usados, self.opciones_para(grupo, tiempo, sin_aceites=True))
                    salida.append((resto, porciones - 1))
                    continue
            elif grupo == 'cereales' and porciones >= 3:
                mitad = (porciones / 2).quantize(Decimal(1), rounding='ROUND_CEILING')
                partes = [mitad, porciones - mitad]
            for parte in partes:
                alimento = self.elegir(grupo, tiempo, usados)
                usados.add(alimento.id)
                salida.append((alimento, parte))
        return salida


def validar(propuestos, requerido, catalogo):
    """[(alimento, porciones)] si la propuesta cubre exacto lo que pide la minuta con
    alimentos de la lista; None si no."""
    try:
        suma, salida = defaultdict(Decimal), []
        for alimento_id, porciones in propuestos:
            alimento = catalogo.por_id.get(int(alimento_id))
            porciones = Decimal(str(porciones))
            if alimento is None:
                return None
            if alimento.grupo == 'libres':
                salida.append((alimento, Decimal(0)))
                continue
            if alimento.grupo not in requerido or porciones <= 0 or porciones % PASO:
                return None
            suma[alimento.grupo] += porciones
            salida.append((alimento, porciones))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return salida if dict(suma) == requerido else None


def _texto_catalogo(catalogo, grupos):
    bloques = []
    for grupo in [*grupos, 'libres']:
        lineas = [f'{a.id}: {a.nombre} = {a.medida}' + (f' ({a.gramos} g)' if a.gramos else '')
                  for a in catalogo.por_grupo.get(grupo, [])]
        titulo = 'Libres (opcionales, porciones 0)' if grupo == 'libres' else NOMBRE_GRUPO[grupo]
        bloques.append(f'### {titulo}\n' + '\n'.join(lineas))
    return '\n\n'.join(bloques)


def _texto_requerido(requerido):
    return ', '.join(f'{grupo} {porciones.normalize()}' for grupo, porciones in requerido.items())


def _crear_componentes(comida, componentes):
    ComponenteComida.objects.bulk_create(
        ComponenteComida(comida=comida, alimento=a, porciones=p) for a, p in componentes)


def minuta_para_menu(usuario):
    minutas.proceso_con_alimentacion(usuario)
    minuta = minutas.vigente_de(usuario)
    if minuta is None:
        raise ReglaNegocioError('Carga primero el plan de tu nutricionista.')
    return minuta


def generar(usuario, semana, usar_ia=True):
    minuta = minuta_para_menu(usuario)
    contexto = Contexto(usuario, minuta)
    inicio = minuta.proceso.fecha_inicio
    fechas = [f for f in (semana + timedelta(days=i) for i in range(7)) if f >= inicio]
    if not fechas:
        raise ReglaNegocioError(
            f'Tu proceso inicia el {inicio.day}/{inicio.month}: arma el menú de la semana en que empieza.')
    pedidos = [(f, t, r) for f in fechas for t in minuta.tiempos() if (r := contexto.requerido(f, t))]
    en_casa = [(f, t, r) for f, t, r in pedidos if not contexto.preferencias.come_por_fuera(t, f)]

    elector = Elector(contexto, semilla=f'{usuario.pk}-{semana.isoformat()}')
    # Lo que la minuta nombra se arma con esos alimentos. Solo lo que no nombra (por ejemplo
    # "1 porción de fruta") lo propone la IA, con lo que ya sabemos de la persona.
    abiertos = {}
    for f, t, r in en_casa:
        libre = {g: p for g, p in r.items() if not elector.nombra(g)}
        if libre:
            abiertos[(f, t)] = libre

    propuestas = {}
    if usar_ia and abiertos:
        anterior = usuario.menus.filter(semana=semana - timedelta(days=7)).first()
        evitar = sorted({a.nombre for c in anterior.comidas.all() for a in
                         (x.alimento for x in c.componentes.all())}) if anterior else []
        grupos = sorted({g for r in abiertos.values() for g in r}, key=GRUPOS_CON_ALIMENTOS.index)
        try:
            respuesta = AIService().proponer_menu(
                usuario=usuario, minuta=minuta,
                catalogo=_texto_catalogo(contexto.permitidos, grupos),
                pedidos='\n'.join(f'{f.isoformat()} ({DIAS[f.weekday()]}) {t}: {_texto_requerido(r)}'
                                  for (f, t), r in abiertos.items()),
                evitar=evitar,
            )
            propuestas = {(c.get('fecha'), c.get('tiempo')): c for c in respuesta.get('comidas', [])
                          if isinstance(c, dict)}
        except Exception:
            log.exception('La IA no pudo completar el menú; se arma con los intercambios.')

    validas = 0
    with transaction.atomic():
        MenuSemanal.objects.filter(usuario=usuario, semana=semana).delete()
        menu = MenuSemanal.objects.create(usuario=usuario, minuta=minuta, semana=semana)
        for fecha, tiempo, requerido in pedidos:
            libre = abiertos.get((fecha, tiempo), {})
            componentes = elector.componentes({g: p for g, p in requerido.items() if g not in libre}, tiempo)
            if libre:
                propuesta = propuestas.get((fecha.isoformat(), tiempo)) or {}
                de_la_ia = validar(propuesta.get('componentes') or [], libre, contexto.permitidos)
                if de_la_ia:
                    validas += 1
                componentes += de_la_ia or elector.componentes(libre, tiempo)
            comida = ComidaMenu.objects.create(
                menu=menu, fecha=fecha, tiempo=tiempo, nombre='',
                por_fuera=contexto.preferencias.come_por_fuera(tiempo, fecha))
            _crear_componentes(comida, componentes)
        if validas:
            menu.generado_con_ia = True
            menu.save(update_fields=['generado_con_ia'])
    return menu


def _contexto_de(comida):
    return Contexto(comida.menu.usuario, comida.menu.minuta)


def opciones(componente):
    """Alimentos que pueden ir en lugar de ese, en las mismas porciones: los que la minuta nombra
    para ese grupo o, si no nombra ninguno, los de la lista de intercambios del grupo."""
    permitidos = _contexto_de(componente.comida).permitidos
    return [a for a in permitidos.por_grupo.get(componente.alimento.grupo, []) if a.id != componente.alimento_id]


@transaction.atomic
def cambiar_alimento(comida, componente, alimento_id):
    alimento = _contexto_de(comida).permitidos.del_grupo(alimento_id, componente.alimento.grupo)
    if alimento is None:
        raise ReglaNegocioError('Ese alimento no está en tu minuta como cambio de este grupo.')
    componente.alimento = alimento
    componente.save(update_fields=['alimento'])
    comida.nombre, comida.cambiada = '', True
    comida.save(update_fields=['nombre', 'cambiada'])
    return comida


@transaction.atomic
def sugerir(comida, motivo):
    """Otra opción para esa comida, con las mismas porciones de la minuta."""
    contexto = _contexto_de(comida)
    requerido = contexto.requerido(comida.fecha, comida.tiempo)
    actuales = list(comida.componentes.select_related('alimento'))
    componentes, nombre = None, ''
    try:
        grupos = sorted(requerido, key=GRUPOS_CON_ALIMENTOS.index)
        respuesta = AIService().proponer_comida(
            usuario=comida.menu.usuario, minuta=contexto.minuta,
            tiempo=NOMBRE_TIEMPO[comida.tiempo], requerido=_texto_requerido(requerido),
            catalogo=_texto_catalogo(contexto.permitidos, grupos),
            actual=', '.join(c.alimento.nombre for c in actuales), motivo=MOTIVOS[motivo],
        )
        componentes = validar(respuesta.get('componentes') or [], requerido, contexto.permitidos)
        nombre = str(respuesta.get('nombre') or '')[:120] if componentes else ''
    except Exception:
        log.exception('La IA no pudo proponer otra comida; se arma con los intercambios.')
    if not componentes:
        elector = Elector(contexto, semilla=random.random())
        componentes = elector.componentes(requerido, comida.tiempo, evitar={c.alimento_id for c in actuales})

    comida.componentes.all().delete()
    _crear_componentes(comida, componentes)
    comida.nombre, comida.cambiada, comida.por_fuera = nombre, True, False
    comida.save(update_fields=['nombre', 'cambiada', 'por_fuera'])
    return comida


def marcar_por_fuera(comida, por_fuera):
    comida.por_fuera = por_fuera
    comida.save(update_fields=['por_fuera'])
    return comida


def _ajustar(comida, requerido, elector):
    """Deja la comida cubriendo exacto lo requerido, tocando lo menos posible."""
    componentes = [c for c in comida.componentes.select_related('alimento') if c.alimento.grupo != 'libres']
    for c in componentes:
        if c.alimento.grupo not in requerido:
            c.delete()
    for grupo, porciones in requerido.items():
        del_grupo = [c for c in componentes if c.alimento.grupo == grupo]
        diferencia = porciones - sum((c.porciones for c in del_grupo), Decimal(0))
        if diferencia > 0 and del_grupo:
            del_grupo[0].porciones += diferencia
            del_grupo[0].save(update_fields=['porciones'])
        elif diferencia > 0:
            ComponenteComida.objects.create(comida=comida, alimento=elector.elegir(grupo, comida.tiempo),
                                            porciones=diferencia)
        for c in reversed(del_grupo):
            if diferencia >= 0:
                break
            quitar = min(c.porciones, -diferencia)
            diferencia += quitar
            c.porciones -= quitar
            if c.porciones:
                c.save(update_fields=['porciones'])
            else:
                c.delete()


@transaction.atomic
def reajustar(usuario):
    """Tras un cambio de suplementos o de comidas por fuera, pone al día las comidas
    que faltan de los menús de esta semana en adelante."""
    hoy = timezone.localdate()
    for menu in usuario.menus.filter(semana__gte=lunes(hoy)).select_related('minuta__proceso'):
        contexto = Contexto(usuario, menu.minuta)
        elector = Elector(contexto, semilla=f'{usuario.pk}-{menu.semana.isoformat()}-ajuste')
        for comida in menu.comidas.filter(fecha__gte=hoy):
            requerido = contexto.requerido(comida.fecha, comida.tiempo)
            _ajustar(comida, requerido, elector)
            if comida.fecha > hoy:
                por_fuera = contexto.preferencias.come_por_fuera(comida.tiempo, comida.fecha)
                if por_fuera != comida.por_fuera:
                    marcar_por_fuera(comida, por_fuera)


def consolidado(menu):
    """{alimento: porciones} de lo que se cocina en casa esa semana."""
    total = defaultdict(Decimal)
    for c in ComponenteComida.objects.filter(comida__menu=menu, comida__por_fuera=False).select_related('alimento'):
        total[c.alimento] += c.porciones
    return total


CATEGORIA_MERCADO = {
    'carnes': 'proteinas', 'sustitutos': 'proteinas', 'leguminosas': 'proteinas', 'lacteos': 'lacteos',
    'cereales': 'granos', 'verduras': 'verduras', 'libres': 'verduras', 'frutas': 'frutas',
    'grasas': 'condimentos', 'semillas': 'condimentos',
}


def leche_para_proteina(menu, num_personas=1):
    """ml de leche de la semana para mezclar la proteína, o 0 si no se mezcla con leche.
    Es el líquido de la porción de cada día en que se toma (una porción al día)."""
    suplementos = menu.minuta.proceso.suplementos.filter(liquido='leche', liquido_ml__isnull=False)
    ml = 0
    for s in suplementos:
        dias = sum(1 for i in range(7) if s.activo_en(menu.semana + timedelta(days=i)))
        ml += s.liquido_ml * dias
    return ml * num_personas


def item_leche(ml):
    """El renglón de la lista de mercado para esa leche."""
    litros = f'{ml / 1000:.1f}'.replace('.', ',').removesuffix(',0')
    return {'nombre': 'Leche para la proteína', 'cantidad': f'{litros} L' if ml >= 1000 else f'{ml} ml',
            'frecuencia': 'semanal'}
