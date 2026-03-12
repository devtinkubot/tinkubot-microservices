from services.taxonomia.clustering import construir_cluster_key


def test_construir_cluster_key_no_agrupa_dominios_distintos():
    legal = construir_cluster_key(
        proposed_domain_code="legal",
        proposal_type="alias",
        normalized_text="asesoria compra casa",
        source_text="asesoria compra casa",
    )
    inmob = construir_cluster_key(
        proposed_domain_code="inmobiliario",
        proposal_type="alias",
        normalized_text="asesoria compra casa",
        source_text="asesoria compra casa",
    )

    assert legal != inmob


def test_construir_cluster_key_no_agrupa_proposal_type_distinto():
    alias = construir_cluster_key(
        proposed_domain_code="vehiculos",
        proposal_type="alias",
        normalized_text="revision mecanica compra auto",
        source_text="revision mecanica compra auto",
    )
    canonical = construir_cluster_key(
        proposed_domain_code="vehiculos",
        proposal_type="new_canonical",
        normalized_text="revision mecanica compra auto",
        source_text="revision mecanica compra auto",
    )

    assert alias != canonical
