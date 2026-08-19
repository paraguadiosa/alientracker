import datetime
from typing import List

from nicegui import ui

from beaverhabits import utils
from beaverhabits.configs import settings
from beaverhabits.core.completions import get_habit_date_completion
from beaverhabits.frontend import javascript, textarea
from beaverhabits.frontend.components import (
    HabitCheckBox,
    IndexStreakBadge,
    IndexTotalBadge,
    filter_habits_with_tags,
    habit_name_menu,
    habits_by_tags,
    note_tick,
    tag_filter_component,
)
from beaverhabits.frontend.layout import layout
from beaverhabits.frontend.todo_page import todo_section
from beaverhabits.frontend.unhabit_page import unhabit_section
from beaverhabits.storage.storage import (
    Habit,
    HabitList,
    HabitListBuilder,
    HabitStatus,
)
from beaverhabits.storage.todo import DictTodoList
from beaverhabits.storage.unhabit import DictUnhabitList

NAME_COLS, DATE_COLS = settings.INDEX_HABIT_NAME_COLUMNS, 2
COUNT_BADGE_COLS = 2 if settings.INDEX_SHOW_HABIT_COUNT else 0
COUNT_BADGE_COLS += 2 if settings.INDEX_SHOW_HABIT_STREAK else 0
LEFT_CLASSES, RIGHT_CLASSES = (
    # grid 5
    f"col-span-{NAME_COLS} truncate max-w-[{24 * NAME_COLS}px]",
    # grid 2 2 2 2 2
    f"col-span-{DATE_COLS} px-1 place-self-center",
)
COMPAT_CLASSES = "pl-4 pr-0 py-0 dark:shadow-none"

# Sticky date row for long habit list
STICKY_STYLES = "position: sticky; top: 0; z-index: 1;"


def grid(columns, rows):
    g = ui.grid(columns=columns, rows=rows)
    g.classes("w-full gap-0 items-center")
    return g


def week_headers(days: list[datetime.date]):
    for day in days:
        yield day.strftime("%a")
    if settings.INDEX_SHOW_HABIT_STREAK:
        yield "Stk"
    if settings.INDEX_SHOW_HABIT_COUNT:
        yield "Sum"


def day_headers(days: list[datetime.date]):
    for day in days:
        yield day.strftime("%d")
    if settings.INDEX_SHOW_HABIT_STREAK:
        yield "*"
    if settings.INDEX_SHOW_HABIT_COUNT:
        yield "#"


def habit_row(habit: Habit, tag: str, days: list[datetime.date]):
    name = habit_name_menu(habit, index_page_ui.refresh)
    name.classes(LEFT_CLASSES)
    name.props(f'role="heading" aria-level="2" aria-label="{habit.name}"')

    today = max(days)
    status_map = get_habit_date_completion(habit, min(days), today)
    for day in days:
        status = status_map.get(day, [])
        checkbox = HabitCheckBox(
            status, habit, today, day, refresh=habit_list_ui.refresh
        )
        checkbox.classes(RIGHT_CLASSES)
        # checkbox.classes("theme-icon-lazy invisible")

    if settings.INDEX_SHOW_HABIT_STREAK:
        IndexStreakBadge(today, habit).classes(RIGHT_CLASSES)

    if settings.INDEX_SHOW_HABIT_COUNT:
        IndexTotalBadge(today, habit).classes(RIGHT_CLASSES)


@ui.refreshable
def habit_list_ui(days: list[datetime.date], active_habits: List[Habit]):
    if settings.ENABLE_TAG_FILTERS:
        active_habits = filter_habits_with_tags(active_habits)

    # Total cloumn for each row
    columns = NAME_COLS + len(days) * DATE_COLS + COUNT_BADGE_COLS

    with ui.column().classes("gap-1.5"):
        # Date Headers
        with grid(columns, 2).classes(COMPAT_CLASSES).style(STICKY_STYLES) as g:
            g.props('aria-hidden="true"').classes("theme-header-date")
            for it in (week_headers(days), day_headers(days)):
                ui.label("").classes(LEFT_CLASSES)
                for label in it:
                    ui.label(label).classes(RIGHT_CLASSES)

        # Habit Rows
        groups = habits_by_tags(active_habits)

        for tag, habit_list in groups.items():
            if not habit_list:
                continue

            for habit in habit_list:
                with ui.card().classes(COMPAT_CLASSES).classes("theme-card-shadow"):
                    with grid(columns, 1):
                        habit_row(habit, tag, days)

            ui.space()


def get_active_habits(habits: HabitList) -> List[Habit]:
    return HabitListBuilder(habits).status(HabitStatus.ACTIVE).build()


def refresh_habit_list_when_today_changes(
    days: list[datetime.date], habits: HabitList
) -> None:
    rendered_today = max(days)

    async def refresh_if_needed() -> None:
        nonlocal rendered_today
        today = await utils.get_user_today_date()
        if today == rendered_today:
            return
        rendered_today = today
        new_days = await utils.dummy_days(settings.INDEX_HABIT_DATE_COLUMNS)
        if settings.INDEX_HABIT_DATE_REVERSE:
            new_days = list(reversed(new_days))
        habit_list_ui.refresh(new_days, get_active_habits(habits))

    ui.timer(60, refresh_if_needed, immediate=False)


@ui.refreshable
def index_page_ui(
    days: list[datetime.date],
    habits: HabitList,
    todo_list: DictTodoList | None = None,
    unhabit_list: DictUnhabitList | None = None,
):
    active_habits = get_active_habits(habits)
    if settings.INDEX_HABIT_DATE_REVERSE:
        days = list(reversed(days))

    with layout(habit_list=habits):
        # Stack on mobile, side by side on large screens.
        columns = ui.row().classes(
            "w-full items-start gap-4 flex-col lg:flex-row"
        )

        with columns, ui.column().classes("gap-1.5 w-full lg:w-auto"):
            if settings.ENABLE_TAG_FILTERS:
                tag_filter_component(active_habits, refresh=habit_list_ui.refresh)

            if not active_habits:
                ui.label("List is empty.").classes("mx-auto w-80")
            else:
                habit_list_ui(days, active_habits)

            if unhabit_list is not None:
                unhabit_section(unhabit_list, days)

        if todo_list is not None:
            with columns, ui.column().classes("w-full lg:w-[340px] shrink-0 gap-1.5") as todos_col:
                todos_col.mark("todos-column")
                todos_title = ui.label("Todos").classes("text-lg text-primary theme-glow-text")
                todos_title.props('role="heading" aria-level="2"')
                todo_section(todo_list)

    # placeholder to preload js cache (daily notes)
    textarea.Textarea("").classes("hidden").props('aria-hidden="true"')
    ui.input("").classes("hidden").props('aria-hidden="true"')
