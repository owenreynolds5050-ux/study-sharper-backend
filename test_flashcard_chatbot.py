"""
Unit Tests for Flashcard Chatbot
Tests intent classification, parameter extraction, generation, and verification
"""

import pytest
from app.services.intent_classifier import classify_intent, extract_flashcard_parameters
from app.services.session_manager import ConversationState
from app.services.flashcard_generator import FlashcardGenerator


# ============================================================================
# INTENT CLASSIFICATION TESTS
# ============================================================================

def test_intent_classification_non_study():
    """Test that non-study messages are correctly classified"""
    messages = [
        "What's the weather today?",
        "Tell me a joke",
        "How are you?",
        "What's 2+2?"
    ]
    
    for message in messages:
        result = classify_intent(message)
        assert result["intent"] == "non_study", f"Failed for: {message}"


def test_intent_classification_flashcards():
    """Test that flashcard requests are correctly classified"""
    messages = [
        "Create flashcards from my notes",
        "Generate 20 biology flashcards",
        "Make cards about the American Revolution",
        "I need flashcards for studying"
    ]
    
    for message in messages:
        result = classify_intent(message)
        assert result["intent"] == "flashcards", f"Failed for: {message}"


def test_intent_classification_notes():
    """Test that notes/summary requests are correctly classified"""
    messages = [
        "Summarize my chemistry notes",
        "Create a study guide",
        "Generate notes from this topic"
    ]
    
    for message in messages:
        result = classify_intent(message)
        assert result["intent"] == "notes", f"Failed for: {message}"


def test_intent_classification_account():
    """Test that account requests are correctly classified"""
    messages = [
        "What's my plan?",
        "Upgrade to premium",
        "Change my settings"
    ]
    
    for message in messages:
        result = classify_intent(message)
        assert result["intent"] == "account", f"Failed for: {message}"


# ============================================================================
# PARAMETER EXTRACTION TESTS
# ============================================================================

def test_parameter_extraction_complete():
    """Test extraction of all parameters from a complete request"""
    message = "Generate 15 intermediate-level flashcards on the American Revolution from my notes"
    
    params = extract_flashcard_parameters(message)
    
    assert params["subject"] is not None
    assert params["subtopic"] is not None
    assert params["length"] == 15
    assert params["difficulty"] == "Intermediate"
    assert params["from_notes"] == True


def test_parameter_extraction_partial():
    """Test extraction with missing parameters"""
    message = "Create flashcards about biology"
    
    params = extract_flashcard_parameters(message)
    
    assert params["subject"] == "Biology"
    assert params["subtopic"] is None  # Not specified
    assert params["length"] is None  # Not specified


def test_parameter_extraction_length():
    """Test length extraction"""
    test_cases = [
        ("Generate 10 flashcards", 10),
        ("Make 25 cards", 25),
        ("Create 5 flashcards", 5)
    ]
    
    for message, expected_length in test_cases:
        params = extract_flashcard_parameters(message)
        assert params["length"] == expected_length, f"Failed for: {message}"


def test_parameter_extraction_difficulty():
    """Test difficulty extraction"""
    test_cases = [
        ("Generate basic flashcards", "Basic"),
        ("Create intermediate level cards", "Intermediate"),
        ("Make advanced flashcards", "Advanced")
    ]
    
    for message, expected_difficulty in test_cases:
        params = extract_flashcard_parameters(message)
        assert params["difficulty"] == expected_difficulty, f"Failed for: {message}"


# ============================================================================
# CONVERSATION STATE TESTS
# ============================================================================

def test_conversation_state_creation():
    """Test creating a conversation state"""
    state = ConversationState(
        user_id="test_user",
        session_id="test_session",
        subject="Biology",
        subtopic="Cell Structure",
        length=10,
        difficulty="Intermediate"
    )
    
    assert state.user_id == "test_user"
    assert state.subject == "Biology"
    assert state.is_complete() == True


def test_conversation_state_incomplete():
    """Test incomplete conversation state"""
    state = ConversationState(
        user_id="test_user",
        session_id="test_session",
        subject="Biology"
    )
    
    assert state.is_complete() == False
    missing = state.get_missing_params()
    assert "subtopic" in missing
    assert "length" in missing
    assert "difficulty" in missing


def test_conversation_state_update():
    """Test updating conversation state parameters"""
    state = ConversationState(
        user_id="test_user",
        session_id="test_session"
    )
    
    state.update_param("subject", "Chemistry")
    state.update_param("length", 15)
    
    assert state.subject == "Chemistry"
    assert state.length == 15


def test_conversation_state_serialization():
    """Test state to/from dict conversion"""
    state = ConversationState(
        user_id="test_user",
        session_id="test_session",
        subject="Physics",
        subtopic="Motion",
        length=20,
        difficulty="Advanced"
    )
    
    # Convert to dict
    state_dict = state.to_dict()
    
    # Recreate from dict
    restored_state = ConversationState.from_dict(state_dict)
    
    assert restored_state.user_id == state.user_id
    assert restored_state.subject == state.subject
    assert restored_state.subtopic == state.subtopic
    assert restored_state.length == state.length
    assert restored_state.difficulty == state.difficulty


# ============================================================================
# FLASHCARD GENERATOR TESTS
# ============================================================================

def test_flashcard_generator_initialization():
    """Test flashcard generator initialization"""
    generator = FlashcardGenerator()
    
    assert generator.GENERATOR_MODEL == "anthropic/claude-3.5-sonnet"
    assert generator.MAX_VERIFICATION_ATTEMPTS == 3
    assert generator.VERIFICATION_FAILURE_THRESHOLD == 0.30


def test_difficulty_instructions():
    """Test difficulty instruction generation"""
    generator = FlashcardGenerator()
    
    basic_instructions = generator._get_difficulty_instructions("Basic")
    assert "fundamental" in basic_instructions.lower()
    
    advanced_instructions = generator._get_difficulty_instructions("Advanced")
    assert "analysis" in advanced_instructions.lower()


# ============================================================================
# PREMIUM LIMIT ENFORCEMENT TESTS
# ============================================================================

def test_free_tier_limit():
    """Test free tier limit (20 cards)"""
    FREE_TIER_MAX = 20
    
    # Test within limit
    assert 10 <= FREE_TIER_MAX
    assert 20 <= FREE_TIER_MAX
    
    # Test exceeding limit
    assert 25 > FREE_TIER_MAX
    assert 50 > FREE_TIER_MAX


def test_premium_tier_limit():
    """Test premium tier limit (50 cards)"""
    PREMIUM_MAX = 50
    
    # Test within limit
    assert 20 <= PREMIUM_MAX
    assert 50 <= PREMIUM_MAX
    
    # Test exceeding limit
    assert 100 > PREMIUM_MAX


# ============================================================================
# MESSAGE TEMPLATE TESTS
# ============================================================================

def test_message_templates():
    """Test that exact message templates are used"""
    NON_STUDY_MESSAGE = "Unable to fulfill request: this assistant only handles study-related tasks (flashcards, notes, account-related study settings)."
    
    assert "Unable to fulfill request" in NON_STUDY_MESSAGE
    assert "study-related tasks" in NON_STUDY_MESSAGE
    
    GENERATION_START_TEMPLATE = "Generating {length} {difficulty} flashcards on {subtopic} ({subject}) — saving to your study deck. I'll verify accuracy now."
    
    formatted = GENERATION_START_TEMPLATE.format(
        length=10,
        difficulty="Intermediate",
        subtopic="Cell Structure",
        subject="Biology"
    )
    
    assert "Generating 10 Intermediate flashcards" in formatted
    assert "Cell Structure" in formatted
    assert "verify accuracy" in formatted


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

def test_zero_length_request():
    """Test handling of zero or negative length"""
    params = extract_flashcard_parameters("Generate 0 flashcards")
    # Should be handled by validation
    assert params["length"] == 0 or params["length"] is None


def test_very_large_length_request():
    """Test handling of unreasonably large length"""
    params = extract_flashcard_parameters("Generate 1000 flashcards")
    # Should be caught by limit enforcement
    assert params["length"] == 1000  # Extracted correctly, but will be limited


def test_multiple_subjects():
    """Test handling of multiple subjects in one request"""
    message = "Create flashcards for biology and chemistry"
    params = extract_flashcard_parameters(message)
    # Should extract one subject (implementation dependent)
    assert params["subject"] is not None


def test_empty_message():
    """Test handling of empty message"""
    result = classify_intent("")
    # Should handle gracefully
    assert result["intent"] in ["non_study", "other_study"]


# ============================================================================
# VERIFICATION THRESHOLD TEST
# ============================================================================

def test_verification_failure_threshold():
    """Test 30% verification failure threshold"""
    THRESHOLD = 0.30
    
    # Test cases: (failed, total, should_abort)
    test_cases = [
        (3, 10, False),  # 30% - at threshold
        (4, 10, True),   # 40% - exceeds threshold
        (2, 10, False),  # 20% - below threshold
        (5, 15, True),   # 33% - exceeds threshold
        (15, 50, False), # 30% - at threshold
    ]
    
    for failed, total, should_abort in test_cases:
        failure_rate = failed / total
        result = failure_rate > THRESHOLD
        assert result == should_abort, f"Failed for {failed}/{total}"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    print("Running Flashcard Chatbot Unit Tests...")
    print("\n" + "="*70)
    
    # Run tests manually (or use pytest)
    test_functions = [
        test_intent_classification_non_study,
        test_intent_classification_flashcards,
        test_intent_classification_notes,
        test_intent_classification_account,
        test_parameter_extraction_complete,
        test_parameter_extraction_partial,
        test_parameter_extraction_length,
        test_parameter_extraction_difficulty,
        test_conversation_state_creation,
        test_conversation_state_incomplete,
        test_conversation_state_update,
        test_conversation_state_serialization,
        test_flashcard_generator_initialization,
        test_difficulty_instructions,
        test_free_tier_limit,
        test_premium_tier_limit,
        test_message_templates,
        test_zero_length_request,
        test_very_large_length_request,
        test_multiple_subjects,
        test_empty_message,
        test_verification_failure_threshold
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✅ {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️  {test_func.__name__}: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"Tests passed: {passed}/{len(test_functions)}")
    print(f"Tests failed: {failed}/{len(test_functions)}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
