from services.taxonomia.clustering import construir_cluster_key


def test_construir_cluster_key_prioriza_canonico():
    cluster_key = construir_cluster_key(
        proposed_domain_code="Inmobiliario",
        proposal_type="new_canonical",
        proposed_canonical_name="Asesoría para compra de vivienda",
        normalized_text="asesoria compra casa",
        source_text="asesoría compra casa",
    )

    assert cluster_key == "inmobiliario|new canonical|asesoria para compra de vivienda"


def test_construir_cluster_key_agrupa_variantes_por_tokens():
    first = construir_cluster_key(
        proposed_domain_code="legal",
        proposal_type="alias",
        normalized_text="asesoria compra casa",
        source_text="asesoria compra casa",
    )
    second = construir_cluster_key(
        proposed_domain_code="legal",
        proposal_type="alias",
        normalized_text="compra casa asesoria",
        source_text="compra casa asesoria",
    )

    assert first == second
