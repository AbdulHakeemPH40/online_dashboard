from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class IntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integration'
    
    def ready(self):
        """Import signals and initialize database settings when app is ready"""
        import integration.signals  # noqa
        
        # Initialize SQLite WAL mode for better concurrent write handling
        self._initialize_sqlite_wal_mode()
    
    def _initialize_sqlite_wal_mode(self):
        """
        Enable SQLite WAL (Write-Ahead Logging) mode for better concurrent access.
        
        WAL mode benefits:
        - Allows concurrent reads while writing
        - Better performance for write operations
        - Improved crash recovery
        
        This runs once when Django starts up.
        """
        try:
            from django.db import connection
            from django.conf import settings
            
            # Only apply to SQLite databases
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                with connection.cursor() as cursor:
                    # Enable WAL mode
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    result = cursor.fetchone()
                    logger.info(f"SQLite journal_mode set to: {result[0]}")
                    
                    # Set busy timeout (30 seconds = 30000 milliseconds)
                    cursor.execute("PRAGMA busy_timeout=30000;")
                    logger.info("SQLite busy_timeout set to 30000ms (30 seconds)")
                    
                    # Set synchronous mode to NORMAL for better performance
                    # (FULL is safer but slower, NORMAL is good balance)
                    cursor.execute("PRAGMA synchronous=NORMAL;")
                    logger.info("SQLite synchronous mode set to NORMAL")
                    
                    # Set WAL autocheckpoint to 1000 pages to manage WAL file size
                    cursor.execute("PRAGMA wal_autocheckpoint=1000;")
                    logger.info("SQLite wal_autocheckpoint set to 1000 pages")
                    
                    logger.info("✅ SQLite WAL mode initialized successfully")
        
        except Exception as e:
            # Log error but don't crash the application
            logger.error(f"Failed to initialize SQLite WAL mode: {str(e)}", exc_info=True)
            logger.warning("Application will continue with default SQLite settings")
