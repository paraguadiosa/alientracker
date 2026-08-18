"""One-off todo items, stored in the same user data dict as the habits.

The `todos` key lives next to `habits`, so persistence (disk or database)
works through the existing observable-dict backup mechanism.
"""

import time

from beaverhabits.utils import generate_short_hash


class DictTodo:
    def __init__(self, data: dict, todo_list: "DictTodoList") -> None:
        self.data = data
        self._todo_list = todo_list

    @property
    def todo_list(self) -> "DictTodoList":
        return self._todo_list

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @name.setter
    def name(self, value: str) -> None:
        self.data["name"] = value

    @property
    def done(self) -> bool:
        return self.data.get("done", False)

    @done.setter
    def done(self, value: bool) -> None:
        self.data["done"] = value
        self.data["done_at"] = int(time.time()) if value else None

    @property
    def created_at(self) -> int:
        return self.data.get("created_at", 0)

    def to_dict(self) -> dict:
        return self.data

    def __str__(self):
        return f"{self.name} {'[x]' if self.done else '[ ]'}"

    __repr__ = __str__


class DictTodoList:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.is_new = "todos" not in data
        if self.is_new:
            self.data["todos"] = []

    @property
    def todos(self) -> list[DictTodo]:
        return [DictTodo(d, self) for d in self.data["todos"]]

    async def get_todo_by(self, todo_id: str) -> DictTodo | None:
        for todo in self.todos:
            if todo.id == todo_id:
                return todo
        return None

    async def add(self, name: str) -> str:
        todo_id = generate_short_hash(name)
        d = {
            "id": todo_id,
            "name": name,
            "done": False,
            "created_at": int(time.time()),
        }
        self.data["todos"].append(d)
        return todo_id

    async def remove(self, todo: DictTodo) -> None:
        self.data["todos"].remove(todo.data)

    async def clear_done(self) -> None:
        self.data["todos"][:] = [t.data for t in self.todos if not t.done]
