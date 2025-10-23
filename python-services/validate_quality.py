#!/usr/bin/env python3
"""
Script de Validación de Calidad Local - TinkuBot Python Services

Ejecuta todas las validaciones de calidad antes de subir a GitHub.
Uso: python validate_quality.py [--fix] [--service nombre_servicio]

Opciones:
--fix : Aplica correcciones automáticas (formato con black)
--service : Valida solo un servicio específico (ai-clientes, ai-proveedores, search-token)
"""

import subprocess
import sys
import os
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

# Colores para salida
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_banner():
    """Muestra el banner del validador"""
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║          🔍 VALIDADOR DE CALIDAD - TINKUBOT PYTHON          ║
║                 Antes de subir a GitHub                    ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
{Colors.WHITE}
Este script ejecuta las siguientes validaciones:
• Formato de código (Black)
• Linting (Flake8)
• Type Checking (MyPy)
• Seguridad (Bandit)
• Importaciones ordenadas (isort)
• Complejidad (McCabe)
{Colors.END}
""")

def print_success(message: str):
    """Imprime mensaje de éxito"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    """Imprime mensaje de error"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message: str):
    """Imprime mensaje de advertencia"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_info(message: str):
    """Imprime mensaje informativo"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def run_command(cmd: List[str], description: str, cwd: str = None) -> Tuple[bool, str]:
    """
    Ejecuta un comando y retorna (éxito, salida)

    Args:
        cmd: Comando a ejecutar
        description: Descripción para mostrar
        cwd: Directorio de trabajo

    Returns:
        Tuple[bool, str]: (éxito, salida)
    """
    print(f"\n{Colors.CYAN}🔍 Ejecutando: {description}{Colors.END}")
    print(f"{Colors.MAGENTA}Comando: {' '.join(cmd)}{Colors.END}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60  # 60 segundos timeout
        )

        if result.returncode == 0:
            print_success(f"{description} - OK")
            if result.stdout.strip():
                print(f"{Colors.WHITE}{result.stdout}{Colors.END}")
            return True, result.stdout
        else:
            print_error(f"{description} - ERROR")
            if result.stderr.strip():
                print(f"{Colors.RED}{result.stderr}{Colors.END}")
            if result.stdout.strip():
                print(f"{Colors.YELLOW}{result.stdout}{Colors.END}")
            return False, result.stderr

    except subprocess.TimeoutExpired:
        print_error(f"{description} - TIMEOUT (60s)")
        return False, "Timeout after 60 seconds"
    except Exception as e:
        print_error(f"{description} - EXCEPTION: {str(e)}")
        return False, str(e)

def check_tool_availability(tool_name: str) -> bool:
    """Verifica si una herramienta está disponible"""
    try:
        result = subprocess.run([tool_name, "--version"],
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except:
        return False

def validate_formatting(services: List[str], fix: bool = False) -> bool:
    """Valida y opcionalmente corrige el formato con Black"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}📝 VALIDACIÓN DE FORMATO (BLACK){Colors.END}")

    if not check_tool_availability("black"):
        print_warning("Black no está instalado. Instalando...")
        success, _ = run_command([sys.executable, "-m", "pip", "install", "black"],
                              "Instalando Black")
        if not success:
            print_error("No se pudo instalar Black")
            return False

    all_success = True
    black_cmd = [sys.executable, "-m", "black"]

    if fix:
        black_cmd.append("--line-length=88")
        print_info("Modo de corrección automática activado")
    else:
        black_cmd.extend(["--check", "--line-length=88"])
        print_info("Modo de verificación (sin cambios)")

    for service in services:
        service_path = Path(service)
        if not service_path.exists():
            print_warning(f"Servicio {service} no encontrado, omitiendo...")
            continue

        print(f"\n{Colors.CYAN}Validando formato en: {service}{Colors.END}")
        success, _ = run_command(black_cmd + [str(service_path)], f"Black - {service}")
        all_success = all_success and success

    return all_success

def validate_imports(services: List[str], fix: bool = False) -> bool:
    """Valida y ordena importaciones con isort"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}📦 VALIDACIÓN DE IMPORTACIONES (ISORT){Colors.END}")

    if not check_tool_availability("isort"):
        print_warning("isort no está instalado. Instalando...")
        success, _ = run_command([sys.executable, "-m", "pip", "install", "isort"],
                              "Instalando isort")
        if not success:
            print_error("No se pudo instalar isort")
            return False

    all_success = True
    isort_cmd = [sys.executable, "-m", "isort", "--profile", "black", "--line-length", "88"]

    if fix:
        print_info("Modo de corrección automática activado")
    else:
        isort_cmd.append("--check-only")
        print_info("Modo de verificación (sin cambios)")

    for service in services:
        service_path = Path(service)
        if not service_path.exists():
            continue

        print(f"\n{Colors.CYAN}Validando importaciones en: {service}{Colors.END}")
        success, _ = run_command(isort_cmd + [str(service_path)], f"isort - {service}")
        all_success = all_success and success

    return all_success

def validate_linting(services: List[str]) -> bool:
    """Valida el código con Flake8"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔍 VALIDACIÓN LINTING (FLAKE8){Colors.END}")

    if not check_tool_availability("flake8"):
        print_warning("Flake8 no está instalado. Instalando...")
        success, _ = run_command([sys.executable, "-m", "pip", "install", "flake8"],
                              "Instalando Flake8")
        if not success:
            print_error("No se pudo instalar Flake8")
            return False

    # Crear configuración de Flake8
    flake8_config = """
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude =
    __pycache__,
    .git,
    __pycache__,
    .venv,
    venv,
    .eggs,
    *.egg,
    build,
    dist
max-complexity = 10
"""

    config_path = Path(".flake8")
    with open(config_path, "w") as f:
        f.write(flake8_config)

    all_success = True

    for service in services:
        service_path = Path(service)
        if not service_path.exists():
            continue

        print(f"\n{Colors.CYAN}Validando linting en: {service}{Colors.END}")
        success, _ = run_command([sys.executable, "-m", "flake8", str(service_path)],
                              f"Flake8 - {service}")
        all_success = all_success and success

    # Limpiar archivo de configuración
    config_path.unlink(missing_ok=True)

    return all_success

def validate_types(services: List[str]) -> bool:
    """Valida tipos con MyPy"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔧 VALIDACIÓN DE TIPOS (MYPY){Colors.END}")

    if not check_tool_availability("mypy"):
        print_warning("MyPy no está instalado. Instalando...")
        success, _ = run_command([sys.executable, "-m", "pip", "install", "mypy"],
                              "Instalando MyPy")
        if not success:
            print_error("No se pudo instalar MyPy")
            return False

    all_success = True

    for service in services:
        service_path = Path(service)
        if not service_path.exists():
            continue

        main_py = service_path / "main.py"
        if not main_py.exists():
            continue

        print(f"\n{Colors.CYAN}Validando tipos en: {service}{Colors.END}")

        # MyPy configuration
        mypy_cmd = [
            sys.executable, "-m", "mypy",
            "--ignore-missing-imports",
            "--no-strict-optional",
            "--warn-redundant-casts",
            "--warn-unused-ignores",
            str(main_py)
        ]

        success, _ = run_command(mypy_cmd, f"MyPy - {service}")
        all_success = all_success and success

    return all_success

def validate_security(services: List[str]) -> bool:
    """Valida seguridad con Bandit"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔒 VALIDACIÓN DE SEGURIDAD (BANDIT){Colors.END}")

    if not check_tool_availability("bandit"):
        print_warning("Bandit no está instalado. Instalando...")
        success, _ = run_command([sys.executable, "-m", "pip", "install", "bandit"],
                              "Instalando Bandit")
        if not success:
            print_error("No se pudo instalar Bandit")
            return False

    all_success = True

    for service in services:
        service_path = Path(service)
        if not service_path.exists():
            continue

        print(f"\n{Colors.CYAN}Validando seguridad en: {service}{Colors.END}")

        bandit_cmd = [
            sys.executable, "-m", "bandit",
            "-r", str(service_path),
            "-f", "json",
            "-q"
        ]

        success, _ = run_command(bandit_cmd, f"Bandit - {service}")
        all_success = all_success and success

    return all_success

def validate_syntax(services: List[str]) -> bool:
    """Valida sintaxis básica de Python"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}🐍 VALIDACIÓN DE SINTAXIS PYTHON{Colors.END}")

    all_success = True

    for service in services:
        service_path = Path(service)
        if not service_path.exists():
            continue

        print(f"\n{Colors.CYAN}Validando sintaxis en: {service}{Colors.END}")

        python_files = list(service_path.rglob("*.py"))
        for py_file in python_files:
            success, _ = run_command(
                [sys.executable, "-m", "py_compile", str(py_file)],
                f"Python syntax - {py_file.name}"
            )
            all_success = all_success and success
            if not success:
                print_error(f"Error de sintaxis en {py_file}")

    return all_success

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Validador de calidad para TinkuBot Python Services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python validate_quality.py                    # Validar todos los servicios
  python validate_quality.py --service ai-clientes  # Validar solo ai-clientes
  python validate_quality.py --fix                 # Corregir automáticamente
        """
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Aplica correcciones automáticas (formato con Black e isort)"
    )

    parser.add_argument(
        "--service",
        choices=["ai-clientes", "ai-proveedores", "search-token"],
        help="Valida solo un servicio específico"
    )

    args = parser.parse_args()

    print_banner()

    # Determinar servicios a validar
    if args.service:
        services = [args.service]
        print_info(f"Validando solo el servicio: {args.service}")
    else:
        services = ["ai-clientes", "ai-proveedores", "search-token"]
        print_info("Validando todos los servicios Python")

    if args.fix:
        print_warning("Modo de corrección automática activado")

    # Ejecutar validaciones
    results = {}

    # 1. Validar sintaxis primero
    results["syntax"] = validate_syntax(services)

    # 2. Validar formato y orden
    results["formatting"] = validate_formatting(services, fix=args.fix)
    results["imports"] = validate_imports(services, fix=args.fix)

    # 3. Validaciones estáticas
    results["linting"] = validate_linting(services)
    results["types"] = validate_types(services)
    results["security"] = validate_security(services)

    # Resumen final
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}║                        RESUMEN DE VALIDACIÓN                    ║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════════════════╝{Colors.END}")

    for check_name, success in results.items():
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        color = Colors.GREEN if success else Colors.RED
        print(f"{color}{check_name.upper():<12}: {status}{Colors.END}")

    total_checks = len(results)
    passed_checks = sum(results.values())

    print(f"\n{Colors.WHITE}Resultados: {passed_checks}/{total_checks} validaciones pasaron{Colors.END}")

    if passed_checks == total_checks:
        print_success("🎉 Todas las validaciones pasaron. Código listo para GitHub!")
        return 0
    else:
        print_error(f"⚠️  {total_checks - passed_checks} validaciones fallaron.")
        print_info("Corrige los problemas antes de subir a GitHub.")
        if not args.fix:
            print_info("Sugerencia: Ejecuta con --fix para correcciones automáticas.")
        return 1

if __name__ == "__main__":
    sys.exit(main())