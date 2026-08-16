
## MarketingOS AI v0.8B — Usage Analytics

Date: 2026-08-07

Status: PASS

Implemented:
- Workspace Usage Analytics API
- Generation count aggregation
- Completed / failed / pending / draft statistics
- Input / output / total token statistics
- Historical AI estimated cost aggregation
- Subscription plan information
- Monthly Credit usage information
- Remaining Credit calculation
- Tenant-isolated Usage API

Validated:
- Backend v0.8.0 healthy
- Usage API authenticated access works
- Cross-tenant access returns HTTP 403
- OpenAPI contains Usage route
- Existing historical generation cost remains preserved
- Legacy pre-credit generation is not backfilled into Credit Ledger

Important compatibility note:
- FastAPI 0.141.1 uses lazy _IncludedRouter objects.
- app.routes direct APIRoute inspection is not a valid route-registration test.
- OpenAPI and HTTP routing are the authoritative verification methods.

Baseline historical usage at validation:
- Total generations: 8
- Completed: 3
- Failed: 2
- Pending: 1
- Draft: 2
- Input tokens: 1195
- Output tokens: 754
- Total tokens: 1949
- Historical estimated AI cost: USD 0.005719
- Current plan: Pro
- Plan price: TWD 1490
- Monthly Credits: 1000

## MarketingOS AI v0.8C — Profit Analytics

Date: 2026-08-07

Status: PASS

Implemented:
- Plan revenue analytics
- AI cost conversion USD -> TWD
- Projected gross profit
- Projected gross margin
- Average completed generation cost
- Cost per cycle credit metric
- Decimal-safe financial calculations

Accounting semantics:
- plan_revenue_twd is configured subscription price, not confirmed payment.
- projected_gross_profit_twd is projected margin before non-AI operating expenses.
- Historical AI cost is sourced from content_generations.
- Credit Ledger remains an event/accounting audit trail.

Current temporary FX assumption:
- USD/TWD = 32.00
- This will later be replaced by configurable or live FX data.

## MarketingOS AI v0.9A — Frontend Authentication

Date: 2026-08-07

Status: PASS

Implemented:
- Next.js login page
- Dashboard shell
- Server-side Backend API helper
- Login proxy
- Authenticated /me proxy
- Logout proxy
- HttpOnly access token cookie
- HttpOnly refresh token cookie
- Root redirect to login
- Responsive dashboard layout

Security:
- Access token is not stored in localStorage.
- Refresh token is not stored in localStorage.
- Auth tokens are stored in HttpOnly cookies.
- Browser communicates with Next.js auth proxy instead of exposing Backend bearer tokens.

Build fix:
- Initial frontend build failed because tsconfig.json did not define the @/* path alias.
- Added baseUrl "." and paths "@/*": ["./*"].
- Frontend production build then passed.

Validated:
- /login returns HTTP 200
- unauthenticated /api/auth/me returns HTTP 401
- authenticated frontend login works
- authenticated /api/auth/me returns HTTP 200
- dashboard returns HTTP 200
- logout clears frontend authentication cookies
- logout causes /api/auth/me to return HTTP 401

## MarketingOS AI v0.9B — Real Dashboard

Date: 2026-08-07

Status: PASS

Implemented:
- Authenticated frontend Usage API proxy
- Real Workspace data loading
- Real Subscription plan card
- Real AI Credit balance
- Monthly Credit progress
- AI generation statistics
- Token usage statistics
- Historical AI cost display
- Projected profit display
- Projected gross margin display
- Subscription cycle display
- Responsive SaaS Dashboard
- Correct /api/auth/me response mapping

Security:
- Browser still does not receive backend bearer tokens directly.
- Usage requests pass through the Next.js server proxy.
- Proxy reads authentication from HttpOnly cookies.
- Unauthenticated Usage proxy access returns HTTP 401.

Current Dashboard baseline:
- Plan: Pro
- Plan price: TWD 1490
- Credits: 1000
- Historical generations: 8
- Total tokens: 1949
- Historical AI cost: USD 0.005719
- Projected gross profit: TWD 1489.82

Accounting note:
- Projected profit is not confirmed payment revenue.
- Operating expenses are not yet included.

## MarketingOS AI v0.9C — AI Content Generator UI

Date: 2026-08-07

Status: PASS

Implemented:
- Brand list frontend proxy
- AI generation frontend proxy
- AI Content Generator page
- Brand selector
- Platform selector
- Topic input
- Marketing objective input
- Generated content output
- Token usage metadata
- AI cost metadata
- Copy-to-clipboard action
- Dashboard AI Creator navigation
- Responsive creator interface

Security:
- Browser does not receive Backend bearer token.
- AI generation requests use Next.js HttpOnly-cookie proxy.
- Unauthenticated Brand and Generation proxy requests return HTTP 401.
- Backend workspace and brand tenant isolation remains authoritative.

Billing:
- Successful AI content generation deducts 1 Credit.
- Hard Limit remains enforced before OpenAI invocation.
- AI provider failures remain covered by the existing Credit refund flow.

Validation:
- Frontend production build passed.
- Brand proxy returned HTTP 200.
- Real AI generation returned HTTP 201.
- Generated content status was completed.
- Credit balance decreased exactly by 1.
- Create page returned HTTP 200.
- Unauthenticated generation returned HTTP 401.

Test generation:
- Platform: Threads
- Model: gpt-5.6-luna
- Input tokens: 396
- Output tokens: 144
- Estimated API cost: USD 0.001260

Issue fixed during validation:
- Initial validation script had an invalid Python line break at `generation = data["generation"]`.
- The AI request itself had already succeeded, so generation was not repeated and no duplicate Credit was charged.

## MarketingOS AI v0.10B — Brand Management UI

Date: 2026-08-07

Status: PASS

Implemented:
- Brand Management page
- Brand list UI
- New Brand form
- Full Brand Brain editor
- Brand GET frontend proxy
- Brand POST frontend proxy
- Brand PATCH frontend proxy
- Brand DELETE frontend proxy
- Responsive Brand Management layout

Brand Brain fields:
- Name
- Industry
- Website
- Description
- Tone
- Target audience
- Brand voice
- Value proposition
- Products and services
- Keywords
- Forbidden words
- Default CTA
- Language
- Country
- Brand guidelines

Security validation:
- Unauthenticated Brand detail returns HTTP 401.
- Tenant B cannot GET Tenant A Brand.
- Tenant B cannot PATCH Tenant A Brand.
- Cross-tenant modification is rejected with HTTP 403.

CRUD validation:
- Temporary Brand CREATE returned HTTP 201.
- Brand GET returned HTTP 200.
- Brand PATCH returned HTTP 200.
- Brand appeared in Brand List.
- Temporary Brand DELETE returned HTTP 204.
- Deleted Brand subsequently returned HTTP 404.
- Existing Alpha Coffee Brand was preserved.
- Existing Content History was preserved.

Safety note:
- Alpha Coffee was not used for DELETE validation.
- DELETE testing used a dedicated temporary Brand only.

## MarketingOS AI v0.10C — Content History UI

Date: 2026-08-07

Status: PASS

Implemented:
- Content History frontend proxy
- Content History page
- Brand filter
- Platform filter
- Status filter
- Completed / failed / pending / draft status labels
- Token metadata
- AI model metadata
- AI cost metadata
- Expandable generated content
- Copy generated content action
- Responsive Content History layout
- Dashboard / Brand / Creator / History navigation

Data handling:
- Completed content is shown as publishable generated output.
- Failed tasks show provider/system error state.
- Draft tasks are clearly identified as drafts.
- Pending historical tasks are displayed separately and are not treated as completed content.

Security:
- Content History requests use the existing HttpOnly-cookie frontend proxy pattern.
- Unauthenticated History API requests return HTTP 401.
- Backend tenant isolation remains authoritative.

Validation:
- Frontend production build passed.
- Content History proxy returned HTTP 200.
- Existing Alpha Coffee history remained intact.
- History page returned HTTP 200.
- Unauthenticated Content History proxy returned HTTP 401.

## MarketingOS AI v0.11B — SocialAccount Core

Date: 2026-08-07

Status: PASS

Implemented:
- social_accounts database table
- Workspace-scoped social accounts
- Optional Brand association
- Generic SocialPlatform enum
- Generic SocialAccountStatus enum
- Platform account ID
- Account name
- Username
- Profile URL
- OAuth scope metadata
- Token expiry metadata
- Last sync timestamp
- Error metadata
- Active/inactive state
- Workspace / platform / platform_account_id uniqueness protection
- Workspace and Brand indexes
- Alembic migration persisted on host

Supported platform identifiers:
- instagram
- facebook
- threads
- linkedin
- x

Supported account states:
- pending
- connected
- expired
- revoked
- error

Database validation:
- Alembic upgraded from 32af27b96513 to db5694b707bd
- social_accounts table created successfully
- workspace_id -> workspaces.id foreign key validated
- brand_id -> brands.id foreign key validated
- workspace_id index validated
- brand_id index validated
- unique workspace/platform/platform_account_id index validated

Security:
- No plaintext access_token column
- No plaintext refresh_token column
- No plaintext generic token column
- OAuth credential encryption intentionally deferred to v0.11C

Alembic rule:
- Revision files generated inside disposable Docker containers are not considered complete.
- Alembic revision generation must persist the migration file on the host.
- Migration order must be determined by revision/down_revision/head, not file modification time.

## MarketingOS AI v0.11C — OAuth Token Encryption

Date: 2026-08-07

Status: PASS

Implemented:

- Added cryptography dependency for OAuth credential encryption.
- Added OAUTH_TOKEN_ENCRYPTION_KEY configuration.
- Added Fernet-based OAuth encryption service.
- Added encrypted access token storage field.
- Added encrypted refresh token storage field.
- Added Alembic migration for encrypted OAuth credential fields.
- OAuth credential encryption key is stored outside source code.
- Token objects use safe representations that do not expose credential values.

Database security:

- No plaintext access_token column exists.
- No plaintext refresh_token column exists.
- OAuth token ciphertext fields are stored in social_accounts.
- Encryption / decryption database self-test passed.
- Alembic current revision matches head.

API security:

- OAuth token plaintext is never included in SocialAccount responses.
- OAuth token ciphertext is never included in SocialAccount responses.
- OAuth encryption key is never returned through API responses.

Validation:

- Fernet key validation passed.
- OAuth credential encryption round-trip passed.
- Database encrypted-token storage test passed.
- Existing SocialAccount model remained operational.

## MarketingOS AI v0.11D — Social Account API Core

Date: 2026-08-07

Status: PASS

Implemented:

- Workspace SocialAccount list API.
- SocialAccount detail API.
- SocialAccount update API.
- SocialAccount delete API.
- Workspace membership validation.
- Role-based write protection.
- Cross-workspace Brand validation.

Authorization:

- Workspace members may read SocialAccount records.
- owner / admin / manager / editor may update supported metadata.
- owner / admin may delete SocialAccount records.
- Cross-workspace access is rejected.

PATCH allowlist:

- brand_id
- account_name
- username
- profile_url
- is_active

Security:

- OAuth access tokens cannot be modified through SocialAccount PATCH.
- OAuth refresh tokens cannot be modified through SocialAccount PATCH.
- OAuth ciphertext fields cannot be modified through SocialAccount PATCH.
- OAuth credential fields are not returned by API responses.
- Cross-tenant Brand assignment is rejected.

Validation:

- HTTP tenant isolation tests passed.
- Secret-field isolation tests passed.
- Temporary SocialAccount test records were cleaned up.

## MarketingOS AI v0.11E — Meta OAuth State V2

Date: 2026-08-08

Status: PASS

Background:

- Initial OAuth state implementation used a signed Base64URL payload.
- Internal create / verify / replay tests passed.
- Public HTTPS callback transport tests passed.
- During a real Facebook OAuth round-trip, the state received by the callback did not match the state originally issued.
- One observed callback contained an unrelated 7-character state value while the issued v1 state was approximately 230 characters.
- The exact external cause of that altered state was not treated as established.

Architecture change:

- Replaced route usage of payload-bearing v1 state with opaque server-side OAuth State V2.
- V2 state uses secrets.token_urlsafe(32).
- State is approximately 43 URL-safe characters.
- State contains no client-readable workspace, provider, user, timestamp, or signature payload.
- State payload is stored server-side in Redis.
- Redis payload binds:
  - workspace_id
  - provider
  - initiating user_id
  - issued_at
- State TTL is 600 seconds.
- Redis SET NX prevents duplicate registration.
- Redis GETDEL provides atomic one-time consumption.
- Replay attempts are rejected.
- Provider mismatch is rejected.
- Expired and invalid state values are rejected.

Security validation:

- V2 state entropy / URL-safe format gate passed.
- Workspace binding gate passed.
- Provider binding gate passed.
- Initiating-user binding gate passed.
- Atomic consume gate passed.
- Replay rejection gate passed.
- Redis consumed-key removal gate passed.
- Public HTTPS callback accepted a valid V2 state.
- Reusing the same V2 state returned an already-used / expired error.
- Legacy v1 service regression tests remained passing during migration.
- Production OAuth routes now use V2 state.

Post-debug cleanup:

- Temporary OAuth state fingerprints were removed.
- Temporary OAuth state shape diagnostics were removed.
- No OAuth state value is intentionally written to application logs.

## MarketingOS AI v0.11F — Meta OAuth Identity Verification

Date: 2026-08-08

Status: PASS

Implemented:

- Added explicit httpx dependency for outbound Meta API calls.
- Added Meta OAuth service.
- Meta authorization endpoint integration.
- Server-side authorization-code exchange.
- Meta /me identity verification.
- Meta user access token is sent to Graph API using Authorization: Bearer.
- Meta token exchange uses POST request data rather than placing credentials in the request URL.
- OAuth callback consumes and verifies V2 state before credential exchange.
- Callback returns a generic identity verification result and does not expose OAuth credentials.

Current OAuth scope:

- public_profile

Successful real-world flow:

- MarketingOS generated a new OAuth State V2 value.
- Browser was redirected to Facebook Login.
- User completed Facebook authorization.
- Facebook redirected to the configured MarketingOS callback.
- Callback received the same V2 state that was issued.
- V2 state validation passed.
- Authorization code exchange passed.
- Meta /me identity verification passed.
- Final callback response returned status identity_verified.

OAuth security hardening:

- Nginx OAuth callback access logging is disabled.
- Uvicorn access logging is disabled to avoid OAuth query-string credential leakage.
- OAuth callback code and state are not intentionally written to logs.
- Meta App Secret is not logged.
- Meta access tokens are not logged.
- Meta provider error message bodies are not logged.
- Safe Meta failure diagnostics retain only provider error type / code / subcode.
- Temporary OAuth test start route was removed after successful real-world validation.
- Official OAuth callback route remains configured.

Nginx callback:

- /_marketingos/oauth/meta/callback
- Proxies only to the MarketingOS backend OAuth callback.
- Existing CBEMS routing remains separate and operational.

Final deployment validation:

- Backend production image rebuilt successfully.
- Backend health returned healthy.
- OAuth State V2 deployed-source gate passed.
- Temporary state diagnostics absence gate passed.
- Meta error-message leakage gate passed.
- Safe Meta type / code / subcode diagnostics gate passed.
- Temporary /_marketingos/oauth/meta/start-test route confirmed removed.
- Official OAuth callback confirmed present.

Current boundary:

- Meta user identity verification is complete.
- Facebook Page assets are NOT yet persisted as connected SocialAccount records.
- Page discovery, Page selection, Page credential encryption, and SocialAccount creation are the next development phase.

## MarketingOS AI v0.12A — Meta Page Discovery

Date: 2026-08-08

Status: PASS

Implemented:

- Added Facebook Page discovery after successful Meta OAuth identity verification.
- Added MetaManagedPage representation.
- Page access tokens use safe object representations and are not exposed through repr output.
- Added /me/accounts discovery using the authenticated Meta access token.
- Meta Graph API version remains explicitly pinned by the backend.
- Page discovery requests use Authorization: Bearer transport.
- Page discovery does not place OAuth access tokens in request URLs.
- Pagination remains constrained to the fixed /me/accounts endpoint.
- Arbitrary provider paging URLs are not followed.
- Page discovery pagination is capped to prevent unbounded traversal.
- Callback response exposes only safe Page metadata:
  - Page ID
  - Page name
  - Page tasks
- Page access tokens are not included in callback responses.

Security validation:

- MetaManagedPage token repr isolation passed.
- Bearer-token transport gate passed.
- Access-token URL-query isolation passed.
- Fixed-endpoint pagination gate passed.
- Provider error-message leakage gate passed.
- Callback Page-token response isolation passed.
- Mock multi-page discovery passed.
- Mock pagination passed.

Real-world findings:

- The original Meta app rejected pages_show_list as an invalid scope for the existing login configuration.
- This was treated as an app/use-case configuration issue rather than bypassing the permission requirement.
- Development moved to a Meta Business app configured for Facebook Page management.
- Initial real Page discovery with Facebook Login for Business returned page_count=0.
- Business Settings inspection confirmed that the selected Business Portfolio did not yet contain a Facebook Page.
- The owned Facebook Page was subsequently added to the selected Business Portfolio.
- A fresh OAuth State V2 authorization was issued.
- Real Page discovery then returned page_count=1.
- The authorized Page exposed Page-management tasks including:
  - ADVERTISE
  - ANALYZE
  - CREATE_CONTENT
  - MESSAGING
  - MODERATE
  - MANAGE

Boundary at completion:

- Real Facebook Page discovery is operational.
- Page access tokens are still kept out of API responses.
- Persistent encrypted SocialAccount storage is implemented in v0.12C.

## MarketingOS AI v0.12B — Facebook Login for Business

Date: 2026-08-08

Status: PASS

Architecture change:

- Migrated the real Meta connection flow to Facebook Login for Business.
- Created a dedicated Meta Business app/use case for Facebook Page management.
- Added META_BUSINESS_LOGIN_CONFIG_ID configuration.
- Business Login authorization URLs now use:
  - client_id
  - redirect_uri
  - response_type=code
  - override_default_response_type=true
  - config_id
  - OAuth State V2
- Legacy scope query parameters are intentionally not included in the Business Login authorization URL.
- Meta App Secret is never included in the authorization URL.

Business Login configuration:

- Business Login configuration ID:
  - 1557497166058318
- Token type selected for the Business Login configuration:
  - System User Access Token
- Configured token lifetime:
  - 60 days
- Configured asset type:
  - Facebook Pages
- Initial configured Page permission:
  - pages_show_list
- The Business Portfolio selected during real authorization was the portfolio used for MarketingOS Page assets.

Real-world validation:

- MarketingOS generated a fresh opaque OAuth State V2 value.
- Facebook Login for Business opened successfully.
- Business Portfolio selection completed successfully.
- Facebook Page asset selection completed successfully after the owned Page had been added to the Business Portfolio.
- Meta redirected back to the official MarketingOS callback.
- OAuth State V2 validation passed.
- Meta authorization-code exchange passed.
- Meta identity verification passed.
- Meta Page discovery passed.
- Final discovery returned exactly one authorized Page.

Security:

- OAuth authorization URL contains no Meta App Secret.
- Legacy scope parameter is absent from Business Login authorization URLs.
- OAuth State V2 remains opaque and one-time-use.
- Temporary OAuth start routes use access_log off.
- Temporary OAuth start routes are removed after each real validation.
- Official callback access logging remains disabled.
- Uvicorn access logging remains disabled for OAuth query-string protection.
- OAuth callback code, state values, access tokens, and provider secrets are not intentionally logged.

Operational finding:

- page_count=0 during the first Business Login test was explained by the selected Business Portfolio having no Page asset assigned.
- After the owned Page was added to that Business Portfolio, the same architecture returned page_count=1.
- No alternative or unsafe token transport was required.

Current production boundary:

- Business Login remains under development/test configuration.
- Production customer rollout still requires the appropriate Meta production access, review, verification, and permission approvals.
- Facebook publishing permission is not assumed from pages_show_list alone.
- Publishing permissions and Publishing Safety are separate subsequent phases.

## MarketingOS AI v0.12C — Meta SocialAccount Persistence

Date: 2026-08-08

Status: PASS

Implemented:

- Added dedicated SocialAccount connection persistence service.
- Added idempotent Facebook Page SocialAccount upsert.
- Existing SocialAccount is matched by:
  - workspace_id
  - platform=facebook
  - platform_account_id
- Reconnecting the same Page updates the existing record instead of creating a duplicate.
- Existing brand_id and user-managed metadata are preserved during reconnect.
- Facebook Page status is persisted as connected.
- Connected Page remains active.
- Page account name and profile metadata are refreshed on reconnect.
- Page sync timestamp is recorded.
- Page access token is encrypted with the existing Fernet OAuth token cipher before ORM persistence.
- Only access_token_ciphertext is written to the SocialAccount model.
- No plaintext token database column was introduced.
- Persistence service uses db.flush() and leaves commit ownership to the callback transaction.

Callback authorization hardening:

- OAuth State V2 initiating user_id is re-read at callback time.
- The initiating User must still exist.
- The initiating User must still be active.
- Workspace write permission is re-evaluated at callback time.
- An OAuth state issued earlier does not preserve authorization if the user's access changes before callback.
- Inactive users are rejected before Meta token exchange.
- Users whose Workspace write permission has been revoked are rejected before Meta token exchange.

Transaction behavior:

- Successful Page persistence commits through the callback transaction.
- Persistence failures trigger rollback.
- Persistence failures return a generic HTTP error.
- Provider tokens, ciphertext values, SQL parameters, and provider response bodies are not included in persistence error logs.

Zero-Page behavior:

- A completed OAuth flow with zero authorized Facebook Pages is not treated as a connected SocialAccount.
- Zero-Page callbacks are rejected before persistence.

Real PostgreSQL security validation:

- Fake Page token insertion passed.
- Fernet ciphertext storage passed.
- Ciphertext decrypt round-trip passed.
- Same Page reconnect reused the same database row.
- Duplicate SocialAccount prevention passed.
- Encrypted token rotation passed.
- Plaintext Page token was absent from the raw PostgreSQL row.
- Plaintext token columns were confirmed absent.
- SocialAccount API serialization contained neither plaintext token nor ciphertext.
- Temporary security-test rows were successfully removed.

Callback integration mock validation:

- Inactive initiating user rejection passed.
- Inactive user was blocked before Meta exchange.
- Revoked Workspace write permission rejection passed.
- Revoked user was blocked before Meta exchange.
- Authorized callback persistence path passed.
- Callback transaction commit passed.
- Connected response metadata passed.
- Callback token response isolation passed.
- Persistence failure rollback passed.
- Persistence error secret isolation passed.
- Zero-Page persistence blocking passed.

Deployment validation:

- Backend production image rebuilt successfully.
- Backend health returned HTTP 200.
- Deployed callback initiating-user re-check passed.
- Deployed Workspace write re-check passed.
- Deployed encrypted persistence path passed.
- Deployed commit / rollback paths passed.
- Deployed token-logging gate passed.
- Backend container runs as a non-root user.
- PostgreSQL production connectivity passed.
- Pre-real-OAuth security-test Page row count was zero.
- Pre-real-OAuth real Page row count was zero.

Real Meta persistence validation:

- Facebook Login for Business completed successfully.
- OAuth State V2 completed successfully.
- Exactly one Facebook Page was authorized.
- Callback returned:
  - status=pages_connected
  - page_count=1
- The connected Facebook Page ID is:
  - 119402794592265
- The final persisted Page account name currently reported by Meta/PostgreSQL is:
  - 小八寶花店
- Exactly one SocialAccount row exists for that Page.
- platform=facebook
- status=connected
- is_active=true
- Workspace ownership matched the initiating Workspace.
- Encrypted Page access token is present.
- The encrypted credential was verified by presence/length only during the final production check; its value was not printed.
- token_expires_at remains unset because Page-token expiration semantics have not yet been independently verified.
- No user-token expiration value is copied into the Page-token expiration field without evidence.
- Final callback response contains safe Page metadata only.
- Temporary /_marketingos/oauth/meta/start-test route was removed.
- Official /_marketingos/oauth/meta/callback route remains present.

Final status:

- Real Meta Business Login: PASS
- Real Facebook Page discovery: PASS
- Fernet Page-token persistence: PASS
- SocialAccount idempotency: PASS
- Callback-time authorization revalidation: PASS
- Tenant / Workspace isolation: PASS
- Token response isolation: PASS
- Real connected SocialAccount persistence: PASS

Next phase:

- Add and validate the Meta permissions required for Facebook Page publishing.
- Do not assume pages_show_list grants publishing rights.
- Add Publishing Safety controls before enabling real automated posting.
- Continue to keep OAuth credentials encrypted at rest and excluded from frontend/API responses.

## v0.13A-v0.13B — Publishing Safety + Publication API Core

### Scope

Implemented the first secure publishing foundation for
MarketingOS AI.

This phase intentionally does **not** provide a real publishing
HTTP endpoint and does **not** call the Meta Graph publishing API.

The supported flow at this stage is:

`ContentGeneration.completed`
→ `Publication draft`
→ explicit approval
→ future publishing phase.

### v0.13A — Publication data model

Added:

- `backend/app/models/publication.py`
- Alembic revision:
  `b731c8e24d91_create_publications.py`

Publication states:

- `draft`
- `approved`
- `publishing`
- `published`
- `failed`
- `cancelled`

Core fields include:

- workspace / brand / content-generation references
- social-account reference
- creator and approver audit references
- target platform/account snapshot
- exact `content_snapshot`
- SHA-256 `content_hash`
- workspace-scoped `idempotency_key`
- approval timestamp
- publish-attempt count
- provider post metadata
- sanitized failure information
- publish/create/update timestamps

The publication table contains no OAuth token,
refresh-token, secret, or ciphertext fields.

### Database safety

Migration applied successfully:

`2e7e665d1446 -> b731c8e24d91`

Verified against PostgreSQL:

- publication enum exists
- publication indexes exist
- workspace-scoped idempotency UNIQUE constraint exists
- duplicate key inside the same workspace is rejected
- the same key in different workspaces is allowed
- no OAuth-secret columns exist
- security-test rows are removed after testing

A PostgreSQL pre-migration backup was created before
applying the migration.

### Publishing Safety state machine

Added:

`backend/app/services/publication_workflow.py`

Implemented:

- completed-content requirement
- connected/active SocialAccount requirement
- encrypted-credential presence requirement
- content-platform/account-platform match
- brand-target consistency validation
- exact publication content snapshot
- SHA-256 snapshot-integrity validation
- explicit approval audit
- row locking with `SELECT ... FOR UPDATE`
- approval-before-publishing requirement
- publish-attempt counter
- published-state terminal protection
- provider result state transition helpers
- sanitized failure-state helper

Transaction ownership remains with callers.

The workflow service performs no Meta network request and
does not decrypt OAuth credentials.

### State-machine database verification

Real PostgreSQL testing verified:

- draft creation
- idempotent draft reuse
- conflicting idempotency rejection
- unapproved publishing rejection
- explicit approval
- approval audit persistence
- approval idempotency
- approved → publishing
- publish-attempt increment
- publishing → published
- published resend rejection
- tampered draft approval rejection
- tampered approved publication rejection
- workspace isolation
- complete security-test cleanup

### v0.13B — Publication API Core

Added:

- `backend/app/schemas/publication.py`
- `backend/app/api/publications.py`

Registered Publication router in the FastAPI application.

Exposed HTTP routes:

- `GET /api/workspaces/{workspace_id}/publications`
- `POST /api/workspaces/{workspace_id}/publications/drafts`
- `GET /api/workspaces/{workspace_id}/publications/{publication_id}`
- `POST /api/workspaces/{workspace_id}/publications/{publication_id}/approve`

No `/publish` HTTP route exists in this phase.

### Publication API authorization

Read operations require workspace membership.

Write / approval operations use the existing workspace
write-role policy:

- owner
- admin
- manager
- editor

Viewer remains read-only.

Real HTTP/ASGI testing verified:

- unauthenticated requests rejected
- owner draft creation
- owner approval
- viewer list/detail access
- viewer draft creation rejected
- viewer approval rejected
- cross-workspace list access rejected
- cross-workspace detail access rejected
- cross-workspace approval rejected
- idempotent request reuse
- idempotency conflict returns HTTP 409
- approval idempotency
- Publication responses expose no OAuth secrets
- `/publish` returns HTTP 404
- all temporary users/workspaces/content/accounts/publications
  are removed after testing

### Deployment verification

Backend image rebuilt and deployed successfully.

Production-container gates:

- `/api/health` → HTTP 200
- PostgreSQL → healthy
- Redis → healthy
- backend runtime UID → 100 (`appuser`)
- backend is non-root
- Alembic → `b731c8e24d91 (head)`
- deployed Publication OpenAPI allowlist → PASS
- deployed OpenAPI secret isolation → PASS
- deployed approval gate → PASS
- deployed snapshot-integrity gate → PASS
- deployed row-lock gate → PASS
- deployed OAuth-token decryption absent → PASS
- deployed Meta publishing network call absent → PASS
- live `/publish` route → HTTP 404

### Security boundary after v0.13B

The deployed system can:

- create Publication drafts
- list Publications
- read Publication details
- explicitly approve Publications

The deployed HTTP API cannot yet:

- transition a Publication into publishing
- decrypt a Facebook Page token for publishing
- call the Meta Graph publishing endpoint
- publish a real Facebook post

Real provider publishing remains intentionally disabled
until the Meta Publishing Adapter and its mock/dry-run
security gates are completed.

### Result

`v0.13A Publishing Safety Core: PASS`

`v0.13B Publication API Core: PASS`

`v0.13B deployed backend security gate: PASS`

Next planned phase:

`v0.13C — Meta Publishing Adapter (mock/dry-run first)`

## v0.13C — Meta Publishing Adapter + Safe Dry-run

### Scope

Implemented the first Meta publishing-provider boundary and
a safe approved-Publication dry-run workflow.

This phase intentionally does **not** publish a real
Facebook Page post.

The deployed system still has no real `/publish` HTTP route.

### Meta Publishing Adapter foundation

Added:

- `backend/app/services/meta_publishing.py`

Implemented:

- Meta publishing exception hierarchy
- immutable Facebook Page text-post plan
- metadata-only dry-run model
- provider result model
- injectable publishing transport protocol
- SHA-256 content integrity metadata
- safe Meta error allowlist
- provider-result validation
- arbitrary transport-exception sanitization

The approved message is hidden from dataclass `repr`.

The dry-run object contains only metadata and never contains:

- message content
- Page access token
- OAuth ciphertext
- refresh token
- client secret

The adapter foundation contains no concrete HTTP client and
performs no Meta Graph network request.

### Safe Meta error handling

Meta-style provider errors are reduced to an explicit
operational allowlist:

- error type
- error code
- error subcode

Provider message text, trace ids, request ids, tokens and
`error_data` are intentionally excluded.

Mock testing verified that arbitrary transport exception
text is not propagated to the caller.

### Mock / dry-run adapter verification

Verified:

- Page-id validation
- content validation
- exact content hash generation
- content-length metadata
- message `repr` isolation
- metadata-only dry-run output
- fake-token isolation
- injectable mock transport
- provider-result validation
- transport-exception sanitization
- missing credential rejection
- no OAuth decryption
- no Meta HTTP request

Result:

`v0.13C Mock / Dry-run Adapter Gate: PASS`

### Approved Publication dry-run orchestration

Added:

- `backend/app/services/publication_dry_run.py`

The orchestration layer re-reads the Publication and current
SocialAccount from PostgreSQL before producing a dry-run.

Required conditions:

- Publication exists in the requested workspace
- Publication status is `approved`
- approval audit is complete
- approved content snapshot hash remains valid
- Publication has no provider post id
- SocialAccount still exists in the same workspace
- SocialAccount remains `connected`
- SocialAccount remains active
- account platform remains Facebook
- Publication platform remains Facebook
- provider Page id is still present
- live provider Page id still matches the approved target
- associated brand still matches when applicable
- encrypted credential is still present

The encrypted credential is checked for presence only.

Dry-run orchestration never decrypts it.

The resulting dry-run content hash must also match the
approved Publication snapshot hash.

### PostgreSQL dry-run safety verification

Real PostgreSQL testing verified:

- unapproved Publication dry-run rejected
- approved Publication dry-run accepted
- Workspace isolation
- revoked SocialAccount rejected
- missing credential rejected
- target-account drift rejected
- tampered approved content rejected
- dry-run response excludes content and credentials
- all temporary test data removed

Result:

`v0.13C PostgreSQL Dry-run Orchestration Gate: PASS`

### Dry-run HTTP API

Added:

`POST /api/workspaces/{workspace_id}/publications/{publication_id}/dry-run`

Dry-run is treated as a publishing-preparation action and
therefore requires the existing workspace write-role policy.

Allowed roles:

- owner
- admin
- manager
- editor

Viewer remains read-only and cannot initiate dry-run.

The HTTP response is restricted to exactly:

- `provider`
- `platform`
- `action`
- `target_account_id`
- `endpoint_path`
- `content_hash`
- `content_length`

The response intentionally does not expose the complete
Publication content.

### Real HTTP authorization verification

Real HTTP/ASGI + PostgreSQL testing verified:

- owner Publication draft → HTTP 201
- unapproved dry-run → HTTP 409
- viewer dry-run → HTTP 403
- cross-workspace dry-run → HTTP 403
- owner approval → HTTP 200
- approved dry-run → HTTP 200
- response field allowlist
- content/token/ciphertext isolation
- dry-run does not mutate Publication state
- publish-attempt count remains zero
- provider post id remains null
- published timestamp remains null
- target-account drift → HTTP 409
- revoked account → HTTP 422
- real `/publish` route → HTTP 404
- complete temporary-data cleanup

Result:

`v0.13C Real HTTP Dry-run Authorization Gate: PASS`

### HTTP 422 compatibility cleanup

Replaced deprecated:

`HTTP_422_UNPROCESSABLE_ENTITY`

with:

`HTTP_422_UNPROCESSABLE_CONTENT`

The HTTP status remains 422.

FastAPI/OpenAPI import was verified with Python
DeprecationWarning promoted to an error.

Result:

`v0.13C 422 compatibility fix: PASS`

### Production deployment verification

Backend image rebuilt and deployed successfully.

Production-container verification:

- backend container became healthy
- `/api/health` → HTTP 200
- PostgreSQL → healthy
- Redis → healthy
- backend runtime UID → 100 (`appuser`)
- backend remains non-root
- Alembic → `b731c8e24d91 (head)`
- Publication OpenAPI route allowlist → PASS
- dry-run response allowlist → PASS
- OpenAPI secret isolation → PASS
- deprecated 422 constant absent → PASS
- approved-only dry-run requirement → PASS
- snapshot-integrity recheck → PASS
- current-account validation → PASS
- credential presence-only validation → PASS
- OAuth token decryption absent → PASS
- concrete Meta HTTP transport absent → PASS
- unauthenticated `/dry-run` → HTTP 401
- real `/publish` → HTTP 404

Deployed Publication HTTP surface:

- `GET /api/workspaces/{workspace_id}/publications`
- `POST /api/workspaces/{workspace_id}/publications/drafts`
- `GET /api/workspaces/{workspace_id}/publications/{publication_id}`
- `POST /api/workspaces/{workspace_id}/publications/{publication_id}/approve`
- `POST /api/workspaces/{workspace_id}/publications/{publication_id}/dry-run`

No real publishing route exists.

### Security boundary after v0.13C

The deployed system can now safely:

`completed content`
→ `Publication draft`
→ `explicit approval`
→ `dry-run metadata`

It still cannot:

- start a real provider publishing attempt through HTTP
- decrypt the real Facebook Page access token for publishing
- execute a real Meta Graph publishing request
- automatically retry an ambiguous provider request
- create a real Facebook Page post

These restrictions are intentional.

### Remaining publishing prerequisites

Before enabling real publishing, the implementation still
requires:

- verification of current Meta publishing permissions
- concrete Meta HTTP transport
- narrowly scoped OAuth-decryption boundary
- final publish-time account revalidation
- unknown-outcome / duplicate-post protection
- safe provider-response parsing
- controlled mock transport integration testing
- explicit real-post test procedure
- final `/publish` authorization and security gate

### Version metadata note

At this deployment the health endpoint still reports:

`"version": "0.8.1"`

This is the existing application version metadata and is
not the v0.13C development milestone identifier.

Release/version metadata should be aligned separately.

### Result

`v0.13C Meta Publishing Adapter foundation: PASS`

`v0.13C Approved Publication Dry-run Orchestration: PASS`

`v0.13C Dry-run HTTP API: PASS`

`v0.13C deployed backend security gate: PASS`

Next planned phase:

`v0.13D — Meta Publishing Permission + Execution Safety`


---

## MarketingOS AI v0.13D — Meta Publishing Permission + Execution Safety

Date: 2026-08-09

Status: PASS

### Meta publishing permission verification

Added:

`backend/app/services/meta_permissions.py`

Required Facebook Page publishing permissions are explicitly defined as:

- `pages_show_list`
- `pages_read_engagement`
- `pages_manage_posts`

Permission readiness is no longer inferred from:

- Business Login configuration names
- requested permissions
- Facebook Page task lists
- stale `SocialAccount.scopes` metadata

A dedicated Meta Page-token introspection layer now verifies the actual token grant.

Verification checks include:

- token validity
- configured Meta App match
- token type is `PAGE`
- required permissions are granted
- explicit granular Page target mismatch detection
- canonical normalized scope output

Provider error handling remains restricted to safe operational metadata:

- error type
- error code
- error subcode

Provider message text, trace ids, raw error payloads, tokens, ciphertext and App secrets are not propagated.

MockTransport validation passed for:

- valid PAGE token
- all required publishing permissions
- missing `pages_manage_posts`
- explicit target mismatch
- configured App mismatch
- provider error sanitization
- network exception sanitization
- token/result representation isolation

Result:

`v0.13D Meta permission verifier mock gate: PASS`

### Live Meta permission verification

A controlled read-only live permission check was performed against the already-connected Facebook Page credential.

The stored Page access token was decrypted only in process memory.

Live `/debug_token` verification confirmed:

- token valid: YES
- configured Meta App match: YES
- token type: PAGE
- `pages_show_list`: GRANTED
- `pages_read_engagement`: GRANTED
- `pages_manage_posts`: GRANTED
- explicit Page target mismatch: NO
- publishing permission readiness: PASS

No `/feed` request was performed.

No Facebook post was created.

No Publication state was changed.

No token or ciphertext was printed.

Result:

`v0.13D Live Meta publishing permission gate: PASS`

### Verified scope persistence

Removed the legacy static persistence value:

`META_PAGE_SCOPES = "pages_show_list"`

`SocialAccount.scopes` is no longer populated from a hardcoded permission string.

OAuth callback flow now performs:

`OAuth code exchange`
→ `Meta identity verification`
→ `Facebook Page discovery`
→ `actual Page-token permission introspection`
→ `canonical verified scopes`
→ `encrypted SocialAccount persistence`
→ `transaction commit`

`upsert_meta_page_connections()` now requires verified scope metadata for each Page.

A Page without verified publishing readiness is rejected before SocialAccount persistence.

The existing connected Page was updated only after a fresh live permission verification.

Persisted canonical scope metadata:

`pages_manage_posts,pages_read_engagement,pages_show_list,public_profile`

During this metadata update:

- Page token was not changed
- encrypted credential was not changed
- OAuth reconnect was not performed
- `/feed` was not called
- no post was created
- Publication state was not changed

Result:

`v0.13D Verified Meta scope persistence: PASS`

### Meta HTTP publishing transport

Added a concrete Meta Graph HTTP publishing transport while keeping execution dependency-injected.

The transport:

- builds the approved Page `/feed` target
- sends the Page credential in the Authorization header
- does not place the publishing credential in the publishing URL/query string
- disables redirects
- uses a finite timeout
- accepts only a valid provider post id as confirmed success
- sanitizes provider errors
- never returns raw provider error payloads

No production HTTP publish route invokes this transport.

MockTransport validation passed for:

- confirmed success
- safe Meta 4xx rejection
- Meta 5xx response
- timeout
- invalid JSON success response
- missing provider post id
- arbitrary transport exception isolation

### Ambiguous provider outcome safety

Introduced:

`MetaPublishingOutcomeUnknown`

A provider timeout or Meta 5xx response is not treated as a safely retryable failure.

Once a provider request may have been dispatched, the system does not assume that the Page post was not created.

This prevents automatic duplicate posting after an ambiguous provider outcome.

Result:

`v0.13D Meta HTTP transport mock gate: PASS`

### Publication execution boundary

Added:

`backend/app/services/publication_executor.py`

Publishing execution now uses a deliberately narrow sequence:

`approved`
→ durable `publishing` claim
→ PostgreSQL commit
→ live Publication/SocialAccount revalidation
→ late credential decryption
→ injected provider transport
→ confirmed finalization

Before provider execution the executor revalidates:

- Publication workspace ownership
- `publishing` state
- approval audit fields
- immutable content snapshot hash
- absence of an existing provider post id
- Facebook platform
- exact approved target account
- current SocialAccount existence
- SocialAccount workspace
- connected status
- active status
- Facebook platform match
- Page id match
- brand consistency
- encrypted credential presence

The plaintext Page credential is decrypted at one narrow execution boundary immediately before the provider transport call.

It is not persisted or returned.

### Durable PostgreSQL claim

`begin_publication_attempt()` transitions:

`approved`
→ `publishing`

and increments:

`publish_attempts`

before external provider execution.

The execution service commits that claim before decrypting the credential or initiating the provider request.

A real PostgreSQL transaction test using an independent database session verified that before MockTransport provider execution:

- status was already `publishing`
- `publish_attempts` was already `1`
- provider post id was still null

This protects against transaction rollback reopening an approved Publication after a provider request may already have succeeded.

Result:

`v0.13D Durable Publication claim: PASS`

### Confirmed provider success

A confirmed provider response containing a valid provider post id transitions:

`publishing`
→ `published`

The provider post id is persisted.

The success path was validated with MockTransport and real PostgreSQL state.

### Definite provider rejection

A definite sanitized provider rejection transitions:

`publishing`
→ `failed`

Provider tokens and raw provider messages are not stored in `last_error`.

### Unknown outcome / reconciliation state

A timeout, Meta 5xx, or uncertain post-finalization condition does not transition back to `approved`.

It also does not become an ordinary automatically retryable failure.

The Publication intentionally remains:

`publishing`

with a safe reconciliation marker.

A second execution attempt is blocked by the existing Publication state machine before another provider request can occur.

Real PostgreSQL validation confirmed:

- timeout path remained `publishing`
- reconciliation marker persisted
- `publish_attempts` remained `1`
- second execution attempt was rejected
- second provider request did not occur

Result:

`v0.13D Unknown-outcome duplicate-post protection: PASS`

### Executor security validation

Mock-only executor tests passed for:

- durable claim before provider call
- confirmed success → published
- definite rejection → failed
- provider error isolation
- timeout → reconciliation state
- ambiguous outcome remains non-retryable
- post-claim validation failure blocks network
- decrypt failure blocks network
- decrypt exception isolation

Real PostgreSQL / MockTransport transaction tests passed.

Temporary Publication test rows were removed after validation.

No real Meta publishing call occurred during executor validation.

Result:

`v0.13D Publication executor safety gate: PASS`

### Production deployment

Backend production image was rebuilt and deployed.

Production regression verified:

- backend health: healthy
- `/api/health`: HTTP 200
- OAuth callback permission verifier deployed
- legacy `META_PAGE_SCOPES` hardcode absent
- verified-scope persistence deployed
- required Meta publishing permission set deployed
- Meta permission HTTP transport import available
- Meta publishing HTTP transport import available
- unknown-outcome exception available
- Publication executor available
- backend runtime UID: 100
- backend remains non-root
- Alembic: `b731c8e24d91 (head)`
- PostgreSQL verified scopes persisted correctly

Deployed Publication HTTP surface remains:

- `GET /api/workspaces/{workspace_id}/publications`
- `POST /api/workspaces/{workspace_id}/publications/drafts`
- `GET /api/workspaces/{workspace_id}/publications/{publication_id}`
- `POST /api/workspaces/{workspace_id}/publications/{publication_id}/approve`
- `POST /api/workspaces/{workspace_id}/publications/{publication_id}/dry-run`

The real:

`POST .../publications/{publication_id}/publish`

route does not exist and returns HTTP 404.

Result:

`v0.13D Production deployment regression: PASS`

### Security boundary after v0.13D

The backend now has the internal primitives required for controlled Facebook Page publishing:

`verified Page permission`
→ `approved Publication`
→ `durable execution claim`
→ `late credential decrypt`
→ `safe Meta transport`
→ `confirmed success / definite failure / reconciliation`

However, real publishing remains intentionally disabled through the public HTTP API.

No real Facebook Page post was created during v0.13D.

Before the first controlled real post, the remaining work includes:

- final `/publish` authorization and HTTP security design
- explicit controlled real-post test procedure
- explicit operator reconciliation procedure for ambiguous outcomes
- protection against accidental repeated operator action
- final real-post confirmation immediately before execution
- post-publication reconciliation/verification procedure
- appropriate Meta production access, review and verification before customer production rollout

### Version metadata note

The health endpoint continues to report:

`"version": "0.8.1"`

This is existing application version metadata and is separate from the v0.13D engineering milestone.

Version metadata alignment remains a separate cleanup task.

### v0.13D final result

`Meta publishing permission verification: PASS`

`Verified scope persistence: PASS`

`Meta HTTP transport safety: PASS`

`Publication executor safety: PASS`

`Unknown-outcome duplicate-post protection: PASS`

`Real PostgreSQL transaction safety: PASS`

`Production deployment regression: PASS`

`Real /publish route: ABSENT`

`Real Facebook post created during v0.13D: NO`

### Next publishing boundary

Do not enable real Facebook publishing until the controlled real-publish authorization, reconciliation and explicit-confirmation gates are designed and validated.


### v0.13D Ambiguous HTTP 2xx outcome correction

A final publishing-safety review identified an important
provider-outcome classification edge case.

Previously, Meta Graph HTTP responses with an HTTP 2xx status
but without a trustworthy provider post id were classified as
a definite provider failure.

This was corrected because an HTTP 2xx response means the
provider may already have created the Page post even when the
response body is malformed or incomplete.

The following cases are now classified as:

`MetaPublishingOutcomeUnknown`

- HTTP 2xx with an invalid / non-JSON response body
- HTTP 2xx with no valid provider post id

The executor therefore follows the existing ambiguous-outcome
path:

`provider request may have succeeded`
→ `Publication remains publishing`
→ `manual reconciliation required`
→ `automatic retry blocked`

A normal definite Meta 4xx rejection remains:

`MetaPublishingProviderError`
→ `Publication failed`

Regression verification passed for:

- HTTP 200 invalid JSON → outcome unknown
- HTTP 200 missing post id → outcome unknown
- HTTP 400 → definite provider rejection
- wrapper exception isolation
- executor ambiguous-outcome handling
- duplicate-post retry protection

The corrected backend image was rebuilt and deployed.

Production verification confirmed:

- backend healthy
- deployed ambiguous-2xx behavior correct
- backend remains non-root
- Alembic remains at `b731c8e24d91 (head)`
- verified Meta scopes unchanged
- real `/publish` route remains absent
- no real Meta publishing request was made
- no Facebook post was created

Result:

`v0.13D Ambiguous HTTP 2xx correctness gate: PASS`


## MarketingOS AI v0.13E-A — Controlled Publish Foundation

Date: 2026-08-09

Status: PASS

v0.13E-A establishes the authorization, confirmation and
durable operator-audit foundation required before a real
publishing HTTP endpoint may exist.

### Publishing authorization boundary

Real external publishing now has an independent Workspace
permission policy:

- owner: allowed
- admin: allowed
- manager: allowed
- editor: blocked
- viewer: blocked

Normal Workspace write permissions remain unchanged.

### One-time publishing confirmation

A dedicated Redis-backed publishing confirmation service was
added.

The confirmation value is:

- cryptographically random
- opaque
- short-lived
- one-time consumable
- never used as a Publication database field

TTL:

`180 seconds`

Server-side confirmation state is bound to:

`user_id`
→ `workspace_id`
→ `publication_id`
→ `content_hash`

Redis registration uses atomic create-if-absent behavior and
consumption uses atomic `GETDEL`.

A binding mismatch fails closed: the confirmation is consumed
before validation and cannot later be replayed with corrected
parameters.

Both mock and real Redis tests passed.

No confirmation value was printed or persisted in the
Publication table.

### Durable publishing operator audit

Migration:

`a13e0a91c7f2`

added:

- `publish_triggered_by_user_id`
- `publish_triggered_at`

The trigger-user field references `users.id` with
`ON DELETE SET NULL`.

The publishing operator audit is written inside the same
locked transaction as:

`approved`
→ `publishing`

and:

`publish_attempts: 0`
→ `publish_attempts: 1`

`begin_publication_attempt()` continues to use
`SELECT ... FOR UPDATE`.

v0.13E-A additionally hard-blocks any Publication that already
has a publishing attempt from silently starting another
provider execution.

### Real PostgreSQL transaction verification

A real PostgreSQL transaction gate passed.

Before claim commit, an independent database session still saw:

- status `approved`
- publish attempts `0`
- no trigger user
- no trigger timestamp

After claim commit, an independent session saw atomically:

- status `publishing`
- publish attempts `1`
- correct triggering operator
- trigger timestamp present

A second claim was rejected.

An explicitly constructed approved Publication with a prior
publish attempt was also rejected without mutation.

All temporary PostgreSQL Publications were removed after the
test.

### Production deployment

The v0.13E-A backend was rebuilt and deployed after migration.

Production verification confirmed:

- backend healthy
- backend remains non-root
- Alembic revision `a13e0a91c7f2`
- publish role policy deployed
- 180-second confirmation policy deployed
- real Redis one-time confirmation behavior passed
- Publication trigger audit model/schema deployed
- executor trigger-user propagation deployed
- existing five Publication HTTP routes unchanged
- real `/publish` route remains absent

### External side-effect boundary

v0.13E-A does not enable Facebook publishing.

During this phase:

- no `/publish` HTTP endpoint existed
- no OAuth credential was decrypted by the production gate
- no Meta `/feed` request was made
- no Facebook Page post was created

Result:

`v0.13E-A Controlled Publish Foundation: PASS`

### Next boundary

Before real publishing can be enabled, the HTTP confirmation
issuance/consumption workflow and reconciliation/operator
procedures must be designed and validated.

The first real Facebook Page post remains disabled until all
remaining controlled-publish gates pass and immediate operator
confirmation is explicitly provided.


## MarketingOS AI v0.13E-B — Publish Confirmation HTTP Gate

Date: 2026-08-09

Status: PASS

v0.13E-B introduces the first controlled publishing HTTP
boundary without enabling provider-side publishing.

### HTTP route

Added:

`POST /api/workspaces/{workspace_id}/publications/{publication_id}/publish-confirmation`

The endpoint requires the dedicated external publishing
authorization policy:

- owner: allowed
- admin: allowed
- manager: allowed
- editor: blocked
- viewer: blocked

### Issuance sequence

The HTTP endpoint performs:

authenticated user
→ publish authorization
→ Publication publishing preflight
→ immutable snapshot/hash verification
→ current SocialAccount/target verification
→ credential-presence check only
→ one-time Redis confirmation issuance

The confirmation has a 180-second TTL and remains bound to:

- user
- Workspace
- Publication
- approved content hash

### Real production verification

A real temporary approved Publication was created against an
existing connected Facebook SocialAccount.

A real authenticated HTTP request to the production
publish-confirmation endpoint succeeded.

The returned confirmation value was never printed.

Real Redis verification confirmed:

- key creation
- expected TTL
- correct binding
- atomic consumption
- replay rejection
- cleanup

The HTTP confirmation endpoint did not:

- change Publication status
- increment publish_attempts
- write trigger-user audit
- write trigger timestamp
- write provider_post_id

The temporary Publication and Redis confirmation were removed
after verification.

### External side-effect boundary

v0.13E-B still does not expose a real publishing endpoint.

`POST .../publish`

remains absent from source, OpenAPI and production HTTP.

During this phase:

- no OAuth credential was decrypted
- no provider executor was invoked
- no Meta `/feed` request was made
- no Facebook Page post was created

Result:

`v0.13E-B Publish Confirmation HTTP Gate: PASS`

### Next boundary

The next phase must design and validate controlled
confirmation consumption plus provider execution.

An ambiguous provider result must continue to remain
`publishing` and require reconciliation.

No real Facebook Page post may be created until the complete
controlled-publish execution gate has passed and immediate
operator confirmation is explicitly provided.


## MarketingOS AI v0.13E-C — Controlled Execution Foundation

Date: 2026-08-09

Status: PASS

v0.13E-C establishes the controlled provider-execution
orchestration foundation while keeping the real publishing
HTTP endpoint disabled.

### Real-publish kill switch

A server-side setting was added:

`real_publish_enabled`

Default:

`false`

The controlled execution orchestration fails closed before
Publication preflight, Redis confirmation consumption,
credential decryption, durable execution claim or provider
execution when the kill switch is disabled.

Production deployment verified the setting remains OFF.

### Confirmation key hardening

Publication confirmation values remain opaque 256-bit bearer
values returned only to the authorized operator.

Redis keyspace no longer contains the raw bearer value.

Redis lookup keys are now:

`publication_publish_confirmation:SHA256(confirmation)`

The server-side payload remains bound to:

- user
- Workspace
- Publication
- content hash
- issuance time

Atomic GETDEL and replay protection remain unchanged.

### Controlled execution orchestration

The controlled orchestration sequence is:

kill switch
→ current approved Publication preflight
→ exact content-hash comparison
→ atomic one-time confirmation consumption
→ durable Publication execution claim
→ late credential decryption
→ injected provider transport
→ durable outcome classification

The orchestration service accepts only an injected
`MetaPublishingTransport`.

It does not construct `MetaGraphHTTPTransport`.

No production application source currently constructs the
concrete Meta Graph transport.

### Real integration verification

A real integration gate passed using:

- real PostgreSQL
- real Redis
- real encrypted Facebook Page credential
- real credential decryption
- `httpx.MockTransport`

Three temporary approved Publications verified:

1. mock success
   → `published`

2. definite HTTP 400 rejection
   → `failed`

3. ambiguous timeout
   → remains `publishing`
   → manual reconciliation required

Each execution recorded:

- publish attempts = 1
- triggering operator
- trigger timestamp

Confirmation replay was rejected.

No automatic provider retry was introduced.

All temporary PostgreSQL and Redis test data was removed.

### Production verification

Production deployment confirmed:

- backend healthy
- backend non-root
- database revision remains `a13e0a91c7f2`
- real-publish kill switch OFF
- hashed confirmation Redis keys
- publish-confirmation HTTP remains operational
- exact six Publication HTTP routes remain
- real `/publish` route remains absent
- no concrete Meta transport constructor exists in
  production application source

### External side-effect boundary

During v0.13E-C:

- no real `/publish` HTTP route existed
- no Meta Graph publishing request was made
- no Facebook Page post was created

The real credential decrypt path was exercised only with an
injected mock HTTP transport.

Result:

`v0.13E-C Controlled Execution Foundation: PASS`

### Next boundary

The next phase may design the source-only `/publish` HTTP
execution gate.

Any such route must continue to require:

- authenticated operator
- dedicated publish permission
- exact approved content hash
- one-time confirmation
- server-side real-publish kill switch
- durable execution claim
- reconciliation-safe provider outcome handling

Production real publishing must remain disabled until the
source and production safety gates pass and an explicit
immediate operator decision is made for the first real
Facebook Page post.


## MarketingOS AI v0.13E-C Security Hardening — Confirmation No-Store

Date: 2026-08-09

Status: PASS

A post-deployment security review identified that the
`publish-confirmation` response returned an opaque one-time
bearer confirmation without explicit HTTP anti-cache headers.

The endpoint now returns:

- `Cache-Control: no-store`
- `Pragma: no-cache`
- `Expires: 0`

The earlier Redis hardening remains active. Redis lookup keys
use SHA-256 of the bearer confirmation rather than the raw
confirmation value.

The first C-only hotfix deployment attempt failed health
checks because the generated production-only source added a
`response: Response` parameter without importing FastAPI
`Response`. The generator incorrectly searched for the
substring `Response,`, which was already present inside
`PublicationConfirmationResponse,`.

The deployment automatically rolled back successfully.

The hotfix generator was corrected to validate the actual
FastAPI imported symbol. The exact patched source then passed:

- Python compilation
- application import
- ASGI health
- Uvicorn runtime
- production deployment health
- real publish-confirmation HTTP header verification

Production remained within the v0.13E-C safety boundary:

- Publication routes: 6
- real `/publish`: absent
- `real_publish_enabled`: false
- database revision unchanged
- backend non-root
- no Meta publishing request
- no Facebook post created

Host source retains the later source-only v0.13E-D-A
`/publish` work, but that route was not included in this
C-only production hotfix.

Result:

`v0.13E-C Confirmation No-Store Security Hardening: PASS`


## MarketingOS AI v0.13E-D-B — HTTP End-to-End Integration Gate

Date: 2026-08-09

Status: PASS

The source-only controlled `/publish` flow was exercised
end-to-end through the real FastAPI ASGI application.

The integration gate used:

- real JWT authentication
- real Workspace publish authorization
- real PostgreSQL Publication rows
- real Redis confirmation issuance
- atomic confirmation GETDEL
- SHA-256-derived Redis confirmation keys
- HTTP anti-cache protection on confirmation responses
- the real encrypted Facebook Page credential decrypt path
- injected `MetaGraphHTTPTransport`
- `httpx.MockTransport` as the provider boundary

Verified safety and execution behavior:

- kill switch blocks before transport construction
- kill switch causes no Redis consume, DB mutation or decrypt
- stale content hash returns HTTP 409 before confirmation consumption
- stale content hash causes no decrypt or provider request
- durable PostgreSQL `publishing` claim, attempt count and
  operator audit are committed before provider execution
- mock success returns HTTP 200 and persists `published`
- mock provider 400 returns HTTP 502 and persists `failed`
- provider error details are not exposed or persisted
- mock timeout returns HTTP 202 with reconciliation required
- unknown outcome remains `publishing`
- no automatic retry is introduced
- operator trigger audit is durable on every claimed attempt
- Page credential is decrypted only for actual provider execution
- Page token is not placed in the provider URL
- mocked provider receives Bearer authorization
- all three provider execution paths made exactly one mock call
- credential decrypt occurred exactly three times

A preliminary Step 3 compile command attempted to create
bytecode under the source bind mount and was denied because
the non-root backend user cannot write to that directory.
This was not a Python syntax failure. Recovery used an
in-memory `compile()` gate with bytecode writes disabled.

Production remained isolated throughout D-B:

- production Publication routes: 6
- production `/publish`: absent / HTTP 404
- production `real_publish_enabled`: false
- production confirmation anti-cache hardening remains active
- database revision: a13e0a91c7f2
- backend runs non-root
- temporary D-B Publication rows: 0
- no real Meta publishing request
- no Facebook post created

Result:

`v0.13E-D-B HTTP End-to-End Integration Gate: PASS`


## MarketingOS AI v0.13E-D-C — Disabled /publish Production Deployment

Date: 2026-08-09

Status: PASS

The previously source-only controlled Publication `/publish`
endpoint was deployed to production after completing the
v0.13E-D-B HTTP end-to-end integration gate.

Production now exposes seven Publication operations including:

`POST /api/workspaces/{workspace_id}/publications/{publication_id}/publish`

The execution kill switch remains disabled:

`real_publish_enabled = false`

The production default publish transport remains fail-closed
and does not construct `MetaGraphHTTPTransport`.

Production deployment verification included:

- exact pre-validated candidate image deployment
- backend health verification
- seven Publication routes
- `/publish` present as POST
- real publish execution kill switch OFF
- default provider transport fail-closed
- no concrete Meta transport construction in the deployed path
- confirmation response `Cache-Control: no-store`
- confirmation response `Pragma: no-cache`
- real authenticated HTTP confirmation issuance
- real authenticated `/publish` request returning HTTP 503
- disabled execution does not consume the confirmation
- disabled execution does not claim or mutate the Publication
- in-process bomb transport verifies kill switch executes
  before transport construction
- in-process bomb cipher verifies kill switch executes before
  OAuth Page credential decryption
- database revision remains a13e0a91c7f2
- backend continues to run non-root
- temporary D-C rows and Redis confirmations cleaned

No real Meta publishing transport was constructed or invoked,
and no Facebook post was created.

Result:

`v0.13E-D-C Disabled /publish Production Deployment: PASS`


## MarketingOS AI v0.13E-E-A — Real Provider Wiring Foundation

Date: 2026-08-09

Status: PASS

A second independent fail-closed control was added for the
production Meta publishing transport:

`meta_publish_transport_enabled = false`

The existing execution kill switch remains:

`real_publish_enabled = false`

The provider factory now constructs `MetaGraphHTTPTransport`
only when `meta_publish_transport_enabled` is explicitly true.
Otherwise it raises
`PublicationPublishTransportUnavailable`.

This creates a two-gate production model:

`real_publish_enabled AND meta_publish_transport_enabled`

The Publication HTTP endpoint continues to check
`real_publish_enabled` before requesting transport wiring.

The controlled execution layer independently checks the same
execution kill switch before Redis confirmation consumption or
Publication state mutation.

The executor continues to decrypt the Page credential only
after the durable PostgreSQL publishing claim commits.

Source verification confirmed:

- provider wiring defaults OFF
- real publishing defaults OFF
- disabled provider wiring fails closed
- enabled wiring constructs `MetaGraphHTTPTransport`
- transport construction itself performs no network request
- existing `/publish` HTTP safety regressions remain PASS
- no environment secret values were printed
- no OAuth credential was printed
- no real Meta request occurred
- no Facebook post was created

Production was not rebuilt or restarted during E-A.

Result:

`v0.13E-E-A Real Provider Wiring Foundation: PASS`


## MarketingOS AI v0.13E-E-B — Double-OFF Real Provider Wiring Deployment

Date: 2026-08-09

Status: PASS

The real Meta provider transport wiring foundation was
deployed to production.

Production now contains the concrete transport factory wiring
for `MetaGraphHTTPTransport`, but both independent execution
controls remain disabled:

`real_publish_enabled = false`

`meta_publish_transport_enabled = false`

Production verification confirmed:

- `/publish` remains present
- backend is healthy
- real publishing execution switch is OFF
- Meta provider wiring switch is OFF
- default provider factory fails closed
- exactly one concrete `MetaGraphHTTPTransport` constructor
  exists, inside `publication_publish_transport.py`
- API, orchestration and executor layers do not construct the
  concrete transport
- enabling only transport wiring constructs the HTTP transport
  without making a network request
- live double-OFF `/publish` returns HTTP 503
- disabled execution does not consume the confirmation
- disabled execution does not mutate the Publication
- a process-local test enabled only the first execution gate
  while leaving provider wiring OFF
- the independent provider gate returned HTTP 503 before
  concrete transport construction
- the independent provider gate returned before OAuth Page
  credential decryption
- the independent provider gate did not consume Redis
  confirmation state
- the independent provider gate did not claim or mutate the
  Publication
- all process-local overrides were restored
- database revision remains a13e0a91c7f2
- backend continues to run non-root
- temporary E-B data was cleaned

No OAuth credential value was printed.

No Meta publishing HTTP request was sent.

No Facebook post was created.

Result:

`v0.13E-E-B Double-OFF Real Provider Wiring Deployment: PASS`


## MarketingOS AI v0.13E-E-C Step 2 — Single-Post Activation Grant

Date: 2026-08-09

Status: PASS — source only

A third, publication-specific safety control was added in
source without changing production.

The activation grant is:

- opaque and randomly generated
- 256-bit
- stored server-side only
- represented in Redis keyspace only by SHA-256 digest
- registered with SET NX EX
- atomically consumed with GETDEL
- bound to workspace_id
- bound to publication_id
- bound to operator user_id
- bound to exact Publication content_hash
- short-lived with a 120-second TTL
- one-time and replay resistant

Activation authorization is deliberately narrower than
ordinary Publication publishing permission.

Current ordinary publish roles:

- owner
- admin
- manager

Current activation role:

- owner only

The activation authorization layer first invokes the existing
`require_workspace_publish` boundary and then applies the
owner-only activation restriction.

A new source-only endpoint was added:

`POST /api/workspaces/{workspace_id}/publications/{publication_id}/publish-activation`

The endpoint:

- authorizes before Publication discovery
- performs an approved Publication dry-run
- binds the grant to the exact current content hash
- returns HTTP 201 on successful issuance
- returns a generic HTTP 503 on activation backend failure
- applies Cache-Control: no-store
- applies Pragma: no-cache
- applies Expires: 0
- does not mutate Publication state
- does not decrypt OAuth credentials
- does not construct or invoke Meta transport

Step 2 intentionally does NOT yet consume the activation grant
inside `/publish`.

Production remains unchanged:

- Publication routes: 7
- `/publish`: present
- `/publish-activation`: absent
- `real_publish_enabled`: false
- `meta_publish_transport_enabled`: false
- database revision: a13e0a91c7f2
- backend non-root
- no real Redis activation state created
- no Meta request
- no Facebook post

Result:

`v0.13E-E-C Step 2 Single-Post Activation Grant: PASS`


## MarketingOS AI v0.13E-E-C Step 3B — Activation Publish Gate

Date: 2026-08-09

Status: PASS — source only

The single-publication activation grant is now wired into the
source `/publish` execution path.

`PublicationPublishRequest` now requires three security-bound
inputs:

- activation
- confirmation
- content_hash

Source execution ordering is:

publish authorization
→ real_publish_enabled
→ Meta provider transport factory
→ activation execution gate
→ existing controlled confirmation execution
→ durable PostgreSQL claim
→ credential decrypt
→ provider request

The activation execution gate independently rechecks both
global controls before consuming the activation bearer:

- real_publish_enabled
- meta_publish_transport_enabled

It then performs:

approved Publication dry-run
→ exact content hash comparison
→ atomic activation GETDEL

Only after activation succeeds may the existing controlled
execution layer consume the publication confirmation.

Activation failure maps to generic HTTP 409 and does not reach
the existing confirmation/executor path.

Step 3B intentionally did not run the older D-B real
PostgreSQL/Redis integration test because its five `/publish`
payloads still require migration to the new activation
contract. That migration and real integration gate are the
next step.

Production remains unchanged:

- Publication routes: 7
- `/publish`: present
- `/publish-activation`: absent
- real_publish_enabled: false
- meta_publish_transport_enabled: false
- database revision: a13e0a91c7f2
- no credential decrypt
- no real Meta request
- no Facebook post

Result:

`v0.13E-E-C Step 3B Activation Publish Gate: PASS`


## MarketingOS AI v0.13E-E-C Step 3C-B — Activated HTTP End-to-End Gate

Date: 2026-08-09

Status: PASS — source integration only

The existing real PostgreSQL/Redis Publication HTTP
integration gate was migrated to the single-publication
activation contract.

The integration operator selection was narrowed from:

- owner
- admin
- manager

to:

- owner only

The integration now issues, through the real source HTTP
routes:

1. publication confirmation
2. publication activation

Activation properties verified in the real Redis integration:

- owner-authorized issuance
- HTTP 201
- Cache-Control: no-store
- Pragma: no-cache
- Expires: 0
- exact Publication content_hash binding
- SHA-256 Redis key
- raw activation bearer absent from Redis keyspace
- one-time GETDEL consumption

Five `/publish` requests now carry:

- activation
- confirmation
- content_hash

Safety behavior verified:

- global execution disabled blocks before transport
- disabled execution leaves activation reusable
- stale content hash fails before activation consumption
- stale content hash leaves both activation and confirmation reusable
- successful publish consumes activation and confirmation
- definite provider rejection consumes activation and confirmation
- outcome-unknown consumes activation and confirmation
- outcome-unknown does not create an automatic retry path
- durable PostgreSQL publishing claim is committed before provider execution
- real encrypted Page credential decrypt path executes only after durable claim
- provider success maps to published
- provider rejection maps to failed
- provider timeout remains publishing / manual reconciliation

All provider behavior used `MetaGraphHTTPTransport` with an
explicit `httpx.MockTransport` injection.

No default real Meta network transport was used by the
integration.

Production remained unchanged:

- production Publication routes: 7
- production `/publish`: present
- production `/publish-activation`: absent
- `real_publish_enabled`: false
- `meta_publish_transport_enabled`: false
- database revision: a13e0a91c7f2
- backend remained healthy and non-root
- production backend was not rebuilt or restarted

Temporary PostgreSQL and Redis integration data was cleaned.

No OAuth credential value was printed.

No activation or confirmation bearer value was printed.

No real Meta publishing HTTP request was sent.

No Facebook post was created.

Result:

`v0.13E-E-C Step 3C-B Activated HTTP End-to-End Gate: PASS`


## MarketingOS AI v0.13E-E-C — Single-Post Activation Production Deployment

Date: 2026-08-09

Status: PASS — deployed double-OFF

Production now includes the single-publication activation
safety layer.

Production Publication HTTP surface:

- Publication routes: 8
- `/publish`: present
- `/publish-confirmation`: present
- `/publish-activation`: present

`PublicationPublishRequest` requires:

- activation
- confirmation
- content_hash

Activation safety:

- activation issuance is owner-only
- activation TTL is 120 seconds
- activation bearer is stored under a SHA-256-derived Redis key
- raw activation bearer is absent from Redis keyspace
- activation is atomically consumed with GETDEL
- exact Workspace / Publication / User / content-hash binding
- activation is consumed before confirmation/executor
- activation issuance uses no-store/no-cache response controls

Production remains disabled for real publishing:

- `real_publish_enabled=false`
- `meta_publish_transport_enabled=false`
- default provider transport factory fails closed

Live production double-OFF verification used a dedicated
temporary fake Facebook target with intentionally invalid
credential ciphertext.

The real production HTTP `/publish` route returned HTTP 503
while the global execution switch was disabled.

Verified before any execution:

- activation remained unconsumed
- confirmation remained unconsumed
- Publication remained approved
- publish_attempts remained zero
- trigger audit remained unset
- no durable publishing claim was created

The second independent provider-wiring gate was also verified
against the exact deployed application with a process-local
execution-switch override:

- provider wiring remained disabled
- Meta transport constructor calls: zero
- credential decrypt calls: zero
- activation consumption: zero
- confirmation consumption: zero
- Publication mutation: zero

Temporary PostgreSQL and Redis test data was completely
removed.

Production invariants:

- deployed image:
  sha256:e924a341cadd838d981d945ec4351d18f77e6ccb31913cd3820dc44847e6d5b8
- database revision: a13e0a91c7f2
- backend non-root
- backend healthy
- no database migration
- no production restart during final safety gate
- no real Meta publishing request
- no Facebook post created

Result:

`v0.13E-E-C Single-Post Activation Production Deployment: PASS`


## MarketingOS AI v0.13E-E-D Step 2A — Exact Canary Target Foundation

Date: 2026-08-09

Status: PASS — source only

Added two fail-closed server-side configuration fields:

- `meta_publish_canary_workspace_id`
- `meta_publish_canary_publication_id`

Both default to `None`.

No `.env` values were added.

Added:

`app/services/publication_canary_target.py`

The helper requires an exact match of:

- Workspace UUID
- Publication UUID

Safety semantics:

- target unset -> rejected
- partially configured target -> rejected
- wrong Workspace -> rejected
- wrong Publication -> rejected
- exact Workspace + Publication -> allowed
- mismatch and unavailable states use the same generic internal
  rejection class so configured target identifiers are not exposed

This step intentionally does not wire the helper into production
request paths yet.

Production remained unchanged:

- Publication routes: 8
- real_publish_enabled=false
- meta_publish_transport_enabled=false
- no backend rebuild
- no backend restart
- no database migration
- no Redis mutation
- no credential decrypt
- no Meta request
- no Facebook post

Result:

`v0.13E-E-D Step 2A Exact Canary Target Foundation: PASS`


## MarketingOS AI v0.13E-E-D Step 2B — Exact Canary Target Wiring

Date: 2026-08-09

Status: PASS — source only

Exact first-live-post canary targeting is enforced at three
independent application boundaries.

Activation issuance:

owner authorization
→ exact Workspace + Publication target
→ dry-run
→ activation issuance

Publish HTTP:

publish authorization
→ real_publish_enabled
→ exact Workspace + Publication target
→ provider factory
→ activation
→ confirmation / controlled executor

Activation execution defense-in-depth:

real_publish_enabled
→ meta_publish_transport_enabled
→ exact Workspace + Publication target
→ dry-run / exact content hash
→ activation GETDEL
→ confirmation / executor

Default source configuration remains fail-closed:

- real_publish_enabled=false
- meta_publish_transport_enabled=false
- meta_publish_canary_workspace_id=None
- meta_publish_canary_publication_id=None

No `.env` canary target was added.

Dedicated exact-target regressions and all existing
non-integration publishing regressions passed.

Legacy tests used a test-process-only canary bypass.
Existing test source files were not modified.

Production remained unchanged:

- no backend rebuild
- no backend restart
- no database migration
- no production Redis mutation
- no credential decrypt
- no real Meta request
- no Facebook post

Result:

`v0.13E-E-D Step 2B Exact Canary Target Wiring: PASS`


## MarketingOS AI v0.13E-E-D Step 2C — Exact Canary PostgreSQL/Redis Integration

Date: 2026-08-09

Status: PASS — source/integration only

The existing activated HTTP integration now enforces exact
server-side Workspace + Publication canary targeting.

Real HTTP activation issuance verified:

- target unset -> HTTP 409
- wrong Workspace -> HTTP 409
- wrong Publication -> HTTP 409
- rejected targets never reach the Redis activation issuer
- exact targets issue exactly three activation grants

With both global publishing switches enabled only inside the
isolated integration process:

- wrong Workspace /publish -> HTTP 409
- wrong Publication /publish -> HTTP 409
- provider factory call count does not increase
- activation is not consumed
- confirmation is not consumed
- durable PostgreSQL claim is not created
- credential decrypt call count does not increase

Exact scenario targeting:

1. first Publication -> stale hash + success
2. second Publication -> definite provider rejection
3. third Publication -> outcome unknown / reconciliation

Integration uses real authentication, real PostgreSQL, real
Redis, and the real encrypted credential decrypt path.

Provider execution remains exclusively behind
httpx.MockTransport.

All process-local canary settings, publishing switches,
activation wrapper, provider factory, and cipher are restored
in finally.

Temporary Redis grants and temporary PostgreSQL Publications
are cleaned by the integration.

Production remains unchanged and double-OFF.

No real Meta network request or Facebook post was created.

Result:

`v0.13E-E-D Step 2C Exact Canary PostgreSQL/Redis Integration: PASS`


## MarketingOS AI v0.13E-E-D Step 3A — Double-OFF Candidate Build

Date: 2026-08-09

Status: PASS — candidate build only

A new backend candidate containing the completed E-D exact
canary-target hardening was built.

Candidate tag:

`marketingos-backend:v013eed-candidate`

Candidate exact image:

`sha256:2d21bb9f9f2d63341a95d500fa99277b8ba009c5044286d11b173599020ea303`

Rollback tag preserving the current E-C production image:

`marketingos-backend:v013eec-prod-before-ed-20260809_203810`

Candidate verification:

- packaged source matches current E-D source
- Publication route count = 8
- /publish present
- /publish-activation present
- real_publish_enabled=false
- meta_publish_transport_enabled=false
- canary Workspace unset
- canary Publication unset
- exact-target application call sites = 3
- concrete MetaGraphHTTPTransport constructor count = 1
- backend runtime UID = 100

The local :latest tag was restored after candidate
verification.

Production was not rebuilt, recreated, restarted, or
modified.

No database migration or production Redis mutation occurred.

No real Meta request or Facebook post was created.

Result:

`v0.13E-E-D Step 3A Double-OFF Candidate Build: PASS`


## MarketingOS AI v0.13E-E-D Step 3B — Isolated Candidate Fail-Closed Gate

Date: 2026-08-09

Status: PASS — isolated candidate only

The exact E-D candidate image was executed directly with
Docker network mode set to none.

Verified packaged runtime defaults:

- Publication routes = 8
- /publish present
- /publish-activation present
- real_publish_enabled=false
- meta_publish_transport_enabled=false
- canary Workspace unset
- canary Publication unset
- exact-target application call sites = 3
- runtime UID = 100

Behavior gates inside the exact candidate verified:

- master OFF rejects /publish before provider factory
- process-local master ON with canary target unset rejects
  /publish before provider factory
- activation issuance with target unset rejects before
  dry-run and activation issuer
- defense-in-depth execution with both switches ON but
  canary unset rejects before dry-run and activation GETDEL
- an exact process-local canary target permits the existing
  dry-run + activation verification layer

Static topology remains:

- exactly 3 exact-target application call sites
- exactly 1 concrete MetaGraphHTTPTransport constructor

The candidate container used Docker `--network none`.

Therefore this step performed:

- no PostgreSQL calls
- no Redis calls
- no credential decrypt
- no Meta HTTP calls
- no Facebook post

Production and local image tags remained unchanged.

Result:

`v0.13E-E-D Step 3B Isolated Candidate Fail-Closed Gate: PASS`


## MarketingOS AI v0.13E-E-D Step 3C — Production Double-OFF Deployment

Date: 2026-08-09

Status: PASS — production deployed, publishing disabled

The exact v0.13E-E-D canary-hardened backend candidate was
deployed to production.

Exact production image:

`sha256:2d21bb9f9f2d63341a95d500fa99277b8ba009c5044286d11b173599020ea303`

Production runtime verification:

- Publication routes = 8
- /publish present
- /publish-activation present
- real_publish_enabled=false
- meta_publish_transport_enabled=false
- canary Workspace unset
- canary Publication unset
- canary environment keys absent
- exact-target application call sites = 3
- concrete MetaGraphHTTPTransport constructor count = 1
- backend runtime UID = 100
- health = HTTP 200
- Alembic revision unchanged

The previous production image remains available through the
dedicated rollback tag.

No production canary target was configured.

No publishing switch was enabled.

No database migration was performed.

No real Meta request or Facebook post was created.

Result:

`v0.13E-E-D Step 3C Production Double-OFF Deployment: PASS`


## MarketingOS AI v0.13E-E-D Step 3D — Production Double-OFF Live Safety Gate

Date: 2026-08-09

Status: PASS — production live safety verification

The deployed E-D production backend was verified through the
actual running Uvicorn HTTP process while publishing remained
double-OFF and both canary targets remained unset.

A short-lived JWT for an active Workspace owner was generated
in process memory only and was never printed.

Using a deliberately nonexistent random Publication UUID:

- LIVE /publish-activation with canary target unset -> HTTP 409
- LIVE /publish with master switch OFF -> HTTP 503
- no Publication row was created
- no canary target was configured
- no publishing switch was enabled

The deployed production image was also exercised in a
separate process-local defense-in-depth test:

- master ON + canary unset blocks before provider factory
- activation issuance blocks before dry-run / Redis issuer
- execution blocks before dry-run / activation GETDEL

These process-local overrides did not modify the serving
Uvicorn process.

Production remained:

- exact E-D image
- real_publish_enabled=false
- meta_publish_transport_enabled=false
- canary Workspace unset
- canary Publication unset
- health HTTP 200
- Alembic revision unchanged
- backend not restarted

No credential decrypt or real Meta publishing request was
performed.

No Facebook post was created.

Result:

`v0.13E-E-D Step 3D Production Double-OFF Live Safety Gate: PASS`


## MarketingOS AI v0.13E-E-D Step 4B — Dedicated Live Canary Publication

Date: 2026-08-09

Status: dedicated approved canary created; publishing disabled

The first live Facebook publishing canary was prepared as a
dedicated immutable approved Publication.

Target Page:

`小八寶花店`

Target Facebook Page ID:

`119402794592265`

Exact approved content:

`自動發布測試`

The Publication uses an immutable content snapshot and
SHA-256 content hash.

The existing publishing dry-run passed before the creation
transaction was committed and again against the durable row.

Production remained double-OFF.

Canary environment targets remained unset.

No Redis grant was issued.

The Page credential was not decrypted.

No Meta publishing HTTP request was made.

No Facebook post was created.


## MarketingOS AI v0.13E-E-D Step 4C — Exact Production Canary Target Lock

Date: 2026-08-09

Status: PASS — exact target configured, publishing disabled

Production is now configured to permit the first live
publishing canary only for this exact target:

Workspace:

`2f1ba3f9-d863-4274-a872-ab83fb7a2aa7`

Publication:

`93081fd9-469b-40f6-8537-373fa6a865ec`

Facebook Page:

`小八寶花店`

Page ID:

`119402794592265`

Exact immutable content:

`自動發布測試`

The dedicated Publication remains approved with zero publish
attempts.

Both production publishing switches remain disabled:

- real_publish_enabled=false
- meta_publish_transport_enabled=false

No activation grant was issued.

No confirmation grant was issued.

No credential was decrypted.

No Meta publishing HTTP request was made.

No Facebook post was created.


## MarketingOS AI v0.13E-E-D Step 4D — Final Armed-but-OFF Pre-Live Gate

Date: 2026-08-09

Status: PASS — ready for explicit live-canary authorization

Exact production target:

Workspace:

`2f1ba3f9-d863-4274-a872-ab83fb7a2aa7`

Publication:

`93081fd9-469b-40f6-8537-373fa6a865ec`

Facebook Page:

`小八寶花店`

Page ID:

`119402794592265`

Exact immutable content:

`自動發布測試`

Pre-live verification passed:

- dedicated Publication remains approved
- publish_attempts remains zero
- no reconciliation record exists
- connected/active Facebook Page matches exactly
- encrypted credential is present but was not decrypted
- pages_manage_posts is present
- pages_read_engagement is present
- active Workspace owner is present
- dry-run endpoint is /119402794592265/feed
- exact content hash matches
- exact canary-target helper accepts only the configured pair
- Redis contains no activation/confirmation publishing grants
- production backend was not restarted
- production health remains HTTP 200
- Alembic revision is unchanged

Production remains:

- real_publish_enabled=false
- meta_publish_transport_enabled=false

No activation grant was issued.

No confirmation grant was issued.

No credential decrypt occurred.

No Meta publishing request was made.

No Facebook post was created.



## MarketingOS AI v0.13E-E-D Step 4E-R2 — First Real Facebook Canary

Date: 2026-08-09

Target Page: `小八寶花店`

Page ID: `119402794592265`

Workspace: `2f1ba3f9-d863-4274-a872-ab83fb7a2aa7`

Publication: `93081fd9-469b-40f6-8537-373fa6a865ec`

Exact immutable content: `自動發布測試`

Live /publish request count: `1`

HTTP status observed by local client: `200`

Final durable status: `published`

Final publish_attempts: `1`

Result: `PUBLISHED`

Automatic retry: `NONE`

Final production runtime: `OFF|OFF|UNSET|UNSET`

Recorded at: `2026-08-09T13:39:11.143316+00:00`


## MarketingOS AI v0.13E-E-D Step 4F — First Real Facebook Canary Closure

Date: 2026-08-09

Status: PASS — first real Facebook automated publication succeeded.

Target Page:

`小八寶花店`

Page ID:

`119402794592265`

Exact published content:

`自動發布測試`

Publication:

`93081fd9-469b-40f6-8537-373fa6a865ec`

Provider post ID:

`119402794592265_122219138390047230`

Final durable state:

- status=published
- publish_attempts=1
- publish trigger audit present
- published timestamp present
- last_error absent
- reconciliation records absent

Execution guarantees observed:

- exactly one /publish request
- automatic retry was not used
- one-time activation was consumed/cleaned
- one-time confirmation was consumed/cleaned

Production after the canary was restored to:

- real_publish_enabled=false
- meta_publish_transport_enabled=false
- canary Workspace unset
- canary Publication unset

Backend remains healthy and runs as non-root UID 100.

The first real Meta/Facebook publishing canary is formally
complete.


## MarketingOS AI v0.13F Step 2A — Publishing Mode Policy Foundation

Date: 2026-08-09

Status: PASS — source-only normal/canary mode foundation.

Added fail-closed configuration:

`meta_publish_canary_mode_enabled: bool = True`

Default behavior therefore remains canary-only.

Added a pure publication target-policy abstraction:

- canary mode requires the exact configured Workspace and Publication
- normal mode removes only the exact canary-target restriction
- the policy performs no DB access
- the policy performs no Redis access
- the policy performs no credential decryption
- the policy performs no provider network request

Existing application canary wiring was intentionally left unchanged
during Step 2A.

The first isolated test invocation failed only because the test script
was executed without `/app` on `PYTHONPATH`.

The corrected isolated execution used:

`PYTHONPATH=/app`

and the policy regression passed.

Production was not rebuilt, restarted or deployed.

Production remained:

- real_publish_enabled=false
- meta_publish_transport_enabled=false
- canary Workspace unset
- canary Publication unset

No Meta request was performed.

No Facebook post was created.


## MarketingOS AI v0.13F Step 2B — Mode-Aware Publishing Target Wiring

Date: 2026-08-09

Status: PASS — source-only mode-aware publishing wiring.

Two validation-script issues were corrected during Step 2B:

1. the exact-canary helper intentionally remains once inside the
   v0.13F target-policy abstraction and must not be counted as stale
   application wiring;
2. `publish_attempts` is mutated by the publication workflow's
   `begin_publication_attempt` transition, while the executor invokes
   that transition and commits the durable publishing claim before
   credential decryption/provider execution.

Final application topology:

- `/publish` mode-aware target policy: 1
- `/publish-activation` mode-aware target policy: 1
- activation execution mode-aware target policy: 1
- exact-canary helper inside target-policy abstraction: 1
- legacy exact-canary application wiring: 0

CANARY mode remains fail-closed.

CANARY activation remains owner-only.

NORMAL activation uses the established publishing authorization.

Preserved safety controls:

- master publishing kill switch
- Meta transport kill switch
- approval/read-only dry-run
- immutable content hash
- one-time activation
- one-time confirmation
- durable publishing claim
- publish-attempt accounting
- late credential decryption
- definite provider rejection handling
- outcome-unknown reconciliation
- no automatic retry

No production build or deployment occurred.

Production was not restarted.

No database migration occurred.

No real Meta request occurred.

No Facebook post was created.


## MarketingOS AI v0.13F Step 2C-B — NORMAL Mode Real PG/Redis Integration

Date: 2026-08-09

Status: PASS — NORMAL-mode backend publishing integration.

The existing integration already contained canary Workspace and
Publication target save/restore lifecycle. Earlier generated-test
attempts incorrectly duplicated those target captures.

The final integration therefore added only the missing
`meta_publish_canary_mode_enabled` lifecycle.

The existing CANARY regressions were retained.

After CANARY activation gating was validated, the test:

- switched to NORMAL mode process-locally
- set canary Workspace target to None
- set canary Publication target to None
- removed the earlier canary activation grants
- reissued three activations through the real HTTP endpoint
- used real Redis hashed activation storage
- retained real confirmations
- executed publishing with exact-target enforcement disabled

The original wrong-canary `/publish` regression was executed with
CANARY mode temporarily restored.

The success, definite rejection and timeout provider scenarios then
ran again in NORMAL mode.

Validated provider outcomes:

- mock success -> published
- mock 400 rejection -> failed
- mock timeout -> publishing / reconciliation required
- no automatic retry for ambiguous outcome

Integration used:

- real authentication
- real PostgreSQL
- real Redis
- real confirmation issuance
- real activation issuance
- real activation GETDEL
- real confirmation GETDEL
- real durable execution claim
- real credential decrypt path
- httpx.MockTransport provider boundary

No real Meta request occurred.

Temporary database rows and Redis grants were cleaned.

Production was not rebuilt, deployed or restarted.

Production remained publishing OFF/OFF with canary targets unset.


## MarketingOS AI v0.13F Step 3A — Candidate Build

Date: 2026-08-09

Status: PASS — backend candidate built and fully verified without deployment.

Candidate image:

`sha256:c5e6fc6b7d930811b54965a62f0871597fc739df192863b717064cb38f4ce362`

Candidate tag:

`marketingos-backend:v013f-candidate`

Production rollback tag:

`marketingos-backend:v013eed-prod-before-v013f-20260809_224326`

The production Dockerfile intentionally excludes test source files.

An initial verification command omitted Docker interactive STDIN while
feeding a Python heredoc, producing an empty result. The candidate did
not contain tests; the verification command was corrected.

Final candidate verification:

- production runtime image contains no /app/tests directory
- all packaged app/**/*.py files exactly match host source
- default mode is CANARY / fail-closed
- real_publish_enabled=false
- meta_publish_transport_enabled=false
- canary Workspace unset
- canary Publication unset
- runtime UID 100
- exact-canary helper exists only inside the target-policy abstraction
- three application call sites use the mode-aware target policy
- host regressions mounted read-only passed against candidate app code
- required publishing routes import successfully

Production was not deployed or restarted.

Local marketingos-backend:latest remains the current production image.

No database migration occurred.

No real Meta request occurred.

No Facebook post was created.


## MarketingOS AI v0.13F Step 3B — Candidate Real PG/Redis Integration

Date: 2026-08-09

Status: PASS — built candidate image passed the full NORMAL-mode
backend integration against real PostgreSQL and Redis.

Candidate:

`sha256:c5e6fc6b7d930811b54965a62f0871597fc739df192863b717064cb38f4ce362`

The candidate application code came entirely from the built image.
Only backend/tests was mounted read-only for regression execution.

Integration used:

- real authentication
- real PostgreSQL
- real Redis
- real publication confirmation issuance
- real confirmation GETDEL
- real publication activation issuance
- real activation GETDEL
- real durable publication claim
- real credential decryption path
- NORMAL mode with canary targets unset
- httpx.MockTransport as the Meta provider boundary

The existing CANARY fail-closed and wrong-target checks remained part
of the integration.

Validated outcomes:

- mock success -> published
- definite provider rejection -> failed
- mock timeout -> publishing / reconciliation required
- ambiguous outcome automatic retry -> none

Temporary PostgreSQL rows were removed.

Temporary Redis activation/confirmation grants were removed.

Production backend was not replaced or restarted.

Production remained publishing OFF/OFF.

Local marketingos-backend:latest remained the current production
image.

No real Meta request occurred.

No Facebook post was created.


## MarketingOS AI v0.13F Step 3C — Production Deploy

Date: 2026-08-09

Status: PASS — v0.13F candidate deployed to production while
publishing remained fail-closed.

Production image:

`sha256:c5e6fc6b7d930811b54965a62f0871597fc739df192863b717064cb38f4ce362`

Production tag:

`marketingos-backend:v013f-prod`

Rollback image:

`sha256:2d21bb9f9f2d63341a95d500fa99277b8ba009c5044286d11b173599020ea303`

Rollback tag:

`marketingos-backend:v013eed-prod-before-v013f-20260809_224326`

Compose deployment reference inventory established that backend is a
build-only service with no explicit image field.

The confirmed implicit Compose build/deployment tag is:

`marketingos-backend:latest`

Deployment was performed by retagging the already-validated candidate
to that exact implicit tag and recreating only the backend service with
--no-build and --no-deps.

Production safety state:

- real_publish_enabled=false
- meta_publish_transport_enabled=false
- meta_publish_canary_mode_enabled=true
- canary Workspace unset
- canary Publication unset
- runtime UID 100
- required publishing routes present
- mode-aware target application calls: three
- exact-canary helper isolated to policy abstraction
- Publication durable state unchanged
- Redis publishing grants absent
- health HTTP 200
- no database migration

NORMAL publishing remains inactive.

No real Meta request occurred.

No Facebook post was created.

Security follow-up:

The Step 3C-R2 inventory printed resolved environment values. Any
credentials exposed in that diagnostic output must be rotated before
NORMAL/live publishing is enabled.


## MarketingOS AI v0.13F Step 3D — Production Post-Deploy Audit

Date: 2026-08-09

Status: PASS — v0.13F production deployment audited after restart.

Production image:

`sha256:c5e6fc6b7d930811b54965a62f0871597fc739df192863b717064cb38f4ce362`

Verified:

- production, candidate, latest and immutable production tags match
- rollback image remains preserved
- runtime UID 100
- real publishing switch OFF
- Meta publishing transport switch OFF
- publishing mode CANARY / fail-closed
- canary Workspace unset
- canary Publication unset
- health stable at HTTP 200
- DB revision a13e0a91c7f2
- durable Publication state unchanged
- no unresolved publishing/reconciliation row
- no Redis activation grant
- no Redis confirmation grant
- required publishing routes present
- exact-canary helper isolated to target-policy abstraction
- three mode-aware application target gates present
- no critical exception indicator in fresh backend logs
- no Meta provider-network indicator in fresh backend logs

No production restart occurred during this audit.

No database migration occurred.

No normal publishing was activated.

No real Meta request was intentionally executed.

Security prerequisite before NORMAL/live publishing:

Secrets exposed by the earlier Step 3C-R2 diagnostic output must be
rotated before enabling NORMAL/live publishing.


## MarketingOS AI v0.13F Step 4B-B — OpenAI API Key Cutover

Date: 2026-08-10

Status: PASS.

- replacement OpenAI API key authenticated before cutover
- replacement key differs from previous production key
- secret values were not emitted
- `.env` updated atomically and remains mode 600
- backend recreated successfully
- runtime settings loaded replacement key
- module-global AsyncOpenAI client loaded replacement key
- runtime OpenAI authentication returned HTTP 200
- production image unchanged
- publishing remained OFF/OFF
- mode remained CANARY / fail-closed
- canary targets remained unset
- database revision unchanged
- Redis publication grants absent
- no Meta request occurred

Provider-side removal of the old/exposed OpenAI API keys remains
required.


## MarketingOS AI v0.13F Step 4B-B-R3 — OpenAI Key Rotation Closed

Date: 2026-08-10

Status: CLOSED.

- replacement OpenAI API key loaded by production
- runtime authentication returned HTTP 200
- production key suffix verified as FcEA
- previous production OpenAI key E0YA revoked provider-side
- production publishing state remained fail-closed
- no Meta request occurred


## MarketingOS AI v0.13F Step 4B-C — Meta App Secret Rotation

Date: 2026-08-10

Status: PASS.

- Meta provider App Secret reset completed
- replacement App Secret validated against Meta before local cutover
- secret values were not emitted
- `.env` updated atomically and remains mode 600
- backend recreated successfully
- runtime loaded replacement Meta App Secret
- runtime Meta app credential validation returned HTTP 200
- production image unchanged
- publishing remained OFF/OFF
- mode remained CANARY / fail-closed
- canary targets remained unset
- database revision unchanged
- Redis publication grants absent
- no Meta publish request occurred


## MarketingOS AI v0.13F Step 4B-D — PostgreSQL Password Rotation

Date: 2026-08-10

Status: PASS.

- generated an independent 256-bit PostgreSQL credential
- PostgreSQL role password rotated under SCRAM-SHA-256
- old credential rejected on the real backend-to-database Docker network
- POSTGRES_PASSWORD and DATABASE_URL updated atomically
- `.env` remains mode 600
- PostgreSQL container recreated with replacement environment
- backend recreated with replacement DATABASE_URL
- fresh backend database authentication verified
- production image unchanged
- publishing remained OFF/OFF
- mode remained CANARY / fail-closed
- database revision unchanged
- Redis publication grants absent
- no Meta publish request occurred


## MarketingOS AI v0.13F Step 4B-E — SECRET_KEY Rotation

Date: 2026-08-10

Status: PASS.

- generated an independent replacement SECRET_KEY
- secret values were never emitted
- `.env` updated atomically and remains mode 600
- backend recreated successfully
- runtime loaded replacement SECRET_KEY
- replacement-key JWT encode/decode verified
- synthetic access JWT signed with previous SECRET_KEY is rejected
- access JWT lifetime remains 1800 seconds
- live OAuth flow uses Redis-backed v2 state
- no pending OAuth state existed during rotation
- refresh-token rows were not modified
- production image unchanged
- publishing remained OFF/OFF
- mode remained CANARY / fail-closed
- database revision unchanged
- Redis publication grants absent
- no external API request occurred


## MarketingOS AI v0.13F Step 4B-F — OAuth Token Encryption Key Rotation

Date: 2026-08-10

Status: PASS.

- generated an independent replacement Fernet key
- encryption-key values were never emitted
- backend stopped during the ciphertext/key cutover
- existing OAuth ciphertext decrypted under the previous key
- ciphertext re-encrypted transactionally under the replacement key
- `.env` cut over atomically and remains mode 600
- backend recreated with replacement encryption key
- runtime module-global OAuth cipher decrypts persisted ciphertext
- previous Fernet key no longer decrypts current persisted ciphertext
- Facebook SocialAccount ciphertext footprint remained 1 access / 0 refresh
- production image unchanged
- publishing remained OFF/OFF
- mode remained CANARY / fail-closed
- database revision unchanged
- OAuth/publishing transient Redis state absent
- no external API request occurred


## MarketingOS AI v0.13F Step 4C-B — Historical Credential Backup Sanitization

Date: 2026-08-10

Status: PASS.

- historical configuration backups retained structurally
- rotated credential plaintext removed from four historical production env backups
- `.env.example` converted to non-secret placeholders
- historical DATABASE_URL password material removed
- replacement production credentials were not copied into historical backups
- historical backup env files remain mode 600
- `.env.example` remains mode 644
- project files scanned for captured historical credential values
- no rotation recovery files remained
- current production `.env` unchanged
- current OAuth ciphertext remained decryptable
- production health and publishing safety state unchanged


## MarketingOS AI v0.13F Step 4C-C — Credential Exposure Incident Closure

Date: 2026-08-10

Status: CLOSED.

- OpenAI production API key rotated and current key validated
- old OpenAI API key revocation confirmed by operator
- Meta App Secret rotation closed
- PostgreSQL production credential rotation closed
- SECRET_KEY rotation closed
- OAuth Fernet encryption-key rotation closed
- Facebook OAuth ciphertext re-encrypted under replacement key
- historical credential backups sanitized
- rotation recovery files absent
- production image unchanged
- production publishing remains OFF/OFF and CANARY fail-closed
- database revision unchanged
- OAuth/publishing transient Redis state absent

Credential exposure incident status: CLOSED.
