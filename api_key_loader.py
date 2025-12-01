#!/usr/bin/env python3
"""
API Key Loader for Claude Code Self-Review Hook

Loads API keys from multiple sources in order of priority:
1. Environment variables (highest priority)
2. api_keys.json file
3. config.json (with ${VAR} substitution)
"""

import os
import json
import re
from pathlib import Path
from typing import Optional, Dict

class APIKeyLoader:
    """Manages API key loading from various sources"""

    def __init__(self, hooks_dir: Optional[Path] = None):
        if hooks_dir is None:
            # Default to ~/.claude/hooks
            self.hooks_dir = Path.home() / ".claude" / "hooks"
        else:
            self.hooks_dir = Path(hooks_dir)

        self.api_keys_file = self.hooks_dir / "api_keys.json"
        self.config_file = self.hooks_dir / "config.json"
        self._cache: Dict[str, str] = {}
        self._loaded = False

    def _load_from_file(self) -> Dict[str, str]:
        """Load API keys from api_keys.json file"""
        keys = {}
        if self.api_keys_file.exists():
            try:
                with open(self.api_keys_file, "r", encoding="utf-8") as f:
                    keys = json.load(f)
            except Exception:
                pass
        return keys

    def _substitute_env_vars(self, value: str) -> str:
        """Replace ${VAR} patterns with environment variable values"""
        pattern = r'\$\{([^}]+)\}'

        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(pattern, replacer, value)

    def _load_all(self):
        """Load all API keys from all sources"""
        if self._loaded:
            return

        # 1. Load from api_keys.json file (lowest priority for file-based)
        file_keys = self._load_from_file()
        self._cache.update(file_keys)

        # 2. Environment variables override file-based keys
        env_keys = [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "COHERE_API_KEY",
            "MISTRAL_API_KEY",
            "GROQ_API_KEY",
        ]

        for key in env_keys:
            env_value = os.environ.get(key)
            if env_value:
                self._cache[key] = env_value

        self._loaded = True

    def get(self, key_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get an API key by name.

        Args:
            key_name: Name of the API key (e.g., 'GEMINI_API_KEY')
            default: Default value if key not found

        Returns:
            API key value or default
        """
        self._load_all()

        # Check cache first
        if key_name in self._cache:
            value = self._cache[key_name]
            # Substitute any remaining ${VAR} patterns
            return self._substitute_env_vars(value)

        return default

    def get_gemini_key(self) -> Optional[str]:
        """Get Gemini API key"""
        return self.get("GEMINI_API_KEY")

    def get_openai_key(self) -> Optional[str]:
        """Get OpenAI API key"""
        return self.get("OPENAI_API_KEY")

    def get_anthropic_key(self) -> Optional[str]:
        """Get Anthropic API key"""
        return self.get("ANTHROPIC_API_KEY")

    def has_key(self, key_name: str) -> bool:
        """Check if an API key is available"""
        return self.get(key_name) is not None

    def list_available_keys(self) -> list:
        """List all available API key names"""
        self._load_all()
        return [k for k, v in self._cache.items() if v]

    def reload(self):
        """Force reload of all API keys"""
        self._loaded = False
        self._cache.clear()
        self._load_all()


# Singleton instance
_loader: Optional[APIKeyLoader] = None


def get_loader(hooks_dir: Optional[Path] = None) -> APIKeyLoader:
    """Get the singleton APIKeyLoader instance"""
    global _loader
    if _loader is None:
        _loader = APIKeyLoader(hooks_dir)
    return _loader


def get_api_key(key_name: str, default: Optional[str] = None) -> Optional[str]:
    """Convenience function to get an API key"""
    return get_loader().get(key_name, default)


# For backwards compatibility
def load_api_keys() -> Dict[str, str]:
    """Load all API keys and return as dictionary"""
    loader = get_loader()
    loader._load_all()
    return dict(loader._cache)


if __name__ == "__main__":
    # Test/debug
    loader = get_loader()
    print("Available API keys:")
    for key in loader.list_available_keys():
        # Mask the value for security
        value = loader.get(key)
        masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
        print(f"  {key}: {masked}")
