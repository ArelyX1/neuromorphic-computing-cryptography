from typing import Optional, List, Tuple
from .entities import (
    ChallengeResponsePair, DroneIdentity, TelemetryPacket,
    EncryptedPayload, DroneSession, AttackLog, DroneStatus,
)
from .ports import (
    CRPRepository, DroneRepository, SessionRepository,
    TelemetryRepository, AttackRepository, PUFPort,
)


class DroneAuthService:
    def __init__(
        self,
        crp_repo: CRPRepository,
        drone_repo: DroneRepository,
        session_repo: SessionRepository,
        puf: PUFPort,
    ):
        self.crp_repo = crp_repo
        self.drone_repo = drone_repo
        self.session_repo = session_repo
        self.puf = puf

    async def authenticate(self, drone_id: str) -> Tuple[bool, Optional[str], Optional[EncryptedPayload]]:
        exists = await self.drone_repo.exists(drone_id)
        if not exists:
            identity = DroneIdentity(drone_id=drone_id, puf_seed=abs(hash(drone_id)) % 1000)
            await self.drone_repo.save(identity)

        challenge = self.puf.generate_challenge()
        response = self.puf.evaluate(challenge, noisy=True)

        crp = ChallengeResponsePair(
            challenge=challenge,
            response=response,
            drone_id=drone_id,
        )
        await self.crp_repo.save(crp)

        if response == response:
            session = DroneSession(
                drone_id=drone_id,
                session_key=f"session_{drone_id}_{abs(hash(str(challenge)))}",
                challenge_used=challenge,
                response_expected=response,
            )
            await self.session_repo.save(session)
            return True, session.session_key, None

        return False, None, None


class TelemetryService:
    def __init__(self, telemetry_repo: TelemetryRepository, session_repo: SessionRepository, puf: PUFPort):
        self.telemetry_repo = telemetry_repo
        self.session_repo = session_repo
        self.puf = puf

    async def send_telemetry(self, packet: TelemetryPacket) -> EncryptedPayload:
        session = await self.session_repo.find_active(packet.drone_id)
        challenge = session.challenge_used if session else self.puf.generate_challenge()

        plaintext = packet.to_dict()
        import json
        payload = json.dumps(plaintext).encode("utf-8")

        encrypted = self.puf.encrypt(payload, challenge)
        await self.telemetry_repo.save(packet, encrypted)
        return encrypted


class AttackDetectionService:
    def __init__(self, attack_repo: AttackRepository, puf: PUFPort):
        self.attack_repo = attack_repo
        self.puf = puf

    async def simulate_attack(self, fake_seed: int, real_challenge: list, real_response: int) -> AttackLog:
        import numpy as np
        from puf_crypto.simulation.hybrid_puf import HybridPUF

        fake_puf = HybridPUF(n=64, k=4, seed=fake_seed, preprocessor="vigenere")
        fake_challenge = np.array(real_challenge, dtype=np.int8)
        fake_response = int(fake_puf.eval(fake_challenge, noisy=False))
        detected = fake_response != real_response

        log = AttackLog(
            fake_seed=fake_seed,
            fake_response=fake_response,
            real_response=real_response,
            detected=detected,
        )
        if self.attack_repo:
            await self.attack_repo.save(log)
        return log
