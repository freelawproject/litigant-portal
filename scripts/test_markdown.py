#!/usr/bin/env python3
"""
Test script to send prompts to Ollama and analyze raw output for markdown patterns.

Usage:
    python scripts/test_markdown.py              # Run all test prompts
    python scripts/test_markdown.py --prompt "your question"  # Single prompt
    python scripts/test_markdown.py --analyze   # Analyze saved responses
"""

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
OUTPUT_DIR = Path(__file__).parent / "markdown_samples"

# Test prompts designed to trigger various markdown patterns
TEST_PROMPTS = [
    "What are the steps to file for eviction in Chicago?",
    "List the courts in Cook County with their addresses",
    "How do I serve legal documents in Illinois?",
    "What are the requirements for small claims court?",
    "Explain the difference between civil and criminal cases",
    "What forms do I need for a divorce in Illinois?",
    "How long does an eviction process take?",
    "What are my rights as a tenant in Chicago?",
]

# Patterns to detect (regex, description)
MARKDOWN_PATTERNS = [
    (r"\\+", "Backslash escapes"),
    (r"<!--.*?-->", "HTML comments"),
    (r"\*{3,}", "Excessive asterisks"),
    (r"#{4,}", "Deep headers (h4+)"),
    (r"```", "Code blocks"),
    (r"`[^`]+`", "Inline code"),
    (r"\|.*\|.*\|", "Tables"),
    (r"^\s*[-*]\s+\[[ x]\]", "Checkboxes"),
    (r"^>\s+", "Blockquotes"),
    (r"\[\^.+\]", "Footnotes"),
    (r"~~.+~~", "Strikethrough"),
    (r"<[a-zA-Z][^>]*>", "HTML tags"),
    (r"&[a-zA-Z]+;", "HTML entities"),
    (r"\d+\\\.", "Escaped list numbers"),
]


def send_prompt(prompt: str) -> str:
    """Send a prompt to Ollama and return raw response."""
    try:
        data = json.dumps(
            {
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "")
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        return ""


def analyze_response(text: str) -> list[tuple[str, list[str]]]:
    """Analyze text for markdown patterns, return list of (pattern_name, matches)."""
    findings = []
    for pattern, name in MARKDOWN_PATTERNS:
        matches = re.findall(pattern, text, re.MULTILINE)
        if matches:
            # Dedupe and limit matches shown
            unique = list(set(matches))[:5]
            findings.append((name, unique))
    return findings


def run_test(prompt: str, save: bool = True) -> dict:
    """Run a single test prompt and analyze the response."""
    print(f"\n{'=' * 60}")
    print(f"PROMPT: {prompt}")
    print("=" * 60)

    response = send_prompt(prompt)
    if not response:
        print("No response received")
        return {}

    print(f"\nRAW RESPONSE:\n{response}")

    findings = analyze_response(response)
    if findings:
        print(f"\n{'!' * 40}")
        print("DETECTED PATTERNS:")
        for name, matches in findings:
            print(f"  - {name}: {matches}")
        print("!" * 40)
    else:
        print("\n[No unhandled patterns detected]")

    result = {
        "prompt": prompt,
        "response": response,
        "findings": [(n, m) for n, m in findings],
    }

    if save:
        OUTPUT_DIR.mkdir(exist_ok=True)
        # Save individual response
        filename = (
            OUTPUT_DIR
            / f"response_{len(list(OUTPUT_DIR.glob('*.json')))}.json"
        )
        with open(filename, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to: {filename}")

    return result


def run_all_tests():
    """Run all test prompts."""
    print("Running markdown pattern tests...")
    print(f"Model: {MODEL}")
    print(f"Prompts: {len(TEST_PROMPTS)}")

    all_findings = {}
    for prompt in TEST_PROMPTS:
        result = run_test(prompt)
        for name, matches in result.get("findings", []):
            if name not in all_findings:
                all_findings[name] = []
            all_findings[name].extend(matches)

    print("\n" + "=" * 60)
    print("SUMMARY - All detected patterns:")
    print("=" * 60)
    for name, matches in sorted(all_findings.items()):
        unique = list(set(matches))[:10]
        print(f"  {name}: {len(matches)} occurrences")
        for m in unique:
            print(f"    - {repr(m)}")


def analyze_saved():
    """Analyze all saved response files."""
    if not OUTPUT_DIR.exists():
        print("No saved responses found. Run tests first.")
        return

    all_findings = {}
    for file in OUTPUT_DIR.glob("*.json"):
        with open(file) as f:
            data = json.load(f)
        for name, matches in data.get("findings", []):
            if name not in all_findings:
                all_findings[name] = []
            all_findings[name].extend(matches)

    print("ANALYSIS OF SAVED RESPONSES")
    print("=" * 60)
    for name, matches in sorted(all_findings.items()):
        unique = list(set(matches))
        print(f"\n{name}: {len(matches)} total, {len(unique)} unique")
        for m in unique[:10]:
            print(f"  - {repr(m)}")


def main():
    parser = argparse.ArgumentParser(description="Test LLM markdown output")
    parser.add_argument("--prompt", "-p", help="Single prompt to test")
    parser.add_argument(
        "--analyze", "-a", action="store_true", help="Analyze saved responses"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Don't save responses to files"
    )
    args = parser.parse_args()

    if args.analyze:
        analyze_saved()
    elif args.prompt:
        run_test(args.prompt, save=not args.no_save)
    else:
        run_all_tests()


if __name__ == "__main__":
    main()
