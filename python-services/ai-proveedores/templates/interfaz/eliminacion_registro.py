"""Mensajes para la funcionalidad de eliminación de registro de proveedor."""


def solicitar_confirmacion_eliminacion() -> str:
    """Solicita confirmación al usuario para eliminar su registro.

    Returns:
        Mensaje con advertencia de acción irreversible y opciones
    """
    return (
        "*⚠️ ¿Estás seguro de eliminar tu registro?*\n\n"
        "Esta acción eliminará:\n"
        "- Tu perfil de la base de datos\n"
        "- Tus servicios registrados\n"
        "- Tus fotos y documentos\n"
        "- Todas tus configuraciones\n\n"
        "*Esta acción NO se puede deshacer*\n\n"
        "Responde:\n"
        "1) Confirmar eliminación\n"
        "2) Cancelar y volver al menú"
    )


def confirmar_eliminacion_exitosa() -> str:
    """Confirma que el registro fue eliminado correctamente.

    Returns:
        Mensaje de confirmación y despedida
    """
    return (
        "*✅ Registro eliminado correctamente*\n\n"
        "Tu información ha sido eliminada permanentemente de nuestra base de datos.\n\n"
        "Gracias por haber sido parte de Tinkubot. ¡Te deseamos lo mejor!"
    )


def error_eliminacion_fallida(mensaje_error: str = "") -> str:
    """Informa que la eliminación falló.

    Args:
        mensaje_error: Mensaje técnico del error (opcional)

    Returns:
        Mensaje de error con detalles técnicos si se proporcionan
    """
    if mensaje_error:
        return (
            "*❌ Error al eliminar el registro*\n\n"
            "No se pudo completar la eliminación. Por favor, intenta nuevamente.\n\n"
            f"Detalle: {mensaje_error}"
        )
    return (
        "*❌ No se pudo eliminar el registro*\n\n"
        "Hubo un error al procesar. Inténtalo nuevamente o contacta soporte si el problema persiste."
    )


def informar_eliminacion_cancelada() -> str:
    """Confirma que la eliminación fue cancelada.

    Returns:
        Confirmación de cancelación y que el registro se mantiene activo
    """
    return (
        "*✅ Eliminación cancelada*\n\n"
        "Tu registro se mantiene activo en Tinkubot.\n\n"
        "Puedes continuar accediendo a todos nuestros servicios."
    )


def advertencia_eliminacion_irreversible() -> str:
    """Advierte que la acción de eliminación no se puede deshacer.

    Returns:
        Advertencia fuerte sobre la irreversibilidad de la acción
    """
    return (
        "*⚠️ ADVERTENCIA IMPORTANTE*\n\n"
        "La eliminación de tu registro es *PERMANENTE e IRREVERSIBLE*.\n\n"
        "Una vez eliminado:\n"
        "- No podrás recuperar tu información\n"
        "- Perderás todo tu historial\n"
        "- Deberás registrarte nuevamente si quieres usar nuestros servicios\n\n"
        "Si tienes dudas, puedes cancelar ahora y contactarnos."
    )
