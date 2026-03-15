from services.orquestador_retrollamadas import OrquestadorRetrollamadas


def test_build_expone_preparar_proveedor_para_detalle():
    retrollamadas = OrquestadorRetrollamadas(
        supabase=None,
        repositorio_flujo=None,
        repositorio_clientes=None,
        buscador=None,
        moderador_contenido=None,
        programador_retroalimentacion=None,
        gestor_leads=None,
        logger=None,
        supabase_bucket="tinkubot-providers",
        supabase_base_url="https://supabase.example",
    )

    callbacks = retrollamadas.build()

    assert "preparar_proveedor_para_detalle" in callbacks
    assert callable(callbacks["preparar_proveedor_para_detalle"])
