import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, LargeBinary, Text
from sqlalchemy.dialects.postgresql import UUID
from .base import Base


class CRPRecord(Base):
    __tablename__ = "crp_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    drone_id = Column(String(64), nullable=False, index=True)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    used_at = Column(DateTime(timezone=True), nullable=True)


class DroneIdentity(Base):
    __tablename__ = "drone_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(String(64), unique=True, nullable=False, index=True)
    puf_seed = Column(Integer, nullable=False)
    challenge_length = Column(Integer, default=64)
    registered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_auth = Column(DateTime(timezone=True), nullable=True)


class DroneSession(Base):
    __tablename__ = "drone_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(String(64), nullable=False, index=True)
    session_key = Column(Text, nullable=False)
    challenge_used = Column(Text, nullable=False)
    response_expected = Column(Text, nullable=False)
    established_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True)


class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(String(64), nullable=False, index=True)
    encrypted_payload = Column(Text, nullable=False)
    iv = Column(Text, nullable=False)
    gps_lat = Column(Float, nullable=True)
    gps_lon = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    battery = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    verified = Column(Boolean, default=False)
