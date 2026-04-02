from services.review.menu import poner_flujo_en_menu_revision


def test_poner_flujo_en_menu_revision_estandariza_estado_y_flags():
    flujo = {"verification_notified": False}

    resultado = poner_flujo_en_menu_revision(flujo, verification_notified=True)

    assert resultado is flujo
    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["has_consent"] is True
    assert flujo["esta_registrado"] is True
    assert flujo["pending_review_attempts"] == 0
    assert flujo["review_silenced"] is False
    assert flujo["verification_notified"] is True


def test_poner_flujo_en_menu_revision_tambien_habilita_acceso_para_aprobado_canonico():
    flujo = {}

    poner_flujo_en_menu_revision(flujo)

    assert flujo["state"] == "awaiting_menu_option"
