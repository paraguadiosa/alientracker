from collections.abc import Callable

from nicegui import ui

from beaverhabits.frontend import icons
from beaverhabits.frontend.layout import layout
from beaverhabits.storage.todo import DictTodo, DictTodoList

CARD_CLASSES = "pl-4 pr-2 py-0 dark:shadow-none theme-card-shadow w-full"


def todo_row(todo_list: DictTodoList, todo: DictTodo, refresh: Callable):
    async def toggle(e):
        todo.done = e.value
        refresh()

    async def remove():
        await todo_list.remove(todo)
        refresh()

    card = ui.card().classes(CARD_CLASSES)
    with card, ui.row().classes("w-full items-center no-wrap"):
        name = ui.label(todo.name).classes("truncate")
        name.props(f'role="heading" aria-level="2" aria-label="{todo.name}"')
        if todo.done:
            name.classes("line-through").style("color: #1f8a4c")
        ui.space()
        checkbox = ui.checkbox(value=todo.done, on_change=toggle)
        checkbox.props(f'aria-label="Mark {todo.name} as done"')
        checkbox.mark("todo-done")
        delete = ui.button(icon=icons.DELETE, on_click=remove)
        delete.props("flat fab-mini color=grey-9")
        delete.props(f'aria-label="Delete {todo.name}"')
        delete.mark("todo-delete")


def todo_section(todo_list: DictTodoList):
    """Todo list plus add form, without page layout. Embeddable in any page."""

    # The refreshable is defined per page build, so a refresh only re-renders
    # the current client and never touches other connected clients.
    @ui.refreshable
    def todo_list_ui():
        todos = todo_list.todos
        if not todos:
            ui.label("List is empty.").classes("mx-auto w-80")
            return

        with ui.column().classes("gap-1.5 w-full"):
            for todo in todos:
                todo_row(todo_list, todo, todo_list_ui.refresh)

    async def add():
        name = name_input.value.strip() if name_input.value else ""
        if not name:
            ui.notify("Todo name is required", color="negative")
            return
        await todo_list.add(name)
        name_input.value = ""
        todo_list_ui.refresh()

    todo_list_ui()

    with ui.row().classes("w-full items-center no-wrap"):
        name_input = ui.input(placeholder="New todo...").classes("grow")
        name_input.on("keydown.enter", add)
        name_input.mark("todo-input")
        add_btn = ui.button("Add", on_click=add)
        add_btn.props('aria-label="Add todo"')
        add_btn.mark("todo-add")


def todo_page_ui(todo_list: DictTodoList):
    with layout(title="Todos"):
        todo_section(todo_list)
