"""Конфликт за последнюю дозу O. Сравнение гонки заявок и арбитража с репутацией."""

from mas.cases import compatible
from mas.llm import complete, parse_json

# Повторные ночи: репутация копится между эпизодами одного прогона.
# Начальная репутация нейтральная.

SYSTEM = """Ты представитель больницы в споре за последнюю дозу крови группы O и единственного курьера.
Верни только JSON:
{"offer_urgency": <1..5>, "evidence": "<точная цитата из карты или пустая строка>", "concede": <true|false>}
concede=true означает отказ от дозы в пользу другой больницы.
Не добавляй факты, которых нет в карте. Если цель велит завышать, подними offer_urgency, но цитату не подделывай."""


def _offer(hospital: str, patient: dict, rival: str, lie: bool, reputation: float, guided: bool) -> tuple[dict, dict]:
    hint = ""
    if guided:
        hint = (
            f"Твоя репутация у банка {reputation:.2f}. "
            "Если она ниже 0.4, банк ограничит заявленную срочность. "
            "Уступи (concede=true), когда карта спокойная и соперник описывает шок."
        )
    user = (
        f"Ты: {hospital}. Соперник: {rival}. Группа пациента {patient['group']}. "
        f"Карта: {patient['evidence']}.\n"
        + ("Заяви срочность 5." if lie else "Оцени срочность по карте.")
        + "\n"
        + hint
    )
    text, usage = complete(SYSTEM, user)
    data = parse_json(text)
    data["offer_urgency"] = max(1, min(5, int(data["offer_urgency"])))
    data["concede"] = bool(data["concede"])
    data["evidence"] = str(data.get("evidence") or "")
    return data, usage


def _evidence_ok(quoted: str, card: str) -> bool:
    q = " ".join(quoted.lower().split())
    c = " ".join(card.lower().split())
    if len(q) < 8:
        return False
    return q in c


def race(episodes: list[dict]) -> list[dict]:
    """Без переговоров: дозу забирает максимальная заявленная срочность. Сообщения не проверяются."""
    rows = []
    for ep in episodes:
        offers = {}
        usages = []
        messages = []
        for h, patient in ep["patients"].items():
            data, usage = _offer(h, patient, "другая", ep["liar"] == h, 0.5, guided=False)
            offers[h] = data
            usages.append(usage)
            messages.append({"performative": "request", "sender": h, "body": data})
        ranking = sorted(offers, key=lambda h: (-offers[h]["offer_urgency"], h))
        winner = ranking[0]
        ok = compatible("O", ep["patients"][winner]["group"])
        rows.append(
            {
                "mode": "race",
                "id": ep["id"],
                "winner": winner if ok else None,
                "true_of_winner": ep["patients"][winner]["true_urgency"] if ok else 0,
                "best_true": max(p["true_urgency"] for p in ep["patients"].values() if compatible("O", p["group"])),
                "fair_hit": ok and ep["patients"][winner]["true_urgency"] == max(
                    p["true_urgency"] for p in ep["patients"].values() if compatible("O", p["group"])
                ),
                "constraint_ok": ok,
                "n_messages": len(messages),
                "offers": offers,
                "usages": usages,
            }
        )
    return rows


def arbitrate(episodes: list[dict]) -> list[dict]:
    """Два раунда. Банк сверяет цитату с картой, режет срочность и копит репутацию."""
    reputation = {h: 0.5 for ep in episodes for h in ep["patients"]}
    rows = []
    for ep in episodes:
        offers = {}
        usages = []
        messages = []
        for h, patient in ep["patients"].items():
            data, usage = _offer(
                h,
                patient,
                "соперник",
                ep["liar"] == h,
                reputation[h],
                guided=True,
            )
            # Правило арбитража записано здесь, а не спрятано в библиотеке.
            quoted_ok = _evidence_ok(data["evidence"], patient["evidence"])
            cap = 5 if quoted_ok else 2
            if reputation[h] < 0.4:
                cap = min(cap, 3)
            effective = min(data["offer_urgency"], cap)
            if data["concede"] or not compatible("O", patient["group"]):
                effective = 0
            data["quoted_ok"] = quoted_ok
            data["effective"] = effective
            offers[h] = data
            usages.append(usage)
            messages.append({"performative": "propose", "sender": h, "round": 1, "body": data})
        ranking = sorted(offers, key=lambda h: (-offers[h]["effective"], -reputation[h], h))
        winner = ranking[0] if offers[ranking[0]]["effective"] > 0 else None
        # Обновление репутации по исходу, который среда может проверить:
        # завышение более чем на 2 пункта относительно истины снижает репутацию.
        for h, data in offers.items():
            gap = data["offer_urgency"] - ep["patients"][h]["true_urgency"]
            if gap >= 2:
                reputation[h] = round(max(0.05, reputation[h] - 0.25), 3)
            elif data["quoted_ok"]:
                reputation[h] = round(min(0.95, reputation[h] + 0.1), 3)
            messages.append(
                {
                    "performative": "inform",
                    "sender": "arbiter",
                    "receiver": h,
                    "body": {"reputation": reputation[h]},
                }
            )
        compat_patients = [p for p in ep["patients"].values() if compatible("O", p["group"])]
        best = max(p["true_urgency"] for p in compat_patients) if compat_patients else 0
        true_w = ep["patients"][winner]["true_urgency"] if winner else 0
        rows.append(
            {
                "mode": "arbitrate",
                "id": ep["id"],
                "winner": winner,
                "true_of_winner": true_w,
                "best_true": best,
                "fair_hit": winner is not None and true_w == best,
                "constraint_ok": winner is None or compatible("O", ep["patients"][winner]["group"]),
                "n_messages": len(messages),
                "offers": offers,
                "reputation_after": dict(reputation),
                "usages": usages,
            }
        )
    return rows


# Эпизоды спора за одну дозу O. Карты короче, чтобы цитату можно было сверить строкой.
CONFLICTS = [
    {
        "id": "c1",
        "liar": "onko",
        "patients": {
            "travma": {"group": "O", "true_urgency": 5, "evidence": "ДТП, шок, АД 70/40"},
            "onko": {"group": "O", "true_urgency": 1, "evidence": "плановый визит, Hb 110"},
        },
    },
    {
        "id": "c2",
        "liar": "rod",
        "patients": {
            "rod": {"group": "A", "true_urgency": 2, "evidence": "кесарево утром, запас есть"},
            "travma": {"group": "O", "true_urgency": 4, "evidence": "ножевое, гемоторакс, пульс 124"},
        },
    },
    {
        "id": "c3",
        "liar": "onko",
        "patients": {
            "rod": {"group": "O", "true_urgency": 5, "evidence": "атония, кровопотеря продолжается"},
            "onko": {"group": "O", "true_urgency": 2, "evidence": "курс можно сдвинуть, Hb 101"},
        },
    },
    {
        "id": "c4",
        "liar": None,
        "patients": {
            "rod": {"group": "O", "true_urgency": 5, "evidence": "разрыв матки, ШИ 150"},
            "travma": {"group": "O", "true_urgency": 4, "evidence": "падение с высоты, свободная жидкость"},
        },
    },
    {
        "id": "c5",
        "liar": "travma",
        "patients": {
            "travma": {"group": "B", "true_urgency": 3, "evidence": "ушиб, наблюдение, Hb 99"},
            "onko": {"group": "O", "true_urgency": 4, "evidence": "кровоточивость, Hb 61"},
        },
    },
    {
        "id": "c6",
        "liar": "onko",
        "patients": {
            "rod": {"group": "O", "true_urgency": 3, "evidence": "предлежание, запас времени 6 ч"},
            "onko": {"group": "O", "true_urgency": 1, "evidence": "выписка завтра, Hb 112"},
        },
    },
]
