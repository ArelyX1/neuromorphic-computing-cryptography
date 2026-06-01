from typing import Optional, List
from ..domain.entities import (
    DroneIdentity, TelemetryPacket, EncryptedPayload,
    ChallengeResponsePair, AttackLog, DroneStatus,
)
from ..domain.ports import (
    CRPRepository, DroneRepository, SessionRepository,
    TelemetryRepository, AttackRepository, PUFPort,
)
from ..domain.services import DroneAuthService, TelemetryService, AttackDetectionService


class AuthenticateDroneUseCase:
    def __init__(self, auth_service: DroneAuthService):
        self.auth_service = auth_service

    async def execute(self, drone_id: str) -> dict:
        success, session_key, _ = await self.auth_service.authenticate(drone_id)
        return {
            "success": success,
            "drone_id": drone_id,
            "session_key": session_key or "",
            "message": "Autenticación PUF exitosa" if success else "Falló autenticación PUF",
        }


class SendTelemetryUseCase:
    def __init__(self, telemetry_service: TelemetryService):
        self.telemetry_service = telemetry_service

    async def execute(self, packet: TelemetryPacket) -> EncryptedPayload:
        return await self.telemetry_service.send_telemetry(packet)


class SimulateAttackUseCase:
    def __init__(self, attack_service: AttackDetectionService, puf: PUFPort):
        self.attack_service = attack_service
        self.puf = puf

    def execute(self, fake_seed: int) -> AttackLog:
        challenge = self.puf.generate_challenge()
        real_response = self.puf.evaluate(challenge, noisy=False)
        return self.attack_service.simulate_attack(fake_seed, challenge.tolist() if hasattr(challenge, 'tolist') else challenge, real_response)


class GetDroneStatusUseCase:
    async def execute(self) -> DroneStatus:
        return DroneStatus()
