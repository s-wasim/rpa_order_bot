from .db import init_db, get_session, seed_inventory


def main():
    init_db()
    with get_session() as session:
        seed_inventory(session)
    print("Database initialized and seeded.")


if __name__ == "__main__":
    main()
