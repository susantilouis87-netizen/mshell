#!/usr/bin/env python3  
# -*- coding: utf-8 -*-  
"""  
================================================================================  
MSHELL PRO - ADVANCED TERMINAL ENVIRONMENT v0.22.0  
Developed for: Louis  
  
New features in this version:  
- rev <CMD> <COUNT> : Mengulang eksekusi perintah.  
- see <VAR>         : Melihat nilai dari variabel.  
- A = see B         : Chained assignment syntax.  
- Symmetrical UI    : Strict square edges for UI rendering.  
- Extended Toolkit  : Hex Viewer, Text Editor, Network Scanner, RAF Simulator.  
  
================================================================================  
"""  
  
from __future__ import annotations  
  
import ast  
import base64  
import datetime as _dt  
import io  
import json  
import os  
import platform  
import py_compile  
import re  
import runpy  
import shlex  
import shutil  
import socket  
import subprocess  
import sys  
import tempfile  
import threading  
import time
import math
from contextlib import redirect_stdout, redirect_stderr  
from dataclasses import dataclass, field  
from pathlib import Path  
from typing import Callable, Optional, Any, List, Dict, Tuple  
import urllib.request  
  
# ==============================================================================  
# UI CONFIGURATION & SYMMETRICAL COLORS  
# ==============================================================================  
class UI:  
    """  
    Provides strict Symmetrical UI formatting.  
    All borders are rigid, sharp, and square. No rounded corners allowed.  
    """
    G = "\033[32m"  
    C = "\033[36m"  
    Y = "\033[33m"  
    R = "\033[31m"  
    M = "\033[35m"  
    B = "\033[34m"  
    W = "\033[37m"  
    BOLD = "\033[1m"  
    DIM = "\033[2m"  
    RESET = "\033[0m"  
  
    @staticmethod  
    def box(text: str, color: str = "") -> None:  
        """  
        Renders a perfectly square box around the provided text.  
        
        Args:  
            text: The string to be wrapped in a box.  
            color: The ANSI color code for the box.  
        """
        lines = text.splitlines() or [""]  
        width = max(len(line) for line in lines) + 4  
        print(f"{color}+{'=' * (width - 2)}+")  
        for line in lines:  
            print(f"| {line.ljust(width - 4)} |")  
        print(f"+{'=' * (width - 2)}+{UI.RESET}")  
  
    @staticmethod  
    def colored_text(label: str, value: str, color: str) -> None:  
        """  
        Prints a key-value pair with a colored value.  
        """
        print(f"{label}: {color}{value}{UI.RESET}")  

    @staticmethod
    def draw_separator() -> None:
        """
        Draws a sharp horizontal separator.
        """
        print(f"{UI.DIM}+{'-' * 78}+{UI.RESET}")

# ==============================================================================  
# SMALL UTILITIES  
# ==============================================================================  
def now_str() -> str:  
    """  
    Returns the current timestamp as a formatted string.  
    """
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
  
  
def safe_json_load(path: Path, default: Any) -> Any:  
    """  
    Safely loads a JSON file, returning a default value if it fails.  
    """
    if not path.exists():  
        return default  
    try:  
        with path.open("r", encoding="utf-8") as f:  
            return json.load(f)  
    except Exception:  
        return default  
  
  
def safe_json_save(path: Path, data: Any) -> None:  
    """  
    Safely saves data to a JSON file using a temporary atomic swap.  
    """
    tmp = path.with_suffix(path.suffix + ".tmp")  
    with tmp.open("w", encoding="utf-8") as f:  
        json.dump(data, f, indent=4, ensure_ascii=False)  
    tmp.replace(path)  
  
  
def strip_ansi(text: str) -> str:  
    """  
    Strips ANSI escape codes from a string for logging purposes.  
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", text)  
  
  
def detect_compiler() -> Optional[str]:  
    """  
    Detects the presence of a C compiler in the system PATH.  
    """
    for name in ("gcc", "clang", "cc", "tcc"):  
        p = shutil.which(name)  
        if p:  
            return p  
    if os.name == "nt":  
        for name in ("cl.exe", "clang.exe", "gcc.exe"):  
            p = shutil.which(name)  
            if p:  
                return p  
    return None  
  
  
# ==============================================================================  
# JOBS & PROCESS MANAGEMENT
# ==============================================================================  
@dataclass  
class JobRecord:  
    """  
    Data model representing a background job or thread.  
    """
    id: int  
    command: str  
    kind: str = "thread"  
    created_at: str = field(default_factory=lambda: _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))  
    status: str = "running"  
    exit_code: Optional[int] = None  
    output: str = ""  
    thread: Optional[threading.Thread] = None  
    process: Optional[subprocess.Popen] = None  
    stop_event: threading.Event = field(default_factory=threading.Event)  
    processes: list = field(default_factory=list)  
  
  
class JobManager:  
    """  
    Manages all background processes and multithreading tasks within MShell.  
    """
    def __init__(self):  
        self._lock = threading.Lock()  
        self._next_id = 1  
        self._jobs: dict[int, JobRecord] = {}  
  
    def create_thread_job(self, command: str) -> JobRecord:  
        """  
        Registers a new background thread job.  
        """
        with self._lock:  
            job = JobRecord(id=self._next_id, command=command, kind="thread")  
            self._jobs[job.id] = job  
            self._next_id += 1  
            return job  
  
    def create_process_job(self, command: str, process: subprocess.Popen) -> JobRecord:  
        """  
        Registers a new subprocess job.  
        """
        with self._lock:  
            job = JobRecord(id=self._next_id, command=command, kind="process", process=process)  
            self._jobs[job.id] = job  
            self._next_id += 1  
            return job  
  
    def all_jobs(self) -> list[JobRecord]:  
        """  
        Returns a list of all jobs currently tracked.  
        """
        with self._lock:  
            return [self._jobs[k] for k in sorted(self._jobs)]  
  
    def get(self, job_id: int) -> Optional[JobRecord]:  
        """  
        Retrieves a job by its integer ID.  
        """
        with self._lock:  
            return self._jobs.get(job_id)  
  
    def finish(self, job_id: int, status: str, exit_code: Optional[int] = None, output: str = "") -> None:  
        """  
        Marks a job as finished and saves its output buffer.  
        """
        with self._lock:  
            job = self._jobs.get(job_id)  
            if not job:  
                return  
            job.status = status  
            job.exit_code = exit_code  
            job.output = output  
  
    def attach_process(self, job_id: int, process: subprocess.Popen) -> None:  
        """  
        Attaches an active subprocess to a tracked job.  
        """
        with self._lock:  
            job = self._jobs.get(job_id)  
            if job:  
                job.processes.append(process)  
  
    def kill(self, job_id: int) -> bool:  
        """  
        Sends a termination signal to a tracked job.  
        """
        with self._lock:  
            job = self._jobs.get(job_id)  
            if not job:  
                return False  
            job.stop_event.set()  
            alive = False  
            for proc in list(job.processes) + ([job.process] if job.process else []):  
                if proc and proc.poll() is None:  
                    alive = True  
                    try:  
                        proc.terminate()  
                    except Exception:  
                        pass  
            if not alive:  
                job.status = "killed"  
            return True  
  
  
# ==============================================================================  
# SANDBOX & KERNEL SECURITY SIMULATION
# ==============================================================================  
@dataclass  
class SandboxPolicy:  
    """  
    Defines the security policy for embedded Python and C execution.  
    """
    enabled: bool = True  
    allow_network: bool = False  
    allow_subprocess: bool = False  
    allowed_imports: tuple[str, ...] = (  
        "math",  
        "json",  
        "re",  
        "base64",  
        "datetime",  
        "time",  
        "random",  
        "statistics",  
        "itertools",  
        "functools",  
        "collections",  
        "decimal",  
        "fractions",  
        "operator",  
        "typing",  
        "sys",  
    )  
  
  
class Sandbox:  
    """  
    Provides an isolated environment for untrusted scripts.  
    """
    def __init__(self, config_dir: Path):  
        self.config_dir = config_dir  
        self.policy = SandboxPolicy()  
  
    def _allowed_roots(self) -> list[Path]:  
        """  
        Returns the directories that the sandbox is allowed to read from.  
        """
        return [self.config_dir.resolve(), Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]  
  
    def describe(self) -> str:  
        """  
        Provides a human-readable description of the current sandbox state.  
        """
        roots = "\n".join(f"- {p}" for p in self._allowed_roots())  
        mods = ", ".join(self.policy.allowed_imports)  
        return (  
            f"ENABLED: {self.policy.enabled}\n"  
            f"ALLOW_NETWORK: {self.policy.allow_network}\n"  
            f"ALLOW_SUBPROCESS: {self.policy.allow_subprocess}\n"  
            f"ALLOWED_IMPORTS: {mods}\n"  
            f"ALLOWED_ROOTS:\n{roots}"  
        )  
  
    def path_allowed(self, path: Path) -> bool:  
        """  
        Validates if a given path is within the allowed sandbox roots.  
        """
        try:  
            rp = path.expanduser().resolve()  
        except Exception:  
            return False  
        for root in self._allowed_roots():  
            try:  
                if rp == root or root in rp.parents:  
                    return True  
            except Exception:  
                continue  
        return False  
  
    def safe_open(self, file, mode="r", *args, **kwargs):  
        """  
        Overridden open() function to enforce sandbox filesystem policies.  
        """
        path = Path(file)  
        if not self.path_allowed(path):  
            raise PermissionError(f"Sandbox blocked file access: {file}")  
        return open(path, mode, *args, **kwargs)  
  
    def safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):  
        """  
        Overridden __import__ to restrict module access in untrusted code.  
        """
        root = name.split(".")[0]  
        if root not in self.policy.allowed_imports:  
            raise ImportError(f"Sandbox blocked import: {root}")  
        return __import__(name, globals, locals, fromlist, level)  
  
    def safe_builtins(self):  
        """  
        Constructs a safe dictionary of Python builtins.  
        """
        return {  
            "abs": abs,  
            "all": all,  
            "any": any,  
            "bool": bool,  
            "dict": dict,  
            "enumerate": enumerate,  
            "float": float,  
            "int": int,  
            "len": len,  
            "list": list,  
            "max": max,  
            "min": min,  
            "print": print,  
            "range": range,  
            "reversed": reversed,  
            "round": round,  
            "set": set,  
            "sorted": sorted,  
            "str": str,  
            "sum": sum,  
            "tuple": tuple,  
            "zip": zip,  
            "map": map,  
            "filter": filter,  
            "chr": chr,  
            "ord": ord,  
            "pow": pow,  
            "type": type,  
            "isinstance": isinstance,  
            "Exception": Exception,  
            "ValueError": ValueError,  
            "TypeError": TypeError,  
            "KeyError": KeyError,  
            "IndexError": IndexError,  
            "ImportError": ImportError,  
            "__import__": self.safe_import,  
            "open": self.safe_open,  
            "input": lambda prompt="": input(prompt),  
        }  
  
    def exec_code(self, code: str, filename: str, argv: list[str], stdin: str = "") -> str:  
        """  
        Executes a block of Python code strictly within the sandbox constraints.  
        """
        if not self.policy.enabled:  
            raise RuntimeError("Sandbox is disabled")  
        stdout_buf = io.StringIO()  
        stderr_buf = io.StringIO()  
  
        class _Stdin(io.StringIO):  
            def isatty(self):  
                return False  
  
        old_argv = sys.argv[:]  
        old_stdin = sys.stdin  
        try:  
            sys.argv = [filename, *argv]  
            sys.stdin = _Stdin(stdin)  
            glb = {  
                "__name__": "__main__",  
                "__file__": filename,  
                "__package__": None,  
                "__builtins__": self.safe_builtins(),  
                "__sandbox__": True,  
                "argv": argv,  
                "stdin": stdin,  
            }  
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):  
                exec(compile(code, filename, "exec"), glb, glb)  
            return stdout_buf.getvalue() + stderr_buf.getvalue()  
        finally:  
            sys.argv = old_argv  
            sys.stdin = old_stdin  
  
  
# ==============================================================================  
# SAFE CALCULATOR  
# ==============================================================================  
class SafeCalc(ast.NodeVisitor):  
    """  
    AST-based safe math evaluator to prevent arbitrary code execution during math ops.  
    """
    ALLOWED_BINOPS = {  
        ast.Add: lambda a, b: a + b,  
        ast.Sub: lambda a, b: a - b,  
        ast.Mult: lambda a, b: a * b,  
        ast.Div: lambda a, b: a / b,  
        ast.FloorDiv: lambda a, b: a // b,  
        ast.Mod: lambda a, b: a % b,  
        ast.Pow: lambda a, b: a ** b,  
    }  
    ALLOWED_UNARY = {  
        ast.UAdd: lambda a: +a,  
        ast.USub: lambda a: -a,  
    }  
  
    def visit(self, node):  # type: ignore[override]  
        """  
        Traverses the AST tree safely.  
        """
        if isinstance(node, ast.Expression):  
            return self.visit(node.body)  
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):  
            return node.value  
        if isinstance(node, ast.BinOp) and type(node.op) in self.ALLOWED_BINOPS:  
            return self.ALLOWED_BINOPS[type(node.op)](self.visit(node.left), self.visit(node.right))  
        if isinstance(node, ast.UnaryOp) and type(node.op) in self.ALLOWED_UNARY:  
            return self.ALLOWED_UNARY[type(node.op)](self.visit(node.operand))  
        raise ValueError("Ekspresi tidak diizinkan")  
  
    @classmethod  
    def eval(cls, expr: str) -> float:  
        """  
        Parses and evaluates a string math expression.  
        """
        tree = ast.parse(expr, mode="eval")  
        return cls().visit(tree)  
  
  
# ==============================================================================  
# PERSISTENCE ENGINE  
# ==============================================================================  
@dataclass  
class DataCenter:  
    """  
    Manages loading, saving, and persisting all user settings, variables, and aliases.  
    """
    config_dir: Path = field(default_factory=lambda: Path.home() / ".mshell")  
    vars_file: Path = field(init=False)  
    mods_file: Path = field(init=False)  
    hist_file: Path = field(init=False)  
    aliases_file: Path = field(init=False)  
    py_plugins_dir: Path = field(init=False)  
    c_build_dir: Path = field(init=False)  
  
    vars: dict = field(default_factory=dict)  
    mods: dict = field(default_factory=dict)  
    aliases: dict = field(default_factory=dict)  
  
    def __post_init__(self):  
        self.config_dir.mkdir(parents=True, exist_ok=True)  
        self.py_plugins_dir = self.config_dir / "py_plugins"  
        self.c_build_dir = self.config_dir / "c_build"  
        self.py_plugins_dir.mkdir(exist_ok=True)  
        self.c_build_dir.mkdir(exist_ok=True)  
  
        self.vars_file = self.config_dir / "env_vars.json"  
        self.mods_file = self.config_dir / "plugins.json"  
        self.hist_file = self.config_dir / "history.log"  
        self.aliases_file = self.config_dir / "aliases.json"  
        self.load_all()  
  
    def load_all(self) -> None:  
        """  
        Loads all local configs into memory.  
        """
        self.vars = safe_json_load(  
            self.vars_file,  
            {"USER": "louis", "SHELL": "mshell-pro", "VER": "0.22.0"},  
        )  
        self.mods = safe_json_load(self.mods_file, {})  
        self.aliases = safe_json_load(  
            self.aliases_file,  
            {  
                "ll": "ls -la",  
                "grep": "findstr" if os.name == "nt" else "grep",  
                "cls": "clear",  
            },  
        )  
  
    def save_vars(self) -> None:  
        safe_json_save(self.vars_file, self.vars)  
  
    def save_mods(self) -> None:  
        safe_json_save(self.mods_file, self.mods)  
  
    def save_aliases(self) -> None:  
        safe_json_save(self.aliases_file, self.aliases)  
  
    def log_history(self, cmd: str) -> None:  
        try:  
            with self.hist_file.open("a", encoding="utf-8") as f:  
                f.write(f"[{now_str()}] {cmd}\n")  
        except Exception:  
            pass  
  
  
# ==============================================================================  
# CONTROL-FLOW NODES  
# ==============================================================================  
@dataclass  
class IfBranch:  
    kind: str  # if / elif / else  
    condition: str = ""  
    body: list[str] = field(default_factory=list)  
  
  
@dataclass  
class IfBlock:  
    branches: list[IfBranch] = field(default_factory=list)  
  
  
@dataclass  
class TryBlock:  
    try_body: list[str] = field(default_factory=list)  
    exc_body: list[str] = field(default_factory=list)  
    pass_body: list[str] = field(default_factory=list)  
  
  
@dataclass  
class DoUntilBlock:  
    body: list[str] = field(default_factory=list)  
    condition: str = ""  
  
  
# ==============================================================================  
# EXTENDED TOOLKIT (BUILTINS)
# ==============================================================================  
class ExtendedToolkit:
    """
    Houses all the new advanced built-in tools like Hex Viewer, System Monitor, etc.
    Designed symmetrically and strictly for MSHELL PRO environment.
    """
    
    @staticmethod
    def cmd_hexdump(args: list[str], stdin: Optional[str] = None) -> str:
        """
        Dumps binary or text data into a strict symmetrical hex layout.
        """
        data = stdin if stdin else " ".join(args)
        if not data:
            print("Usage: hexdump <string> or echo <str> | hexdump")
            return ""
        
        bdata = data.encode('utf-8', errors='ignore')
        UI.box("HEX VIEWER", UI.Y)
        
        output = []
        for i in range(0, len(bdata), 16):
            chunk = bdata[i:i+16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            line = f"{i:08X}  {hex_str:<47}  |{ascii_str:<16}|"
            print(line)
            output.append(line)
        return "\n".join(output)

    @staticmethod
    def cmd_sysmon(args: list[str], stdin: Optional[str] = None) -> str:
        """
        A pseudo-system monitor that checks memory, CPU structure, and device ID.
        Includes references to specific hardware environments.
        """
        UI.box("SYSMONITOR PRO", UI.M)
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Node    : {platform.node()}")
        print(f"Machine : {platform.machine()}")
        
        # Hardcoded environmental checks based on known variables
        print("Hardware Context:")
        print(" -> Detected Target : MSI GF63 Thin (MS-16R8) [Simulated]")
        print(" -> Mobile Sync     : iQOO Z10 Native Profile [Simulated]")
        print(f" -> Python Core     : {platform.python_version()}")
        
        try:
            import psutil
            mem = psutil.virtual_memory()
            print(f"Memory  : {mem.used / 1024 / 1024:.2f} MB / {mem.total / 1024 / 1024:.2f} MB")
        except ImportError:
            print(f"Memory  : {UI.DIM}[psutil not installed, using estimates]{UI.RESET}")
            
        return "sysmon executed"

    @staticmethod
    def cmd_rafsim(args: list[str], stdin: Optional[str] = None) -> str:
        """
        Simulates a Read-After-Free (RAF) exploit sequence in kernel memory context.
        Strictly an educational simulation block.
        """
        UI.box("KERNEL EXP SIMULATOR", UI.R)
        print(f"{UI.Y}[*]{UI.RESET} Initializing memory pool allocation...")
        time.sleep(0.3)
        print(f"{UI.G}[+]{UI.RESET} Object A allocated at 0xFFFF800012345678")
        time.sleep(0.3)
        print(f"{UI.Y}[*]{UI.RESET} Freeing Object A...")
        time.sleep(0.3)
        print(f"{UI.R}[!]{UI.RESET} Dangling pointer retained in cache.")
        time.sleep(0.4)
        print(f"{UI.Y}[*]{UI.RESET} Reallocating Object B of same size...")
        time.sleep(0.3)
        print(f"{UI.G}[+]{UI.RESET} Object B overlaps Object A space.")
        print(f"{UI.R}[!] Read-After-Free (RAF) triggered! Execution hijacked.{UI.RESET}")
        return "raf_sim_complete"


# ==============================================================================  
# CORE SHELL ENGINE  
# ==============================================================================  
class MShell:  
    """  
    The main execution engine for MShell Pro.  
    Handles tokenization, pipelines, environment routing, and UI.  
    """
    def __init__(self):  
        self.db = DataCenter()  
        self.is_running = True  
        self.exit_code = 0  
        self.jobs = JobManager()  
        self.sandbox = Sandbox(self.db.config_dir)  
        self._job_local = threading.local()  
        self.builtins: dict[str, Callable[..., Any]] = {}  
        self.register_builtins()  
        self.boot_plugins()  
  
    # --------------------------------------------------------------------------  
    # REGISTRATION  
    # --------------------------------------------------------------------------  
    def register_builtins(self):  
        """  
        Registers all native built-in commands.  
        """
        # File System  
        self.builtins["ls"] = self.cmd_ls  
        self.builtins["cd"] = self.cmd_cd  
        self.builtins["pwd"] = self.cmd_pwd  
        self.builtins["cat"] = self.cmd_cat  
        self.builtins["mkdir"] = self.cmd_mkdir  
        self.builtins["rm"] = self.cmd_rm  
        self.builtins["touch"] = self.cmd_touch  
  
        # System & Env  
        self.builtins["set"] = self.cmd_set  
        self.builtins["unset"] = self.cmd_unset  
        self.builtins["env"] = self.cmd_env  
        self.builtins["exit"] = self.cmd_exit  
        self.builtins["clear"] = self.cmd_clear  
        self.builtins["help"] = self.cmd_help  
        self.builtins["whoami"] = self.cmd_whoami  
        self.builtins["sysinfo"] = self.cmd_sysinfo  
  
        # Tools & Security  
        self.builtins["calc"] = self.cmd_calc  
        self.builtins["hash"] = self.cmd_hash  
        self.builtins["encrypt"] = self.cmd_encrypt  
        self.builtins["decrypt"] = self.cmd_decrypt  
        self.builtins["netinfo"] = self.cmd_netinfo  
        self.builtins["hexdump"] = ExtendedToolkit.cmd_hexdump
        self.builtins["sysmon"] = ExtendedToolkit.cmd_sysmon
        self.builtins["rafsim"] = ExtendedToolkit.cmd_rafsim
  
        # NEW FEATURES: rev & see
        self.builtins["rev"] = self.cmd_rev
        self.builtins["see"] = self.cmd_see

        # Python & C  
        self.builtins["py"] = self.cmd_py  
        self.builtins["cextender"] = self.cmd_cextender  
  
        # Plugin System  
        self.builtins["install"] = self.cmd_install  
        self.builtins["plugins"] = self.cmd_plugins  
        self.builtins["alias"] = self.cmd_alias  
        self.builtins["unalias"] = self.cmd_unalias  
        self.builtins["jobs"] = self.cmd_jobs  
        self.builtins["fg"] = self.cmd_fg  
        self.builtins["kill"] = self.cmd_kill  
        self.builtins["sandbox"] = self.cmd_sandbox  
        self.builtins["notify"] = self.cmd_notify
        self.builtins["fastfetch"] = self.cmd_fastfetch
        self.builtins["cyrl"] = self.cmd_cyrl
    def boot_plugins(self):  
        """  
        Loads installed plugins from the data center at boot.  
        """
        for name, info in self.db.mods.items():  
            ptype = info.get("type", "json")  
            commands = info.get("commands", [])  
            for cmd in commands:  
                if ptype == "py":  
                    self.builtins[cmd] = self.python_plugin_wrapper(name, cmd)  
                elif ptype == "c":  
                    self.builtins[cmd] = self.c_plugin_wrapper(name, cmd)  
                else:  
                    self.builtins[cmd] = self.json_plugin_wrapper(name, cmd)  
  
    # --------------------------------------------------------------------------  
    # WRAPPERS  
    # --------------------------------------------------------------------------  
    def json_plugin_wrapper(self, plugin_name: str, cmd_name: str):  
        def _run(args, stdin=None):  
            print(f"{UI.Y}[Plugin:{plugin_name}]{UI.RESET} Executing {cmd_name} with {args}")  
        return _run  
  
    def python_plugin_wrapper(self, plugin_name: str, cmd_name: str):  
        def _run(args, stdin=None):  
            meta = self.db.mods.get(plugin_name, {})  
            script = meta.get("script")  
            if not script or not Path(script).exists():  
                print(f"{UI.R}Python plugin '{plugin_name}' missing script.{UI.RESET}")  
                return  
            return self.run_python_script(Path(script), args=args, stdin=stdin, plugin_name=plugin_name)  
        return _run  
  
    def c_plugin_wrapper(self, plugin_name: str, cmd_name: str):  
        def _run(args, stdin=None):  
            meta = self.db.mods.get(plugin_name, {})  
            src = meta.get("source")  
            if not src or not Path(src).exists():  
                print(f"{UI.R}C plugin '{plugin_name}' missing source.{UI.RESET}")  
                return  
            return self.build_and_run_c(Path(src), args=args, stdin=stdin, plugin_name=plugin_name)  
        return _run  
  
    # --------------------------------------------------------------------------  
    # BUILTIN COMMANDS - NEW FEATURES (rev, see)
    # --------------------------------------------------------------------------  
    def cmd_rev(self, args, stdin=None):
        """
        Repeats a specified command a number of times.
        Syntax: rev <CMD> <COUNT>
        """
        if len(args) < 2:
            print("Usage: rev <CMD> <COUNT>")
            print("Note: The count can be a variable ($VAR)")
            return ""

        try:
            # Evaluate the last argument as the count integer
            count_str = args[-1]
            count = int(count_str)
        except ValueError:
            print(f"{UI.R}rev error: COUNT must be an integer. Got '{args[-1]}'{UI.RESET}")
            return ""

        # Reconstruct the command without the count
        cmd_parts = args[:-1]
        cmd_str = " ".join(cmd_parts)

        # Execute it COUNT times sequentially
        last_out = ""
        for _ in range(count):
            self.execute_line(cmd_str, emit=True)
            
        return ""

    def cmd_see(self, args, stdin=None):
        """
        Sees and returns the value of a variable.
        Syntax: see <VAR>
        """
        if not args:
            print("Usage: see <VAR_NAME>")
            return ""
            
        var_name = args[0]
        # Strip $ if the user accidentally included it
        if var_name.startswith('$'):
            var_name = var_name[1:]
            
        val = self.db.vars.get(var_name, "")
        print(val)
        return str(val)

    # --------------------------------------------------------------------------  
    # BUILTIN COMMANDS - FILE SYSTEM  
    # --------------------------------------------------------------------------  
    def cmd_ls(self, args, stdin=None):  
        path = Path(args[0]) if args else Path(".")  
        try:  
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))  
            for e in entries:  
                try:  
                    size = e.stat().st_size  
                    mtime = _dt.datetime.fromtimestamp(e.stat().st_mtime).strftime("%Y-%m-%d %H:%M")  
                    color = UI.B + UI.BOLD if e.is_dir() else UI.W  
                    print(f"{color}{e.name.ljust(24)}{UI.RESET} {UI.DIM}{str(size).rjust(10)} bytes | {mtime}{UI.RESET}")  
                except Exception:  
                    print(e.name)  
        except Exception as e:  
            print(f"{UI.R}ls: {e}{UI.RESET}")  
  
    def cmd_cd(self, args, stdin=None):  
        target = args[0] if args else os.path.expanduser("~")  
        try:  
            os.chdir(target)  
        except Exception as e:  
            print(f"{UI.R}cd: {e}{UI.RESET}")  
  
    def cmd_pwd(self, args, stdin=None):  
        print(os.getcwd())  
  
    def cmd_cat(self, args, stdin=None):  
        if stdin is not None and stdin != "":  
            print(stdin, end="" if stdin.endswith("\n") else "\n")  
            return stdin  
        if not args:  
            return ""  
        try:  
            with open(args[0], "r", encoding="utf-8", errors="ignore") as f:  
                content = f.read()  
                print(content, end="" if content.endswith("\n") else "\n")  
                return content  
        except Exception as e:  
            print(f"{UI.R}cat: {e}{UI.RESET}")  
            return ""  
  
    def cmd_mkdir(self, args, stdin=None):  
        if not args:  
            print("Usage: mkdir <path>")  
            return  
        try:  
            os.makedirs(args[0], exist_ok=True)  
            print(f"Dir '{args[0]}' created.")  
        except Exception as e:  
            print(f"{UI.R}mkdir: {e}{UI.RESET}")  
  
    def cmd_rm(self, args, stdin=None):  
        if not args:  
            print("Usage: rm <path>")  
            return  
        p = Path(args[0])  
        try:  
            if p.is_dir():  
                shutil.rmtree(p)  
            else:  
                p.unlink()  
            print(f"Removed {args[0]}")  
        except Exception as e:  
            print(f"{UI.R}rm: {e}{UI.RESET}")  
  
    def cmd_touch(self, args, stdin=None):  
        if not args:  
            print("Usage: touch <path>")  
            return  
        try:  
            Path(args[0]).touch()  
            print(f"Touched {args[0]}")  
        except Exception as e:  
            print(f"{UI.R}touch: {e}{UI.RESET}")  
  
    # --------------------------------------------------------------------------  
    # BUILTIN COMMANDS - ENV  
    # --------------------------------------------------------------------------  
    def cmd_set(self, args, stdin=None):  
        if len(args) < 2 and stdin in (None, ""):  
            print("Usage: set <KEY> <VALUE>")  
            return  
        if not args:  
            print("Usage: set <KEY> <VALUE>")  
            return  
        key = args[0]  
        val = " ".join(args[1:]) if len(args) > 1 else (stdin.strip() if stdin else "")  
        self.db.vars[key] = val  
        self.db.save_vars()  
        print(f"{UI.G}Variable {key} set.{UI.RESET}")  
  
    def cmd_unset(self, args, stdin=None):  
        if not args:  
            print("Usage: unset <KEY>")  
            return  
        key = args[0]  
        if key in self.db.vars:  
            del self.db.vars[key]  
            self.db.save_vars()  
            print(f"{UI.Y}Variable {key} removed.{UI.RESET}")  
        else:  
            print(f"{UI.R}unset: {key} not found{UI.RESET}")  
  
    def cmd_env(self, args, stdin=None):  
        UI.box("ENVIRONMENT VARIABLES", UI.C)  
        for k, v in sorted(self.db.vars.items()):  
            print(f"{UI.G}{k}{UI.RESET} = {v}")  
  
    def cmd_sysinfo(self, args, stdin=None):  
        UI.box("SYSTEM ARCHITECTURE", UI.M)  
        print(f"OS: {platform.system()} {platform.release()}")  
        print(f"Node: {platform.node()}")  
        print(f"Arch: {platform.machine()}")  
        print(f"Python: {platform.python_version()}")  
        print(f"MShell: {self.db.vars.get('VER', 'unknown')}")  
  
    def cmd_whoami(self, args, stdin=None):  
        print(f"{UI.C}{self.db.vars.get('USER', 'unknown')}{UI.RESET} @ {platform.node()}")  
  
    def cmd_clear(self, args, stdin=None):  
        os.system("cls" if os.name == "nt" else "clear")  
  
    def cmd_exit(self, args, stdin=None):  
        self.is_running = False  
        print(f"{UI.M}Closing MShell Pro...{UI.RESET}")  
        time.sleep(1) 
        print(f"Tak kenal maka tak tau, maka selamat tinggalah Mshell Pro.")  
        
    def cmd_help(self, args, stdin=None):  
        UI.box("MSHELL PRO ASSISTANCE", UI.G)  
        print("Core commands:")  
        cmds = sorted(k for k in self.builtins.keys() if k not in {"alias", "unalias"})  
        for i in range(0, len(cmds), 4):  
            print("  ".join(c.ljust(15) for c in cmds[i:i+4]))  
        print()  
        print("Assignments: A = 10 | A = see B | A = $B")
        print("Repeater:    rev <CMD> <COUNT>")
        print("Python:      py run <file.py|code> | py run --unsafe <file.py|code> | py compile <file.py>")  
        print("C:           cextender build <file.c> [-o name] | cextender run <file.c>")  
        print("Jobs:        jobs | fg <id> | kill <id>")  
        print("Sandbox:     sandbox [on|off|status]")  
        print("Plugins:     install json|py|c ...")  
        print("Blocks:      if/elif/else/endif | try/exc/pass | do/until/stop")  
  
    # --------------------------------------------------------------------------  
    # BUILTIN COMMANDS - SECURITY / TOOLS  
    # --------------------------------------------------------------------------  
    def cmd_hash(self, args, stdin=None):  
        if not args and not stdin:  
            print("Usage: hash <string> or echo <string> | hash")  
            return  
        data = stdin if stdin is not None and stdin != "" else " ".join(args)  
        md5 = __import__("hashlib").md5(data.encode()).hexdigest()  
        sha256 = __import__("hashlib").sha256(data.encode()).hexdigest()  
        print(f"MD5: {UI.Y}{md5}{UI.RESET}")  
        print(f"SHA256: {UI.G}{sha256}{UI.RESET}")  
        return sha256  
  
    def cmd_encrypt(self, args, stdin=None):  
        data = stdin if stdin is not None and stdin != "" else " ".join(args)  
        if not data:  
            return ""  
        enc = base64.b64encode(data.encode()).decode()  
        print(f"Base64: {UI.C}{enc}{UI.RESET}")  
        return enc  
  
    def cmd_decrypt(self, args, stdin=None):  
        data = stdin if stdin is not None and stdin != "" else " ".join(args)  
        if not data:  
            return ""  
        try:  
            dec = base64.b64decode(data.encode()).decode()  
            print(f"Plain: {UI.G}{dec}{UI.RESET}")  
            return dec  
        except Exception:  
            print(f"{UI.R}Invalid Base64 data{UI.RESET}")  
            return ""  
  
    def cmd_netinfo(self, args, stdin=None):  
        hostname = socket.gethostname()  
        local_ip = "127.0.0.1"  
        try:  
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
            try:  
                s.connect(("8.8.8.8", 80))  
                local_ip = s.getsockname()[0]  
            finally:  
                s.close()  
        except Exception:  
            try:  
                local_ip = socket.gethostbyname(hostname)  
            except Exception:  
                pass  
        print(f"Hostname: {UI.C}{hostname}{UI.RESET}")  
        print(f"Local IP: {UI.G}{local_ip}{UI.RESET}")  
  
    def cmd_calc(self, args, stdin=None):  
        expr = " ".join(args) if args else (stdin or "")  
        if not expr.strip():  
            print("Usage: calc <expression> or echo <expression> | calc")  
            return  
        try:  
            result = SafeCalc.eval(expr)  
            print(f"{UI.Y}Result: {result}{UI.RESET}")  
            return str(result)  
        except Exception as e:  
            print(f"{UI.R}Calc Error: {e}{UI.RESET}")  
            return ""  

    def cmd_notify(self, args, stdin=None):
        target = " ".join(args) if args else (stdin or "")
        if not target.strip():
            print("Usage: notify <URL or IP>")
            return

        try:
            result = subprocess.run(
                ["ping", "-c", "1", target],
                capture_output=True,
                text=True
            )

            output = result.stdout

            match = re.search(r"time[=<]([\d.]+)\s*ms", output)

            if match:
                latency = match.group(1)
                print(f"🔔 NOTIFY → {target}")
                print(f"⏱ latency send = {latency} ms")
            else:
                print(f"🔔 NOTIFY → {target}")
                print("⏱ latency send = N/A")

        except Exception as e:
            print(f"❌ notify error: {e}")
            
    def cmd_fastfetch(self, args, stdin=None):
        # Logo M
        logo = [
            "███    ███",
            "████  ████",
            "██ ████ ██",
            "██  ██  ██",
            "██      ██",
        ]

        # Info system
        info = [
            f"OS       : {sys.platform}",
            f"Kernel   : {os.name}",
            f"Python   : {sys.version.split()[0]}",
        ]

        # CPU
        if sys.platform.startswith("win"):
            cpu = os.environ.get("PROCESSOR_IDENTIFIER", "Unknown CPU")
        else:
            cpu = platform.machine() or "Unknown CPU"

        info.append(f"CPU      : {cpu}")

        # RAM
        ram = "Unknown"
        if sys.platform.startswith("linux"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            ram_bytes = pages * page_size
            ram = ram_bytes / (1024 ** 3)
        elif sys.platform == "win32":
            try:
                ram = os.popen("wmic computersystem get TotalPhysicalMemory").read().split()[-1]
            except:
                pass

        info.append(f"RAM      : {ram}")

        # Print logo + info side by side
        max_lines = max(len(logo), len(info))

        for i in range(max_lines):
            left = logo[i] if i < len(logo) else " " * len(logo[0])
            right = info[i] if i < len(info) else ""
            print(f"{left}   {right}")    
    
    
    def cmd_cyrl(self, args, stdin=None):
        url = " ".join(args) if args else (stdin or "")
        if not url.strip():
            print("usage: cyrl <url> or <ip>")
            return

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = r.read(500).decode(errors="ignore")
                print(data)
        except Exception as e:
            print(f"Cyrl Error: {e}")
    # --------------------------------------------------------------------------  
    # ALIAS COMMANDS  
    # --------------------------------------------------------------------------  
    def cmd_alias(self, args, stdin=None):  
        if len(args) == 0:  
            UI.box("ALIASES", UI.Y)  
            for k, v in sorted(self.db.aliases.items()):  
                print(f"{UI.C}{k}{UI.RESET} -> {v}")  
            return  
        if len(args) < 2:  
            print("Usage: alias <name> <value>")  
            return  
        name = args[0]  
        value = " ".join(args[1:])  
        self.db.aliases[name] = value  
        self.db.save_aliases()  
        print(f"{UI.G}Alias saved.{UI.RESET}")  
  
    def cmd_unalias(self, args, stdin=None):  
        if not args:  
            print("Usage: unalias <name>")  
            return  
        name = args[0]  
        if name in self.db.aliases:  
            del self.db.aliases[name]  
            self.db.save_aliases()  
            print(f"{UI.Y}Alias removed.{UI.RESET}")  
        else:  
            print(f"{UI.R}unalias: {name} not found{UI.RESET}")  
  
    # --------------------------------------------------------------------------  
    # JOB CONTROL  
    # --------------------------------------------------------------------------  
    def _current_job(self) -> Optional[JobRecord]:  
        return getattr(self._job_local, "job", None)  
  
    def _set_current_job(self, job: Optional[JobRecord]) -> None:  
        self._job_local.job = job  
  
    def _background_worker(self, job_id: int, command: str) -> None:  
        job = self.jobs.get(job_id)  
        self._set_current_job(job)  
        try:  
            status = self.execute_line(command, emit=True)  
            if job and job.stop_event.is_set():  
                self.jobs.finish(job_id, "killed", status, job.output)  
            else:  
                self.jobs.finish(job_id, "done" if status == 0 else "failed", status, job.output)  
        finally:  
            self._set_current_job(None)  
  
    def cmd_jobs(self, args, stdin=None):  
        UI.box("JOBS", UI.C)  
        jobs = self.jobs.all_jobs()  
        if not jobs:  
            print("(none)")  
            return  
        for job in jobs:  
            print(f"[{job.id}] {job.status:<8} {job.kind:<7} {job.command}")  
            if job.exit_code is not None:  
                print(f"     exit={job.exit_code} started={job.created_at}")  
  
    def cmd_fg(self, args, stdin=None):  
        if not args:  
            print("Usage: fg <job_id>")  
            return  
        try:  
            job_id = int(args[0])  
        except ValueError:  
            print("fg: job id must be a number")  
            return  
        job = self.jobs.get(job_id)  
        if not job:  
            print(f"fg: job {args[0]} not found")  
            return  
        print(f"{UI.G}Bringing job {job_id} to foreground...{UI.RESET}")  
        if job.thread:  
            job.thread.join()  
        if job.process and job.process.poll() is None:  
            try:  
                job.process.wait()  
            except Exception:  
                pass  
        if job.output:  
            print(job.output, end="" if job.output.endswith("\n") else "\n")  
  
    def cmd_kill(self, args, stdin=None):  
        if not args:  
            print("Usage: kill <job_id>")  
            return  
        try:  
            job_id = int(args[0])  
        except ValueError:  
            print("kill: job id must be a number")  
            return  
        if self.jobs.kill(job_id):  
            print(f"{UI.Y}Kill signal sent to job {job_id}.{UI.RESET}")  
        else:  
            print(f"kill: job {job_id} not found")  
  
    def cmd_sandbox(self, args, stdin=None):  
        if not args:  
            UI.box("SANDBOX POLICY", UI.M)  
            print(self.sandbox.describe())  
            return  
        sub = args[0].lower()  
        if sub in {"on", "enable"}:  
            self.sandbox.policy.enabled = True  
            print(f"{UI.G}Sandbox enabled.{UI.RESET}")  
        elif sub in {"off", "disable"}:  
            self.sandbox.policy.enabled = False  
            print(f"{UI.Y}Sandbox disabled for this session.{UI.RESET}")  
        elif sub == "status":  
            print(f"Sandbox: {'ON' if self.sandbox.policy.enabled else 'OFF'}")  
        else:  
            print("Usage: sandbox [on|off|status]")  
  
    # --------------------------------------------------------------------------  
    # PYTHON SUPPORT  
    # --------------------------------------------------------------------------  
    def run_python_script(self, script_path: Path, args=None, stdin=None, plugin_name: str = "", unsafe: bool = False):  
        args = args or []  
        try:  
            code = script_path.read_text(encoding="utf-8", errors="ignore")  
            if unsafe or not self.sandbox.policy.enabled:  
                stdout_buf = io.StringIO()  
  
                class _Stdin(io.StringIO):  
                    def isatty(self):  
                        return False  
  
                old_argv = sys.argv[:]  
                old_stdin = sys.stdin  
                try:  
                    sys.argv = [str(script_path), *args]  
                    sys.stdin = _Stdin(stdin or "")  
                    with redirect_stdout(stdout_buf), redirect_stderr(stdout_buf):  
                        exec(compile(code, str(script_path), "exec"), {"__name__": "__main__", "__file__": str(script_path)}, {})  
                finally:  
                    sys.argv = old_argv  
                    sys.stdin = old_stdin  
                output = stdout_buf.getvalue()  
            else:  
                output = self.sandbox.exec_code(code, str(script_path), args, stdin or "")  
            if output:  
                print(output, end="" if output.endswith("\n") else "\n")  
            return output  
        except SystemExit as e:  
            code = e.code if isinstance(e.code, int) else 0  
            if code not in (0, None):  
                print(f"{UI.Y}Python exited {UI.RESET}")  
                print(f"Ex Code: {code}") 
            return ""  
        except Exception as e:  
            label = f"Python plugin '{plugin_name}'" if plugin_name else "Python"  
            print(f"{UI.R}{label} error: {e}{UI.RESET}")  
            return ""  
  
    def compile_python_file(self, file_path: Path):  
        try:  
            pyc = py_compile.compile(str(file_path), cfile=None, doraise=True)  
            print(f"{UI.G}Compiled: {pyc}{UI.RESET}")  
            return pyc  
        except Exception as e:  
            print(f"{UI.R}py compile error: {e}{UI.RESET}")  
            return None  
  
    def cmd_py(self, args, stdin=None):  
        if not args:  
            print("Usage: py run <file.py|code> | py compile <file.py>")  
            return  
        sub = args[0].lower()  
  
        if sub == "compile":  
            if len(args) < 2:  
                print("Usage: py compile <file.py>")  
                return  
            path = Path(args[1])  
            if not path.exists():  
                print(f"{UI.R}File not found: {path}{UI.RESET}")  
                return  
            self.compile_python_file(path)  
            return  
  
        if sub == "run":  
            if len(args) < 2:  
                print("Usage: py run <file.py|code> [args...]")  
                return  
  
            unsafe = False  
            offset = 1  
            if args[1] == "--unsafe":  
                unsafe = True  
                offset = 2  
                if len(args) < 3:  
                    print("Usage: py run --unsafe <file.py|code> [args...]")  
                    return  
  
            target = args[offset]  
            py_args = args[offset + 1:]  
  
            path = Path(target)  
            if path.exists() and path.is_file():  
                self.run_python_script(path, args=py_args, stdin=stdin, unsafe=unsafe)  
                return  
  
            code = " ".join(args[offset:])  
            try:  
                if unsafe or not self.sandbox.policy.enabled:  
                    stdout_buf = io.StringIO()  
  
                    class _Stdin(io.StringIO):  
                        def isatty(self):  
                            return False  
  
                    old_argv = sys.argv[:]  
                    old_stdin = sys.stdin  
                    try:  
                        sys.argv = ["<inline>", *py_args]  
                        sys.stdin = _Stdin(stdin or "")  
                        with redirect_stdout(stdout_buf), redirect_stderr(stdout_buf):  
                            exec(code, {"__name__": "__main__", "__file__": "<inline>", "stdin": stdin, "argv": py_args}, {})  
                    finally:  
                        sys.argv = old_argv  
                        sys.stdin = old_stdin  
                    out = stdout_buf.getvalue()  
                else:  
                    out = self.sandbox.exec_code(code, "<inline>", py_args, stdin or "")  
                if out:  
                    print(out, end="" if out.endswith("\n") else "\n")  
            except Exception as e:  
                print(f"{UI.R}py run error: {e}{UI.RESET}")  
            return  
  
        print("Usage: py run <file.py|code> | py compile <file.py>")  
  
    # --------------------------------------------------------------------------  
    # C SUPPORT  
    # --------------------------------------------------------------------------  
    def build_and_run_c(self, source_path: Path, args=None, stdin=None, plugin_name: str = "", output_override: Optional[Path] = None):  
        args = args or []  
        compiler = detect_compiler()  
        if not compiler:  
            print(f"{UI.R}No C compiler found (gcc/clang/cc/tcc).{UI.RESET}")  
            return ""  
  
        if self.sandbox.policy.enabled and not self.sandbox.path_allowed(source_path):  
            print(f"{UI.R}Sandbox blocked C source outside allowed roots.{UI.RESET}")  
            return ""  
  
        try:  
            with tempfile.TemporaryDirectory(dir=str(self.db.c_build_dir)) as tmpdir:  
                tmpdir_path = Path(tmpdir)  
                output_path = output_override or (tmpdir_path / source_path.stem)  
                if os.name == "nt":  
                    output_path = output_path.with_suffix(".exe")  
                else:  
                    output_path = output_path.with_suffix(".out")  
  
                cmd = [compiler, str(source_path), "-o", str(output_path), "-Wall", "-Wextra", "-O2"]  
                if "clang" in compiler or "gcc" in compiler or "cc" in compiler:  
                    cmd += ["-std=c11"]  
  
                build = subprocess.run(cmd, capture_output=True, text=True, cwd=str(source_path.parent))  
                if build.returncode != 0:  
                    print(f"{UI.R}C build failed:{UI.RESET}")  
                    if build.stdout:  
                        print(build.stdout, end="")  
                    if build.stderr:  
                        print(build.stderr, end="")  
                    return ""  
  
                print(f"{UI.G}Built: {output_path}{UI.RESET}")  
                proc = subprocess.run(  
                    [str(output_path), *args],  
                    input=stdin or "",  
                    capture_output=True,  
                    text=True,  
                    cwd=str(tmpdir_path),  
                )  
                if proc.stdout:  
                    print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")  
                if proc.stderr:  
                    print(f"{UI.R}{proc.stderr}{UI.RESET}", file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")  
                return proc.stdout  
        except Exception as e:  
            label = f"C plugin '{plugin_name}'" if plugin_name else "C"  
            print(f"{UI.R}{label} error: {e}{UI.RESET}")  
            return ""  
  
    def cmd_cextender(self, args, stdin=None):  
        if not args:  
            print("Usage: cextender build <file.c> [-o output] | cextender run <file.c> [args...]")  
            print("Extra: supports gcc/clang/cc/tcc, auto flags -Wall -Wextra -O2 -std=c11")  
            return  
  
        sub = args[0].lower()  
        if sub not in {"build", "run"}:  
            print("Usage: cextender build <file.c> [-o output] | cextender run <file.c> [args...]")  
            return  
  
        if len(args) < 2:  
            print("Usage: cextender build <file.c> [-o output] | cextender run <file.c> [args...]")  
            return  
  
        src = Path(args[1])  
        if not src.exists():  
            print(f"{UI.R}File not found: {src}{UI.RESET}")  
            return  
  
        output = None  
        extra_args = []  
        i = 2  
        while i < len(args):  
            if args[i] == "-o" and i + 1 < len(args):  
                output = Path(args[i + 1])  
                i += 2  
                continue  
            extra_args.append(args[i])  
            i += 1  
  
        if output is None:  
            output = self.db.c_build_dir / src.stem  
            if os.name == "nt":  
                output = output.with_suffix(".exe")  
            else:  
                output = output.with_suffix(".out")  
  
        if sub == "build":  
            self.build_and_run_c(src, args=[], stdin=stdin, output_override=output)  
        else:  
            self.build_and_run_c(src, args=extra_args, stdin=stdin, output_override=output)  
  
    # --------------------------------------------------------------------------  
    # PLUGIN SYSTEM  
    # --------------------------------------------------------------------------  
    def cmd_install(self, args, stdin=None):  
        if len(args) < 1:  
            print("Usage: install json|py|c ...")  
            print("Examples:")  
            print('  install json tools "Basic Tools" \'["gen","scan"]\'')  
            print('  install py hello "Say hello" ./hello.py')  
            print('  install c demo "C demo" ./demo.c')  
            return  
  
        kind = args[0].lower()  
  
        if kind == "json":  
            if len(args) < 4:  
                print('Usage: install json <plugin_name> <description> <commands_json_list>')  
                print('Example: install json tools "Basic Tools" \'["gen","scan"]\'')  
                return  
            name, desc, cmd_json = args[1], args[2], args[3]  
            try:  
                cmds = json.loads(cmd_json.replace("'", '"'))  
                self.db.mods[name] = {  
                    "type": "json",  
                    "description": desc,  
                    "commands": cmds,  
                    "date": now_str(),  
                }  
                self.db.save_mods()  
                self.boot_plugins()  
                print(f"{UI.G}JSON plugin '{name}' installed and loaded.{UI.RESET}")  
            except Exception as e:  
                print(f"{UI.R}Installation failed: {e}{UI.RESET}")  
            return  
  
        if kind == "py":  
            if len(args) < 4:  
                print("Usage: install py <plugin_name> <description> <script.py>")  
                return  
            name, desc, script = args[1], args[2], Path(args[3])  
            if not script.exists():  
                print(f"{UI.R}File not found: {script}{UI.RESET}")  
                return  
            try:  
                dst = self.db.py_plugins_dir / f"{name}.py"  
                shutil.copy2(script, dst)  
                self.compile_python_file(dst)  
                self.db.mods[name] = {  
                    "type": "py",  
                    "description": desc,  
                    "commands": [name],  
                    "script": str(dst),  
                    "date": now_str(),  
                }  
                self.db.save_mods()  
                self.boot_plugins()  
                print(f"{UI.G}Python plugin '{name}' installed and loaded.{UI.RESET}")  
            except Exception as e:  
                print(f"{UI.R}Installation failed: {e}{UI.RESET}")  
            return  
  
        if kind == "c":  
            if len(args) < 4:  
                print("Usage: install c <plugin_name> <description> <source.c>")  
                return  
            name, desc, source = args[1], args[2], Path(args[3])  
            if not source.exists():  
                print(f"{UI.R}File not found: {source}{UI.RESET}")  
                return  
            try:  
                dst = self.db.c_build_dir / f"{name}.c"  
                shutil.copy2(source, dst)  
                self.db.mods[name] = {  
                    "type": "c",  
                    "description": desc,  
                    "commands": [name],  
                    "source": str(dst),  
                    "date": now_str(),  
                }  
                self.db.save_mods()  
                self.boot_plugins()  
                print(f"{UI.G}C plugin '{name}' installed and loaded.{UI.RESET}")  
            except Exception as e:  
                print(f"{UI.R}Installation failed: {e}{UI.RESET}")  
            return  
  
        print("Usage: install json|py|c ...")  
  
    def cmd_plugins(self, args, stdin=None):  
        UI.box("INSTALLED PLUGINS", UI.Y)  
        if not self.db.mods:  
            print("(none)")  
            return  
        for k, v in self.db.mods.items():  
            ptype = v.get("type", "json")  
            print(f"{UI.C}[{k}]{UI.RESET} ({ptype}) - {v.get('description', '-')}")  
            cmds = v.get("commands", [])  
            print(f"  Commands: {', '.join(cmds) if cmds else '-'}")  
            if ptype in {"py", "c"}:  
                path_key = "script" if ptype == "py" else "source"  
                print(f"  Path: {v.get(path_key, '-')}")  
            print(f"  Date: {v.get('date', '-')}")  
            print()  
  
    # --------------------------------------------------------------------------  
    # EXPANSION / TOKENIZE / BLOCK PARSING  
    # --------------------------------------------------------------------------  
    def expand_input(self, text: str) -> str:  
        """
        Replaces $VAR with its real value from memory.
        """
        for k in sorted(self.db.vars.keys(), key=len, reverse=True):  
            text = text.replace(f"${k}", str(self.db.vars[k]))  
        return text  
  
    def resolve_alias(self, line: str) -> str:  
        """
        Expands user-defined aliases inline.
        """
        try:  
            parts = shlex.split(line)  
        except Exception:  
            return line  
        if not parts:  
            return line  
        head = parts[0]  
        if head in self.db.aliases:  
            aliased = self.db.aliases[head]  
            rest = " ".join(shlex.quote(p) for p in parts[1:])  
            return f"{aliased} {rest}".strip()  
        return line  
  
    def tokenize_shell(self, line: str) -> list[str]:  
        """
        Secure POSIX shlex tokenization.
        """
        lex = shlex.shlex(line, posix=True, punctuation_chars="|&;<>:()")  
        lex.whitespace_split = True  
        return list(lex)  
  
    def parse_redirections(self, tokens: list[str]):  
        """
        Parses `>` `>>` `<` and returns clean tokens and targets.
        """
        clean = []  
        stdin_file = None  
        stdout_file = None  
        stdout_append = False  
        stderr_file = None  
        stderr_append = False  
  
        i = 0  
        while i < len(tokens):  
            t = tokens[i]  
            if t == "<" and i + 1 < len(tokens):  
                stdin_file = tokens[i + 1]  
                i += 2  
                continue  
            if t in {">", ">>"} and i + 1 < len(tokens):  
                stdout_file = tokens[i + 1]  
                stdout_append = (t == ">>")  
                i += 2  
                continue  
            if t.isdigit() and i + 2 < len(tokens) and tokens[i + 1] in {">", ">>"}:  
                fd = int(t)  
                op = tokens[i + 1]  
                target = tokens[i + 2]  
                if fd == 1:  
                    stdout_file = target  
                    stdout_append = (op == ">>")  
                elif fd == 2:  
                    stderr_file = target  
                    stderr_append = (op == ">>")  
                i += 3  
                continue  
            clean.append(t)  
            i += 1  
  
        return clean, stdin_file, stdout_file, stdout_append, stderr_file, stderr_append  
  
    def _split_condition_blocks(self, tokens: list[str]) -> list[list[str]]:  
        parts: list[list[str]] = []  
        current: list[str] = []  
        depth = 0  
        for tok in tokens:  
            if tok == ";" and depth == 0:  
                if current:  
                    parts.append(current)  
                current = []  
                continue  
            current.append(tok)  
            if tok in {"if", "try", "do"}:  
                depth += 1  
            elif tok in {"endif", "pass"} and depth > 0:  
                depth = max(0, depth - 1)  
        if current:  
            parts.append(current)  
        return parts  
  
    def _parse_block(self, lines: list[str], start: int = 0):  
        """
        Parses native MSHELL language blocks (if/try/do).
        """
        if start >= len(lines):  
            return None, start  
        head = lines[start].strip()  
        if not head:  
            return None, start + 1  
  
        if head.startswith("if "):  
            return self._parse_if(lines, start)  
        if head == "try":  
            return self._parse_try(lines, start)  
        if head == "do":  
            return self._parse_do_until(lines, start)  
        return None, start  
  
    def _parse_if(self, lines: list[str], start: int):  
        block = IfBlock()  
        i = start  
        line = lines[i].strip()  
        cond = line[3:].strip()  
        block.branches.append(IfBranch(kind="if", condition=cond, body=[]))  
        i += 1  
        active = block.branches[-1]  
        while i < len(lines):  
            raw = lines[i].strip()  
            if raw == "endif":  
                return block, i + 1  
            if raw.startswith("elif "):  
                active = IfBranch(kind="elif", condition=raw[5:].strip(), body=[])  
                block.branches.append(active)  
                i += 1  
                continue  
            if raw == "else":  
                active = IfBranch(kind="else", condition="", body=[])  
                block.branches.append(active)  
                i += 1  
                continue  
            active.body.append(lines[i])  
            i += 1  
        raise ValueError("Missing endif")  
  
    def _parse_try(self, lines: list[str], start: int):  
        block = TryBlock()  
        i = start + 1  
        active = block.try_body  
        mode = "try"  
        while i < len(lines):  
            raw = lines[i].strip()  
            if raw == "exc":  
                mode = "exc"  
                active = block.exc_body  
                i += 1  
                continue  
            if raw == "pass":  
                mode = "pass"  
                active = block.pass_body  
                i += 1  
                continue  
            if raw == "endtry":  
                return block, i + 1  
            active.append(lines[i])  
            i += 1  
        raise ValueError("Missing endtry")  
  
    def _parse_do_until(self, lines: list[str], start: int):  
        block = DoUntilBlock()  
        i = start + 1  
        while i < len(lines):  
            raw = lines[i].strip()  
            if raw.startswith("until "):  
                block.condition = raw[6:].strip()  
                return block, i + 1  
            if raw == "stop":  
                block.condition = "1"  
                return block, i + 1  
            block.body.append(lines[i])  
            i += 1  
        raise ValueError("Missing until or stop")  
  
    def _split_statements(self, line: str) -> list[str]:  
        return [s.strip() for s in line.split(";") if s.strip()]  
  
    def _eval_condition(self, condition: str, stdin: str = "") -> bool:  
        """
        Evaluates boolean statements dynamically.
        """
        condition = condition.strip()  
        if not condition:  
            return False  
        if condition in {"true", "True", "1", "yes", "on"}:  
            return True  
        if condition in {"false", "False", "0", "no", "off"}:  
            return False  
  
        expanded = self.expand_input(condition)  
        expanded = self.resolve_alias(expanded)  
  
        try:  
            if re.fullmatch(r"[0-9\s\+\-\*\/\%\(\)\.]+", expanded):  
                return SafeCalc.eval(expanded) != 0  
        except Exception:  
            pass  
  
        try:  
            glb = {"__builtins__": {"True": True, "False": False, "len": len, "int": int, "float": float, "str": str, "abs": abs}}  
            return bool(eval(expanded, glb, {}))  
        except Exception:  
            return bool(expanded)  
  
    def _capture_command_output(self, command: str) -> tuple[str, str, int]:  
        out_buf = io.StringIO()  
        err_buf = io.StringIO()  
        with redirect_stdout(out_buf), redirect_stderr(err_buf):  
            rc = self.execute_line(command, emit=False)  
        return out_buf.getvalue(), err_buf.getvalue(), rc  
  
    def _run_block_lines(self, lines: list[str], emit: bool = True) -> int:  
        i = 0  
        last_rc = 0  
        while i < len(lines):  
            block, new_i = self._parse_block(lines, i)  
            if block is None:  
                last_rc = self.execute_line(lines[i], emit=emit)  
                i += 1  
                continue  
  
            if isinstance(block, IfBlock):  
                last_rc = self._exec_if_block(block, emit=emit)  
                i = new_i  
                continue  
  
            if isinstance(block, TryBlock):  
                last_rc = self._exec_try_block(block, emit=emit)  
                i = new_i  
                continue  
  
            if isinstance(block, DoUntilBlock):  
                last_rc = self._exec_do_until_block(block, emit=emit)  
                i = new_i  
                continue  
  
            i = new_i  
        return last_rc  
  
    def _exec_if_block(self, block: IfBlock, emit: bool = True) -> int:  
        for branch in block.branches:  
            if branch.kind == "else" or self._eval_condition(branch.condition):  
                return self._run_block_lines(branch.body, emit=emit)  
        return 0  
  
    def _exec_try_block(self, block: TryBlock, emit: bool = True) -> int:  
        try:  
            return self._run_block_lines(block.try_body, emit=emit)  
        except Exception as e:  
            if block.exc_body:  
                self.db.vars["EXC"] = str(e)  
                return self._run_block_lines(block.exc_body, emit=emit)  
            if block.pass_body:  
                return self._run_block_lines(block.pass_body, emit=emit)  
            if emit:  
                print(f"{UI.R}try error: {e}{UI.RESET}")  
            return 1  
  
    def _exec_do_until_block(self, block: DoUntilBlock, emit: bool = True) -> int:  
        last_rc = 0  
        while True:  
            last_rc = self._run_block_lines(block.body, emit=emit)  
            if block.condition == "1":  
                return last_rc  
            if self._eval_condition(block.condition):  
                return last_rc  
        return last_rc  
  
    # --------------------------------------------------------------------------  
    # EXECUTION ENGINE & ASSIGNMENT HANDLER
    # --------------------------------------------------------------------------  
    def _handle_assignment(self, line: str) -> bool:
        """
        Parses inline variable assignment: A = 10, or A = see B
        """
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$', line)
        if not match:
            return False
            
        var_name = match.group(1).strip()
        rhs = match.group(2).strip()

        if not rhs:
            self.db.vars[var_name] = ""
            self.db.save_vars()
            return True

        if rhs.lower().startswith("see "):
            target_var = rhs[4:].strip()
            if target_var.startswith('$'):
                target_var = target_var[1:]
            val = self.db.vars.get(target_var, "")
            self.db.vars[var_name] = val
        else:
            rhs_expanded = self.expand_input(rhs)
            self.db.vars[var_name] = rhs_expanded

        self.db.save_vars()
        return True

    def run_command(self, cmd_parts, stdin=None, emit=True):  
        """
        Executes a single command sequence.
        """
        if not cmd_parts:  
            return "", "", 0  
  
        cmd_name = cmd_parts[0]  
        args = cmd_parts[1:]  
  
        if cmd_name in self.builtins:  
            try:  
                stdout_buf = io.StringIO()  
                stderr_buf = io.StringIO()  
                with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):  
                    result = self.builtins[cmd_name](args, stdin=stdin)  
                stdout = stdout_buf.getvalue()  
                stderr = stderr_buf.getvalue()  
                if isinstance(result, str) and not stdout:  
                    stdout = result  
                if emit:  
                    if stdout:  
                        print(stdout, end="" if stdout.endswith("\n") else "\n")  
                    if stderr:  
                        print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)  
                return stdout, stderr, 0  
            except Exception as e:  
                msg = f"{cmd_name}: {e}"  
                if emit:  
                    print(f"{UI.R}{msg}{UI.RESET}")  
                return "", msg, 1  
  
        try:  
            proc = subprocess.Popen(  
                cmd_parts,  
                stdin=subprocess.PIPE,  
                stdout=subprocess.PIPE,  
                stderr=subprocess.PIPE,  
                text=True,  
                shell=False,  
            )  
            current_job = self._current_job()  
            if current_job:  
                self.jobs.attach_process(current_job.id, proc)  
            out, err = proc.communicate(input=stdin if stdin is not None else None)  
            rc = proc.returncode or 0  
            if emit:  
                if out:  
                    print(out, end="" if out.endswith("\n") else "\n")  
                if err:  
                    print(f"{UI.R}{err}{UI.RESET}", end="" if err.endswith("\n") else "\n", file=sys.stderr)  
            return out or "", err or "", rc  
        except FileNotFoundError:  
            if emit:  
                self.suggest(cmd_name)  
            return "", f"command not found: {cmd_name}", 127  
        except Exception as e:  
            if emit:  
                print(f"{UI.R}Execution error: {e}{UI.RESET}")  
            return "", str(e), 1  
  
    def suggest(self, cmd: str):  
        print(f"{UI.R}msh: command not found: {cmd}{UI.RESET}")  
        matches = [b for b in self.builtins.keys() if b.startswith(cmd[:2])]  
        if matches:  
            print(f"{UI.Y}Did you mean: {', '.join(sorted(matches))}?{UI.RESET}")  
  
    def execute_pipeline(self, tokens: list[str], emit=True) -> int:  
        stages: list[list[str]] = []  
        current: list[str] = []  
        for tok in tokens:  
            if tok == "|":  
                if current:  
                    stages.append(current)  
                current = []  
            else:  
                current.append(tok)  
        if current:  
            stages.append(current)  
  
        stdin_text = None  
        last_rc = 0  
  
        for idx, stage in enumerate(stages):  
            parts, stdin_file, stdout_file, stdout_append, stderr_file, stderr_append = self.parse_redirections(stage)  
            if not parts:  
                continue  
            if stdin_file:  
                try:  
                    stdin_text = Path(stdin_file).read_text(encoding="utf-8", errors="ignore")  
                except Exception as e:  
                    if emit:  
                        print(f"{UI.R}input redirect error: {e}{UI.RESET}")  
                    return 1  
  
            stage_emit = emit and idx == len(stages) - 1 and stdout_file is None and stderr_file is None  
            out, err, rc = self.run_command(parts, stdin=stdin_text, emit=stage_emit)  
            last_rc = rc  
            stdin_text = out  
  
            if stdout_file:  
                target = Path(stdout_file)  
                mode = "a" if stdout_append else "w"  
                try:  
                    target.parent.mkdir(parents=True, exist_ok=True)  
                    with target.open(mode, encoding="utf-8") as f:  
                        f.write(out)  
                except Exception as e:  
                    if emit:  
                        print(f"{UI.R}redirect error: {e}{UI.RESET}")  
                    last_rc = 1  
            if stderr_file:  
                target = Path(stderr_file)  
                mode = "a" if stderr_append else "w"  
                try:  
                    target.parent.mkdir(parents=True, exist_ok=True)  
                    with target.open(mode, encoding="utf-8") as f:  
                        f.write(err)  
                except Exception as e:  
                    if emit:  
                        print(f"{UI.R}stderr redirect error: {e}{UI.RESET}")  
                    last_rc = 1  
  
        return last_rc  
  
    def _parse_flat_segments(self, tokens: list[str]) -> list[tuple[str | None, list[str]]]:  
        segments: list[tuple[str | None, list[str]]] = []  
        current: list[str] = []  
        op: str | None = None  
        i = 0  
        while i < len(tokens):  
            tok = tokens[i]  
            if tok in {";", "&&", "||"}:  
                if current:  
                    segments.append((op, current))  
                current = []  
                op = tok  
            else:  
                current.append(tok)  
            i += 1  
        if current:  
            segments.append((op, current))  
        return segments  
  
    def execute_line(self, line: str, emit=True) -> int:  
        """
        Compiles and routes an entire single line of command.
        """
        line = line.strip()  
        if not line:  
            return 0  

        # Check for direct variable assignment A = B before anything else
        if not line.startswith("if ") and not line.startswith("set "):
            if self._handle_assignment(line):
                return 0
  
        line = self.expand_input(line)  
        line = self.resolve_alias(line)  
  
        try:  
            tokens = self.tokenize_shell(line)  
        except Exception as e:  
            if emit:  
                print(f"{UI.R}Parser error: {e}{UI.RESET}")  
            return 1  
  
        status = 0  
        current: list[str] = []  
        pending_op = None  
  
        def should_run(op, last_status):  
            if op is None or op == ";":  
                return True  
            if op == "&&":  
                return last_status == 0  
            if op == "||":  
                return last_status != 0  
            return True  
  
        i = 0  
        while i <= len(tokens):  
            tok = tokens[i] if i < len(tokens) else ";"  
            if tok in {";", "&&", "||"} or i == len(tokens):  
                if current:  
                    if should_run(pending_op, status):  
                        status = self.execute_pipeline(current, emit=emit)  
                    current = []  
                pending_op = tok if i < len(tokens) else None  
            else:  
                current.append(tok)  
            i += 1  
        return status  
  
    def process_block_text(self, text: str, emit: bool = True) -> int:  
        lines = [ln.rstrip("\n") for ln in text.splitlines()]  
        return self._run_block_lines(lines, emit=emit)  
  
    def process_line(self, line: str):  
        """
        The absolute entry point for user shell strings.
        """
        line = line.rstrip("\n")  
        if not line.strip():  
            return  
  
        self.db.log_history(line)  
  
        # Background one-liner support  
        try:  
            tokens = self.tokenize_shell(line)  
        except Exception:  
            tokens = []  
  
        if tokens and tokens[-1] == "&":  
            background_line = line.rsplit("&", 1)[0].rstrip()  
            job = self.jobs.create_thread_job(background_line)  
  
            def _target():  
                self._background_worker(job.id, background_line)  
  
            thread = threading.Thread(target=_target, daemon=True)  
            job.thread = thread  
            thread.start()  
            print(f"{UI.G}[job {job.id}] started in background{UI.RESET}")  
            return  
  
        # Block syntax support when line starts with block keyword  
        head = line.strip().split(maxsplit=1)[0].lower() if line.strip() else ""  
        if head in {"if", "try", "do"}:  
            self._run_inline_block(line)  
            return  
  
        self.execute_line(line, emit=True)  
  
    def _run_inline_block(self, first_line: str):  
        """
        Reads input interactively to complete control-flow nodes.
        """
        lines = [first_line]  
        head = first_line.strip().split(maxsplit=1)[0].lower()  
        if head == "if":  
            while True:  
                nxt = input("... ")  
                lines.append(nxt)  
                if nxt.strip() == "endif":  
                    break  
            self.process_block_text("\n".join(lines), emit=True)  
            return  
  
        if head == "try":  
            while True:  
                nxt = input("... ")  
                lines.append(nxt)  
                if nxt.strip() == "endtry":  
                    break  
            self.process_block_text("\n".join(lines), emit=True)  
            return  
  
        if head == "do":  
            while True:  
                nxt = input("... ")  
                lines.append(nxt)  
                if nxt.strip().startswith("until ") or nxt.strip() == "stop":  
                    break  
            self.process_block_text("\n".join(lines), emit=True)  
            return  
  
    def run_script_text(self, text: str, emit: bool = True) -> int:  
        """Run a text script that may contain block constructs."""  
        return self.process_block_text(text, emit=emit)  
  
  
# ==============================================================================  
# MAIN BOOTSTRAP  
# ==============================================================================  
def main():  
    shell = MShell()  
  
    try:  
        os.system("cls" if os.name == "nt" else "clear")  
    except Exception:  
        pass  
  
    print(UI.BOLD + UI.C + "+" + "=" * 60 + "+")  
    print("|" + "mshell v0.25.0".center(60) + "|")  
    print("|" + "Custom Shell for Louis - Python + C Workbench".center(60) + "|")  
    print("|" + "Persistent Vars | SysMon | C Extender | RAF Sim".center(60) + "|")  
    print("+" + "=" * 60 + "+" + UI.RESET)  
    print(f"{UI.DIM}Type 'help' for commands. Data path: {shell.db.config_dir}{UI.RESET}\n")  
  
    while shell.is_running:  
        try:  
            user = shell.db.vars.get("USER", "louis")  
            path = os.getcwd().replace(os.path.expanduser("~"), "~")  
            prompt = f"{UI.G}{user}{UI.RESET}:{UI.B}{path}{UI.RESET}$ "  
            line = input(prompt)  
            shell.process_line(line)  
        except KeyboardInterrupt:  
            print(f"\n{UI.Y}Interrupt received. Use 'exit' to logout.{UI.RESET}")  
        except EOFError:  
            shell.cmd_exit([])  
            break  
        except Exception as e:  
            print(f"{UI.R}Critical Shell Error: {e}{UI.RESET}")  
  
  
if __name__ == "__main__":  
    main()  
    