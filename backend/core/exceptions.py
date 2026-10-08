from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class ReglaNegocioError(Exception):
    """La operación pedida no respeta una regla del dominio."""


class DatoInmutableError(Exception):
    """Se intentó modificar un dato que, por regla de negocio, no se puede cambiar."""


def manejar_excepciones(exc, context):
    """Responde `{detail}` con el mensaje de las reglas de negocio en vez de un 500."""
    if isinstance(exc, ReglaNegocioError):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, DatoInmutableError):
        return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
    return exception_handler(exc, context)
