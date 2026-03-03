"""
JARVIS-OS Plugin Manager — Dynamic plugin loading, hot-reload, and marketplace.
Supports installing plugins from git URLs and watching for changes.
"""

import asyncio
import importlib
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.plugins")


class PluginManager:
    """Manages plugin lifecycle with hot-reload and marketplace features."""

    def __init__(self, config: dict):
        self.config = config
        self.plugin_dir = Path(config.get("plugins", {}).get("plugin_dir", "./plugins"))
        self.auto_discover = config.get("plugins", {}).get("auto_discover", True)
        self.plugins: dict[str, dict] = {}
        self.kernel = None
        self._watcher = None
        self._installed_file = self.plugin_dir / ".installed.json"

    async def initialize(self, kernel):
        self.kernel = kernel
        if self.auto_discover:
            await self.discover_plugins()
        # Start file watcher for hot-reload
        self._start_watcher()

    async def shutdown(self):
        self._stop_watcher()
        for name, plugin in self.plugins.items():
            try:
                module = plugin.get("module")
                if module and hasattr(module, "on_unload"):
                    await module.on_unload()
            except Exception as e:
                logger.error(f"Plugin unload error ({name}): {e}")

    async def discover_plugins(self):
        """Scan plugin directory and load all plugins."""
        if not self.plugin_dir.exists():
            return

        for path in sorted(self.plugin_dir.glob("*.py")):
            if path.name.startswith("_") or path.name == "manager.py":
                continue
            try:
                await self.load_plugin(path)
            except Exception as e:
                logger.error(f"Failed to load plugin {path.name}: {e}")

    async def load_plugin(self, path: Path) -> Optional[dict]:
        """Load or reload a single plugin."""
        module_name = f"plugins.{path.stem}"

        # Unload if already loaded
        if path.stem in self.plugins:
            await self.unload_plugin(path.stem)

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            info = getattr(module, "PLUGIN_INFO", {"name": path.stem, "version": "0.0.0"})
            tools = []
            if hasattr(module, "get_tools"):
                tools = module.get_tools()

            plugin = {
                "name": info.get("name", path.stem),
                "version": info.get("version", "0.0.0"),
                "description": info.get("description", ""),
                "capabilities": info.get("capabilities", []),
                "tools": tools,
                "module": module,
                "path": str(path),
                "enabled": True,
                "loaded_at": __import__("datetime").datetime.now().isoformat(),
            }
            self.plugins[path.stem] = plugin

            # Call on_load
            if hasattr(module, "on_load") and self.kernel:
                await module.on_load(self.kernel)

            logger.info(f"Plugin loaded: {info.get('name')} v{info.get('version')} ({len(tools)} tools)")
            return plugin

        except Exception as e:
            logger.error(f"Plugin load error ({path.stem}): {e}")
            return None

    async def unload_plugin(self, name: str):
        """Unload a plugin."""
        if name in self.plugins:
            module = self.plugins[name].get("module")
            if module and hasattr(module, "on_unload"):
                try:
                    await module.on_unload()
                except Exception:
                    pass
            del self.plugins[name]
            module_name = f"plugins.{name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

    async def reload_plugin(self, name: str) -> Optional[dict]:
        """Hot-reload a plugin."""
        if name in self.plugins:
            path = Path(self.plugins[name]["path"])
            logger.info(f"Hot-reloading plugin: {name}")
            return await self.load_plugin(path)
        return None

    async def execute_tool(self, plugin_name: str, tool_name: str,
                           arguments: dict, context: dict = None) -> dict:
        """Execute a tool from a specific plugin."""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return {"error": f"Plugin not found: {plugin_name}"}
        if not plugin.get("enabled"):
            return {"error": f"Plugin disabled: {plugin_name}"}

        module = plugin.get("module")
        if not module or not hasattr(module, "execute"):
            return {"error": f"Plugin has no execute function: {plugin_name}"}

        try:
            return await module.execute(tool_name, arguments, context or {})
        except Exception as e:
            return {"error": f"Plugin execution error: {str(e)}"}

    async def install_from_git(self, url: str) -> dict:
        """Install a plugin from a git URL."""
        try:
            import subprocess
            import tempfile

            # Clone to temp dir
            tmp = tempfile.mkdtemp(prefix="jarvis_plugin_")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, tmp],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return {"status": "error", "message": f"Git clone failed: {result.stderr}"}

            # Find plugin files
            installed = []
            for py_file in Path(tmp).glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                dest = self.plugin_dir / py_file.name
                import shutil
                shutil.copy2(py_file, dest)
                plugin = await self.load_plugin(dest)
                if plugin:
                    installed.append(plugin["name"])

            # Also check for plugins/ subdirectory
            plugins_sub = Path(tmp) / "plugins"
            if plugins_sub.exists():
                for py_file in plugins_sub.glob("*.py"):
                    if py_file.name.startswith("_") or py_file.name == "manager.py":
                        continue
                    dest = self.plugin_dir / py_file.name
                    import shutil
                    shutil.copy2(py_file, dest)
                    plugin = await self.load_plugin(dest)
                    if plugin:
                        installed.append(plugin["name"])

            # Clean up
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

            # Record installation
            self._record_install(url, installed)

            return {
                "status": "success",
                "installed": installed,
                "message": f"Installed {len(installed)} plugin(s) from {url}",
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _record_install(self, url: str, plugin_names: list):
        """Record installed plugins for tracking."""
        installed = {}
        if self._installed_file.exists():
            try:
                installed = json.loads(self._installed_file.read_text())
            except Exception:
                pass
        installed[url] = {
            "plugins": plugin_names,
            "installed_at": __import__("datetime").datetime.now().isoformat(),
        }
        self._installed_file.write_text(json.dumps(installed, indent=2))

    # ── Hot-Reload File Watcher ──────────────────────────────────

    def _start_watcher(self):
        """Start watching plugin directory for changes."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class PluginFileHandler(FileSystemEventHandler):
                def __init__(self, manager):
                    self.manager = manager

                def on_modified(self, event):
                    if event.src_path.endswith(".py") and not os.path.basename(event.src_path).startswith("_"):
                        name = Path(event.src_path).stem
                        if name != "manager" and name in self.manager.plugins:
                            logger.info(f"Plugin file changed: {name}")
                            asyncio.get_event_loop().call_soon_threadsafe(
                                asyncio.ensure_future,
                                self.manager.reload_plugin(name),
                            )

            observer = Observer()
            observer.schedule(PluginFileHandler(self), str(self.plugin_dir), recursive=False)
            observer.daemon = True
            observer.start()
            self._watcher = observer
            logger.info("Plugin hot-reload watcher started")
        except ImportError:
            logger.debug("watchdog not available — hot-reload disabled")
        except Exception as e:
            logger.debug(f"Could not start file watcher: {e}")

    def _stop_watcher(self):
        if self._watcher:
            try:
                self._watcher.stop()
            except Exception:
                pass

    # ── Query Methods ────────────────────────────────────────────

    def get_all_tools(self) -> list:
        """Get all tools from all enabled plugins."""
        tools = []
        for name, plugin in self.plugins.items():
            if plugin.get("enabled"):
                for tool in plugin.get("tools", []):
                    tools.append({**tool, "_plugin": name})
        return tools

    def get_plugin_list(self) -> list:
        return [
            {
                "name": p["name"], "version": p["version"],
                "description": p["description"],
                "capabilities": p["capabilities"],
                "tools": [t["name"] for t in p.get("tools", [])],
                "enabled": p["enabled"],
            }
            for p in self.plugins.values()
        ]

    def find_plugin_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which plugin provides a given tool."""
        for name, plugin in self.plugins.items():
            if plugin.get("enabled"):
                for tool in plugin.get("tools", []):
                    if tool["name"] == tool_name:
                        return name
        return None
