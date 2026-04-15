from services.shared.estados_proveedor import (
    CHECKPOINTS_ONBOARDING,
    ESTADO_CANONICO_APROBADO,
    ESTADO_CANONICO_PENDIENTE,
    ESTADO_CANONICO_RECHAZADO,
    MENU_POST_REGISTRO_STATES,
    ONBOARDING_REANUDACION_STATES,
    STANDARD_ONBOARDING_STATES,
    normalizar_estado_administrativo,
)


def test_normalizar_estado_administrativo_solo_acepta_estado_canonico():
    assert (
        normalizar_estado_administrativo(status="approved") == ESTADO_CANONICO_APROBADO
    )
    assert (
        normalizar_estado_administrativo(status="rejected") == ESTADO_CANONICO_RECHAZADO
    )
    assert (
        normalizar_estado_administrativo(status="pending") == ESTADO_CANONICO_PENDIENTE
    )


def test_taxonomia_de_onboarding_mantiene_fronteras_claras():
    assert "onboarding_real_phone" in STANDARD_ONBOARDING_STATES
    assert "review_pending_verification" in CHECKPOINTS_ONBOARDING
    assert "awaiting_menu_option" in ONBOARDING_REANUDACION_STATES
    assert "maintenance_personal_info_action" in MENU_POST_REGISTRO_STATES
    assert "maintenance_dni_front_photo_update" in MENU_POST_REGISTRO_STATES
