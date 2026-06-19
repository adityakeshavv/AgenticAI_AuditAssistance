from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models import TransactionMaster


def main() -> None:
    try:
        with SessionLocal() as db:
            transactions = db.query(TransactionMaster).limit(5).all()

            for tx in transactions:
                print(tx.transaction_id, tx.amount, tx.status)
    except SQLAlchemyError as exc:
        print("Database connection/query failed.")
        print("Check AUDIT_DATABASE_URL in your .env file.")
        print(str(exc))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
