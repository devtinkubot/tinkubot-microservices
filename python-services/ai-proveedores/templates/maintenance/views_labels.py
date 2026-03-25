"""Etiquetas visibles para las vistas de detalle de maintenance."""

from templates.shared.estados import estado_no_registrada, estado_no_registrado


def titulo_nombre_actual() -> str:
    return "*Nombre actual*"


def etiqueta_nombres_documento() -> str:
    return "Nombres: "


def etiqueta_apellidos_documento() -> str:
    return "Apellidos: "


def etiqueta_cedula_documento() -> str:
    return "Cédula: "


def titulo_foto_perfil() -> str:
    return "Foto de perfil"


def titulo_cedula_frontal() -> str:
    return "Cédula frontal"


def titulo_cedula_reverso() -> str:
    return "Cédula reverso"


def titulo_facebook() -> str:
    return "Facebook"


def titulo_instagram() -> str:
    return "Instagram"


def valor_no_registrado() -> str:
    return estado_no_registrado()


def valor_no_registrada() -> str:
    return estado_no_registrada()
