#!/usr/bin/env python3
"""
Validación de Dockerfiles y docker-compose.yml
Verifica mejores prácticas de seguridad y configuración.

Ejecutar: python validate_docker.py
"""

import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(Enum):
    """Niveles de severidad para validaciones."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class ValidationResult:
    """Resultado de una validación."""
    file_path: str
    check_name: str
    severity: Severity
    message: str
    line: Optional[int] = None
    passed: bool = False


class DockerfileValidator:
    """Valida Dockerfiles."""

    NON_ROOT_USER_PATTERNS = [
        r"USER\s+(?!root)[\w-]+",
        r"USER\s+\d{3,4}",  # UID numerado (ej: 1000)
    ]

    def __init__(self, dockerfile_path: str | Path):
        self.path = Path(dockerfile_path)
        self.content = self.path.read_text()
        self.lines = self.content.split("\n")
        self.results: list[ValidationResult] = []
        self._base_images = self._extract_base_images()

    def validate(self) -> list[ValidationResult]:
        """Ejecuta todas las validaciones."""
        self._check_dockerignore()
        self._check_base_image_version()
        self._check_labels()
        self._check_healthcheck()
        self._check_non_root_user()
        self._check_python_unbuffered()
        self._check_node_env()
        self._check_add_vs_copy()
        self._check_caching_layers()

        return self.results

    def _extract_base_images(self) -> list[str]:
        """Extrae imágenes base desde instrucciones FROM."""
        images: list[str] = []
        from_pattern = re.compile(r"^FROM\s+([^\s]+)(?:\s+AS\s+\S+)?", re.IGNORECASE)
        for line in self.lines:
            match = from_pattern.match(line.strip())
            if match:
                images.append(match.group(1))
        return images

    def _add_result(
        self,
        check_name: str,
        severity: Severity,
        message: str,
        line: Optional[int] = None,
        passed: bool = False,
    ) -> None:
        self.results.append(
            ValidationResult(
                file_path=str(self.path),
                check_name=check_name,
                severity=severity,
                message=message,
                line=line,
                passed=passed,
            )
        )

    def _check_dockerignore(self) -> None:
        """Verifica que existe .dockerignore en el mismo directorio."""
        dockerignore_path = self.path.parent / ".dockerignore"
        if dockerignore_path.exists():
            self._add_result(
                check_name=".dockerignore",
                severity=Severity.INFO,
                message=f"Existe .dockerignore",
                passed=True,
            )
        else:
            self._add_result(
                check_name=".dockerignore",
                severity=Severity.CRITICAL,
                message="Falta archivo .dockerignore (optimiza tamaño de imagen)",
            )

    def _check_base_image_version(self) -> None:
        """Verifica que la imagen base tenga versión específica."""
        from_pattern = re.compile(r"^FROM\s+([^\s]+)(?:\s+AS\s+\S+)?", re.IGNORECASE)

        for i, line in enumerate(self.lines, 1):
            match = from_pattern.match(line.strip())
            if not match:
                continue

            image = match.group(1)
            has_digest = "@" in image
            has_tag = ":" in image.split("@", 1)[0]
            is_latest = image.endswith(":latest")

            if has_digest or (has_tag and not is_latest):
                self._add_result(
                    check_name="Base Image Version",
                    severity=Severity.INFO,
                    message=f"Versión específica: {image}",
                    line=i,
                    passed=True,
                )
            else:
                self._add_result(
                    check_name="Base Image Version",
                    severity=Severity.MEDIUM,
                    message=f"Imagen base sin versión específica: {image}",
                    line=i,
                )

    def _check_labels(self) -> None:
        """Verifica metadatos LABEL."""
        labels_found = re.findall(r"^LABEL\s+", self.content, re.MULTILINE)

        if len(labels_found) >= 2:
            self._add_result(
                check_name="LABEL Metadata",
                severity=Severity.INFO,
                message=f"Se encontraron {len(labels_found)} LABEL",
                passed=True,
            )
        else:
            self._add_result(
                check_name="LABEL Metadata",
                severity=Severity.LOW,
                message="Falta agregar LABEL con metadata (maintainer, version, description)",
            )

    def _check_healthcheck(self) -> None:
        """Verifica directiva HEALTHCHECK."""
        if re.search(r"^HEALTHCHECK\s+", self.content, re.MULTILINE):
            self._add_result(
                check_name="HEALTHCHECK",
                severity=Severity.INFO,
                message="Directiva HEALTHCHECK presente",
                passed=True,
            )
        else:
            self._add_result(
                check_name="HEALTHCHECK",
                severity=Severity.MEDIUM,
                message="Falta directiva HEALTHCHECK (importante para orquestación)",
            )

    def _check_non_root_user(self) -> None:
        """Verifica que el contenedor no ejecute como root."""
        has_user = False
        is_non_root = False

        for i, line in enumerate(self.lines, 1):
            if re.match(r"^USER\s+", line.strip()):
                has_user = True
                # Verificar si no es root
                for pattern in self.NON_ROOT_USER_PATTERNS:
                    if re.search(pattern, line):
                        is_non_root = True
                        break

        if not has_user:
            self._add_result(
                check_name="Non-Root User",
                severity=Severity.HIGH,
                message="No se especifica usuario (ejecuta como root por defecto)",
            )
        elif is_non_root:
            self._add_result(
                check_name="Non-Root User",
                severity=Severity.INFO,
                message="Usuario no-root configurado",
                passed=True,
            )
        else:
            self._add_result(
                check_name="Non-Root User",
                severity=Severity.HIGH,
                message="Contenedor ejecuta como root",
            )

    def _check_python_unbuffered(self) -> None:
        """Verifica PYTHONUNBUFFERED para servicios Python."""
        if any("python" in img.lower() for img in self._base_images):
            if re.search(r"ENV\s+PYTHONUNBUFFERED=1", self.content):
                self._add_result(
                    check_name="PYTHONUNBUFFERED",
                    severity=Severity.INFO,
                    message="PYTHONUNBUFFERED=1 configurado",
                    passed=True,
                )
            else:
                self._add_result(
                    check_name="PYTHONUNBUFFERED",
                    severity=Severity.LOW,
                    message="Falta ENV PYTHONUNBUFFERED=1 (mejora logging de Python)",
                )

    def _check_node_env(self) -> None:
        """Verifica NODE_ENV=production para servicios Node.js."""
        if any(re.search(r"\bnode\b", img.lower()) for img in self._base_images):
            if re.search(r"ENV\s+NODE_ENV=production", self.content):
                self._add_result(
                    check_name="NODE_ENV",
                    severity=Severity.INFO,
                    message="NODE_ENV=production configurado",
                    passed=True,
                )
            else:
                self._add_result(
                    check_name="NODE_ENV",
                    severity=Severity.MEDIUM,
                    message="Falta ENV NODE_ENV=production",
                )

    def _check_add_vs_copy(self) -> None:
        """Advierte sobre uso de ADD vs COPY."""
        add_count = len(re.findall(r"^\s*ADD\s+", self.content, re.MULTILINE))

        if add_count > 0:
            self._add_result(
                check_name="ADD vs COPY",
                severity=Severity.LOW,
                message=f"Se encontraron {add_count} instrucciones ADD (preferir COPY excepto para URLs/tar)",
            )

    def _check_caching_layers(self) -> None:
        """Verifica optimización de cache (requirements primero)."""
        # Buscar patrón: COPY requirements.txt antes de COPY código
        req_line = None
        code_line = None

        for i, line in enumerate(self.lines, 1):
            if re.search(r"COPY\s+requirements\.txt", line):
                req_line = i
            if re.search(r"COPY\s+\.\s+\.", line) or re.search(r"COPY\s+\S+\s+\.", line):
                if code_line is None:  # Primer COPY de código
                    code_line = i

        if req_line and code_line and req_line < code_line:
            self._add_result(
                check_name="Layer Caching",
                severity=Severity.INFO,
                message="requirements.txt copiado antes del código (cache optimizado)",
                passed=True,
            )


class DockerComposeValidator:
    """Valida docker-compose.yml."""

    def __init__(self, compose_path: str | Path = "docker-compose.yml"):
        self.path = Path(compose_path)
        self.content = self.path.read_text()
        self.results: list[ValidationResult] = []

    def validate(self) -> list[ValidationResult]:
        """Ejecuta todas las validaciones."""
        self._check_healthcheck()
        self._check_resource_limits()
        self._check_logging()
        self._check_restart_policy()
        self._check_networks()
        self._check_image_versions()

        return self.results

    def _add_result(
        self,
        check_name: str,
        severity: Severity,
        message: str,
        passed: bool = False,
    ) -> None:
        self.results.append(
            ValidationResult(
                file_path=str(self.path),
                check_name=check_name,
                severity=severity,
                message=message,
                passed=passed,
            )
        )

    def _check_healthcheck(self) -> None:
        """Verifica healthcheck en servicios."""
        services_block = self._extract_services_block()
        services = re.findall(r"^\s{2}([\w-]+):", services_block, re.MULTILINE)

        services_with_healthcheck = []
        for service in services:
            # Buscar healthcheck dentro del servicio
            service_block = self._extract_service_block(service)
            if "healthcheck:" in service_block:
                services_with_healthcheck.append(service)

        if len(services_with_healthcheck) == len(services):
            self._add_result(
                check_name="Service Healthchecks",
                severity=Severity.INFO,
                message=f"Todos {len(services)} servicios tienen healthcheck",
                passed=True,
            )
        else:
            missing = [s for s in services if s not in services_with_healthcheck]
            self._add_result(
                check_name="Service Healthchecks",
                severity=Severity.MEDIUM,
                message=f"Servicios sin healthcheck: {', '.join(missing)}",
            )

    def _check_resource_limits(self) -> None:
        """Verifica límites de recursos."""
        has_limits = "resources:" in self.content and "limits:" in self.content

        if has_limits:
            self._add_result(
                check_name="Resource Limits",
                severity=Severity.INFO,
                message="Límites de recursos configurados",
                passed=True,
            )
        else:
            self._add_result(
                check_name="Resource Limits",
                severity=Severity.MEDIUM,
                message="Falta configurar límites de recursos (deploy.resources.limits)",
            )

    def _check_logging(self) -> None:
        """Verifica configuración de logging."""
        has_logging = "logging:" in self.content and "max-size:" in self.content

        if has_logging:
            self._add_result(
                check_name="Logging Configuration",
                severity=Severity.INFO,
                message="Logging con rotación configurado",
                passed=True,
            )
        else:
            self._add_result(
                check_name="Logging Configuration",
                severity=Severity.LOW,
                message="Falta configurar rotación de logs (logging.options.max-size)",
            )

    def _check_restart_policy(self) -> None:
        """Verifica políticas de reinicio."""
        has_restart = "restart_policy:" in self.content

        if has_restart:
            self._add_result(
                check_name="Restart Policy",
                severity=Severity.INFO,
                message="Política de reinicio configurada",
                passed=True,
            )
        else:
            self._add_result(
                check_name="Restart Policy",
                severity=Severity.LOW,
                message="Falta configurar restart_policy",
            )

    def _check_networks(self) -> None:
        """Verifica configuración de redes."""
        has_networks = "networks:" in self.content and "tinkubot-network:" in self.content

        if has_networks:
            self._add_result(
                check_name="Network Configuration",
                severity=Severity.INFO,
                message="Red personalizada configurada",
                passed=True,
            )
        else:
            self._add_result(
                check_name="Network Configuration",
                severity=Severity.MEDIUM,
                message="Usa red default (considerar red personalizada)",
            )

    def _check_image_versions(self) -> None:
        """Advierte sobre imágenes sin versión específica."""
        # Buscar imágenes externas (no build locales)
        image_lines = re.findall(r"^\s*image:\s*([^\s#]+)", self.content, re.MULTILINE)

        for image in image_lines:
            if "@" in image:
                continue  # digest pinning is OK
            if ":" not in image or image.endswith(":latest"):
                self._add_result(
                    check_name="Image Versions",
                    severity=Severity.LOW,
                    message=f"Imagen sin versión específica: {image if ':' in image else image + ':latest'}",
                )

    def _extract_service_block(self, service_name: str) -> str:
        """Extrae el bloque de configuración de un servicio."""
        # Encontrar inicio del servicio
        pattern = rf"^\s{{2}}{service_name}:\s*$"
        match = re.search(pattern, self.content, re.MULTILINE)

        if not match:
            return ""

        # Encontrar fin (siguiente servicio al mismo nivel)
        start = match.end()
        next_service = re.search(rf"^\s{{2}}\w+:\s*$", self.content[start:], re.MULTILINE)

        if next_service:
            return self.content[start : start + next_service.start()]
        return self.content[start:]

    def _extract_services_block(self) -> str:
        """Extrae el bloque de servicios del docker-compose."""
        match = re.search(r"^services:\s*$", self.content, re.MULTILINE)
        if not match:
            return ""
        start = match.end()
        # Termina cuando aparece otra clave top-level
        next_top = re.search(r"^[a-zA-Z0-9_-]+:\s*$", self.content[start:], re.MULTILINE)
        if next_top:
            return self.content[start : start + next_top.start()]
        return self.content[start:]


def print_results(results: list[ValidationResult]) -> None:
    """Imprime resultados de validación."""
    # Agrupar por severidad
    by_severity: dict[Severity, list[ValidationResult]] = {
        sev: [] for sev in Severity
    }

    for r in results:
        by_severity[r.severity].append(r)

    # Ordenar severidades por importancia
    severity_order = [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
        Severity.INFO,
    ]

    total_passed = sum(1 for r in results if r.passed)
    total_checks = len(results)

    print("\n" + "=" * 70)
    print(" RESULTADOS DE VALIDACIÓN DOCKER")
    print("=" * 70)
    print(f"\nTotal: {total_passed}/{total_checks} checks pasaron\n")

    for severity in severity_order:
        items = by_severity[severity]
        if not items:
            continue

        # Color ANSI para terminal
        colors = {
            Severity.CRITICAL: "\033[91m",  # Rojo
            Severity.HIGH: "\033[91m",
            Severity.MEDIUM: "\033[93m",  # Amarillo
            Severity.LOW: "\033[94m",  # Azul
            Severity.INFO: "\033[92m",  # Verde
        }
        reset = "\033[0m"

        color = colors.get(severity, "")
        icon = "✓" if severity == Severity.INFO else "⚠"

        print(f"{color}{icon} {severity.value}{reset} ({len(items)})")

        for item in items:
            location = ""
            if item.line:
                location = f":{item.line}"
            print(f"  • {item.file_path}{location}")
            print(f"    [{item.check_name}] {item.message}")

        print()

    # Resumen final
    critical = len(by_severity[Severity.CRITICAL])
    high = len(by_severity[Severity.HIGH])

    if critical > 0 or high > 0:
        print(f"\033[91m❌ Se encontraron {critical} críticos y {high} altos\033[0m")
        return 1
    else:
        print(f"\033[92m✓ Validación completada sin errores críticos\033[0m")
        return 0


def find_all_dockerfiles() -> list[Path]:
    """Encuentra todos los Dockerfiles en el proyecto."""
    dockerfiles = []

    # Servicios Python
    python_services = ["ai-clientes", "ai-proveedores", "ai-search", "av-proveedores"]
    for svc in python_services:
        df = Path(f"python-services/{svc}/Dockerfile")
        if df.exists():
            dockerfiles.append(df)

    # Servicios Node.js
    node_services = ["frontend", "wa-clientes", "wa-proveedores"]
    for svc in node_services:
        df = Path(f"nodejs-services/{svc}/Dockerfile")
        if df.exists():
            dockerfiles.append(df)

    return dockerfiles


def main() -> int:
    """Función principal."""
    all_results: list[ValidationResult] = []

    # Validar Dockerfiles
    print("🔍 Escaneando Dockerfiles...")
    dockerfiles = find_all_dockerfiles()

    for df in dockerfiles:
        validator = DockerfileValidator(df)
        all_results.extend(validator.validate())

    # Validar docker-compose.yml
    print("🔍 Escaneando docker-compose.yml...")
    if Path("docker-compose.yml").exists():
        compose_validator = DockerComposeValidator()
        all_results.extend(compose_validator.validate())

    # Imprimir resultados
    return print_results(all_results)


if __name__ == "__main__":
    sys.exit(main())
