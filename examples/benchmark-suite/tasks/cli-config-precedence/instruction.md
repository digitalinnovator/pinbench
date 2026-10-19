Bug report: users say that `APP_TIMEOUT=0` in the environment is ignored. The app keeps using
the timeout from the config file or the built-in default.

Fix the settings code in `/app` so that every rule below holds. The code is `cli.py`,
`config.py` and `defaults.py`; `test_config.py` reproduces the report (`python -m pytest -q`).

Rules:

- The settings are `timeout` (int), `retries` (int) and `prefix` (str).
- Each setting has four sources. From highest to lowest priority: its command-line flag
  (`--timeout`, `--retries`, `--prefix`), its environment variable (`APP_TIMEOUT`,
  `APP_RETRIES`, `APP_PREFIX`), the config file named by the `--config` flag (a JSON object
  keyed by setting name), and `DEFAULTS` in `defaults.py`.
- Each of the four flags comes with a value, as two arguments (`--prefix x`) or as one
  (`--prefix=x`). With two, the value is the whole next argument, whatever it is: it may be
  empty, it may start with `-`, and it is never read as a flag itself. With one, the value is
  everything after the first `=`, and it may be empty.
- A flag sets its setting whenever it is given. If any flag is repeated, the last one counts.
- An environment variable sets its setting when it exists and its value is not the empty string.
- The config file sets a setting when its key is present and the value is not `null`. Any other
  key in the file is ignored.
- Each setting, independently of the others, takes its value from the highest-priority source
  that sets it. A value that is set always counts, whatever the value is.
- Flag and environment values of `timeout` and `retries` are converted to `int`. All input is
  valid, so add no validation.
- `config.load_settings(environ, path=None)` applies the environment, the config file and the
  defaults. `cli.resolve(argv, environ)` applies all four sources. Keep both signatures:
  `environ` is a dict of strings, `path` is the config file path or `None` for no file, `argv`
  is a list of strings. Both return a new dict with exactly the three settings as keys.
- Leave `defaults.py` as it is. No call may modify `DEFAULTS`, `argv` or `environ`.
