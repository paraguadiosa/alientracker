# Alientracker

A self-hosted habit tracking app, alien-themed.

## Features

- Daily habit tracking with a green martian terminal theme.
- Todo list: one-off tasks shown side by side with the daily habits
  on the main page (`/gui`), and standalone at `/gui/todos`.
  On first use it is seeded with starter todos: "Ir al médico",
  "Aprender a manejar", "Tomar tereré".
  Todos live in the `todos` key of the existing user data store.
  Set `TASKS_URL` to link to an external task manager; empty hides the link.

## Origin

Alientracker is an independent project derived from
[Beaver Habit Tracker](https://github.com/daya0576/beaverhabits) by
Henry Zhu (daya0576), used under the BSD 3-Clause License.
Development started in the `alienhabits` fork and continues here.
See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE) for details.
