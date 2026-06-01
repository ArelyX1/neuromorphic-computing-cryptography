from abc import ABC, abstractmethod
from typing import Optional, List
from .entities import (
    ChallengeResponsePair, DroneIdentity, TelemetryPacket,
    EncryptedPayload, DroneSession, AttackLog, DroneStatus,
)


class CRPRepository(ABC):
    @abstractmethod
    async def save(self, crp: ChallengeResponsePair) -> None: ...

    @abstractmethod
    async def find_by_challenge(self, drone_id: str, challenge: list) -> Optional[ChallengeResponsePair]: ...

    @abstractmethod
    async def mark_used(self, crp_id: str) -> None: ...

    @abstractmethod
    async def list_by_drone(self, drone_id: str, limit: int = 50) -> List[ChallengeResponsePair]: ...


class DroneRepository(ABC):
    @abstractmethod
    async def save(self, identity: DroneIdentity) -> None: ...

    @abstractmethod
    async def find_by_id(self, drone_id: str) -> Optional[DroneIdentity]: ...

    @abstractmethod
    async def exists(self, drone_id: str) -> bool: ...


class SessionRepository(ABC):
    @abstractmethod
    async def save(self, session: DroneSession) -> None: ...

    @abstractmethod
    async def find_active(self, drone_id: str) -> Optional[DroneSession]: ...

    @abstractmethod
    async def deactivate(self, drone_id: str) -> None: ...


class TelemetryRepository(ABC):
    @abstractmethod
    async def save(self, packet: TelemetryPacket, encrypted: EncryptedPayload) -> None: ...

    @abstractmethod
    async def list_by_drone(self, drone_id: str, limit: int = 100) -> list: ...


class AttackRepository(ABC):
    @abstractmethod
    async def save(self, log: AttackLog) -> None: ...

    @abstractmethod
    async def list_all(self, limit: int = 50) -> List[AttackLog]: ...


class PUFPort(ABC):
    @abstractmethod
    def generate_challenge(self) -> list: ...

    @abstractmethod
    def evaluate(self, challenge: list, noisy: bool = False) -> int: ...

    @abstractmethod
    def encrypt(self, plaintext: bytes, challenge: list) -> EncryptedPayload: ...

    @abstractmethod
    def decrypt(self, encrypted: EncryptedPayload) -> bytes: ...
