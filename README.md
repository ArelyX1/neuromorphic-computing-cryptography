# Cifrado Multicapa PUF-AES-CBC-CTR-Spike-ChaCha20

Esquema de cifrado híbrido de cuatro capas con PUF neuromórfica para seguridad en comunicaciones de drones de reparto.

**Pipeline:** PUFKeyDerivation → AES-256-CBC (PKCS7) → AES-256-CTR → Spike Permutation → ChaCha20


<img width="1190" height="642" alt="image" src="https://github.com/user-attachments/assets/8b74e218-a088-499d-a6c6-50b8f1ab98f8" />
<img width="1200" height="639" alt="image" src="https://github.com/user-attachments/assets/f7dc7567-161c-4c45-a174-d83e2d8b5f4d" />
<img width="1182" height="639" alt="image" src="https://github.com/user-attachments/assets/b98b503c-ce13-4435-a932-693a267e6a7b" />
<img width="1181" height="629" alt="image" src="https://github.com/user-attachments/assets/6f5039ca-f728-47ce-9f7b-eacef2065b05" />
<img width="1144" height="600" alt="image" src="https://github.com/user-attachments/assets/89c6933a-7ffc-4d03-89a1-d8ba3488ab7c" />



## Requisitos

- Python ≥ 3.12
- Node.js ≥ 18 (para frontend)
- PostgreSQL 15+ (opcional, para GraphQL)

## Quick Start

```bash
# 1. Clonar el repositorio
git clone https://github.com/ArelyX1/neuromorphic-computing-cryptography.git
cd neuromorphic-computing-cryptography

# 2. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias del backend
pip install -r requirements.txt

# 4. Instalar dependencias del frontend
cd frontend
npm install
cd ..

# 5. (Opcional) Iniciar servidor Flask
python api/server.py

# 6. (Opcional) En otra terminal, iniciar frontend
cd frontend
npm run dev
```

## Ejecución

### 1. Servidor Flask (API)

```bash
source .venv/bin/activate
python api/server.py
```

Servidor en `http://127.0.0.1:5000`. Endpoints:
- `GET /api/status` — estado del sistema
- `GET /api/attack/<seed>` — simular ataque de suplantación
- `GET /api/reset` — reiniciar simulación
- `GET /stream` — SSE de telemetría en tiempo real
- `POST /graphql` — GraphQL (autenticación, telemetría, ataques)

### 2. Frontend React

```bash
cd frontend
npm run dev
```

Dashboard en `http://localhost:3000`. El proxy de Vite redirige `/api`, `/stream`, `/graphql` al backend.

## Archivos del proyecto (descripción detallada)

### Núcleo criptográfico — `puf_crypto/`

| Archivo | Objetivo |
|---------|----------|
| `simulation/hybrid_puf.py` | **PUF neuromórfica híbrida**. Contiene `MemristorCrossbar` (crossbar de memristores con conductancias seedeables), `LIFNeuron` (neurona Leaky Integrate-and-Fire usando `snntorch.Leaky`), `NeuromorphicPUFPreprocessor` (codificación de spikes por rate-coding), `NeuromorphicHybridPUF` (clase base con evaluación de 4 bits, STDP opcional, generación de CRP), y `HybridPUF` (wrapper legacy con preprocesadores Vigenere/Caesar/XOR para compatibilidad). |
| `custom_cipher.py` | **Cifrado multicapa PUF-driven**. `PUFKeyDerivation` deriva claves AES de 256 bits a partir de respuestas PUF con `SHA-256`. `PUFCipher` implementa el pipeline de 4 capas: **AES-256-CBC** (PKCS7) → **AES-256-CTR** → **Spike Permutation** (permutación de bits basada en el challenge) → **ChaCha20**. |
| `drone_telemetry.py` | **Simulador de enlace criptográfico de dron**. `DroneCryptoLink` modela un dron real: autenticación PUF, cifrado/descifrado de telemetría, y `simulate_flight()` que genera paquetes GPS/altitud/batería, los cifra y los descifra para verificación. |
| `db/base.py` | Declara `Base = declarative_base()` de SQLAlchemy, usado por los modelos ORM. |
| `db/models.py` | Re-exporta los modelos SQLAlchemy desde `api.infrastructure.db.models` para mantener el núcleo autocontenido. |
| `db/config.py` | Configuración de conexión asíncrona a PostgreSQL vía `asyncpg` + SQLAlchemy. |

### API — `api/` (Arquitectura Hexagonal)

| Archivo | Objetivo |
|---------|----------|
| `server.py` | **Entrypoint del servidor**. Inicializa Flask, monta GraphQL (`/graphql`), define rutas REST (`/api/status`, `/api/attack/<seed>`, `/api/reset`), SSE en `/stream` para telemetría en tiempo real, y arranca el loop de simulación de dron en un thread daemon. Usa **Hypercorn** (ASGI) en vez de Flask threaded para evitar conflictos con `asyncpg`. |
| `graphql_schema.py` | **Esquema Strawberry GraphQL**. Define queries `authenticate`, `drone_status`, `telemetry_history`, `simulate_attack`. |
| `domain/entities.py` | **Entidades del dominio** (dataclasses): `ChallengeResponsePair`, `DroneIdentity`, `TelemetryPacket`, `EncryptedPayload`, `DroneSession`, `AttackLog`, `DroneStatus`. |
| `domain/ports.py` | **Puertos/abstract interfaces**: `CRPRepository`, `DroneRepository`, `SessionRepository`, `TelemetryRepository`, `AttackRepository`, `PUFPort`. Define el contrato que la infraestructura debe implementar. |
| `domain/services.py` | **Servicios del dominio**: `DroneAuthService` (autenticación PUF), `TelemetryService` (envío de telemetría cifrada), `AttackDetectionService` (simula atacante con seed falso y compara respuestas). |
| `application/use_cases.py` | **Casos de uso**: `AuthenticateDroneUseCase`, `SendTelemetryUseCase`, `SimulateAttackUseCase`, `GetDroneStatusUseCase`. Orquestan servicios del dominio. |
| `infrastructure/puf_adapter.py` | **Adaptador PUF** (`HybridPUFAdapter`). Implementa `PUFPort` wrappeando `HybridPUF`. Incluye `_puf_bit_sequence()` para derivar secuencias de bits multi-evaluación y cifrado/descifrado multicapa completo (AES-CBC → AES-CTR → Spike → ChaCha20). |
| `infrastructure/db/config.py` | Configuración de motores SQLAlchemy asíncrono (`asyncpg`, pool_size=20) y síncrono (para el thread de simulación). |
| `infrastructure/db/models.py` | Modelos ORM: `CRPRecordModel`, `DroneIdentityModel`, `DroneSessionModel`, `TelemetryLogModel`, `AttackLogModel`. |
| `infrastructure/db/repositories.py` | Implementaciones SQLAlchemy de los puertos: `SQLAlchemyCRPRepository`, `SQLAlchemyDroneRepository`, `SQLAlchemySessionRepository`, `SQLAlchemyTelemetryRepository`, `SQLAlchemyAttackRepository`. |
| `infrastructure/graphql/schema.py` | Tipos Strawberry GraphQL: `CRPType`, `DroneIdentityType`, `DroneSessionType`, `TelemetryType`, `AttackLogType`, `EncryptedPayloadType`, `DroneStatusType`, `AuthResult`, `TelemetryInput`. |
| `infrastructure/graphql/resolvers.py` | Resolvers GraphQL que conectan las queries con los casos de uso y repositorios. |
| `static/index.html` | Interfaz web estática (fallback cuando no corre React). Muestra consola de dron con telemetría, ataques, y visualización de spikes. |
| `static/app.js` | Lógica JS de la interfaz estática: SSE, animación de partículas, actualización del dashboard, simulación de ataques. |
| `static/style.css` | Estilos glassmorphism dark para la interfaz estática. |

### Frontend — `frontend/` (React + Vite)

| Archivo | Objetivo |
|---------|----------|
| `src/App.jsx` | **Dashboard principal React**. Usa SSE para telemetría en tiempo real, muestra estado del dron (GPS, altitud, batería, velocidad), información criptográfica (ciphertext, IVs, nonces), detección de ataques, y estadísticas de fuerza bruta. |
| `src/main.jsx` | Punto de entrada de React. |
| `index.html` | HTML base para Vite. |
| `vite.config.js` | Configuración de Vite: puerto 3000, proxy de `/api`, `/stream`, `/graphql` a `http://127.0.0.1:5000`. |
| `static/index.html` | Versión estática standalone (copia de `api/static/index.html` para despliegue sin backend). |
| `static/app.js` | Versión estática standalone. |
| `static/style.css` | Versión estática standalone. |

### Raíz

| Archivo | Objetivo |
|---------|----------|
| `setup_db.py` | Script para inicializar tablas en PostgreSQL. Crea todas las tablas del ORM (`crp_records`, `drone_identities`, `drone_sessions`, `telemetry_logs`, `attack_logs`). |
| `requirements.txt` | Dependencias Python: `flask`, `flask-cors`, `strawberry-graphql`, `sqlalchemy`, `asyncpg`, `psycopg2-binary`, `cryptography`, `numpy`, `torch>=2.0.0`, `snntorch>=0.9`, `hypercorn>=0.17`, `python-dotenv`. |
| `.env` | Variables de entorno (no trackeada): `DATABASE_URL` para PostgreSQL. |

## Notas

- La autenticación no requiere PostgreSQL; los CRP se generan bajo demanda. Con DB habilitada, los CRP se almacenan como *helper data*.
- No editar `.env` si no se usa PostgreSQL — la API funciona sin base de datos.
- El paper LaTeX compila con `lualatex main.tex && biber main && lualatex main.tex`.


