import re

from beaverhabits.frontend.layout import THEME_CSS, THEME_INIT_JS, THEME_TOGGLE_JS


def scope_vars(pattern):
    match = re.search(pattern + r" \{(.*?)\}", THEME_CSS, re.S | re.M)
    assert match, f"scope not found: {pattern}"
    return set(re.findall(r"(--th[a-z-]*):", match.group(1)))


def test_theme_variables_defined_in_both_scopes():
    used = set(re.findall(r"var\((--th[a-z-]*)\)", THEME_CSS))
    assert used, "theme uses no variables"
    dark = scope_vars(r"^html")
    light = scope_vars(re.escape('html[data-theme="light"]'))
    assert used <= dark, f"missing in dark scope: {used - dark}"
    assert used <= light, f"missing in light scope: {used - light}"


def test_light_theme_palette():
    assert 'html[data-theme="light"]' in THEME_CSS
    # Solarized-style warm paper base and dark green ink
    assert "#f4f7ec" in THEME_CSS
    assert "#1a3c22" in THEME_CSS
    # Dark scope keeps the phosphor terminal colors
    assert "#00ff41" in THEME_CSS
    assert "#040804" in THEME_CSS


def test_theme_scripts():
    assert "alienhabits-theme" in THEME_INIT_JS
    assert "prefers-color-scheme: light" in THEME_INIT_JS
    assert "data-theme" in THEME_INIT_JS
    assert "localStorage" in THEME_TOGGLE_JS
    assert "data-theme" in THEME_TOGGLE_JS


def test_narrow_screen_grid_rule_excludes_heatmap():
    """The <=360px rule that enlarges grid checkboxes must never hit heatmap cells."""
    match = re.search(r"@media \(max-width: 360px\) \{(.*?)\}\n\n", THEME_CSS, re.S)
    assert match, "max-width: 360px block not found"
    scope = match.group(1)
    assert (
        ".nicegui-grid:not(.theme-header-date):not(.theme-heatmap) .q-checkbox__inner"
        in scope
    )
    assert (
        ".nicegui-grid:not(.theme-header-date):not(.theme-heatmap) .q-checkbox" in scope
    )
    # Heatmap glyph stays pinned to the cell size inside the same block.
    assert ".theme-heatmap .q-checkbox__inner" in scope
    assert "font-size: var(--hm-cell);" in scope
    # The grid rule can no longer match a heatmap checkbox.
    assert ".nicegui-grid:not(.theme-header-date) .q-checkbox__inner" not in scope


def test_heatmap_cell_size_rules():
    """Heatmap cells and glyphs are pinned to --hm-cell in px."""
    assert ".theme-heatmap .q-checkbox--dense .q-checkbox__inner" in THEME_CSS
    assert "font-size: var(--hm-cell);" in THEME_CSS
    assert "width: var(--hm-cell);" in THEME_CSS
