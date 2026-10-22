from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Engine, String, Text, Uuid, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.schemas import Document
from app.service import DependencyUnavailable


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PostgresRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(self, documents: list[Document]) -> list[Document]:
        try:
            with Session(self.engine) as session, session.begin():
                session.execute(
                    insert(DocumentRow)
                    .values([document.model_dump() for document in documents])
                    .on_conflict_do_nothing(index_elements=[DocumentRow.id])
                )
                rows = session.scalars(
                    select(DocumentRow).where(DocumentRow.id.in_([doc.id for doc in documents]))
                )
                saved = {row.id: Document.model_validate(row) for row in rows}
            return [saved[doc.id] for doc in documents]
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("PostgreSQL write failed") from exc

    def get(self, document_id: UUID) -> Document | None:
        try:
            with Session(self.engine) as session:
                row = session.get(DocumentRow, document_id)
                return Document.model_validate(row) if row is not None else None
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("PostgreSQL read failed") from exc

    def list(self, limit: int, offset: int) -> list[Document]:
        try:
            with Session(self.engine) as session:
                rows = session.scalars(
                    select(DocumentRow)
                    .order_by(DocumentRow.created_at, DocumentRow.id)
                    .limit(limit)
                    .offset(offset)
                )
                return [Document.model_validate(row) for row in rows]
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("PostgreSQL read failed") from exc

    def check_ready(self) -> None:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("PostgreSQL is not ready") from exc
