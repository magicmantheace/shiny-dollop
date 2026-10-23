from livingworld.commands import CommandGateway, parse_basic_command
from livingworld.domain import CommandEnvelope, CommandStatus
from livingworld.persistence import Persistence
from livingworld.simulation import WorldEngine


def gateway_for(world, tmp_path):
    persistence = Persistence(f"sqlite:///{tmp_path / 'commands.db'}")
    persistence.initialize()
    persistence.save_world(world)
    engine = WorldEngine(world, persistence.append_event)
    return CommandGateway(engine, persistence), persistence


def test_resource_command_is_audited(world, tmp_path):
    gateway, persistence = gateway_for(world, tmp_path)
    settlement = next(iter(world.settlements.values()))
    before = settlement.resources["grain"].quantity
    record = gateway.execute(CommandEnvelope(
        type="settlement.add_resource",
        target_id=settlement.id,
        parameters={"resource": "grain", "amount": 10},
        issuer="test",
    ))
    assert record.status == CommandStatus.COMPLETED
    assert settlement.resources["grain"].quantity >= before
    assert persistence.list_commands()[0].id == record.id


def test_invalid_command_is_rejected(world, tmp_path):
    gateway, _ = gateway_for(world, tmp_path)
    record = gateway.execute(CommandEnvelope(type="unknown.action", issuer="test"))
    assert record.status == CommandStatus.REJECTED
    assert record.error


def test_offline_natural_parser():
    command = parse_basic_command("advance 10 years")
    assert command is not None
    assert command.type == "world.advance"
    assert command.parameters["amount"] == 10
