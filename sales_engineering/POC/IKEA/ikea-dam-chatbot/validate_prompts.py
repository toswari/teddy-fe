#!/usr/bin/env python3
"""
Quick validator to ensure the prompts config is loaded and the taxonomy prompt
includes the design styles classification guide.
"""
import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "app_config.toml"


def load_prompts_section():
    with open(CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)
    return cfg.get("prompts", {})


def main():
    prompts = load_prompts_section()
    taxonomy = prompts.get("taxonomy_prompt", "") or ""
    system = prompts.get("system_prompt", "") or ""
    user_tpl = prompts.get("user_prompt_template", "{user_question}")

    # Compose a sample final prompt similar to the app
    question = "Identify the design style and room type."
    complete = user_tpl.format(user_question=question) if "{user_question}" in user_tpl else question
    final_prompt = f"{system}\n\n{complete}\n\n{taxonomy}" if system else f"{complete}\n\n{taxonomy}"

    # Checks
    has_guide = "DESIGN STYLES CLASSIFICATION GUIDE" in taxonomy
    has_format_header = "## IKEA Taxonomy Detected:" in taxonomy

    print("Guide present:", has_guide)
    print("Format header present:", has_format_header)
    print("Final prompt length:", len(final_prompt))

    # Simple assert-like exit codes
    if not (has_guide and has_format_header):
        raise SystemExit(2)

    print("OK: Prompt contains the design styles guide and required header.")


if __name__ == "__main__":
    main()
