"""Create the first local administrator without exposing a password in logs."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.core.security import hash_password, normalize_login  # noqa: E402
from app.database.session import create_engine_and_session  # noqa: E402
from app.models import AccountModel, AccountStatus  # noqa: E402
from app.services.audit_service import record_audit  # noqa: E402
from sqlalchemy import select  # noqa: E402


async def create_admin(login: str, display_name: str, password: str) -> None:
    settings = Settings()
    engine, session_factory = create_engine_and_session(settings.active_database_url)
    try:
        async with session_factory() as db:
            normalized = normalize_login(login)
            existing = (
                await db.execute(
                    select(AccountModel).where(
                        AccountModel.login_normalized == normalized
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise SystemExit("登录名已存在，未创建账号。")
            now = datetime.now(UTC)
            account = AccountModel(
                id=f"user_{uuid4().hex}",
                login=login.strip(),
                login_normalized=normalized,
                display_name=display_name.strip() or login.strip(),
                password_hash=hash_password(
                    password,
                    n_log2=settings.auth_scrypt_n_log2,
                    r=settings.auth_scrypt_r,
                    p=settings.auth_scrypt_p,
                ),
                role="admin",
                status=AccountStatus.ACTIVE,
                password_changed_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(account)
            await db.flush()
            record_audit(
                db,
                None,
                action="admin.bootstrap",
                target_type="account",
                target_id=account.id,
                details={"role": account.role},
            )
            await db.commit()
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an XZD administrator account")
    parser.add_argument("--login", required=True)
    parser.add_argument("--display-name", default="")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read password and confirmation from stdin for isolated automation.",
    )
    args = parser.parse_args()
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        confirmation = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("Admin password (min 12 characters): ")
        confirmation = getpass.getpass("Repeat admin password: ")
    if password != confirmation:
        print("两次密码不一致。", file=sys.stderr)
        return 2
    if len(password) < 12:
        print("密码至少需要 12 个字符。", file=sys.stderr)
        return 2
    asyncio.run(create_admin(args.login, args.display_name, password))
    print("管理员账号创建成功。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
