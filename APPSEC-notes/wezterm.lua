local wezterm = require 'wezterm'

local config = wezterm.config_builder()

-----------------------------------------------------------
-- PREMIUM BLACK DEVELOPER THEME
-----------------------------------------------------------

-- Colors
config.color_scheme = "Batman"

config.colors = {
    background = "#050505",
    foreground = "#cdd6f4",
    cursor_bg = "#ffffff",
    cursor_fg = "#000000",

    selection_bg = "#44475a",
    selection_fg = "#ffffff",

    ansi = {
        "#000000",
        "#ff5555",
        "#50fa7b",
        "#f1fa8c",
        "#bd93f9",
        "#ff79c6",
        "#8be9fd",
        "#bbbbbb",
    },

    brights = {
        "#555555",
        "#ff6e6e",
        "#69ff94",
        "#ffffa5",
        "#d6acff",
        "#ff92df",
        "#a4ffff",
        "#ffffff",
    },

    tab_bar = {
        background = "#000000",

        active_tab = {
            bg_color = "#222222",
            fg_color = "#ffffff",
        },

        inactive_tab = {
            bg_color = "#050505",
            fg_color = "#777777",
        },

        inactive_tab_hover = {
            bg_color = "#111111",
            fg_color = "#cccccc",
        },
    },
}


-----------------------------------------------------------
-- FONT
-----------------------------------------------------------

config.font = wezterm.font_with_fallback({
    "Ubuntu Mono",
    "Noto Color Emoji",
})

config.font_size = 13.5
config.line_height = 1.15

config.bold_brightens_ansi_colors = true


-----------------------------------------------------------
-- WINDOW STYLE
-----------------------------------------------------------

-- Keep Linux minimize/maximize/close buttons
config.window_decorations = "TITLE | RESIZE"

config.window_background_opacity = 1.0
config.text_background_opacity = 1.0

config.window_padding = {
    left = 12,
    right = 12,
    top = 12,
    bottom = 12,
}


-----------------------------------------------------------
-- TABS
-----------------------------------------------------------

config.enable_tab_bar = true
config.use_fancy_tab_bar = true
config.hide_tab_bar_if_only_one_tab = false

config.tab_bar_at_bottom = true


-----------------------------------------------------------
-- CURSOR
-----------------------------------------------------------

config.default_cursor_style = "BlinkingBar"

config.cursor_blink_rate = 600

config.cursor_thickness = 2


-----------------------------------------------------------
-- PERFORMANCE
-----------------------------------------------------------

config.front_end = "WebGpu"

config.max_fps = 144

config.animation_fps = 60


-----------------------------------------------------------
-- SCROLLING
-----------------------------------------------------------

config.scrollback_lines = 20000


-----------------------------------------------------------
-- KEYBOARD SHORTCUTS
-----------------------------------------------------------

config.keys = {

    -- New tab
    {
        key = "t",
        mods = "CTRL|SHIFT",
        action = wezterm.action.SpawnTab "CurrentPaneDomain",
    },

    -- Close pane
    {
        key = "w",
        mods = "CTRL|SHIFT",
        action = wezterm.action.CloseCurrentPane {
            confirm = true
        },
    },

    -- Split vertical (side-by-side panes)
    {
        key = "\\",
        mods = "CTRL|SHIFT",
        action = wezterm.action.SplitVertical {
            domain = "CurrentPaneDomain"
        },
    },
    {
        key = "UpArrow",
        mods = "CTRL|SHIFT",
        action = wezterm.action.SplitVertical {
            domain = "CurrentPaneDomain"
        },
    },
    {
        key = "DownArrow",
        mods = "CTRL|SHIFT",
        action = wezterm.action.SplitVertical {
            domain = "CurrentPaneDomain"
        },
    },

    -- Split horizontal (top/bottom panes)
    {
        key = "-",
        mods = "CTRL|SHIFT",
        action = wezterm.action.SplitHorizontal {
            domain = "CurrentPaneDomain"
        },
    },
    {
        key = "LeftArrow",
        mods = "CTRL|SHIFT",
        action = wezterm.action.SplitHorizontal {
            domain = "CurrentPaneDomain"
        },
    },
    {
        key = "RightArrow",
        mods = "CTRL|SHIFT",
        action = wezterm.action.SplitHorizontal {
            domain = "CurrentPaneDomain"
        },
    },

    -- Search scrollback
    {
        key = "f",
        mods = "CTRL|SHIFT",
        action = wezterm.action.ActivateCopyMode,
    },

}


-----------------------------------------------------------
-- STARTUP SIZE
-----------------------------------------------------------

config.initial_cols = 120
config.initial_rows = 35


-----------------------------------------------------------
-- MISC
-----------------------------------------------------------

config.audible_bell = "Disabled"

config.window_close_confirmation = "NeverPrompt"

return config
