import re
import sqlite3

import httpx

WRITE = re.compile(r"\s*(INSERT|UPDATE|DELETE|REPLACE)\b", re.IGNORECASE)


class Crash(BaseException):
    # Not an Exception, so no handler in Glue can catch it: it stands for the process dying.
    pass


class CrashingConnection:
    # Wraps Glue's connection, counts its writes and dies just before write number `at`.
    def __init__(self, conn: sqlite3.Connection, at: int = 0):
        self.conn = conn
        self.at = at
        self.writes: list[str] = []
        self.dead = False

    def execute(self, sql: str, params: object = ()) -> sqlite3.Cursor:
        self.before(sql, WRITE.match(sql) is not None)
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, rows: object) -> sqlite3.Cursor:
        self.before(sql, WRITE.match(sql) is not None)
        return self.conn.executemany(sql, rows)

    def executescript(self, script: str) -> sqlite3.Cursor:
        self.before(script, any(WRITE.match(part) for part in script.split(";")))
        return self.conn.executescript(script)

    def __getattr__(self, name: str) -> object:
        # in_transaction, commit, rollback and close: none of them writes a row.
        return getattr(self.conn, name)

    def before(self, sql: str, write: bool) -> None:
        # A dead process runs nothing more, reads included.
        if self.dead:
            raise Crash("after the crash")
        if not write:
            return
        self.writes.append(" ".join(sql.split()))
        if len(self.writes) == self.at:
            self.dead = True
            raise Crash(self.writes[-1])


class Webhooks:
    # Stands in for a sender's own retry: a webhook Glue never answered is sent again.
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.unanswered: list[tuple[str, dict]] = []

    async def post(self, url: str, **request: object) -> httpx.Response:
        sent = (url, request)
        self.unanswered.append(sent)
        response = await self.http.post(url, **request)
        self.unanswered.remove(sent)
        return response

    async def send_again(self) -> None:
        while self.unanswered:
            url, request = self.unanswered.pop(0)
            await self.http.post(url, **request)
