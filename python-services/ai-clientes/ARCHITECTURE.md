# AI-Clientes Architecture Rules

## Composition Root
- `principal.py` is the only composition root.
- Concrete implementations (`Redis`, `Supabase`, HTTP clients) must be wired there.

## Contracts First
- Domain/orchestration layers should depend on contracts (`contracts/*.py`) instead of concrete infra classes.
- Current first-scope contracts: `IRepositorioFlujo`, `IRepositorioClientes`.

## Dependency Direction
- Allowed: `services/*` -> `contracts/*`
- Avoid: `services/*` -> `infrastructure/*` concrete classes (except strictly transitional code paths already in place).

## Testing Strategy
- Keep behavior tests as-is.
- Add contract tests to verify repository implementations satisfy protocol behavior:
  - `tests/contracts/test_repositorio_flujo_contract.py`
  - `tests/contracts/test_repositorio_clientes_contract.py`

## Non-goals in this stage
- No changes to `flows/*`.
- No changes to `templates/*`.
- No user-facing behavior changes.
