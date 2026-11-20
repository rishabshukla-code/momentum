"""Copy local SQLite history into the database in DATABASE_URL (e.g. SingleStore).

Run:  python -m momentum.migrate            (from sqlite:///momentum.db)
      python -m momentum.migrate --check    (only test the connection)
Rows that already exist in the target are skipped, so it is safe to run twice.
"""
import argparse

from sqlalchemy import func, insert, select, text

from . import config, store


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="sqlite:///momentum.db")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    target = store.engine
    host = target.url.host or target.url.database
    with target.connect() as c:
        version = c.execute(text("SELECT VERSION()" if target.dialect.name == "mysql"
                                 else "SELECT sqlite_version()")).scalar()
    print(f"connected to {target.dialect.name} at {host} (version {version})")
    store.init_db()
    print("tables ready:", ", ".join(store.meta.tables))
    if a.check:
        return
    if a.source == config.DATABASE_URL:
        raise SystemExit("source and target are the same database")

    src = store.make_engine(a.source)
    for table in (store.users, store.tasks, store.nudges):
        with src.connect() as s:
            rows = [dict(r) for r in s.execute(select(table)).mappings()]
        pk = list(table.primary_key.columns)[0]
        with target.begin() as t:
            have = set(t.execute(select(pk)).scalars())
            new = [r for r in rows if r[pk.name] not in have]
            if new:
                t.execute(insert(table), new)
            total = t.execute(select(func.count()).select_from(table)).scalar()
        print(f"{table.name}: copied {len(new)} of {len(rows)} rows (target now has {total})")


if __name__ == "__main__":
    main()
