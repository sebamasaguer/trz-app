from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTERS_DIR = ROOT / "app" / "routers"

ROUTE_RE = re.compile(
    r'@router\.(get|post|put|patch|delete)\("([^"]+)"[\s\S]*?def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
    re.MULTILINE,
)

REQUIRE_ROLES_RE = re.compile(
    r"require_roles\(([^)]*)\)",
    re.MULTILINE,
)


def normalize_roles(raw: str) -> str:
    raw = raw.strip()
    raw = raw.replace("\n", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw


def main() -> None:
    print("=" * 90)
    print("AUDITORÍA DE ROLES - SISTEMA TRZ")
    print("=" * 90)
    print()

    if not ROUTERS_DIR.exists():
        print(f"No existe carpeta de routers: {ROUTERS_DIR}")
        return

    findings = []

    for py_file in sorted(ROUTERS_DIR.glob("*.py")):
        text = py_file.read_text(encoding="utf-8", errors="replace")

        route_matches = list(ROUTE_RE.finditer(text))
        if not route_matches:
            continue

        for idx, match in enumerate(route_matches):
            method = match.group(1).upper()
            path = match.group(2)
            func_name = match.group(3)

            start = match.start()
            end = route_matches[idx + 1].start() if idx + 1 < len(route_matches) else len(text)
            block = text[start:end]

            roles_match = REQUIRE_ROLES_RE.search(block)
            roles_raw = normalize_roles(roles_match.group(1)) if roles_match else "SIN require_roles"

            findings.append(
                {
                    "file": py_file.relative_to(ROOT).as_posix(),
                    "method": method,
                    "path": path,
                    "func": func_name,
                    "roles": roles_raw,
                }
            )

    admin_missing = []

    for f in findings:
        roles = f["roles"]

        if roles == "SIN require_roles":
            continue

        # Casos donde aparece ALUM_ONLY, PROF_ONLY, ADMIN_ONLY, etc.
        # No intentamos resolver imports; solo marcamos rutas sensibles para revisión.
        has_admin_literal = "ADMINISTRADOR" in roles
        has_admin_group = "ADMIN" in roles or "ADMIN_PANEL" in roles or "ADMIN_ONLY" in roles

        if not has_admin_literal and not has_admin_group:
            admin_missing.append(f)

    print("RUTAS DETECTADAS")
    print("-" * 90)

    for f in findings:
        print(f"{f['method']:6} {f['path']:<45} {f['file']:<35} roles={f['roles']}")

    print()
    print("=" * 90)
    print("POSIBLES RUTAS DONDE ADMINISTRADOR NO ESTÁ INCLUIDO")
    print("=" * 90)

    if not admin_missing:
        print("No se detectaron rutas con require_roles donde ADMINISTRADOR parezca faltar.")
    else:
        for f in admin_missing:
            print(f"{f['method']:6} {f['path']:<45} {f['file']:<35} roles={f['roles']}")

    print()
    print("Nota:")
    print("- Esta auditoría no modifica código.")
    print("- Sirve para detectar rutas que conviene revisar manualmente.")
    print("- Las páginas ALUMNO pueden requerir lógica especial porque dependen de datos del alumno autenticado.")


if __name__ == "__main__":
    main()