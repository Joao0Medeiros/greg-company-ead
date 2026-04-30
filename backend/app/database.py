from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# 🔥 pega a URL do banco (Render)
DATABASE_URL = os.getenv("DATABASE_URL")

# ⚠️ fallback (opcional pra rodar local)
if not DATABASE_URL:
    DATABASE_URL = "postgresql://greg:GnhHvftfTWvS1DdnV9y5w4cpGnB4o7pE@dpg-d7pm0pugvqtc73acqfc0-a.oregon-postgres.render.com/gregcompany"

# 🔧 engine do banco
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

# 🔗 sessão do banco
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 📦 base dos models (SQLAlchemy)
Base = declarative_base()

# 🔁 dependência do FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
