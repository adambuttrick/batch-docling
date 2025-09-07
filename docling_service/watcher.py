import os
import json
import time
from pathlib import Path
from typing import List, Set, Optional, Dict, Any

from .config import get_config
from .app_controller import AppController
from .batch_manager import get_batch_manager


class DirectoryWatcher:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.config = get_config()
            self.app_controller = AppController()
            self.batch_manager = get_batch_manager()
            self.watch_directory = self.config.get("daemon", "watch_directory", "./watch_input")
            self.scan_interval = self.config.get("daemon", "scan_interval", 10)
            self.processed_dirs_file = self.config.get("daemon", "processed_dirs_file", ".processed_directories.json")
            self.output_base_dir = self.config.get("daemon", "output_base_dir", "./watch_output")
            self.processed_directories = self._load_processed_directories()
            self.running = False
            self.initialized = True
    
    def _load_processed_directories(self) -> Set[str]:
        if not os.path.exists(self.processed_dirs_file):
            return set()
        
        try:
            with open(self.processed_dirs_file, 'r') as f:
                data = json.load(f)
                return set(data.get("processed", []))
        except (json.JSONDecodeError, IOError):
            return set()
    
    def _save_processed_directories(self) -> None:
        try:
            with open(self.processed_dirs_file, 'w') as f:
                json.dump({"processed": list(self.processed_directories)}, f)
        except IOError as e:
            print(f"Failed to save processed directories: {e}")
    
    def _find_pdf_files(self, directory: str) -> List[str]:
        pdf_files = []
        try:
            for file in os.listdir(directory):
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(directory, file))
        except OSError as e:
            print(f"Error scanning directory {directory}: {e}")
        return pdf_files
    
    def _scan_for_new_directories(self) -> List[str]:
        if not os.path.exists(self.watch_directory):
            os.makedirs(self.watch_directory, exist_ok=True)
            return []
        
        new_directories = []
        try:
            for item in os.listdir(self.watch_directory):
                item_path = os.path.join(self.watch_directory, item)
                if os.path.isdir(item_path):
                    dir_key = os.path.abspath(item_path)
                    if dir_key not in self.processed_directories:
                        pdf_files = self._find_pdf_files(item_path)
                        if pdf_files:
                            new_directories.append(item_path)
        except OSError as e:
            print(f"Error scanning watch directory: {e}")
        
        return new_directories
    
    def _process_directory(self, directory: str) -> Dict[str, Any]:
        dir_name = os.path.basename(directory)
        output_dir = os.path.join(self.output_base_dir, dir_name)
        os.makedirs(output_dir, exist_ok=True)
        
        result = {"directory": directory, "status": "failed", "batch_id": None}
        
        try:
            batch_result = self.app_controller.process_batch(
                input_dir=directory,
                output_dir=output_dir
            )
            result["status"] = "processing"
            result["batch_id"] = batch_result.get("batch_id")
            result["total_files"] = batch_result.get("total_files")
        except Exception as e:
            print(f"Failed to process directory {directory}: {e}")
            result["error"] = str(e)
        finally:
            dir_key = os.path.abspath(directory)
            self.processed_directories.add(dir_key)
            self._save_processed_directories()
        
        return result
    
    def start_watching(self) -> None:
        self.running = True
        print(f"Starting directory watcher on: {self.watch_directory}")
        print(f"Scan interval: {self.scan_interval} seconds")
        
        while self.running:
            new_directories = self._scan_for_new_directories()
            
            for directory in new_directories:
                print(f"Found new directory with PDFs: {directory}")
                result = self._process_directory(directory)
                
                if result["status"] == "processing":
                    print(f"Batch {result.get('batch_id')} started with {result.get('total_files')} files")
                else:
                    print(f"Failed to process {directory}: {result.get('error', 'Unknown error')}")
            
            time.sleep(self.scan_interval)
    
    def stop_watching(self) -> None:
        self.running = False
        print("Stopping directory watcher")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "watch_directory": self.watch_directory,
            "processed_count": len(self.processed_directories),
            "scan_interval": self.scan_interval
        }
    
    def reset_processed_directories(self) -> None:
        self.processed_directories.clear()
        self._save_processed_directories()
        print("Processed directories list has been reset")


def get_watcher() -> DirectoryWatcher:
    return DirectoryWatcher()