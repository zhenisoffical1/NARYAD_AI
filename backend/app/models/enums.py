from enum import StrEnum


class Role(StrEnum):
    MASTER = "master"
    WORKER = "worker"
    BOSS = "boss"
    ADMIN = "admin"


class Shift(StrEnum):
    DAY = "day"
    NIGHT = "night"


class Criticality(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class OrderType(StrEnum):
    PLANNED = "planned"
    UNPLANNED = "unplanned"


class Priority(StrEnum):
    EMERGENCY = "emergency"
    HIGH = "high"
    NORMAL = "normal"
    PLANNED = "planned"


class OrderStatus(StrEnum):
    ISSUED = "ISSUED"
    QUEUED = "QUEUED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    DONE = "DONE"
    AI_REVIEW = "AI_REVIEW"
    REWORK = "REWORK"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = frozenset({OrderStatus.CLOSED, OrderStatus.CANCELLED})

STATUS_LABELS: dict[OrderStatus, str] = {
    OrderStatus.ISSUED: "Выдан",
    OrderStatus.QUEUED: "В очереди",
    OrderStatus.ACCEPTED: "Принят в работу",
    OrderStatus.REJECTED: "Отклонён",
    OrderStatus.IN_PROGRESS: "В работе",
    OrderStatus.PAUSED: "Приостановлен",
    OrderStatus.DONE: "Исполнено",
    OrderStatus.AI_REVIEW: "Проверка ИИ",
    OrderStatus.REWORK: "На доработку",
    OrderStatus.CLOSED: "Закрыт",
    OrderStatus.CANCELLED: "Отменён",
}


class PhotoKind(StrEnum):
    BEFORE = "before"
    AFTER = "after"


class Verdict(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_REMARKS = "accepted_with_remarks"
    REWORK = "rework"


class AssessmentStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
