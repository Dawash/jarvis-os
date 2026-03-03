"""
JARVIS-OS System Control — Full system interaction capabilities.
File ops, process management, networking, screenshots, clipboard, etc.
"""

import asyncio
import os
import shutil
import signal
import socket
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil


class SystemControl:
    """Provides full system-level control to JARVIS agents."""

    def __init__(self):
        self.kernel = None

    async def initialize(self, kernel):
        self.kernel = kernel

    async def shutdown(self):
        pass

    # ── System Info ──────────────────────────────────────────────

    def get_system_stats(self) -> dict:
        cpu_freq = psutil.cpu_freq()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        boot = datetime.fromtimestamp(psutil.boot_time())

        return {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "cpu": {
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "usage_percent": psutil.cpu_percent(interval=0.5),
                "freq_mhz": cpu_freq.current if cpu_freq else 0,
                "per_core": psutil.cpu_percent(percpu=True),
            },
            "memory": {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent,
            },
            "network": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv,
            },
            "boot_time": boot.isoformat(),
        }

    def get_processes(self, sort_by: str = "cpu_percent", limit: int = 20) -> list:
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status", "username"]):
            try:
                info = proc.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x.get(sort_by, 0) or 0, reverse=True)
        return procs[:limit]

    def kill_process(self, pid: int, force: bool = False) -> dict:
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if force:
                proc.kill()
            else:
                proc.terminate()
            return {"status": "success", "message": f"Process {name} (PID {pid}) terminated"}
        except psutil.NoSuchProcess:
            return {"status": "error", "message": f"Process {pid} not found"}
        except psutil.AccessDenied:
            return {"status": "error", "message": f"Access denied for PID {pid}"}

    def get_network_connections(self) -> list:
        connections = []
        for conn in psutil.net_connections(kind="inet"):
            connections.append({
                "fd": conn.fd,
                "family": str(conn.family),
                "type": str(conn.type),
                "local_addr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                "remote_addr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                "status": conn.status,
                "pid": conn.pid,
            })
        return connections

    # ── File Operations ──────────────────────────────────────────

    def list_directory(self, path: str = ".") -> list:
        p = Path(path).resolve()
        items = []
        for item in sorted(p.iterdir()):
            stat = item.stat()
            items.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": item.suffix if item.is_file() else None,
            })
        return items

    def read_file(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {"error": f"File not found: {path}"}
        try:
            content = p.read_text(errors="replace")
            return {
                "path": str(p.resolve()),
                "content": content,
                "size": p.stat().st_size,
                "lines": content.count("\n") + 1,
            }
        except Exception as e:
            return {"error": str(e)}

    def write_file(self, path: str, content: str) -> dict:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"status": "success", "path": str(p.resolve()), "size": len(content)}

    def create_directory(self, path: str) -> dict:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "path": str(p.resolve())}

    def delete_path(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {"error": f"Path not found: {path}"}
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return {"status": "success", "deleted": str(p.resolve())}

    def copy_path(self, src: str, dst: str) -> dict:
        s, d = Path(src), Path(dst)
        if not s.exists():
            return {"error": f"Source not found: {src}"}
        if s.is_dir():
            shutil.copytree(str(s), str(d))
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(s), str(d))
        return {"status": "success", "src": str(s), "dst": str(d)}

    def move_path(self, src: str, dst: str) -> dict:
        s = Path(src)
        if not s.exists():
            return {"error": f"Source not found: {src}"}
        shutil.move(str(s), str(dst))
        return {"status": "success", "src": str(s), "dst": str(dst)}

    def search_files(self, directory: str, pattern: str = "*", recursive: bool = True) -> list:
        p = Path(directory)
        if recursive:
            matches = list(p.rglob(pattern))
        else:
            matches = list(p.glob(pattern))
        return [{"path": str(m), "is_dir": m.is_dir(), "size": m.stat().st_size if m.is_file() else 0} for m in matches[:200]]

    # ── Shell Execution ──────────────────────────────────────────

    async def execute_command(self, command: str, cwd: str = None, timeout: int = 60) -> dict:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return {
                "status": "success",
                "return_code": process.returncode,
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "command": command,
            }
        except asyncio.TimeoutError:
            process.kill()
            return {"status": "error", "message": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def run_background_process(self, command: str, cwd: str = None) -> dict:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            return {
                "status": "success",
                "pid": process.pid,
                "command": command,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Screenshot ───────────────────────────────────────────────

    def take_screenshot(self, output_path: str = None) -> dict:
        try:
            import pyautogui
            import tempfile
            if not output_path:
                tmp_dir = tempfile.gettempdir()
                output_path = str(Path(tmp_dir) / f"jarvis_screenshot_{int(datetime.now().timestamp())}.png")
            screenshot = pyautogui.screenshot()
            screenshot.save(output_path)
            return {"status": "success", "path": output_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Application Management ───────────────────────────────────

    async def open_application(self, app_name: str) -> dict:
        system = platform.system()
        try:
            if system == "Linux":
                result = await self.execute_command(f"nohup {app_name} &>/dev/null &")
            elif system == "Darwin":
                result = await self.execute_command(f"open -a '{app_name}'")
            elif system == "Windows":
                result = await self.execute_command(f'start "" "{app_name}"')
            else:
                return {"status": "error", "message": f"Unsupported platform: {system}"}
            return {"status": "success", "app": app_name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Clipboard (cross-platform) ───────────────────────────────

    async def get_clipboard(self) -> dict:
        system = platform.system()
        try:
            if system == "Windows":
                result = await self.execute_command("powershell.exe -command Get-Clipboard")
            elif system == "Darwin":
                result = await self.execute_command("pbpaste")
            else:
                result = await self.execute_command("xclip -selection clipboard -o")
            return {"content": result.get("stdout", ""), "status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def set_clipboard(self, content: str) -> dict:
        system = platform.system()
        try:
            if system == "Windows":
                # Use powershell to set clipboard
                proc = await asyncio.create_subprocess_shell(
                    "powershell.exe -command Set-Clipboard -Value $input",
                    stdin=asyncio.subprocess.PIPE,
                )
            elif system == "Darwin":
                proc = await asyncio.create_subprocess_shell(
                    "pbcopy",
                    stdin=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    "xclip -selection clipboard",
                    stdin=asyncio.subprocess.PIPE,
                )
            await proc.communicate(input=content.encode())
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
