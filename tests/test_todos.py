import asyncio
import datetime

from nicegui import ui
from nicegui.testing import User

from beaverhabits.frontend.index_page import index_page_ui
from beaverhabits.frontend.todo_page import todo_page_ui
from beaverhabits.storage.todo import DictTodoList
from beaverhabits.views import STARTER_TODOS, dummy_habit_list, seed_todo_list


def make_todo_list() -> DictTodoList:
    return DictTodoList({"habits": []})


def test_todo_list_created_empty():
    data = {"habits": []}
    todo_list = DictTodoList(data)
    assert todo_list.is_new
    assert todo_list.todos == []
    assert data["todos"] == []


def test_existing_todo_list_is_not_new():
    data = {"todos": [{"id": "1", "name": "x", "done": True}]}
    todo_list = DictTodoList(data)
    assert not todo_list.is_new
    assert len(todo_list.todos) == 1
    assert todo_list.todos[0].done
    assert str(todo_list.todos[0]) == "x [x]"


async def test_add_and_get_todo():
    todo_list = make_todo_list()
    todo_id = await todo_list.add("Ir al médico")

    todo = await todo_list.get_todo_by(todo_id)
    assert todo is not None
    assert todo.name == "Ir al médico"
    assert not todo.done
    assert todo.created_at > 0
    assert await todo_list.get_todo_by("missing") is None


async def test_rename_todo():
    todo_list = make_todo_list()
    todo_id = await todo_list.add("old")
    todo = await todo_list.get_todo_by(todo_id)
    todo.name = "new"
    assert todo_list.todos[0].name == "new"


async def test_toggle_done_sets_timestamp():
    todo_list = make_todo_list()
    todo_id = await todo_list.add("Aprender a manejar")
    todo = await todo_list.get_todo_by(todo_id)

    todo.done = True
    assert todo.done
    assert todo.data["done_at"] is not None

    todo.done = False
    assert not todo.done
    assert todo.data["done_at"] is None


async def test_remove_and_clear_done():
    todo_list = make_todo_list()
    done_id = await todo_list.add("done item")
    await todo_list.add("open item")
    todo = await todo_list.get_todo_by(done_id)
    todo.done = True

    await todo_list.clear_done()
    assert [t.name for t in todo_list.todos] == ["open item"]

    await todo_list.remove(todo_list.todos[0])
    assert todo_list.todos == []


async def test_todos_share_dict_with_habits():
    data = {"habits": []}
    todo_list = DictTodoList(data)
    await todo_list.add("Tomar tereré")
    assert data["todos"][0]["name"] == "Tomar tereré"


async def test_seed_starter_todos_once():
    todo_list = make_todo_list()
    await seed_todo_list(todo_list)
    assert [t.name for t in todo_list.todos] == list(STARTER_TODOS)

    # Seeding runs only on first creation.
    await seed_todo_list(todo_list)
    assert len(todo_list.todos) == len(STARTER_TODOS)


async def test_todo_page(user: User):
    todo_list = make_todo_list()
    await todo_list.add("Ir al médico")

    @ui.page("/")
    def page():
        todo_page_ui(todo_list)

    await user.open("/")
    await user.should_see("Todos")
    await user.should_see("Ir al médico")


async def test_todo_page_empty(user: User):
    todo_list = make_todo_list()

    @ui.page("/")
    def page():
        todo_page_ui(todo_list)

    await user.open("/")
    await user.should_see("List is empty.")


async def test_todo_page_interactions(user: User):
    todo_list = make_todo_list()

    @ui.page("/")
    def page():
        todo_page_ui(todo_list)

    await user.open("/")
    await user.should_see("List is empty.")

    # Empty names are rejected.
    user.find("todo-add").click()
    await asyncio.sleep(0.1)
    assert todo_list.todos == []

    # Add a todo.
    user.find("todo-input").type("Ir al médico")
    user.find("todo-add").click()
    await user.should_not_see("List is empty.")
    await user.should_see("Ir al médico")
    assert [t.name for t in todo_list.todos] == ["Ir al médico"]

    # Toggle it done.
    user.find("todo-done").click()
    await asyncio.sleep(0.1)
    assert todo_list.todos[0].done

    # Delete it.
    user.find("todo-delete").click()
    await user.should_see("List is empty.")
    assert todo_list.todos == []


async def test_index_page_shows_habits_and_todos(user: User):
    today = datetime.date(2024, 5, 1)
    days = [today - datetime.timedelta(days=i) for i in reversed(range(5))]
    habits = dummy_habit_list(days)
    todo_list = make_todo_list()
    await todo_list.add("Ir al médico")

    @ui.page("/")
    def page():
        index_page_ui(days, habits, todo_list)

    await user.open("/")
    await user.should_see("Habits")
    await user.should_see("Todos")
    await user.should_see("Ir al médico")
