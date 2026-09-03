from agent.trade_log import TRADE_FIELDS, TradeLog


def test_append_and_load_roundtrip(tmp_path):
    log = TradeLog(tmp_path / "history.json")

    added = log.append({"symbol": "AAPL", "order_id": "abc", "status": "filled"})
    trades = log.load()

    assert added is True
    assert len(trades) == 1
    assert trades[0]["symbol"] == "AAPL"
    # Every schema field is present even though the entry omitted most of them.
    assert set(trades[0]) == set(TRADE_FIELDS)


def test_append_dedups_by_order_id(tmp_path):
    log = TradeLog(tmp_path / "history.json")

    assert log.append({"symbol": "AAPL", "order_id": "abc"}) is True
    assert log.append({"symbol": "AAPL", "order_id": "abc"}) is False
    assert len(log.load()) == 1


def test_entries_without_order_id_are_all_kept(tmp_path):
    log = TradeLog(tmp_path / "history.json")

    log.append({"symbol": "AAPL", "order_id": None})
    log.append({"symbol": "AAPL", "order_id": None})

    assert len(log.load()) == 2


def test_missing_file_loads_empty(tmp_path):
    log = TradeLog(tmp_path / "nope.json")

    assert log.load() == []


def test_corrupt_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("not valid json {", encoding="utf-8")
    log = TradeLog(path)

    assert log.load() == []
    # A subsequent append still works and produces a valid file.
    assert log.append({"symbol": "MSFT", "order_id": "x"}) is True
    assert len(log.load()) == 1
