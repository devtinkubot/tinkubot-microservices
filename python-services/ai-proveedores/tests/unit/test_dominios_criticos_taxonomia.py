import asyncio

import services.servicios_proveedor.utilidades.dominios_criticos as modulo


def test_refrescar_taxonomia_dominios_criticos_carga_aliases_y_ejemplos(monkeypatch):
    class _LectorStub:
        async def obtener_taxonomia_publicada(self, force_refresh=False):
            assert force_refresh is False
            return {
                "publication": {"version": 1},
                "version": 1,
                "domains": [
                    {
                        "code": "inmobiliario",
                        "aliases": [
                            {
                                "alias_normalized": "servicio inmobiliario",
                                "alias_text": "servicio inmobiliario",
                            }
                        ],
                        "canonical_services": [
                            {
                                "canonical_name": "compra de casa",
                                "canonical_normalized": "compra de casa",
                            }
                        ],
                        "rules": [
                            {
                                "required_dimensions": [
                                    "operacion",
                                    "tipo de inmueble",
                                ],
                                "generic_examples": [
                                    "asesoria inmobiliaria",
                                ],
                                "provider_prompt_template": "Describe la operación y el tipo de inmueble con el que trabajas.",
                                "sufficient_examples": [
                                    "compra de casa",
                                    "renta de departamento",
                                ],
                            }
                        ],
                    }
                ],
            }

    monkeypatch.setattr(modulo, "_LECTOR_TAXONOMIA", _LectorStub())
    modulo._MAPA_SERVICIOS_GENERICOS_DINAMICO.clear()

    asyncio.run(modulo.refrescar_taxonomia_dominios_criticos())

    assert (
        modulo.detectar_dominio_critico_generico("servicio inmobiliario")
        == "inmobiliario"
    )
    assert (
        modulo.detectar_dominio_critico_generico("asesoría inmobiliaria")
        == "inmobiliario"
    )
    assert "Describe la operación y el tipo de inmueble" in modulo.mensaje_pedir_precision_servicio(
        "servicio inmobiliario"
    )
    assert "compra de casa" in modulo.mensaje_pedir_precision_servicio(
        "servicio inmobiliario"
    )
    assert "operacion" in modulo.mensaje_pedir_precision_servicio(
        "servicio inmobiliario"
    )
    clasificacion = modulo.clasificar_servicio_critico("servicio inmobiliario")
    assert clasificacion["domain"] == "inmobiliario"
    assert clasificacion["specificity"] == "insufficient"
    assert clasificacion["source"] == "taxonomy"
    assert clasificacion["missing_dimensions"] == [
        "operacion",
        "tipo de inmueble",
    ]
    assert modulo.detectar_dominio_critico_generico("compra de casa") is None


def test_clasificar_servicio_critico_sin_taxonomia_no_recurre_a_hardcode():
    modulo._MAPA_SERVICIOS_GENERICOS_DINAMICO.clear()

    clasificacion = modulo.clasificar_servicio_critico("asesoria legal")

    assert clasificacion["domain"] is None
    assert clasificacion["specificity"] == "unknown"
    assert clasificacion["source"] == "none"
