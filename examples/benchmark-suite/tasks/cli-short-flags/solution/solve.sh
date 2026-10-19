#!/bin/bash
cat > /app/cliargs.py <<'EOF'
import re

_NEGATIVE_NUMBER = re.compile(r"-[0-9]+(\.[0-9]+)?")


def _long_name(spec: dict[str, bool], text: str) -> str | None:
    """The long spec name that `text` stands for, or None when no long name starts with it.

    Raises ValueError when `text` is a prefix of more than one long name.
    """
    long_names = [name for name in spec if len(name) > 1]
    if text in long_names:
        return text
    if len(text) < 2:
        return None
    matches = [name for name in long_names if name.startswith(text)]
    if len(matches) > 1:
        raise ValueError(f"ambiguous option --{text}: {', '.join(matches)}")
    return matches[0] if matches else None


def parse_argv(argv: list[str], spec: dict[str, bool]) -> tuple[dict[str, bool | str], list[str]]:
    """Split argv into (options, positionals) according to spec."""
    options: dict[str, bool | str] = {}
    positionals: list[str] = []
    i = 0

    def put(name: str, value: bool | str) -> None:
        # Re-insert so the key takes the place of this, its latest, occurrence.
        options.pop(name, None)
        options[name] = value

    def next_value(label: str) -> str:
        nonlocal i
        if i >= len(argv):
            raise ValueError(f"option {label} needs a value")
        i += 1
        return argv[i - 1]

    while i < len(argv):
        arg = argv[i]
        i += 1
        if arg == "--":
            positionals.extend(argv[i:])
            break
        if arg == "-" or not arg.startswith("-") or _NEGATIVE_NUMBER.fullmatch(arg):
            positionals.append(arg)
        elif arg.startswith("--"):
            text, equals, value = arg[2:].partition("=")
            # A direct match (in full or shortened) comes first. "--no-" is the fallback, and only
            # when no long name starts with the text: an ambiguous prefix has already raised.
            name = _long_name(spec, text)
            if name is None:
                negated = _long_name(spec, text[3:]) if text.startswith("no-") else None
                if negated is None or spec[negated] or equals:
                    raise ValueError(f"unknown or misused option: {arg}")
                put(negated, False)
            elif spec[name]:
                put(name, value if equals else next_value(f"--{name}"))
            elif equals:
                raise ValueError(f"flag --{name} does not take a value")
            else:
                put(name, True)
        else:
            for pos in range(1, len(arg)):
                char = arg[pos]
                if char not in spec:
                    raise ValueError(f"unknown option: -{char}")
                if not spec[char]:
                    put(char, True)
                    continue
                rest = arg[pos + 1 :]
                if not rest:
                    # The option is the last character: only then is the next argument taken.
                    put(char, next_value(f"-{char}"))
                else:
                    # One leading "=" is dropped; what remains may be empty.
                    put(char, rest[1:] if rest.startswith("=") else rest)
                break
    return options, positionals
EOF
