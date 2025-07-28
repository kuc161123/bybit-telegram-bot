#!/usr/bin/env python3
"""
Memory Leak Prevention Utilities for Long-Running Trading Bot
Implements 2025 best practices for memory management and leak prevention

Features:
- Weak reference management
- Circular reference detection
- Object lifecycle tracking
- Automatic cleanup of unused objects
- Memory growth monitoring
"""
import gc
import sys
import time
import weakref
import logging
import threading
from typing import Dict, List, Set, Any, Optional, Callable
from collections import defaultdict, deque
from dataclasses import dataclass
import tracemalloc

logger = logging.getLogger(__name__)

@dataclass
class ObjectInfo:
    """Information about tracked objects"""
    obj_id: int
    obj_type: str
    creation_time: float
    size_bytes: int
    ref_count: int

class WeakReferenceManager:
    """
    Manages weak references to prevent circular reference memory leaks
    Based on 2025 Python memory management best practices
    """
    
    def __init__(self):
        self._weak_refs: Dict[int, weakref.ref] = {}
        self._callbacks: Dict[int, List[Callable]] = defaultdict(list)
        self._cleanup_count = 0
        self._last_cleanup = time.time()
        
    def register_object(self, obj: Any, cleanup_callback: Optional[Callable] = None) -> int:
        """Register an object for weak reference tracking"""
        obj_id = id(obj)
        
        def callback_wrapper(ref):
            """Called when object is garbage collected"""
            self._cleanup_count += 1
            logger.debug(f"Object {obj_id} ({type(obj).__name__}) garbage collected")
            
            # Run cleanup callbacks
            for callback in self._callbacks.get(obj_id, []):
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error in cleanup callback for {obj_id}: {e}")
            
            # Clean up tracking data
            self._weak_refs.pop(obj_id, None)
            self._callbacks.pop(obj_id, None)
        
        # Create weak reference with callback
        self._weak_refs[obj_id] = weakref.ref(obj, callback_wrapper)
        
        # Register cleanup callback if provided
        if cleanup_callback:
            self._callbacks[obj_id].append(cleanup_callback)
        
        return obj_id
    
    def add_cleanup_callback(self, obj_id: int, callback: Callable) -> bool:
        """Add a cleanup callback for an existing tracked object"""
        if obj_id in self._weak_refs:
            self._callbacks[obj_id].append(callback)
            return True
        return False
    
    def is_object_alive(self, obj_id: int) -> bool:
        """Check if a tracked object is still alive"""
        ref = self._weak_refs.get(obj_id)
        if ref is None:
            return False
        return ref() is not None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get weak reference manager statistics"""
        alive_count = sum(1 for ref in self._weak_refs.values() if ref() is not None)
        
        return {
            "tracked_objects": len(self._weak_refs),
            "alive_objects": alive_count,
            "dead_objects": len(self._weak_refs) - alive_count,
            "cleanup_count": self._cleanup_count,
            "last_cleanup": self._last_cleanup
        }
    
    def cleanup_dead_references(self) -> int:
        """Manually cleanup dead weak references"""
        dead_refs = []
        for obj_id, ref in self._weak_refs.items():
            if ref() is None:
                dead_refs.append(obj_id)
        
        for obj_id in dead_refs:
            self._weak_refs.pop(obj_id, None)
            self._callbacks.pop(obj_id, None)
        
        if dead_refs:
            logger.debug(f"Cleaned up {len(dead_refs)} dead weak references")
        
        self._last_cleanup = time.time()
        return len(dead_refs)

class CircularReferenceDetector:
    """
    Detects and helps resolve circular references that prevent garbage collection
    """
    
    def __init__(self):
        self._tracked_types: Set[type] = set()
        self._detection_history: deque = deque(maxlen=100)
        
    def add_tracked_type(self, obj_type: type) -> None:
        """Add an object type to track for circular references"""
        self._tracked_types.add(obj_type)
        logger.debug(f"Now tracking {obj_type.__name__} for circular references")
    
    def detect_cycles(self) -> List[Dict[str, Any]]:
        """Detect circular references in tracked object types"""
        cycles_found = []
        
        # Use gc.get_referrers to find circular references
        for obj in gc.get_objects():
            if type(obj) in self._tracked_types:
                cycles = self._find_cycles_for_object(obj)
                if cycles:
                    cycles_found.extend(cycles)
        
        # Record detection results
        detection_result = {
            "timestamp": time.time(),
            "cycles_found": len(cycles_found),
            "tracked_types": len(self._tracked_types)
        }
        self._detection_history.append(detection_result)
        
        if cycles_found:
            logger.warning(f"🔄 Detected {len(cycles_found)} potential circular references")
        
        return cycles_found
    
    def _find_cycles_for_object(self, obj: Any) -> List[Dict[str, Any]]:
        """Find circular references for a specific object"""
        cycles = []
        visited = set()
        
        def traverse(current_obj, path):
            obj_id = id(current_obj)
            if obj_id in visited:
                # Found a cycle
                cycle_start = path.index(obj_id) if obj_id in path else len(path)
                cycle_path = path[cycle_start:] + [obj_id]
                cycles.append({
                    "cycle_path": cycle_path,
                    "cycle_length": len(cycle_path) - 1,
                    "object_types": [type(o).__name__ for o in path]
                })
                return
            
            visited.add(obj_id)
            path.append(obj_id)
            
            # Traverse referrers (limit depth to prevent infinite recursion)
            if len(path) < 10:
                for referrer in gc.get_referrers(current_obj):
                    if type(referrer) in self._tracked_types:
                        traverse(referrer, path.copy())
        
        try:
            traverse(obj, [])
        except Exception as e:
            logger.debug(f"Error during cycle detection: {e}")
        
        return cycles
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get circular reference detection statistics"""
        if not self._detection_history:
            return {"status": "No detections performed"}
        
        recent_detections = list(self._detection_history)[-10:]
        total_cycles = sum(d["cycles_found"] for d in recent_detections)
        avg_cycles = total_cycles / len(recent_detections) if recent_detections else 0
        
        return {
            "total_detections": len(self._detection_history),
            "recent_cycles_found": total_cycles,
            "average_cycles_per_detection": avg_cycles,
            "tracked_types": list(t.__name__ for t in self._tracked_types),
            "last_detection": recent_detections[-1]["timestamp"] if recent_detections else None
        }

class ObjectLifecycleTracker:
    """
    Tracks object lifecycles to identify memory leaks and unusual patterns
    """
    
    def __init__(self, max_tracked_objects: int = 10000):
        self._tracked_objects: Dict[int, ObjectInfo] = {}
        self._max_tracked = max_tracked_objects
        self._creation_rate: deque = deque(maxlen=300)  # 5 minutes of data
        self._type_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()
        
    def track_object_creation(self, obj: Any) -> int:
        """Track the creation of an object"""
        with self._lock:
            obj_id = id(obj)
            obj_type = type(obj).__name__
            current_time = time.time()
            
            # Calculate object size (estimate)
            try:
                size_bytes = sys.getsizeof(obj)
            except (TypeError, OverflowError):
                size_bytes = 0
            
            obj_info = ObjectInfo(
                obj_id=obj_id,
                obj_type=obj_type,
                creation_time=current_time,
                size_bytes=size_bytes,
                ref_count=sys.getrefcount(obj)
            )
            
            # Limit tracking to prevent memory usage from tracking itself
            if len(self._tracked_objects) >= self._max_tracked:
                # Remove oldest entries
                oldest_items = sorted(
                    self._tracked_objects.items(),
                    key=lambda x: x[1].creation_time
                )
                for old_id, _ in oldest_items[:len(oldest_items) // 4]:
                    self._tracked_objects.pop(old_id, None)
            
            self._tracked_objects[obj_id] = obj_info
            self._type_counts[obj_type] += 1
            self._creation_rate.append(current_time)
            
            return obj_id
    
    def track_object_deletion(self, obj_id: int) -> bool:
        """Track the deletion of an object"""
        with self._lock:
            obj_info = self._tracked_objects.pop(obj_id, None)
            if obj_info:
                self._type_counts[obj_info.obj_type] = max(0, self._type_counts[obj_info.obj_type] - 1)
                return True
            return False
    
    def get_object_lifetime(self, obj_id: int) -> Optional[float]:
        """Get the lifetime of a tracked object"""
        with self._lock:
            obj_info = self._tracked_objects.get(obj_id)
            if obj_info:
                return time.time() - obj_info.creation_time
            return None
    
    def get_long_lived_objects(self, min_age_seconds: float = 3600) -> List[ObjectInfo]:
        """Get objects that have been alive for longer than specified time"""
        with self._lock:
            current_time = time.time()
            long_lived = [
                obj_info for obj_info in self._tracked_objects.values()
                if (current_time - obj_info.creation_time) > min_age_seconds
            ]
            return sorted(long_lived, key=lambda x: x.creation_time)
    
    def get_creation_rate(self, window_seconds: int = 60) -> float:
        """Get object creation rate per second over specified window"""
        current_time = time.time()
        recent_creations = [
            t for t in self._creation_rate
            if (current_time - t) <= window_seconds
        ]
        return len(recent_creations) / window_seconds if window_seconds > 0 else 0
    
    def get_lifecycle_stats(self) -> Dict[str, Any]:
        """Get comprehensive object lifecycle statistics"""
        with self._lock:
            current_time = time.time()
            
            # Calculate age distribution
            ages = [current_time - obj.creation_time for obj in self._tracked_objects.values()]
            avg_age = sum(ages) / len(ages) if ages else 0
            max_age = max(ages) if ages else 0
            
            # Get top object types by count
            top_types = sorted(
                self._type_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return {
                "total_tracked": len(self._tracked_objects),
                "average_age_seconds": avg_age,
                "max_age_seconds": max_age,
                "creation_rate_per_minute": self.get_creation_rate(60) * 60,
                "top_object_types": dict(top_types),
                "long_lived_objects": len(self.get_long_lived_objects(3600)),  # 1 hour+
                "very_long_lived_objects": len(self.get_long_lived_objects(86400))  # 1 day+
            }

class MemoryLeakPreventionSystem:
    """
    Comprehensive memory leak prevention system combining all utilities
    """
    
    def __init__(self):
        self.weak_ref_manager = WeakReferenceManager()
        self.cycle_detector = CircularReferenceDetector()
        self.lifecycle_tracker = ObjectLifecycleTracker()
        self._monitoring_enabled = False
        self._tracemalloc_enabled = False
        
        # Initialize tracemalloc if available
        try:
            if not tracemalloc.is_tracing():
                tracemalloc.start(25)  # Store 25 frames
                self._tracemalloc_enabled = True
                logger.info("✅ Tracemalloc enabled for memory leak detection")
        except Exception as e:
            logger.warning(f"Could not enable tracemalloc: {e}")
    
    def enable_monitoring(self, track_types: Optional[List[type]] = None) -> None:
        """Enable comprehensive memory leak monitoring"""
        self._monitoring_enabled = True
        
        # Add common problematic types for tracking
        default_types = [dict, list, set, object]
        if track_types:
            default_types.extend(track_types)
        
        for obj_type in default_types:
            self.cycle_detector.add_tracked_type(obj_type)
        
        logger.info(f"✅ Memory leak monitoring enabled for {len(default_types)} types")
    
    def register_object_for_tracking(self, obj: Any, cleanup_callback: Optional[Callable] = None) -> int:
        """Register an object for comprehensive tracking"""
        if not self._monitoring_enabled:
            return -1
        
        # Track in lifecycle tracker
        obj_id = self.lifecycle_tracker.track_object_creation(obj)
        
        # Register weak reference
        self.weak_ref_manager.register_object(obj, cleanup_callback)
        
        return obj_id
    
    def perform_comprehensive_check(self) -> Dict[str, Any]:
        """Perform comprehensive memory leak check"""
        if not self._monitoring_enabled:
            return {"status": "Monitoring not enabled"}
        
        logger.info("🔍 Performing comprehensive memory leak check...")
        
        # Detect circular references
        cycles = self.cycle_detector.detect_cycles()
        
        # Get statistics from all components
        weak_ref_stats = self.weak_ref_manager.get_stats()
        lifecycle_stats = self.lifecycle_tracker.get_lifecycle_stats()
        detection_stats = self.cycle_detector.get_detection_stats()
        
        # Get tracemalloc info if available
        tracemalloc_info = {}
        if self._tracemalloc_enabled and tracemalloc.is_tracing():
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_info = {
                    "current_mb": current / 1024 / 1024,
                    "peak_mb": peak / 1024 / 1024,
                    "tracing": True
                }
            except Exception as e:
                tracemalloc_info = {"error": str(e), "tracing": False}
        
        # Perform cleanup
        cleaned_refs = self.weak_ref_manager.cleanup_dead_references()
        gc_collected = gc.collect()
        
        report = {
            "timestamp": time.time(),
            "circular_references": {
                "cycles_found": len(cycles),
                "cycle_details": cycles[:5] if cycles else []  # Limit output
            },
            "weak_references": weak_ref_stats,
            "object_lifecycle": lifecycle_stats,
            "detection_history": detection_stats,
            "tracemalloc": tracemalloc_info,
            "cleanup_performed": {
                "weak_refs_cleaned": cleaned_refs,
                "gc_objects_collected": gc_collected
            },
            "recommendations": self._generate_recommendations(cycles, lifecycle_stats)
        }
        
        if cycles or lifecycle_stats.get("long_lived_objects", 0) > 100:
            logger.warning("🚨 Potential memory issues detected - see comprehensive report")
        else:
            logger.info("✅ Memory leak check completed - no major issues detected")
        
        return report
    
    def _generate_recommendations(self, cycles: List[Dict], lifecycle_stats: Dict) -> List[str]:
        """Generate recommendations based on memory analysis"""
        recommendations = []
        
        if cycles:
            recommendations.append(f"Found {len(cycles)} circular references - consider using weak references")
        
        if lifecycle_stats.get("long_lived_objects", 0) > 50:
            recommendations.append("Many long-lived objects detected - review object cleanup patterns")
        
        creation_rate = lifecycle_stats.get("creation_rate_per_minute", 0)
        if creation_rate > 1000:
            recommendations.append(f"High object creation rate ({creation_rate:.0f}/min) - consider object pooling")
        
        if not recommendations:
            recommendations.append("Memory usage patterns appear normal")
        
        return recommendations
    
    def get_memory_health_summary(self) -> Dict[str, Any]:
        """Get a summary of memory health status"""
        if not self._monitoring_enabled:
            return {"status": "not_enabled", "message": "Memory monitoring not enabled"}
        
        weak_ref_stats = self.weak_ref_manager.get_stats()
        lifecycle_stats = self.lifecycle_tracker.get_lifecycle_stats()
        
        # Calculate health score (0-100)
        health_score = 100
        
        # Deduct points for issues
        long_lived = lifecycle_stats.get("long_lived_objects", 0)
        if long_lived > 100:
            health_score -= min(30, long_lived // 10)
        
        dead_refs = weak_ref_stats.get("dead_objects", 0)
        total_refs = weak_ref_stats.get("tracked_objects", 1)
        dead_ratio = dead_refs / total_refs
        if dead_ratio > 0.2:  # More than 20% dead references
            health_score -= 20
        
        creation_rate = lifecycle_stats.get("creation_rate_per_minute", 0)
        if creation_rate > 1000:
            health_score -= 15
        
        # Determine status
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 60:
            status = "fair"
        elif health_score >= 40:
            status = "poor"
        else:
            status = "critical"
        
        return {
            "status": status,
            "health_score": max(0, health_score),
            "monitoring_enabled": self._monitoring_enabled,
            "tracemalloc_enabled": self._tracemalloc_enabled,
            "summary_stats": {
                "tracked_objects": lifecycle_stats.get("total_tracked", 0),
                "long_lived_objects": long_lived,
                "creation_rate": creation_rate,
                "weak_references": weak_ref_stats.get("tracked_objects", 0)
            }
        }

# Global memory leak prevention system
memory_leak_prevention = MemoryLeakPreventionSystem()

# Convenience functions
def enable_memory_monitoring(track_types: Optional[List[type]] = None) -> None:
    """Enable global memory leak monitoring"""
    memory_leak_prevention.enable_monitoring(track_types)

def register_for_cleanup(obj: Any, cleanup_callback: Optional[Callable] = None) -> int:
    """Register an object for memory leak prevention tracking"""
    return memory_leak_prevention.register_object_for_tracking(obj, cleanup_callback)

def check_for_memory_leaks() -> Dict[str, Any]:
    """Perform comprehensive memory leak check"""
    return memory_leak_prevention.perform_comprehensive_check()

def get_memory_health() -> Dict[str, Any]:
    """Get memory health summary"""
    return memory_leak_prevention.get_memory_health_summary()

# Decorator for automatic object tracking
def track_memory_usage(cleanup_callback: Optional[Callable] = None):
    """Decorator to automatically track object memory usage"""
    def decorator(cls):
        original_init = cls.__init__
        
        def enhanced_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            register_for_cleanup(self, cleanup_callback)
        
        cls.__init__ = enhanced_init
        return cls
    
    return decorator