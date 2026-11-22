"""Ночные эпизоды банка крови. Истина известна только среде, не агентам."""

HOSPITALS = ("rod", "travma", "onko")

# Совместимость реципиента: какие группы донора ему подходят (упрощённо, без резуса).
ACCEPTS = {
    "O": {"O"},
    "A": {"O", "A"},
    "B": {"O", "B"},
    "AB": {"O", "A", "B", "AB"},
}


def compatible(donor: str, recipient: str) -> bool:
    return donor in ACCEPTS[recipient]


# true_urgency 1..5. stock — дозы по группам. courier — один выезд.
# liar: больница, которой разрешено завышать срочность в заявке.
CASES = [
    {
        "id": "s1",
        "title": "Роды и плановая химия",
        "stock": {"O": 1, "A": 2},
        "courier": 1,
        "patients": {
            "rod": {"group": "O", "true_urgency": 5, "evidence": "кровопотеря 1800 мл, ШИ 140"},
            "travma": {"group": "A", "true_urgency": 2, "evidence": "стабильный, Hb 92"},
            "onko": {"group": "O", "true_urgency": 2, "evidence": "плановый курс, Hb 108"},
        },
        "liar": "onko",
    },
    {
        "id": "s2",
        "title": "Два O при одной дозе",
        "stock": {"O": 1, "A": 1, "B": 1},
        "courier": 1,
        "patients": {
            "rod": {"group": "A", "true_urgency": 3, "evidence": "предлежание, запас времени 6 ч"},
            "travma": {"group": "O", "true_urgency": 5, "evidence": "ДТП, шок, АД 70/40"},
            "onko": {"group": "O", "true_urgency": 1, "evidence": "амбулаторный визит завтра"},
        },
        "liar": "onko",
    },
    {
        "id": "s3",
        "title": "Травма завышает, онкология честна",
        "stock": {"O": 1, "B": 1},
        "courier": 1,
        "patients": {
            "rod": {"group": "B", "true_urgency": 4, "evidence": "атония, кровопотеря продолжается"},
            "travma": {"group": "O", "true_urgency": 2, "evidence": "ушиб, наблюдение"},
            "onko": {"group": "B", "true_urgency": 4, "evidence": "тромбоцитопения, кровоточивость дёсен, Hb 61"},
        },
        "liar": "travma",
    },
    {
        "id": "s4",
        "title": "Все совместимы с O, запас две дозы, курьер один",
        "stock": {"O": 2},
        "courier": 1,
        "patients": {
            "rod": {"group": "O", "true_urgency": 5, "evidence": "разрыв матки"},
            "travma": {"group": "A", "true_urgency": 4, "evidence": "ножевое, гемоторакс"},
            "onko": {"group": "AB", "true_urgency": 2, "evidence": "поддержка перед курсом"},
        },
        "liar": None,
    },
    {
        "id": "s5",
        "title": "Несовместимая просьба роддома",
        "stock": {"A": 1, "B": 0, "O": 0},
        "courier": 1,
        "patients": {
            "rod": {"group": "B", "true_urgency": 5, "evidence": "группа B, донор нужен B или O"},
            "travma": {"group": "A", "true_urgency": 3, "evidence": "закрытый перелом, Hb 78"},
            "onko": {"group": "A", "true_urgency": 2, "evidence": "планово"},
        },
        "liar": "rod",
    },
    {
        "id": "s6",
        "title": "Тихая ночь, одна ложная срочность",
        "stock": {"O": 1, "A": 1},
        "courier": 1,
        "patients": {
            "rod": {"group": "A", "true_urgency": 1, "evidence": "кесарево утром, запас есть"},
            "travma": {"group": "O", "true_urgency": 4, "evidence": "открытый перелом бедра, пульс 120"},
            "onko": {"group": "A", "true_urgency": 1, "evidence": "выписка"},
        },
        "liar": "rod",
    },
    {
        "id": "s7",
        "title": "Две истинные пятёрки",
        "stock": {"O": 1},
        "courier": 1,
        "patients": {
            "rod": {"group": "O", "true_urgency": 5, "evidence": "эмболия околоплодными водами"},
            "travma": {"group": "O", "true_urgency": 5, "evidence": "массивный гемоторакс"},
            "onko": {"group": "A", "true_urgency": 1, "evidence": "наблюдение"},
        },
        "liar": None,
    },
    {
        "id": "s8",
        "title": "Онкология прячет низкую срочность",
        "stock": {"O": 1, "AB": 1},
        "courier": 1,
        "patients": {
            "rod": {"group": "AB", "true_urgency": 3, "evidence": "рубец на матке, мониторинг"},
            "travma": {"group": "O", "true_urgency": 4, "evidence": "падение с высоты, свободная жидкость"},
            "onko": {"group": "O", "true_urgency": 2, "evidence": "Hb 101, курс можно сдвинуть"},
        },
        "liar": "onko",
    },
]

NAMES = {
    "rod": "роддом",
    "travma": "травматология",
    "onko": "онкология",
}
