"""Correos de la app, con el estilo de la página: fondo oscuro, rojo guerrero y dorado.

Todos llevan HTML (para que se vean bien) y la misma versión en texto plano (por si el
correo no muestra HTML). Un fallo al enviar se anota en el log y nunca tumba lo que se hacía.
"""
import logging
from html import escape
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage

log = logging.getLogger(__name__)

FONDO, TARJETA, TEXTO, APAGADO = '#100d0b', '#1b1511', '#f3ece7', '#a89f98'
ROJO, DORADO = '#C0392B', '#D4AF37'
LOGO = Path(__file__).parent / 'assets' / 'logo-correo.png'
FUENTE = "'Barlow', 'Segoe UI', Helvetica, Arial, sans-serif"


def _url(ruta):
    return f'{settings.FRONTEND_URL.rstrip("/")}{ruta}'


def _html(titulo, parrafos, boton=None, nota=''):
    """boton: (texto, url). Diseño de una columna con tablas, que es lo que aguantan los correos."""
    cuerpo = ''.join(
        f'<p style="margin:0 0 16px;font-size:16px;line-height:1.55;color:{TEXTO};">{p}</p>' for p in parrafos)
    if boton:
        texto, url = boton
        cuerpo += (
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px 0 8px;"><tr>'
            f'<td style="background:{ROJO};border-radius:10px;">'
            f'<a href="{escape(url)}" style="display:inline-block;padding:14px 28px;font-family:{FUENTE};'
            f'font-size:16px;font-weight:700;color:#ffffff;text-decoration:none;">{escape(texto)}</a>'
            f'</td></tr></table>'
            f'<p style="margin:12px 0 0;font-size:13px;line-height:1.5;color:{APAGADO};">'
            f'Si el botón no abre, copia este enlace en tu navegador:<br>'
            f'<a href="{escape(url)}" style="color:{DORADO};word-break:break-all;">{escape(url)}</a></p>')
    if nota:
        cuerpo += f'<p style="margin:24px 0 0;font-size:13px;line-height:1.5;color:{APAGADO};">{nota}</p>'
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<title>{escape(titulo)}</title></head>
<body style="margin:0;padding:0;background:{FONDO};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};">
<tr><td align="center" style="padding:32px 16px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">
    <tr><td align="center" style="padding:0 0 20px;">
      <img src="cid:logo" width="150" alt="Camino del Guerrero" style="display:block;border:0;width:150px;height:auto;">
    </td></tr>
    <tr><td style="background:{TARJETA};border-radius:16px;border-top:3px solid {ROJO};padding:32px 28px;font-family:{FUENTE};">
      <h1 style="margin:0 0 18px;font-size:24px;line-height:1.25;color:{TEXTO};">{escape(titulo)}</h1>
      {cuerpo}
    </td></tr>
    <tr><td align="center" style="padding:20px 8px 0;font-family:{FUENTE};font-size:12px;line-height:1.5;color:{APAGADO};">
      Camino del Guerrero · tu proceso, a tu ritmo.
    </td></tr>
  </table>
</td></tr></table></body></html>'''


class CorreoConLogo(EmailMessage):
    """Texto plano + HTML, con el logo dentro del correo (se ve aunque el cliente no cargue
    imágenes de internet)."""

    def __init__(self, *args, html, **kwargs):
        super().__init__(*args, **kwargs)
        self.html = html

    def _add_bodies(self, msg):
        msg.set_content(self.body)
        msg.add_alternative(self.html, subtype='html')
        msg.get_payload()[1].add_related(LOGO.read_bytes(), 'image', 'png', cid='<logo>',
                                         filename='logo.png', disposition='inline')


def _enviar(destino, asunto, texto, html):
    try:
        CorreoConLogo(asunto, texto, settings.DEFAULT_FROM_EMAIL, [destino], html=html).send(fail_silently=False)
    except Exception:
        log.exception('No se pudo enviar el correo "%s".', asunto)


def enviar_recuperacion(usuario, enlace, minutos):
    html = _html(
        'Recupera tu clave',
        [f'Hola {escape(usuario.nombre)}, pediste crear una clave nueva.',
         f'Tu usuario es <strong style="color:{DORADO};">{escape(usuario.email)}</strong>.'],
        boton=('Crear clave nueva', enlace),
        nota=f'El enlace dura {minutos} minutos, sirve una sola vez y solo se abre en el navegador '
             'donde pediste recuperar la clave. Si no fuiste tú, ignora este mensaje: tu clave sigue igual.')
    texto = (f'Hola {usuario.nombre},\n\nPediste crear una clave nueva en Camino del Guerrero.\n\n'
             f'Tu usuario es: {usuario.email}\n\nCrea tu clave aquí (dura {minutos} minutos, sirve una sola vez y solo se abre en el navegador '
             f'donde la pediste):\n{enlace}\n\nSi no fuiste tú, ignora este mensaje: tu clave sigue igual.')
    _enviar(usuario.email, 'Recupera tu clave de Camino del Guerrero', texto, html)


def enviar_bienvenida(usuario):
    entrada = _url('/auth/login')
    html = _html(
        f'Bienvenido, {usuario.nombre}',
        ['Tu cuenta ya está lista. Con la app llevas tu proceso de principio a fin: tus medidas, '
         'el plan de tu nutricionista, tu menú, tu lista de mercado y tus avisos.',
         f'Para entrar usa tu correo: <strong style="color:{DORADO};">{escape(usuario.email)}</strong>.',
         'Tus datos de inicio (nombre, sexo, fecha de nacimiento, estatura y medidas iniciales) quedan '
         'guardados tal cual y no se editan, así tu avance es real.'],
        boton=('Entrar a la app', entrada),
        nota='Si olvidas tu clave, en el inicio de sesión toca "¿Olvidaste tu clave?" y te la enviamos.')
    texto = (f'Bienvenido, {usuario.nombre}.\n\nTu cuenta de Camino del Guerrero ya está lista.\n'
             f'Tu usuario es: {usuario.email}\n\nEntra aquí: {entrada}\n\n'
             'Tus datos de inicio quedan guardados tal cual y no se editan.\n'
             'Si olvidas tu clave, en el inicio de sesión toca "¿Olvidaste tu clave?".')
    _enviar(usuario.email, 'Bienvenido a Camino del Guerrero', texto, html)
