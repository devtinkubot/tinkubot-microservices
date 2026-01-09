#!/usr/bin/env python3
"""
Script de validación de la estructura de tests.

Verifica que todos los archivos y tests necesarios existan.
Ejecutar antes de comenzar la refactorización Sprint-1.12.
"""

import sys
from pathlib import Path

# Colores para terminal
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def check_file_exists(filepath: str, required: bool = True) -> bool:
    """Verifica si un archivo existe."""
    path = Path(filepath)
    exists = path.exists()

    if exists:
        print(f"{GREEN}✓{NC} {filepath}")
    elif required:
        print(f"{RED}✗{NC} {filepath} (REQUERIDO)")
    else:
        print(f"{YELLOW}⚠{NC} {filepath} (opcional)")

    return exists


def validate_test_structure() -> bool:
    """Valida que la estructura de tests esté completa."""
    print(f"\n{YELLOW}=== Validando Estructura de Tests ==={NC}\n")

    all_valid = True

    # Archivos requeridos
    required_files = [
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/requirements-test.txt",
        "tests/README.md",
        "tests/api/__init__.py",
        "tests/api/test_endpoints.py",
        "pytest.ini",
    ]

    print(f"{YELLOW}Archivos Requeridos:{NC}")
    for filepath in required_files:
        if not check_file_exists(filepath, required=True):
            all_valid = False

    print(f"\n{YELLOW}Archivos Opcionales:{NC}")
    optional_files = ["run_tests.sh", "tests/fixtures/"]
    for filepath in optional_files:
        check_file_exists(filepath, required=False)

    return all_valid


def validate_test_content() -> bool:
    """Valida que el archivo de tests tenga contenido."""
    print(f"\n{YELLOW}=== Validando Contenido de Tests ==={NC}\n")

    test_file = Path("tests/api/test_endpoints.py")
    if not test_file.exists():
        print(f"{RED}✗{NC} tests/api/test_endpoints.py no existe")
        return False

    content = test_file.read_text()

    # Verificar que existan las clases de tests
    required_classes = [
        "TestHealthEndpoint",
        "TestIntelligentSearchEndpoint",
        "TestSendWhatsAppEndpoint",
        "TestHandleWhatsAppMessageEndpoint",
        "TestNotifyApprovalEndpoint",
        "TestGetProvidersEndpoint",
    ]

    all_valid = True
    print(f"{YELLOW}Clases de Tests Requeridas:{NC}")
    for class_name in required_classes:
        if class_name in content:
            print(f"{GREEN}✓{NC} {class_name}")
        else:
            print(f"{RED}✗{NC} {class_name} NO encontrada")
            all_valid = False

    # Contar tests
    test_count = content.count("def test_")
    print(f"\n{YELLOW}Total de Tests:{NC} {test_count}")

    if test_count < 30:
        print(f"{YELLOW}⚠{NC} Se esperan al menos 30 tests, hay {test_count}")
        all_valid = False

    return all_valid


def print_summary() -> None:
    """Imprime resumen de uso."""
    print(f"\n{YELLOW}=== Resumen de Uso ==={NC}\n")
    print("Instalar dependencias:")
    print(f"  {GREEN}pip install -r tests/requirements-test.txt{NC}\n")
    print("Ejecutar todos los tests:")
    print(f"  {GREEN}pytest tests/ -v{NC}\n")
    print("Ejecutar solo endpoints:")
    print(f"  {GREEN}pytest tests/api/test_endpoints.py -v{NC}\n")
    print("Ejecutar con coverage:")
    print(f"  {GREEN}pytest tests/ --cov=. --cov-report=html{NC}\n")
    print("Usar el script:")
    print(f"  {GREEN}./run_tests.sh --all{NC}\n")


def main() -> int:
    """Función principal."""
    structure_valid = validate_test_structure()
    content_valid = validate_test_content()
    print_summary()

    if structure_valid and content_valid:
        print(f"{GREEN}=== ✓ VALIDACIÓN COMPLETADA ==={NC}")
        print(f"{GREEN}Tests listos para Sprint-1.12{NC}\n")
        return 0
    else:
        print(f"{RED}=== ✗ VALIDACIÓN FALLÓ ==={NC}")
        print(f"{RED}Falta completar la estructura de tests{NC}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
