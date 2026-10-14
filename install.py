"""Add the ChatSee skills and the ChatSee MCP server to a project, for editors without a
plugin installer (Claude Code, Codex and Gemini have one; see the README).

    python install.py copilot              # GitHub Copilot in VS Code, into the current folder
    python install.py cursor               # Cursor, into the current folder
    python install.py copilot --project PATH

Run it from your project folder, wherever this repository was cloned:

    cd my-agent
    python ../Chatsee-Skills/install.py copilot

It copies the four skills and adds a `chatsee` entry to the editor's MCP file, keeping any
servers the project already has. Run it again to update. Nothing here holds a credential:
the editor signs in with ChatSee in the browser the first time it uses the server.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# editor -> (skills mirror in this repo, where it goes, MCP file, key that holds the servers)
EDITORS = {
    "copilot": (".github/skills", ".github/skills", ".vscode/mcp.json", "servers"),
    "cursor": (".cursor/skills", ".cursor/skills", ".cursor/mcp.json", "mcpServers"),
}
NEXT_STEPS = {
    "copilot": (
        "Open this folder in VS Code, open .vscode/mcp.json and click 'Start' above \"chatsee\".\n"
        "Sign in with ChatSee in the browser, then use Copilot Chat in Agent mode."
    ),
    "cursor": (
        "Open this folder in Cursor, then Settings -> MCP: 'chatsee' shows 'Needs login'.\n"
        "Click it, sign in with ChatSee in the browser, then use the Agent chat."
    ),
}


def install(editor: str, project: Path) -> None:
    skills_src, skills_dst, mcp_rel, key = EDITORS[editor]
    if project.resolve() == HERE:
        sys.exit("Run this from your own project folder, not from inside Chatsee-Skills.")

    src = HERE / skills_src
    dst = project / skills_dst
    for skill in sorted(p for p in src.iterdir() if p.is_dir()):
        shutil.copytree(skill, dst / skill.name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        print(f"  skill   {skills_dst}/{skill.name}")

    server = json.loads((HERE / mcp_rel).read_text(encoding="utf-8"))[key]
    target = project / mcp_rel
    config = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    config.setdefault(key, {}).update(server)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"  server  {mcp_rel}  ->  " + ", ".join(f"{k}: {v['url']}" for k, v in server.items()))

    print(f"\nChatSee is set up for {editor} in {project}\n\nNext: {NEXT_STEPS[editor]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Add ChatSee to a project for Copilot (VS Code) or Cursor.")
    ap.add_argument("editor", choices=sorted(EDITORS))
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="project folder (default: current folder)")
    args = ap.parse_args()
    if not args.project.is_dir():
        sys.exit(f"No such folder: {args.project}")
    install(args.editor, args.project)


if __name__ == "__main__":
    main()
