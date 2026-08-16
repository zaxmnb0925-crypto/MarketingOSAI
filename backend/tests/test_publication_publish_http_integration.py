import asyncio
import inspect
from contextlib import asynccontextmanager
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
from sqlalchemy import delete, select

import sys as _publication_compat_sys
from pathlib import Path as _publication_compat_Path

_publication_compat_dir = str(
    _publication_compat_Path(
        __file__
    ).resolve().parent
)

if (
    _publication_compat_dir
    not in _publication_compat_sys.path
):
    _publication_compat_sys.path.insert(
        0,
        _publication_compat_dir,
    )

from _publication_test_compat import (
    publication_publishing_source_path,
    publication_source_paths,
    publication_source_text,
    publications,
)
from _integration_run_identity import integration_token, integration_uuid
import app.services.publication_executor as executor

from app.core.database import get_db
from app.core.redis_client import redis_client
from app.core.security import create_access_token
from app.main import app
from app.models.membership import (
    Membership,
    MembershipRole,
)
from app.models.publication import (
    Publication,
    PublicationStatus,
    utcnow,
)
from app.models.social_account import (
    SocialAccount,
    SocialAccountStatus,
    SocialPlatform,
)
from app.models.user import User
from app.services.meta_publishing import (
    MetaGraphHTTPTransport,
)
from app.services.publication_confirmation_store import (
    _key,
)
from app.services.publication_workflow import (
    content_sha256,
)
from app.services.publication_activation_store import _key as _activation_key


MESSAGES = (
    "v0.13E-D-B HTTP mock success",
    "v0.13E-D-B HTTP mock rejection",
    "v0.13E-D-B HTTP mock unknown",
)


RUN_USER_ID = integration_uuid("publish-http-user")
RUN_WORKSPACE_ID = integration_uuid("publish-http-workspace")
RUN_MEMBERSHIP_ID = integration_uuid("publish-http-membership")
RUN_SOCIAL_ACCOUNT_ID = integration_uuid("publish-http-social-account")
RUN_PROVIDER_ID = integration_token("publish-http-page")


@asynccontextmanager
async def session():
    dependency = get_db()

    if not inspect.isasyncgen(
        dependency
    ):
        raise AssertionError(
            "get_db is not async generator"
        )

    db = await anext(
        dependency
    )

    try:
        yield db
    finally:
        await dependency.aclose()


async def load_publication(
    publication_id,
):
    async with session() as db:
        result = await db.execute(
            select(Publication).where(
                Publication.id
                == publication_id
            )
        )

        return result.scalar_one_or_none()


class CountingCipher:
    def __init__(
        self,
        inner,
    ):
        self.inner = inner
        self.calls = 0

    def decrypt(
        self,
        ciphertext,
    ):
        self.calls += 1

        #
        # Exercise the real decrypt implementation.
        # Never print ciphertext or plaintext.
        #
        return self.inner.decrypt(
            ciphertext
        )


async def main():
    publication_ids = [
        uuid4(),
        uuid4(),
        uuid4(),
    ]

    confirmations = {}
    activations = {}
    hashes = {}

    original_factory = (
        publications.get_publication_publish_transport
    )

    original_enabled = (
        publications.settings.real_publish_enabled
    )
    original_transport_enabled = (
        publications.settings.meta_publish_transport_enabled
    )

    original_canary_workspace_id = (
        publications.settings.meta_publish_canary_workspace_id
    )

    original_canary_publication_id = (
        publications.settings.meta_publish_canary_publication_id
    )

    original_cipher = (
        executor.oauth_token_cipher
    )

    original_create_activation = (
        publications.create_publication_activation
    )

    activation_issue_calls = 0

    async def counting_create_activation(
        *args,
        **kwargs,
    ):
        nonlocal activation_issue_calls

        activation_issue_calls += 1

        return await original_create_activation(
            *args,
            **kwargs,
        )

    publications.create_publication_activation = (
        counting_create_activation
    )

    counting_cipher = CountingCipher(
        original_cipher
    )

    executor.oauth_token_cipher = (
        counting_cipher
    )

    current_transport = {
        "value": None,
    }

    factory_calls = 0
    access_token = None

    mock_calls = {
        "success": 0,
        "rejection": 0,
        "unknown": 0,
    }

    def transport_factory():
        nonlocal factory_calls

        factory_calls += 1

        value = current_transport[
            "value"
        ]

        if value is None:
            raise AssertionError(
                "transport requested without mock"
            )

        return value

    publications.get_publication_publish_transport = (
        transport_factory
    )

    try:
        #
        # Find a real connected Facebook Page plus an
        # active owner/admin/manager in the same Workspace.
        #
        async with session() as db:
            result = await db.execute(
                select(
                    SocialAccount,
                    Membership,
                    User,
                )
                .join(
                    Membership,
                    Membership.workspace_id
                    == SocialAccount.workspace_id,
                )
                .join(
                    User,
                    User.id
                    == Membership.user_id,
                )
                .where(
                    SocialAccount.platform
                    == SocialPlatform.facebook,
                    SocialAccount.status
                    == SocialAccountStatus.connected,
                    SocialAccount.is_active.is_(
                        True
                    ),
                    SocialAccount.platform_account_id.is_not(
                        None
                    ),
                    SocialAccount.access_token_ciphertext.is_not(
                        None
                    ),
                    Membership.role
                    == MembershipRole.owner,
                    User.is_active.is_(
                        True
                    ),
                    SocialAccount.id == RUN_SOCIAL_ACCOUNT_ID,
                    SocialAccount.workspace_id == RUN_WORKSPACE_ID,
                    SocialAccount.platform_account_id == RUN_PROVIDER_ID,
                )
                .limit(1)
            )

            row = result.first()

            if row is None:
                raise AssertionError(
                    "No eligible Facebook target/operator"
                )

            account = row[0]
            membership = row[1]
            user = row[2]

            workspace_id = (
                account.workspace_id
            )
            user_id = user.id
            account_id = account.id
            brand_id = account.brand_id
            page_id = (
                account.platform_account_id
            )

            if (
                membership.workspace_id
                != workspace_id
            ):
                raise AssertionError(
                    "operator workspace mismatch"
                )

        print(
            "Eligible real Facebook target/operator: PASS"
        )

        #
        # Create three temporary approved Publications.
        #
        async with session() as db:
            for publication_id, message in zip(
                publication_ids,
                MESSAGES,
            ):
                content_hash = (
                    content_sha256(
                        message
                    )
                )

                hashes[
                    publication_id
                ] = content_hash

                db.add(
                    Publication(
                        id=publication_id,
                        workspace_id=workspace_id,
                        brand_id=brand_id,
                        content_generation_id=None,
                        social_account_id=account_id,
                        created_by_user_id=user_id,
                        status=(
                            PublicationStatus.approved
                        ),
                        platform="facebook",
                        target_account_id=page_id,
                        target_account_name=None,
                        content_snapshot=message,
                        content_hash=content_hash,
                        idempotency_key=(
                            "v013e-d-b-"
                            + uuid4().hex
                        ),
                        approved_by_user_id=user_id,
                        approved_at=utcnow(),
                        publish_triggered_by_user_id=None,
                        publish_triggered_at=None,
                        publish_attempts=0,
                        provider_post_id=None,
                        provider_permalink=None,
                        last_error=None,
                        published_at=None,
                    )
                )

            await db.commit()

        print(
            "Three temporary approved Publications: PASS"
        )

        #
        # Real JWT authentication against source ASGI app.
        #
        access_token, _ = (
            create_access_token(
                user_id
            )
        )

        asgi_transport = httpx.ASGITransport(
            app=app
        )

        async with httpx.AsyncClient(
            transport=asgi_transport,
            base_url="http://source-test",
            timeout=15.0,
            follow_redirects=False,
        ) as client:

            #
            # Issue three confirmations using the real HTTP
            # route and real Redis.
            #
            for publication_id in publication_ids:
                response = await client.post(
                    (
                        f"/api/workspaces/{workspace_id}"
                        f"/publications/{publication_id}"
                        "/publish-confirmation"
                    ),
                    headers={
                        "Authorization":
                            f"Bearer {access_token}",
                    },
                )

                if response.status_code != 201:
                    raise AssertionError(
                        "confirmation HTTP "
                        f"{response.status_code}"
                    )

                #
                # D-B also protects the C anti-cache fix.
                #
                if (
                    response.headers.get(
                        "Cache-Control"
                    )
                    != "no-store"
                ):
                    raise AssertionError(
                        "confirmation Cache-Control missing"
                    )

                if (
                    response.headers.get(
                        "Pragma"
                    )
                    != "no-cache"
                ):
                    raise AssertionError(
                        "confirmation Pragma missing"
                    )

                body = response.json()

                confirmation = body.get(
                    "confirmation"
                )

                if (
                    not isinstance(
                        confirmation,
                        str,
                    )
                    or len(
                        confirmation
                    ) < 32
                ):
                    raise AssertionError(
                        "confirmation missing"
                    )

                if (
                    body.get(
                        "content_hash"
                    )
                    != hashes[
                        publication_id
                    ]
                ):
                    raise AssertionError(
                        "confirmation hash mismatch"
                    )

                confirmations[
                    publication_id
                ] = confirmation

                key = _key(
                    confirmation
                )

                if confirmation in key:
                    raise AssertionError(
                        "raw confirmation in Redis key"
                    )

                if not await redis_client.exists(
                    key
                ):
                    raise AssertionError(
                        "confirmation Redis key missing"
                    )

            print(
                "Real HTTP confirmation issuance x3: PASS"
            )
            print(
                "Confirmation HTTP anti-cache: PASS"
            )
            print(
                "Real Redis hashed confirmation keys: PASS"
            )
            #
            # E-D exact-canary activation issuance gates.
            #
            first_activation_id = (
                publication_ids[0]
            )

            first_activation_url = (
                f"/api/workspaces/{workspace_id}"
                f"/publications/{first_activation_id}"
                "/publish-activation"
            )

            activation_factory_before = (
                factory_calls
            )

            activation_cipher_before = (
                counting_cipher.calls
            )

            #
            # UNSET target.
            #
            publications.settings.meta_publish_canary_workspace_id = (
                None
            )

            publications.settings.meta_publish_canary_publication_id = (
                None
            )

            rejected = await client.post(
                first_activation_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
            )

            if rejected.status_code != 409:
                raise AssertionError(
                    "unset activation canary HTTP "
                    f"{rejected.status_code}"
                )

            if activation_issue_calls != 0:
                raise AssertionError(
                    "unset target reached activation issuer"
                )

            #
            # Wrong Workspace.
            #
            publications.settings.meta_publish_canary_workspace_id = (
                uuid4()
            )

            publications.settings.meta_publish_canary_publication_id = (
                first_activation_id
            )

            rejected = await client.post(
                first_activation_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
            )

            if rejected.status_code != 409:
                raise AssertionError(
                    "wrong Workspace activation HTTP "
                    f"{rejected.status_code}"
                )

            if activation_issue_calls != 0:
                raise AssertionError(
                    "wrong Workspace reached activation issuer"
                )

            #
            # Wrong Publication.
            #
            publications.settings.meta_publish_canary_workspace_id = (
                workspace_id
            )

            publications.settings.meta_publish_canary_publication_id = (
                publication_ids[1]
            )

            rejected = await client.post(
                first_activation_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
            )

            if rejected.status_code != 409:
                raise AssertionError(
                    "wrong Publication activation HTTP "
                    f"{rejected.status_code}"
                )

            if activation_issue_calls != 0:
                raise AssertionError(
                    "wrong Publication reached activation issuer"
                )

            if (
                factory_calls
                != activation_factory_before
            ):
                raise AssertionError(
                    "activation rejection reached provider factory"
                )

            if (
                counting_cipher.calls
                != activation_cipher_before
            ):
                raise AssertionError(
                    "activation rejection decrypted credential"
                )

            stored = await load_publication(
                first_activation_id
            )

            if (
                stored is None
                or stored.status
                != PublicationStatus.approved
                or stored.publish_attempts != 0
                or stored.publish_triggered_by_user_id
                is not None
                or stored.publish_triggered_at
                is not None
            ):
                raise AssertionError(
                    "activation rejection mutated Publication"
                )

            if not await redis_client.exists(
                _key(
                    confirmations[
                        first_activation_id
                    ]
                )
            ):
                raise AssertionError(
                    "activation rejection consumed confirmation"
                )

            print(
                "Activation canary unset -> HTTP 409: PASS"
            )

            print(
                "Activation wrong Workspace -> HTTP 409: PASS"
            )

            print(
                "Activation wrong Publication -> HTTP 409: PASS"
            )

            print(
                "Rejected activation Redis issuance calls: NONE"
            )

            print(
                "Rejected activation DB/decrypt/provider activity: NONE"
            )

            #
            # E-C: issue one real, owner-authorized activation grant
            # for each temporary approved Publication.
            #
            for publication_id in publication_ids:
                publications.settings.meta_publish_canary_workspace_id = (
                    workspace_id
                )

                publications.settings.meta_publish_canary_publication_id = (
                    publication_id
                )

                activation_response = await client.post(
                    (
                        f"/api/workspaces/{workspace_id}"
                        f"/publications/{publication_id}"
                        "/publish-activation"
                    ),
                    headers={
                        "Authorization":
                            f"Bearer {access_token}",
                    },
                )

                if activation_response.status_code != 201:
                    raise AssertionError(
                        "activation HTTP "
                        f"{activation_response.status_code}"
                    )

                if (
                    activation_response.headers.get(
                        "Cache-Control"
                    )
                    != "no-store"
                ):
                    raise AssertionError(
                        "activation Cache-Control no-store missing"
                    )

                if (
                    activation_response.headers.get(
                        "Pragma"
                    )
                    != "no-cache"
                ):
                    raise AssertionError(
                        "activation Pragma no-cache missing"
                    )

                if (
                    activation_response.headers.get(
                        "Expires"
                    )
                    != "0"
                ):
                    raise AssertionError(
                        "activation Expires 0 missing"
                    )

                activation_body = (
                    activation_response.json()
                )

                activation_value = (
                    activation_body.get(
                        "activation"
                    )
                )

                if (
                    not isinstance(
                        activation_value,
                        str,
                    )
                    or len(
                        activation_value
                    ) < 32
                ):
                    raise AssertionError(
                        "activation bearer missing"
                    )

                if (
                    activation_body.get(
                        "content_hash"
                    )
                    != hashes[
                        publication_id
                    ]
                ):
                    raise AssertionError(
                        "activation content hash mismatch"
                    )

                activation_key = (
                    _activation_key(
                        activation_value
                    )
                )

                if activation_value in activation_key:
                    raise AssertionError(
                        "raw activation appears in Redis key"
                    )

                if not await redis_client.exists(
                    activation_key
                ):
                    raise AssertionError(
                        "hashed activation Redis key missing"
                    )

                raw_key = (
                    "publication_publish_activation:"
                    + activation_value
                )

                if await redis_client.exists(
                    raw_key
                ):
                    raise AssertionError(
                        "raw activation Redis key exists"
                    )

                activations[
                    publication_id
                ] = activation_value

            if activation_issue_calls != 3:
                raise AssertionError(
                    "activation issuance calls mismatch: "
                    f"{activation_issue_calls}"
                )

            print(
                "Exact-target activation Redis issuance x3: PASS"
            )

            print(
                "Real publish-activation issuance x3: PASS"
            )
            print(
                "Activation HTTP anti-cache: PASS"
            )
            print(
                "Hashed activation Redis keys: PASS"
            )
            print(
                "Raw activation Redis keys: NONE"
            )

            first_id = (
                publication_ids[0]
            )

            publications.settings.meta_publish_canary_workspace_id = (
                workspace_id
            )

            publications.settings.meta_publish_canary_publication_id = (
                first_id
            )

            publish_url = (
                f"/api/workspaces/{workspace_id}"
                f"/publications/{first_id}"
                "/publish"
            )

            #
            # Kill switch OFF must block before transport
            # construction, Redis consume, DB mutation and
            # credential decryption.
            #
            publications.settings.real_publish_enabled = (
                False
            )

            current_transport[
                "value"
            ] = None

            response = await client.post(
                publish_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                json={
                    "activation": activations[first_id],
                    "confirmation":
                        confirmations[
                            first_id
                        ],
                    "content_hash":
                        hashes[
                            first_id
                        ],
                },
            )

            if (
                response.status_code
                != 503
            ):
                raise AssertionError(
                    "disabled /publish HTTP "
                    f"{response.status_code}"
                )

            if factory_calls != 0:
                raise AssertionError(
                    "kill switch reached transport factory"
                )

            if counting_cipher.calls != 0:
                raise AssertionError(
                    "kill switch decrypted credential"
                )

            if not await redis_client.exists(
                _key(
                    confirmations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "kill switch consumed confirmation"
                )

            stored = (
                await load_publication(
                    first_id
                )
            )

            if (
                stored is None
                or stored.status
                != PublicationStatus.approved
                or stored.publish_attempts != 0
                or stored.publish_triggered_by_user_id
                is not None
                or stored.publish_triggered_at
                is not None
            ):
                raise AssertionError(
                    "kill switch mutated Publication"
                )

            print(
                "Real HTTP kill switch fail-closed: PASS"
            )
            print(
                "Kill switch Redis/DB/decrypt/provider activity: NONE"
            )

            #
            # Switch ON only inside this transient test
            # process. No env or production setting changes.
            #
            if not await redis_client.exists(
                _activation_key(
                    activations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "kill switch consumed activation"
                )

            print(
                "Kill switch leaves activation reusable: PASS"
            )

            publications.settings.real_publish_enabled = (
                True
            )
            publications.settings.meta_publish_transport_enabled = (
                True
            )

            #
            # E-D exact-canary /publish rejection gate.
            #
            exact_payload = {
                "activation":
                    activations[
                        first_id
                    ],
                "confirmation":
                    confirmations[
                        first_id
                    ],
                "content_hash":
                    hashes[
                        first_id
                    ],
            }

            canary_factory_before = (
                factory_calls
            )

            canary_cipher_before = (
                counting_cipher.calls
            )

            #
            # Wrong Workspace.
            #
            publications.settings.meta_publish_canary_workspace_id = (
                uuid4()
            )

            publications.settings.meta_publish_canary_publication_id = (
                first_id
            )

            response = await client.post(
                publish_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                json=exact_payload,
            )

            if response.status_code != 409:
                raise AssertionError(
                    "wrong Workspace /publish HTTP "
                    f"{response.status_code}"
                )

            #
            # Wrong Publication.
            #
            publications.settings.meta_publish_canary_workspace_id = (
                workspace_id
            )

            publications.settings.meta_publish_canary_publication_id = (
                publication_ids[1]
            )

            response = await client.post(
                publish_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                json=exact_payload,
            )

            if response.status_code != 409:
                raise AssertionError(
                    "wrong Publication /publish HTTP "
                    f"{response.status_code}"
                )

            if (
                factory_calls
                != canary_factory_before
            ):
                raise AssertionError(
                    "wrong canary reached provider factory"
                )

            if (
                counting_cipher.calls
                != canary_cipher_before
            ):
                raise AssertionError(
                    "wrong canary decrypted credential"
                )

            if not await redis_client.exists(
                _activation_key(
                    activations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "wrong canary consumed activation"
                )

            if not await redis_client.exists(
                _key(
                    confirmations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "wrong canary consumed confirmation"
                )

            stored = await load_publication(
                first_id
            )

            if (
                stored is None
                or stored.status
                != PublicationStatus.approved
                or stored.publish_attempts != 0
                or stored.publish_triggered_by_user_id
                is not None
                or stored.publish_triggered_at
                is not None
                or stored.provider_post_id
                is not None
                or stored.published_at
                is not None
            ):
                raise AssertionError(
                    "wrong canary created durable DB claim"
                )

            print(
                "Wrong canary Workspace /publish -> HTTP 409: PASS"
            )

            print(
                "Wrong canary Publication /publish -> HTTP 409: PASS"
            )

            print(
                "Wrong canary provider factory delta: ZERO"
            )

            print(
                "Wrong canary activation GETDEL: NONE"
            )

            print(
                "Wrong canary confirmation GETDEL: NONE"
            )

            print(
                "Wrong canary durable DB claim: NONE"
            )

            print(
                "Wrong canary credential decrypt delta: ZERO"
            )

            #
            # Restore exact first target for stale-hash and
            # success paths.
            #
            publications.settings.meta_publish_canary_workspace_id = (
                workspace_id
            )

            publications.settings.meta_publish_canary_publication_id = (
                first_id
            )

            #
            # Stale content hash must fail before Redis
            # consume, credential decrypt or provider call.
            #
            stale_provider_calls = 0

            async def stale_handler(
                request: httpx.Request,
            ):
                nonlocal stale_provider_calls

                stale_provider_calls += 1

                raise AssertionError(
                    "stale hash reached provider"
                )

            current_transport[
                "value"
            ] = MetaGraphHTTPTransport(
                transport=httpx.MockTransport(
                    stale_handler
                )
            )

            response = await client.post(
                publish_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                json={
                    "activation": activations[first_id],
                    "confirmation":
                        confirmations[
                            first_id
                        ],
                    "content_hash":
                        "b" * 64,
                },
            )

            if response.status_code != 409:
                raise AssertionError(
                    "stale hash HTTP "
                    f"{response.status_code}"
                )

            if stale_provider_calls != 0:
                raise AssertionError(
                    "stale hash reached provider"
                )

            if counting_cipher.calls != 0:
                raise AssertionError(
                    "stale hash decrypted credential"
                )

            if not await redis_client.exists(
                _key(
                    confirmations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "stale hash consumed confirmation"
                )

            stored = await load_publication(
                first_id
            )

            if (
                stored is None
                or stored.status
                != PublicationStatus.approved
                or stored.publish_attempts != 0
            ):
                raise AssertionError(
                    "stale hash mutated Publication"
                )

            print(
                "Real HTTP stale-hash gate: PASS"
            )
            print(
                "Stale hash leaves confirmation reusable: PASS"
            )
            if not await redis_client.exists(
                _activation_key(
                    activations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "stale hash consumed activation"
                )

            print(
                "Stale hash leaves activation reusable: PASS"
            )

            #
            # SUCCESS
            #
            # Reuse the still-valid first confirmation after
            # the stale-hash attempt.
            #
            durable_claim_observed = False

            async def success_handler(
                request: httpx.Request,
            ):
                nonlocal durable_claim_observed

                mock_calls[
                    "success"
                ] += 1

                expected_path = (
                    f"/v23.0/{page_id}/feed"
                )

                if (
                    request.url.path
                    != expected_path
                ):
                    raise AssertionError(
                        "unexpected Meta feed path"
                    )

                if (
                    "access_token"
                    in request.url.params
                ):
                    raise AssertionError(
                        "Page token leaked into URL"
                    )

                authorization = (
                    request.headers.get(
                        "Authorization",
                        "",
                    )
                )

                if (
                    not authorization.startswith(
                        "Bearer "
                    )
                    or len(
                        authorization
                    ) <= len(
                        "Bearer "
                    )
                ):
                    raise AssertionError(
                        "Bearer authorization missing"
                    )

                form = parse_qs(
                    request.content.decode(
                        "utf-8"
                    )
                )

                if (
                    form.get(
                        "message"
                    )
                    != [
                        MESSAGES[0]
                    ]
                ):
                    raise AssertionError(
                        "success message mismatch"
                    )

                #
                # The executor must durably commit the claim
                # before provider execution. This query uses
                # a separate real PostgreSQL session while
                # the mocked provider request is in flight.
                #
                claimed = await load_publication(
                    first_id
                )

                if claimed is None:
                    raise AssertionError(
                        "durable claim Publication missing"
                    )

                if (
                    claimed.status
                    != PublicationStatus.publishing
                    or claimed.publish_attempts != 1
                    or claimed.publish_triggered_by_user_id
                    != user_id
                    or claimed.publish_triggered_at
                    is None
                ):
                    raise AssertionError(
                        "provider reached before durable claim"
                    )

                durable_claim_observed = True

                return httpx.Response(
                    200,
                    json={
                        "id":
                            "mock_page_mock_success",
                    },
                    request=request,
                )

            current_transport[
                "value"
            ] = MetaGraphHTTPTransport(
                transport=httpx.MockTransport(
                    success_handler
                )
            )

            response = await client.post(
                publish_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                json={
                    "activation": activations[first_id],
                    "confirmation":
                        confirmations[
                            first_id
                        ],
                    "content_hash":
                        hashes[
                            first_id
                        ],
                },
            )

            if response.status_code != 200:
                raise AssertionError(
                    "success /publish HTTP "
                    f"{response.status_code}"
                )

            success_body = (
                response.json()
            )

            if (
                success_body.get(
                    "status"
                )
                != "published"
            ):
                raise AssertionError(
                    "success status not published"
                )

            if (
                success_body.get(
                    "provider_post_id"
                )
                != "mock_page_mock_success"
            ):
                raise AssertionError(
                    "provider post ID mismatch"
                )

            if (
                success_body.get(
                    "reconciliation_required"
                )
                is not False
            ):
                raise AssertionError(
                    "success incorrectly requires reconciliation"
                )

            if await redis_client.exists(
                _key(
                    confirmations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "success confirmation not consumed"
                )

            stored = await load_publication(
                first_id
            )

            if stored is None:
                raise AssertionError(
                    "success Publication missing"
                )

            if (
                stored.status
                != PublicationStatus.published
            ):
                raise AssertionError(
                    "success durable status mismatch"
                )

            if stored.publish_attempts != 1:
                raise AssertionError(
                    "success attempt count mismatch"
                )

            if (
                stored.publish_triggered_by_user_id
                != user_id
            ):
                raise AssertionError(
                    "success operator audit mismatch"
                )

            if (
                stored.publish_triggered_at
                is None
            ):
                raise AssertionError(
                    "success trigger timestamp missing"
                )

            if (
                stored.provider_post_id
                != "mock_page_mock_success"
            ):
                raise AssertionError(
                    "success provider ID not durable"
                )

            if stored.published_at is None:
                raise AssertionError(
                    "success published_at missing"
                )

            if mock_calls["success"] != 1:
                raise AssertionError(
                    "success provider call count mismatch"
                )

            if durable_claim_observed is not True:
                raise AssertionError(
                    "durable claim was not observed"
                )

            print(
                "Real durable PostgreSQL claim before provider: PASS"
            )
            print(
                "Mock success -> HTTP 200 / published: PASS"
            )
            print(
                "Success durable operator audit: PASS"
            )
            print(
                "Success confirmation GETDEL: PASS"
            )
            if await redis_client.exists(
                _activation_key(
                    activations[
                        first_id
                    ]
                )
            ):
                raise AssertionError(
                    "success activation not consumed"
                )

            print(
                "Success activation GETDEL: PASS"
            )

            #
            # DEFINITE PROVIDER REJECTION
            #
            second_id = (
                publication_ids[1]
            )

            publications.settings.meta_publish_canary_workspace_id = (
                workspace_id
            )

            publications.settings.meta_publish_canary_publication_id = (
                second_id
            )

            second_url = (
                f"/api/workspaces/{workspace_id}"
                f"/publications/{second_id}"
                "/publish"
            )

            provider_secret = (
                "SECRET_PROVIDER_INTERNAL_DETAIL"
            )

            async def rejection_handler(
                request: httpx.Request,
            ):
                mock_calls[
                    "rejection"
                ] += 1

                expected_path = (
                    f"/v23.0/{page_id}/feed"
                )

                if (
                    request.url.path
                    != expected_path
                ):
                    raise AssertionError(
                        "rejection Meta path mismatch"
                    )

                if (
                    "access_token"
                    in request.url.params
                ):
                    raise AssertionError(
                        "rejection token leaked into URL"
                    )

                authorization = (
                    request.headers.get(
                        "Authorization",
                        "",
                    )
                )

                if not authorization.startswith(
                    "Bearer "
                ):
                    raise AssertionError(
                        "rejection Bearer missing"
                    )

                form = parse_qs(
                    request.content.decode(
                        "utf-8"
                    )
                )

                if (
                    form.get(
                        "message"
                    )
                    != [
                        MESSAGES[1]
                    ]
                ):
                    raise AssertionError(
                        "rejection message mismatch"
                    )

                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message":
                                provider_secret,
                            "type":
                                "OAuthException",
                            "code":
                                200,
                            "error_subcode":
                                2018001,
                        }
                    },
                    request=request,
                )

            current_transport[
                "value"
            ] = MetaGraphHTTPTransport(
                transport=httpx.MockTransport(
                    rejection_handler
                )
            )

            response = await client.post(
                second_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                json={
                    "activation": activations[second_id],
                    "confirmation":
                        confirmations[
                            second_id
                        ],
                    "content_hash":
                        hashes[
                            second_id
                        ],
                },
            )

            if response.status_code != 502:
                raise AssertionError(
                    "provider rejection HTTP "
                    f"{response.status_code}"
                )

            if (
                provider_secret
                in response.text
            ):
                raise AssertionError(
                    "provider secret leaked to HTTP response"
                )

            if await redis_client.exists(
                _key(
                    confirmations[
                        second_id
                    ]
                )
            ):
                raise AssertionError(
                    "rejection confirmation not consumed"
                )

            stored = await load_publication(
                second_id
            )

            if stored is None:
                raise AssertionError(
                    "rejection Publication missing"
                )

            if (
                stored.status
                != PublicationStatus.failed
            ):
                raise AssertionError(
                    "provider rejection not durable failed"
                )

            if stored.publish_attempts != 1:
                raise AssertionError(
                    "rejection attempt count mismatch"
                )

            if (
                stored.publish_triggered_by_user_id
                != user_id
            ):
                raise AssertionError(
                    "rejection operator audit mismatch"
                )

            if (
                stored.publish_triggered_at
                is None
            ):
                raise AssertionError(
                    "rejection trigger timestamp missing"
                )

            if (
                provider_secret
                in str(
                    stored.last_error
                    or ""
                )
            ):
                raise AssertionError(
                    "provider secret persisted"
                )

            if stored.provider_post_id is not None:
                raise AssertionError(
                    "rejection stored provider post ID"
                )

            if mock_calls["rejection"] != 1:
                raise AssertionError(
                    "rejection provider call count mismatch"
                )

            print(
                "Mock 400 -> HTTP 502 / failed: PASS"
            )
            print(
                "Provider rejection secret isolation: PASS"
            )
            print(
                "Rejection durable operator audit: PASS"
            )
            if await redis_client.exists(
                _activation_key(
                    activations[
                        second_id
                    ]
                )
            ):
                raise AssertionError(
                    "rejection activation not consumed"
                )

            print(
                "Rejection activation GETDEL: PASS"
            )

            #
            # OUTCOME UNKNOWN
            #
            third_id = (
                publication_ids[2]
            )

            publications.settings.meta_publish_canary_workspace_id = (
                workspace_id
            )

            publications.settings.meta_publish_canary_publication_id = (
                third_id
            )

            third_url = (
                f"/api/workspaces/{workspace_id}"
                f"/publications/{third_id}"
                "/publish"
            )

            timeout_secret = (
                "SECRET_TIMEOUT_INTERNAL_DETAIL"
            )

            async def unknown_handler(
                request: httpx.Request,
            ):
                mock_calls[
                    "unknown"
                ] += 1

                expected_path = (
                    f"/v23.0/{page_id}/feed"
                )

                if (
                    request.url.path
                    != expected_path
                ):
                    raise AssertionError(
                        "unknown Meta path mismatch"
                    )

                if (
                    "access_token"
                    in request.url.params
                ):
                    raise AssertionError(
                        "unknown token leaked into URL"
                    )

                authorization = (
                    request.headers.get(
                        "Authorization",
                        "",
                    )
                )

                if not authorization.startswith(
                    "Bearer "
                ):
                    raise AssertionError(
                        "unknown Bearer missing"
                    )

                form = parse_qs(
                    request.content.decode(
                        "utf-8"
                    )
                )

                if (
                    form.get(
                        "message"
                    )
                    != [
                        MESSAGES[2]
                    ]
                ):
                    raise AssertionError(
                        "unknown message mismatch"
                    )

                raise httpx.ReadTimeout(
                    timeout_secret,
                    request=request,
                )

            current_transport[
                "value"
            ] = MetaGraphHTTPTransport(
                transport=httpx.MockTransport(
                    unknown_handler
                )
            )

            response = await client.post(
                third_url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                json={
                    "activation": activations[third_id],
                    "confirmation":
                        confirmations[
                            third_id
                        ],
                    "content_hash":
                        hashes[
                            third_id
                        ],
                },
            )

            if response.status_code != 202:
                raise AssertionError(
                    "unknown outcome HTTP "
                    f"{response.status_code}"
                )

            unknown_body = (
                response.json()
            )

            if (
                unknown_body.get(
                    "status"
                )
                != "publishing"
            ):
                raise AssertionError(
                    "unknown status not publishing"
                )

            if (
                unknown_body.get(
                    "reconciliation_required"
                )
                is not True
            ):
                raise AssertionError(
                    "unknown reconciliation flag missing"
                )

            if (
                timeout_secret
                in response.text
            ):
                raise AssertionError(
                    "timeout secret leaked to HTTP"
                )

            if await redis_client.exists(
                _key(
                    confirmations[
                        third_id
                    ]
                )
            ):
                raise AssertionError(
                    "unknown confirmation not consumed"
                )

            stored = await load_publication(
                third_id
            )

            if stored is None:
                raise AssertionError(
                    "unknown Publication missing"
                )

            if (
                stored.status
                != PublicationStatus.publishing
            ):
                raise AssertionError(
                    "unknown outcome not durable publishing"
                )

            if stored.publish_attempts != 1:
                raise AssertionError(
                    "unknown attempt count mismatch"
                )

            if (
                stored.publish_triggered_by_user_id
                != user_id
            ):
                raise AssertionError(
                    "unknown operator audit mismatch"
                )

            if (
                stored.publish_triggered_at
                is None
            ):
                raise AssertionError(
                    "unknown trigger timestamp missing"
                )

            if (
                timeout_secret
                in str(
                    stored.last_error
                    or ""
                )
            ):
                raise AssertionError(
                    "timeout secret persisted"
                )

            if stored.provider_post_id is not None:
                raise AssertionError(
                    "unknown stored provider post ID"
                )

            if stored.published_at is not None:
                raise AssertionError(
                    "unknown incorrectly marked published"
                )

            if mock_calls["unknown"] != 1:
                raise AssertionError(
                    "unknown provider call count mismatch"
                )

            print(
                "Mock timeout -> HTTP 202 / reconciliation: PASS"
            )
            print(
                "Outcome unknown remains publishing: PASS"
            )
            print(
                "Unknown durable operator audit: PASS"
            )
            if await redis_client.exists(
                _activation_key(
                    activations[
                        third_id
                    ]
                )
            ):
                raise AssertionError(
                    "unknown activation not consumed"
                )

            print(
                "Unknown activation GETDEL: PASS"
            )
            print(
                "Unknown automatic retry introduced: NO"
            )

            #
            # Cross-scenario execution counts.
            #
            if counting_cipher.calls != 3:
                raise AssertionError(
                    "credential decrypt count mismatch: "
                    f"{counting_cipher.calls}"
                )

            if factory_calls != 4:
                raise AssertionError(
                    "transport factory count mismatch: "
                    f"{factory_calls}"
                )

            if mock_calls != {
                "success": 1,
                "rejection": 1,
                "unknown": 1,
            }:
                raise AssertionError(
                    "mock provider call counts mismatch"
                )

            print(
                "Real credential decrypt path x3: PASS"
            )
            print(
                "Mock provider execution exactly x3: PASS"
            )
            print(
                "Transport factory count including stale gate: 4"
            )

        access_token = None

    finally:
        #
        # Restore every process-local override before cleanup.
        #
        access_token = None

        publications.settings.meta_publish_canary_publication_id = (
            original_canary_publication_id
        )

        publications.settings.meta_publish_canary_workspace_id = (
            original_canary_workspace_id
        )

        publications.settings.meta_publish_transport_enabled = (
            original_transport_enabled
        )

        publications.settings.real_publish_enabled = (
            original_enabled
        )

        publications.get_publication_publish_transport = (
            original_factory
        )

        publications.create_publication_activation = (
            original_create_activation
        )

        executor.oauth_token_cipher = (
            original_cipher
        )

        cleanup_errors = []

        #
        # Remove any confirmation still present. Successful,
        # rejected and unknown executions should already have
        # consumed theirs via atomic GETDEL. The kill-switch /
        # stale-hash confirmation may still exist if a failure
        # interrupted the test before successful execution.
        #
        try:
            for confirmation in tuple(
                confirmations.values()
            ):
                await redis_client.delete(
                    _key(
                        confirmation
                    )
                )

            for activation_value in tuple(
                activations.values()
            ):
                await redis_client.delete(
                    _activation_key(
                        activation_value
                    )
                )

        except Exception:
            cleanup_errors.append(
                "redis"
            )

        #
        # Delete only Publications created by this test.
        #
        try:
            async with session() as db:
                await db.execute(
                    delete(Publication).where(
                        Publication.id.in_(
                            publication_ids
                        )
                    )
                )

                await db.commit()
        except Exception:
            cleanup_errors.append(
                "database"
            )

        #
        # Verify the temporary Publication rows are gone.
        #
        try:
            async with session() as db:
                result = await db.execute(
                    select(Publication.id).where(
                        Publication.id.in_(
                            publication_ids
                        )
                    )
                )

                remaining = list(
                    result.scalars().all()
                )

                if remaining:
                    cleanup_errors.append(
                        "database-verification"
                    )
        except Exception:
            cleanup_errors.append(
                "database-verification"
            )

        if cleanup_errors:
            raise AssertionError(
                "D-B cleanup failed: "
                + ",".join(
                    cleanup_errors
                )
            )

        print(
            "Process-local kill switch restored: PASS"
        )
        print(
            "Publish transport factory restored: PASS"
        )
        print(
            "OAuth cipher restored: PASS"
        )
        print(
            "Temporary Redis confirmation/activation cleanup: PASS"
        )
        print(
            "Temporary PostgreSQL Publications cleanup: PASS"
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )

    print()
    print(
        "v0.13E-E-C ACTIVATED HTTP END-TO-END GATE: PASS"
    )
    print(
        "Real authentication: PASS"
    )
    print(
        "Real publish-confirmation issuance: PASS"
    )
    print(
        "Real publish-activation issuance: PASS"
    )
    print(
        "Owner-only activation operator: PASS"
    )
    print(
        "Hashed activation Redis keys: PASS"
    )
    print(
        "Activation GETDEL before confirmation/executor: PASS"
    )
    print(
        "Confirmation HTTP no-store: PASS"
    )
    print(
        "Real Redis GETDEL consumption: PASS"
    )
    print(
        "Hashed confirmation Redis keys: PASS"
    )
    print(
        "Kill switch before transport construction: PASS"
    )
    print(
        "Stale hash before confirmation consumption: PASS"
    )
    print(
        "Real durable PostgreSQL claim: PASS"
    )
    print(
        "Real credential decrypt path: PASS"
    )
    print(
        "Mock success -> HTTP 200 / published: PASS"
    )
    print(
        "Mock 400 -> HTTP 502 / failed: PASS"
    )
    print(
        "Mock timeout -> HTTP 202 / reconciliation: PASS"
    )
    print(
        "Durable operator audit: PASS"
    )
    print(
        "Automatic retry introduced: NO"
    )
    print(
        "Real Meta network calls: NONE"
    )
    print(
        "Facebook posts created: NONE"
    )


# v0.14 Step 4C-B2-D2-R3-D2 disposable synthetic identity fixture
def test_v014_synthetic_identity_main_equivalence():
    import asyncio
    from uuid import uuid4

    from sqlalchemy import delete

    from app.models.membership import (
        Membership,
        MembershipRole,
    )
    from app.models.social_account import (
        SocialAccount,
        SocialAccountStatus,
        SocialPlatform,
    )
    from app.models.user import User
    from app.models.workspace import Workspace

    async def run():
        user_id = RUN_USER_ID
        workspace_id = RUN_WORKSPACE_ID
        membership_id = RUN_MEMBERSHIP_ID
        social_account_id = RUN_SOCIAL_ACCOUNT_ID

        unique = integration_token("publish-http-fixture")

        plaintext_token = (
            "v014-disposable-synthetic-token-"
            + unique
        )

        ciphertext = (
            executor
            .oauth_token_cipher
            .encrypt(
                plaintext_token
            )
        )

        if not ciphertext:
            raise AssertionError(
                "synthetic ciphertext missing"
            )

        if ciphertext == plaintext_token:
            raise AssertionError(
                "synthetic token was not encrypted"
            )

        recovered = (
            executor
            .oauth_token_cipher
            .decrypt(
                ciphertext
            )
        )

        if recovered != plaintext_token:
            raise AssertionError(
                "synthetic token cipher roundtrip failed"
            )

        user = User(
            id=user_id,
            email=(
                "v014-r3-d2-"
                + unique
                + "@example.invalid"
            ),
            is_active=True,
        )

        workspace = Workspace(
            id=workspace_id,
            name=(
                "v014 R3 D2 "
                + unique
            ),
            slug=(
                "v014-r3-d2-"
                + unique
            ),
        )

        membership = Membership(
            id=membership_id,
            user_id=user_id,
            workspace_id=workspace_id,
            role=MembershipRole.owner,
        )

        social_account = SocialAccount(
            id=social_account_id,
            workspace_id=workspace_id,
            platform=SocialPlatform.facebook,
            status=SocialAccountStatus.connected,
            platform_account_id=RUN_PROVIDER_ID,
            account_name=(
                "v014 synthetic page "
                + unique
            ),
            access_token_ciphertext=ciphertext,
            is_active=True,
        )

        try:
            async with session() as db:
                db.add(user)
                db.add(workspace)

                await db.flush()

                db.add(membership)
                db.add(social_account)

                await db.commit()

            #
            # Existing integration contract.
            # This is the exact main() already present
            # in the test file.
            #
            await main()

        finally:
            #
            # Disposable DB only.
            # Delete in FK-safe order.
            #
            async with session() as db:
                await db.execute(
                    delete(
                        SocialAccount
                    ).where(
                        SocialAccount.id
                        == social_account_id
                    )
                )

                await db.execute(
                    delete(
                        Membership
                    ).where(
                        Membership.id
                        == membership_id
                    )
                )

                await db.execute(
                    delete(
                        Workspace
                    ).where(
                        Workspace.id
                        == workspace_id
                    )
                )

                await db.execute(
                    delete(
                        User
                    ).where(
                        User.id
                        == user_id
                    )
                )

                await db.commit()

    asyncio.run(run())
