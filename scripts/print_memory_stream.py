#!/usr/bin/env python3
"""Fetch and decode the Galactic Console system memory stream."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
from typing import Any


def _import_client() -> Any:
    """Import the Galactic Console client module.

    Separating the import allows the script to emit a helpful error message
    instead of the default traceback when the dependency is missing.
    """

    try:
        import galactic_console_client  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise SystemExit(
            "The 'galactic_console_client' package is required. "
            "Install it before running this script."
        ) from exc

    return galactic_console_client


def _create_client(client_module: Any, base_url: str | None, api_key: str | None) -> Any:
    """Create a client instance from the imported module.

    The exact structure of ``galactic_console_client`` depends on how it was
    generated. The helper tries a couple of common patterns so the script can
    work with both hand-written and OpenAPI-generated clients.
    """

    # Pattern 1: the module exposes a high-level ``GalacticConsoleClient``.
    if hasattr(client_module, "GalacticConsoleClient"):
        kwargs: dict[str, Any] = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        return client_module.GalacticConsoleClient(**kwargs)

    # Pattern 2: OpenAPI client with Configuration/ApiClient classes.
    if hasattr(client_module, "Configuration") and hasattr(client_module, "ApiClient"):
        configuration = client_module.Configuration()
        if base_url:
            configuration.host = base_url
        if api_key:
            configuration.api_key = getattr(configuration, "api_key", {})
            configuration.api_key["api_key"] = api_key

        api_client = client_module.ApiClient(configuration)

        # Some generators expose a dedicated API class for system operations.
        for attr_name in ("SystemApi", "SystemsApi", "DefaultApi"):
            api = getattr(client_module, attr_name, None)
            if api is not None:
                return api(api_client)

        return api_client

    # Fall back to returning the module itself. The call helper below can cope
    # with modules exposing ``getSystem`` at the top level.
    return client_module


def _call_get_system(client: Any) -> Any:
    """Call the ``getSystem`` operation on the given client."""

    candidate_objects = [client]
    # Some clients expose a nested attribute, e.g. ``client.system``.
    for attr_name in ("system", "systems", "console"):
        nested = getattr(client, attr_name, None)
        if nested is not None:
            candidate_objects.append(nested)

    for obj in candidate_objects:
        for name in ("getSystem", "get_system"):
            method = getattr(obj, name, None)
            if callable(method):
                return method()

    raise SystemExit("Unable to locate a 'getSystem' call on the client.")


def _extract_memory_stream(system_payload: Any) -> Any:
    """Extract the memory stream value from an API payload."""

    if system_payload is None:
        raise SystemExit("The getSystem call returned no data.")

    # Handle objects with attribute access (e.g. model instances).
    for attr_name in ("memory_stream", "memoryStream", "memory"):
        if hasattr(system_payload, attr_name):
            return getattr(system_payload, attr_name)

    # Handle mapping-based responses.
    if isinstance(system_payload, dict):
        for key in ("memory_stream", "memoryStream", "memory", "memory_streams"):
            if key in system_payload:
                return system_payload[key]

    raise SystemExit("The system payload does not contain a memory stream.")


def _decode_memory_stream(memory_stream: Any, encoding: str) -> str:
    """Decode the memory stream value into text."""

    raw_bytes: bytes
    if isinstance(memory_stream, (bytes, bytearray)):
        raw_bytes = bytes(memory_stream)
    elif isinstance(memory_stream, str):
        try:
            raw_bytes = base64.b64decode(memory_stream, validate=True)
        except (binascii.Error, ValueError):  # Not base64; fall back to text.
            raw_bytes = memory_stream.encode(encoding, errors="strict")
    else:
        # Attempt to serialise unsupported types into JSON before encoding.
        raw_bytes = json.dumps(memory_stream, ensure_ascii=False).encode(encoding)

    try:
        return raw_bytes.decode(encoding)
    except UnicodeDecodeError:
        # If the provided encoding fails, try UTF-8 as a sensible default.
        return raw_bytes.decode("utf-8", errors="replace")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the script."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        dest="base_url",
        help="Override the Galactic Console API base URL.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="API key used to authenticate with the Galactic Console API.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Text encoding to use when decoding the memory stream (default: utf-8).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the script's main logic."""

    args = parse_args(argv)
    client_module = _import_client()
    client = _create_client(client_module, args.base_url, args.api_key)
    system_payload = _call_get_system(client)
    memory_stream = _extract_memory_stream(system_payload)
    decoded = _decode_memory_stream(memory_stream, args.encoding)
    print(decoded)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
