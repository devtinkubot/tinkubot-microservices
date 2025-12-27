#!/usr/bin/env python3
"""
Script de Validación de Calidad Local - TinkuBot (Python + Node.js)

Ejecuta validaciones de calidad antes de subir a GitHub.
Uso: python validate_quality_code.py [--fix] [--service nombre_servicio] [--stack python|node|all]

Opciones:
--fix : Aplica correcciones automáticas (formato con black)
--service : Valida un servicio específico (python o node)
--stack : Ejecuta validaciones para python, node o ambos (default: all)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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
║          🔍 VALIDADOR DE CALIDAD - TINKUBOT (PY/JS)         ║
║                 Antes de subir a GitHub                    ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
{Colors.WHITE}
Este script ejecuta las siguientes validaciones:
• Python: Black, Flake8, MyPy, Bandit, isort, sintaxis
• Node: Prettier, ESLint (según scripts definidos)
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

def load_package_scripts(service_path: Path) -> Dict[str, str]:
    """Carga los scripts desde package.json."""
    package_json = service_path / "package.json"
    if not package_json.exists():
        return {}
    try:
        return json.loads(package_json.read_text()).get("scripts", {})
    except Exception:
        return {}

def ensure_node_modules(service_path: Path, install_deps: bool) -> bool:
    """Asegura dependencias Node instaladas."""
    node_modules = service_path / "node_modules"
    if node_modules.exists():
        return True
    if not install_deps:
        print_warning(
            f"node_modules no existe en {service_path.name}. Ejecuta con --node-install para instalar."
        )
        return False
    install_cmd = ["npm", "ci"] if (service_path / "package-lock.json").exists() else ["npm", "install"]
    success, _ = run_command(install_cmd, f"Instalando dependencias Node - {service_path.name}", cwd=str(service_path))
    return success

def run_npm_script(service_path: Path, script_name: str, description: str) -> bool:
    """Ejecuta un script npm si existe."""
    scripts = load_package_scripts(service_path)
    if script_name not in scripts:
        print_warning(f"Script '{script_name}' no existe en {service_path.name}, omitiendo...")
        return False
    success, _ = run_command(["npm", "run", script_name], description, cwd=str(service_path))
    return success

def run_npm_audit(service_path: Path, description: str) -> bool:
    """Ejecuta npm audit con un umbral conservador."""
    success, _ = run_command(
        ["npm", "audit", "--audit-level=high"],
        description,
        cwd=str(service_path)
    )
    return success

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
        black_cmd.append("--line-length=120")
        print_info("Modo de corrección automática activado")
    else:
        black_cmd.extend(["--check", "--line-length=120"])
        print_info("Modo de verificación (sin cambios)")

    for service in services:
        service_path = Path("python-services") / service
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
    isort_cmd = [sys.executable, "-m", "isort", "--profile", "black", "--line-length", "120"]

    if fix:
        print_info("Modo de corrección automática activado")
    else:
        isort_cmd.append("--check-only")
        print_info("Modo de verificación (sin cambios)")

    for service in services:
        service_path = Path("python-services") / service
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
max-line-length = 120
extend-ignore = E203, W503, E501, C901
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
max-complexity = 15
"""

    config_path = Path(".flake8")
    with open(config_path, "w") as f:
        f.write(flake8_config)

    all_success = True

    for service in services:
        service_path = Path("python-services") / service
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
        service_path = Path("python-services") / service
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
            "--explicit-package-bases",  # Evitar error de módulos duplicados
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
        service_path = Path("python-services") / service
        if not service_path.exists():
            continue

        print(f"\n{Colors.CYAN}Validando seguridad en: {service}{Colors.END}")

        bandit_cmd = [
            sys.executable, "-m", "bandit",
            "-r", str(service_path),
            "-f", "json",
            "-ll",  # Minimum severity level: medium (ignora LOW)
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
        service_path = Path("python-services") / service
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

def validate_node_quality(services: List[str], fix: bool = False, run_audit: bool = False,
                          install_deps: bool = False) -> Dict[str, bool]:
    """Valida calidad en servicios Node.js."""
    results: Dict[str, bool] = {}

    print(f"\n{Colors.BOLD}{Colors.BLUE}🟢 VALIDACIÓN NODE.JS{Colors.END}")

    if not check_tool_availability("npm"):
        print_error("npm no está instalado o no está en PATH")
        results["node"] = False
        return results

    for service in services:
        service_path = Path("nodejs-services") / service
        if not service_path.exists():
            print_warning(f"Servicio Node {service} no encontrado, omitiendo...")
            continue

        print(f"\n{Colors.CYAN}Validando Node en: {service}{Colors.END}")

        if not ensure_node_modules(service_path, install_deps):
            results[f"{service}-deps"] = False
            continue

        fmt_script = "format" if fix else "format:check"
        results[f"{service}-format"] = run_npm_script(
            service_path,
            fmt_script,
            f"Prettier - {service}"
        )
        results[f"{service}-lint"] = run_npm_script(
            service_path,
            "lint",
            f"ESLint - {service}"
        )

        if run_audit:
            results[f"{service}-audit"] = run_npm_audit(
                service_path,
                f"npm audit - {service}"
            )

    return results

def main():
    """Función principal"""
    python_services = ["ai-clientes", "ai-proveedores", "ai-search", "av-proveedores"]
    node_services = ["frontend", "wa-clientes", "wa-proveedores"]

    parser = argparse.ArgumentParser(
        description="Validador de calidad para TinkuBot (Python + Node.js)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python validate_quality_code.py                    # Validar todos los servicios
  python validate_quality_code.py --service ai-clientes  # Validar solo ai-clientes
  python validate_quality_code.py --service wa-clientes  # Validar solo wa-clientes
  python validate_quality_code.py --stack node           # Validar solo Node.js
  python validate_quality_code.py --fix                 # Corregir automáticamente
        """
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Aplica correcciones automáticas (formato con Black e isort)"
    )

    parser.add_argument(
        "--service",
        choices=python_services + node_services,
        help="Valida solo un servicio específico"
    )

    parser.add_argument(
        "--stack",
        choices=["python", "node", "all"],
        default="all",
        help="Selecciona qué stack validar (default: all)"
    )

    parser.add_argument(
        "--node-audit",
        action="store_true",
        help="Ejecuta npm audit en servicios Node.js (puede requerir red)"
    )

    parser.add_argument(
        "--node-install",
        action="store_true",
        help="Instala dependencias Node.js si faltan (npm ci/install)"
    )

    args = parser.parse_args()

    print_banner()

    # Determinar servicios a validar
    if args.service:
        if args.service in python_services:
            python_services = [args.service]
            node_services = []
        else:
            node_services = [args.service]
            python_services = []
        print_info(f"Validando solo el servicio: {args.service}")
    else:
        if args.stack == "python":
            node_services = []
            print_info("Validando solo servicios Python")
        elif args.stack == "node":
            python_services = []
            print_info("Validando solo servicios Node.js")
        else:
            print_info("Validando servicios Python y Node.js")

    if args.fix:
        print_warning("Modo de corrección automática activado")

    # Ejecutar validaciones
    results = {}

    if python_services:
        # 1. Validar sintaxis primero
        results["py-syntax"] = validate_syntax(python_services)

        # 2. Validar formato y orden
        results["py-formatting"] = validate_formatting(python_services, fix=args.fix)
        results["py-imports"] = validate_imports(python_services, fix=args.fix)

        # 3. Validaciones estáticas
        results["py-linting"] = validate_linting(python_services)
        results["py-types"] = validate_types(python_services)
        results["py-security"] = validate_security(python_services)

    if node_services:
        node_results = validate_node_quality(
            node_services,
            fix=args.fix,
            run_audit=args.node_audit,
            install_deps=args.node_install
        )
        results.update(node_results)

    # Resumen final
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}║                        RESUMEN DE VALIDACIÓN                    ║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════════════════╝{Colors.END}")

    for check_name, success in results.items():
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        color = Colors.GREEN if success else Colors.RED
        print(f"{color}{check_name.upper():<12}: {status}{Colors.END}")

    total_checks = len(results)
    passed_checks = sum(1 for success in results.values() if success)

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
