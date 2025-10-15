# queue.py - Simple thread-safe queue implementation for MicroPython

import _thread
import utime

class Empty(Exception):
    """Exception raised when Queue.get() is called on an empty queue."""
    pass

class Full(Exception):
    """Exception raised when Queue.put() is called on a full queue."""
    pass

class Queue:
    """
    Simple thread-safe FIFO queue implementation for MicroPython.
    Supports blocking and non-blocking operations with timeouts.
    """
    
    def __init__(self, maxsize=0):
        """
        Initialize a queue.
        
        Args:
            maxsize: Maximum number of items in queue (0 = unlimited)
        """
        self.maxsize = maxsize
        self._queue = []
        self._lock = _thread.allocate_lock()
        self._not_empty = _thread.allocate_lock()
        self._not_full = _thread.allocate_lock()
        
        # Start with not_empty locked (will be released when item added)
        self._not_empty.acquire()
        
        # Start with not_full unlocked (unless maxsize is 0)
        if maxsize == 0:
            self._not_full.acquire()
    
    def qsize(self):
        """Return the approximate size of the queue."""
        with self._lock:
            return len(self._queue)
    
    def empty(self):
        """Return True if the queue is empty."""
        with self._lock:
            return len(self._queue) == 0
    
    def full(self):
        """Return True if the queue is full."""
        with self._lock:
            if self.maxsize <= 0:
                return False
            return len(self._queue) >= self.maxsize
    
    def put(self, item, block=True, timeout=None):
        """
        Put an item into the queue.
        
        Args:
            item: Item to put in queue
            block: If True, block until space available
            timeout: Max time to wait (seconds). None = wait forever
            
        Raises:
            Full: If queue is full and block=False
        """
        if timeout is not None:
            end_time = utime.time() + timeout
        
        with self._lock:
            # Check if queue is full
            while self.maxsize > 0 and len(self._queue) >= self.maxsize:
                if not block:
                    raise Full("Queue is full")
                
                # Release main lock and wait for space
                self._lock.release()
                
                if timeout is None:
                    # Wait indefinitely
                    self._not_full.acquire()
                else:
                    # Wait with timeout
                    remaining = end_time - utime.time()
                    if remaining <= 0:
                        self._lock.acquire()
                        raise Full("Queue is full")
                    
                    # Simple timeout wait (not perfect but works)
                    start_wait = utime.time()
                    while not self._try_acquire_with_timeout(self._not_full, 0.01):
                        if utime.time() - start_wait >= remaining:
                            self._lock.acquire()
                            raise Full("Queue is full")
                
                # Re-acquire the main lock
                self._lock.acquire()
            
            # Add item to queue
            self._queue.append(item)
            
            # Signal that queue is not empty
            try:
                self._not_empty.release()
            except:
                pass  # Already released
    
    def get(self, block=True, timeout=None):
        """
        Remove and return an item from the queue.
        
        Args:
            block: If True, block until item available
            timeout: Max time to wait (seconds). None = wait forever
            
        Returns:
            The next item from the queue
            
        Raises:
            Empty: If queue is empty and block=False or timeout exceeded
        """
        if timeout is not None:
            end_time = utime.time() + timeout
        
        with self._lock:
            # Check if queue is empty
            while len(self._queue) == 0:
                if not block:
                    raise Empty("Queue is empty")
                
                # Release main lock and wait for item
                self._lock.release()
                
                if timeout is None:
                    # Wait indefinitely
                    self._not_empty.acquire()
                else:
                    # Wait with timeout
                    remaining = end_time - utime.time()
                    if remaining <= 0:
                        self._lock.acquire()
                        raise Empty("Queue is empty")
                    
                    # Simple timeout wait
                    start_wait = utime.time()
                    while not self._try_acquire_with_timeout(self._not_empty, 0.01):
                        if utime.time() - start_wait >= remaining:
                            self._lock.acquire()
                            raise Empty("Queue is empty")
                
                # Re-acquire the main lock
                self._lock.acquire()
            
            # Get item from queue
            item = self._queue.pop(0)
            
            # Signal that queue is not full
            if self.maxsize > 0:
                try:
                    self._not_full.release()
                except:
                    pass  # Already released
            
            return item
    
    def put_nowait(self, item):
        """Put an item into the queue without blocking."""
        return self.put(item, block=False)
    
    def get_nowait(self):
        """Remove and return an item from the queue without blocking."""
        return self.get(block=False)
    
    def _try_acquire_with_timeout(self, lock, timeout):
        """Try to acquire a lock with timeout."""
        # This is a simple implementation - MicroPython doesn't have
        # a native way to acquire locks with timeout
        start = utime.time()
        while utime.time() - start < timeout:
            if lock.acquire(0):  # Non-blocking acquire
                return True
            utime.sleep_ms(1)
        return False

# Simpler alternative if you don't need all the features:
class SimpleQueue:
    """
    Simplified queue for basic use cases.
    Not fully thread-safe but good enough for many scenarios.
    """
    
    def __init__(self, maxsize=0):
        self.maxsize = maxsize
        self._queue = []
        self._lock = _thread.allocate_lock()
    
    def put(self, item, block=False):
        """Add item to queue."""
        with self._lock:
            if self.maxsize > 0 and len(self._queue) >= self.maxsize:
                if not block:
                    return False
                # For blocking, you'd need to implement wait logic
                return False
            self._queue.append(item)
            return True
    
    def get(self, timeout=None):
        """Get item from queue with optional timeout."""
        end_time = utime.time() + timeout if timeout else None
        
        while True:
            with self._lock:
                if self._queue:
                    return self._queue.pop(0)
            
            if timeout is not None:
                if utime.time() >= end_time:
                    raise Empty("Queue is empty")
            
            utime.sleep_ms(10)  # Small delay to prevent busy waiting
    
    def empty(self):
        """Check if queue is empty."""
        with self._lock:
            return len(self._queue) == 0
    
    def qsize(self):
        """Get queue size."""
        with self._lock:
            return len(self._queue)