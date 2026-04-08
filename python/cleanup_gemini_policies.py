#!/usr/bin/env python3

import argparse
import dataclasses
import tomllib
import typing


class Args(argparse.Namespace):
    file: str = ""
    line_length_limit: int = 80


@dataclasses.dataclass
class Rule:
    """Represents a rule parsed from the TOML file."""

    decision: str
    priority: int
    toolName: str
    commandPrefix: list[str] = dataclasses.field(default_factory=list)
    deny_message: str | None = None


def parse_rules(file_path: str) -> list[Rule]:
    """Parses a TOML file into a list of Rule objects.

    Args:
        file_path: The path to the TOML file.

    Returns:
        A list of parsed Rule objects.
    """
    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    rules: list[Rule] = []
    for r_dict in typing.cast(
        list[dict[str, int | str | list[str]]], data.get("rule", [])
    ):
        rules.append(
            Rule(
                decision=typing.cast(str, r_dict["decision"]),
                priority=typing.cast(int, r_dict["priority"]),
                toolName=typing.cast(str, r_dict["toolName"]),
                commandPrefix=typing.cast(list[str], r_dict.get("commandPrefix", [])),
                deny_message=typing.cast(str | None, r_dict.get("deny_message")),
            )
        )
    return rules


def process_rules(rules: list[Rule]) -> list[Rule]:
    """Combines run_shell_command rules and sorts the list.

    Args:
        rules: The original list of rules.

    Returns:
        The processed and sorted list of rules.
    """
    combined_shell_rules: dict[tuple[str, int, str | None], Rule] = {}
    other_rules: list[Rule] = []

    for rule in rules:
        if rule.toolName == "run_shell_command":
            key = (rule.decision, rule.priority, rule.deny_message)
            if key not in combined_shell_rules:
                combined_shell_rules[key] = Rule(
                    toolName="run_shell_command",
                    decision=rule.decision,
                    priority=rule.priority,
                    deny_message=rule.deny_message,
                )
            for prefix in rule.commandPrefix:
                if prefix not in combined_shell_rules[key].commandPrefix:
                    combined_shell_rules[key].commandPrefix.append(prefix)
        else:
            other_rules.append(rule)

    for rule in combined_shell_rules.values():
        rule.commandPrefix.sort()

    all_rules = list(combined_shell_rules.values()) + other_rules

    def sort_key(r: Rule) -> tuple[str, str, int, str | None]:
        return (r.toolName, r.decision, r.priority, r.deny_message)

    all_rules.sort(key=sort_key)
    return all_rules


def format_rules(rules: list[Rule], line_length_limit: int = 80) -> str:
    """Formats rules into a TOML string.

    Args:
        rules: The list of rules to format.
        line_length_limit: The maximum line length for commandPrefix before wrapping.

    Returns:
        The formatted TOML content as a string.
    """
    output: list[str] = []
    for i, rule in enumerate(rules):
        if i > 0:
            output.append("")
        output.append("[[rule]]")
        output.append(f'toolName = "{rule.toolName}"')
        output.append(f'decision = "{rule.decision}"')
        output.append(f"priority = {rule.priority}")
        if rule.deny_message:
            output.append(f'deny_message = "{rule.deny_message}"')
        if rule.commandPrefix:
            prefixes = ", ".join(f'"{p}"' for p in rule.commandPrefix)
            single_line = f"commandPrefix = [ {prefixes} ]"
            if len(single_line) > line_length_limit:
                output.append("commandPrefix = [")
                for j, prefix in enumerate(rule.commandPrefix):
                    comma = "," if j < len(rule.commandPrefix) - 1 else ""
                    output.append(f'  "{prefix}"{comma}')
                output.append("]")
            else:
                output.append(single_line)
    return "\n".join(output) + "\n"


def main() -> None:
    """Main execution entry point."""
    parser = argparse.ArgumentParser(description="Cleanup and sort TOML rules.")
    _ = parser.add_argument("file", type=str, help="Path to the TOML file to process")
    _ = parser.add_argument(
        "--line-length-limit",
        type=int,
        default=80,
        help="Maximum line length for commandPrefix before wrapping (default: 80)",
    )
    args = parser.parse_args(namespace=Args())

    rules = parse_rules(args.file)
    processed_rules = process_rules(rules)
    content = format_rules(processed_rules, line_length_limit=args.line_length_limit)

    with open(args.file, "w", encoding="utf-8") as f:
        _ = f.write(content)


if __name__ == "__main__":
    main()
