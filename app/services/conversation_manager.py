"""
Conversation State Manager - Prevents loops and tracks conversation context
Ensures AI never asks the same question twice and generates after max 2 clarifications
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ConversationState:
    """Track conversation context to prevent loops and redundant questions."""
    
    user_id: str
    session_id: str
    
    # What we know about the request
    subject: Optional[str] = None
    topic: Optional[str] = None
    quantity: Optional[int] = None
    difficulty: Optional[str] = None
    
    # Conversation tracking
    questions_asked: List[str] = field(default_factory=list)  # Track what we already asked
    topics_mentioned: List[str] = field(default_factory=list)  # Track what user said
    turns_count: int = 0
    
    # Decision flags
    has_notes: bool = False
    user_confirmed_generic: bool = False
    ready_to_generate: bool = False
    
    # Generated content tracking (for multi-set sessions)
    generated_sets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timestamp
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_question_asked(self, question_type: str):
        """Record that we asked this type of question."""
        if question_type not in self.questions_asked:
            self.questions_asked.append(question_type)
            logger.debug(f"Added question type: {question_type}")
    
    def already_asked(self, question_type: str) -> bool:
        """Check if we already asked this."""
        return question_type in self.questions_asked
    
    def update_from_user_message(self, message: str, extracted_info: Dict[str, Any]):
        """Update state based on user's message."""
        self.turns_count += 1
        self.updated_at = datetime.now()
        
        if extracted_info.get("subject"):
            self.subject = extracted_info["subject"]
            self.topics_mentioned.append(extracted_info["subject"])
            logger.info(f"Updated subject to: {self.subject}")
        
        if extracted_info.get("topic"):
            self.topic = extracted_info["topic"]
            logger.info(f"Updated topic to: {self.topic}")
        
        if extracted_info.get("quantity"):
            self.quantity = extracted_info["quantity"]
            logger.info(f"Updated quantity to: {self.quantity}")
        
        if extracted_info.get("difficulty"):
            self.difficulty = extracted_info["difficulty"]
        
        if extracted_info.get("confirmed_generic"):
            self.user_confirmed_generic = True
            logger.info("User confirmed generic flashcards")
    
    def has_enough_info_to_generate(self) -> bool:
        """Determine if we have sufficient information to generate flashcards."""
        
        # Minimum requirements: subject OR confirmation to proceed with generic
        has_subject = self.subject is not None
        confirmed_proceed = self.user_confirmed_generic
        
        # Safety: after 3 turns, we should generate something
        forced_by_turns = self.turns_count >= 3
        
        result = (has_subject or confirmed_proceed) or forced_by_turns
        
        if result:
            logger.info(f"Has enough info to generate: subject={has_subject}, confirmed={confirmed_proceed}, forced={forced_by_turns}")
        
        return result
    
    def should_ask_clarification(self) -> bool:
        """Determine if we should ask another question or just proceed."""
        
        # Don't ask more than 2 clarification questions
        if len(self.questions_asked) >= 2:
            logger.info("Max clarification questions reached (2)")
            return False
        
        # If we have enough info, don't ask
        if self.has_enough_info_to_generate():
            logger.info("Have enough info, no clarification needed")
            return False
        
        return True
    
    def reset_for_new_set(self):
        """Reset state for generating another flashcard set in same session."""
        logger.info(f"Resetting conversation state for new set. Previous subject: {self.subject}")
        
        # Keep user_id, session_id, has_notes, generated_sets
        # Reset request-specific info
        self.subject = None
        self.topic = None
        self.quantity = None
        self.difficulty = None
        self.questions_asked = []
        self.topics_mentioned = []
        self.turns_count = 0
        self.user_confirmed_generic = False
        self.ready_to_generate = False
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "subject": self.subject,
            "topic": self.topic,
            "quantity": self.quantity,
            "difficulty": self.difficulty,
            "questions_asked": self.questions_asked,
            "topics_mentioned": self.topics_mentioned,
            "turns_count": self.turns_count,
            "has_notes": self.has_notes,
            "user_confirmed_generic": self.user_confirmed_generic,
            "ready_to_generate": self.ready_to_generate,
            "generated_sets": self.generated_sets,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationState':
        """Create from dictionary."""
        # Convert ISO strings back to datetime
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        
        return cls(**data)


# In-memory storage for conversation states (replace with Redis/database in production)
_conversation_states: Dict[str, ConversationState] = {}


def get_conversation_state(user_id: str, session_id: str) -> ConversationState:
    """Get or create conversation state for user session."""
    key = f"{user_id}:{session_id}"
    
    if key not in _conversation_states:
        logger.info(f"Creating new conversation state for {key}")
        _conversation_states[key] = ConversationState(
            user_id=user_id,
            session_id=session_id
        )
    
    return _conversation_states[key]


def save_conversation_state(state: ConversationState):
    """Save conversation state."""
    key = f"{state.user_id}:{state.session_id}"
    _conversation_states[key] = state
    logger.debug(f"Saved conversation state for {key}")


def clear_conversation_state(user_id: str, session_id: str):
    """Clear conversation state (e.g., when user explicitly starts over)."""
    key = f"{user_id}:{session_id}"
    if key in _conversation_states:
        del _conversation_states[key]
        logger.info(f"Cleared conversation state for {key}")


def extract_subjects_from_notes(notes: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    """Extract unique subjects from user's notes."""
    subjects = set()
    
    for note in notes:
        # Try to get subject from multiple fields
        if note.get('subject'):
            subjects.add(note['subject'])
        
        # Try folder name as subject
        if note.get('folder_name'):
            subjects.add(note['folder_name'])
        
        # Try extracting from title (e.g., "Biology Chapter 1" -> "Biology")
        title = note.get('title', '')
        if title:
            # Take first word if it looks like a subject
            first_word = title.split()[0] if title.split() else None
            if first_word and len(first_word) > 3 and first_word[0].isupper():
                subjects.add(first_word)
    
    result = list(subjects)[:limit]
    logger.debug(f"Extracted subjects from notes: {result}")
    return result


def extract_topics_from_subject(notes: List[Dict[str, Any]], subject: str, limit: int = 3) -> List[str]:
    """Extract specific topics from notes of a particular subject."""
    topics = set()
    
    # Filter notes by subject (case-insensitive)
    subject_lower = subject.lower()
    subject_notes = [
        n for n in notes 
        if subject_lower in (n.get('title', '') + ' ' + n.get('subject', '')).lower()
    ]
    
    logger.debug(f"Found {len(subject_notes)} notes for subject: {subject}")
    
    # Extract key topics from titles
    for note in subject_notes[:5]:  # Limit to recent 5 notes
        title = note.get('title', '')
        
        # Remove subject name from title to get topic
        title_clean = title.replace(subject, '').strip()
        
        # Extract meaningful phrases
        if title_clean and len(title_clean) > 3:
            # Take first meaningful part
            parts = title_clean.split('-')
            if parts:
                topic = parts[0].strip()
                if len(topic) > 3:
                    topics.add(topic)
    
    result = list(topics)[:limit] if topics else [
        f"{subject} basics", 
        f"{subject} concepts", 
        f"key {subject} terms"
    ]
    
    logger.debug(f"Extracted topics for {subject}: {result}")
    return result
