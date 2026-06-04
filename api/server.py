import json
import math
import time
import queue
import threading
import numpy as np
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from strawberry.flask.views import AsyncGraphQLView

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.graphql_schema import schema
from api.infrastructure.puf_adapter import HybridPUFAdapter
from api.domain.entities import TelemetryPacket, DroneStatus

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})

app.add_url_rule(
    "/graphql",
    view_func=AsyncGraphQLView.as_view("graphql", schema=schema),
)

puf = HybridPUFAdapter()
drone_status = DroneStatus()
event_queue = queue.Queue()


def _save_telemetry_sync(packet, encrypted):
    try:
        from api.infrastructure.db.config import SyncSessionLocal
        from api.infrastructure.db.models import TelemetryLogModel
        from datetime import datetime, timezone
        with SyncSessionLocal() as session:
            log = TelemetryLogModel(
                drone_id=packet.drone_id,
                encrypted_payload=encrypted.ciphertext,
                iv=encrypted.iv,
                gps_lat=packet.gps_lat,
                gps_lon=packet.gps_lon,
                altitude=packet.altitude,
                battery=packet.battery,
                timestamp=datetime.now(timezone.utc),
                verified=True,
            )
            session.add(log)
            session.commit()
    except Exception as e:
        print(f"Warning: could not save telemetry to DB: {e}")


def drone_simulation_loop():
    step = 0
    base_lat, base_lon = -16.4090, -71.5374
    while True:
        t = step * 1.0
        drone_status.gps_lat = base_lat + math.sin(t * 0.01) * 0.002
        drone_status.gps_lon = base_lon + math.cos(t * 0.01) * 0.002
        drone_status.altitude = 100.0 + step * 0.5 + math.sin(t * 0.05) * 2
        drone_status.speed = 15.0 + math.sin(t * 0.1) * 3
        drone_status.battery = max(0, 100.0 - step * 0.5)
        drone_status.heading = (step * 10) % 360
        drone_status.signal_strength = 70 + int(20 * math.sin(t * 0.2))
        drone_status.packets_sent = step + 1

        if not drone_status.authenticated:
            try:
                challenge = puf.generate_challenge()
                response = puf.evaluate(challenge, noisy=True)
                drone_status.authenticated = True
                drone_status.challenge = str(challenge[:8])
                drone_status.response = str(response)
                event_queue.put({"type": "auth", "status": "success"})
            except Exception as e:
                event_queue.put({"type": "error", "message": str(e)})

        try:
            packet = TelemetryPacket(
                drone_id="NEURO-DRON-01",
                gps_lat=drone_status.gps_lat,
                gps_lon=drone_status.gps_lon,
                altitude=drone_status.altitude,
                speed=drone_status.speed,
                battery=drone_status.battery,
                heading=drone_status.heading,
                timestamp=time.time(),
                status="en_route" if drone_status.battery > 20 else "returning",
            )
            challenge = puf.generate_challenge()
            import json as _json
            encrypted = puf.encrypt(_json.dumps(packet.to_dict()).encode("utf-8"), challenge)
            event_queue.put({
                "type": "telemetry",
                "packet": {
                    "ciphertext": encrypted.ciphertext[:64],
                    "iv": encrypted.iv[:8],
                    "nonce_ctr": encrypted.nonce_ctr[:8],
                    "iv_cbc": encrypted.iv_cbc[:8],
                    "chacha_iv": encrypted.chacha_iv[:8],
                    "drone_id": encrypted.drone_id,
                    "size": encrypted.size,
                }
            })
            _save_telemetry_sync(packet, encrypted)
        except Exception as e:
            event_queue.put({"type": "error", "message": str(e)})

        spike_levels = [0.1 + 0.8 * abs(math.sin(t * 0.3 + i)) for i in range(5)]
        conductance_mean = 0.35 + 0.3 * abs(math.sin(t * 0.05))
        conductance_std = 0.12 + 0.06 * abs(math.cos(t * 0.07))

        event_queue.put({"type": "status", "data": {
            "authenticated": drone_status.authenticated,
            "gps_lat": drone_status.gps_lat,
            "gps_lon": drone_status.gps_lon,
            "altitude": drone_status.altitude,
            "speed": drone_status.speed,
            "battery": drone_status.battery,
            "heading": drone_status.heading,
            "signal_strength": drone_status.signal_strength,
            "packets_sent": drone_status.packets_sent,
            "challenge": drone_status.challenge,
            "response": drone_status.response,
            "attack_detected": drone_status.attack_detected,
            "spike_levels": spike_levels,
            "conductance_mean": round(conductance_mean, 4),
            "conductance_std": round(conductance_std, 4),
        }})
        time.sleep(1.5)
        step += 1


threading.Thread(target=drone_simulation_loop, daemon=True).start()


@app.route("/")
def index():
    return jsonify({"message": "NeuroPUF API - Frontend runs at http://localhost:3000", "status": "operational", "version": "3.0"})


@app.route("/api/status")
def get_status():
    return jsonify({
        "authenticated": drone_status.authenticated,
        "gps_lat": drone_status.gps_lat,
        "gps_lon": drone_status.gps_lon,
        "altitude": drone_status.altitude,
        "speed": drone_status.speed,
        "battery": drone_status.battery,
        "heading": drone_status.heading,
        "signal_strength": drone_status.signal_strength,
        "packets_sent": drone_status.packets_sent,
        "challenge": drone_status.challenge,
        "response": drone_status.response,
        "attack_detected": drone_status.attack_detected,
    })


def _save_attack_log_sync(fake_seed, fake_response, real_response, detected):
    from api.infrastructure.db.config import SyncSessionLocal
    from api.domain.entities import AttackLog

    with SyncSessionLocal() as session:
        from api.infrastructure.db.models import AttackLogModel
        log = AttackLogModel(
            fake_seed=fake_seed,
            fake_response=fake_response,
            real_response=real_response,
            detected=detected,
        )
        session.add(log)
        session.commit()


@app.route("/api/attack/<int:fake_seed>")
def trigger_attack(fake_seed):
    challenge = puf.generate_challenge()
    real_response = puf.evaluate(challenge, noisy=False)

    from puf_crypto.simulation.hybrid_puf import HybridPUF
    fake_puf = HybridPUF(n=64, k=4, seed=fake_seed, preprocessor="chaotic")
    fake_response = int(fake_puf.eval(np.array(challenge, dtype=np.int8), noisy=False))
    detected = fake_response != real_response

    drone_status.attack_detected = detected
    event_queue.put({"type": "attack", "seed": fake_seed, "detected": detected})
    try:
        _save_attack_log_sync(fake_seed, fake_response, real_response, detected)
    except Exception as e:
        print(f"Warning: could not save attack log to DB: {e}")
    return jsonify({
        "attack_simulated": True,
        "fake_seed": fake_seed,
        "fake_response": fake_response,
        "real_response": real_response,
        "detected": detected,
    })


@app.route("/api/reset")
def reset():
    global drone_status, puf
    puf = HybridPUFAdapter()
    drone_status = DroneStatus()
    return jsonify({"status": "reset_ok"})


@app.route("/stream")
def stream():
    def generate():
        while True:
            try:
                data = event_queue.get(timeout=10)
                yield f"data: {json.dumps(data)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "Access-Control-Allow-Origin": "*"})


if __name__ == "__main__":
    print("=" * 60)
    print("  NeuroPUF API v3.0 - Hexagonal + GraphQL")
    print("  Server:  http://0.0.0.0:5000")
    print("  GraphQL: http://0.0.0.0:5000/graphql")
    print("  Frontend: http://localhost:3000  (cd frontend && npm run dev)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
