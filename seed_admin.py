import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import User, Role
from app.security import hash_password

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def main():
    db = SessionLocal()

    try:
        email = "admin@gym.com"
        password = "Admin123!"

        exists = db.query(User).filter(User.email == email).first()
        if exists:
            print("Admin ya existe:", email)
            return

        u = User(
            email=email,
            first_name="Admin",
            last_name="Principal",
            dni=None,
            birth_date=None,
            address="",
            full_name="Administrador",
            role=Role.ADMINISTRADOR,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(u)
        db.commit()

        print("✅ Admin creado")
        print("   Email:", email)
        print("   Pass :", password)
    finally:
        db.close()


if __name__ == "__main__":
    main()