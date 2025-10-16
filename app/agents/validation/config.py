"""
Validation Configuration
Thresholds and settings for content validation
"""

from typing import Dict, Any


class ValidationConfig:
    """Configuration for validation thresholds and requirements"""
    
    # Safety settings
    SAFETY_REQUIRED = True
    ALLOW_MATURE_EDUCATIONAL_CONTENT = True  # For appropriate topics like history, science
    
    # Quality thresholds
    MIN_QUALITY_SCORE = 0.6
    MIN_QUALITY_SCORE_STRICT = 0.8  # For premium content or exams
    
    # Accuracy thresholds
    MIN_ACCURACY_SCORE = 0.7
    MIN_ACCURACY_SCORE_STRICT = 0.9  # For exam generation
    
    # Retry settings
    MAX_VALIDATION_RETRIES = 2
    RETRY_WITH_CORRECTIONS = True
    ENABLE_VALIDATION = True  # Master switch to enable/disable validation
    
    # Content type specific settings
    VALIDATION_REQUIREMENTS = {
        "flashcard_generation": {
            "require_accuracy": True,
            "require_quality": True,
            "require_safety": True,
            "min_accuracy": 0.75,
            "min_quality": 0.7,
            "max_retries": 2
        },
        "quiz_generation": {
            "require_accuracy": True,
            "require_quality": True,
            "require_safety": True,
            "min_accuracy": 0.85,
            "min_quality": 0.75,
            "max_retries": 2
        },
        "exam_generation": {
            "require_accuracy": True,
            "require_quality": True,
            "require_safety": True,
            "min_accuracy": 0.9,
            "min_quality": 0.85,
            "max_retries": 2
        },
        "summary_generation": {
            "require_accuracy": True,
            "require_quality": True,
            "require_safety": True,
            "min_accuracy": 0.8,
            "min_quality": 0.7,
            "max_retries": 2
        },
        "chat": {
            "require_accuracy": False,  # Chat is conversational, not fact-checked
            "require_quality": False,   # More lenient for chat
            "require_safety": True,     # Safety always required
            "min_accuracy": 0.6,
            "min_quality": 0.5,
            "max_retries": 1
        }
    }
    
    @classmethod
    def get_requirements(cls, content_type: str) -> Dict[str, Any]:
        """
        Get validation requirements for a specific content type.
        
        Args:
            content_type: Type of content being validated
            
        Returns:
            Dictionary with validation requirements
        """
        return cls.VALIDATION_REQUIREMENTS.get(
            content_type,
            {
                "require_accuracy": True,
                "require_quality": True,
                "require_safety": True,
                "min_accuracy": cls.MIN_ACCURACY_SCORE,
                "min_quality": cls.MIN_QUALITY_SCORE,
                "max_retries": cls.MAX_VALIDATION_RETRIES
            }
        )
    
    @classmethod
    def should_validate(cls, content_type: str) -> bool:
        """Check if validation is enabled for this content type"""
        if not cls.ENABLE_VALIDATION:
            return False
        return True
    
    @classmethod
    def get_max_retries(cls, content_type: str) -> int:
        """Get maximum retry attempts for content type"""
        requirements = cls.get_requirements(content_type)
        return requirements.get("max_retries", cls.MAX_VALIDATION_RETRIES)
    
    @classmethod
    def passes_validation(
        cls,
        content_type: str,
        safety_score: float = 1.0,
        quality_score: float = 1.0,
        accuracy_score: float = 1.0,
        is_safe: bool = True
    ) -> tuple[bool, str]:
        """
        Check if content passes validation requirements.
        
        Args:
            content_type: Type of content
            safety_score: Safety score (0.0-1.0)
            quality_score: Quality score (0.0-1.0)
            accuracy_score: Accuracy score (0.0-1.0)
            is_safe: Whether content is safe
            
        Returns:
            Tuple of (passes, reason)
        """
        requirements = cls.get_requirements(content_type)
        
        # Safety is always mandatory
        if requirements.get("require_safety", True) and not is_safe:
            return False, "Content failed safety check"
        
        # Check quality
        if requirements.get("require_quality", True):
            min_quality = requirements.get("min_quality", cls.MIN_QUALITY_SCORE)
            if quality_score < min_quality:
                return False, f"Quality score {quality_score:.2f} below minimum {min_quality:.2f}"
        
        # Check accuracy
        if requirements.get("require_accuracy", True):
            min_accuracy = requirements.get("min_accuracy", cls.MIN_ACCURACY_SCORE)
            if accuracy_score < min_accuracy:
                return False, f"Accuracy score {accuracy_score:.2f} below minimum {min_accuracy:.2f}"
        
        return True, "All validation checks passed"
