"""
Catálogo de profesiones y sinónimos para AI Clientes Service.
"""

from __future__ import annotations

from typing import Dict, Set

# Sinónimos comunes de servicios/profesiones
COMMON_SERVICE_SYNONYMS: Dict[str, Set[str]] = {
    "plomero": {"plomero", "plomeria", "plomería"},
    "electricista": {"electricista", "electricistas"},
    "médico": {"médico", "medico", "doctor", "doctora"},
    "mecánico": {
        "mecanico",
        "mecánico",
        "mecanicos",
        "mecanica automotriz",
        "taller mecanico",
    },
    "pintor": {"pintor", "pintura", "pintores"},
    "albañil": {"albañil", "albanil", "maestro de obra"},
    "gasfitero": {"gasfitero", "gasfiteria", "fontanero"},
    "cerrajero": {"cerrajero", "cerrajeria"},
    "veterinario": {"veterinario", "veterinaria"},
    "chef": {"chef", "cocinero", "cocinera"},
    "mesero": {"mesero", "mesera", "camarero", "camarera"},
    "profesor": {"profesor", "profesora", "maestro", "maestra"},
    "bartender": {"bartender", "barman"},
    "carpintero": {"carpintero", "carpinteria"},
    "jardinero": {"jardinero", "jardineria"},
    "marketing": {
        "marketing",
        "marketing digital",
        "mercadotecnia",
        "publicidad",
        "publicista",
        "agente de publicidad",
        "campanas de marketing",
        "campanas publicitarias",
        "community manager",
        "community manager",
        "gestor de redes sociales",
        "gestor de contenido",
        "social media",
        "social media manager",
        "redes sociales",
        "administrador de redes sociales",
        "community manager",
        "gestion de redes sociales",
        "community management",
        "digital marketing",
        "social media marketing",
    },
    "diseñador gráfico": {
        "diseño grafico",
        "diseno grafico",
        "diseñador grafico",
        "designer grafico",
        "graphic designer",
        "diseñador",
    },
    "consultor": {
        "consultor",
        "consultoria",
        "consultoría",
        "asesor",
        "asesoria",
        "asesoría",
        "consultor de negocios",
    },
    "desarrollador": {
        "desarrollador",
        "programador",
        "developer",
        "desarrollo web",
        "software developer",
        "ingeniero de software",
    },
    "contador": {
        "contador",
        "contadora",
        "contable",
        "contabilidad",
        "finanzas",
    },
    "abogado": {
        "abogado",
        "abogada",
        "legal",
        "asesoria legal",
        "asesoría legal",
        "servicios legales",
    },
}

COMMON_SERVICES = list(COMMON_SERVICE_SYNONYMS.keys())

