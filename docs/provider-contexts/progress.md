# Provider Context Split Progress

## Current status
Audit complete, review is now owned by a single boundary, availability is now fully owned by its route and processor boundaries, onboarding now has its own route boundary and is limited to the alta journey, and maintenance routing is being sliced by concern while the shared router owns the remaining entry bridges.

## Completed
- Identified the need to separate onboarding, review, and maintenance
- Defined the target folders in English and one word each
- Created the new folder skeleton in the repo
- Documented the migration plan and the decision boundaries
- Audited wrappers, facades, and compatibility bridges in `ai-proveedores`
- Wrote a state audit that classifies onboarding, maintenance, review, and legacy aliases
- Added a block-level audit for onboarding, maintenance, and review
- Added an ownership matrix that maps states to onboarding, review, maintenance, and shared bridges
- Added a migration-priority document that orders the next refactor steps by ownership and risk
- Prioritized the remaining shared-router branches for extraction in the next pass
- Extracted the availability-response state into `routes/availability`
- Delegated availability session handling out of `flows/router.py`
- Moved the Redis-backed availability processor into `services/availability/processor.py`
- Retired `services/disponibilidad_interceptacion.py` after the canonical processor boundary was established
- Added an onboarding route boundary under `routes/onboarding`
- Moved onboarding entry, consent, and confirmation handling behind `routes/onboarding`
- Restricted onboarding to the alta journey so registered providers do not re-enter it from the shared router
- Extracted the first review policy into `services/review`
- Added a review router entrypoint under `routes/review`
- Moved review initial-entry handling behind `routes/review`
- Kept `services/sesion_proveedor.py` as a compatibility facade
- Moved the menu-limited review response into `services/maintenance`
- Added a maintenance router bridge for the limited menu state
- Moved the registered menu handoff into `routes/maintenance`
- Removed the maintenance fallback that bounced non-registered providers back into onboarding
- Restricted the main maintenance menu handler to registered providers only
- Moved social and profile-view routing into `routes/maintenance/handlers`
- Moved personal/professional submenu routing into `routes/maintenance/info`
- Added an onboarding-specific service-edit subflow with its own `onboarding_*` states
- Normalized menu add-service transitions to `maintenance_service_add`
- Updated the dedupe and submenu tests to the new service-add contract
- Retired the `awaiting_service_add` compatibility alias from runtime maps
- Retired the last legacy service aliases from runtime maps
- Removed the legacy service maintenance aliases from the maintenance services router
- Removed the old `templates/verificacion` compatibility wrapper
- Removed the old `templates/registro/resumen_consentimiento.py` wrapper
- Removed the empty `templates/verificacion` package entrypoint
- Updated onboarding and maintenance states to use separate namespaces
- Modernized maintenance profile and social handlers to prefer `maintenance_*` states
- Updated the social-network update resolver to recognize modern maintenance states
- Moved the remaining maintenance-facing submenu tests to the modern service/profile vocabulary
- Modernized maintenance-facing transitions in `gestor_vistas_perfil.py` to emit `maintenance_*` states when the flow is already in maintenance
- Confirmed the remaining `awaiting_*` names in the profile-view router are shared-flow bridges, not dead wrappers
- Confirmed the remaining router-level `awaiting_availability_response`, `awaiting_personal_info_action`, and `awaiting_professional_info_action` states are still live business or orchestration states
- Moved `awaiting_personal_info_action` and `awaiting_professional_info_action` into `routes/maintenance/info`
- Moved `awaiting_deletion_confirmation` into `routes/maintenance/deletion`
- Consolidated review entry and limited-menu handling under `routes/review`

## In progress
- Determining which remaining maintenance branches should move next
- Classifying what can be removed immediately versus what must stay until maintenance is split
- Review inventory by file has been documented
- Evaluating whether more compatibility wrappers can be retired without breaking live runtime paths
- Cleaning up the remaining legacy aliases in router/state checkpoints only after verifying live readers/writers are gone
- Confirmed the remaining service aliases were safe to retire once traffic and live sessions were no longer a concern
- Evaluating whether the remaining maintenance aliases should be renamed in the router-facing view/state layer
- Reviewing whether the last `awaiting_*` states in the profile-view router should remain legacy onboarding bridges or be renamed in a future pass
- Keeping the profile-view router bridges until onboarding and maintenance stop sharing the same edit path
- Leaving the shared router branches in place until the business-flow states themselves are split or renamed intentionally
- Using the ownership matrix as the next source of truth for deciding which router branches still need to move
- Using the migration-priority document to decide the next branch to extract from the shared router
- Preparing the shared router split starting with availability response and the remaining maintenance submenu branches
- Availability response is now delegated out of `flows/router.py`
- Availability has dedicated route and processor boundaries for the pending-response session state
- Onboarding now has a dedicated route boundary for entry, consent, and confirmation

## Pending
- Split the rest of maintenance/menu responsibilities into `routes/maintenance` and `services/maintenance`
- Update imports and tests gradually
- Retire compatibility facades after the new context consumers are fully switched

## Risks
- Shared router still coordinates too many branches
- Some states are persisted in Redis and Supabase simultaneously
- Legacy routes may still reference review or onboarding behavior
- A hard move without facades could break imports or runtime behavior

## Notes
- `models`, `config`, and `infrastructure` are not being removed
- The migration is intentionally gradual
- Review is the first context because it is the clearest boundary between registration and operations
