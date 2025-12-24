"""
Batch Transaction Manager for processing bulk operations in smaller transaction chunks.

This module provides utilities to split large bulk operations into smaller batches,
reducing database lock time and allowing concurrent operations to interleave.
"""

import logging
from django.db import transaction
from typing import List, Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)


class BatchTransactionManager:
    """
    Manages batch processing of bulk operations to minimize database lock time.
    
    Instead of processing all items in one large transaction (which locks the database
    for a long time), this manager splits items into smaller batches and processes
    each batch in its own transaction. This allows other operations to run between batches.
    
    Example:
        manager = BatchTransactionManager(batch_size=100)
        
        def process_item(item):
            # Process single item
            item.save()
        
        result = manager.process_in_batches(
            items=my_items,
            process_func=process_item,
            progress_callback=lambda p: print(f"Progress: {p}%")
        )
        
        print(f"Processed {result['successful']} items, {result['failed']} failed")
    """
    
    def __init__(self, batch_size: int = 1000):
        """
        Initialize batch manager.
        
        Args:
            batch_size (int): Number of items to process per transaction (default: 1000)
                             Smaller batches = less lock time but more overhead
                             Larger batches = more lock time but less overhead
                             1000 is a good balance for 2-3 concurrent users
                             
                             Recommended values:
                             - 100: Very safe for 5+ concurrent users (slower)
                             - 500: Balanced for 3-4 concurrent users
                             - 1000: Fast for 2-3 concurrent users (recommended)
                             - 2000: Very fast for 1-2 concurrent users (riskier)
        """
        self.batch_size = batch_size
        logger.debug(f"BatchTransactionManager initialized with batch_size={batch_size}")
    
    def process_in_batches(
        self,
        items: List[Any],
        process_func: Callable[[Any], None],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Process items in batches with individual transactions.
        
        Each batch is processed in its own atomic transaction. If a batch fails,
        only that batch is rolled back - other batches continue processing.
        
        Args:
            items (List[Any]): List of items to process
            process_func (Callable): Function to process each item
                                    Should accept one item as argument
                                    Should NOT commit transactions (handled by manager)
            progress_callback (Optional[Callable]): Optional callback for progress updates
                                                   Called with (processed_count, total_count)
        
        Returns:
            dict: Processing results with keys:
                - total (int): Total number of items
                - successful (int): Number of successfully processed items
                - failed (int): Number of failed items
                - errors (list): List of error details for failed items
                - batches_processed (int): Number of batches completed
                - batches_failed (int): Number of batches that failed
        
        Example:
            def save_item(item):
                item.outlet_mrp = new_mrp
                item.save()
            
            result = manager.process_in_batches(
                items=item_outlets,
                process_func=save_item
            )
        """
        total_items = len(items)
        successful_count = 0
        failed_count = 0
        errors = []
        batches_processed = 0
        batches_failed = 0
        
        logger.info(f"Starting batch processing: {total_items} items in batches of {self.batch_size}")
        
        # Split items into batches
        for batch_num, i in enumerate(range(0, total_items, self.batch_size), start=1):
            batch = items[i:i + self.batch_size]
            batch_size = len(batch)
            
            try:
                # Process this batch in an atomic transaction
                with transaction.atomic():
                    for item_idx, item in enumerate(batch):
                        try:
                            process_func(item)
                            successful_count += 1
                        
                        except Exception as e:
                            failed_count += 1
                            error_detail = {
                                'batch': batch_num,
                                'item_index': i + item_idx,
                                'error': str(e),
                                'item': str(item) if hasattr(item, '__str__') else repr(item)
                            }
                            errors.append(error_detail)
                            logger.error(
                                f"Error processing item {i + item_idx} in batch {batch_num}: {str(e)}"
                            )
                            # Continue processing other items in this batch
                
                batches_processed += 1
                logger.debug(f"Batch {batch_num} completed: {batch_size} items processed")
            
            except Exception as e:
                # Entire batch failed (transaction rolled back)
                batches_failed += 1
                failed_count += batch_size
                logger.error(f"Batch {batch_num} failed completely: {str(e)}", exc_info=True)
                
                # Log batch failure
                batch_error = {
                    'batch': batch_num,
                    'batch_size': batch_size,
                    'error': f"Batch transaction failed: {str(e)}",
                    'items_affected': batch_size
                }
                errors.append(batch_error)
            
            # Call progress callback if provided
            if progress_callback:
                try:
                    processed_so_far = min(i + self.batch_size, total_items)
                    progress_callback(processed_so_far, total_items)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {str(e)}")
        
        # Log final summary
        logger.info(
            f"Batch processing complete: {successful_count}/{total_items} successful, "
            f"{failed_count} failed, {batches_processed} batches processed, "
            f"{batches_failed} batches failed"
        )
        
        return {
            'total': total_items,
            'successful': successful_count,
            'failed': failed_count,
            'errors': errors,
            'batches_processed': batches_processed,
            'batches_failed': batches_failed
        }
    
    def split_into_batches(self, items: List[Any]) -> List[List[Any]]:
        """
        Split a list of items into batches.
        
        This is a utility method if you want to manually handle batch processing.
        
        Args:
            items (List[Any]): List of items to split
        
        Returns:
            List[List[Any]]: List of batches, each containing up to batch_size items
        
        Example:
            manager = BatchTransactionManager(batch_size=100)
            batches = manager.split_into_batches(my_items)
            
            for batch in batches:
                # Process batch manually
                pass
        """
        batches = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            batches.append(batch)
        
        return batches
