# ExacqMan

A Python tool for extracting footage from ExacqVision servers via the ExacqVision Web API. It creates timelapses, compresses footage, and overlays timestamps, driven by command-line arguments and a TOML config file.

ExacqMan ships as a single installable package exposing two console commands:

- **`exacqman`** — the CLI (extract / compress / timelapse / crop / init).
- **`exacqman-web`** — a small FastAPI web UI that wraps the same CLI (start / stop / status). See [`src/exacqman/web/README.md`](src/exacqman/web/README.md) for the UI and the **CLI ↔ backend integration contract** (JSON event stream, stage taxonomy, error types, exit codes) used by programmatic callers.

The web UI is bundled but **opt-in at runtime** — installing the package never starts a server.

For API testing, [explore the Postman collection](https://weareipc.postman.co/workspace/Industrial-Pallet-Corp~f0dc5379-c365-405e-8a29-ee8050839c42/collection/38801065-56761369-c40d-4cb1-9ab1-3f0a7efb59c9?action=share&creator=38801065&active-environment=7096363-3d41cab2-1adc-47b2-8041-ef8c9b87eb00).

## Installation

### Homebrew (recommended)

```bash
brew tap industrial-pallet-corp/utilities
brew install exacqman
```

This installs both the `exacqman` and `exacqman-web` commands and a bundled `ffmpeg` (via `imageio-ffmpeg`). Config and credentials live in `$(brew --prefix)/etc/exacqman`; see [Configuration](#configuration). To run the web UI as a managed background service, see [Running the web UI as a service](#running-the-web-ui-as-a-service).

> Packaging the tap formula? See [Packaging (Homebrew tap)](#packaging-homebrew-tap) for ready-to-paste `service`, `caveats`, and seeding blocks.

### From source (development)

Requires **Python 3.11+** (the CLI uses the stdlib `tomllib`). Dependencies are declared in `pyproject.toml` and installed automatically:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # editable install for development
exacqman --help
```

## Quick start

```bash
exacqman init                 # seed config + credentials into $(brew --prefix)/etc/exacqman
exacqman --help               # CLI usage

exacqman extract ch dock-10 5/30 9am 9:05am  # extract footage

exacqman-web --help           # web server usage
exacqman-web start            # run the local web UI in the foreground (http://localhost:8887)
brew services start exacqman  # or run the web UI as a managed background service
```

`exacqman init` copies the bundled templates into the [config directory](#configuration) and prints the exact paths plus next steps. The credentials file is written with `0600` permissions.

## Configuration

Configuration is split into two TOML files:

- a **config** file (`*.config`) — servers, cameras, and `[settings]` defaults; and
- a **credentials** file (`*.credentials`) — the `[auth]` username/password.

### Where they live

ExacqMan looks for config files in a standard, cwd-independent location so the tool works from any directory:

| Precedence | Config source |
| --- | --- |
| 1 | `--config <file>` (and `--credentials <file>`) on the command line |
| 2 | `$EXACQMAN_CONFIG_DIR/*.config` |
| 3 | `$(brew --prefix)/etc/exacqman/*.config` (Homebrew) or `~/.config/exacqman/*.config` (XDG) |
| 4 | `*.config` in the current working directory |

When no `--config` is given, ExacqMan auto-discovers a `*.config` from the locations above (preferring one named `default.config`). The Homebrew `etc/exacqman` location is the documented "where does Homebrew keep config for this package" spot and survives upgrades.

**Credentials** resolve relative to the config file's own directory (or `--credentials <path>` / `[settings].credentials_file`). The credentials file beside the config is treated as **shared service auth** by convention; for personal or ad-hoc auth, point `--credentials` at a private file anywhere.

### Config file format

`[settings]` is the reserved defaults table. Every other top-level table is a **server** (e.g. `[ch]`, `[gpa]`) with a `url`. Cameras are sub-tables of their server, `[<server>.<alias>]`, so the same alias can be reused across servers without ID collisions.

```toml
[settings]
credentials_file = "default.credentials"
timezone = "America/Indiana/Indianapolis"
timelapse_multiplier = 50
default_compression_level = "high"  # none | low | medium | high
font_weight = 3                     # 1 (thinnest) .. 5 (heaviest)
default_crop = true
default_crop_dimensions = [[0, 0], [1920, 1080]]
port = 8887                         # web UI port (exacqman-web start)

[ch]
url = "http://192.168.1.100"

[gpa]
url = "http://192.168.2.100"

[ch.front_door]
id = 1
crop_dimensions = [[624, 14], [666, 766]]
compression_level = "low"           # optional per-camera override

[ch.back_door]
id = 2
```

- Server names must not be `settings` (reserved) and must not contain `.`.
- Each server table needs a non-empty `url`; each camera needs a positive-integer `id`.
- `default_crop` (boolean) sets whether extracts/timelapses crop by default. Override per-run with `-c true` / `-c false`.
- Omit a camera's `crop_dimensions` to fall back to `[settings].default_crop_dimensions`; omit both to pick interactively (use the `crop` command to capture them).
- `crop_dimensions` are `[[x, y], [width, height]]` integer arrays.
- `timelapse_multiplier` must be a positive integer.
- `default_compression_level` is `none`, `low`, `medium`, or `high` (`none` bypasses the compression step entirely, keeping native quality at the cost of larger files). Set `compression_level` inside a `[<server>.<alias>]` camera table to override it for that camera (symmetrical with `default_crop_dimensions` / `crop_dimensions`); a `--quality` flag overrides both.
- `font_weight` is an integer from `1` (thinnest) to `5` (heaviest); the overlay stroke scales with the export size so the perceived weight is consistent at any resolution.
- `port` (optional) sets the web UI's listening port; defaults to `8887` if omitted. A `--port/-p` flag on `exacqman-web start` overrides it for that run.

## Output (exports)

Finished videos are written to **`./exports`** in the current working directory by default. Override per-run with `--output-dir <dir>`, or globally with the `EXACQMAN_EXPORTS_DIR` environment variable (used by the background service — see below). Output files are always `.mp4`.

While a job runs, the intermediate files (the raw download, the timelapsed clip, the compressed clip) are written to a separate temporary location — an `exacqman-tmp` sibling of the exports dir by default, overridable with `EXACQMAN_TMP_DIR` — and only the single finished, tagged file is moved into the exports dir on success. This keeps half-finished files out of the exports listing (and the web file browser) while extraction is in progress.

## CLI usage

Run `exacqman --help` (or `exacqman <command> --help`) for full options. Five commands:

- **extract** — retrieve footage, timelapse, timestamp, and compress.
- **compress** — compress an existing video to a target quality.
- **timelapse** — timelapse an existing video, with optional cropping/timestamping.
- **crop** — grab a recent frame from one camera and open the interactive crop selector, printing crop dimensions for your config (no extraction).
- **init** — scaffold config + credentials into the standard config directory.

### extract

```bash
exacqman extract server camera_alias [date] [start] [end] [config_file] \
  [--config CONFIG] [--credentials CREDENTIALS] \
  [-o OUTPUT_NAME] [--output-dir DIR] [--quality {low,medium,high}] \
  [--multiplier N] [-c {true,false}] [--caption TEXT] [--no-text]
```

- `server` (required, first positional): server name, must match a top-level `[<server>]` table.
- `camera_alias` (required), `date` (`M/D` or `M/D/YYYY`), `start`/`end` (e.g. `6pm`, `18:30`).
- `config_file` / `--config`: config to use; omit to auto-discover (see [Configuration](#configuration)).
- `--start-iso-datetime` / `--end-iso-datetime`: ISO 8601 datetimes (e.g. `2026-05-27T09:30:00-04:00`). When given together they replace the positional `date`/`start`/`end` form with full, unambiguous precision — intended for programmatic callers (the web UI uses these).
- `-o, --output_name`: output filename. When omitted, a canonical `{YYYY-MM-DD}_{HHMM}_{server}_{camera}_{multiplier}x.mp4` name is built.
- `--output-dir`: deliver a single clean `{name}.mp4` into this directory (intermediates removed). Defaults to the current directory.
- `--quality`, `--multiplier`, `-c/--crop {true,false}`, `--caption`, `--no-text` (skip timestamp and caption overlays).

### compress

```bash
exacqman compress video_filename {low,medium,high} [-o OUTPUT_NAME]
```

### timelapse

```bash
exacqman timelapse video_filename multiplier [-o OUTPUT_NAME] [-c {true,false}] [--caption TEXT] [--no-text]
```

### crop

```bash
exacqman crop server camera_alias [config_file] [--config CONFIG] \
  [--credentials CREDENTIALS] [--lookback-minutes N]
```

- `server` (required, first positional): server name, must match a top-level `[<server>]` table.
- `camera_alias` (required, second positional): camera alias, must match a `[<server>.<alias>]` entry.

Grabs a short clip from ~now, opens the interactive ROI selector on its first frame, and prints `crop_dimensions` / `default_crop_dimensions` lines ready to paste into your config (it can also offer to write them back automatically). Opens a GUI window, so it requires a display.

### init

```bash
exacqman init [--force]
```

Copies the bundled `default.config` and `default.credentials` templates into the config directory (`--force` overwrites existing files).

### Examples

```bash
exacqman init
exacqman extract ch front_door 3/11 6pm 8pm --multiplier 10 -c true
exacqman compress input.mp4 medium -o compressed.mp4
exacqman timelapse input.mp4 5 -c true
exacqman crop ch front_door
```

### Listing cameras

`list-cameras` logs into the configured server(s) and prints the cameras they
report, cross-referenced against the aliases in your config:

```bash
exacqman list-cameras                # every server in the discovered config
exacqman list-cameras --server ch    # just one server
exacqman list-cameras --json         # machine-readable
```

## Web UI

```bash
exacqman-web start            # foreground on http://localhost:8887 (Ctrl-C to stop)
exacqman-web start --reload   # development auto-reload
exacqman-web status
exacqman-web stop
```

`start` runs a single foreground uvicorn process. The port is resolved as `--port/-p` (if given) → `[settings].port` in `default.config` → the built-in **8887**; bind interface with `--host`. `stop`/`status` locate the server via a PID file (in the log directory) or by listener discovery on the port. See [`src/exacqman/web/README.md`](src/exacqman/web/README.md) for endpoints and the integration contract.

### Running the web UI as a service

There is intentionally **no `--background` flag**. Unattended operation (auto-restart, start-at-login) is delegated to the OS service manager. On Homebrew:

```bash
brew services start exacqman      # supervised via launchd (macOS) / systemd (Linux)
brew services stop exacqman
```

The service runs the same foreground `exacqman-web start`, reads config from `etc/exacqman`, writes logs to `var/log`, and exports to a stable directory (set via `EXACQMAN_EXPORTS_DIR`). It is **never started automatically** by `brew install`.

## Runtime locations summary

| What | Homebrew install | From source / XDG | Env override |
| --- | --- | --- | --- |
| Config + credentials | `$(brew --prefix)/etc/exacqman` | `~/.config/exacqman` | `EXACQMAN_CONFIG_DIR` |
| Exports | `./exports` (cwd) | `./exports` (cwd) | `EXACQMAN_EXPORTS_DIR` |
| Tmp dir (in-progress intermediates) | `exacqman-tmp` sibling of exports | `exacqman-tmp` sibling of exports | `EXACQMAN_TMP_DIR` |
| Logs + PID file | `$(brew --prefix)/var/log` | `~/.local/state/exacqman` | `EXACQMAN_LOG_DIR` |

The installed package itself is read-only — nothing is ever written inside it. All locations resolve through `exacqman.paths`.

## Packaging (Homebrew tap)

ExacqMan is **brew-only** (no PyPI publish target; `pip` is used internally by the formula's virtualenv to build the source tarball). The package is a standard `src/`-layout, PEP 621 `pyproject.toml` project built with `hatchling`, so `brew create --python` + `brew update-python-resources` work as-is. Hints for the tap's `Formula/exacqman.rb`:

**Build:** a `Language::Python::Virtualenv` formula. Console scripts `exacqman` and `exacqman-web` are declared in `[project.scripts]`. `depends_on "ffmpeg"` is optional — the wheel bundles ffmpeg via `imageio-ffmpeg`.

**Seed the standard dirs** (Homebrew preserves `etc` across upgrades; never ship a real credentials file in the bottle — `exacqman init` writes one `0600` on first run):

```ruby
# Template ships inside the package data dir of the unpacked source tarball.
pkgetc.install "src/exacqman/data/default.config" => "default.config.example" unless (pkgetc/"default.config").exist?
(var/"exacqman/exports").mkpath
(var/"log").mkpath
```

**Opt-in background service** (not started by `brew install`; only by `brew services start exacqman`):

```ruby
service do
  run [opt_bin/"exacqman-web", "start", "--host", "127.0.0.1", "--port", "8887"]
  keep_alive true
  working_dir var/"exacqman"                       # stable cwd
  log_path var/"log/exacqman-web.log"
  error_log_path var/"log/exacqman-web.log"
  environment_variables EXACQMAN_EXPORTS_DIR: var/"exacqman/exports"
end
```

The in-progress tmp dir defaults to an `exacqman-tmp` sibling of the exports dir (`var/"exacqman/exacqman-tmp"` here — same filesystem, so delivering the finished file is a fast rename), so no extra `environment_variables` entry is required. Set `EXACQMAN_TMP_DIR` only if you want scratch space somewhere else.

`exacqman-web start` is a clean foreground process (no self-daemonizing), exactly what `brew services` expects. The service reads config from `#{etc}/exacqman` automatically (no `--config` needed) because `exacqman.paths` detects the Homebrew prefix from the install location.

**Caveats** (make the opt-ins discoverable):

```ruby
def caveats
  <<~EOS
    Config and credentials live in #{etc}/exacqman (run `exacqman init` to seed them).
    To run the web UI as a background service:  brew services start exacqman
  EOS
end
```

## Notes

- Timestamps are overlaid using server-provided clip data; cropping is configurable or interactive.
- Compression uses the `libx264` codec with bitrate/resolution tuned by quality level.
- Ensure network access to the ExacqVision server and valid credentials.
