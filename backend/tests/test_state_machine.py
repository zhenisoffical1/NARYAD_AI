import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, Forbidden, Invalid
from app.models import OrderEvent
from app.models.enums import TERMINAL_STATUSES, OrderStatus, Role
from app.services.notifications.live import pending_events
from app.services.state_machine import (
    TRANSITIONS,
    Action,
    ActorKind,
    apply_transition,
    available_actions,
    check_transition,
)

S = OrderStatus
A, M, SYS = ActorKind.ASSIGNEE, ActorKind.MASTER, ActorKind.SYSTEM

# Ровно таблица из CLAUDE.md, раздел 4: (из, действие, кто, в)
ALLOWED = [
    (S.ISSUED, Action.ACCEPT, A, S.ACCEPTED),
    (S.ISSUED, Action.QUEUE, A, S.QUEUED),
    (S.ISSUED, Action.REJECT, A, S.REJECTED),
    (S.QUEUED, Action.ACCEPT, A, S.ACCEPTED),
    (S.ACCEPTED, Action.START, A, S.IN_PROGRESS),
    (S.IN_PROGRESS, Action.PAUSE, A, S.PAUSED),
    (S.IN_PROGRESS, Action.COMPLETE, A, S.DONE),
    (S.PAUSED, Action.RESUME, A, S.IN_PROGRESS),
    (S.DONE, Action.BEGIN_REVIEW, SYS, S.AI_REVIEW),
    (S.AI_REVIEW, Action.CLOSE, M, S.CLOSED),
    (S.AI_REVIEW, Action.SEND_TO_REWORK, M, S.REWORK),
    (S.AI_REVIEW, Action.SEND_TO_REWORK, SYS, S.REWORK),
    (S.REWORK, Action.RESUME_REWORK, A, S.IN_PROGRESS),
    (S.REJECTED, Action.REISSUE, M, S.ISSUED),
]


@pytest.mark.parametrize(("source", "action", "actor", "target"), ALLOWED)
def test_allowed_transitions(source: S, action: Action, actor: ActorKind, target: S) -> None:
    transition = check_transition(source, action, actor, reason="причина")
    assert transition.target == target


@pytest.mark.parametrize("source", sorted(set(S) - TERMINAL_STATUSES))
def test_master_can_cancel_any_non_terminal(source: S) -> None:
    assert check_transition(source, Action.CANCEL, M, reason="ошибка выдачи").target == S.CANCELLED


def test_transition_table_matches_spec() -> None:
    """Нет «лишних» переходов сверх спецификации (кроме отмены из любого нетерминального)."""
    spec = {(src, act) for src, act, _, _ in ALLOWED}
    actual = {
        (src, t.action)
        for t in TRANSITIONS.values()
        if t.action != Action.CANCEL
        for src in t.sources
    }
    assert actual == spec


@pytest.mark.parametrize(
    ("source", "action", "actor"),
    [
        (S.ISSUED, Action.START, A),  # нельзя начать, не приняв
        (S.QUEUED, Action.START, A),
        (S.QUEUED, Action.REJECT, A),  # отклонить можно только выданный
        (S.ACCEPTED, Action.COMPLETE, A),  # «Исполнено» только из «В работе»
        (S.PAUSED, Action.COMPLETE, A),
        (S.DONE, Action.CLOSE, M),  # закрыть можно только после проверки ИИ
        (S.IN_PROGRESS, Action.CLOSE, M),
        (S.REWORK, Action.COMPLETE, A),  # доработку сначала надо начать
        (S.REJECTED, Action.ACCEPT, A),
    ],
)
def test_forbidden_transitions_conflict(source: S, action: Action, actor: ActorKind) -> None:
    with pytest.raises(Conflict) as exc:
        check_transition(source, action, actor, reason="x", number=147)
    assert "№147" in exc.value.message


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATUSES))
@pytest.mark.parametrize("action", list(Action))
def test_terminal_statuses_are_final(terminal: S, action: Action) -> None:
    with pytest.raises(Conflict, match="изменить его нельзя"):
        check_transition(terminal, action, M, reason="x")


@pytest.mark.parametrize(
    ("source", "action", "actor"),
    [
        (S.AI_REVIEW, Action.CLOSE, A),  # исполнитель не закрывает сам себе
        (S.ISSUED, Action.ACCEPT, M),  # мастер не принимает за исполнителя
        (S.DONE, Action.BEGIN_REVIEW, M),  # проверку запускает только система
        (S.ISSUED, Action.CANCEL, A),
        (S.AI_REVIEW, Action.CLOSE, SYS),  # финальное слово за мастером
    ],
)
def test_wrong_actor_forbidden(source: S, action: Action, actor: ActorKind) -> None:
    with pytest.raises(Forbidden):
        check_transition(source, action, actor, reason="x")


@pytest.mark.parametrize(
    ("source", "action", "actor"),
    [
        (S.ISSUED, Action.REJECT, A),
        (S.IN_PROGRESS, Action.PAUSE, A),
        (S.ACCEPTED, Action.CANCEL, M),
    ],
)
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reason_required(source: S, action: Action, actor: ActorKind, reason: str | None) -> None:
    with pytest.raises(Invalid, match="Укажите причину"):
        check_transition(source, action, actor, reason=reason)


def test_conflict_message_suggests_next_actions() -> None:
    with pytest.raises(Conflict) as exc:
        check_transition(S.ISSUED, Action.START, A, number=12)
    assert "«Принять в работу»" in exc.value.message
    assert "«Поставить в очередь»" in exc.value.message


def test_available_actions_for_worker_on_issued() -> None:
    assert set(available_actions(S.ISSUED, A)) == {Action.ACCEPT, Action.QUEUE, Action.REJECT}


async def test_apply_writes_event_timestamp_and_live_event(
    session: AsyncSession, make_employee, order_factory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee(Role.WORKER)
    order = await order_factory(master=master, assignee=worker)

    await apply_transition(session, order, Action.ACCEPT, actor=worker, comment="иду")
    await session.commit()

    assert order.status == S.ACCEPTED
    assert order.accepted_at is not None
    events = (await session.scalars(select(OrderEvent))).all()
    assert len(events) == 1
    assert (events[0].from_status, events[0].to_status) == (S.ISSUED, S.ACCEPTED)
    assert events[0].actor_id == worker.id
    assert events[0].comment == "иду"

    live = pending_events(session)
    assert live[-1].type == "order.status_changed"
    assert live[-1].is_for(worker.id, Role.WORKER)
    assert live[-1].is_for(master.id, Role.MASTER)
    assert not live[-1].is_for(worker.id + 999, Role.WORKER)


async def test_apply_rejects_other_worker(
    session: AsyncSession, make_employee, order_factory
) -> None:
    master = await make_employee(Role.MASTER)
    assignee = await make_employee(Role.WORKER)
    stranger = await make_employee(Role.WORKER)
    order = await order_factory(master=master, assignee=assignee)

    with pytest.raises(Forbidden, match="другому исполнителю"):
        await apply_transition(session, order, Action.ACCEPT, actor=stranger)
    assert order.status == S.ISSUED


async def test_boss_cannot_change_status(
    session: AsyncSession, make_employee, order_factory
) -> None:
    master = await make_employee(Role.MASTER)
    boss = await make_employee(Role.BOSS)
    order = await order_factory(master=master, assignee=None)
    with pytest.raises(Forbidden):
        await apply_transition(session, order, Action.CANCEL, actor=boss, reason="x")


async def test_complete_requires_works_and_fault_code(
    session: AsyncSession, make_employee, order_factory
) -> None:
    master = await make_employee(Role.MASTER)
    worker = await make_employee(Role.WORKER)
    order = await order_factory(master=master, assignee=worker, status=S.IN_PROGRESS)

    with pytest.raises(Invalid, match="выполненные работы, шифр неисправности"):
        await apply_transition(session, order, Action.COMPLETE, actor=worker)
    assert order.status == S.IN_PROGRESS


async def test_full_happy_path(session: AsyncSession, make_employee, order_factory) -> None:
    from app.models import FaultCode

    master = await make_employee(Role.MASTER)
    worker = await make_employee(Role.WORKER)
    order = await order_factory(master=master, assignee=worker)
    code = FaultCode(code="Г-02", category="Г", name="Течь гидравлики")
    session.add(code)
    await session.flush()

    await apply_transition(session, order, Action.QUEUE, actor=worker)
    await apply_transition(session, order, Action.ACCEPT, actor=worker)
    await apply_transition(session, order, Action.START, actor=worker)
    await apply_transition(session, order, Action.PAUSE, actor=worker, reason="ждёт запчасти")
    await apply_transition(session, order, Action.RESUME, actor=worker)
    order.works_done = "Заменено уплотнение"
    order.fault_code_id = code.id
    await apply_transition(session, order, Action.COMPLETE, actor=worker)
    await apply_transition(session, order, Action.BEGIN_REVIEW, actor=None)
    await apply_transition(session, order, Action.CLOSE, actor=master)
    await session.commit()

    assert order.status == S.CLOSED
    history = (await session.scalars(select(OrderEvent).order_by(OrderEvent.id))).all()
    assert [e.to_status for e in history] == [
        S.QUEUED,
        S.ACCEPTED,
        S.IN_PROGRESS,
        S.PAUSED,
        S.IN_PROGRESS,
        S.DONE,
        S.AI_REVIEW,
        S.CLOSED,
    ]
    assert history[3].reason == "ждёт запчасти"
    assert history[6].actor_id is None  # проверку запустила система
