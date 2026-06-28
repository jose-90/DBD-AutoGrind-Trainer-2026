import ctypes
import re
import asyncio
import logging
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass
import pymem
import pymem.process
import psutil
import numpy as np
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

log = logging.getLogger(__name__)

@dataclass
class PointerPath:
    base_address: int
    offsets: List[int]

class ProcessWatcher:
    """Watches the target process and re-attaches if it restarts."""
    def __init__(self, process_name: str, on_attach, on_detach):
        self.process_name = process_name
        self.on_attach = on_attach
        self.on_detach = on_detach
        self.running = False

    async def watch(self):
        self.running = True
        attached_pid = None
        while self.running:
            pid = self._find_process()
            if pid and pid != attached_pid:
                attached_pid = pid
                log.info(f"Process {self.process_name} found (PID {pid})")
                await self.on_attach(pid)
            elif not pid and attached_pid:
                log.warning(f"Process {self.process_name} lost")
                attached_pid = None
                await self.on_detach()
            await asyncio.sleep(2)

    def _find_process(self) -> Optional[int]:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and self.process_name.lower() in proc.info['name'].lower():
                return proc.info['pid']
        return None

    def stop(self):
        self.running = False

class MemoryManager:
    """Sophisticated memory interface with pattern scanning and pointer caching."""

    def __init__(self):
        self.pm: Optional[pymem.Pymem] = None
        self.base_address: int = 0
        self.cached_pointers: Dict[str, int] = {}
        self.attached = False

    def attach(self, process_name: str = "DeadByDaylight.exe") -> bool:
        try:
            self.pm = pymem.Pymem(process_name)
            self.base_address = pymem.process.module_from_name(
                self.pm.process_handle, process_name
            ).lpBaseOfDll
            self.attached = True
            log.info(f"Attached to {process_name} at 0x{self.base_address:X}")
            return True
        except Exception as e:
            log.error(f"Failed to attach: {e}")
            return False

    def read_int(self, address: int) -> int:
        return self.pm.read_int(address)

    def write_int(self, address: int, value: int) -> None:
        self.pm.write_int(address, value)

    def read_float(self, address: int) -> float:
        return self.pm.read_float(address)

    def write_float(self, address: int, value: float) -> None:
        self.pm.write_float(address, value)

    def read_bytes(self, address: int, size: int) -> bytes:
        return self.pm.read_bytes(address, size)

    def write_bytes(self, address: int, data: bytes) -> None:
        self.pm.write_bytes(address, data, len(data))

    def pattern_scan(self, pattern: str, module_base: int, module_size: int) -> Optional[int]:
        """AOB scan using numpy for ultra‑fast searching."""
        pattern_bytes, mask = self._parse_pattern(pattern)
        buffer = (ctypes.c_char * module_size)()
        ctypes.windll.kernel32.ReadProcessMemory(
            self.pm.process_handle,
            ctypes.c_void_p(module_base),
            buffer,
            module_size,
            None
        )
        data = np.frombuffer(buffer, dtype=np.uint8)
        # Convert pattern and mask to numpy arrays
        pat_arr = np.array(pattern_bytes, dtype=np.uint8)
        mask_arr = np.array(mask, dtype=np.bool_)

        # Sliding window search
        for i in range(len(data) - len(pat_arr)):
            window = data[i:i+len(pat_arr)]
            if np.all((window & mask_arr) == (pat_arr & mask_arr)):
                return module_base + i
        return None

    @staticmethod
    def _parse_pattern(pattern: str) -> Tuple[List[int], List[bool]]:
        """Convert IDA‑style pattern to bytes and mask."""
        bytes_list = []
        mask_list = []
        for byte_str in pattern.split():
            if byte_str == "?" or byte_str == "??":
                bytes_list.append(0x00)
                mask_list.append(False)
            else:
                bytes_list.append(int(byte_str, 16))
                mask_list.append(True)
        return bytes_list, mask_list

    def resolve_pointer(self, base: int, offsets: List[int]) -> int:
        address = base
        for offset in offsets:
            address = self.read_int(address) + offset
        return address

    def follow_pointer_path(self, path: PointerPath) -> int:
        """Resolve and cache pointer chains."""
        key = f"{path.base_address:x}-{path.offsets}"
        if key in self.cached_pointers:
            return self.cached_pointers[key]
        addr = self.resolve_pointer(path.base_address, path.offsets)
        self.cached_pointers[key] = addr
        return addr

    def invalidate_cache(self):
        self.cached_pointers.clear()

    def detach(self):
        self.attached = False
        self.pm = None
