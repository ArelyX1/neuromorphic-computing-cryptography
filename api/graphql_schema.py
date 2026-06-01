import strawberry
from typing import List
from .infrastructure.graphql.schema import (
    AuthResult, EncryptedPayloadType, TelemetryType,
    AttackLogType, DroneStatusType, TelemetryInput,
)
from .infrastructure.graphql.resolvers import (
    resolve_auth, resolve_send_telemetry, resolve_simulate_attack,
    resolve_get_telemetry, resolve_drone_status,
)


@strawberry.type
class Query:
    @strawberry.field
    async def authenticate(self, drone_id: str) -> AuthResult:
        return await resolve_auth(drone_id)

    @strawberry.field
    async def drone_status(self) -> DroneStatusType:
        return resolve_drone_status()

    @strawberry.field
    async def telemetry_history(self, drone_id: str, limit: int = 50) -> List[TelemetryType]:
        return await resolve_get_telemetry(drone_id, limit)

    @strawberry.field
    def simulate_attack(self, fake_seed: int) -> AttackLogType:
        return resolve_simulate_attack(fake_seed)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def send_telemetry(self, input: TelemetryInput) -> EncryptedPayloadType:
        return await resolve_send_telemetry(input)


schema = strawberry.Schema(query=Query, mutation=Mutation)
