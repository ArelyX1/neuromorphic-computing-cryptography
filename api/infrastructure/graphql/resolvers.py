import json
import numpy as np
from typing import List, Optional
from strawberry.types import Info

from ...domain.entities import (
    TelemetryPacket, DroneIdentity, ChallengeResponsePair,
)
from ...domain.services import DroneAuthService, TelemetryService, AttackDetectionService
from ...application.use_cases import (
    AuthenticateDroneUseCase, SendTelemetryUseCase,
    SimulateAttackUseCase, GetDroneStatusUseCase,
)
from ..db.repositories import (
    SQLAlchemyCRPRepository, SQLAlchemyDroneRepository,
    SQLAlchemySessionRepository, SQLAlchemyTelemetryRepository,
    SQLAlchemyAttackRepository,
)
from ..puf_adapter import HybridPUFAdapter
from .schema import (
    AuthResult, EncryptedPayloadType, TelemetryType,
    AttackLogType, DroneStatusType, TelemetryInput,
)


class ResolverContext:
    def __init__(self):
        self.puf = HybridPUFAdapter()
        self._deps = None

    @property
    def deps(self):
        if self._deps is None:
            from ...infrastructure.db.config import AsyncSessionLocal
            import asyncio
            self._deps = AsyncSessionLocal
        return self._deps

    async def get_repos(self):
        from ...infrastructure.db.config import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            crp_repo = SQLAlchemyCRPRepository(session)
            drone_repo = SQLAlchemyDroneRepository(session)
            session_repo = SQLAlchemySessionRepository(session)
            telemetry_repo = SQLAlchemyTelemetryRepository(session)
            attack_repo = SQLAlchemyAttackRepository(session)
            yield crp_repo, drone_repo, session_repo, telemetry_repo, attack_repo


ctx = ResolverContext()


async def resolve_auth(drone_id: str) -> AuthResult:
    async with ctx.deps() as session:
        crp_repo = SQLAlchemyCRPRepository(session)
        drone_repo = SQLAlchemyDroneRepository(session)
        session_repo = SQLAlchemySessionRepository(session)
        auth_service = DroneAuthService(crp_repo, drone_repo, session_repo, ctx.puf)
        use_case = AuthenticateDroneUseCase(auth_service)
        result = await use_case.execute(drone_id)
        return AuthResult(**result)


async def resolve_send_telemetry(input: TelemetryInput) -> EncryptedPayloadType:
    async with ctx.deps() as session:
        session_repo = SQLAlchemySessionRepository(session)
        telemetry_repo = SQLAlchemyTelemetryRepository(session)
        telemetry_service = TelemetryService(telemetry_repo, session_repo, ctx.puf)
        use_case = SendTelemetryUseCase(telemetry_service)
        packet = TelemetryPacket(
            drone_id=input.drone_id,
            gps_lat=input.gps_lat,
            gps_lon=input.gps_lon,
            altitude=input.altitude,
            speed=input.speed,
            battery=input.battery,
            heading=input.heading,
            timestamp=__import__('time').time(),
            status=input.status,
        )
        encrypted = await use_case.execute(packet)
        return EncryptedPayloadType(
            ciphertext=encrypted.ciphertext,
            iv=encrypted.iv,
            iv_cbc=encrypted.iv_cbc,
            nonce_ctr=encrypted.nonce_ctr,
            chacha_iv=encrypted.chacha_iv,
            drone_id=encrypted.drone_id,
            size=encrypted.size,
        )


def resolve_simulate_attack(fake_seed: int) -> AttackLogType:
    from ...infrastructure.db.config import AsyncSessionLocal
    attack_service = AttackDetectionService(None, ctx.puf)
    use_case = SimulateAttackUseCase(attack_service, ctx.puf)
    log = use_case.execute(fake_seed)
    return AttackLogType(
        fake_seed=log.fake_seed,
        fake_response=log.fake_response,
        real_response=log.real_response,
        detected=log.detected,
    )


async def resolve_get_telemetry(drone_id: str, limit: int = 50) -> List[TelemetryType]:
    async with ctx.deps() as session:
        repo = SQLAlchemyTelemetryRepository(session)
        logs = await repo.list_by_drone(drone_id, limit)
        return [
            TelemetryType(
                drone_id=log.drone_id,
                gps_lat=log.gps_lat or 0,
                gps_lon=log.gps_lon or 0,
                altitude=log.altitude or 0,
                battery=log.battery or 0,
                encrypted_payload=log.encrypted_payload[:32] + "...",
                verified=log.verified,
            )
            for log in logs
        ]


def resolve_drone_status() -> DroneStatusType:
    return DroneStatusType(
        authenticated=True,
        altitude=100.0,
        speed=15.0,
        battery=100.0,
        heading=0.0,
        gps_lat=-16.4090,
        gps_lon=-71.5374,
        signal_strength=85,
        packets_sent=0,
        attack_detected=False,
    )
