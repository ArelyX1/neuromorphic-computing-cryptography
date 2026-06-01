import json
import math
import time
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional
from .simulation.hybrid_puf import NeuromorphicHybridPUF, HybridPUF
from .custom_cipher import PUFCipher


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
    status: str


class DroneCryptoLink:
    def __init__(self, drone_id: str, puf_seed: int, n: int = 64, k: int = 4):
        self.drone_id = drone_id
        self.puf_seed = puf_seed
        self.puf = HybridPUF(n=n, k=k, seed=puf_seed, preprocessor="vigenere",
                              preprocessor_key=f"DRONE_{drone_id}")
        self.cipher = PUFCipher(self.puf)
        self.session_challenge: Optional[np.ndarray] = None
        self.authenticated = False

    def authenticate(self) -> dict:
        challenge = self.puf.generate_challenge()
        response = self.puf.eval(challenge, noisy=True)
        self.session_challenge = challenge
        self.authenticated = True
        return {
            "drone_id": self.drone_id,
            "challenge": challenge.tolist(),
            "response": int(response),
        }

    def verify_response(self, challenge: np.ndarray, expected_response: int) -> bool:
        actual = self.puf.eval(challenge, noisy=False)
        return actual == expected_response

    def encrypt_telemetry(self, packet: TelemetryPacket) -> dict:
        if not self.authenticated or self.session_challenge is None:
            raise RuntimeError("Drone not authenticated. Call authenticate() first.")
        payload = json.dumps(asdict(packet)).encode("utf-8")
        encrypted = self.cipher.encrypt(payload, self.session_challenge)
        encrypted["drone_id"] = self.drone_id
        return encrypted

    def decrypt_telemetry(self, encrypted: dict) -> TelemetryPacket:
        plaintext = self.cipher.decrypt(encrypted)
        data = json.loads(plaintext.decode("utf-8"))
        return TelemetryPacket(**data)

    @staticmethod
    def simulate_gps_drift(base_lat: float = -16.4090, base_lon: float = -71.5374, t: float = 0):
        return (
            base_lat + math.sin(t * 0.01) * 0.001,
            base_lon + math.cos(t * 0.01) * 0.001,
        )

    def simulate_flight(self, steps: int = 10, interval: float = 1.0):
        print(f"\n[DRONE {self.drone_id}] Iniciando vuelo neuromórfico...")
        auth_data = self.authenticate()
        print(f"  -> Autenticación NeuroPUF: challenge={auth_data['challenge'][:5]}... response={auth_data['response']}")

        for i in range(steps):
            t = i * interval
            lat, lon = self.simulate_gps_drift(t=t)
            packet = TelemetryPacket(
                drone_id=self.drone_id,
                gps_lat=lat,
                gps_lon=lon,
                altitude=100.0 + i * 0.5,
                speed=15.0 + math.sin(t) * 2,
                battery=100.0 - i * 3.0,
                heading=(i * 36) % 360,
                timestamp=time.time(),
                status="en_route" if i < steps - 1 else "landing",
            )
            encrypted = self.encrypt_telemetry(packet)
            decrypted = self.decrypt_telemetry(encrypted)
            layers = encrypted.get('iv_cbc','?')[:6] if isinstance(encrypted.get('iv_cbc',''), str) else '?'
            print(f"  [{i+1}/{steps}] GPS=({decrypted.gps_lat:.4f}, {decrypted.gps_lon:.4f}) "
                  f"alt={decrypted.altitude:.1f}m bat={decrypted.battery:.1f}% "
                  f"cifrado={len(encrypted['ciphertext'])}B "
                  f"[AES-CBC AES-CTR Spike ChaCha20]")

        print(f"[DRONE {self.drone_id}] Vuelo neuromórfico completado.\n")
