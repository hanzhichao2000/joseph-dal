"""Explicit runtime environment declarations."""

import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


def config_path(xdg_config_home: str | None, home: Path) -> Path:
    root = Path(xdg_config_home) if xdg_config_home else None
    if root is None or not root.is_absolute():
        root = home / ".config"
    return root / "joseph" / ".env"


def parse_dotenv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Malformed dotenv line")
        name, value = line.split("=", 1)
        name = name.strip()
        raw_value = value
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in values:
            raise ValueError("Malformed or duplicate dotenv key")
        if value.startswith(("'", '"')):
            quote = value[0]
            chars: list[str] = []
            index = 1
            while index < len(value) and value[index] != quote:
                if quote == '"' and value[index] == "\\":
                    index += 1
                    if index >= len(value) or value[index] not in '\\"nrt':
                        raise ValueError("Invalid dotenv escape")
                    chars.append({"n": "\n", "r": "\r", "t": "\t"}.get(value[index], value[index]))
                else:
                    chars.append(value[index])
                index += 1
            if index == len(value):
                raise ValueError("Unterminated dotenv value")
            rest = value[index + 1 :]
            if rest and (
                not rest[0].isspace() or (rest.strip() and not rest.lstrip().startswith("#"))
            ):
                raise ValueError("Invalid dotenv trailing text")
            values[name] = "".join(chars)
        else:
            values[name] = re.split(r"\s+#", raw_value, maxsplit=1)[0].strip()
    return values


def _supports_secure_file_reading() -> bool:
    return os.name == "posix" and all(
        hasattr(os, name) for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY", "geteuid")
    )


def read_shared_file(path: Path, *, controlled: bool = False) -> dict[str, str] | None:
    if not _supports_secure_file_reading():
        raise ValueError("Secure shared file access unavailable")
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Shared file path must be absolute")
    fds: list[int] = []
    try:
        directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.append(directory)
        for part in path.parts[1:-1]:
            directory = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            fds.append(directory)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        fds.append(fd)
        metadata = os.fstat(fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & ~0o600
        ):
            raise ValueError("Unsafe shared file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read().decode("utf-8")
        return parse_dotenv(content)
    except FileNotFoundError:
        if controlled:
            raise ValueError("Missing required shared file") from None
        return None
    except (OSError, UnicodeError):
        raise ValueError("Cannot safely read shared file") from None
    finally:
        for opened in reversed(fds):
            os.close(opened)


@dataclass(frozen=True)
class Declaration:
    owner: str
    name: str
    is_shared: bool = False
    sensitive: bool = False
    allowed_sources: frozenset[str] = frozenset({"file", "environment"})
    controlled_allow_environment: bool = False
    controlled_allow_override: bool = False
    required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_sources", frozenset(self.allowed_sources))

    @classmethod
    def shared(
        cls,
        owner: str,
        name: str,
        *,
        sensitive: bool = False,
        allowed_sources: frozenset[str] = frozenset({"file", "environment"}),
        controlled_allow_environment: bool = False,
        controlled_allow_override: bool = False,
        required: bool = False,
    ) -> "Declaration":
        return cls(
            owner=owner,
            name=name,
            is_shared=True,
            sensitive=sensitive,
            allowed_sources=allowed_sources,
            controlled_allow_environment=controlled_allow_environment,
            controlled_allow_override=controlled_allow_override,
            required=required,
        )


class Registry:
    def __init__(self) -> None:
        self._declarations: list[Declaration] = []
        self._active: tuple[Declaration, ...] | None = None
        self._reservations = [
            (name, f"JOSEPH_{name.upper()}_")
            for name in ("api", "dal", "alpha", "mini", "pilot", "live")
        ]
        self._active_reservations: tuple[tuple[str, str], ...] = ()

    def reserve(self, owner: str, prefix: str) -> None:
        reservation = (owner, prefix)
        if reservation not in self._reservations:
            self._reservations.append(reservation)

    def owner_of(self, name: str) -> str | None:
        if self._active is None:
            raise RuntimeError("Registry must be finalized before lookup")
        return next(
            (owner for owner, prefix in self._active_reservations if name.startswith(prefix)), None
        )

    def register(self, declaration: Declaration) -> None:
        if declaration not in self._declarations:
            self._declarations.append(declaration)

    def finalize(self) -> tuple[Declaration, ...]:
        metadata = [field for pair in self._reservations for field in pair]
        metadata.extend(field for item in self._declarations for field in (item.owner, item.name))
        if any(any(not char.isprintable() for char in field) for field in metadata):
            raise ValueError("Invalid registry metadata")
        for index, (owner, prefix) in enumerate(self._reservations):
            if not owner or not re.fullmatch(r"JOSEPH_[A-Z][A-Z0-9_]*_", prefix):
                raise ValueError(f"Invalid reservation {prefix} ({owner})")
            for other_owner, other_prefix in self._reservations[index + 1 :]:
                if prefix.startswith(other_prefix) or other_prefix.startswith(prefix):
                    raise ValueError(
                        f"Overlapping prefixes {prefix} ({owner}), {other_prefix} ({other_owner})"
                    )
        names: dict[str, Declaration] = {}
        for declaration in self._declarations:
            previous = names.get(declaration.name)
            if previous is not None and previous != declaration:
                raise ValueError(
                    f"Conflicting declaration {declaration.name}: "
                    f"{previous.owner}, {declaration.owner}"
                )
            names[declaration.name] = declaration
        for declaration in self._declarations:
            if not declaration.owner or not declaration.allowed_sources <= {"file", "environment"}:
                raise ValueError(f"Invalid declaration {declaration.name}")
            if not re.fullmatch(r"JOSEPH_[A-Z][A-Z0-9_]*[A-Z0-9]|JOSEPH_[A-Z]", declaration.name):
                raise ValueError(f"Invalid variable name {declaration.name}")
            if declaration.is_shared and any(
                declaration.name.startswith(prefix) for _, prefix in self._reservations
            ):
                raise ValueError(f"Shared variable overlaps package {declaration.name}")
            if not declaration.is_shared and not any(
                declaration.name.startswith(prefix) for _, prefix in self._reservations
            ):
                raise ValueError(f"Unreserved variable {declaration.name}")
            for owner, prefix in self._reservations:
                if declaration.name.startswith(prefix) and declaration.owner != owner:
                    raise ValueError(
                        f"Invalid owner for {declaration.name}: {declaration.owner}, {owner}"
                    )
            names[declaration.name] = declaration
        self._active_reservations = tuple(self._reservations)
        self._active = tuple(self._declarations)
        return self._active

    def resolve_sources(
        self,
        file: Mapping[str, str] | None,
        environment: Mapping[str, str],
        *,
        controlled: bool = False,
    ) -> tuple[dict[str, str], tuple[tuple[str, ...], ...]]:
        if self._active is None:
            raise RuntimeError("Registry must be finalized before resolution")
        if file is None:
            if controlled:
                raise ValueError("Missing required shared file")
            file = {}
        values: dict[str, str] = {}
        diagnostics: list[tuple[str, ...]] = []
        for item in self._active:
            if item.required and item.name not in file and item.name not in environment:
                raise ValueError(f"Missing required variable: {item.name}")
            for source, supplied in (("file", file), ("environment", environment)):
                if item.name in supplied and source not in item.allowed_sources:
                    raise ValueError(f"Disallowed {source} source: {item.name}")
            if controlled and item.name in environment and not item.controlled_allow_environment:
                raise ValueError(f"Disallowed environment source: {item.name}")
            if (
                controlled
                and item.name in file
                and item.name in environment
                and not item.controlled_allow_override
            ):
                raise ValueError(f"Disallowed override: {item.name}")
            if item.name in file:
                values[item.name] = file[item.name]
            if item.name in environment:
                if item.name in file:
                    diagnostics.append((item.name, "file", "environment"))
                values[item.name] = environment[item.name]
        active_names = {item.name for item in self._active}
        active_owners = {item.owner for item in self._active if not item.is_shared}
        for source, supplied in (("file", file), ("environment", environment)):
            for name in supplied:
                if not name.startswith("JOSEPH_") or name in active_names:
                    continue
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    raise ValueError(f"Invalid {source} variable name")
                owner = self.owner_of(name)
                if owner is None or owner in active_owners:
                    diagnostics.append((name, source))
        return values, tuple(diagnostics)

    def redacted(self, values: Mapping[str, str]) -> dict[str, str]:
        if self._active is None:
            raise RuntimeError("Registry must be finalized before redaction")
        return {
            item.name: "***" if item.sensitive else values[item.name]
            for item in self._active
            if item.name in values
        }
