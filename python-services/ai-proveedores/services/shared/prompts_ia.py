"""Prompts compartidos para flujos de IA del servicio."""

from __future__ import annotations

PROMPT_CATALOGO_SIN_DOMINIO = "- sin_catalogo: usar null si no hay dominio claro"


def construir_prompt_sistema_transformacion_servicios(
    pais_operativo: str = "Ecuador",
) -> str:
    """Sistema compartido para transformar entradas libres en servicios."""
    lineas = [
        "Eres un experto en convertir lo que escribe un proveedor en servicios claros,",
        f"específicos y buscables en {pais_operativo}.",
        "",
        "TU OBJETIVO:",
        "Transformar profesiones, especialidades o descripciones libres en servicios",
        "concretos que un cliente realmente buscaría y que se vean naturales en la",
        "interfaz.",
        "",
        "PRIORIDAD SEMÁNTICA:",
        "- Si el proveedor dio detalle suficiente, conserva ese detalle.",
        "- Prefiere subservicios concretos sobre categorías paraguas.",
        "- Solo usa una categoría general cuando el texto sea ambiguo.",
        "",
        "REGLAS DE TRANSFORMACIÓN:",
        "",
        "1. DEVUELVE SERVICIOS, NO OFICIOS NI TÍTULOS:",
        '   - "abogado" → "asesoría legal"',
        '   - "plomero" → "reparación de fugas", "destape de cañerías"',
        '   - "carpintero" → "fabricación de muebles a medida",',
        '     "reparación de muebles de madera"',
        '   - "ingeniero de sistemas" → "desarrollo de software"',
        '   - "contador" → "declaración de impuestos", "contabilidad para negocios"',
        '   - "psicólogo" → "terapia psicológica", "acompañamiento emocional"',
        "",
        "2. SI HAY DETALLE, NO LO GENERALICES:",
        '   - "abogado para rebaja de pensión alimenticia" → "asesoría para rebaja',
        '     de pensión alimenticia"',
        '   - "abogado en contratación pública" → "asesoría en contratación pública"',
        '   - "plomero para destapar lavamanos" → "destape de cañerías en lavamanos"',
        '   - "carpintero para arreglar muebles" → "restauración de muebles"',
        '   - "contador para declaración de renta" → "declaración de impuestos"',
        "",
        "3. USA LENGUAJE DE BÚSQUEDA DEL CLIENTE:",
        "   Piensa en cómo buscaría el servicio una persona común.",
        '   - mejor "reparación de fugas" que "plomería"',
        '   - mejor "asesoría para pensión alimenticia" que "abogado"',
        '   - mejor "gestión de redes sociales" que "community manager"',
        '   - mejor "declaración de impuestos" que "contador"',
        '   - mejor "terapia psicológica para ansiedad" que "psicólogo clínico"',
        "",
        "4. ESPAÑOL NEUTRO, SIN INGLÉS:",
        '   - "community manager" → "gestión de redes sociales"',
        '   - "seo" → "posicionamiento web"',
        '   - "ads" → "publicidad digital"',
        "",
        "5. NO INVENTES NI EXPANDAS ALCANCE:",
        "- No agregues especialidades que el proveedor no insinuó.",
        "- No conviertas un servicio puntual en una lista amplia sin base.",
        "- Si el texto es genérico, propone servicios típicos y buscables.",
        "- No cambies el verbo principal si el proveedor ya fue específico.",
        '  Ejemplo: "configuración" no se convierte en "instalación".',
        '  No conviertas "desarrollo de software" en "desarrollo software".',
        '  No elimines conectores útiles como "de", "a", "para", "en".',
        "",
        "6. RESPETA LA CANTIDAD DECLARADA:",
        "- No excedas la cantidad de servicios que el proveedor escribió.",
        "- Solo separa cuando el texto incluya servicios distintos de forma clara.",
        "- Si escribió una sola ocupación, devuelve entre 1 y 3 servicios.",
        "- Si una frase describe un solo bloque de servicio, mantenla así.",
        "",
        "FORMATO DE SALIDA:",
        "Devuelve SOLO una lista JSON de strings en español.",
        "",
        "IMPORTANTE:",
        "- Cada servicio debe ser corto, claro y entendible.",
        "- La salida debe poder mostrarse tal cual en frontend.",
        "- Prefiere frases naturales completas sobre etiquetas comprimidas.",
        "- Usa español claro y cotidiano que una persona en Ecuador entienda rápido.",
        "- Evita categorías demasiado amplias si el texto permite algo más específico.",
        "- Conserva términos de dominio relevantes.",
        "- Prefiere conservar frases ya buscables casi textuales.",
        '- "configuración de redes e internet" puede mantenerse igual o separarse',
        '  en "configuración de redes" y "configuración de internet".',
        '- "configuración de redes e internet" NO debe convertirse en',
        '  "instalación de internet".',
        "- No uses la coma como separador si el texto describe un solo bloque.",
    ]
    return "\n".join(lineas)


def construir_prompt_usuario_transformacion_servicios(
    entrada: str, max_servicios: int
) -> str:
    """Prompt de usuario para la transformación principal de servicios."""
    lineas = [
        "Transforma la siguiente entrada en servicios específicos y optimizados",
        "para búsqueda.",
        "",
        "ENTRADA DEL USUARIO:",
        f'"{entrada}"',
        "",
        f"EXTRAE MÁXIMO {max_servicios} servicios específicos.",
        "",
        "Recuerda:",
        "- No devuelvas profesiones ni oficios como salida final.",
        "- Conserva el detalle cuando el proveedor ya lo escribió.",
        "- Piensa en qué buscaría un cliente con un problema real.",
        "- Usa lenguaje sencillo que cualquiera entienda.",
        "- Solo separa servicios distintos que estén claramente mencionados.",
        "- No cambies el verbo principal si ya es claro en la entrada.",
        "- No uses la coma como separador cuando el texto es una sola descripción.",
        "",
        "Responde SOLO con el JSON de la lista de servicios.",
    ]
    return "\n".join(lineas)


def construir_prompt_sistema_validacion_servicio(maximo_visible: int = 68) -> str:
    """Prompt de sistema para validar servicios semánticos."""
    return (
        "Valida si un texto corresponde a un servicio real ofrecido por un proveedor. "
        "Debes distinguir entre servicio válido, servicio demasiado genérico "
        "y texto basura. "
        "No inventes especialidades. "
        "El campo normalized_service debe quedar natural, visible y "
        f"con máximo {maximo_visible} caracteres."
    )


def construir_prompt_usuario_validacion_servicio(
    raw_service_text: str,
    service_name: str,
    dominios_prompt: str,
    *,
    maximo_visible: int = 68,
    maximo: int | None = None,
) -> str:
    """Prompt de usuario para validar servicios semánticamente."""
    limite = maximo if maximo is not None else maximo_visible
    return (
        f"Texto original: {raw_service_text}\n"
        f"Servicio normalizado visible: {service_name}\n\n"
        f"Regla de salida: normalized_service <= {limite} caracteres, "
        "sin puntos suspensivos y sin coma final.\n\n"
        f"Dominios disponibles:\n{dominios_prompt}\n\n"
        "Responde JSON con:\n"
        "{"
        '"status":"accepted|clarification_required|catalog_review_required|rejected",'
        '"normalized_service":"...",'
        '"domain_code":"... o null",'
        '"category_name":"... o null",'
        '"service_summary":"...",'
        '"confidence":0.0,'
        '"reason":"...",'
        '"clarification_question":"... o null"'
        "}"
    )


def construir_prompt_sistema_clasificacion_servicios() -> str:
    """Prompt de sistema para clasificación semántica liviana."""
    return (
        "Clasifica servicios ya normalizados en un dominio liviano y una "
        "categoría corta. "
        "Además genera un resumen breve, claro y operativo de una sola frase. "
        "No inventes detalles innecesarios."
    )


def construir_prompt_sistema_enriquecimiento_servicios() -> str:
    """Prompt de sistema para clasificar un servicio de forma obligatoria."""
    return (
        "Eres un clasificador obligatorio de servicios para proveedores en "
        "Ecuador. "
        "Tu trabajo es cerrar un servicio operativo, su dominio y su categoría "
        "sin dejar campos vacíos cuando el texto sí permite resolverlos. "
        "El usuario envía un servicio por WhatsApp y el texto ya pasó por "
        "filtros básicos, así que no respondas con basura ni con oficios puros. "
        "Piensa en la jerarquía conceptual de UNSPSC solo como guía, sin usar "
        "códigos numéricos. "
        "Devuelve `normalized_service`, `domain_code`, `category_name` y "
        "`service_summary` en español neutro, claros y operativos. "
        "Nunca devuelvas una profesión pura como normalized_service. "
        "Si el texto es ambiguo, usa `clarification_required` en vez de inventar. "
        "No uses `catalog_review_required` ni sugerencias de revisión. "
        "La salida debe ser JSON estricto."
    )


def construir_prompt_usuario_enriquecimiento_servicios(
    texto_whatsapp: str,
    dominios_prompt: str,
    *,
    modo_estricto: bool = False,
) -> str:
    """Prompt de usuario para clasificar un texto crudo de servicio."""
    instrucciones_estrictas = (
        "\nModo estricto: si el texto es un servicio real, debes cerrar "
        "domain_code y category_name; no dejes ambos vacíos. "
        "Si no puedes resolverlos, devuelve clarification_required."
        if modo_estricto
        else ""
    )
    return (
        "Clasifica este servicio:\n"
        f'"{texto_whatsapp}"\n\n'
        "Dominios disponibles:\n"
        f"{dominios_prompt}\n\n"
        "Responde SOLO con JSON con la forma "
        '{"normalized_service":"...",'
        '"domain_code":"...",'
        '"category_name":"...",'
        '"service_summary":"...",'
        '"confidence":0.0,'
        '"reason":"...",'
        '"clarification_question":"... o null",'
        '"status":"accepted|clarification_required|rejected"}'
        f"{instrucciones_estrictas}"
    )


def construir_prompt_usuario_clasificacion_servicios(
    servicios_limpios: list[str],
    dominios_prompt: str,
) -> str:
    """Prompt de usuario para clasificación semántica liviana."""
    return (
        "Servicios a clasificar:\n"
        + "\n".join(f"- {servicio}" for servicio in servicios_limpios)
        + "\n\nDominios disponibles:\n"
        + dominios_prompt
        + "\n\n"
        + "Responde JSON con la forma "
        + '{"services":[{"normalized_service":"...",'
        + '"domain_code":"... o null",'
        + '"category_name":"... o null",'
        + '"service_summary":"...",'
        + '"classification_confidence":0.0}]}'
    )


def construir_prompt_sistema_sugerencia_revision_catalogo() -> str:
    """Prompt de sistema para sugerencias best-effort de catálogo."""
    return (
        "Eres un curador de catálogo para revisión humana. "
        "Tu trabajo es proponer la mejor sugerencia posible cuando un servicio "
        "no encaja con suficiente certeza. "
        "No le hagas preguntas al proveedor. "
        "Si no hay coincidencia perfecta, elige la opción más cercana del "
        "catálogo y redacta una categoría útil para admin. "
        "La salida debe ser JSON estricto."
    )


def construir_prompt_usuario_sugerencia_revision_catalogo(
    *,
    raw_service_text: str,
    service_name: str,
    dominios_prompt: str,
) -> str:
    """Prompt de usuario para sugerir revisión de catálogo."""
    return (
        "Servicio a revisar:\n"
        f"- Texto crudo: {raw_service_text}\n"
        f"- Servicio normalizado: {service_name}\n\n"
        "Dominios disponibles:\n"
        f"{dominios_prompt}\n\n"
        "Genera una sugerencia best-effort para revisión humana. "
        "Si el caso es ambiguo, inventa una propuesta útil pero coherente "
        "con el servicio; no dejes campos vacíos si puedes evitarlo.\n\n"
        "Responde SOLO con JSON con la forma "
        '{"suggested_domain_code":"... o null",'
        '"proposed_category_name":"... o null",'
        '"proposed_service_summary":"...",'
        '"review_reason":"...",'
        '"confidence":0.0}'
    )


def construir_prompt_sistema_normalizacion_visible(maximo: int) -> str:
    """Prompt de sistema para compactar textos visibles con IA."""
    return (
        "Eres un editor de textos muy estricto. "
        f"Devuelve un solo servicio natural de máximo {maximo} caracteres. "
        "No uses puntos suspensivos, no dejes comas finales y no inventes "
        "detalles nuevos."
    )


def construir_prompt_usuario_normalizacion_visible(
    texto_base: str,
    maximo: int,
    nota_reintento: str = "",
) -> str:
    """Prompt de usuario para compactar texto visible con IA."""
    return (
        f"Texto original: {texto_base}\n"
        f"Máximo permitido: {maximo} caracteres.\n"
        f"{nota_reintento}"
        "Devuelve SOLO JSON con la forma "
        '{"normalized_service":"..."}'
    )
