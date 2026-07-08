"""ExacqMan: extract, timelapse, and compress footage from ExacqVision servers."""

__version__ = "3.4.4"

# Default TCP port for the web UI (`exacqman-web start`). This is the fallback
# used when neither a `--port` flag nor a `[settings].port` config value is set,
# and the default offered by `exacqman init`. Kept here as the single source of
# truth so the CLI, the web server, and the bundled default.config agree.
DEFAULT_WEB_PORT = 8887
