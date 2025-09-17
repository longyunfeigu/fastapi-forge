"""Storage service entry point and lifecycle management."""
from typing import Optional
from functools import lru_cache

from core.config import settings
from core.logging_config import get_logger
from .base import StorageProvider
from .config import StorageConfig, StorageType
from .factory import create_provider
from .utils import (
    LoggingMiddleware,
    ValidationMiddleware,
    apply_middleware
)

logger = get_logger(__name__)

# Global storage client instance
_storage_client: Optional[StorageProvider] = None


@lru_cache
def get_storage_config() -> StorageConfig:
    """Get storage configuration from settings.
    
    Assembles StorageConfig from core.config.settings to maintain
    single source of truth for configuration.
    
    Returns:
        Storage configuration instance
    """
    config_dict = {
        "type": getattr(settings, "STORAGE_TYPE", StorageType.LOCAL),
        "bucket": getattr(settings, "STORAGE_BUCKET", None),
        "region": getattr(settings, "STORAGE_REGION", None),
        "endpoint": getattr(settings, "STORAGE_ENDPOINT", None),
        "public_base_url": getattr(settings, "STORAGE_PUBLIC_BASE_URL", None),
        
        # S3 specific
        "aws_access_key_id": getattr(settings, "AWS_ACCESS_KEY_ID", None),
        "aws_secret_access_key": getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        "s3_sse": getattr(settings, "S3_SSE", None),
        "s3_acl": getattr(settings, "S3_ACL", "private"),
        
        # OSS specific
        "oss_access_key_id": getattr(settings, "OSS_ACCESS_KEY_ID", None),
        "oss_access_key_secret": getattr(settings, "OSS_ACCESS_KEY_SECRET", None),
        
        # Local specific
        "local_base_path": getattr(settings, "STORAGE_LOCAL_BASE_PATH", "/tmp/storage"),
        
        # Advanced settings
        "max_retry_attempts": getattr(settings, "STORAGE_MAX_RETRY_ATTEMPTS", 3),
        "timeout": getattr(settings, "STORAGE_TIMEOUT", 30),
        "enable_ssl": getattr(settings, "STORAGE_ENABLE_SSL", True),
        "presign_max_size": getattr(settings, "STORAGE_PRESIGN_MAX_SIZE", 100 * 1024 * 1024),
        "presign_content_types": getattr(
            settings,
            "STORAGE_PRESIGN_CONTENT_TYPES",
            [
                "image/jpeg", "image/png", "image/gif", "image/webp",
                "application/pdf", "video/mp4", "audio/mpeg"
            ]
        )
    }
    
    return StorageConfig(**config_dict)


async def init_storage_client() -> None:
    """Initialize storage client.
    
    Creates and configures the storage provider based on configuration.
    Similar pattern to redis_client.py for consistency.
    """
    global _storage_client
    
    if _storage_client is not None:
        logger.warning("Storage client already initialized")
        return
    
    try:
        config = get_storage_config()
        
        # Create provider
        provider = await create_provider(config)
        
        # Apply middleware
        middlewares = []
        
        # Add logging middleware
        middlewares.append(LoggingMiddleware())
        
        # Add validation middleware if configured
        if hasattr(settings, "STORAGE_VALIDATION_ENABLED") and settings.STORAGE_VALIDATION_ENABLED:
            max_size = getattr(settings, "STORAGE_MAX_FILE_SIZE", 100 * 1024 * 1024)
            allowed_types = getattr(settings, "STORAGE_ALLOWED_TYPES", None)
            middlewares.append(ValidationMiddleware(max_size, allowed_types))
        
        # Apply middleware
        _storage_client = apply_middleware(provider, middlewares)
        
        logger.info(
            "Storage client initialized",
            provider=config.type,
            bucket=config.bucket
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize storage client", error=str(e))
        raise


def get_storage_client() -> Optional[StorageProvider]:
    """Get storage client instance.
    
    Returns:
        Storage provider instance or None if not initialized
    """
    return _storage_client


async def shutdown_storage_client() -> None:
    """Shutdown storage client.
    
    Performs cleanup for storage provider.
    """
    global _storage_client
    
    if _storage_client is None:
        return
    
    try:
        # Perform any cleanup if needed
        # Most providers don't need explicit cleanup
        logger.info("Storage client shutdown")
    except Exception as e:
        logger.error(f"Error during storage shutdown", error=str(e))
    finally:
        _storage_client = None


async def get_storage() -> StorageProvider:
    """FastAPI dependency for storage service.
    
    Returns:
        Storage provider instance
        
    Raises:
        RuntimeError: If storage not initialized
    """
    client = get_storage_client()
    if client is None:
        raise RuntimeError(
            "Storage client not initialized. "
            "Call init_storage_client() during startup."
        )
    return client


# Export public interface
__all__ = [
    # Lifecycle
    "init_storage_client",
    "get_storage_client",
    "shutdown_storage_client",
    "get_storage",
    
    # Configuration
    "get_storage_config",
    "StorageConfig",
    "StorageType",
    
    # Base types
    "StorageProvider",
    
    # Models
    "UploadResult",
    "StorageObject",
    "StorageMetadata",
    "PresignedRequest",
    
    # Exceptions
    "StorageError",
    "NotFoundError",
    "PermissionDeniedError",
    "TransientError",
    "ConfigurationError",
    "ValidationError",
    
    # Utils
    "key_builder",
    "guess_content_type",
    "safe_join",
]

# Import models and exceptions for easier access
from .models import (
    UploadResult,
    StorageObject,
    StorageMetadata,
    PresignedRequest
)
from .exceptions import (
    StorageError,
    NotFoundError,
    PermissionDeniedError,
    TransientError,
    ConfigurationError,
    ValidationError
)
from .utils import (
    key_builder,
    guess_content_type,
    safe_join
)
