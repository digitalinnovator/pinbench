"""In-memory row store."""


class Store:
    """Rows are dicts with a unique string "id" and an integer "created_at" timestamp."""

    def __init__(self):
        self._rows = []

    def add(self, id, created_at):
        self._rows.append({"id": id, "created_at": created_at})

    def delete(self, id):
        self._rows = [row for row in self._rows if row["id"] != id]

    def scan(self):
        """Return copies of all rows ordered by created_at, oldest first."""
        rows = sorted(self._rows, key=lambda row: row["created_at"])
        return [dict(row) for row in rows]
