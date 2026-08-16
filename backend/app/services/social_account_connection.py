from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_account import (
    SocialAccount,
    SocialAccountStatus,
    SocialPlatform,
    utcnow,
)
from app.services.meta_oauth import MetaManagedPage
from app.services.oauth_crypto import oauth_token_cipher


async def upsert_meta_page_connections(
    db: AsyncSession,
    workspace_id: UUID,
    pages: tuple[MetaManagedPage, ...],
    verified_scopes_by_page_id: dict[str, str],
) -> tuple[SocialAccount, ...]:
    accounts: list[SocialAccount] = []

    for page in pages:
        if not page.id:
            raise ValueError(
                "Meta Page id cannot be empty"
            )

        if not page.name:
            raise ValueError(
                "Meta Page name cannot be empty"
            )

        if not page.access_token:
            raise ValueError(
                "Meta Page access token cannot be empty"
            )

        verified_scopes = (
            verified_scopes_by_page_id.get(
                page.id
            )
        )

        if (
            not isinstance(
                verified_scopes,
                str,
            )
            or not verified_scopes.strip()
        ):
            raise ValueError(
                "Verified Meta Page scopes are required"
            )

        verified_scopes = (
            verified_scopes.strip()
        )

        # Plaintext Page token exists only in process memory.
        # Only Fernet ciphertext is assigned to ORM state.
        token_ciphertext = oauth_token_cipher.encrypt(
            page.access_token
        )

        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.workspace_id
                == workspace_id,
                SocialAccount.platform
                == SocialPlatform.facebook,
                SocialAccount.platform_account_id
                == page.id,
            )
        )

        account = result.scalar_one_or_none()

        if account is None:
            account = SocialAccount(
                workspace_id=workspace_id,
                platform=SocialPlatform.facebook,
                status=SocialAccountStatus.connected,
                platform_account_id=page.id,
                account_name=page.name,
                profile_url=(
                    f"https://www.facebook.com/"
                    f"{page.id}"
                ),
                scopes=verified_scopes,
                access_token_ciphertext=(
                    token_ciphertext
                ),
                refresh_token_ciphertext=None,
                token_expires_at=None,
                last_synced_at=utcnow(),
                last_error=None,
                is_active=True,
            )

            db.add(account)

        else:
            # Preserve brand_id and other user-managed
            # metadata on reconnect.
            account.status = (
                SocialAccountStatus.connected
            )
            account.account_name = page.name
            account.profile_url = (
                f"https://www.facebook.com/"
                f"{page.id}"
            )
            account.scopes = verified_scopes
            account.access_token_ciphertext = (
                token_ciphertext
            )
            account.refresh_token_ciphertext = None
            account.token_expires_at = None
            account.last_synced_at = utcnow()
            account.last_error = None
            account.is_active = True

        accounts.append(account)

    # Flush only. Transaction ownership remains with
    # the caller so callback persistence is atomic.
    await db.flush()

    return tuple(accounts)
