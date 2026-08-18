from collections.abc import Callable

from nicegui import ui

from beaverhabits.frontend.components import (
    PRESS_DELAY,
    menu_icon_item,
    separator,
)
from beaverhabits.frontend.layout import layout
from beaverhabits.storage.todo import DictTodo, DictTodoList

CARD_CLASSES = "pl-4 pr-2 py-0 dark:shadow-none theme-card-shadow w-full"


def todo_edit_dialog(todo: DictTodo) -> ui.dialog:
    async def save():
        new_name = name_input.value.strip() if name_input.value else ""
        if not new_name:
            ui.notify("Todo name is required", color="negative")
            return
        todo.name = new_name
        dialog.submit(True)

    with ui.dialog() as dialog, ui.card().props("flat") as card:
        dialog.props('backdrop-filter="blur(4px)"')
        card.classes("w-5/6 max-w-96")

        name_input = ui.input("Name", value=todo.name).classes("w-full")
        name_input.mark("todo-edit-input")
        name_input.on("keydown.enter", save)

        with ui.row():
            save_btn = ui.button("Save", on_click=save)
            save_btn.mark("todo-save")
            ui.button("Cancel", on_click=dialog.close)

    return dialog


def todo_row(todo_list: DictTodoList, todo: DictTodo, refresh: Callable):
    edit_dialog = todo_edit_dialog(todo)

    async def toggle(e):
        todo.done = e.value
        refresh()

    async def toggle_by_click():
        todo.done = not todo.done
        refresh()

    async def remove():
        await todo_list.remove(todo)
        refresh()

    async def edit():
        if await edit_dialog:
            refresh()

    card = ui.card().classes(CARD_CLASSES)
    with card, ui.row().classes("w-full items-center no-wrap"):
        # Clicking the name toggles done (tracker-style).
        name = ui.label(todo.name).classes("truncate cursor-pointer text-primary")
        name.props(f'role="heading" aria-level="2" aria-label="{todo.name}"')
        if todo.done:
            name.classes("line-through").style("color: #1f8a4c")
        name.props(f'data-long-press-delay="{PRESS_DELAY}"')
        name.on("click", toggle_by_click)
        name.mark("todo-name")

        # Menu button: the QMenu is nested inside so Quasar anchors it
        # to the button and the popup renders on top of it.
        menu_btn = ui.button(icon="more_vert")
        menu_btn.props('flat unelevated dense')
        menu_btn.props('aria-label="Todo actions"')
        menu_btn.mark("todo-menu-btn")
        with menu_btn:
            with ui.menu() as menu:
                menu.props("auto-close transition-duration=0")
                menu_icon_item("Edit", edit).mark("todo-edit")
                separator()
                menu_icon_item("Delete", remove).mark("todo-delete")

        # Long-press and contextmenu on the name still open the menu
        # (anchored to the button, not the row).
        name.on("long-press.prevent", menu.open)
        name.on("contextmenu", menu.open)

        ui.space()

        # Same icons and colors as the habit tracker checkboxes.
        checkbox = ui.checkbox("", value=todo.done, on_change=toggle)
        checkbox.props(
            'checked-icon="sym_o_check" unchecked-icon="sym_o_close" keep-color'
        )
        checkbox.classes("theme-icon-checkbox")
        checkbox.props(f'aria-label="Mark {todo.name} as done"')
        checkbox.mark("todo-done")


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
