import argparse
import logging

from .admin_defaults import seed_admin_defaults, seed_bootstrap_admin
from .database import Base, SessionLocal, engine
from .schema_compat import ensure_sqlite_admin_columns

logger = logging.getLogger(__name__)


def run_seed(only: str = "all") -> dict:
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_admin_columns(engine)
    db = SessionLocal()
    try:
        result: dict[str, str] = {}
        if only in {"all", "rates", "templates", "settings", "service-types", "classification"}:
            seed_admin_defaults(db)
            result["defaults"] = "seeded"
        if only in {"all", "admin"}:
            user = seed_bootstrap_admin(db)
            result["admin"] = user.email if user else "skipped"
        return result
    except Exception:
        logger.exception("Seed command failed")
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Clinical AI Webapp defaults")
    parser.add_argument("--only", choices=["all", "rates", "templates", "admin", "settings", "service-types", "classification"], default="all")
    args = parser.parse_args()
    print(run_seed(args.only))


if __name__ == "__main__":
    main()
