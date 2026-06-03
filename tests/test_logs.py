import time
import threading
from launcher.logs import resolve, tail_lines


def test_resolve_picks_newest_script_log(tmp_path):
    old = tmp_path / "script_2020.log"
    old.write_text("old")
    new = tmp_path / "script_2026.log"
    new.write_text("new")
    # make `new` newer
    import os
    os.utime(new, (time.time() + 10, time.time() + 10))
    paths = resolve(tmp_path)
    assert paths["script"] == new


def test_resolve_missing_returns_none(tmp_path):
    paths = resolve(tmp_path)
    assert paths["rpt"] is None


def test_resolve_client_from_separate_dir_not_server_log(tmp_path):
    server = tmp_path / "profiles"
    client = tmp_path / "profiles_client"
    server.mkdir()
    client.mkdir()
    srv_log = server / "script_srv.log"
    srv_log.write_text("server")
    cli_log = client / "script_cli.log"
    cli_log.write_text("client")
    paths = resolve(server, client)
    assert paths["script"] == srv_log
    assert paths["client"] == cli_log
    assert paths["client"] != paths["script"]  # the bug we fixed


def test_tail_lines_reads_existing_then_new(tmp_path):
    f = tmp_path / "script_x.log"
    f.write_text("line1\nline2\n", encoding="utf-8")
    gen = tail_lines(f, poll=0.01)
    assert next(gen) == "line1"
    assert next(gen) == "line2"
    with f.open("a", encoding="utf-8") as fh:
        fh.write("line3\n")
    assert next(gen) == "line3"
    gen.close()


def test_tail_lines_history_replays_only_last_n(tmp_path):
    f = tmp_path / "script_h.log"
    f.write_text("".join(f"line{i}\n" for i in range(1, 6)), encoding="utf-8")
    gen = tail_lines(f, poll=0.01, history=2)
    assert next(gen) == "line4"   # only the last 2 existing lines
    assert next(gen) == "line5"
    with f.open("a", encoding="utf-8") as fh:
        fh.write("line6\n")
    assert next(gen) == "line6"   # then follows new appends
    gen.close()


def test_tail_lines_should_stop_unblocks_quiet_follower(tmp_path):
    # A quiet log (no new lines) must still let a consumer thread exit when
    # should_stop flips — otherwise a follower worker would hang forever.
    f = tmp_path / "script_q.log"
    f.write_text("only\n", encoding="utf-8")
    stop = threading.Event()
    seen = []

    def consume():
        for line in tail_lines(f, poll=0.01, should_stop=stop.is_set):
            seen.append(line)

    t = threading.Thread(target=consume)
    t.start()
    time.sleep(0.1)        # consume the existing line, then idle in follow loop
    stop.set()             # ask it to stop while the file is quiet
    t.join(timeout=2)
    assert not t.is_alive()  # exited cleanly, no hang
    assert seen == ["only"]


from launcher.logs import last_lines


def test_last_lines_returns_tail(tmp_path):
    f = tmp_path / "script_x.log"
    f.write_text("".join(f"line{i}\n" for i in range(1, 11)), encoding="utf-8")
    assert last_lines(f, 3) == ["line8", "line9", "line10"]


def test_last_lines_missing_file(tmp_path):
    assert last_lines(tmp_path / "nope.log", 5) == []
