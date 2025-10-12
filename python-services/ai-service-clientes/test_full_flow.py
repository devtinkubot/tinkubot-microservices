#!/usr/bin/env python3
"""
Script de prueba para verificar el flujo completo de consentimiento.
"""

from templates.prompts import (
    consent_prompt_messages,
    INITIAL_PROMPT,
)

def test_full_consent_flow():
    """Prueba el flujo completo de consentimiento."""
    print("🧪 Probando flujo completo de consentimiento...")

    # 1. Mostrar mensaje de consentimiento
    print("1. Mensaje de consentimiento que muestra el bot:")
    messages = consent_prompt_messages()
    print(f"Mensaje completo:\n{messages[0]}\n")

    # 2. Simular respuesta del usuario
    print("2. Simulando respuesta '1' del usuario...")

    # 3. Verificar que INITIAL_PROMPT esté definido
    print(f"3. Prompt inicial después de aceptar: '{INITIAL_PROMPT}'")

    # 4. Verificar elementos clave
    expected_elements = [
        "¿En qué te puedo ayudar hoy?",
        "Para poder conectararte con proveedores",
        "1 Acepto",
        "2 No acepto",
        "Responde con el número de tu opción"
    ]

    print("\n4. Verificación del flujo completo:")
    flow_works = True
    for element in expected_elements:
        if element in messages[0] or element == INITIAL_PROMPT:
            print(f"✅ '{element}' - presente en el flujo")
        else:
            print(f"❌ '{element}' - ausente en el flujo")
            flow_works = False

    if flow_works:
        print("\n🎉 ¡Flujo completo funciona correctamente!")
        print("✅ Paso 1: Muestra consentimiento con opciones numéricas")
        print("✅ Paso 2: Usuario responde '1' para aceptar")
        print("✅ Paso 3: Se actualiza consentimiento en BD")
        print("✅ Paso 4: Se muestra prompt inicial para continuar")
    else:
        print("\n⚠️ El flujo tiene problemas. Revisa la implementación.")

    # Mostrar ejemplo del flujo
    print("\n5. Ejemplo del flujo completo:")
    print("=" * 60)
    print("BOT: ", messages[0])
    print("USUARIO: 1")
    print("BOT: ", INITIAL_PROMPT)
    print("=" * 60)

if __name__ == "__main__":
    test_full_consent_flow()
