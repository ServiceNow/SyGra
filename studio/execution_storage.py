"""
Scalable Execution Storage for SyGra Studio.

This module provides a scalable, per-run storage architecture that:
- Stores each execution in its own file (not one monolithic JSON)
- Maintains a lightweight index for fast listing/filtering
- References output files instead of duplicating data
- Supports pagination for UI scalability
- Is designed to be extensible for future multi-user support

Directory Structure:
    studio/
    └── .executions/
        ├── index.json              # Lightweight index (metadata only)
        └── runs/
            └── {execution_id}.json # Full execution data per run

The index file only contains essential metadata for listing:
- id, workflow_id, workflow_name, status, started_at, completed_at, duration_ms

Full execution data (including logs, node_states, etc.) is stored per-run
and loaded on demand when viewing a specific execution.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from threading import Lock
import fcntl

from studio.models import (
    ExecutionStatus,
    NodeExecutionState,
    WorkflowExecution,
)


# Storage version for migration support
STORAGE_VERSION = "2.0"

# Maximum runs to keep in index (for memory efficiency)
# Older runs are still accessible but not in the quick index
MAX_INDEX_ENTRIES = 10000


class ExecutionIndex:
    """Lightweight execution metadata for index file."""

    def __init__(
        self,
        id: str,
        workflow_id: str,
        workflow_name: str,
        status: str,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
    ):
        self.id = id
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.status = status
        self.started_at = started_at
        self.completed_at = completed_at
        self.duration_ms = duration_ms
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionIndex":
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            workflow_name=data["workflow_name"],
            status=data["status"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms"),
            error=data.get("error"),
        )

    @classmethod
    def from_execution(cls, execution: WorkflowExecution) -> "ExecutionIndex":
        """Create index entry from full execution."""
        return cls(
            id=execution.id,
            workflow_id=execution.workflow_id,
            workflow_name=execution.workflow_name,
            status=execution.status.value if hasattr(execution.status, 'value') else execution.status,
            started_at=execution.started_at.isoformat() if execution.started_at else None,
            completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
            duration_ms=execution.duration_ms,
            error=execution.error,
        )


class ExecutionStorage:
    """
    Scalable execution storage with per-run files and lightweight index.

    Thread-safe with file locking for concurrent access.
    Designed to be extensible for future multi-user support.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize execution storage.

        Args:
            base_dir: Base directory for storage. Defaults to studio/.executions/
        """
        if base_dir is None:
            base_dir = Path(__file__).parent / ".executions"

        self.base_dir = Path(base_dir)
        self.runs_dir = self.base_dir / "runs"
        self.index_file = self.base_dir / "index.json"
        self.legacy_file = Path(__file__).parent / ".executions_history.json"

        # In-memory cache for active/recent executions
        self._cache: Dict[str, WorkflowExecution] = {}
        self._index_cache: Dict[str, ExecutionIndex] = {}
        self._lock = Lock()

        # Ensure directories exist
        self._ensure_directories()

        # Migrate from legacy format if needed
        self._migrate_if_needed()

        # Load index into memory
        self._load_index()

    def _ensure_directories(self):
        """Create storage directories if they don't exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _get_run_file(self, execution_id: str) -> Path:
        """Get the file path for a specific run."""
        return self.runs_dir / f"{execution_id}.json"

    def _migrate_if_needed(self):
        """Migrate from legacy monolithic JSON if it exists."""
        if not self.legacy_file.exists():
            return

        # Check if already migrated
        if self.index_file.exists():
            # Verify index has entries or legacy is empty
            try:
                with open(self.index_file, 'r') as f:
                    index_data = json.load(f)
                    if index_data.get("runs") and len(index_data["runs"]) > 0:
                        # Already migrated, optionally remove legacy
                        return
            except:
                pass

        print(f"[ExecutionStorage] Migrating from legacy format...")

        try:
            with open(self.legacy_file, 'r') as f:
                legacy_data = json.load(f)

            migrated_count = 0
            index_entries = []

            for exec_id, exec_data in legacy_data.items():
                try:
                    # Convert node_states if needed
                    if 'node_states' in exec_data and exec_data['node_states']:
                        exec_data['node_states'] = {
                            k: NodeExecutionState(**v) if isinstance(v, dict) else v
                            for k, v in exec_data['node_states'].items()
                        }

                    # Create WorkflowExecution object
                    execution = WorkflowExecution(**exec_data)

                    # Save per-run file
                    run_file = self._get_run_file(exec_id)
                    with open(run_file, 'w') as f:
                        json.dump(execution.model_dump(mode='json'), f, default=str)

                    # Create index entry
                    index_entry = ExecutionIndex.from_execution(execution)
                    index_entries.append(index_entry)

                    migrated_count += 1
                except Exception as e:
                    print(f"[ExecutionStorage] Warning: Failed to migrate {exec_id}: {e}")

            # Sort by started_at, newest first
            index_entries.sort(
                key=lambda e: e.started_at or "",
                reverse=True
            )

            # Save index
            index_data = {
                "version": STORAGE_VERSION,
                "total_runs": len(index_entries),
                "last_updated": datetime.now().isoformat(),
                "runs": [e.to_dict() for e in index_entries[:MAX_INDEX_ENTRIES]]
            }

            with open(self.index_file, 'w') as f:
                json.dump(index_data, f, indent=2)

            # Rename legacy file to backup
            backup_file = self.legacy_file.with_suffix('.json.bak')
            shutil.move(str(self.legacy_file), str(backup_file))

            print(f"[ExecutionStorage] Migrated {migrated_count} executions. Legacy file backed up to {backup_file}")

        except Exception as e:
            print(f"[ExecutionStorage] Migration failed: {e}")

    def _load_index(self):
        """Load index into memory and verify files exist."""
        needs_save = False

        with self._lock:
            self._index_cache.clear()

            if not self.index_file.exists():
                return

            try:
                with open(self.index_file, 'r') as f:
                    data = json.load(f)

                missing_files = []
                for entry_data in data.get("runs", []):
                    entry = ExecutionIndex.from_dict(entry_data)
                    # Verify the run file still exists
                    run_file = self._get_run_file(entry.id)
                    if run_file.exists():
                        self._index_cache[entry.id] = entry
                    else:
                        missing_files.append(entry.id)

                # If files were deleted externally, mark for index update
                if missing_files:
                    print(f"[ExecutionStorage] Detected {len(missing_files)} missing run files, cleaning up index...")
                    needs_save = True

            except Exception as e:
                print(f"[ExecutionStorage] Warning: Failed to load index: {e}")

        # Save outside the lock to avoid deadlock
        if needs_save:
            self._save_index()

    def _save_index(self):
        """Save index to disk."""
        with self._lock:
            # Sort by started_at, newest first
            entries = sorted(
                self._index_cache.values(),
                key=lambda e: e.started_at or "",
                reverse=True
            )

            index_data = {
                "version": STORAGE_VERSION,
                "total_runs": len(entries),
                "last_updated": datetime.now().isoformat(),
                "runs": [e.to_dict() for e in entries[:MAX_INDEX_ENTRIES]]
            }

            # Write with file locking for safety
            try:
                with open(self.index_file, 'w') as f:
                    # Try to get exclusive lock (non-blocking)
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except (IOError, OSError):
                        pass  # Continue without lock on Windows or if busy

                    json.dump(index_data, f, indent=2)

                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except (IOError, OSError):
                        pass
            except Exception as e:
                print(f"[ExecutionStorage] Warning: Failed to save index: {e}")

    def save_execution(self, execution: WorkflowExecution):
        """
        Save an execution (both to per-run file and update index).

        Args:
            execution: The execution to save.
        """
        exec_id = execution.id

        # Save per-run file
        run_file = self._get_run_file(exec_id)
        try:
            with open(run_file, 'w') as f:
                json.dump(execution.model_dump(mode='json'), f, default=str)
        except Exception as e:
            print(f"[ExecutionStorage] Warning: Failed to save run file {exec_id}: {e}")
            return

        # Update index
        with self._lock:
            index_entry = ExecutionIndex.from_execution(execution)
            self._index_cache[exec_id] = index_entry

            # Update in-memory cache
            self._cache[exec_id] = execution

        # Save index (only for completed/failed/cancelled)
        if execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            self._save_index()

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """
        Get full execution by ID.

        Args:
            execution_id: The execution ID.

        Returns:
            The full WorkflowExecution or None if not found.
        """
        # Check in-memory cache first
        with self._lock:
            if execution_id in self._cache:
                return self._cache[execution_id]

        # Load from per-run file
        run_file = self._get_run_file(execution_id)
        if not run_file.exists():
            return None

        try:
            with open(run_file, 'r') as f:
                data = json.load(f)

            # Convert node_states if needed
            if 'node_states' in data and data['node_states']:
                data['node_states'] = {
                    k: NodeExecutionState(**v) if isinstance(v, dict) else v
                    for k, v in data['node_states'].items()
                }

            execution = WorkflowExecution(**data)

            # Cache it
            with self._lock:
                self._cache[execution_id] = execution

            return execution

        except Exception as e:
            print(f"[ExecutionStorage] Warning: Failed to load execution {execution_id}: {e}")
            return None

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ExecutionIndex], int]:
        """
        List executions with filtering and pagination.

        Args:
            workflow_id: Filter by workflow ID.
            status: Filter by status.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            Tuple of (list of ExecutionIndex entries, total count matching filters)
        """
        with self._lock:
            entries = list(self._index_cache.values())

        # Apply filters
        if workflow_id:
            entries = [e for e in entries if e.workflow_id == workflow_id]

        if status:
            entries = [e for e in entries if e.status == status]

        # Sort by started_at, newest first
        entries.sort(key=lambda e: e.started_at or "", reverse=True)

        total = len(entries)

        # Apply pagination
        entries = entries[offset:offset + limit]

        return entries, total

    def list_executions_full(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[WorkflowExecution], int]:
        """
        List full executions (for backward compatibility).

        This loads full execution data for each entry.
        Use list_executions() for lightweight listing.

        Args:
            workflow_id: Filter by workflow ID.
            status: Filter by status.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            Tuple of (list of WorkflowExecution objects, total count)
        """
        index_entries, total = self.list_executions(
            workflow_id=workflow_id,
            status=status,
            limit=limit,
            offset=offset,
        )

        executions = []
        for entry in index_entries:
            execution = self.get_execution(entry.id)
            if execution:
                executions.append(execution)

        return executions, total

    def delete_execution(self, execution_id: str) -> bool:
        """
        Delete an execution.

        Args:
            execution_id: The execution ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        with self._lock:
            self._cache.pop(execution_id, None)
            self._index_cache.pop(execution_id, None)

        # Remove per-run file
        run_file = self._get_run_file(execution_id)
        if run_file.exists():
            try:
                run_file.unlink()
            except Exception as e:
                print(f"[ExecutionStorage] Warning: Failed to delete run file {execution_id}: {e}")
                return False

        # Save updated index
        self._save_index()

        return True

    def update_execution_in_memory(self, execution: WorkflowExecution):
        """
        Update execution in memory only (for active executions).

        Use this during execution progress updates to avoid disk I/O.
        Call save_execution() when execution completes.

        Args:
            execution: The execution to update.
        """
        with self._lock:
            self._cache[execution.id] = execution

            # Also update index cache
            index_entry = ExecutionIndex.from_execution(execution)
            self._index_cache[execution.id] = index_entry

    def refresh_index(self) -> int:
        """
        Refresh the index by re-scanning the runs directory.

        Detects files deleted externally and orphaned files not in the index.

        Returns:
            Number of changes detected (removed or added entries).
        """
        changes = 0

        with self._lock:
            # Check for missing files (in index but not on disk)
            missing = []
            for exec_id in list(self._index_cache.keys()):
                run_file = self._get_run_file(exec_id)
                if not run_file.exists():
                    missing.append(exec_id)

            for exec_id in missing:
                del self._index_cache[exec_id]
                # Also remove from in-memory cache
                self._cache.pop(exec_id, None)
                changes += 1

            if missing:
                print(f"[ExecutionStorage] Removed {len(missing)} entries for missing files")

            # Check for orphaned files (on disk but not in index)
            if self.runs_dir.exists():
                for run_file in self.runs_dir.glob("*.json"):
                    exec_id = run_file.stem
                    if exec_id not in self._index_cache:
                        # Try to load and add to index
                        try:
                            with open(run_file, 'r') as f:
                                data = json.load(f)
                            execution = WorkflowExecution(**data)
                            index_entry = ExecutionIndex.from_execution(execution)
                            self._index_cache[exec_id] = index_entry
                            changes += 1
                            print(f"[ExecutionStorage] Added orphaned file to index: {exec_id}")
                        except Exception as e:
                            print(f"[ExecutionStorage] Warning: Could not index orphaned file {exec_id}: {e}")

        # Save updated index if changes were made
        if changes > 0:
            self._save_index()

        return changes

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._lock:
            total = len(self._index_cache)

            status_counts = {}
            workflow_counts = {}

            for entry in self._index_cache.values():
                status_counts[entry.status] = status_counts.get(entry.status, 0) + 1
                workflow_counts[entry.workflow_id] = workflow_counts.get(entry.workflow_id, 0) + 1

        return {
            "total_executions": total,
            "status_breakdown": status_counts,
            "workflow_breakdown": workflow_counts,
            "storage_version": STORAGE_VERSION,
            "index_file": str(self.index_file),
            "runs_directory": str(self.runs_dir),
        }

    def cleanup_old_runs(self, keep_days: int = 30, keep_min: int = 100):
        """
        Cleanup old execution data to manage disk space.

        Args:
            keep_days: Keep executions from the last N days.
            keep_min: Always keep at least this many executions.
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=keep_days)
        cutoff_str = cutoff.isoformat()

        with self._lock:
            entries = sorted(
                self._index_cache.values(),
                key=lambda e: e.started_at or "",
                reverse=True
            )

        # Keep recent and minimum count
        to_delete = []
        kept_count = 0

        for entry in entries:
            if kept_count < keep_min:
                kept_count += 1
                continue

            if entry.started_at and entry.started_at < cutoff_str:
                to_delete.append(entry.id)

        # Delete old executions
        for exec_id in to_delete:
            self.delete_execution(exec_id)

        if to_delete:
            print(f"[ExecutionStorage] Cleaned up {len(to_delete)} old executions")


# Global singleton instance
_storage_instance: Optional[ExecutionStorage] = None


def get_storage() -> ExecutionStorage:
    """Get the global ExecutionStorage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ExecutionStorage()
    return _storage_instance
