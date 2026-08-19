"""Unhabits: things the user wants to stop doing.

Unhabits live in the `unhabits` key of the user data dict, next to `habits`
and `todos`. Each entry has the same shape as a habit (id, name, records), so
it reuses DictHabit for record and tick handling. Checking a day means the
user successfully avoided the unhabit that day.
"""

from beaverhabits.storage.dict import DictHabit
from beaverhabits.utils import generate_short_hash


class DictUnhabitList:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.is_new = "unhabits" not in data
        if self.is_new:
            self.data["unhabits"] = []

    @property
    def unhabits(self) -> list[DictHabit]:
        return [DictHabit(d, self) for d in self.data["unhabits"]]

    async def get_unhabit_by(self, unhabit_id: str) -> DictHabit | None:
        for unhabit in self.unhabits:
            if unhabit.id == unhabit_id:
                return unhabit
        return None

    async def add(self, name: str) -> str:
        unhabit_id = generate_short_hash(name)
        self.data["unhabits"].append(
            {"id": unhabit_id, "name": name, "records": []}
        )
        return unhabit_id

    async def remove(self, unhabit: DictHabit) -> None:
        self.data["unhabits"].remove(unhabit.data)
