"""Guardrails de arquitectura para mantener separados los contextos."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTEXTS = {"onboarding", "maintenance", "review", "availability"}

# Esta lista congela el estado actual mientras reducimos el acoplamiento.
# Cualquier cruce nuevo entre contextos debe pasar por revisión explícita.
LEGACY_CROSS_CONTEXT_IMPORTS = {
    (
        "flows/onboarding/handlers/servicios.py",
        "services.maintenance.validacion_semantica",
    ),
    (
        "services/onboarding/registration/registro_proveedor.py",
        "services.maintenance.validacion_semantica",
    ),
}


def _iter_python_files() -> list[Path]:
    paths: list[Path] = []
    for root_name in ("services", "flows", "routes", "templates"):
        paths.extend((ROOT / root_name).rglob("*.py"))
    return sorted(paths)


def _source_context(rel_path: Path) -> str | None:
    if len(rel_path.parts) < 2:
        return None
    if rel_path.parts[1] not in CONTEXTS:
        return None
    return rel_path.parts[1]


def _target_context(module: str) -> str | None:
    for part in module.split("."):
        if part in CONTEXTS:
            return part
    return None


def _scan_cross_context_edges() -> set[tuple[str, str]]:
    discovered: set[tuple[str, str]] = set()
    for path in _iter_python_files():
        rel = path.relative_to(ROOT)
        source_context = _source_context(rel)
        if source_context is None:
            continue

        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:  # pragma: no cover - file is already invalid
            raise AssertionError(f"No se pudo parsear {rel}: {exc}") from exc

        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]

            for module in modules:
                target_context = _target_context(module)
                if target_context is None or target_context == source_context:
                    continue

                discovered.add((rel.as_posix(), module))

    return discovered


def test_no_new_cross_context_imports_are_introduced() -> None:
    discovered = _scan_cross_context_edges()
    unexpected = discovered - LEGACY_CROSS_CONTEXT_IMPORTS

    assert not unexpected, (
        "Se detectaron nuevos cruces entre contextos. "
        "Mueve la lógica al contexto dueño o añade una excepción explícita "
        f"solo si es un puente temporal aprobado: {sorted(unexpected)}"
    )
