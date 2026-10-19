#!/bin/bash
# Plausible careless solution: it implements each rule the obvious way and stops once the visible
# test passes. Three stated rules are broken:
#   - a repeated option is stored with a plain assignment, so its key keeps the place of the first
#     occurrence instead of the last;
#   - a short option's value has its leading "=" dropped before the "is anything left" check, so a
#     value that is empty after the "=" is replaced by the next argument;
#   - the long-name lookup answers "no match" for a prefix of several long names, so such a prefix
#     that starts with "no-" is still read as "--no-name" instead of being rejected.
cat > /app/cliargs.py <<'EOF'
import re

_NEGATIVE = re.compile(r"-[0-9]+(\.[0-9]+)?")


def _find(long_names: list[str], name: str) -> str | None:
    if name in long_names:
        return name
    if len(name) >= 2:
        matches = [n for n in long_names if n.startswith(name)]
        if len(matches) == 1:
            return matches[0]
    return None


def parse_argv(argv: list[str], spec: dict[str, bool]) -> tuple[dict[str, bool | str], list[str]]:
    """Split argv into (options, positionals) according to spec."""
    long_names = [name for name in spec if len(name) > 1]
    options: dict[str, bool | str] = {}
    positionals: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        i += 1
        if arg == "--":
            positionals.extend(argv[i:])
            break
        if arg == "-" or not arg.startswith("-") or _NEGATIVE.fullmatch(arg):
            positionals.append(arg)
        elif arg.startswith("--"):
            written, equals, value = arg[2:].partition("=")
            name = _find(long_names, written)
            negated = False
            if name is None and written.startswith("no-"):
                name = _find(long_names, written[3:])
                negated = True
            if name is None:
                raise ValueError(f"unknown or ambiguous option: --{written}")
            if negated:
                if spec[name] or equals:
                    raise ValueError(f"--no-{name} is not a valid flag")
                options[name] = False
            elif spec[name]:
                if not equals:
                    if i >= len(argv):
                        raise ValueError(f"option --{name} needs a value")
                    value = argv[i]
                    i += 1
                options[name] = value
            else:
                if equals:
                    raise ValueError(f"flag --{name} does not take a value")
                options[name] = True
        else:
            for pos in range(1, len(arg)):
                char = arg[pos]
                if char not in spec:
                    raise ValueError(f"unknown option: -{char}")
                if spec[char]:
                    value = arg[pos + 1 :]
                    if value.startswith("="):
                        value = value[1:]
                    if not value:
                        if i >= len(argv):
                            raise ValueError(f"option -{char} needs a value")
                        value = argv[i]
                        i += 1
                    options[char] = value
                    break
                options[char] = True
    return options, positionals
EOF
