#!/usr/bin/env python3
"""
Template for run_claude.py - SWE-bench Pro Hackathon
This script should invoke Claude to solve the given task.
"""

import os
import sys
import json
import yaml
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import google.generativeai as genai


# Initialize the agent log file
AGENT_LOG_PATH = "/tmp/agent.log"

def log_to_agent(entry: Dict[str, Any]):
    """Append entry to agent.log AND write readable prompts.md"""
    entry["timestamp"] = datetime.utcnow().isoformat() + "Z"

    # --- Save JSONL log (original behaviour) ---
    with open(AGENT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # --- NEW: Write readable markdown log ---
    try:
        with open("/tmp/prompts.md", "a") as md:
            if entry.get("type") == "request":
                md.write("\n## 🧠 Prompt Sent to Claude\n\n")
                md.write(entry.get("content", "") + "\n")

            elif entry.get("type") == "response":
                md.write("\n## 🤖 Claude Response\n\n")
                md.write(entry.get("content", "") + "\n")

            elif entry.get("type") == "tool_use":
                tool = entry.get("tool", "unknown")
                md.write(f"\n## 🛠️ Tool Used: {tool}\n\n")
                md.write(json.dumps(entry.get("args", {}), indent=2) + "\n")

    except Exception as e:
        print(f"Warning: Failed to write prompts.md: {e}")


def read_file(file_path: str) -> Dict[str, Any]:
    """Tool: Read a file's contents"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        log_to_agent({
            "type": "tool_use",
            "tool": "read_file",
            "args": {"file_path": file_path},
            "result": {"success": True, "content_length": len(content)}
        })

        return {"success": True, "content": content}
    except Exception as e:
        log_to_agent({
            "type": "tool_use",
            "tool": "read_file",
            "args": {"file_path": file_path},
            "result": {"success": False, "error": str(e)}
        })
        return {"success": False, "error": str(e)}

def write_file(file_path: str, content: str) -> Dict[str, Any]:
    """Tool: Write content to a file"""
    try:
        with open(file_path, 'w') as f:
            f.write(content)

        log_to_agent({
            "type": "tool_use",
            "tool": "write_file",
            "args": {"file_path": file_path},
            "result": {"success": True, "content_length": len(content)}
        })

        return {"success": True}
    except Exception as e:
        log_to_agent({
            "type": "tool_use",
            "tool": "write_file",
            "args": {"file_path": file_path},
            "result": {"success": False, "error": str(e)}
        })
        return {"success": False, "error": str(e)}

def edit_file(file_path: str, old_text: str, new_text: str) -> Dict[str, Any]:
    """Tool: Edit a specific part of a file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        if old_text not in content:
            return {"success": False, "error": "Old text not found in file"}

        new_content = content.replace(old_text, new_text, 1)

        with open(file_path, 'w') as f:
            f.write(new_content)

        log_to_agent({
            "type": "tool_use",
            "tool": "edit_file",
            "args": {"file_path": file_path, "old_text_length": len(old_text), "new_text_length": len(new_text)},
            "result": {"success": True}
        })

        return {"success": True}
    except Exception as e:
        log_to_agent({
            "type": "tool_use",
            "tool": "edit_file",
            "args": {"file_path": file_path},
            "result": {"success": False, "error": str(e)}
        })
        return {"success": False, "error": str(e)}

def run_bash(command: str) -> Dict[str, Any]:
    """Tool: Execute a bash command"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )

        log_to_agent({
            "type": "tool_use",
            "tool": "run_bash",
            "args": {"command": command},
            "result": {
                "success": True,
                "returncode": result.returncode,
                "stdout_length": len(result.stdout),
                "stderr_length": len(result.stderr)
            }
        })

        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        log_to_agent({
            "type": "tool_use",
            "tool": "run_bash",
            "args": {"command": command},
            "result": {"success": False, "error": str(e)}
        })
        return {"success": False, "error": str(e)}

def load_task(task_file: str) -> Dict[str, Any]:
    """Load the task definition from YAML file"""
    with open(task_file, 'r') as f:
        return yaml.safe_load(f)

def create_tools():
    """Create tool definitions for Claude"""
    return [
        {
            "name": "read_file",
            "description": "Read the contents of a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "write_file",
            "description": "Write content to a file (creates or overwrites)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["file_path", "content"]
            }
        },
        {
            "name": "edit_file",
            "description": "Edit a specific part of a file by replacing old text with new text",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to edit"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The exact text to replace"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The new text to insert"
                    }
                },
                "required": ["file_path", "old_text", "new_text"]
            }
        },
        {
            "name": "run_bash",
            "description": "Execute a bash command",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    ]

def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool based on its name and arguments"""
    if tool_name == "read_file":
        return read_file(tool_args["file_path"])
    elif tool_name == "write_file":
        return write_file(tool_args["file_path"], tool_args["content"])
    elif tool_name == "edit_file":
        return edit_file(tool_args["file_path"], tool_args["old_text"], tool_args["new_text"])
    elif tool_name == "run_bash":
        return run_bash(tool_args["command"])
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

def main():
    """Main function to run Claude on the task"""
    import argparse

    parser = argparse.ArgumentParser(description="Run Claude on a SWE-bench Pro task")
    parser.add_argument("--task-file", required=True, help="Path to the task YAML file")
    args = parser.parse_args()

    # Load the task
    task = load_task(args.task_file)

    # Initialize Claude client
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        sys.exit(1)

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel("gemini-1.5-pro")

    # Prepare the task instruction
    task_instruction = f"""
You are an expert software engineer. You need to solve the following task:

{task['description']}

Technical Requirements:
{task['requirements']}

Interface Specification:
{task['interface']}

The repository is already set up in /testbed. The failing tests are:
{', '.join(task['tests']['fail_to_pass'])}

You have access to the following tools:
- read_file: Read file contents
- write_file: Create or overwrite files
- edit_file: Make specific edits to files
- run_bash: Execute bash commands

Please analyze the failing tests, understand what needs to be implemented, and make the necessary changes to fix them.
Focus on the files mentioned in the task: {', '.join(task['files_to_modify'])}
"""

    # Log the initial request
    log_to_agent({
        "type": "request",
        "content": task_instruction
    })

    # Create the initial message
    messages = [
        {
            "role": "user",
            "content": task_instruction
        }
    ]

    # Main interaction loop
    max_iterations = 30
    for iteration in range(max_iterations):
        print(f"Iteration {iteration + 1}/{max_iterations}")

        # Get Claude's response
        response = model.generate_content(messages[-1]["content"])

        # Log the response
        log_to_agent({
            "type": "response",
            "content": response.text if response.content and hasattr(response.content[0], 'text') else "",
            "stop_reason": response.stop_reason
        })

        # Check if Claude wants to use a tool
        if response.stop_reason == "tool_use":
            tool_use = response.content[-1]
            tool_name = tool_use.name
            tool_args = tool_use.input

            print(f"Claude wants to use tool: {tool_name}")

            # Execute the tool
            tool_result = execute_tool(tool_name, tool_args)

            # Add tool use and result to messages
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(tool_result)
                    }
                ]
            })

        elif response.stop_reason == "end_turn":
            # Claude is done
            print("Claude finished the task")
            break

        else:
            print(f"Unexpected stop reason: {response.stop_reason}")
            break

    print(f"Task execution completed. Agent log saved to {AGENT_LOG_PATH}")

if __name__ == "__main__":
    main()