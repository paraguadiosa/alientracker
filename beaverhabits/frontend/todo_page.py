from collections.abc import Callable

from nicegui import ui

from beaverhabits.configs import settings
from beaverhabits.frontend.components import (
    PRESS_DELAY,
    menu_icon_item,
    separator,
)
from beaverhabits.frontend.layout import layout
from beaverhabits.storage.todo import DictTodo, DictTodoList

CARD_CLASSES = "pl-4 pr-2 py-0 dark:shadow-none theme-card-shadow w-full"

# Reorder support (drag handle on each row, like the habit order page).
# The drop handler is registered once per client; the refresh callback is
# looked up lazily because the todo section is rebuilt when the embedding
# page refreshes.
_todo_drop_registered: set[str] = set()
_todo_script_added: set[str] = set()
_todo_refresh: dict[str, Callable] = {}

SORTABLE_SCRIPT = """<script type="module">
import '/statics/libs/sortable.min.js';
if (!window.__todoSortableInited) {
    window.__todoSortableInited = true;
    const initTodoSortable = () => {
        const el = document.querySelector('.todo-sortable');
        if (el && !el.__todoSortable) {
            Sortable.create(el, {
                handle: '.todo-drag-handle',
                animation: 150,
                ghostClass: 'opacity-50',
                onEnd: (evt) => emitEvent("todo_drop", {
                    id: evt.item.dataset.todoId,
                    new_index: evt.newIndex,
                }),
            });
            el.__todoSortable = true;
        }
    };
    document.addEventListener('DOMContentLoaded', initTodoSortable);
    new MutationObserver(initTodoSortable).observe(document.body, {childList: true, subtree: true});
}
</script>"""


async def todo_item_drop(e, todo_list: DictTodoList, refresh: Callable | None = None) -> None:
    """Reorder the todo list after a Sortable drop."""
    todo_id = e.args["id"]
    new_index = int(e.args["new_index"])
    todo = await todo_list.get_todo_by(todo_id)
    if todo is None:
        return
    await todo_list.move(todo, new_index)
    if refresh:
        refresh()


def register_todo_drop(todo_list: DictTodoList) -> None:
    """Wire the todo_drop event to the reorder handler, once per client.

    The refresh callback is resolved at event time, so re-renders of the
    todo section keep working after the embedding page refreshes.
    """
    client = ui.context.client
    if client.id in _todo_drop_registered:
        return
    _todo_drop_registered.add(client.id)
    ui.on(
        "todo_drop",
        lambda e: todo_item_drop(e, todo_list, _todo_refresh.get(client.id)),
    )


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
    card.props(f'data-todo-id="{todo.id}"')
    card.mark("todo-card")
    with card, ui.row().classes("w-full items-center no-wrap theme-todo-row"):
        # Drag handle: reorder the todo, same pattern as the habit order page.
        handle = ui.icon("drag_indicator")
        handle.classes("todo-drag-handle cursor-grab")
        handle.props('aria-hidden="true"')
        handle.mark("todo-drag-handle")

        # Clicking the name toggles done (tracker-style).
        name = ui.label(todo.name).classes(
            "truncate cursor-pointer text-primary theme-todo-name"
        )
        name.props(f'role="heading" aria-level="2" aria-label="{todo.name}"')
        if todo.done:
            # Dim green strikethrough; inline !important wins over .text-primary.
            name.classes("line-through").style("color: #1f8a4c !important")
        else:
            # Same neon glow as the habit name links.
            name.classes("theme-glow-text")
        name.props(f'data-long-press-delay="{PRESS_DELAY}"')
        name.on("click", toggle_by_click)
        name.mark("todo-name")

        # Menu button: the QMenu is nested inside so Quasar anchors it
        # to the button and the popup renders on top of it.
        menu_btn = ui.button(icon="more_vert")
        menu_btn.props("flat unelevated dense")
        menu_btn.classes("todo-menu-faint")
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

    # External Tasks link (shown only when TASKS_URL is configured).
    if settings.TASKS_URL:
        link = ui.link("Open Tasks", target=settings.TASKS_URL, new_tab=True)
        link.props('icon=open_in_new aria-label="Open external Tasks app"')
        link.classes("text-sm")
        link.mark("tasks-link")

    # The refreshable is defined per page build, so a refresh only re-renders
    # the current client and never touches other connected clients.
    @ui.refreshable
    def todo_list_ui():
        todos = todo_list.todos
        if not todos:
            ui.label("List is empty.").classes("mx-auto w-80 max-w-full")
            return

        with ui.column().classes("todo-sortable gap-1.5 w-full"):
            for todo in todos:
                todo_row(todo_list, todo, todo_list_ui.refresh)

    # Keep the drop handler wired to the current page and refreshable.
    client = ui.context.client
    _todo_refresh[client.id] = todo_list_ui.refresh
    register_todo_drop(todo_list)
    if client.id not in _todo_script_added:
        _todo_script_added.add(client.id)
        ui.add_body_html(SORTABLE_SCRIPT)

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
        add_btn.classes("theme-add-btn")
        add_btn.mark("todo-add")


def todo_page_ui(todo_list: DictTodoList):
    with layout(title="Todos"):
        todo_section(todo_list)
