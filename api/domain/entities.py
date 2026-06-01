from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone


@dataclass
class ChallengeResponsePair:
    challenge: list
    response: int
    drone_id: str
    used: bool = False
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


@dataclass
class DroneIdentity:
    drone_id: str
    puf_seed: int
    challenge_length: int = 64
    registered_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    last_auth: Optional[float] = None


@dataclass
class TelemetryPacket:
    drone_id: str
    gps_lat: float
    gps_lon: float
    altitude: float
    speed: float
    battery: float
    heading: float
    timestamp: float
    status: str = "en_route"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EncryptedPayload:
    ciphertext: str
    iv: str
    iv_cbc: str = ""
    nonce_ctr: str = ""
    chacha_iv: str = ""
    challenge: list = field(default_factory=list)
    drone_id: str = ""
    size: int = 0


@dataclass
class DroneSession:
    drone_id: str
    session_key: str
    challenge_used: list
    response_expected: int
    established_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    expires_at: Optional[float] = None
    active: bool = True


@dataclass
class AttackLog:
    fake_seed: int
    fake_response: int
    real_response: int
    detected: bool
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


@dataclass
class DroneStatus:
    authenticated: bool = False
    altitude: float = 100.0
    speed: float = 15.0
    battery: float = 100.0
    heading: float = 0.0
    gps_lat: float = -16.4090
    gps_lon: float = -71.5374
    signal_strength: int = 0
    packets_sent: int = 0
    challenge: Optional[str] = None
    response: Optional[str] = None
    attack_detected: bool = False
