import asyncio
import datetime

from nicegui import ui
from nicegui.testing import User

from beaverhabits.frontend.index_page import index_page_ui
from beaverhabits.frontend.unhabit_page import unhabit_page_ui
from beaverhabits.storage.unhabit import DictUnhabitList
from beaverhabits.views import dummy_habit_list


def make_unhabit_list() -> DictUnhabitList:
    return DictUnhabitList({"habits": []})


def make_days(count: int = 5) -> list[datetime.date]:
    today = datetime.date(2024, 5, 1)
    return [today - datetime.timedelta(days=i) for i in reversed(range(count))]


def test_unhabit_list_created_empty():
    data = {"habits": []}
    unhabit_list = DictUnhabitList(data)
    assert unhabit_list.is_new
    assert unhabit_list.unhabits == []
    assert data["unhabits"] == []


def test_existing_unhabit_list_is_not_new():
    data = {"unhabits": [{"id": "1", "name": "x", "records": []}]}
    unhabit_list = DictUnhabitList(data)
    assert not unhabit_list.is_new
    assert len(unhabit_list.unhabits) == 1
    assert unhabit_list.unhabits[0].name == "x"


async def test_add_and_get_unhabit():
    unhabit_list = make_unhabit_list()
    unhabit_id = await unhabit_list.add("Doomscrolling")

    unhabit = await unhabit_list.get_unhabit_by(unhabit_id)
    assert unhabit is not None
    assert unhabit.name == "Doomscrolling"
    assert unhabit.ticked_days == []
    assert await unhabit_list.get_unhabit_by("missing") is None


async def test_rename_unhabit():
    unhabit_list = make_unhabit_list()
    unhabit_id = await unhabit_list.add("old")
    unhabit = await unhabit_list.get_unhabit_by(unhabit_id)
    unhabit.name = "new"
    assert unhabit_list.unhabits[0].name == "new"


async def test_tick_unhabit_marks_avoided_day():
    unhabit_list = make_unhabit_list()
    unhabit_id = await unhabit_list.add("Snacking")
    unhabit = await unhabit_list.get_unhabit_by(unhabit_id)

    day = datetime.date(2024, 5, 1)
    await unhabit.tick(day, True)
    assert day in unhabit.ticked_days
    assert unhabit.record_by(day).done

    await unhabit.tick(day, False)
    assert day not in unhabit.ticked_days


async def test_remove_unhabit():
    unhabit_list = make_unhabit_list()
    await unhabit_list.add("one")
    await unhabit_list.add("two")
    await unhabit_list.remove(unhabit_list.unhabits[0])
    assert [u.name for u in unhabit_list.unhabits] == ["two"]


async def test_unhabits_share_dict_with_habits():
    data = {"habits": []}
    unhabit_list = DictUnhabitList(data)
    await unhabit_list.add("Smoking")
    assert data["unhabits"][0]["name"] == "Smoking"


async def test_unhabit_page(user: User):
    unhabit_list = make_unhabit_list()
    await unhabit_list.add("Doomscrolling")
    days = make_days()

    @ui.page("/")
    def page():
        unhabit_page_ui(unhabit_list, days)

    await user.open("/")
    await user.should_see("Unhabits")
    await user.should_see("Doomscrolling")


async def test_unhabit_page_empty(user: User):
    unhabit_list = make_unhabit_list()
    days = make_days()

    @ui.page("/")
    def page():
        unhabit_page_ui(unhabit_list, days)

    await user.open("/")
    await user.should_see("Nothing to unlearn yet.")


async def test_unhabit_page_interactions(user: User):
    unhabit_list = make_unhabit_list()
    days = make_days()

    @ui.page("/")
    def page():
        unhabit_page_ui(unhabit_list, days)

    await user.open("/")
    await user.should_see("Nothing to unlearn yet.")

    # Empty names are rejected.
    user.find("unhabit-add").click()
    await asyncio.sleep(0.1)
    assert unhabit_list.unhabits == []

    # Add an unhabit.
    user.find("unhabit-input").type("Doomscrolling")
    user.find("unhabit-add").click()
    await user.should_not_see("Nothing to unlearn yet.")
    await user.should_see("Doomscrolling")
    assert [u.name for u in unhabit_list.unhabits] == ["Doomscrolling"]

    # Edit it via the menu button.
    user.find("unhabit-menu-btn").click()
    user.find("unhabit-edit").click()
    await asyncio.sleep(0.1)
    user.find("unhabit-edit-input").type(" late")
    user.find("unhabit-save").click()
    await asyncio.sleep(0.1)
    assert unhabit_list.unhabits[0].name == "Doomscrolling late"

    # Delete it via the menu button.
    user.find("unhabit-menu-btn").click()
    user.find("unhabit-delete").click()
    await user.should_see("Nothing to unlearn yet.")
    assert unhabit_list.unhabits == []


async def test_index_page_shows_habits_and_unhabits(user: User):
    today = datetime.date(2024, 5, 1)
    days = [today - datetime.timedelta(days=i) for i in reversed(range(5))]
    habits = dummy_habit_list(days)
    unhabit_list = make_unhabit_list()
    await unhabit_list.add("Doomscrolling")

    @ui.page("/")
    def page():
        index_page_ui(days, habits, unhabit_list=unhabit_list)

    await user.open("/")
    await user.should_see("Habits")
    await user.should_see("Unhabits")
    await user.should_see("Doomscrolling")
