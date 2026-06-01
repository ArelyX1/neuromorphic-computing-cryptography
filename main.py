import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from puf_crypto.simulation.hybrid_puf import HybridPUF
from puf_crypto.custom_cipher import PUFCipher
from puf_crypto.drone_telemetry import DroneCryptoLink, TelemetryPacket


def test_hybrid_puf():
    print("=" * 60)
    print("PRUEBA 1: HybridPUF con preprocesador Vigenère")
    print("=" * 60)
    puf = HybridPUF(n=64, k=4, seed=42, preprocessor="vigenere", preprocessor_key="DRONE")
    challenge = puf.generate_challenge()
    response = puf.eval(challenge)
    print(f"  Challenge (primeros 8 bits): {challenge[:8]}")
    print(f"  Response: {response}")
    print(f"  Challenge Length: {puf.challenge_length}")
    print(f"  Response Length: {puf.response_length}")

    N = 10
    challenges, responses = puf.generate_crp_set(N)
    print(f"  CRP set generado: {N} pares")
    print(f"  Responses: {responses}")
    print(f"  Unique responses: {set(responses.tolist())}")
    print()


def test_custom_cipher():
    print("=" * 60)
    print("PRUEBA 2: PUF-Cipher (Caesar + Vigenère + ChaCha20)")
    print("=" * 60)
    puf = HybridPUF(n=64, k=4, seed=123, preprocessor="vigenere")
    cipher = PUFCipher(puf)
    challenge = puf.generate_challenge()

    plaintext = b"COMANDO: ENTREGAR PAQUETE EN COORDENADAS -16.4090,-71.5374 URGENTE"
    print(f"  Texto original: {plaintext.decode()}")

    encrypted = cipher.encrypt(plaintext, challenge)
    print(f"  Cifrado (hex): {encrypted['ciphertext'].hex()[:48]}...")
    print(f"  IV (hex): {encrypted['iv'].hex()}")
    print(f"  Shift Caesar: {encrypted['shift']}")
    print(f"  Vigenère key: {encrypted['vigenere_key']}")

    decrypted = cipher.decrypt(encrypted)
    print(f"  Texto descifrado: {decrypted.decode()}")
    assert plaintext == decrypted, "ERROR: El descifrado no coincide"
    print("  -> VERIFICADO: cifrado y descifrado correctos")
    print()


def test_drone_link():
    print("=" * 60)
    print("PRUEBA 3: Simulación de Enlace Drone-Base")
    print("=" * 60)
    drone = DroneCryptoLink(drone_id="DRONE-001", puf_seed=999)
    base = DroneCryptoLink(drone_id="DRONE-001", puf_seed=999)

    auth = drone.authenticate()
    challenge = np.array(auth["challenge"], dtype=np.int8)
    response_given = auth["response"]

    verified = base.verify_response(challenge, response_given)
    print(f"  Autenticación PUF: {'EXITOSA' if verified else 'FALLIDA'}")

    packet = TelemetryPacket(
        drone_id="DRONE-001",
        gps_lat=-16.4090,
        gps_lon=-71.5374,
        altitude=150.0,
        speed=12.5,
        battery=85.0,
        heading=270.0,
        timestamp=1234567890.0,
        status="en_route",
    )
    encrypted = drone.encrypt_telemetry(packet)
    decrypted = base.decrypt_telemetry(encrypted)
    print(f"  GPS enviado: ({packet.gps_lat}, {packet.gps_lon})")
    print(f"  GPS recibido: ({decrypted.gps_lat}, {decrypted.gps_lon})")
    assert packet.gps_lat == decrypted.gps_lat, "ERROR: GPS no coincide"
    assert packet.altitude == decrypted.altitude, "ERROR: Altitud no coincide"
    print("  -> VERIFICADO: telemetría cifrada/descifrada correctamente")
    print()


def test_attack_detection():
    print("=" * 60)
    print("PRUEBA 4: Detección de Ataque (drone falso)")
    print("=" * 60)
    real_drone = DroneCryptoLink(drone_id="DRONE-REAL", puf_seed=111)
    fake_drone = DroneCryptoLink(drone_id="DRONE-FAKE", puf_seed=222)

    auth = real_drone.authenticate()
    challenge = np.array(auth["challenge"], dtype=np.int8)

    real_response = real_drone.puf.eval(challenge, noisy=True)
    fake_response = fake_drone.puf.eval(challenge, noisy=True)

    print(f"  Respuesta del dron REAL: {real_response}")
    print(f"  Respuesta del dron FALSO: {fake_response}")
    print(f"  ¿Coinciden? {real_response == fake_response}")

    if real_response != fake_response:
        print("  -> ATAQUE DETECTADO: La huella PUF del drone falso no coincide")
    else:
        print("  -> Coincidencia (baja probabilidad)")
    print()


def test_simulated_flight():
    print("=" * 60)
    print("PRUEBA 5: Vuelo simulado completo")
    print("=" * 60)
    drone = DroneCryptoLink(drone_id="DRONE-CARGO-42", puf_seed=777)
    drone.simulate_flight(steps=5, interval=1.0)


def main():
    print("=" * 60)
    print("  CRYPTO-PROJECT: Cifrado Híbrido PUF para Drones de Reparto")
    print("  Basado en: PUF + Vigenère + Caesar + ChaCha20")
    print("=" * 60)

    test_hybrid_puf()
    test_custom_cipher()
    test_drone_link()
    test_attack_detection()
    test_simulated_flight()

    print("=" * 60)
    print("  TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()
