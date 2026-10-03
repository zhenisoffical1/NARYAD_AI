"""Детерминированные правила: находят факты с цифрами. LLM их только объясняет."""

from app.models.enums import OrderType
from app.services.verification.facts import CheckResult, CheckStatus, ClosureFacts
from app.services.verification.format import duration, num, times

MATERIAL_WARN_RATIO = 1.5
MATERIAL_FAIL_RATIO = 2.5
TIME_SLOW_RATIO = 2.0
TIME_FAST_RATIO = 0.25
MIN_WORKS_LENGTH = 15

# Какие категории материалов уместны для категории шифра
RELEVANT_MATERIALS: dict[str, frozenset[str]] = {
    "М": frozenset(
        {"подшипники", "смазочные", "крепёж", "уплотнения", "сварка", "конвейер", "привод"}
    ),
    "Г": frozenset({"гидравлика", "уплотнения", "смазочные", "крепёж"}),
    "П": frozenset({"пневматика", "уплотнения", "смазочные", "крепёж"}),
    "С": frozenset({"смазочные", "уплотнения", "крепёж"}),
    "Э": frozenset({"электрика", "подшипники", "крепёж"}),
}


def check_completeness(f: ClosureFacts) -> CheckResult:
    items: list[str] = []
    critical = False
    penalty = 0

    if len(f.works_done.strip()) < MIN_WORKS_LENGTH:
        items.append("Описание работ слишком короткое — напишите, что именно сделано.")
        penalty += 8
    if f.order_type == OrderType.UNPLANNED and f.after_photos == 0 and not f.archive:
        items.append("Нет фото «после» — для внепланового наряда оно обязательно.")
        critical = True
        penalty += 35
    if f.no_materials and f.norm_materials:
        typical = ", ".join(name for name, _, _ in f.norm_materials[:3])
        items.append(
            f"Отмечено «без материалов», а по нормативу шифра {f.fault_code} "
            f"обычно расходуются: {typical}."
        )
        penalty += 6

    status = _status(items, critical)
    if items:
        detail = items[0]
    else:
        if f.archive:
            photos = "архивный наряд без фото"
        elif f.after_photos:
            photos = f"фото «после»: {f.after_photos}"
        else:
            photos = "фото не требовалось"
        materials = "без материалов" if f.no_materials else f"материалов: {len(f.materials)}"
        detail = f"Заполнено: работы, шифр {f.fault_code}, {materials}, {photos}."
    return CheckResult("completeness", "Полнота закрытия", status, detail, critical, penalty, items)


def work_minutes(f: ClosureFacts) -> float:
    start = f.started_at or f.issued_at
    return max(0.0, (f.done_at - start).total_seconds() / 60 - f.paused_minutes)


def check_time(f: ClosureFacts) -> CheckResult:
    items: list[str] = []
    penalty = 0
    actual = work_minutes(f)

    if f.norm_hours:
        norm = float(f.norm_hours) * 60
        ratio = actual / norm if norm else 1.0
        if ratio > TIME_SLOW_RATIO:
            items.append(
                f"Работа заняла {duration(actual)} при нормативе {duration(norm)} "
                f"({times(ratio)} дольше)."
            )
            penalty += 8
        elif ratio < TIME_FAST_RATIO:
            items.append(
                f"Работа заняла {duration(actual)} при нормативе {duration(norm)} — "
                "подозрительно быстро, проверьте объём работ."
            )
            penalty += 8
        summary = f"{duration(actual)} при нормативе {duration(norm)}"
    else:
        summary = f"{duration(actual)}, норматив по шифру не задан"

    if f.done_at > f.deadline_at:
        late = (f.done_at - f.deadline_at).total_seconds() / 60
        items.append(f"Срок нарушен на {duration(late)}.")
        penalty += 8

    detail = items[0] if items else f"Выполнено в срок: {summary}."
    return CheckResult("time", "Время и срок", _status(items), detail, False, penalty, items)


def material_ratios(f: ClosureFacts) -> list[tuple[str, float]]:
    """(материал, факт / норма) для материалов с нормой расхода — нужно и аналитике."""
    return [
        (m.name, float(m.quantity / m.norm_quantity))
        for m in f.materials
        if m.norm_quantity and m.norm_quantity > 0
    ]


def check_materials(f: ClosureFacts) -> CheckResult:
    if f.no_materials or not f.materials:
        return CheckResult(
            "materials", "Расход материалов", "skip", "Материалы не списывались.", False, 0, []
        )

    items: list[str] = []
    critical = False
    penalty = 0
    category = f.fault_code[:1]
    relevant = RELEVANT_MATERIALS.get(category, frozenset())

    for m in f.materials:
        if m.norm_quantity and m.norm_quantity > 0:
            ratio = float(m.quantity / m.norm_quantity)
            text = (
                f"Списано {num(m.quantity)} {m.unit} «{m.name}» при норме "
                f"{num(m.norm_quantity)} {m.unit} для шифра {f.fault_code} ({times(ratio)} больше)."
            )
            if ratio > MATERIAL_FAIL_RATIO:
                items.append(text)
                critical = True
                penalty += 30
            elif ratio > MATERIAL_WARN_RATIO:
                items.append(text)
                penalty += 12
        elif m.category and relevant and m.category not in relevant:
            items.append(
                f"«{m.name}» ({m.category}) не типичен для шифра {f.fault_code} "
                f"«{f.fault_name}». Проверьте, что материал списан на этот наряд."
            )
            penalty += 10

    detail = (
        items[0]
        if items
        else f"Расход {len(f.materials)} поз. в пределах нормы для шифра {f.fault_code}."
    )
    return CheckResult(
        "materials", "Расход материалов", _status(items, critical), detail, critical, penalty, items
    )


def _status(items: list[str], critical: bool = False) -> CheckStatus:
    if critical:
        return "fail"
    return "warn" if items else "ok"


def run_rules(f: ClosureFacts) -> list[CheckResult]:
    return [check_completeness(f), check_time(f), check_materials(f)]
