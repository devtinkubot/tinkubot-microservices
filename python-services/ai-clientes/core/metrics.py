"""
Performance Metrics Tracking for ai-clientes.

This module provides performance tracking for operations including database
queries, cache operations, external API calls, and search operations.

The metrics system provides:
- Operation timing (min, max, avg, p95, p99)
- Operation counters (success, failure, total)
- Memory usage tracking
- Custom metric registration

Example:
    >>> from core.metrics import metrics
    >>>
    >>> # Time an operation
    >>> async with metrics.timer("database_query"):
    ...     await repository.find_customer(phone)
    >>>
    >>> # Get statistics
    >>> stats = metrics.get_stats("database_query")
    >>> print(f"Average query time: {stats['avg_ms']}ms")
"""

import asyncio
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Container for metric data points."""
    operation: str
    duration_ms: float
    success: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationStats:
    """Statistics for a single operation."""
    operation: str
    total_calls: int = 0
    success_calls: int = 0
    failure_calls: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    durations: List[float] = field(default_factory=list)

    def add_sample(self, duration_ms: float, success: bool) -> None:
        """Add a performance sample."""
        self.total_calls += 1
        if success:
            self.success_calls += 1
        else:
            self.failure_calls += 1

        self.total_duration_ms += duration_ms
        self.durations.append(duration_ms)

        # Update min/max
        if self.min_duration_ms is None or duration_ms < self.min_duration_ms:
            self.min_duration_ms = duration_ms
        if self.max_duration_ms is None or duration_ms > self.max_duration_ms:
            self.max_duration_ms = duration_ms

    def get_stats(self) -> Dict[str, Any]:
        """Get computed statistics."""
        avg = self.total_duration_ms / self.total_calls if self.total_calls > 0 else 0

        # Calculate percentiles
        sorted_durations = sorted(self.durations)
        n = len(sorted_durations)

        p50 = sorted_durations[n // 2] if n > 0 else 0
        p95 = sorted_durations[int(n * 0.95)] if n > 0 else 0
        p99 = sorted_durations[int(n * 0.99)] if n > 0 else 0

        return {
            "operation": self.operation,
            "total_calls": self.total_calls,
            "success_calls": self.success_calls,
            "failure_calls": self.failure_calls,
            "success_rate_percent": round(
                (self.success_calls / self.total_calls * 100) if self.total_calls > 0 else 0,
                2
            ),
            "avg_ms": round(avg, 2),
            "min_ms": round(self.min_duration_ms or 0, 2),
            "max_ms": round(self.max_duration_ms or 0, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
        }


class PerformanceMetrics:
    """
    Performance metrics tracking system.

    Tracks timing and success/failure rates for operations.

    Attributes:
        operations: Dictionary of operation_name -> OperationStats
        history: List of all MetricData points (for detailed analysis)

    Example:
        >>> metrics = PerformanceMetrics()
        >>> async with metrics.timer("search_providers"):
        ...     results = await search_providers(city, service)
        >>>
        >>> stats = metrics.get_stats("search_providers")
        >>> print(f"Average: {stats['avg_ms']}ms")
    """

    def __init__(self):
        """Initialize the metrics tracker."""
        self.operations: Dict[str, OperationStats] = defaultdict(
            lambda: OperationStats(operation="")
        )
        self.history: List[MetricData] = []
        self._enabled = True
        logger.debug("PerformanceMetrics initialized")

    def enable(self) -> None:
        """Enable metrics collection."""
        self._enabled = True
        logger.info("✅ Metrics collection enabled")

    def disable(self) -> None:
        """Disable metrics collection."""
        self._enabled = False
        logger.info("⏸️ Metrics collection disabled")

    def record(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a performance metric.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether the operation succeeded
            metadata: Optional metadata about the operation

        Example:
            >>> metrics.record("database_query", 45.2, success=True)
        """
        if not self._enabled:
            return

        # Update operation stats
        if operation not in self.operations:
            self.operations[operation] = OperationStats(operation=operation)

        self.operations[operation].add_sample(duration_ms, success)

        # Add to history
        metric_data = MetricData(
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata or {}
        )
        self.history.append(metric_data)

    @asynccontextmanager
    async def timer(
        self,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[None]:
        """
        Context manager for timing operations.

        Args:
            operation: Operation name
            metadata: Optional metadata to attach

        Example:
            >>> async with metrics.timer("search_providers"):
            ...     results = await search_providers(city, service)
        """
        if not self._enabled:
            yield
            return

        start_time = time.perf_counter()
        success = True

        try:
            yield
        except Exception as e:
            success = False
            logger.error(f"❌ Operation '{operation}' failed: {e}")
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.record(operation, duration_ms, success, metadata)

    def timeit(self, operation: str):
        """
        Decorator for timing functions.

        Args:
            operation: Operation name

        Example:
            >>> @metrics.timeit("database_query")
            ... async def get_customer(phone):
            ...     return await repository.find_customer(phone)
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self._enabled:
                    return await func(*args, **kwargs)

                start_time = time.perf_counter()
                success = True

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    logger.error(f"❌ Function '{func.__name__}' failed: {e}")
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    self.record(operation, duration_ms, success)

            return wrapper
        return decorator

    def get_stats(self, operation: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific operation.

        Args:
            operation: Operation name

        Returns:
            Statistics dictionary or None if operation not found

        Example:
            >>> stats = metrics.get_stats("search_providers")
            >>> print(f"Average: {stats['avg_ms']}ms")
        """
        if operation not in self.operations:
            return None

        return self.operations[operation].get_stats()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all operations.

        Returns:
            Dictionary mapping operation names to their statistics

        Example:
            >>> all_stats = metrics.get_all_stats()
            >>> for op, stats in all_stats.items():
            ...     print(f"{op}: {stats['avg_ms']}ms avg")
        """
        return {
            op: stats.get_stats()
            for op, stats in self.operations.items()
        }

    def get_slow_operations(
        self,
        threshold_ms: float = 1000.0,
        min_calls: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get operations slower than threshold.

        Args:
            threshold_ms: Minimum average duration to consider "slow"
            min_calls: Minimum number of calls to be considered

        Returns:
            List of slow operations with their statistics

        Example:
            >>> slow_ops = metrics.get_slow_operations(threshold_ms=500)
            >>> for op in slow_ops:
            ...     print(f"{op['operation']}: {op['avg_ms']}ms")
        """
        slow_ops = []

        for op, stats in self.operations.items():
            if stats.total_calls >= min_calls:
                avg = stats.total_duration_ms / stats.total_calls
                if avg >= threshold_ms:
                    slow_ops.append(stats.get_stats())

        return sorted(slow_ops, key=lambda x: x["avg_ms"], reverse=True)

    def reset(self, operation: Optional[str] = None) -> None:
        """
        Reset metrics.

        Args:
            operation: Specific operation to reset, or None to reset all

        Example:
            >>> metrics.reset("search_providers")  # Reset specific
            >>> metrics.reset()  # Reset all
        """
        if operation:
            if operation in self.operations:
                del self.operations[operation]
            # Filter history
            self.history = [m for m in self.history if m.operation != operation]
            logger.debug(f"Reset metrics for operation: {operation}")
        else:
            self.operations.clear()
            self.history.clear()
            logger.debug("Reset all metrics")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all metrics.

        Returns:
            Dictionary with overall metrics summary

        Example:
            >>> summary = metrics.get_summary()
            >>> print(f"Total operations: {summary['total_operations']}")
        """
        total_calls = sum(stats.total_calls for stats in self.operations.values())
        total_success = sum(stats.success_calls for stats in self.operations.values())
        total_failure = sum(stats.failure_calls for stats in self.operations.values())

        return {
            "enabled": self._enabled,
            "total_operations": len(self.operations),
            "total_calls": total_calls,
            "total_success": total_success,
            "total_failure": total_failure,
            "overall_success_rate_percent": round(
                (total_success / total_calls * 100) if total_calls > 0 else 0,
                2
            ),
            "operations_tracked": list(self.operations.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global metrics instance
metrics = PerformanceMetrics()
