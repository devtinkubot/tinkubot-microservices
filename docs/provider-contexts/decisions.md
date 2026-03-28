# Provider Context Split Decisions

## Decision 1: Use bounded contexts
We will organize the provider code by bounded contexts:

- `onboarding`
- `review`
- `maintenance`
- `shared`

### Why
This makes the provider journey easier to understand and prevents menu behavior from contaminating onboarding.

## Decision 2: Start with review
The first migration step will be `review`.

### Why
`review` is the cleanest boundary between the registration journey and the operational journey. It also owns the silence policy and the approval transition.

## Decision 3: Keep technical layers
We will keep:

- `models`
- `config`
- `infrastructure`

### Why
These are support layers, not business journeys. They should remain available while the bounded contexts evolve.

## Decision 4: Migrate gradually
We will not duplicate the whole service at once.

### Why
The codebase must remain deployable while the migration happens. We prefer extraction, delegation, and compatibility facades over a big-bang rewrite.

## Decision 5: Keep review policy separate from menu logic
Review will own:

- pending review state
- repeated message handling
- silence after repeated insistence
- approval release

Maintenance will own:

- menu
- edits
- post-approval operations

### Why
These are different business behaviors and should not live in the same branch of the router.

## Decision 6: Treat most "flags" as domain state
Values like `pending_verification`, `approved_basic`, and `profile_pending_review` are backend
business state or compatibility labels, not feature toggles. The frontend contract should only
expose `pending`, `approved`, and `rejected`.

### Why
Removing them would break the meaning of the workflow. They should remain, but be owned by the correct bounded context.

## Decision 7: Retire wrappers only after consumers move
Compatibility facades, aliases, and bridge modules can remain during migration, but they must be removed once all imports and runtime paths point to the new contexts.

### Why
This keeps the container deployable while still preventing permanent duplication.

## Decision 8: Review is a bridge-first migration
The first review migration step will keep onboarding transitions intact, then extract the review policy and response ownership into the new context.

### Why
This avoids breaking the handoff from onboarding while still removing review decision-making from the shared router.

## Decision 9: Keep facades during the cutover
`services/sesion_proveedor.py` and the legacy verification constructor remain as compatibility facades while consumers move to `services/review` and `routes/review`.

### Why
This keeps existing tests and runtime imports stable while the new boundary is adopted incrementally.

## Decision 10: Menu-limited review belongs to maintenance
The `pending_verification` branch that opened a limited menu was extracted into
`routes/maintenance` and `services/maintenance`. The frontend no longer consumes it as a status.

### Why
Review should only own the approval state and silence policy. Menu presentation and post-approval navigation belong to maintenance.

## Decision 10b: Review owns the limited-menu decision entry
The initial review entrypoint now lives behind `routes/review`, and it is the one that decides whether a provider in review gets the limited menu handoff or the pure review response.

### Why
This keeps the review decision in one place while still delegating the actual menu rendering to maintenance.

## Decision 11: Registered menu routing belongs to maintenance
The `awaiting_menu_option` entry path is a shared orchestration gate: registered providers are routed into maintenance or review, while the shared router uses it to reopen onboarding consent only when Supabase says the provider is not yet registered.

### Why
This keeps the shared router focused on orchestration while maintenance owns the post-registration interaction model, and onboarding stays limited to the alta journey.

## Decision 11b: Maintenance should not resurrect onboarding
`routes/maintenance` must not redirect unregistered providers back into onboarding. If a provider is already registered in Supabase, the shared dispatcher should restore the operational context instead of letting maintenance reopen registration.

### Why
This preserves the new boundary split: onboarding owns alta only, and maintenance only handles registered-provider operations.

## Decision 11c: The maintenance menu is registered-only
`manejar_estado_menu` now handles only registered-provider menu choices. The registration start path belongs to onboarding and should not live inside the maintenance menu handler.

### Why
This removes the last menu-layer bridge into alta from the maintenance stack and keeps the operational menu focused on post-registration behavior.

## Decision 12: Social and view states belong to maintenance handlers
`awaiting_social_*` and `viewing_*` states were moved behind `routes/maintenance/handlers`.

### Why
These are post-registration interactions and should not remain in the shared router.

## Decision 13: Onboarding services are append-only
The onboarding services flow is limited to capture, confirmation to add another service, and the handoff to social media. Any service editing or correction flow belongs to maintenance, not onboarding.

### Why
This keeps onboarding focused on the minimum viable path to registration and avoids duplicating correction menus inside the initial provider journey.

## Decision 14: Retire wrappers only when no consumers remain
We can delete a wrapper or alias once a repo-wide search shows no live imports or runtime paths depend on it.

### Why
This lets us remove dead compatibility layers without breaking production, while leaving domain state aliases alone until their runtime migration is complete.

## Decision 15: `awaiting_service_add` is retired
The `awaiting_service_add` alias was removed from the runtime compatibility maps once the new `maintenance_service_add` path was fully wired.

### Why
The code no longer needed this alias as a live entry point. Keeping it around only increased ambiguity between onboarding and maintenance.

## Decision 16: Retire the last service aliases
`awaiting_service_action` and `awaiting_service_add_confirmation` were removed once the runtime no longer needed legacy service-state compatibility.

### Why
The service journey now writes and reads `maintenance_*` states directly, so the remaining aliases were only delaying cleanup.

## Decision 17: Remove legacy maintenance service aliases from the maintenance router
The maintenance services router no longer accepts legacy `awaiting_*` service aliases; it only routes the current maintenance vocabulary.

### Why
The new service flow already speaks `maintenance_*`, and the compatibility bridge was no longer needed on the maintenance edge.

## Decision 18: Normalize maintenance profile and social routes toward `maintenance_*`
The profile and social maintenance handlers now normalize state names into `maintenance_*` internally, and the social-network updater recognizes the modern maintenance state names for Facebook and Instagram edits.

### Why
This keeps the maintenance boundary readable and explicit while still tolerating older inputs from existing router paths during the migration.

## Decision 19: Keep onboarding bridges only where the flow is still genuinely shared
`gestor_vistas_perfil.py` now emits `maintenance_*` states for maintenance-only transitions, but keeps `awaiting_*` names where the same code path still serves onboarding or legacy shared flows.

### Why
This lets us keep maintenance clean without forcing an accidental rename of onboarding states that are still part of the active registration journey.

## Decision 20: Treat remaining profile-view `awaiting_*` names as shared-flow bridges
The remaining `awaiting_*` names in `gestor_vistas_perfil.py` are intentionally preserved because onboarding and maintenance still share the same edit path in that router.

### Why
Removing them now would either reintroduce duplicated branching or force a premature split of a shared interaction path that still serves both journeys.

## Decision 21: Keep shared router business states in place until they are intentionally renamed
Router-level states like `awaiting_availability_response` remain in the shared router because they are active business/orchestration states, not dead compatibility wrappers.

### Why
These states still participate in live flow control and session resumption. Moving them just to reduce `awaiting_*` usage would be a cosmetic change with real regression risk.

## Decision 22: Use the ownership matrix as the migration compass
We will use the ownership matrix to decide whether a state or branch belongs to onboarding, review, maintenance, or shared orchestration before making the next move.

### Why
This keeps the migration aligned with business ownership instead of letting folder structure or naming style drive the refactor by itself.

## Decision 23: Follow the migration-priority order
The next changes will follow the priority order established during the provider-context split: review first, maintenance second, onboarding third, shared orchestration cleanup last.

### Why
This keeps the work focused on the highest-value boundaries first and reduces the chance of splitting a bridge before its owner is ready.

## Decision 24: Move availability response handling behind its own route boundary
The `awaiting_availability_response` state is now delegated to `routes/availability` instead of being handled inline in the shared router.

### Why
This reduces the shared router surface without changing the meaning of the state, and it gives availability a clear place to evolve independently from onboarding and maintenance.

## Decision 25: Keep availability session state separate from availability Redis processing
The session-facing `awaiting_availability_response` router state is separate from the Redis-backed availability processing logic in `services/availability/processor.py`.

### Why
The state machine for the chat session and the business logic for incoming availability responses are related but not the same concern. Keeping them split makes each boundary easier to reason about and test.

## Decision 26: Treat availability as its own provider context
Availability is now treated as a fourth provider context alongside onboarding, review, and maintenance.

### Why
The provider-facing wait state is not part of onboarding, review, or maintenance semantics. It is a client-originated interaction with its own ownership boundary, so it should evolve independently on its own path.

## Decision 27: Treat deletion confirmation as maintenance-owned menu behavior
The `awaiting_deletion_confirmation` state belongs to `maintenance` and is handled behind `routes/maintenance/deletion.py`.

### Why
The deletion confirmation is a menu action for a registered provider, not a shared orchestration concern. Moving it behind the maintenance boundary keeps the shared router focused on true cross-cutting states.

## Decision 28: Treat personal and professional info actions as maintenance-owned submenu behavior
The `awaiting_personal_info_action` and `awaiting_professional_info_action` states belong to `maintenance` and are handled behind `routes/maintenance/info.py`.

### Why
These are submenu coordinators for registered providers. They are part of maintenance navigation, not shared orchestration, so they should live behind a maintenance-specific boundary.

## Decision 29: Retire the legacy availability compatibility shim
`services/disponibilidad_interceptacion.py` has been removed now that `services/availability/processor.py` is the canonical availability processor boundary.

### Why
Keeping the shim after the processor boundary was in place only preserved a redundant import path. Removing it makes the availability context fully explicit and avoids having two files that claim the same responsibility.

## Decision 30: Give onboarding its own route boundary
The onboarding entry, consent, and confirmation flow now lives behind `routes/onboarding`.

### Why
This keeps the alta journey isolated from post-registration menus and makes it easier to move side effects to the worker without changing the user-facing flow.

## Decision 31: Persist catalog suggestions in the review table
When a service is understandable but does not close confidently against the operational catalog, the suggestion is stored in `provider_service_catalog_reviews` instead of inventing more columns in `provider_services`.

### Why
`provider_services` stays canonical for the provider profile, while `provider_service_catalog_reviews` acts as the review inbox for admin and governance. This keeps operational data and review data separate, and avoids making the service table harder to query.

### Why
Onboarding is a full context, not a fallback branch of the shared router. Moving it behind its own route boundary makes the shared router thinner and keeps registration logic owned by the onboarding context itself.

## Decision 31: Keep Redis as a shared infrastructure service
Redis will remain a single shared container for cache, session state, and read model storage. If async workers are introduced later, they should reuse the same Redis deployment unless a new operational need appears.

### Why
The current runtime already shares one Redis across `ai-clientes`, `ai-proveedores`, and `ai-search`. Reusing that infrastructure avoids unnecessary operational duplication and keeps the new async layer consistent with the existing topology.

## Decision 32: Introduce async workers only if the repo needs them
If we add background workers later, onboarding is still the safest first use case for durable async processing. The repo does not currently include a BullMQ worker implementation.

### Why
Onboarding is the safest first use case for durable async processing. Starting with one worker keeps the rollout controlled while still validating the queue, idempotency, and Redis-backed propagation pattern.

## Decision 33: Treat the final runtime shape as a deployment detail
The repo does not currently prescribe a worker container count. If async processing is introduced later, the deployment shape should be decided with the implementation and not assumed in advance.

## Decision 34: Treat `runtime` as a conceptual boundary
We will document `runtime` as the set of production layers that execute the service, but we will not force a physical `runtime/` folder if the current top-level package layout is already stable.

### Why
The current import graph and deployment shape already work with `config`, `models`, `flows`, `routes`, `services`, `templates`, `infrastructure`, `utils`, `tools`, and `tests` as separate concerns. A folder move would add churn without improving ownership.

## Decision 35: Onboarding is alta-only
Onboarding only owns the new-provider journey. If Supabase says the provider already exists, the shared router must restore the canonical operational context instead of sending the user back into onboarding.

### Why
Redis can drift out of date, but onboarding should not be used to rescue registered providers. The shared dispatcher should use the persisted profile as truth and route to the appropriate operational boundary.

## Decision 36: Normalize on each onboarding step and keep final persistence focused on state
Each onboarding step must normalize the data it receives before persisting anything for that step. The final stage must not re-interpret identity; it should only finalize provider state.

### Rules
- Consent only advances on the explicit interactive button `continue_provider_onboarding`.
- Free-text answers are ignored and the consent prompt is reissued.
- There is no operational reject button in consent.
- Consent is the first step that may persist `real_phone` automatically, and only when the observed `phone` is a usable numeric JID like `...@s.whatsapp.net`.
- If there is no usable numeric JID, `real_phone` is requested explicitly after consent.
- `@lid` and `user_id`/BSUID are continuity identities, not human phone numbers.
- The closing of onboarding should only adjust provider state fields such as `status`, `has_consent`, and `onboarding_step`.

### Why
This keeps identity rules consistent across steps, prevents late-stage inference drift, and makes the onboarding contract easier to follow for anyone who takes over the project.

## Decision 37: Surface stalled onboarding in the admin dashboard with age-based visual alerts and a strong reset
The admin dashboard should visually flag providers that remain in onboarding for too long based on `created_at`, not on chat activity. The operational view applies to all onboarding states, uses a yellow-orange alert after 48 hours, a red alert after 72 hours, and keeps the signal as a visual cue on the contact/card rather than as provider-facing text. The dashboard may expose a `reset` action for administrators, but that action is a strong operational reset: it clears the active onboarding data while preserving audit history so the provider can register again from scratch.

### Why
This turns the dashboard into an operational triage tool instead of a passive list, helps administrators prioritize stalled onboarding cases quickly, and preserves a clean audit trail when a provider needs a fresh registration attempt.

## Decision 38: Treat onboarding as the first durable worker boundary
If the repo grows a durable worker layer, the first phase should center on onboarding and its operational cleanup/reset paths. Supabase remains the source of truth, Redis remains the operational layer for jobs, locks, and projections, and the worker scope should stay narrow until onboarding proves the pattern. Governanza, monetization, and batch review stay out of phase 1.

### Why
Onboarding is the base of the provider journey and the clearest place to validate durable async processing without turning the first worker pass into a platform rewrite. Keeping the first boundary small reduces risk while still solving the real operational pain.

## Decision 39: Keep service normalization async and inside the provider domain
The onboarding services step captures raw service text, publishes it to Redis, and lets the worker call an internal `ai-proveedores` endpoint for normalization before persisting to Supabase.

### Why
This keeps the user-facing flow fast, reuses the existing normalization logic inside `ai-proveedores`, and avoids a second Redis hop that would add latency and failure modes without adding value.

## Decision 40: Retire `experience_years` from the live provider contract
`experience_range` is now the canonical experience field for providers. The numeric `experience_years` field is considered legacy and should not be used as a source of truth in runtime flows, views, or new persistence paths.

### Why
The business and UX already operate on experience ranges, so keeping the integer field alive only duplicated state and created ambiguity about which value should drive the flow.

## Decision 41: Do not keep a legacy onboarding DLQ stream
The historical `provider_onboarding_events_dlq` stream was removed from the runtime model and should not be treated as a canonical queue or storage contract.

### Why
The DLQ was only an operational escape hatch for a previous failure mode. Once the worker flow was corrected, the legacy DLQ no longer added value and would only confuse the active topology.

## Decision 42: Allow best-effort catalog suggestions only in review records
When a service is ambiguous or lacks a confident domain/category match, `ai-proveedores`
may make a second Structured Outputs pass with `json_schema` and `strict: true` to
produce a best-effort suggestion for `provider_service_catalog_reviews`. The canonical
`provider_services` row must remain unchanged until human approval.

### Why
This gives admins a useful starting point without asking the provider for more details
and without turning uncertain classifications into source-of-truth data.

## Decision log updates
This file should be updated whenever a migration decision changes or a new boundary is introduced.
