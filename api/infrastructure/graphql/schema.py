import strawberry
from typing import List, Optional
from datetime import datetime


@strawberry.type
class CRPType:
    challenge: str
    response: int
    drone_id: str
    used: bool


@strawberry.type
class DroneIdentityType:
    drone_id: str
    puf_seed: int
    challenge_length: int


@strawberry.type
class DroneSessionType:
    drone_id: str
    session_key: str
    active: bool


@strawberry.type
class TelemetryType:
    drone_id: str
    gps_lat: float
    gps_lon: float
    altitude: float
    battery: float
    encrypted_payload: str
    verified: bool


@strawberry.type
class AttackLogType:
    fake_seed: int
    fake_response: int
    real_response: int
    detected: bool


@strawberry.type
class AuthResult:
    success: bool
    drone_id: str
    session_key: str
    message: str


@strawberry.type
class EncryptedPayloadType:
    ciphertext: str
    iv: str
    iv_cbc: str = ""
    nonce_ctr: str = ""
    chacha_iv: str = ""
    drone_id: str = ""
    size: int = 0


@strawberry.type
class DroneStatusType:
    authenticated: bool
    altitude: float
    speed: float
    battery: float
    heading: float
    gps_lat: float
    gps_lon: float
    signal_strength: int
    packets_sent: int
    attack_detected: bool
    challenge: Optional[str] = None
    response: Optional[str] = None


@strawberry.input
class TelemetryInput:
    drone_id: str
    gps_lat: float
    gps_lon: float
    altitude: float
    speed: float
    battery: float
    heading: float
    status: str = "en_route"


@strawberry.input
class AttackInput:
    fake_seed: int
