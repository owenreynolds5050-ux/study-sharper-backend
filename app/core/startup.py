"""
Startup checks and validation
Ensures all required environment variables and dependencies are configured
"""

import logging
import sys
from app.core.config import (
    SUPABASE_URL,
    SUPABASE_KEY,
    OPENROUTER_API_KEY,
    ALLOWED_ORIGINS_LIST
)

logger = logging.getLogger(__name__)


def check_environment_variables() -> bool:
    """
    Validate that all required environment variables are set.
    Returns True if all checks pass, False otherwise.
    """
    missing_vars = []
    warnings = []
    
    # Critical variables
    if not SUPABASE_URL or SUPABASE_URL == "https://your-project.supabase.co":
        missing_vars.append("SUPABASE_URL")
    
    if not SUPABASE_KEY or SUPABASE_KEY == "your-service-role-key-here":
        missing_vars.append("SUPABASE_SERVICE_ROLE_KEY")
    
    # Non-critical but important
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your-openrouter-api-key":
        warnings.append("OPENROUTER_API_KEY not configured - AI features will be limited")
    
    if not ALLOWED_ORIGINS_LIST or ALLOWED_ORIGINS_LIST == ["*"]:
        warnings.append("ALLOWED_ORIGINS not configured - using wildcard (*) which is insecure for production")
    
    # Report findings
    if missing_vars:
        logger.error("=" * 70)
        logger.error("CRITICAL: Missing required environment variables!")
        logger.error("=" * 70)
        for var in missing_vars:
            logger.error(f"  ❌ {var} is not configured")
        logger.error("")
        logger.error("Please set these variables in your .env file or environment.")
        logger.error("See .env.example for reference.")
        logger.error("=" * 70)
        return False
    
    if warnings:
        logger.warning("=" * 70)
        logger.warning("Environment Configuration Warnings:")
        logger.warning("=" * 70)
        for warning in warnings:
            logger.warning(f"  ⚠️  {warning}")
        logger.warning("=" * 70)
    
    # Success
    logger.info("=" * 70)
    logger.info("✅ Environment variables validated successfully")
    logger.info("=" * 70)
    logger.info(f"  Supabase URL: {SUPABASE_URL[:30]}...")
    logger.info(f"  OpenRouter API: {'Configured' if OPENROUTER_API_KEY else 'Missing'}")
    logger.info(f"  CORS Origins: {len(ALLOWED_ORIGINS_LIST)} configured")
    logger.info("=" * 70)
    
    return True


def check_dependencies() -> bool:
    """
    Check that required Python packages are installed.
    Returns True if all checks pass, False otherwise.
    """
    missing_packages = []
    
    try:
        import fastapi
    except ImportError:
        missing_packages.append("fastapi")
    
    try:
        import supabase
    except ImportError:
        missing_packages.append("supabase")
    
    try:
        import jwt
    except ImportError:
        missing_packages.append("pyjwt")
    
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("✅ sentence-transformers available for local embeddings")
    except ImportError:
        logger.warning("⚠️  sentence-transformers not installed - embeddings will use API fallback")
    
    if missing_packages:
        logger.error("=" * 70)
        logger.error("CRITICAL: Missing required Python packages!")
        logger.error("=" * 70)
        for package in missing_packages:
            logger.error(f"  ❌ {package}")
        logger.error("")
        logger.error("Install missing packages with:")
        logger.error(f"  pip install {' '.join(missing_packages)}")
        logger.error("=" * 70)
        return False
    
    return True


def run_startup_checks():
    """
    Run all startup checks.
    Log warnings but don't exit - allow app to start for health checks.
    """
    logger.info("Running startup checks...")
    
    env_ok = check_environment_variables()
    deps_ok = check_dependencies()
    
    if not env_ok or not deps_ok:
        logger.warning("⚠️  Startup checks failed - some features may not work correctly.")
        logger.warning("Please configure environment variables to enable all features.")
        # Don't exit - allow app to start so Railway can check /health endpoint
    else:
        logger.info("✅ All startup checks passed. Application ready.")
