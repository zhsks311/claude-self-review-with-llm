#!/usr/bin/env python3
"""
Claude Code Self-Review Hook - Cross-Platform Installer

Supports: Windows, macOS, Linux

Usage:
    python install.py              # Interactive installation
    python install.py --backup     # Backup existing settings
    python install.py --force      # Overwrite existing files
    python install.py --skip-api   # Skip API key configuration
    python install.py --uninstall  # Uninstall hooks
    python install.py --yes        # Skip confirmation prompts
"""

import os
import sys
import json
import shutil
import platform
import argparse
from pathlib import Path
from typing import Dict

# Colors for terminal output
class Colors:
    if sys.platform == 'win32':
        os.system('')  # Enable ANSI on Windows

    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'

def print_banner(title: str, color: str = Colors.CYAN):
    print()
    print(f"{color}{'=' * 60}{Colors.RESET}")
    print(f"{color}{title:^60}{Colors.RESET}")
    print(f"{color}{'=' * 60}{Colors.RESET}")
    print()

def print_step(step: str, message: str):
    print(f"{Colors.YELLOW}[{step}]{Colors.RESET} {message}")

def print_success(message: str):
    print(f"  {Colors.GREEN}[OK]{Colors.RESET} {message}")

def print_warning(message: str):
    print(f"  {Colors.YELLOW}[!]{Colors.RESET} {message}")

def print_error(message: str):
    print(f"  {Colors.RED}[X]{Colors.RESET} {message}")

class HookInstaller:
    """Cross-platform hook installer"""

    PYTHON_MODULES = [
        "completion_orchestrator.py",
        "intent_extractor.py",
        "todo_state_detector.py",
        "state_manager.py",
        "security.py",
        "review_orchestrator.py",
        "debate_orchestrator.py",
        "quota_monitor.py",
        "api_key_loader.py",
    ]

    WRAPPER_SCRIPTS = {
        "review_completion_wrapper.py": '''#!/usr/bin/env python3
"""Wrapper for completion review"""
import sys
import json
from datetime import datetime
from pathlib import Path

HOOKS_DIR = Path(__file__).parent
LOG_FILE = HOOKS_DIR / "logs" / "hook-debug.log"

def log(message: str):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\\n")
    except Exception:
        pass

def main():
    log("review_completion_wrapper.py executed")
    try:
        input_data = sys.stdin.read()
        log(f"INPUT received (length: {len(input_data)})")
    except Exception as e:
        log(f"Error reading stdin: {e}")
        print(json.dumps({"continue": True}))
        return

    try:
        sys.path.insert(0, str(HOOKS_DIR))
        from completion_orchestrator import main as orchestrator_main
        sys.stdin = __import__('io').StringIO(input_data)
        orchestrator_main()
    except Exception as e:
        log(f"Error in orchestrator: {e}")
        print(json.dumps({"continue": True}))

if __name__ == "__main__":
    main()
''',
        "review_test_wrapper.py": '''#!/usr/bin/env python3
"""Wrapper for test review"""
import sys
import json
import re
from pathlib import Path

HOOKS_DIR = Path(__file__).parent
TEST_PATTERNS = re.compile(r'test|spec|jest|pytest|mvn\\s+test|gradle\\s+test|npm\\s+test|yarn\\s+test', re.IGNORECASE)

def main():
    try:
        input_data = sys.stdin.read()
        hook_input = json.loads(input_data)
    except Exception:
        print(json.dumps({"continue": True}))
        return

    command = hook_input.get("tool_input", {}).get("command", "")
    if not TEST_PATTERNS.search(command):
        print(json.dumps({"continue": True}))
        return

    try:
        sys.path.insert(0, str(HOOKS_DIR))
        from review_orchestrator import main as orchestrator_main
        staged_input = json.dumps({"stage": "test", "hook_input": hook_input})
        sys.stdin = __import__('io').StringIO(staged_input)
        orchestrator_main()
    except Exception:
        print(json.dumps({"continue": True}))

if __name__ == "__main__":
    main()
''',
        "collect_project_context.py": '''#!/usr/bin/env python3
"""Project context collector"""
import sys
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path

def get_command_output(cmd: list) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                                shell=(sys.platform == 'win32'))
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""

def main():
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        print(json.dumps({"error": "Project directory not found"}))
        return

    context = {}

    java_out = get_command_output(["java", "-version"])
    if java_out:
        match = re.search(r'"([^"]+)"', java_out)
        if match:
            context["java_version"] = match.group(1)

    if (project_path / "pyproject.toml").exists() or (project_path / "requirements.txt").exists():
        py_ver = get_command_output(["python", "--version"])
        if py_ver:
            context["python_version"] = py_ver.replace("Python ", "")

    if (project_path / "package.json").exists():
        node_ver = get_command_output(["node", "--version"])
        if node_ver:
            context["node_version"] = node_ver

    if (project_path / "src" / "main" / "java").exists():
        context["project_structure"] = "java-maven-gradle"
    elif (project_path / "app").exists() and (project_path / "package.json").exists():
        context["project_structure"] = "nextjs-or-node"
    elif (project_path / "src").exists() and (project_path / "package.json").exists():
        context["project_structure"] = "typescript-or-react"
    else:
        context["project_structure"] = "unknown"

    context["collected_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(json.dumps(context, indent=2))

if __name__ == "__main__":
    main()
'''
    }

    def __init__(self, backup: bool = False, force: bool = False, skip_api: bool = False, yes: bool = False):
        self.backup = backup
        self.force = force
        self.skip_api = skip_api
        self.yes = yes

        self.script_dir = Path(__file__).parent.resolve()
        self.home_dir = Path.home()
        self.claude_dir = self.home_dir / ".claude"
        self.hooks_dir = self.claude_dir / "hooks"
        self.settings_file = self.claude_dir / "settings.json"
        self.api_keys_file = self.hooks_dir / "api_keys.json"

    def check_python(self) -> bool:
        print_step("0/6", "Checking Python installation...")
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            print_error(f"Python 3.8+ required, found {version.major}.{version.minor}")
            return False
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True

    def create_directories(self):
        print_step("1/6", "Creating directory structure...")
        dirs = [
            self.hooks_dir,
            self.hooks_dir / "adapters",
            self.hooks_dir / "prompts",
            self.hooks_dir / "logs",
            self.hooks_dir / "state",
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
        print_success(f"Created {self.hooks_dir}")

    def backup_settings(self):
        print_step("2/6", "Checking for existing settings...")
        if self.backup and self.settings_file.exists():
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.settings_file.with_suffix(f".json.backup.{timestamp}")
            shutil.copy2(self.settings_file, backup_file)
            print_success(f"Backup created: {backup_file}")
        else:
            print_warning("No backup needed")

    def copy_python_modules(self):
        print_step("3/6", "Copying Python modules...")
        for filename in self.PYTHON_MODULES:
            src = self.script_dir / filename
            dst = self.hooks_dir / filename
            if src.exists():
                shutil.copy2(src, dst)
                print_success(filename)
            else:
                print_warning(f"{filename} not found")

    def copy_adapters(self):
        print_step("4/6", "Copying adapters...")
        adapters_src = self.script_dir / "adapters"
        adapters_dst = self.hooks_dir / "adapters"
        if adapters_src.exists():
            for py_file in adapters_src.glob("*.py"):
                shutil.copy2(py_file, adapters_dst / py_file.name)
                print_success(py_file.name)
        else:
            print_warning("adapters/ directory not found")

    def copy_prompts_and_config(self):
        print_step("5/6", "Copying prompts and configuration...")

        prompts_src = self.script_dir / "prompts"
        prompts_dst = self.hooks_dir / "prompts"
        if prompts_src.exists():
            for txt_file in prompts_src.glob("*.txt"):
                shutil.copy2(txt_file, prompts_dst / txt_file.name)
            print_success("Prompts copied")

        config_src = self.script_dir / "config.json"
        config_dst = self.hooks_dir / "config.json"
        if config_src.exists():
            if not config_dst.exists() or self.force:
                shutil.copy2(config_src, config_dst)
                print_success("config.json")
            else:
                print_warning("config.json already exists (use --force to overwrite)")

        print_step("5.1/6", "Creating wrapper scripts...")
        for filename, content in self.WRAPPER_SCRIPTS.items():
            dst = self.hooks_dir / filename
            dst.write_text(content, encoding='utf-8')
            print_success(filename)

    def update_settings(self):
        print_step("6/6", "Configuring settings.json...")

        hooks_config = {
            "SessionStart": [
                {
                    "matcher": "startup",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python ~/.claude/hooks/collect_project_context.py \"$CWD\""
                        }
                    ]
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "TodoWrite",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python ~/.claude/hooks/review_completion_wrapper.py",
                            "timeout": 180
                        }
                    ]
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python ~/.claude/hooks/review_test_wrapper.py"
                        }
                    ]
                }
            ]
        }

        if self.settings_file.exists():
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}

        settings["hooks"] = hooks_config

        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        print_success("settings.json updated")

    def configure_api_keys(self):
        """Configure API keys - saves to api_keys.json only"""
        if self.skip_api or self.yes:
            print_warning("Skipping API key configuration")
            return

        print_banner("API Key Configuration", Colors.CYAN)
        print(f"API keys will be saved to: {Colors.CYAN}{self.api_keys_file}{Colors.RESET}")
        print()

        api_keys: Dict[str, str] = {}

        try:
            print(f"{Colors.YELLOW}Gemini API Key (Enter to skip): {Colors.RESET}", end="")
            gemini_key = input().strip()
            if gemini_key:
                api_keys["GEMINI_API_KEY"] = gemini_key

            print(f"{Colors.YELLOW}OpenAI API Key (Enter to skip): {Colors.RESET}", end="")
            openai_key = input().strip()
            if openai_key:
                api_keys["OPENAI_API_KEY"] = openai_key

            print(f"{Colors.YELLOW}Anthropic API Key (Enter to skip): {Colors.RESET}", end="")
            anthropic_key = input().strip()
            if anthropic_key:
                api_keys["ANTHROPIC_API_KEY"] = anthropic_key
        except EOFError:
            print_warning("Non-interactive mode, skipping API key configuration")
            return

        if api_keys:
            with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                json.dump(api_keys, f, indent=2)
            print_success(f"API keys saved to {self.api_keys_file}")
        else:
            print_warning("No API keys provided")

    def check_github_cli(self):
        print()
        print(f"{Colors.YELLOW}Checking GitHub CLI...{Colors.RESET}")
        gh_path = shutil.which('gh')
        if gh_path:
            import subprocess
            result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True)
            if result.returncode == 0:
                print_success("GitHub CLI authenticated")
            else:
                print_warning("GitHub CLI not authenticated. Run 'gh auth login' for Copilot support")
        else:
            print_warning("GitHub CLI not found. Install it for Copilot adapter support")

    def install(self):
        print_banner("Claude Code Self-Review Hook - Installer", Colors.CYAN)
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Install path: {self.hooks_dir}")
        print()

        if not self.check_python():
            return False

        self.create_directories()
        self.backup_settings()
        self.copy_python_modules()
        self.copy_adapters()
        self.copy_prompts_and_config()
        self.update_settings()
        self.configure_api_keys()
        self.check_github_cli()

        print_banner("Installation Complete!", Colors.GREEN)
        print(f"Install location: {Colors.CYAN}{self.hooks_dir}{Colors.RESET}")
        print()
        print(f"{Colors.YELLOW}Next steps:{Colors.RESET}")
        print("  1. Restart Claude Code")
        print("  2. TodoWrite will trigger self-review when all todos complete")
        print()
        return True

    def uninstall(self, remove_all: bool = False):
        print_banner("Claude Code Self-Review Hook - Uninstaller", Colors.RED)

        print(f"{Colors.YELLOW}This will remove the self-review hook system.{Colors.RESET}")
        if remove_all:
            print(f"{Colors.RED}ALL files including logs and API keys will be deleted.{Colors.RESET}")

        if not self.yes:
            print()
            print("Continue? [y/N]: ", end="")
            try:
                confirm = input().strip().lower()
            except EOFError:
                confirm = 'n'
            if confirm != 'y':
                print("Uninstallation cancelled.")
                return

        print()
        print_step("1/3", "Removing Python files...")

        for filename in self.PYTHON_MODULES + list(self.WRAPPER_SCRIPTS.keys()):
            file_path = self.hooks_dir / filename
            if file_path.exists():
                file_path.unlink()
                print_success(f"Removed {filename}")

        print_step("2/3", "Removing adapters, prompts, and config...")

        adapters_dir = self.hooks_dir / "adapters"
        if adapters_dir.exists():
            for f in adapters_dir.glob("*.py"):
                f.unlink()
            if remove_all:
                try:
                    adapters_dir.rmdir()
                except OSError:
                    pass
            print_success("Removed adapters/")

        prompts_dir = self.hooks_dir / "prompts"
        if prompts_dir.exists():
            for f in prompts_dir.glob("*.txt"):
                f.unlink()
            if remove_all:
                try:
                    prompts_dir.rmdir()
                except OSError:
                    pass
            print_success("Removed prompts/")

        config_file = self.hooks_dir / "config.json"
        if config_file.exists():
            config_file.unlink()
            print_success("Removed config.json")

        if self.api_keys_file.exists():
            self.api_keys_file.unlink()
            print_success("Removed api_keys.json")

        if remove_all:
            for subdir in ["logs", "state"]:
                dir_path = self.hooks_dir / subdir
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                    print_success(f"Removed {subdir}/")

            # Try to remove hooks directory if empty
            try:
                self.hooks_dir.rmdir()
                print_success("Removed hooks/")
            except OSError:
                pass

        print_step("3/3", "Updating settings.json...")

        if self.settings_file.exists():
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if "hooks" in settings:
                del settings["hooks"]
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)
                print_success("Removed hooks from settings.json")

        print_banner("Uninstallation Complete!", Colors.GREEN)
        print("Please restart Claude Code for changes to take effect.")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Self-Review Hook Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python install.py                    # Interactive installation
  python install.py --backup           # Backup existing settings
  python install.py --force            # Overwrite existing files
  python install.py --skip-api         # Skip API key prompts
  python install.py --yes              # Non-interactive mode
  python install.py --uninstall        # Remove hooks
  python install.py --uninstall --all  # Remove everything
  python install.py --uninstall --yes  # Remove without confirmation
        """
    )

    parser.add_argument('--backup', '-b', action='store_true',
                        help='Backup existing settings before installation')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Overwrite existing files')
    parser.add_argument('--skip-api', '-s', action='store_true',
                        help='Skip API key configuration')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts (non-interactive)')
    parser.add_argument('--uninstall', '-u', action='store_true',
                        help='Uninstall hooks')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Remove all files including logs (with --uninstall)')

    args = parser.parse_args()

    installer = HookInstaller(
        backup=args.backup,
        force=args.force,
        skip_api=args.skip_api,
        yes=args.yes
    )

    if args.uninstall:
        installer.uninstall(remove_all=args.all)
    else:
        installer.install()


if __name__ == "__main__":
    main()
