#!/usr/bin/env python3
"""
Gemini Agent Version - SWE-bench Pro Hackathon
"""

import os
import sys
import json
import yaml
import subprocess
from datetime import datetime, UTC
from typing import Dict, Any

from google import genai

AGENT_LOG_PATH = "/tmp/agent.log"


# -------------------------------------------------
# LOGGING
# -------------------------------------------------
def log_to_agent(entry: Dict[str, Any]):
    entry["timestamp"] = datetime.now(UTC).isoformat()

    with open(AGENT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Write readable prompts.md
    try:
        with open("/tmp/prompts.md", "a") as md:
            if entry.get("type") == "request":
                md.write("\n## 🧠 Prompt Sent to Gemini\n\n")
                md.write(entry.get("content", "") + "\n")

            elif entry.get("type") == "response":
                md.write("\n## 🤖 Gemini Response\n\n")
                md.write(entry.get("content", "") + "\n")

            elif entry.get("type") == "tool_use":
                tool = entry.get("tool", "unknown")
                md.write(f"\n## 🛠️ Tool Used: {tool}\n\n")
                md.write(json.dumps(entry.get("args", {}), indent=2) + "\n")

    except Exception as e:
        print(f"Warning writing prompts.md: {e}")


# -------------------------------------------------
# TOOLS
# -------------------------------------------------
def read_file(file_path: str):
    try:
        with open(file_path, "r") as f:
            content = f.read()

        log_to_agent({"type": "tool_use", "tool": "read_file", "args": {"file_path": file_path}})
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(file_path: str, content: str):
    try:
        with open(file_path, "w") as f:
            f.write(content)

        log_to_agent({"type": "tool_use", "tool": "write_file", "args": {"file_path": file_path}})
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def edit_file(file_path: str, old_text: str, new_text: str):
    try:
        with open(file_path, "r") as f:
            content = f.read()

        if old_text not in content:
            return {"success": False, "error": "Old text not found"}

        new_content = content.replace(old_text, new_text, 1)

        with open(file_path, "w") as f:
            f.write(new_content)

        log_to_agent({"type": "tool_use", "tool": "edit_file", "args": {"file_path": file_path}})
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_bash(command: str):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)

        log_to_agent({"type": "tool_use", "tool": "run_bash", "args": {"command": command}})

        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------
# LOAD TASK
# -------------------------------------------------
def load_task(task_file: str):
    with open(task_file, "r") as f:
        return yaml.safe_load(f)


# -------------------------------------------------
# MAIN AGENT
# -------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", required=True)
    args = parser.parse_args()

    task = load_task(args.task_file)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    task_instruction = f"""
You are an expert software engineer.

Task:
{task['description']}

Requirements:
{task['requirements']}

Interface:
{task['interface']}

Failing tests:
{', '.join(task['tests']['fail_to_pass'])}

Files to modify:
{', '.join(task['files_to_modify'])}

Explain the fix and produce patch-ready code changes.
"""

    log_to_agent({"type": "request", "content": task_instruction})

    print("Sending request to Gemini...")

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=task_instruction,
    )

    try:
        text = response.candidates[0].content.parts[0].text
    except Exception:
        text = str(response)

    log_to_agent({"type": "response", "content": text})

    print("Gemini completed response.")
    print(text)


if __name__ == "__main__":
    main()
