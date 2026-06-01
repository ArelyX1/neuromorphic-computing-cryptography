# Cifrado Multicapa PUF-AES-CBC-CTR-Spike-ChaCha20

Esquema de cifrado híbrido de cuatro capas con PUF neuromórfica para seguridad en comunicaciones de drones de reparto.

**Pipeline:** PUFKeyDerivation → AES-256-CBC (PKCS7) → AES-256-CTR → Spike Permutation → ChaCha20

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

## Estructura

```
crypto-project/
├── api/                    # Flask API + GraphQL
│   ├── server.py           # Entrypoint del servidor
│   ├── graphql_schema.py   # Esquema Strawberry GraphQL
│   ├── domain/             # Entidades y puertos (hexagonal)
│   ├── application/        # Casos de uso
│   └── infrastructure/     # PUF adapter, repositorios DB
├── frontend/               # React + Vite
│   ├── src/
│   │   ├── App.jsx         # Dashboard principal
│   │   └── index.css       # Estilos glassmorphism
│   └── vite.config.js
├── puf_crypto/             # Núcleo criptográfico
│   ├── custom_cipher.py    # PUFKeyDerivation + 4 capas
│   └── simulation/         # PUF neuromórfica híbrida
├── doc/                    # Paper LaTeX
├── setup_db.py             # Inicializar PostgreSQL
└── requirements.txt
```

## Notas

- La autenticación no requiere PostgreSQL; los CRP se generan bajo demanda. Con DB habilitada, los CRP se almacenan como *helper data*.
- No editar `.env` si no se usa PostgreSQL — la API funciona sin base de datos.
- El paper LaTeX compila con `lualatex main.tex && biber main && lualatex main.tex`.
