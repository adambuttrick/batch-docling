import os
import sys
import signal
import time
import threading
from typing import Optional
from .config import get_config
from .watcher import get_watcher


class DaemonService:
    def __init__(self):
        self.config = get_config()
        self.pid_file = self.config.get("daemon", "daemon_pid_file", "daemon.pid")
        self.shutdown_timeout = self.config.get("daemon", "shutdown_timeout", 30)
        self.watcher = None
        self.watcher_thread = None
        self.running = False
    
    def _write_pid(self) -> None:
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
    
    def _read_pid(self) -> Optional[int]:
        if not os.path.exists(self.pid_file):
            return None
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None
    
    def _remove_pid(self) -> None:
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
    
    def _is_process_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def _signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}. Initiating graceful shutdown...")
        self.stop()
        sys.exit(0)
    
    def start(self) -> None:
        existing_pid = self._read_pid()
        if existing_pid and self._is_process_running(existing_pid):
            print(f"Daemon already running with PID {existing_pid}")
            sys.exit(1)
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self._write_pid()
        self.running = True
        print(f"Starting daemon service (PID: {os.getpid()})")
        
        self.watcher = get_watcher()
        self.watcher_thread = threading.Thread(target=self.watcher.start_watching)
        self.watcher_thread.daemon = True
        self.watcher_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self) -> None:
        existing_pid = self._read_pid()
        if not existing_pid:
            print("No daemon PID file found")
            return
        
        if existing_pid == os.getpid():
            self._perform_shutdown()
        else:
            if self._is_process_running(existing_pid):
                print(f"Stopping daemon (PID: {existing_pid})")
                try:
                    os.kill(existing_pid, signal.SIGTERM)
                    timeout = time.time() + self.shutdown_timeout
                    while time.time() < timeout:
                        if not self._is_process_running(existing_pid):
                            print("Daemon stopped successfully")
                            self._remove_pid()
                            return
                        time.sleep(0.5)
                    print(f"Daemon did not stop within {self.shutdown_timeout} seconds")
                except ProcessLookupError:
                    print("Daemon process not found")
            else:
                print("Daemon is not running")
            self._remove_pid()
    
    def _perform_shutdown(self) -> None:
        self.running = False
        if self.watcher:
            print("Stopping directory watcher...")
            self.watcher.stop_watching()
            if self.watcher_thread:
                self.watcher_thread.join(timeout=5)
        self._remove_pid()
        print("Daemon shutdown complete")
    
    def status(self) -> None:
        existing_pid = self._read_pid()
        if not existing_pid:
            print("Daemon is not running (no PID file)")
            return
        
        if self._is_process_running(existing_pid):
            print(f"Daemon is running (PID: {existing_pid})")
        else:
            print(f"Daemon is not running (stale PID file: {existing_pid})")
            self._remove_pid()
    
    def restart(self) -> None:
        print("Restarting daemon...")
        self.stop()
        time.sleep(2)
        self.start()


def main():
    if len(sys.argv) < 2:
        print("Usage: python daemon.py [start|stop|status|restart] [config_file]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if len(sys.argv) > 2:
        config_file = sys.argv[2]
        if os.path.exists(config_file):
            from .config import reload_config
            reload_config(config_file)
            print(f"Using config file: {config_file}")
        else:
            print(f"Config file not found: {config_file}")
            sys.exit(1)
    elif os.path.exists("config.local.yaml"):
        from .config import reload_config
        reload_config("config.local.yaml")
        print("Using config file: config.local.yaml")
    
    daemon = DaemonService()
    
    if command == "start":
        daemon.start()
    elif command == "stop":
        daemon.stop()
    elif command == "status":
        daemon.status()
    elif command == "restart":
        daemon.restart()
    else:
        print(f"Unknown command: {command}\nUsage: python daemon.py [start|stop|status|restart]")
        sys.exit(1)

if __name__ == "__main__":
    main()