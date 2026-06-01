import json
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.entities import (
    ChallengeResponsePair, DroneIdentity, TelemetryPacket,
    EncryptedPayload, DroneSession, AttackLog,
)
from ...domain.ports import (
    CRPRepository, DroneRepository, SessionRepository,
    TelemetryRepository, AttackRepository,
)
from .models import (
    CRPRecordModel, DroneIdentityModel, DroneSessionModel,
    TelemetryLogModel, AttackLogModel,
)


class SQLAlchemyCRPRepository(CRPRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, crp: ChallengeResponsePair) -> None:
        model = CRPRecordModel(
            challenge=json.dumps(crp.challenge),
            response=crp.response,
            drone_id=crp.drone_id,
            used=crp.used,
        )
        self.session.add(model)
        await self.session.commit()

    async def find_by_challenge(self, drone_id: str, challenge: list) -> Optional[ChallengeResponsePair]:
        challenge_str = json.dumps(challenge)
        result = await self.session.execute(
            select(CRPRecordModel).where(
                CRPRecordModel.drone_id == drone_id,
                CRPRecordModel.challenge == challenge_str,
            )
        )
        model = result.scalar_one_or_none()
        if model:
            return ChallengeResponsePair(
                challenge=json.loads(model.challenge),
                response=model.response,
                drone_id=model.drone_id,
                used=model.used,
            )
        return None

    async def mark_used(self, crp_id: str) -> None:
        from datetime import datetime, timezone
        await self.session.execute(
            update(CRPRecordModel)
            .where(CRPRecordModel.id == crp_id)
            .values(used=True, used_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

    async def list_by_drone(self, drone_id: str, limit: int = 50) -> List[ChallengeResponsePair]:
        result = await self.session.execute(
            select(CRPRecordModel)
            .where(CRPRecordModel.drone_id == drone_id)
            .limit(limit)
        )
        return [
            ChallengeResponsePair(
                challenge=json.loads(m.challenge),
                response=m.response,
                drone_id=m.drone_id,
                used=m.used,
            )
            for m in result.scalars().all()
        ]


class SQLAlchemyDroneRepository(DroneRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, identity: DroneIdentity) -> None:
        model = DroneIdentityModel(
            drone_id=identity.drone_id,
            puf_seed=identity.puf_seed,
            challenge_length=identity.challenge_length,
        )
        self.session.add(model)
        await self.session.commit()

    async def find_by_id(self, drone_id: str) -> Optional[DroneIdentity]:
        result = await self.session.execute(
            select(DroneIdentityModel).where(DroneIdentityModel.drone_id == drone_id)
        )
        m = result.scalar_one_or_none()
        if m:
            return DroneIdentity(
                drone_id=m.drone_id,
                puf_seed=m.puf_seed,
                challenge_length=m.challenge_length,
            )
        return None

    async def exists(self, drone_id: str) -> bool:
        result = await self.session.execute(
            select(DroneIdentityModel).where(DroneIdentityModel.drone_id == drone_id)
        )
        return result.scalar_one_or_none() is not None


class SQLAlchemySessionRepository(SessionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, session_entity: DroneSession) -> None:
        model = DroneSessionModel(
            drone_id=session_entity.drone_id,
            session_key=session_entity.session_key,
            challenge_used=json.dumps(session_entity.challenge_used),
            response_expected=session_entity.response_expected,
            active=session_entity.active,
        )
        self.session.add(model)
        await self.session.commit()

    async def find_active(self, drone_id: str) -> Optional[DroneSession]:
        result = await self.session.execute(
            select(DroneSessionModel).where(
                DroneSessionModel.drone_id == drone_id,
                DroneSessionModel.active == True,
            ).order_by(DroneSessionModel.established_at.desc())
        )
        m = result.scalar_one_or_none()
        if m:
            return DroneSession(
                drone_id=m.drone_id,
                session_key=m.session_key,
                challenge_used=json.loads(m.challenge_used),
                response_expected=m.response_expected,
                active=m.active,
            )
        return None

    async def deactivate(self, drone_id: str) -> None:
        await self.session.execute(
            update(DroneSessionModel)
            .where(DroneSessionModel.drone_id == drone_id, DroneSessionModel.active == True)
            .values(active=False)
        )
        await self.session.commit()


class SQLAlchemyTelemetryRepository(TelemetryRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, packet: TelemetryPacket, encrypted: EncryptedPayload) -> None:
        model = TelemetryLogModel(
            drone_id=packet.drone_id,
            encrypted_payload=encrypted.ciphertext,
            iv=encrypted.iv,
            gps_lat=packet.gps_lat,
            gps_lon=packet.gps_lon,
            altitude=packet.altitude,
            battery=packet.battery,
            verified=True,
        )
        self.session.add(model)
        await self.session.commit()

    async def list_by_drone(self, drone_id: str, limit: int = 100) -> list:
        result = await self.session.execute(
            select(TelemetryLogModel)
            .where(TelemetryLogModel.drone_id == drone_id)
            .limit(limit)
        )
        return result.scalars().all()


class SQLAlchemyAttackRepository(AttackRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, log: AttackLog) -> None:
        model = AttackLogModel(
            fake_seed=log.fake_seed,
            fake_response=log.fake_response,
            real_response=log.real_response,
            detected=log.detected,
        )
        self.session.add(model)
        await self.session.commit()

    async def list_all(self, limit: int = 50) -> List[AttackLog]:
        result = await self.session.execute(
            select(AttackLogModel).limit(limit)
        )
        return [
            AttackLog(
                fake_seed=m.fake_seed,
                fake_response=m.fake_response,
                real_response=m.real_response,
                detected=m.detected,
            )
            for m in result.scalars().all()
        ]
