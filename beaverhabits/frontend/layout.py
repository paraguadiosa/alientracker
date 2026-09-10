import time
from contextlib import contextmanager

from nicegui import background_tasks, ui

from beaverhabits import views
from beaverhabits.app.auth import user_logout
from beaverhabits.configs import settings
from beaverhabits.frontend import css, icons
from beaverhabits.frontend.components import (
    compat_card,
    habit_edit_dialog,
    menu_header,
    menu_icon_button,
    menu_icon_item,
    redirect,
    separator,
)
from beaverhabits.frontend.javascript import FIX_ZOOM_POSITIONS, PREVENT_CONTEXT_MENU
from beaverhabits.frontend.menu import add_menu, sort_menu, stats_date_pick_menu
from beaverhabits.plan import plan
from beaverhabits.storage.meta import (
    get_root_path,
    is_page_demo,
    page_path,
    page_title,
)
from beaverhabits.storage.storage import Habit, HabitList
from beaverhabits.utils import get_user_dark_mode, set_user_dark_mode
from beaverhabits.version import IDENTITY

THEME_CSS = """\
/* Green martian terminal theme. Dark is the default. */
/* The light variant follows the Solarized idea: same green hue family,
   warm light base tones, dark green ink. */
/* !important: NiceGUI sets brand colors as inline styles on body. */
html, body {
    --q-primary: #00ff66 !important;
    --q-secondary: #1f8a4c !important;
    --q-accent: #00ff41 !important;
}
html {
    --th-bg: #040804;
    --th-header: #030603;
    --th-panel: #0a100a;
    --th-inset: #0a140a;
    --th-control: #060a06;
    --th-hover: #0d1a0d;
    --th-line: #123f1f;
    --th-text: #00ff41;
    --th-heading: #00ff41;
    --th-accent: #00ff66;
    --th-muted: #1f8a4c;
    --th-on-accent: #040804;
    --th-glow: 0 0 6px rgba(0, 255, 65, 0.35);
    --th-glow-strong: 0 0 6px rgba(0, 255, 102, 0.5);
    --th-check-glow: drop-shadow(0 0 3px rgba(0, 255, 102, 0.4));
    --th-check-shadow: 0 0 6px rgba(0, 255, 102, 0.4);
    --th-card-shadow: 0 0 12px rgba(0, 255, 65, 0.06);
    --th-btn-hover-shadow: 0 0 8px rgba(0, 255, 102, 0.25);
    --th-scanline: rgba(0, 255, 65, 0.03);
}
html[data-theme="light"], html[data-theme="light"] body {
    --q-primary: #0f6a35 !important;
    --q-secondary: #3f6b4d !important;
    --q-accent: #157a3d !important;
}
html[data-theme="light"] {
    --th-bg: #f4f7ec;
    --th-header: #e3ebd6;
    --th-panel: #e9efe0;
    --th-inset: #dde7cf;
    --th-control: #f0f4e6;
    --th-hover: #dfe9d2;
    --th-line: #c3d4b8;
    --th-text: #1a3c22;
    --th-heading: #0f6a35;
    --th-accent: #0f6a35;
    --th-muted: #3f6b4d;
    --th-on-accent: #f4f7ec;
    --th-glow: none;
    --th-glow-strong: none;
    --th-check-glow: none;
    --th-check-shadow: none;
    --th-card-shadow: 0 1px 4px rgba(15, 106, 53, 0.10);
    --th-btn-hover-shadow: 0 0 8px rgba(15, 106, 53, 0.18);
    --th-scanline: rgba(15, 106, 53, 0.05);
}

body, h1, h2, h3, h4, h5, h6,
input, textarea, select, button,
.q-btn, .q-field, .q-item, .q-card, .q-menu, .q-dialog {
    font-family: "JetBrains Mono", "Cascadia Code", "Fira Code",
        ui-monospace, "SF Mono", Menlo, Consolas, "Courier New", monospace !important;
}

body, body.body--dark, .q-layout, .q-page-container, .q-page {
    background-color: var(--th-bg) !important;
    color: var(--th-text);
}

/* Scale the whole UI by 1.5x on large screens only.
   Mobile keeps zoom 1 so the layout fits the viewport. */
/* Keep flex and grid children shrinkable so long content never
   forces horizontal page scroll. */
.nicegui-content > *,
.nicegui-row > *,
.nicegui-column > *,
.nicegui-grid > * {
    min-width: 0;
}

/* User note images must fit the viewport. */
.q-page img,
.q-timeline img {
    max-width: 100%;
    height: auto;
}

body {
    zoom: 1.5;
}

/* Heatmap calendars scroll horizontally inside their card when the
   weeks do not fit, instead of pushing the page wide. */
.theme-heatmap {
    --hm-cell: 20px;
    --hm-week: 22px;
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    padding-bottom: 2px;
}
.theme-hm-cell,
.theme-heatmap .q-checkbox {
    width: var(--hm-cell);
    min-width: var(--hm-cell);
    height: var(--hm-cell);
    min-height: var(--hm-cell);
    flex: none;
}
/* The cell carries Quasar's `.inline-block` utility with !important and
   is a flex item, so it blockifies; the inner box below fills the cell
   exactly, which centers the glyph on both axes. Hide the empty text
   label so it can never add width or height to the cell. */
.theme-heatmap .q-checkbox .q-checkbox__label {
    display: none;
}
/* Size the Quasar control and its icon glyph to the cell. Do not rely on
   Quasar's em-based internals: pin every box to the cell in px. */
.theme-heatmap .q-checkbox--dense .q-checkbox__inner {
    width: var(--hm-cell);
    min-width: var(--hm-cell);
    height: var(--hm-cell);
    min-height: var(--hm-cell);
    font-size: var(--hm-cell);
    line-height: var(--hm-cell);
    display: flex;
    align-items: center;
    justify-content: center;
}
.theme-heatmap .q-checkbox--dense .q-checkbox__icon {
    font-size: var(--hm-cell);
    line-height: 1;
}
.theme-hm-head {
    width: var(--hm-cell);
    min-width: var(--hm-cell);
    height: var(--hm-cell);
    line-height: var(--hm-cell);
    font-size: 9px;
    text-align: center;
    flex: none;
}
.theme-hm-week {
    width: var(--hm-week);
    min-width: var(--hm-week);
    line-height: var(--hm-cell);
    font-size: 9px;
    flex: none;
}

@media (max-width: 640px) {
    body {
        zoom: 1;
        font-size: 16px;
        touch-action: manipulation;
    }

    /* Comfortable touch targets on phones. */
    .q-header button,
    .q-btn[aria-label],
    .q-btn:has(> .q-btn__content > .q-icon) {
        min-width: 44px !important;
        min-height: 44px !important;
    }
    .q-btn:not(.q-btn--round):not(.q-btn--fab):not(.q-btn--dense) {
        min-height: 44px;
    }
    .q-field--dense .q-field__control {
        min-height: 44px;
    }

    /* Habit grid rows: whole-cell tap areas, 44px tall. */
    .nicegui-grid:not(.theme-header-date) > * {
        min-height: 44px;
    }
    .nicegui-grid:not(.theme-header-date) > a {
        line-height: 44px;
    }
    /* Habit cards carry no visible action button, unlike unhabit and todo
       rows. The hidden long-press menu leaves their grid shorter on phones.
       Pin the habit grid to the unhabit natural row height. Todo cards share
       .theme-card-shadow but use a row, not a .nicegui-grid, so they are
       unaffected. */
    .theme-card-shadow .nicegui-grid {
        min-height: 52px;
    }
    .nicegui-grid .q-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }

    /* The date grid gets tight on small screens: keep it scrollable
       instead of squashing the name column. */
    .nicegui-grid {
        min-width: 0;
    }

    /* Sticky date header keeps its own background while scrolling. */
    .theme-sticky {
        background-color: var(--th-header);
        border-bottom: 1px solid var(--th-line);
    }

    .q-page .nicegui-card {
        max-width: 100%;
    }

    .q-input input,
    .q-field__native {
        font-size: 16px; /* prevents iOS zoom on focus */
    }

    /* Keep dialogs and popup menus inside the viewport. */
    .q-dialog .q-card,
    .q-menu {
        max-width: calc(100vw - 24px);
    }

    /* Bigger heatmap cells are easier to tap; the container scrolls. */
    .theme-heatmap {
        --hm-cell: 26px;
        --hm-week: 26px;
    }

    /* Todo rows: taller name tap area and 44px minimum height. */
    .theme-todo-row {
        min-height: 44px;
    }
    .theme-todo-name {
        padding: 12px 0;
    }

    /* Room for the iOS home indicator in standalone mode. */
    .q-page {
        padding-bottom: env(safe-area-inset-bottom);
    }
}

@media (max-width: 360px) {
    /* Five date columns still fit on 320px screens with smaller checks.
       The heatmap is excluded: its cells keep their own --hm-cell size
       on every viewport width. */
    .nicegui-grid:not(.theme-header-date):not(.theme-heatmap) .q-checkbox__inner {
        font-size: 32px;
    }
    .nicegui-grid:not(.theme-header-date):not(.theme-heatmap) .q-checkbox {
        padding-left: 2px;
        padding-right: 2px;
    }
    /* Belt and braces: re-pin the heatmap glyph to the cell so no grid
       rule can ever enlarge it on the narrowest screens. */
    .theme-heatmap .q-checkbox__inner {
        font-size: var(--hm-cell);
    }
    .theme-heatmap .q-checkbox {
        padding-left: 0;
        padding-right: 0;
    }

    /* Calendar navigation arrows stay inside the card on 320px screens. */
    .q-date__navigation,
    .q-date__navigation > * {
        min-width: 0;
    }
    .q-date__navigation > div:first-child,
    .q-date__navigation > div:last-child {
        width: auto;
        min-width: 36px;
    }
    .q-date__navigation .q-date__arrow {
        flex: none;
    }
    .q-date__navigation {
        flex-wrap: wrap;
    }
    .q-date__navigation .q-btn[aria-label] {
        min-width: 36px !important;
        min-height: 36px !important;
    }
}

h1, h2, h3, h4, h5, h6, a {
    color: var(--th-heading) !important;
    text-shadow: var(--th-glow);
}

.text-grey, .text-muted, .q-item__label--caption {
    color: var(--th-muted) !important;
}

.q-card {
    background-color: var(--th-panel) !important;
    border: 1px solid var(--th-line) !important;
    box-shadow: var(--th-card-shadow) !important;
    color: var(--th-text);
}

.q-checkbox .q-checkbox__label,
.q-checkbox {
    color: var(--th-muted);
}
.q-checkbox.q-checkbox--active,
.q-checkbox.q-checkbox--active .q-checkbox__label,
.q-checkbox.q-checkbox--active .q-checkbox__inner {
    color: var(--th-accent) !important;
    text-shadow: var(--th-glow-strong);
    filter: var(--th-check-glow);
}

.q-btn {
    background-color: var(--th-inset) !important;
    border: 1px solid var(--th-line) !important;
    color: var(--th-text) !important;
    box-shadow: none !important;
}
.q-btn:hover {
    border-color: var(--th-accent) !important;
    box-shadow: var(--th-btn-hover-shadow) !important;
}
.q-btn.bg-primary, .q-btn--primary, .q-btn.text-primary {
    background-color: var(--th-inset) !important;
    border-color: var(--th-accent) !important;
    color: var(--th-accent) !important;
}

.q-header {
    background-color: var(--th-header) !important;
    border-bottom: 1px solid var(--th-line) !important;
}

.q-dialog .q-card, .q-menu {
    background-color: var(--th-panel) !important;
    border: 1px solid var(--th-line) !important;
    color: var(--th-text);
}
.q-item {
    background-color: transparent;
    color: var(--th-text);
}
.q-item:hover, .q-item.q-item--active {
    background-color: var(--th-hover) !important;
}

.q-input .q-field__control,
.q-select .q-field__control,
.q-textarea .q-field__control,
.q-field .q-field__control {
    background-color: var(--th-control) !important;
    border: 1px solid var(--th-line) !important;
    color: var(--th-text) !important;
}
.q-field__native, .q-field__input, .q-field__label {
    color: var(--th-text) !important;
    caret-color: var(--th-text);
}
.q-field__label {
    color: var(--th-muted) !important;
}

.q-toggle.q-toggle--active .q-toggle__inner,
.q-toggle.q-toggle--active .q-toggle__track,
.q-toggle.q-toggle--active .q-toggle__thumb {
    color: var(--th-accent) !important;
}
.q-toggle.q-toggle--active .q-toggle__track {
    background-color: var(--th-line) !important;
}

::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: var(--th-bg);
}
::-webkit-scrollbar-thumb {
    background: var(--th-line);
}
::-webkit-scrollbar-thumb:hover {
    background: var(--th-muted);
}
html {
    scrollbar-color: var(--th-line) var(--th-bg);
}

::selection {
    background: var(--th-accent);
    color: var(--th-on-accent);
}

/* Scanlines overlay; pointer-events none so it never blocks clicks. */
body::after {
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 99999;
    background: repeating-linear-gradient(
        to bottom,
        var(--th-scanline) 0px,
        var(--th-scanline) 1px,
        transparent 1px,
        transparent 3px
    );
}

/* Fixes for components still using the app primary rgb(88, 152, 212). */
.q-checkbox__inner:before {
    border-color: var(--th-muted) !important;
    color: var(--th-muted) !important;
}
.q-checkbox__inner:hover:before {
    border-color: var(--th-accent) !important;
}
.q-checkbox[aria-checked="true"] .q-checkbox__inner:before,
.q-checkbox--active .q-checkbox__inner:before {
    border-color: var(--th-accent) !important;
    color: var(--th-accent) !important;
    box-shadow: var(--th-check-shadow);
}
.q-checkbox__inner svg,
.q-checkbox__inner svg path {
    fill: var(--th-accent) !important;
    stroke: var(--th-accent) !important;
}

.text-primary {
    color: var(--th-accent) !important;
}
.bg-primary {
    background-color: var(--th-accent) !important;
}
.bg-primary, .bg-primary .q-btn__content, .bg-primary .q-icon {
    color: var(--th-on-accent) !important;
}

/* Same neon look as the habit name links for todo names and headings. */
.theme-glow-text {
    text-shadow: var(--th-glow);
}

.q-btn.text-primary,
.q-btn .q-icon,
.q-btn__content {
    color: var(--th-text) !important;
}

/* Todo triple-dot: faint like the card frame, not a bright button */
.q-btn.todo-menu-faint {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.q-btn.todo-menu-faint .q-icon {
    color: var(--th-line) !important;
}
.q-btn.todo-menu-faint:hover {
    border: none !important;
    box-shadow: none !important;
}
.q-btn.todo-menu-faint:hover .q-icon {
    color: var(--th-muted) !important;
}

.q-toggle .q-toggle__inner {
    color: var(--th-muted) !important;
}
.q-toggle[aria-checked="true"] .q-toggle__inner,
.q-toggle.q-toggle--active .q-toggle__inner {
    color: var(--th-accent) !important;
}

/* Todo drag handle: faint like the menu button, grab cursor */
.q-icon.todo-drag-handle {
    color: var(--th-line) !important;
    cursor: grab;
}
.q-icon.todo-drag-handle:active {
    cursor: grabbing;
}
.q-icon.todo-drag-handle:hover {
    color: var(--th-muted) !important;
}
.q-toggle[aria-checked="true"] .q-toggle__track,
.q-toggle.q-toggle--active .q-toggle__track {
    background-color: var(--th-line) !important;
}

a, .q-item.q-item--active, .q-item.q-router-link--active {
    color: var(--th-accent) !important;
}

.q-pagination .q-btn--standard,
.q-pagination .q-btn[aria-current="true"],
.q-pagination .q-btn.text-primary {
    color: var(--th-accent) !important;
    border-color: var(--th-accent) !important;
}

.q-linear-progress, .q-circular-progress {
    color: var(--th-accent) !important;
}
"""

THEME_INIT_JS = """\
(function () {
    var theme = "";
    try { theme = localStorage.getItem("alienhabits-theme") || ""; } catch (e) {}
    if (!theme && window.matchMedia &&
        matchMedia("(prefers-color-scheme: light)").matches) theme = "light";
    document.documentElement.setAttribute("data-theme", theme || "dark");
})();
"""

THEME_TOGGLE_JS = """\
(function () {
    var current = document.documentElement.getAttribute("data-theme");
    var next = current === "light" ? "dark" : "light";
    try { localStorage.setItem("alienhabits-theme", next); } catch (e) {}
    document.documentElement.setAttribute("data-theme", next);
})();
"""

# On phones the heatmap cells are enlarged and the container scrolls.
# Show the end (current week) whenever a heatmap is (re)rendered.
HEATMAP_SCROLL_JS = """\
(function () {
    function scrollHeatmapsToEnd() {
        if (window.innerWidth > 640) return;
        document.querySelectorAll('.theme-heatmap').forEach(function (el) {
            if (el.dataset.scrolled) return;
            // Wait until all rows have streamed in before scrolling.
            if (el.scrollWidth <= el.clientWidth) return;
            el.dataset.scrolled = '1';
            el.scrollLeft = el.scrollWidth;
        });
    }
    new MutationObserver(scrollHeatmapsToEnd).observe(document.body, {
        childList: true,
        subtree: true,
    });
    var tries = 0;
    var timer = setInterval(function () {
        scrollHeatmapsToEnd();
        if (++tries > 40) clearInterval(timer);
    }, 250);
    window.addEventListener('load', scrollHeatmapsToEnd);
})();
"""


def pwa_headers():
    # Extend background to iOS notch
    ui.add_head_html("""
        <link rel="apple-touch-icon" href="/statics/images/apple-touch-icon-v4.png">
        
        <meta name="apple-mobile-web-app-title" content="Beaver">
        <meta name="application-name" content="Beaver">
        
        <meta name="theme-color" content="#F9F9F9" media="(prefers-color-scheme: light)" />
        <meta name="theme-color" content="#121212" media="(prefers-color-scheme: dark)" />
        """)

    # Experimental PWA
    if settings.ENABLE_IOS_STANDALONE:
        # Hiding Safari User Interface Components
        ui.add_head_html('<meta name="mobile-web-app-capable" content="yes">')
        ui.add_head_html('<link rel="manifest" href="/statics/pwa/manifest.json">')


def custom_headers():
    # Get current page info
    page_url = "https://beaverhabits.com" + page_path()

    # SEO meta tags
    ui.add_head_html(f"""
        <!-- Basic Meta Tags -->
        <meta name="description" content="A minimal habit tracking app without Goals. Track your daily habits with a simple, privacy-focused interface.">
        <meta name="keywords" content="habit tracker, habit tracking, self-hosted, productivity, daily habits, habit building, open source">
        <meta name="author" content="daya0576">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="{page_url}">
        
        <!-- Open Graph / Facebook -->
        <meta property="og:type" content="website">
        <meta property="og:url" content="{page_url}">
        <meta property="og:title" content="Beaver Habit Tracker">
        <meta property="og:description" content="A minimal habit tracking app without Goals. Track your daily habits with privacy and simplicity.">
        <meta property="og:image" content="https://beaverhabits.com/statics/images/apple-touch-icon-v4.png">
        <meta property="og:site_name" content="Beaver Habit Tracker">
        
        <!-- Twitter -->
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:url" content="{page_url}">
        <meta name="twitter:title" content="Beaver Habit Tracker">
        <meta name="twitter:description" content="A minimal habit tracking app without Goals. Track your daily habits with privacy and simplicity.">
        <meta name="twitter:image" content="https://beaverhabits.com/statics/images/apple-touch-icon-v4.png">
        
        <!-- Structured Data (JSON-LD) -->
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "Beaver Habit Tracker",
            "url": "https://beaverhabits.com",
            "description": "A minimal habit tracking app without Goals",
            "applicationCategory": "ProductivityApplication",
            "operatingSystem": "Web, iOS, Android",
            "offers": {{
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD"
            }},
            "author": {{
                "@type": "Person",
                "name": "daya0576",
                "url": "https://github.com/daya0576"
            }}
        }}
        </script>
        """)

    # Long-press event
    ui.add_head_html('<script src="/statics/libs/long-press-event.min.js"></script>')

    # Analytics
    if settings.UMAMI_ANALYTICS_ID:
        ui.add_head_html(
            f'<script defer src="{settings.UMAMI_SCRIPT_URL}" data-website-id="{settings.UMAMI_ANALYTICS_ID}"></script>'
        )

    # Prevent white flash on page load
    ui.add_css(css.WHITE_FLASH_PREVENT)
    ui.add_css(css.TEXTAREA_CSS)

    # prevent context menu
    ui.add_body_html(f"<script>{PREVENT_CONTEXT_MENU}</script>")

    # keep Quasar overlays anchored to their targets despite the CSS zoom
    ui.add_body_html(f"<script>{FIX_ZOOM_POSITIONS}</script>")

    # keep the current week visible when a heatmap scrolls on phones
    ui.add_body_html(f"<script>{HEATMAP_SCROLL_JS}</script>")

    # custom css styles
    views.apply_theme_style()

    # Green martian terminal theme: dark default, light variant
    ui.add_head_html(f"<style>{THEME_CSS}</style>")
    ui.add_head_html(f"<script>{THEME_INIT_JS}</script>")

    # Unhabits: red "things to stop doing" section + subtle Add buttons.
    ui.add_head_html("""
        <style>
        .theme-unhabit-glow-text {
            color: #ff5555 !important;
            text-shadow: 0 0 6px rgba(255, 85, 85, 0.35);
        }
        .theme-unhabit-card-shadow {
            background-color: transparent !important;
            border: 1px solid #3f1212 !important;
            box-shadow: 0 0 12px rgba(255, 85, 85, 0.06) !important;
        }
        html[data-theme="light"] .theme-unhabit-card-shadow {
            background-color: var(--th-panel, #e9efe0) !important;
            border-color: var(--th-line, #c3d4b8) !important;
            box-shadow: var(--th-card-shadow) !important;
        }
        .theme-unhabit-checkbox .q-checkbox__inner:before {
            border-color: #a03030 !important;
            color: #a03030 !important;
        }
        .theme-unhabit-checkbox .q-checkbox__inner:hover:before {
            border-color: #ff5555 !important;
        }
        .theme-unhabit-checkbox[aria-checked="true"] .q-checkbox__inner:before,
        .theme-unhabit-checkbox.q-checkbox--active .q-checkbox__inner:before {
            border-color: #ff5555 !important;
            color: #ff5555 !important;
            box-shadow: 0 0 6px rgba(255, 85, 85, 0.4);
        }
        .theme-unhabit-checkbox .q-checkbox__inner svg,
        .theme-unhabit-checkbox .q-checkbox__inner svg path {
            fill: #ff5555 !important;
            stroke: #ff5555 !important;
        }
        .theme-unhabit-menu-btn,
        .theme-unhabit-menu-btn .q-icon {
            color: #ff5555 !important;
        }
        .theme-unhabit-menu {
            background-color: var(--th-inset, #0a140a) !important;
            border: 1px solid #3f1212 !important;
        }
        .theme-unhabit-menu .q-item {
            color: #ff5555 !important;
        }
        .theme-unhabit-menu .q-item:hover,
        .theme-unhabit-menu .q-item.q-item--active {
            background-color: var(--th-hover, #0d1a0d) !important;
        }
        .theme-unhabit-menu .q-separator {
            background-color: #3f1212 !important;
        }
        .theme-unhabit-input .q-field__control {
            background-color: transparent !important;
            border: 1px solid #3f1212 !important;
            color: #ff5555 !important;
        }
        .theme-unhabit-input .q-field__control:before,
        .theme-unhabit-input .q-field__control:after {
            border-color: #3f1212 !important;
        }
        html[data-theme="light"] .theme-unhabit-input .q-field__control,
        html[data-theme="light"] .theme-unhabit-input .q-field__control:before,
        html[data-theme="light"] .theme-unhabit-input .q-field__control:after {
            border-color: var(--th-line, #c3d4b8) !important;
        }
        .theme-unhabit-input .q-field__control:after {
            border-color: #ff5555 !important;
        }
        .theme-unhabit-input .q-field__native,
        .theme-unhabit-input .q-field__input,
        .theme-unhabit-input.q-field .q-field__native,
        .theme-unhabit-input.q-field .q-field__input {
            color: #ff5555 !important;
            caret-color: #ff5555 !important;
        }
        .theme-unhabit-input .q-field__native::placeholder,
        .theme-unhabit-input .q-field__input::placeholder {
            color: #a03030 !important;
        }

        /* Subtle section Add buttons: text only, no box. */
        .q-btn.theme-add-btn {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }
        .q-btn.theme-add-btn {
            color: var(--th-text, #00ff41) !important;
        }
        .q-btn.theme-add-btn:hover {
            color: var(--th-accent, #00ff66) !important;
        }

        /* Unhabit primary action: solid red, matching the section palette. */
        .q-btn.theme-unhabit-btn {
            background-color: #a03030 !important;
            border: 1px solid #ff5555 !important;
            color: #ffffff !important;
            box-shadow: none !important;
        }
        .q-btn.theme-unhabit-btn:hover {
            border-color: #ff5555 !important;
            box-shadow: 0 0 8px rgba(255, 85, 85, 0.35) !important;
        }

        /* Subtle 3-dot action buttons: no box, just the icon. */
        .q-btn[aria-label$="actions"],
        .q-btn[aria-label$="actions"]:hover {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }
        </style>
        """)


def show_help_dialog():
    with ui.context.client.content:
        with ui.dialog() as dialog:
            with compat_card().classes("w-[360px] max-w-full"):
                title = IDENTITY.replace("/", " ")
                title = title.split("@")[0] if "@" in title else title
                ui.label(title).classes("text-lg font-bold")
                ui.separator()

                items = {
                    "Documentation": "https://github.com/daya0576/beaverhabits/wiki",
                    "Supporter": "https://www.beaverhabits.com/pricing",
                    "YouTube": "https://www.youtube.com/@beaverhabits",
                    "Bugs & Feature Requests": "https://github.com/daya0576/beaverhabits/issues",
                }

                with ui.grid(columns=2).classes("gap-2"):
                    for name, link in items.items():
                        ui.link(name, link, new_tab=True)

        dialog.props('backdrop-filter="blur(4px)"')
        dialog.open()


@ui.refreshable
def menu_component():
    """Dropdown menu for the top-right corner of the page."""
    with ui.menu().props('role="menu" transition-duration="50"'):
        add_menu()
        separator()

        if "unhabits" not in page_path():
            menu_icon_item("Unhabits", lambda: redirect("unhabits"))
        if "todos" not in page_path():
            menu_icon_item("Todos", lambda: redirect("todos"))
        if "todos" in page_path() or "unhabits" in page_path():
            menu_icon_item("Habits", lambda: redirect(""))
        separator()

        with menu_icon_item("Tools", auto_close=False).classes("pr-1"):
            with ui.item_section().props("side").classes("pl-[1px]"):
                ui.icon(icons.CHEVRON_RIGHT)
            with ui.menu().props('anchor="top end" self="top start" auto-close'):
                # Stats for all habtis
                menu_icon_item("Reorder", lambda: redirect("order"))
                separator()

                # Export & import
                menu_icon_item("Export", lambda: redirect("export"))
                separator()
                imp = menu_icon_item("Import", lambda: redirect("import"))
                if is_page_demo():
                    imp.classes("disabled")
                separator()

                # Stats for all habtis
                menu_icon_item("Stats", lambda: redirect("stats"))
                separator()

        separator()

        # Dark/light alien theme toggle
        menu_icon_item("Toggle theme", lambda: ui.run_javascript(THEME_TOGGLE_JS))
        separator()

        # About page
        menu_icon_item("Help", show_help_dialog)
        separator()

        # Login & Logout
        menu_icon_item("Logout", lambda: user_logout() and ui.navigate.to("/login"))


@ui.refreshable
def dark_mode_button() -> None:
    """Always-visible dark/light toggle shown in the page header."""

    def toggle() -> None:
        ui.run_javascript(THEME_TOGGLE_JS)
        try:
            current = get_user_dark_mode()
        except Exception:
            current = None
        if current is None:
            current = ui.dark_mode().value
        new_value = not current
        try:
            set_user_dark_mode(new_value)
        except ValueError:
            pass
        if new_value:
            ui.dark_mode().enable()
        else:
            ui.dark_mode().disable()
        dark_mode_button.refresh()

    try:
        dark = get_user_dark_mode()
    except Exception:
        dark = None
    if dark is None:
        dark = ui.dark_mode().value
    menu_icon_button(
        "sym_o_light_mode" if dark else "sym_o_dark_mode",
        click=toggle,
        tooltip="Toggle dark / light mode",
    )


@contextmanager
def layout(
    title: str | None = None,
    habit: Habit | None = None,
    habit_list: HabitList | None = None,
    page_ui: ui.refreshable | None = None,
):
    # Standard headers
    custom_headers()
    pwa_headers()

    # Full-width content column with page padding from nicegui-content
    with ui.column().classes("w-full"):

        # Layout wrapper
        with ui.row().classes("w-full gap-x-1"):
            title, target = title or page_title(), get_root_path()
            menu_header(title, target=target)
            ui.space()

            if habit:
                edit_dialog = habit_edit_dialog(habit)
                edit_btn = menu_icon_button("sym_r_pen_size_3", tooltip="Edit habit")
                edit_btn.on_click(edit_dialog.open)
            elif habit_list and "add" in page_path():
                with menu_icon_button("sym_o_swap_vert", tooltip="Sort"):
                    sort_menu(habit_list)
            elif "stats" in page_path() and page_ui:
                with menu_icon_button("sym_o_expand_content", tooltip="Date"):
                    stats_date_pick_menu()

            dark_mode_button()

            with menu_icon_button("sym_o_menu"):
                menu_component()

        yield
