import asyncio
import json
import os
import random
import subprocess
import sys
import time
import tracemalloc
from dataclasses import replace
from itertools import count

import pytest
from feedlog.chains import Chain, retry_chains
from feedlog.live import follow
from feedlog.record import FeedbackRecord
from feedlog.runner import FeedbackRunner, JsonlSink, loop_can_advance
from feedlog.store import FeedbackLog
from feedlog.truncate import truncate_lines


class FakeShell:
    """Stands in for subprocess.run: answers each argv from a script and notes every call."""

    def __init__(self, script: dict) -> None:
        self.script = script
        self.calls: list[tuple] = []

    def __call__(self, argv, cwd, timeout):
        self.calls.append((argv, cwd, timeout))
        outcome = self.script[tuple(argv)]
        if isinstance(outcome, BaseException):
            raise outcome
        code, out, err = outcome
        return subprocess.CompletedProcess(argv, code, out, err)


def keep_last(n: int):
    """A stand-in for truncate_lines (Part 3): keeps the last n lines and says how many it cut."""

    def truncate(text: str) -> tuple[str, int]:
        closed = text.endswith("\n")
        lines = (text[:-1] if closed else text).split("\n") if text else []
        if len(lines) <= n:
            return text, 0
        return "\n".join(lines[-n:]) + ("\n" if closed else ""), len(lines) - n

    return truncate


def numbered(prefix: str = "cmd"):
    counter = count(1)
    return lambda: f"{prefix}-{next(counter)}"


def written(path) -> list[FeedbackRecord]:
    return [FeedbackRecord.from_json(line) for line in path.read_text(encoding="utf-8").split("\n")[:-1]]


_rng = random.Random(37)
_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
KEY_LINES = ["".join(_rng.choice(_B64) for _ in range(64)) for _ in range(50)]
PEM = "-----BEGIN RSA PRIVATE KEY-----\n" + "\n".join(KEY_LINES) + "\n-----END RSA PRIVATE KEY-----\n"

PYTEST_OUT = b"....F.....\nFAILED tests/test_api.py::test_refund - assert 402 == 200\n1 failed, 9 passed in 0.84s\n"
BOOT_HEAD = (
    "bootstrap: checking toolchain\n"
    "python 3.12.7 at /usr/local/bin/python3\n"
    "node 22.11.0 at /usr/local/bin/node\n"
    "locale: en_US.UTF-8\n"
    "keyboard: us-intl\n"
    "tokenizer=fast\n"
    "cache dir: /home/ci/.cache/bootstrap\n"
    "generating deploy key\n"
    "wrote /home/ci/.ssh/deploy_key (mode 600)\n"
    "--- deploy_key ---\n"
)
BOOT_FOOT = "--- end ---\nbootstrap: done in 4.2s\n"
LOGO = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xd8"
WAITING = [f"waiting for db:5432 (attempt {i})" for i in range(1, 36)]
WAIT_OUT = (
    "".join(line + "\n" for line in WAITING)
    + "auth: Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.ci-runner.c2lnbmF0dXJl\n"
    + "still waiting for db:5432\n"
)
SHELL = {
    ("pytest", "-q"): (1, PYTEST_OUT, b""),
    ("./scripts/wait-for-db.sh", "--host", "db"): subprocess.TimeoutExpired(
        ["./scripts/wait-for-db.sh", "--host", "db"],
        2.0,
        output=WAIT_OUT.encode(),
        stderr=b"dsn: host=db port=5432 user=ci password=ci-s3cret\npsql: connection to server at db:5432 refused\n",
    ),
    ("./scripts/bootstrap.sh", "--verbose"): (0, (BOOT_HEAD + PEM + BOOT_FOOT).encode(), b""),
    ("pnpm", "install"): FileNotFoundError(2, "No such file or directory", "pnpm"),
    ("./scripts/release.sh", "--dry-run"): PermissionError(13, "Permission denied", "./scripts/release.sh"),
    ("./scripts/migrate.sh",): OSError(8, "Exec format error", "./scripts/migrate.sh"),
    ("cat", "assets/logo.png"): (0, LOGO, b""),
    ("pytest", "-q", "--lf"): (0, b".\n1 passed in 0.12s\n", b""),
}


@pytest.mark.skip("Part 1")
def test_runner(tmp_path) -> None:
    """Every command leaves one record with no secret in it, and the loop moves on only with an exit code."""
    path = tmp_path / "feedback.jsonl"
    shell = FakeShell(SHELL)
    runner = FeedbackRunner(JsonlSink(path), execute=shell, truncate=keep_last(30), new_id=numbered())

    tests = runner.run(["pytest", "-q"], note="expect 10 passed")
    assert (tests.command_id, tests.command, tests.cwd, tests.agent_note) == (
        "cmd-1", ["pytest", "-q"], os.getcwd(), "expect 10 passed",
    ), "the record keeps the exact argv, where it ran and the agent's note"
    assert (tests.exit_code, tests.error, tests.stdout_tail) == (1, None, PYTEST_OUT.decode())
    assert loop_can_advance(tests), "a failing exit code is feedback the loop has to react to"

    wait = runner.run(["./scripts/wait-for-db.sh", "--host", "db"], note="expect the db to come up", timeout_s=2.0)
    assert wait.exit_code is None, "a command that ran out of time has no exit code"
    assert wait.error == "timeout after 2.0s", "error says why there is no exit code"
    assert (wait.stdout_tail, wait.stderr_tail) == (
        "".join(line + "\n" for line in WAITING[7:])
        + "auth: Authorization: Bearer [REDACTED]\nstill waiting for db:5432\n",
        "dsn: host=db port=5432 user=ci password=[REDACTED]\npsql: connection to server at db:5432 refused\n",
    ), "what a command printed before it timed out is kept, redacted and truncated like any other output"
    assert (wait.truncations, wait.redactions) == ({"stdout": 7, "stderr": 0}, {"stdout": 1, "stderr": 1}), (
        "truncations and redactions count, per stream, the lines cut and the secrets replaced"
    )
    assert not loop_can_advance(wait), "no exit code, no progress"

    boot = runner.run(["./scripts/bootstrap.sh", "--verbose"], note="expect the toolchain to check out")
    assert not any(line in boot.stdout_tail for line in KEY_LINES), (
        "no part of a private key reaches the record, not even when the cut runs through it"
    )
    assert boot.stdout_tail == BOOT_HEAD + "[REDACTED PRIVATE KEY]\n" + BOOT_FOOT, (
        "the key is replaced and every other line is kept as it is"
    )
    assert (boot.truncations, boot.redactions) == ({"stdout": 0, "stderr": 0}, {"stdout": 1, "stderr": 0})

    missing = runner.run(["pnpm", "install"], note="expect the deps to install", cwd="web")
    assert not loop_can_advance(missing), "a command that never started gave no feedback"
    assert missing.exit_code is None, "a command that never started has no exit code"
    assert (missing.exit_code, missing.error) == (
        None, "FileNotFoundError: [Errno 2] No such file or directory: 'pnpm'",
    ), "error names the exception class and its message"
    assert missing.cwd == "web", "the record says where the command ran"

    denied = runner.run(["./scripts/release.sh", "--dry-run"], note="expect a release plan")
    assert (denied.exit_code, denied.error) == (
        None, "PermissionError: [Errno 13] Permission denied: './scripts/release.sh'",
    ), "any command that cannot start still gets its record"
    migrate = runner.run(["./scripts/migrate.sh"], note="expect the migrations to apply")
    assert (migrate.exit_code, migrate.error) == (
        None, "OSError: [Errno 8] Exec format error: './scripts/migrate.sh'",
    ), "any command that cannot start still gets its record"

    logo = runner.run(["cat", "assets/logo.png"], note="expect a PNG header")
    assert (logo.exit_code, logo.stdout_tail) == (0, "\ufffdPNG\r\n\x1a\n\x00\x00\x00\rIHDR\ufffd\ufffd"), (
        "bytes that are not UTF-8 become U+FFFD"
    )

    retry = runner.run(["pytest", "-q", "--lf"], note="expect the refund test to pass now", parent=tests.command_id)
    assert (retry.parent_command_id, retry.exit_code) == ("cmd-1", 0), "a retry points at the attempt it retries"
    assert written(path) == [tests, wait, boot, missing, denied, migrate, logo, retry], "every command leaves exactly one record"
    assert [call[1:] for call in shell.calls[1:4]] == [(None, 2.0), (None, 30.0), ("web", 30.0)], (
        "each command runs where it was asked to, with its own timeout"
    )

    real = FeedbackRunner(JsonlSink(tmp_path / "real.jsonl"), truncate=keep_last(30)).run(
        [sys.executable, "-c", "import sys; print('built 3 wheels'); print('cache miss', file=sys.stderr); sys.exit(3)"],
    )
    assert (real.exit_code, real.stdout_tail, real.stderr_tail) == (3, "built 3 wheels\n", "cache miss\n"), (
        "the default executor runs the real command"
    )


def sized(i: int, nbytes: int) -> FeedbackRecord:
    """Record number i, padded so that its line in the log, newline included, is exactly nbytes long."""
    record = FeedbackRecord(
        command_id=f"r{i:02d}",
        parent_command_id=None if i % 10 == 0 else f"r{i - 1:02d}",
        command=["pytest", "-q", f"tests/test_case_{i}.py"],
        cwd="/srv/checkout",
        stdout_tail=f"✓ {i} passed\n" if i % 4 else "",
        stderr_tail="",
        exit_code=None if i % 7 == 3 else i % 3,
        duration_ms=1000 + i,
        started_at=1761984000.0 + i / 10,
        agent_note="",
        error="timeout after 30.0s" if i % 7 == 3 else None,
        truncations={"stdout": i % 5, "stderr": 0},
        redactions={"stdout": 0, "stderr": i % 2},
    )
    room = nbytes - len(record.to_json().encode("utf-8")) - 1
    padded = replace(record, agent_note="📦" * (room // 4) + "!" * (room % 4))
    assert len(padded.to_json().encode("utf-8")) + 1 == nbytes
    return padded


def lines_of(*records: FeedbackRecord) -> bytes:
    return "".join(record.to_json() + "\n" for record in records).encode("utf-8")


@pytest.mark.skip("Part 2")
def test_rotating_log(tmp_path) -> None:
    """Records come back exactly, the loop reads one small file, and CI gets the whole history in order."""
    path = tmp_path / "feedback.jsonl"
    backup = tmp_path / "feedback.jsonl.bak"
    backup.write_bytes(lines_of(sized(99, 400)))
    assert (FeedbackLog(path).current(), FeedbackLog(path).load_all()) == ([], []), (
        "a log with no file yet is empty, whatever else is in the directory"
    )

    records = [sized(i, 700) for i in range(30)]
    log = FeedbackLog(path, max_bytes=1800, keep=12)
    for i, record in enumerate(records):
        if i == 15:
            log = FeedbackLog(path, max_bytes=1800, keep=12)
        log.append(record)
    rotated = [tmp_path / f"feedback.jsonl.{n}" for n in range(1, 13)]
    assert sorted(tmp_path.iterdir()) == sorted([path, backup, *rotated]), (
        "the log keeps feedback.jsonl.1 to feedback.jsonl.12 and deletes anything older"
    )
    assert [p.stat().st_size for p in [path, *rotated]] == [1400] * 13, (
        "no file grows past max_bytes, counted in bytes: two of these records fit in a file"
    )
    assert (rotated[0].read_bytes(), rotated[11].read_bytes()) == (lines_of(*records[26:28]), lines_of(*records[4:6])), (
        "each file holds whole records, the newest in feedback.jsonl.1"
    )
    assert log.current() == records[28:], "the loop reads the current file only"
    assert log.load_all() == records[4:], "load_all reads every file the log keeps, oldest first"
    by_id = {record.command_id: record for record in log.load_all()}
    chain = ["r29"]
    while by_id[chain[-1]].parent_command_id is not None:
        chain.append(by_id[chain[-1]].parent_command_id)
    assert chain == [f"r{i}" for i in range(29, 19, -1)], "a retry chain can be followed through the rotated files"

    exact = sized(30, 400)
    log.append(exact)
    assert (path.read_bytes(), log.current()) == (lines_of(*records[28:], exact), [*records[28:], exact]), (
        "a file may fill up to max_bytes exactly"
    )
    big = sized(31, 4000)
    log.append(big)
    assert path.read_bytes() == lines_of(big) and rotated[0].read_bytes() == lines_of(*records[28:], exact), (
        "a record larger than max_bytes gets a file to itself"
    )
    after = sized(32, 700)
    FeedbackLog(path, max_bytes=1800, keep=12).append(after)
    assert (rotated[0].read_bytes(), path.read_bytes()) == (lines_of(big), lines_of(after)), (
        "the next record rotates it out, whole"
    )
    assert log.load_all() == records[8:] + [exact, big, after]
    first = tmp_path / "fresh" / "feedback.jsonl"
    first.parent.mkdir()
    FeedbackLog(first, max_bytes=1800, keep=12).append(big)
    assert (list(first.parent.iterdir()), first.read_bytes()) == ([first], lines_of(big)), (
        "a large record that starts a log has nothing to rotate"
    )
    fresh = FeedbackLog(first, max_bytes=1800, keep=12)
    fresh.append(sized(33, 1400))
    fresh.append(sized(34, 401))
    assert fresh.current() == [sized(34, 401)], "no file grows past max_bytes, not even by one byte"
    assert backup.read_bytes() == lines_of(sized(99, 400)), "files that are not part of the log are left alone"


LOG = [f"collected item {i}" for i in range(100)]
ODD = (
    "build 1/4\r\n"
    "progress 10%\r50%\r100%\n"
    "form feed\x0cpage 2\n"
    "fields\x1cseparated\x1dby\x1econtrol codes\n"
    "vertical\x0btab\n"
    "next line\x85here\n"
    "unicode\u2028line\u2029separators\n"
    "done\r\n"
)
INSTANCES = [f"aws_instance.web[{i}]: Creation complete after 31s [id=i-0{i:04x}]" for i in range(40)]
PROVISION = (
    "provision: generating deploy key\n"
    + PEM
    + "provision: creating 40 instances\n"
    + "".join(line + "\n" for line in INSTANCES)
    + "provision: done, 40 instances up\n"
)


@pytest.mark.skip("Part 3")
def test_truncate_lines(tmp_path) -> None:
    """The first and last lines, one marker between them, nothing sampled; lines end at \\n and nowhere else."""
    text = "\n".join(LOG) + "\n"
    assert truncate_lines(text, head=5, tail=30) == ("\n".join(LOG[:5] + ["...truncated 65 lines..."] + LOG[70:]) + "\n", 65), (
        "keep the first head lines and the last tail lines"
    )
    assert truncate_lines(text, head=60, tail=40) == (text, 0), "nothing is cut when head and tail cover every line"
    assert truncate_lines(text, head=60, tail=39) == ("\n".join(LOG[:60] + ["...truncated 1 lines..."] + LOG[61:]) + "\n", 1), (
        "the marker is always ...truncated N lines..., even for one line"
    )
    assert truncate_lines(text, head=3, tail=0) == ("\n".join(LOG[:3] + ["...truncated 97 lines..."]) + "\n", 97), (
        "tail=0 keeps no tail lines"
    )
    assert truncate_lines(text, head=0, tail=2) == ("...truncated 98 lines...\ncollected item 98\ncollected item 99\n", 98)
    assert truncate_lines("\n".join(LOG), head=5, tail=30) == (
        "\n".join(LOG[:5] + ["...truncated 65 lines..."] + LOG[70:]), 65,
    ), "the result ends with \\n exactly when text does"
    assert truncate_lines("", head=5, tail=30) == ("", 0)
    assert truncate_lines("\n\n\n", head=1, tail=1) == ("\n...truncated 1 lines...\n\n", 1), "empty lines are lines"
    assert truncate_lines(ODD, head=2, tail=2) == (
        "build 1/4\r\nprogress 10%\r50%\r100%\n...truncated 4 lines...\nunicode\u2028line\u2029separators\ndone\r\n", 4,
    ), "lines end at \\n and nowhere else"
    with pytest.raises(ValueError):
        truncate_lines(text, head=-1, tail=30)
    with pytest.raises(ValueError):
        truncate_lines(text, head=5, tail=-1)

    access = [f"[{i:06d}] GET /api/v1/orders/{i % 977} 200 {i % 13}ms" for i in range(60000)]
    access_log = "".join(line + "\n" for line in access)
    start = time.perf_counter()
    kept = truncate_lines(access_log)
    elapsed = time.perf_counter() - start
    assert kept == ("\n".join(access[:5] + ["...truncated 59965 lines..."] + access[-30:]) + "\n", 59965)
    assert elapsed < 0.1, "truncating a long log should be quick"

    shell = FakeShell({("./scripts/provision.sh",): (0, PROVISION.encode(), b"")})
    record = FeedbackRunner(JsonlSink(tmp_path / "feedback.jsonl"), execute=shell).run(["./scripts/provision.sh"])
    assert record.stdout_tail == "\n".join(
        ["provision: generating deploy key", "[REDACTED PRIVATE KEY]", "provision: creating 40 instances", *INSTANCES[:2]]
        + ["...truncated 9 lines..."] + INSTANCES[11:] + ["provision: done, 40 instances up"]
    ) + "\n", "the runner keeps 5 + 30 lines of the output with the key already gone"
    assert (record.truncations, record.redactions) == ({"stdout": 9, "stderr": 0}, {"stdout": 1, "stderr": 0})


class FakePipe:
    """One end of a pipe that holds a single write: the writer waits until all of it has been read."""

    def __init__(self) -> None:
        self.data = b""
        self.closed = False
        self.reads = 0
        self._readable: asyncio.Future | None = None
        self._drained: asyncio.Future | None = None

    async def read(self, n: int = -1) -> bytes:
        """Like asyncio.StreamReader.read: up to n bytes once some arrive, or everything up to EOF for n=-1."""
        self.reads += 1
        if n < 0:
            parts = []
            while chunk := await self._next(-1):
                parts.append(chunk)
            return b"".join(parts)
        return await self._next(n)

    async def _next(self, n: int) -> bytes:
        while not self.data and not self.closed:
            self._readable = asyncio.get_running_loop().create_future()
            await self._readable
        size = len(self.data) if n < 0 else min(n, len(self.data))
        chunk, self.data = self.data[:size], self.data[size:]
        if not self.data:
            _wake(self._drained)
        return chunk

    async def write(self, data: bytes) -> None:
        self.data += data
        _wake(self._readable)
        while self.data and not self.closed:
            self._drained = asyncio.get_running_loop().create_future()
            await self._drained

    def close(self) -> None:
        self.closed = True
        _wake(self._readable)
        _wake(self._drained)


def _wake(future) -> None:
    if future is not None and not future.done():
        future.set_result(None)


class FakeProcess:
    """Stands in for asyncio.subprocess.Process and plays a script, one step at a time.

    ("stdout", data) or ("stderr", data) writes to that pipe and waits until all of it has been read;
    a number sleeps that many seconds; "close" closes both pipes. After the last step the pipes are
    closed and the process exits with exit_code. kill() ends it at once with -9. A write that nobody
    reads for 3 seconds makes it give up, so a stuck test fails instead of hanging: the pipes close
    and it exits with -13.
    """

    def __init__(self, script, exit_code: int = 0) -> None:
        self.stdout = FakePipe()
        self.stderr = FakePipe()
        self.returncode: int | None = None
        self.written = 0
        self.killed = False
        self.stuck = False
        self.reads_at_kill: int | None = None
        self._exited = asyncio.get_running_loop().create_future()
        self._play = asyncio.ensure_future(self._run(script, exit_code))

    async def _run(self, script, exit_code: int) -> None:
        for step in script:
            if step == "close":
                self.stdout.close()
                self.stderr.close()
            elif isinstance(step, (int, float)):
                await asyncio.sleep(step)
            else:
                name, data = step
                try:
                    await asyncio.wait_for(getattr(self, name).write(data), 3.0)
                except asyncio.TimeoutError:
                    self.stuck = True
                    break
                self.written += 1
                for _ in range(16):
                    await asyncio.sleep(0)
        self.stdout.close()
        self.stderr.close()
        self._exit(-13 if self.stuck else exit_code)

    def _exit(self, code: int) -> None:
        if self.returncode is None:
            self.returncode = code
            self._exited.set_result(code)

    async def wait(self) -> int:
        return await asyncio.shield(self._exited)

    def kill(self) -> None:
        if self.returncode is None:
            self.killed = True
            self.reads_at_kill = self.stdout.reads + self.stderr.reads
            self._play.cancel()
            self.stdout.close()
            self.stderr.close()
            self._exit(-9)

    @property
    def reads_after_kill(self) -> int:
        return self.stdout.reads + self.stderr.reads - (self.reads_at_kill or 0)


def follow_script(script, command, exit_code: int = 0, **options):
    async def main():
        process = FakeProcess(script, exit_code)
        items = [item async for item in follow(process, command, **options)]
        return process, items

    return asyncio.run(main())


def parse(items: list[bytes]):
    """The progress lines as (pipe, bytes) pairs, and the record."""
    assert items and all(item.endswith(b"\n") for item in items), "every yield is one or more whole lines"
    *progress, last = b"".join(items).split(b"\n")[:-1]
    tag, _, body = last.partition(b" ")
    assert tag == b"[record]" and items[-1] == last + b"\n", "the record comes last: one line, in a yield of its own"
    pairs = []
    for line in progress:
        tag, _, rest = line.partition(b" ")
        assert tag in (b"[stdout]", b"[stderr]"), f"unexpected progress line {line[:40]!r}"
        pairs.append((tag[1:-1].decode(), rest))
    return pairs, json.loads(body)


COMPILES = [f"  [{i:2d}/40] compiling numpy/_core/src/npymath/m{i:02d}.c" for i in range(1, 41)]
PIP = [
    ("stdout", b"Collecting numpy==2.1.0\n"),
    ("stdout", b"  Downloading numpy-2.1.0.tar.gz (18.9 MB)\n"),
    ("stderr", b"warning: no wheel for numpy, building from source\n"),
    ("stdout", b"Building wheels for coll"),
    ("stderr", b"  gcc -O2 -c numpy/_core/src/multiarray/ctors.c\n  gcc -O2 -c numpy/_core/src/umath/loops.c\n"),
    ("stdout", b"ected packages: numpy\n  Building wheel for numpy (pyproject.toml): started\n"),
    *[("stdout", line.encode() + b"\n") for line in COMPILES],
    ("stderr", b"warning: caf\xe9 locale fallback\r\n"),
    ("stdout", b"Successfully installed numpy-2.1.0"),
]


@pytest.mark.skip("Part 4")
def test_follow() -> None:
    """Output goes out line by line while the command runs, in bounded memory, and the deadline is the deadline."""
    process, items = follow_script(PIP, ["pip", "install", "numpy==2.1.0"], head=2, tail=3, timeout_s=1.0)
    progress, record = parse(items)
    assert progress == [
        ("stdout", b"Collecting numpy==2.1.0"),
        ("stdout", b"  Downloading numpy-2.1.0.tar.gz (18.9 MB)"),
        ("stderr", b"warning: no wheel for numpy, building from source"),
        ("stderr", b"  gcc -O2 -c numpy/_core/src/multiarray/ctors.c"),
        ("stderr", b"  gcc -O2 -c numpy/_core/src/umath/loops.c"),
        ("stdout", b"Building wheels for collected packages: numpy"),
        ("stdout", b"  Building wheel for numpy (pyproject.toml): started"),
        *[("stdout", line.encode()) for line in COMPILES],
        ("stderr", b"warning: caf\xe9 locale fallback\r"),
        ("stdout", b"Successfully installed numpy-2.1.0"),
    ], "each line goes out once it is complete, in the order the command finished it, bytes as written"
    assert (
        b"[stderr]   gcc -O2 -c numpy/_core/src/multiarray/ctors.c\n[stderr]   gcc -O2 -c numpy/_core/src/umath/loops.c\n"
        in items
    ), "the lines one chunk completes go out together, in one yield"
    assert record == {
        "command": ["pip", "install", "numpy==2.1.0"],
        "exit_code": 0,
        "error": None,
        "stdout_tail": "Collecting numpy==2.1.0\n  Downloading numpy-2.1.0.tar.gz (18.9 MB)\n...truncated 40 lines...\n"
        + "\n".join(COMPILES[-2:])
        + "\nSuccessfully installed numpy-2.1.0",
        "stderr_tail": "warning: no wheel for numpy, building from source\n  gcc -O2 -c numpy/_core/src/multiarray/ctors.c\n"
        "  gcc -O2 -c numpy/_core/src/umath/loops.c\nwarning: caf\ufffd locale fallback\r\n",
        "truncations": {"stdout": 40, "stderr": 0},
    }, "each pipe keeps its own first and last lines"

    async def first_line():
        process = FakeProcess([("stdout", f"step {i}\n".encode()) for i in range(100)])
        stream = follow(process, ["make", "-j8"])
        first = await stream.__anext__()
        seen = process.written
        await stream.aclose()
        process.kill()
        return first, seen

    first, seen = asyncio.run(first_line())
    assert first == b"[stdout] step 0\n" and seen <= 2, "a line goes out as soon as the chunk that ends it is read"

    process, items = follow_script(
        [("stdout", b"waiting for port 8000\n"), ("stdout", b"retrying in 5s"), 1.0, ("stdout", b" ... server up\n")],
        ["./scripts/serve.sh"],
        timeout_s=0.05,
    )
    progress, record = parse(items)
    assert (process.written, process.reads_after_kill) == (2, 0), "at the deadline the follower kills the command and stops reading"
    assert (process.killed, record["exit_code"], record["error"]) == (True, None, "timeout after 0.05s"), (
        "a command killed at the deadline has no exit code"
    )
    assert (progress, record["stdout_tail"]) == (
        [("stdout", b"waiting for port 8000"), ("stdout", b"retrying in 5s")], "waiting for port 8000\nretrying in 5s",
    ), "the line being written at the deadline still goes out"

    process, items = follow_script(
        [step for i in range(30) for step in (("stdout", f"test_{i:02d} ... ok\n".encode()), 0.02)], ["pytest", "-v"], timeout_s=0.2,
    )
    progress, record = parse(items)
    assert (process.killed, record["exit_code"], process.written < 30) == (True, None, True), (
        "the whole run gets timeout_s, not each read"
    )

    process, items = follow_script([1.0], ["git", "fetch", "origin"], timeout_s=0.05)
    progress, record = parse(items)
    assert (process.killed, record["exit_code"], progress) == (True, None, []), (
        "a command that prints nothing is killed at the deadline too"
    )

    process, items = follow_script(
        [("stdout", b"daemon started, pid 4242\n"), 0.15, "close", 0.15], ["./scripts/start-daemon.sh"], timeout_s=0.2,
    )
    progress, record = parse(items)
    assert (process.killed, record["exit_code"], record["error"]) == (True, None, "timeout after 0.2s"), (
        "waiting for the exit counts against the deadline too"
    )

    def flood():
        for c in range(500):
            yield "stdout", b"".join(f"[{c:03d}:{i:02d}] tests/test_case_{c}_{i}.py PASSED in 0.01s\n".encode() for i in range(100))

    async def consume():
        process = FakeProcess(flood())
        lines, last = 0, b""
        async for item in follow(process, ["pytest", "-q"], head=5, tail=30):
            lines += item.count(b"\n")
            last = item
        return lines, json.loads(last.partition(b" ")[2])

    tracemalloc.start()
    try:
        lines, record = asyncio.run(consume())
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert (lines, record["truncations"], record["exit_code"]) == (50001, {"stdout": 49965, "stderr": 0}, 0)
    assert peak < 1_000_000, "memory stays flat however much the command prints"

    async def real():
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "import sys; print('collected 3 items'); print('slow test', file=sys.stderr); print('3 passed')",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        return [item async for item in follow(process, ["pytest"], timeout_s=30.0)]

    progress, record = parse(asyncio.run(real()))
    assert sorted(progress) == [("stderr", b"slow test"), ("stdout", b"3 passed"), ("stdout", b"collected 3 items")]
    assert (record["exit_code"], record["stdout_tail"]) == (0, "collected 3 items\n3 passed\n"), "follow works on a real subprocess"


def attempt(cid: str, parent: str | None, exit_code: int | None, started_at: float) -> FeedbackRecord:
    return FeedbackRecord(
        command_id=cid,
        parent_command_id=parent,
        command=["make", cid],
        cwd="/srv/checkout",
        stdout_tail="",
        stderr_tail="",
        exit_code=exit_code,
        duration_ms=100,
        started_at=started_at,
        agent_note="",
    )


SESSION = [
    attempt("a1", None, 1, 100.0),
    attempt("b1", None, 0, 101.0),
    attempt("a2", "a1", 1, 102.0),
    attempt("c1", "gone-7", 2, 103.0),
    attempt("d1", None, None, 104.0),
    attempt("a3", "a2", 0, 99.0),
    attempt("e1", None, 1, 105.0),
    attempt("d2", "d1", 2, 106.0),
    attempt("c2", "c1", 0, 107.0),
    attempt("e2", "e1", None, 108.0),
    attempt("d3", "d2", -9, 109.0),
    attempt("d4", "d2", 0, 110.0),
    attempt("f1", "gone-3", 1, 111.0),
    attempt("g1", "gone-3", 0, 112.0),
]


@pytest.mark.skip("Part 5")
def test_retry_chains() -> None:
    """Retries link into chains that fork, survive rotation as orphans, and show the latest real failure."""
    chains = retry_chains(SESSION)
    assert [tuple(chain.attempts) for chain in chains] == [
        ("b1",), ("a1", "a2", "a3"), ("c1", "c2"), ("e1", "e2"), ("d1", "d2", "d3"), ("d1", "d2", "d4"), ("f1",), ("g1",),
    ], "one chain per attempt nobody retried, first attempt first, in the order those last attempts were written"
    assert [chain.orphaned_from for chain in chains] == [None, None, "gone-7", None, None, None, "gone-3", "gone-3"], (
        "a chain whose first attempt retries a record that is gone says which one"
    )
    assert [chain.exit_code for chain in chains] == [0, 0, 0, None, -9, 0, 1, 0], "a chain ends with its last attempt's exit code"
    assert [chain.last_failure for chain in chains] == [None, "a2", "c1", "e1", "d3", "d2", "f1", None], (
        "last_failure is the latest attempt that exited non-zero: no exit code is not a failure, -9 is"
    )
    assert chains == [
        Chain(("b1",), None, 0, None),
        Chain(("a1", "a2", "a3"), None, 0, "a2"),
        Chain(("c1", "c2"), "gone-7", 0, "c1"),
        Chain(("e1", "e2"), None, None, "e1"),
        Chain(("d1", "d2", "d3"), None, -9, "d3"),
        Chain(("d1", "d2", "d4"), None, 0, "d2"),
        Chain(("f1",), "gone-3", 1, "f1"),
        Chain(("g1",), "gone-3", 0, None),
    ], "chains are Chain values, attempts a tuple"
    assert retry_chains([]) == []

    polls = [attempt("p0", None, 1, 0.0)] + [attempt(f"p{i}", f"p{i - 1}", 1, float(i)) for i in range(1, 1500)]
    polls[-1] = replace(polls[-1], exit_code=0)
    assert retry_chains(polls) == [Chain(tuple(f"p{i}" for i in range(1500)), None, 0, "p1498")], (
        "a chain of 1500 attempts is fine"
    )

    with pytest.raises(ValueError):
        retry_chains([attempt("x1", None, 0, 1.0), attempt("x1", None, 1, 2.0)])
    with pytest.raises(ValueError):
        retry_chains([attempt("y1", "y2", 1, 1.0), attempt("y2", "y1", 1, 2.0)])
    with pytest.raises(ValueError):
        retry_chains([attempt("z1", "z1", 1, 1.0)])
    with pytest.raises(ValueError):
        retry_chains([attempt("w2", "w1", 0, 2.0), attempt("w1", None, 1, 1.0)])
