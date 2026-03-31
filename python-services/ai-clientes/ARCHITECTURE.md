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

## Search Result Messaging Policy
- The customer-facing search flow uses only two outcomes:
  - `No hay expertos registrados` when no valid expert remains for the requested service in the requested city.
  - `No hay expertos disponibles` when there are valid experts registered for that service/city, but none of them respond or get accepted during availability.
- Taxonomy coherence can reject semantically similar but incompatible candidates before availability.
- If the retrieval layer returns providers that do not fit the request's domain/category well enough, the flow should still collapse to `No hay expertos registrados` instead of exposing internal matching details to the customer.
- Do not introduce extra customer-facing copies for intermediate validation states unless the product decision explicitly changes.
