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

    # Toggle it done via the checkbox.
    user.find("todo-done").click()
    await asyncio.sleep(0.1)
    assert todo_list.todos[0].done

    # Edit it via the menu button.
    user.find("todo-menu-btn").click()
    user.find("todo-edit").click()
    await asyncio.sleep(0.1)
    user.find("todo-edit-input").type(" con doc")
    user.find("todo-save").click()
    await asyncio.sleep(0.1)
    assert todo_list.todos[0].name == "Ir al médico con doc"

    # Delete it via the menu button.
    user.find("todo-menu-btn").click()
    user.find("todo-delete").click()
    await user.should_see("List is empty.")
    assert todo_list.todos == []


async def test_todo_name_click_toggles_done(user: User):
    """Clicking the todo name toggles done; clicking again toggles back."""
    todo_list = make_todo_list()

    @ui.page("/")
    def page():
        todo_page_ui(todo_list)

    await user.open("/")

    user.find("todo-input").type("Buy milk")
    user.find("todo-add").click()
    await asyncio.sleep(0.1)
    await user.should_see("Buy milk")
    assert not todo_list.todos[0].done

    # First click toggles to done.
    user.find("todo-name").click()
    await asyncio.sleep(0.1)
    assert todo_list.todos[0].done

    # Second click toggles back to not done.
    user.find("todo-name").click()
    await asyncio.sleep(0.1)
    assert not todo_list.todos[0].done


async def test_todo_menu_btn_opens_menu(user: User):
    """The menu button exists and clicking it reveals edit/delete items."""
    todo_list = make_todo_list()

    @ui.page("/")
    def page():
        todo_page_ui(todo_list)

    await user.open("/")

    user.find("todo-input").type("Task")
    user.find("todo-add").click()
    await asyncio.sleep(0.1)
    await user.should_see("Task")

    # The menu button is present.
    menu_btn = user.find("todo-menu-btn")

    # Clicking it reveals the edit and delete menu items.
    menu_btn.click()
    await asyncio.sleep(0.1)
    await user.should_see("Edit")
    await user.should_see("Delete")


async def test_todo_name_has_text_primary_class(user: User):
    """The todo name label uses text-primary and the glow so it matches the habit hue."""
    todo_list = make_todo_list()

    @ui.page("/")
    def page():
        todo_page_ui(todo_list)

    await user.open("/")

    user.find("todo-input").type("Hue check")
    user.find("todo-add").click()
    await asyncio.sleep(0.1)
    await user.should_see("Hue check")

    name_element = user.find("todo-name")
    # UserInteraction.elements contains the underlying NiceGUI elements.
    name_label = next(iter(name_element.elements))
    assert "text-primary" in name_label._classes
    assert "theme-glow-text" in name_label._classes


async def test_done_todo_uses_dim_hue(user: User):
    """A completed todo is dimmed with a strikethrough instead of glowing."""
    todo_list = make_todo_list()

    @ui.page("/")
    def page():
        todo_page_ui(todo_list)

    await user.open("/")

    user.find("todo-input").type("Done item")
    user.find("todo-add").click()
    await asyncio.sleep(0.1)
    await user.should_see("Done item")

    # Mark it done via the checkbox.
    user.find("todo-done").click()
    await asyncio.sleep(0.1)

    name_element = user.find("todo-name")
    name_label = next(iter(name_element.elements))
    assert "line-through" in name_label._classes
    assert "theme-glow-text" not in name_label._classes


async def test_tasks_link_shown_when_url_set(user: User):
    """When TASKS_URL is set, todo_section renders a tasks-link element."""
    from beaverhabits.configs import settings

    original = settings.TASKS_URL
    settings.TASKS_URL = "https://tasks.example.com"
    try:
        todo_list = make_todo_list()

        @ui.page("/")
        def page():
            todo_page_ui(todo_list)

        await user.open("/")
        link_element = user.find("tasks-link")
        link = next(iter(link_element.elements))
        assert link._props.get("href") == "https://tasks.example.com"
    finally:
        settings.TASKS_URL = original


async def test_tasks_link_hidden_when_url_empty(user: User):
    """When TASKS_URL is empty, no tasks-link element exists."""
    from beaverhabits.configs import settings

    original = settings.TASKS_URL
    settings.TASKS_URL = ""
    try:
        todo_list = make_todo_list()

        @ui.page("/")
        def page():
            todo_page_ui(todo_list)

        await user.open("/")
        await user.should_see("List is empty.")
        await user.should_not_see(marker="tasks-link")
    finally:
        settings.TASKS_URL = original


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
