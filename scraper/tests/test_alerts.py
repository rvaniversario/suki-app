from scraper import alerts


def item(id, name, pct, status, lowest=False, featured=True, price=100.0):
    return {
        "id": id,
        "name": name,
        "unit": "kg",
        "price": price,
        "pctVsBaseline": pct,
        "status": status,
        "lowest90": lowest,
        "featured": featured,
    }


ITEMS = [
    item("fish.tilapia", "Tilapia", -8.0, "buy"),
    item("pork.kasim", "Pork kasim", -4.2, "buy"),
    item("beef.rump", "Beef rump", 12.0, "skip"),
    item("chicken.whole", "Whole chicken", -1.0, "ok", lowest=True),
    item("fish.bangus-large", "Bangus (large)", -5.0, "buy", featured=False),
]
LATEST = {"region": "mimaropa", "asOf": "2026-11-10", "items": ITEMS}


def test_newly_buy_and_lowest_trigger():
    prev = {"fish.tilapia": "ok", "pork.kasim": "buy", "chicken.whole": "ok"}
    got = [i["id"] for i in alerts.alert_items(ITEMS, prev, None)]
    # kasim was already "buy" yesterday; bangus is not tracked by default (not featured); rump is pricier
    assert got == ["fish.tilapia", "chicken.whole"]


def test_tracked_ids_override_featured():
    got = [i["id"] for i in alerts.alert_items(ITEMS, {}, ["fish.bangus-large"])]
    assert got == ["fish.bangus-large"]


def test_message_lists_three_then_more():
    many = [item(f"x{i}", f"Item {i}", -10.0 + i, "buy") for i in range(5)]
    title, body = alerts.message(many, "en")
    assert title == "Good buys today"
    assert body == "Item 0 10% below usual, Item 1 9% below usual, Item 2 8% below usual and 2 more"


def test_message_localised():
    title, body = alerts.message([ITEMS[0]], "fil")
    assert title == "Sulit bilhin ngayon"
    assert "Tilapia 8% mas mura" in body


def test_lowest_item_without_drop_has_its_own_wording():
    _, body = alerts.message([item("a", "Tilapia", 0.0, "ok", lowest=True)], "en")
    assert body == "Tilapia at its lowest in 90 days"


class FakeSubs:
    def __init__(self, subs):
        self.subs = {s["id"]: s for s in subs}
        self.deleted, self.sent = [], []

    def list(self, region):
        return [s for s in self.subs.values() if s["region"] == region]

    def delete(self, sub_id):
        self.deleted.append(sub_id)
        self.subs.pop(sub_id)

    def mark_sent(self, sub_id, report_date):
        self.sent.append(sub_id)
        self.subs[sub_id]["last_notified_for"] = report_date


def sub(id, **kw):
    return {"id": id, "endpoint": f"https://push/{id}", "p256dh": "k", "auth": "a", "region": "mimaropa", "tracked_ids": None, "language": "en", **kw}


def test_one_notification_per_subscriber_per_report_date():
    subs = FakeSubs([sub("a"), sub("b", last_notified_for="2026-11-10"), sub("c", region="ncr")])
    calls = []
    stats = alerts.send_for_region(LATEST, {}, subs, lambda s, p: calls.append((s["id"], p)))
    assert [c[0] for c in calls] == ["a"]
    assert stats.sent == 1 and stats.skipped == 1
    # running again for the same report date sends nothing
    stats = alerts.send_for_region(LATEST, {}, subs, lambda s, p: calls.append((s["id"], p)))
    assert len(calls) == 1 and stats.sent == 0


def test_no_notification_when_list_is_empty():
    subs = FakeSubs([sub("a", tracked_ids=["beef.rump"])])
    calls = []
    stats = alerts.send_for_region(LATEST, {}, subs, lambda s, p: calls.append(s))
    assert calls == [] and stats.skipped == 1


def test_expired_subscriptions_are_removed():
    subs = FakeSubs([sub("gone"), sub("ok")])

    def sender(s, payload):
        if s["id"] == "gone":
            raise alerts.Gone("410")

    stats = alerts.send_for_region(LATEST, {}, subs, sender)
    assert subs.deleted == ["gone"]
    assert stats.removed == 1 and stats.sent == 1


def test_other_errors_do_not_stop_the_run():
    subs = FakeSubs([sub("bad"), sub("ok")])

    def sender(s, payload):
        if s["id"] == "bad":
            raise RuntimeError("push service down")

    stats = alerts.send_for_region(LATEST, {}, subs, sender)
    assert stats.failed == 1 and stats.sent == 1 and subs.deleted == []
