from scripts import load_probe


async def test_the_load_probe_reserves_every_order_once(tmp_path):
    numbers = await load_probe.probe(20, str(tmp_path / "glue.db"))

    assert (numbers["reserved"], numbers["duplicates"]) == (20, 0)
