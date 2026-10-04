"""Обезличивание перед отправкой в LLM: ни ФИО, ни телефонов, ни ПИН.

Факты наряда уходят без имён изначально; здесь подчищается свободный текст, который пишут
люди («Ахметов заменил подшипник», «звонить 8 701 …»).
"""

import re
from collections.abc import Iterable

PERSON = "Исполнитель"

_PHONE = re.compile(r"(?:\+7|\b8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b")
_PIN = re.compile(r"(?i)\b(пин|pin|пароль)\s*[:\-]?\s*\d{3,8}\b")


def _name_variants(full_name: str) -> list[str]:
    """«Ахметов Ерлан Каиртаевич» → полное ФИО, «Ахметов Е.», «Ахметов Е.К.», «Ахметов»."""
    parts = full_name.split()
    if not parts:
        return []
    variants = [full_name]
    if len(parts) >= 2:
        variants.append(f"{parts[0]} {parts[1]}")
        initials = "".join(f"{p[0]}." for p in parts[1:])
        variants += [f"{parts[0]} {initials}", f"{parts[0]} {parts[1][0]}."]
    variants.append(parts[0])
    # Длинные варианты раньше коротких — иначе «Ахметов» съест начало «Ахметов Е.»
    return sorted(set(variants), key=len, reverse=True)


def anonymize(text: str, names: Iterable[str] = ()) -> str:
    result = _PHONE.sub("[телефон]", text)
    result = _PIN.sub(r"\1 [скрыт]", result)
    for full_name in names:
        for variant in _name_variants(full_name):
            # Фамилия с падежным окончанием тоже скрывается: «Ахметову», «Ахметова»
            stem = re.escape(variant)
            if " " not in variant and not variant.endswith("."):
                stem += r"[а-яё]{0,3}"
            result = re.sub(rf"(?<![\w]){stem}(?![\w])", PERSON, result)
    return result
