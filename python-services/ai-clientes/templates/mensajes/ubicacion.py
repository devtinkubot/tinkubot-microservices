"""Solicitudes de ciudad y ubicación al usuario."""

def preguntar_ciudad() -> str:
    """Pregunta la ciudad al usuario."""
    return "*¿En qué ciudad lo necesitas?*"

def preguntar_ciudad_con_servicio(service: str) -> str:
    """Pregunta la ciudad dado un servicio específico."""
    return f"Entendido, para {service} ¿en qué ciudad lo necesitas? (ejemplo: Quito, Cuenca)"

def error_ciudad_no_reconocida() -> str:
    """Error cuando la ciudad no es reconocida."""
    return "No reconocí la ciudad. Escríbela de nuevo usando una ciudad de Ecuador (ej: Quito, Guayaquil, Cuenca)."

def solicitar_ciudad_formato() -> str:
    """Solicita la ciudad con formato de ejemplo."""
    return "Indica la ciudad por favor (por ejemplo: Quito, Cuenca)."

def preguntar_ciudad_cambio() -> str:
    """Pregunta ciudad cuando el usuario quiere cambiar."""
    return "¿En qué ciudad necesitas {service}?"
