import uuid
from sqlalchemy import Column, String, Integer, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    file_name = Column(String(255))
    file_size_bytes = Column(BigInteger, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    language_code = Column(String(10), default="en-IN")
    status = Column(String(20), default="uploading")
    stage = Column(String(50), nullable=True)
    progress_percent = Column(Integer, default=0)
    sarvam_job_id = Column(String(100), nullable=True)
    transcript_text = Column(Text, nullable=True)
    analysis_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    chunks = relationship(
        "TranscriptChunk",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    chunk_index = Column(Integer)
    start_ms = Column(Integer)
    end_ms = Column(Integer)
    text = Column(Text)
    embedding_id = Column(String(100), nullable=True)

    session = relationship("Session", back_populates="chunks")
