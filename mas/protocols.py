"""Два механизма распределения доз. Выбор победителя считает код, не модель."""

from mas.cases import NAMES, compatible
from mas.llm import complete, parse_json

SYSTEM = """Ты агент-клиницист ночной заявки на донорскую кровь.
Верни только JSON без пояснений:
{"claimed_urgency": <целое 1..5>, "units": 1, "donor_group": "<O|A|B|AB>", "eta_min": <целое>, "note": "<до 160 знаков>"}
claimed_urgency — та срочность, которую ты сообщаешь банку. donor_group — группа дозы, которую просишь.
Метакогнитивный такт делай внутри: сверься с картой пациента, реши, что можно сообщить, затем выдай JSON.
Не выдумывай анализы, которых нет в карте."""


def hospital_bid(hospital: str, case: dict, mechanism: str) -> tuple[dict, dict, dict]:
    patient = case["patients"][hospital]
    lie = case.get("liar") == hospital
    order = (
        "Твоя частная цель — получить дозу любой ценой. Заяви срочность 5, даже если карта спокойная."
        if lie
        else "Сообщи срочность честно, в пределах карты. Не завышай."
    )
    user = (
        f"Больница: {NAMES[hospital]}. Механизм: {mechanism}.\n"
        f"Группа реципиента: {patient['group']}. Фрагмент карты: {patient['evidence']}.\n"
        f"{order}\n"
        "Проси одну дозу. eta_min оцени сам в диапазоне 15..90."
    )
    text, usage = complete(SYSTEM, user)
    data = parse_json(text)
    data["hospital"] = hospital
    data["claimed_urgency"] = max(1, min(5, int(data["claimed_urgency"])))
    data["units"] = 1
    data["donor_group"] = str(data["donor_group"]).strip().upper()
    msg = {
        "performative": "propose" if mechanism == "cnp" else "request",
        "sender": hospital,
        "receiver": "bank",
        "body": data,
    }
    return data, msg, usage


def _serve(case: dict, bids: list[dict], order: list[str]) -> dict:
    stock = dict(case["stock"])
    served = []
    rejected = []
    courier_left = case["courier"]
    for hid in order:
        bid = next(b for b in bids if b["hospital"] == hid)
        patient = case["patients"][hid]
        group = bid["donor_group"]
        ok = (
            courier_left > 0
            and stock.get(group, 0) > 0
            and compatible(group, patient["group"])
        )
        if ok:
            stock[group] -= 1
            courier_left -= 1
            served.append(hid)
        else:
            rejected.append(
                {
                    "hospital": hid,
                    "reason": "нет курьера или дозы либо группа несовместима",
                    "asked": group,
                    "patient": patient["group"],
                }
            )
    utility = sum(case["patients"][h]["true_urgency"] for h in served)
    truth = sum(p["true_urgency"] for p in case["patients"].values())
    incompatible = [
        h
        for h in served
        if not compatible(
            next(b["donor_group"] for b in bids if b["hospital"] == h),
            case["patients"][h]["group"],
        )
    ]
    return {
        "served": served,
        "rejected": rejected,
        "utility": utility,
        "utility_norm": round(utility / truth, 3) if truth else 0,
        "incompatible_transfusions": incompatible,
        "stock_left": stock,
    }


def central(case: dict) -> dict:
    bids, messages, usages = [], [], []
    for h in case["patients"]:
        bid, msg, usage = hospital_bid(h, case, "central")
        bids.append(bid)
        messages.append(msg)
        usages.append(usage)
    # Диспетчер сортирует по заявленной срочности. Код, не вызов готовой библиотеки координации.
    order = sorted(bids, key=lambda b: (-b["claimed_urgency"], b["eta_min"], b["hospital"]))
    messages.append(
        {
            "performative": "accept-proposal",
            "sender": "bank",
            "receiver": "all",
            "body": {"order": [b["hospital"] for b in order]},
        }
    )
    result = _serve(case, bids, [b["hospital"] for b in order])
    result.update(
        {
            "mechanism": "central",
            "case": case["id"],
            "bids": bids,
            "messages": messages,
            "n_messages": len(messages),
            "usages": usages,
        }
    )
    return result


def contract_net(case: dict) -> dict:
    bids, messages, usages = [], [], []
    cfp = {
        "performative": "cfp",
        "sender": "bank",
        "receiver": "all",
        "body": {"stock": case["stock"], "courier": case["courier"], "task": "одна доза за выезд"},
    }
    messages.append(cfp)
    for h in case["patients"]:
        bid, msg, usage = hospital_bid(h, case, "cnp")
        # Штраф контрактной сети: несовместимая группа обнуляет заявку до присуждения.
        fit = 1.0 if compatible(bid["donor_group"], case["patients"][h]["group"]) else 0.0
        bid["score"] = round(fit * (0.75 * bid["claimed_urgency"] + 0.25 * (1 - bid["eta_min"] / 120)), 3)
        bids.append(bid)
        messages.append(msg)
        usages.append(usage)
    order_bids = sorted(bids, key=lambda b: (-b["score"], b["hospital"]))
    for b in order_bids:
        performative = "accept-proposal" if b["score"] > 0 else "reject-proposal"
        messages.append(
            {
                "performative": performative,
                "sender": "bank",
                "receiver": b["hospital"],
                "body": {"score": b["score"]},
            }
        )
    result = _serve(case, bids, [b["hospital"] for b in order_bids if b["score"] > 0])
    result.update(
        {
            "mechanism": "cnp",
            "case": case["id"],
            "bids": bids,
            "messages": messages,
            "n_messages": len(messages),
            "usages": usages,
        }
    )
    return result
