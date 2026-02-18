#!/usr/bin/env python3
"""
Script de Validación de Calidad Local - TinkuBot Python Services

Ejecuta validaciones de calidad antes de subir a GitHub.

Uso:
  python3 validate_quality.py
  python3 validate_quality.py --scope all
  python3 validate_quality.py --service ai-clientes
  python3 validate_quality.py --fix
  python3 validate_quality.py --strict

Opciones:
  --fix      Aplica correcciones automáticas (black/isort)
  --service  Valida solo un servicio específico
  --scope    changed (default) o all
  --strict   Hace bloqueantes también mypy y bandit
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    END = "\033[0m"


SERVICE_PATH_ALIASES = {
    "search-token": "ai-search",
}

CONFIG_FLAKE8 = Path(".flake8")
CONFIG_MYPY = Path("mypy.ini")
CONFIG_BANDIT = Path("bandit.yaml")


@dataclass
class CheckResult:
    passed: bool
    blocking: bool
    note: str = ""


def print_banner() -> None:
    print(
        f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║          VALIDADOR DE CALIDAD - TINKUBOT PYTHON             ║
║                 Antes de subir a GitHub                     ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
{Colors.WHITE}
Este script ejecuta las siguientes validaciones:
• Formato de código (Black)
• Importaciones ordenadas (isort)
• Linting (Flake8)
• Type checking (MyPy)
• Seguridad (Bandit)
• Sintaxis Python
{Colors.END}
"""
    )


def print_success(message: str) -> None:
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")


def print_error(message: str) -> None:
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def print_warning(message: str) -> None:
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")


def print_info(message: str) -> None:
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")


def run_command(
    cmd: Sequence[str], description: str, timeout: int = 120
) -> Tuple[bool, str]:
    print(f"\n{Colors.CYAN}🔍 Ejecutando: {description}{Colors.END}")
    print(f"{Colors.MAGENTA}Comando: {' '.join(cmd)}{Colors.END}")

    try:
        result = subprocess.run(
            list(cmd), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        print_error(f"{description} - TIMEOUT ({timeout}s)")
        return False, f"Timeout after {timeout} seconds"
    except Exception as exc:
        print_error(f"{description} - EXCEPTION: {exc}")
        return False, str(exc)

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode == 0:
        print_success(f"{description} - OK")
        if output.strip():
            print(f"{Colors.WHITE}{output}{Colors.END}")
        return True, output

    print_error(f"{description} - ERROR")
    if output.strip():
        print(f"{Colors.YELLOW}{output}{Colors.END}")
    return False, output


def check_tool_availability(tool_name: str) -> bool:
    try:
        result = subprocess.run(
            [tool_name, "--version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_service_path(service: str) -> Path:
    alias = SERVICE_PATH_ALIASES.get(service, service)
    direct = Path(alias)
    if direct.exists():
        return direct
    nested = Path("python-services") / alias
    if nested.exists():
        return nested
    return direct


def _git_lines(cmd: Sequence[str]) -> List[str]:
    try:
        result = subprocess.run(
            list(cmd), capture_output=True, text=True, timeout=10, check=False
        )
    except Exception:
        return []

    if result.returncode != 0:
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_changed_python_files() -> List[Path]:
    paths: set[Path] = set()

    # Unstaged changes
    for line in _git_lines(["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"]):
        if line.endswith(".py"):
            paths.add(Path(line))

    # Staged changes
    for line in _git_lines(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"]
    ):
        if line.endswith(".py"):
            paths.add(Path(line))

    # Untracked files
    for line in _git_lines(["git", "ls-files", "--others", "--exclude-standard"]):
        if line.endswith(".py"):
            paths.add(Path(line))

    return sorted(paths)


def filter_targets_for_service(
    service_path: Path, targets: Iterable[Path]
) -> List[Path]:
    service_prefix = str(service_path.resolve())
    selected: List[Path] = []
    for target in targets:
        absolute = target.resolve()
        if str(absolute).startswith(service_prefix) and absolute.exists():
            selected.append(absolute)
    return selected


def discover_python_files(service_path: Path) -> List[Path]:
    return sorted(service_path.rglob("*.py"))


def ensure_tools(tools: Sequence[Tuple[str, str]]) -> bool:
    all_ok = True
    for tool, package in tools:
        if check_tool_availability(tool):
            continue
        print_warning(f"{tool} no está instalado. Instalando...")
        ok, _ = run_command(
            [sys.executable, "-m", "pip", "install", package], f"Instalando {tool}"
        )
        all_ok = all_ok and ok
    return all_ok


def validate_syntax(service_targets: Dict[str, List[Path]]) -> CheckResult:
    print(f"\n{Colors.BOLD}{Colors.BLUE}🐍 VALIDACIÓN DE SINTAXIS PYTHON{Colors.END}")
    all_success = True

    for service, files in service_targets.items():
        if not files:
            print_info(f"Sin archivos .py para validar sintaxis en {service}")
            continue
        print(f"\n{Colors.CYAN}Validando sintaxis en: {service}{Colors.END}")
        for py_file in files:
            success, _ = run_command(
                [sys.executable, "-m", "py_compile", str(py_file)],
                f"Python syntax - {py_file.name}",
            )
            all_success = all_success and success

    return CheckResult(passed=all_success, blocking=True)


def validate_formatting(
    service_targets: Dict[str, List[Path]], fix: bool
) -> CheckResult:
    print(f"\n{Colors.BOLD}{Colors.BLUE}📝 VALIDACIÓN DE FORMATO (BLACK){Colors.END}")
    if not ensure_tools([("black", "black")]):
        return CheckResult(
            passed=False, blocking=True, note="No se pudo instalar black"
        )

    all_success = True
    for service, files in service_targets.items():
        if not files:
            print_info(f"Sin archivos para black en {service}")
            continue

        cmd = [sys.executable, "-m", "black", "--line-length=88"]
        if not fix:
            cmd.append("--check")
        cmd.extend(str(f) for f in files)

        success, _ = run_command(cmd, f"Black - {service}")
        all_success = all_success and success

    return CheckResult(passed=all_success, blocking=True)


def validate_imports(service_targets: Dict[str, List[Path]], fix: bool) -> CheckResult:
    print(
        f"\n{Colors.BOLD}{Colors.BLUE}📦 VALIDACIÓN DE IMPORTACIONES (ISORT){Colors.END}"
    )
    if not ensure_tools([("isort", "isort")]):
        return CheckResult(
            passed=False, blocking=True, note="No se pudo instalar isort"
        )

    all_success = True
    for service, files in service_targets.items():
        if not files:
            print_info(f"Sin archivos para isort en {service}")
            continue

        cmd = [
            sys.executable,
            "-m",
            "isort",
            "--profile",
            "black",
            "--line-length",
            "88",
        ]
        if not fix:
            cmd.append("--check-only")
        cmd.extend(str(f) for f in files)

        success, _ = run_command(cmd, f"isort - {service}")
        all_success = all_success and success

    return CheckResult(passed=all_success, blocking=True)


def validate_linting(service_targets: Dict[str, List[Path]]) -> CheckResult:
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔍 VALIDACIÓN LINTING (FLAKE8){Colors.END}")
    if not ensure_tools([("flake8", "flake8")]):
        return CheckResult(
            passed=False, blocking=True, note="No se pudo instalar flake8"
        )

    all_success = True
    for service, files in service_targets.items():
        if not files:
            print_info(f"Sin archivos para flake8 en {service}")
            continue

        cmd = [
            sys.executable,
            "-m",
            "flake8",
            "--jobs",
            "1",
            "--config",
            str(CONFIG_FLAKE8),
        ]
        cmd.extend(str(f) for f in files)

        success, _ = run_command(cmd, f"Flake8 - {service}")
        all_success = all_success and success

    return CheckResult(passed=all_success, blocking=True)


def validate_types(service_targets: Dict[str, List[Path]], strict: bool) -> CheckResult:
    print(f"\n{Colors.BOLD}{Colors.BLUE}🔧 VALIDACIÓN DE TIPOS (MYPY){Colors.END}")
    if not ensure_tools([("mypy", "mypy")]):
        return CheckResult(
            passed=False, blocking=strict, note="No se pudo instalar mypy"
        )

    all_success = True
    any_files = False
    for service, files in service_targets.items():
        if not files:
            continue
        any_files = True

        cmd = [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(CONFIG_MYPY),
        ]
        cmd.extend(str(f) for f in files)

        success, _ = run_command(cmd, f"MyPy - {service}", timeout=180)
        all_success = all_success and success

    if not any_files:
        print_info("Sin archivos para mypy")
    return CheckResult(passed=all_success, blocking=strict)


def validate_security(
    service_targets: Dict[str, List[Path]], strict: bool
) -> CheckResult:
    print(
        f"\n{Colors.BOLD}{Colors.BLUE}🔒 VALIDACIÓN DE SEGURIDAD (BANDIT){Colors.END}"
    )
    if not ensure_tools([("bandit", "bandit")]):
        return CheckResult(
            passed=False, blocking=strict, note="No se pudo instalar bandit"
        )

    all_success = True
    any_files = False

    for service, files in service_targets.items():
        if not files:
            continue
        any_files = True
        cmd = [
            sys.executable,
            "-m",
            "bandit",
            "-f",
            "json",
            "-q",
            "-c",
            str(CONFIG_BANDIT),
        ]
        cmd.extend(str(f) for f in files)

        success, _ = run_command(cmd, f"Bandit - {service}", timeout=180)
        all_success = all_success and success

    if not any_files:
        print_info("Sin archivos para bandit")
    return CheckResult(passed=all_success, blocking=strict)


def _exclude_templates(files: Iterable[Path], include_templates: bool) -> List[Path]:
    if include_templates:
        return sorted(files)
    return sorted(path for path in files if "/templates/" not in str(path))


def build_service_targets(
    services: Sequence[str], scope: str, include_templates: bool
) -> Dict[str, List[Path]]:
    targets: Dict[str, List[Path]] = {}

    if scope == "changed":
        changed = get_changed_python_files()
        if changed:
            print_info(f"Scope changed: {len(changed)} archivos Python detectados")
        else:
            print_warning("Scope changed: no hay archivos Python cambiados")

        for service in services:
            service_path = resolve_service_path(service)
            if not service_path.exists():
                print_warning(f"Servicio {service} no encontrado, omitiendo")
                targets[service] = []
                continue
            selected = filter_targets_for_service(service_path, changed)
            targets[service] = _exclude_templates(selected, include_templates)
    else:
        for service in services:
            service_path = resolve_service_path(service)
            if not service_path.exists():
                print_warning(f"Servicio {service} no encontrado, omitiendo")
                targets[service] = []
                continue
            selected = discover_python_files(service_path)
            targets[service] = _exclude_templates(selected, include_templates)

    return targets


def summarize_results(results: Dict[str, CheckResult]) -> int:
    top = "╔══════════════════════════════════════════════════════════════╗"
    mid = "║                        RESUMEN DE VALIDACIÓN                ║"
    bot = "╚══════════════════════════════════════════════════════════════╝"
    print(f"\n{Colors.BOLD}{Colors.CYAN}{top}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{mid}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{bot}{Colors.END}")

    for check_name, result in results.items():
        if result.passed:
            status = "✅ PASÓ"
            color = Colors.GREEN
        else:
            gate = "BLOCKING" if result.blocking else "ADVISORY"
            status = f"❌ FALLÓ ({gate})"
            color = Colors.RED if result.blocking else Colors.YELLOW
        print(f"{color}{check_name.upper():<12}: {status}{Colors.END}")

    blocking_failed = [
        name
        for name, result in results.items()
        if result.blocking and not result.passed
    ]
    total_blocking = sum(1 for r in results.values() if r.blocking)
    passed_blocking = sum(1 for r in results.values() if r.blocking and r.passed)

    resumen = f"Resultados bloqueantes: {passed_blocking}/{total_blocking}"
    print(f"\n{Colors.WHITE}{resumen}{Colors.END}")

    if blocking_failed:
        print_error(f"Checks bloqueantes fallidos: {', '.join(blocking_failed)}")
        print_info("Corrige estos checks antes de subir cambios.")
        return 1

    print_success("Checks bloqueantes OK.")
    advisory_failed = [
        name
        for name, result in results.items()
        if not result.blocking and not result.passed
    ]
    if advisory_failed:
        joined = ", ".join(advisory_failed)
        print_warning(f"Checks informativos con fallos (deuda histórica): {joined}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validador de calidad para TinkuBot Python Services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Aplica correcciones automáticas (black/isort)",
    )
    parser.add_argument(
        "--service",
        choices=["ai-clientes", "ai-proveedores", "search-token"],
        help="Valida solo un servicio específico",
    )
    parser.add_argument(
        "--scope",
        choices=["changed", "all"],
        default="changed",
        help="Alcance de archivos a validar (default: changed)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Mypy y Bandit pasan a ser checks bloqueantes",
    )
    parser.add_argument(
        "--include-templates",
        action="store_true",
        help="Incluye archivos dentro de templates en el scope validado",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print_banner()

    services = (
        [args.service]
        if args.service
        else ["ai-clientes", "ai-proveedores", "search-token"]
    )
    print_info(f"Servicios: {', '.join(services)}")
    print_info(f"Scope: {args.scope}")
    print_info(f"Strict: {'sí' if args.strict else 'no'}")

    if args.fix:
        print_warning("Modo fix activado (black/isort)")

    for required_config in (CONFIG_FLAKE8, CONFIG_MYPY, CONFIG_BANDIT):
        if not required_config.exists():
            print_error(f"Falta archivo de configuración: {required_config}")
            return 1

    service_targets = build_service_targets(
        services, args.scope, include_templates=args.include_templates
    )

    results: Dict[str, CheckResult] = {}
    results["syntax"] = validate_syntax(service_targets)
    results["formatting"] = validate_formatting(service_targets, fix=args.fix)
    results["imports"] = validate_imports(service_targets, fix=args.fix)
    results["linting"] = validate_linting(service_targets)
    results["types"] = validate_types(service_targets, strict=args.strict)
    results["security"] = validate_security(service_targets, strict=args.strict)

    return summarize_results(results)


if __name__ == "__main__":
    sys.exit(main())
