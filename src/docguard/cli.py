"""CLI: one JSON object on stdout; operational diagnostics only on stderr."""

import argparse
import os
import sys
from pathlib import Path

from .pipeline import MAX_INPUT_BYTES, extract
from .providers import MockProvider, OllamaProvider, ReplayProvider
from .schema import Document, empty_document


def add_backend_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend", choices=("mock", "ollama", "replay"), default="mock")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL"))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--response-file", type=Path)


def make_provider(args, parser: argparse.ArgumentParser):
    if args.backend == "ollama":
        if not args.model:
            parser.error("--model or OLLAMA_MODEL is required for Ollama")
        return OllamaProvider(args.model, args.ollama_url)
    if args.backend == "replay":
        if args.response_file is None:
            parser.error("--response-file is required for replay")
        return ReplayProvider(args.response_file)
    return MockProvider()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-grounded document extraction")
    subcommands = parser.add_subparsers(dest="command", required=True)
    extraction = subcommands.add_parser("extract", help="Extract a UTF-8 text file, or - for stdin")
    extraction.add_argument("path")
    add_backend_arguments(extraction)
    subcommands.add_parser("schema", help="Print the public JSON Schema")
    args = parser.parse_args(argv)
    if args.command == "schema":
        import json
        print(json.dumps(Document.model_json_schema(), indent=2, ensure_ascii=False))
        return 0
    provider = make_provider(args, extraction)
    try:
        if args.path == "-":
            data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(args.path).open("rb") as stream:
                data = stream.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            document = empty_document("INPUT_TOO_LARGE: limit is 100000 UTF-8 bytes")
            failed = True
        else:
            result = extract(data.decode("utf-8-sig"), provider)
            document, failed = result.document, result.failed
    except (OSError, UnicodeError):
        document = empty_document("INPUT_ERROR: cannot read input as UTF-8 text")
        failed = True
    print(document.model_dump_json(indent=2))
    if failed:
        print("Extraction failed; see warnings in the JSON result.", file=sys.stderr)
    return 2 if failed else 0
