import datetime
from collections.abc import Callable

from nicegui import ui

from beaverhabits.configs import settings
from beaverhabits.core.completions import get_habit_date_completion
from beaverhabits.frontend.components import (
    PRESS_DELAY,
    HabitCheckBox,
    menu_icon_item,
    separator,
)
from beaverhabits.frontend.layout import layout
from beaverhabits.storage.dict import DictHabit
from beaverhabits.storage.unhabit import DictUnhabitList

NAME_COLS, DATE_COLS = settings.INDEX_HABIT_NAME_COLUMNS, 2
LEFT_CLASSES = f"col-span-{NAME_COLS} truncate max-w-[{24 * NAME_COLS}px]"
RIGHT_CLASSES = f"col-span-{DATE_COLS} px-1 place-self-center"
CARD_CLASSES = "pl-4 pr-2 py-0 dark:shadow-none theme-unhabit-card-shadow w-full"
STICKY_STYLES = "position: sticky; top: 0; z-index: 1;"


def grid(columns, rows):
    g = ui.grid(columns=columns, rows=rows)
    g.classes("w-full gap-0 items-center")
    return g


def week_headers(days: list[datetime.date]):
    for day in days:
        yield day.strftime("%a")


def day_headers(days: list[datetime.date]):
    for day in days:
        yield day.strftime("%d")


def unhabit_edit_dialog(unhabit: DictHabit) -> ui.dialog:
    async def save():
        new_name = name_input.value.strip() if name_input.value else ""
        if not new_name:
            ui.notify("Unhabit name is required", color="negative")
            return
        unhabit.name = new_name
        dialog.submit(True)

    with ui.dialog() as dialog, ui.card().props("flat") as card:
        dialog.props('backdrop-filter="blur(4px)"')
        card.classes("w-5/6 max-w-96")

        name_input = ui.input("Name", value=unhabit.name).classes("w-full")
        name_input.mark("unhabit-edit-input")
        name_input.on("keydown.enter", save)

        with ui.row():
            save_btn = ui.button("Save", on_click=save)
            save_btn.mark("unhabit-save")
            ui.button("Cancel", on_click=dialog.close)

    return dialog


def unhabit_row(
    unhabit_list: DictUnhabitList,
    unhabit: DictHabit,
    days: list[datetime.date],
    refresh: Callable,
):
    edit_dialog = unhabit_edit_dialog(unhabit)

    async def remove():
        await unhabit_list.remove(unhabit)
        refresh()

    async def edit():
        if await edit_dialog:
            refresh()

    today = max(days)
    status_map = get_habit_date_completion(unhabit, min(days), today)

    with ui.row().classes("items-center no-wrap").classes(LEFT_CLASSES):
        name = ui.label(unhabit.name).classes("truncate theme-unhabit-glow-text")
        name.props(f'role="heading" aria-level="2" aria-label="{unhabit.name}"')
        name.props(f'data-long-press-delay="{PRESS_DELAY}"')
        name.mark("unhabit-name")

        # Menu button: nested so the QMenu anchors to it and the popup renders
        # on top of the row.
        menu_btn = ui.button(icon="more_vert")
        menu_btn.props('flat unelevated dense')
        menu_btn.props('aria-label="Unhabit actions"')
        menu_btn.classes("theme-unhabit-menu-btn")
        menu_btn.mark("unhabit-menu-btn")
        with menu_btn:
            with ui.menu() as menu:
                menu.props("auto-close transition-duration=0")
                menu_icon_item("Edit", edit).mark("unhabit-edit")
                separator()
                menu_icon_item("Delete", remove).mark("unhabit-delete")

        name.on("long-press.prevent", menu.open)
        name.on("contextmenu", menu.open)

    for day in days:
        status = status_map.get(day, [])
        checkbox = HabitCheckBox(status, unhabit, today, day, refresh=refresh)
        checkbox.classes(RIGHT_CLASSES)
        checkbox.classes("theme-unhabit-checkbox")


def unhabit_section(unhabit_list: DictUnhabitList, days: list[datetime.date]):
    """Unhabit tracker plus add form, without page layout. Embeddable in any page."""

    title = ui.label("Unhabits").classes("text-lg theme-unhabit-glow-text")
    title.props('role="heading" aria-level="2"')

    @ui.refreshable
    def unhabit_list_ui():
        unhabits = unhabit_list.unhabits
        if not unhabits:
            ui.label("Nothing to unlearn yet.").classes("mx-auto w-80")
            return

        columns = NAME_COLS + len(days) * DATE_COLS

        with ui.column().classes("gap-1.5 w-full"):
            # Date headers.
            with grid(columns, 2).classes(CARD_CLASSES).style(STICKY_STYLES) as g:
                g.props('aria-hidden="true"').classes("theme-unhabit-header-date")
                for it in (week_headers(days), day_headers(days)):
                    ui.label("").classes(LEFT_CLASSES)
                    for label in it:
                        ui.label(label).classes(RIGHT_CLASSES)

            # Unhabit rows.
            for unhabit in unhabits:
                with ui.card().classes(CARD_CLASSES):
                    with grid(columns, 1):
                        unhabit_row(
                            unhabit_list, unhabit, days, unhabit_list_ui.refresh
                        )

    async def add():
        name = name_input.value.strip() if name_input.value else ""
        if not name:
            ui.notify("Unhabit name is required", color="negative")
            return
        await unhabit_list.add(name)
        name_input.value = ""
        unhabit_list_ui.refresh()

    unhabit_list_ui()

    with ui.row().classes("w-full items-center no-wrap"):
        name_input = ui.input(placeholder="New unhabit...").classes("grow")
        name_input.on("keydown.enter", add)
        name_input.mark("unhabit-input")
        add_btn = ui.button("Add", on_click=add)
        add_btn.props('aria-label="Add unhabit"')
        add_btn.mark("unhabit-add")


def unhabit_page_ui(unhabit_list: DictUnhabitList, days: list[datetime.date]):
    with layout(title="Unhabits"):
        unhabit_section(unhabit_list, days)
