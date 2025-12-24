"""
Database utility functions for handling SQLite concurrent write operations.

This module provides retry logic and other database-related utilities to handle
SQLite database locking issues when multiple users perform bulk operations simultaneously.
"""

import time
import logging
from functools import wraps
from django.db import OperationalError
import sqlite3

logger = logging.getLogger(__name__)


def retry_on_db_lock(max_retries=5, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator that automatically retries database operations when they fail due to database locks.
    
    This decorator implements exponential backoff retry logic to handle SQLite's
    "database is locked" errors that occur during concurrent write operations.
    
    Args:
        max_retries (int): Maximum number of retry attempts (default: 5)
        initial_delay (float): Initial delay in seconds before first retry (default: 1.0)
        backoff_factor (float): Multiplier for delay between retries (default: 2.0)
                               Delay sequence: 1s, 2s, 4s, 8s, 16s
    
    Returns:
        function: Decorated function that automatically retries on database lock
    
    Raises:
        OperationalError: If all retries are exhausted, raises the original error
                         with a user-friendly message
    
    Example:
        @retry_on_db_lock(max_retries=5)
        def process_bulk_upload(csv_data):
            # Bulk operation code here
            pass
    
    Retry Logic:
        - Catches sqlite3.OperationalError with "database is locked" message
        - Catches django.db.utils.OperationalError with "database is locked" message
        - Waits with exponential backoff: delay = initial_delay * (backoff_factor ^ attempt)
        - Logs each retry attempt with context (function name, attempt number, delay)
        - Re-raises exception with user-friendly message after max retries exhausted
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            delay = initial_delay
            
            while attempt <= max_retries:
                try:
                    # Try to execute the function
                    return func(*args, **kwargs)
                
                except (OperationalError, sqlite3.OperationalError) as e:
                    error_message = str(e).lower()
                    
                    # Check if this is a database lock error
                    if 'database is locked' in error_message:
                        attempt += 1
                        
                        # If we've exhausted all retries, raise with user-friendly message
                        if attempt > max_retries:
                            logger.error(
                                f"Database lock error after {max_retries} retries in {func.__name__}. "
                                f"Original error: {str(e)}"
                            )
                            raise OperationalError(
                                "The system is currently busy processing other requests. "
                                "Please try again in a few minutes."
                            ) from e
                        
                        # Log the retry attempt
                        logger.warning(
                            f"Database locked in {func.__name__}, "
                            f"retry {attempt}/{max_retries} after {delay:.1f}s delay"
                        )
                        
                        # Wait before retrying (exponential backoff)
                        time.sleep(delay)
                        
                        # Increase delay for next retry
                        delay *= backoff_factor
                    
                    else:
                        # Not a database lock error, re-raise immediately
                        raise
                
                except Exception as e:
                    # Not a database error, re-raise immediately
                    raise
            
            # This should never be reached, but just in case
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def get_db_lock_info():
    """
    Get information about current database locks (for debugging/monitoring).
    
    Returns:
        dict: Information about database state including:
            - journal_mode: Current journal mode (should be 'wal')
            - busy_timeout: Current busy timeout in milliseconds
            - wal_checkpoint: WAL checkpoint status
    
    Note:
        This is a utility function for debugging and monitoring purposes.
        It's not used in the main retry logic.
    """
    from django.db import connection
    
    try:
        with connection.cursor() as cursor:
            # Get journal mode
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            
            # Get busy timeout
            cursor.execute("PRAGMA busy_timeout;")
            busy_timeout = cursor.fetchone()[0]
            
            # Get WAL checkpoint info
            cursor.execute("PRAGMA wal_checkpoint;")
            wal_checkpoint = cursor.fetchone()
            
            return {
                'journal_mode': journal_mode,
                'busy_timeout_ms': busy_timeout,
                'wal_checkpoint': wal_checkpoint,
            }
    
    except Exception as e:
        logger.error(f"Failed to get database lock info: {str(e)}")
        return {
            'error': str(e)
        }
