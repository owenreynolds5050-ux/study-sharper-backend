"""
Improved AI Chat Service - With loop prevention, multi-model optimization, and context tracking
"""

from typing import List, Dict, Any, Optional
from app.services.open_router import get_chat_completion
from app.services.embeddings import get_embedding_for_text
from app.services.model_manager import get_appropriate_model
from app.services.conversation_manager import (
    ConversationState,
    get_conversation_state,
    save_conversation_state,
    extract_subjects_from_notes,
    extract_topics_from_subject
)
from app.services.flashcard_verification import sanitize_ai_response
import re
import json
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ENHANCED SYSTEM PROMPT
# ============================================================================

FLASHCARD_ASSISTANT_SYSTEM_PROMPT = """
You are an AI study assistant for Study Sharper, specializing in creating high-quality flashcards for high school and college students.

CORE BEHAVIOR RULES:
1. Be concise: 2-3 sentences maximum per response
2. Be helpful and encouraging with a friendly yet professional tone
3. Always use proper grammar and punctuation
4. Minimize emoji use - occasional use is fine, but don't overdo it
5. NEVER show JSON, code blocks, or structured data formats to users
6. Remember conversation context - never ask the same question twice
7. After 2 clarification questions, generate flashcards even if some details are missing

DECISION-MAKING LOGIC:
- If you have enough information to generate flashcards (subject specified OR user confirmed generic), START GENERATING immediately
- Don't ask unnecessary questions if context provides the answer
- Track what user has already told you and never ask for it again
- If user has multiple subjects, remember which one is currently being discussed

HANDLING NO NOTES SCENARIO:
When user has no notes uploaded:
✅ GOOD: "I don't have any [subject] notes from you yet. I can create generic flashcards, but they'll be much more effective once you upload your class materials. Would you like me to proceed with generic content?"
❌ BAD: Asking multiple times about notes or generic content

HANDLING GENERIC FLASHCARD REQUEST:
- Mention once that notes improve quality
- Offer option to proceed with generic
- Once user confirms, proceed immediately without asking again

MULTI-SET SESSIONS:
- User may request multiple flashcard sets for different subjects in one conversation
- When starting a new set, briefly confirm the new subject but don't re-ask questions you already asked
- Example: "Got it! Switching to biology flashcards now. How many cards would you like?"

CONVERSATION EFFICIENCY:
- Maximum 2 clarifying questions before generating
- If you can infer details from context, do so rather than asking
- Default to 10-15 flashcards if quantity not specified

TONE EXAMPLES:
✅ "Perfect! I'll create 12 chemistry flashcards from your notes on chemical bonding."
✅ "I don't see biology notes yet. Want generic biology cards or prefer to upload notes first?"
✅ "I have what I need! Your flashcards are being generated now - this may take a moment to ensure accuracy."

Remember: You're a study partner, not a robot. Be warm, efficient, and genuinely helpful. Act decisively when you have enough information.
"""

# ============================================================================
# CONTENT MODERATION
# ============================================================================

INAPPROPRIATE_KEYWORDS = [
    "hack", "cheat", "plagiarize", "write my essay", "do my homework",
    "illegal", "drug", "weapon", "violence", "explicit"
]

OUT_OF_SCOPE_PATTERNS = [
    r"write\s+(my|an|the)\s+essay",
    r"do\s+my\s+homework",
    r"solve\s+this\s+problem\s+for\s+me",
    r"give\s+me\s+the\s+answers?",
]


async def validate_request(prompt: str, chatbot_type: str) -> Dict[str, Any]:
    """Check if request is appropriate and within app capabilities."""
    prompt_lower = prompt.lower()
    
    # Check inappropriate content
    for keyword in INAPPROPRIATE_KEYWORDS:
        if keyword in prompt_lower:
            return {
                "valid": False,
                "reason": "inappropriate_content",
                "suggested_response": "I'm here to help with studying! Let's keep our conversation focused on academic topics. How can I assist with your study materials?"
            }
    
    # Check out of scope
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, prompt_lower):
            return {
                "valid": False,
                "reason": "out_of_scope",
                "suggested_response": "I'm designed to help you learn and create study tools like flashcards, quizzes, and summaries. I can't complete assignments for you, but I can help you prepare to do them yourself! What study materials would you like to create?"
            }
    
    # Check too short
    if len(prompt.strip()) < 3:
        return {
            "valid": False,
            "reason": "too_short",
            "suggested_response": "I didn't quite catch that. Could you tell me what kind of study materials you'd like to create?"
        }
    
    return {"valid": True, "reason": "valid"}


# ============================================================================
# RAG - RETRIEVE RELEVANT NOTES
# ============================================================================

async def retrieve_relevant_notes(
    user_id: str,
    query: str,
    supabase,
    subject_filter: Optional[str] = None,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Use vector embeddings to find most relevant notes."""
    try:
        # Generate query embedding
        embedding_result = get_embedding_for_text(query)
        query_embedding = embedding_result["embedding"]
        
        # Perform vector similarity search
        response = supabase.rpc("search_similar_notes", {
            "query_embedding": query_embedding,
            "match_threshold": 0.5,
            "match_count": top_k,
            "p_user_id": user_id
        }).execute()
        
        notes = response.data or []
        
        # Apply subject filter if specified
        if subject_filter and notes:
            subject_lower = subject_filter.lower()
            notes = [n for n in notes if n.get("subject", "").lower() == subject_lower]
        
        return notes
        
    except Exception as e:
        logger.error(f"Error retrieving relevant notes: {str(e)}")
        # Fallback: return recent notes
        try:
            fallback = supabase.table("notes").select(
                "id, title, content, extracted_text, subject, folder_id, created_at"
            ).eq("user_id", user_id).order(
                "created_at", desc=True
            ).limit(top_k).execute()
            
            return fallback.data or []
        except:
            return []


# ============================================================================
# INTENT ANALYSIS
# ============================================================================

async def analyze_user_intent(
    prompt: str,
    conversation_state: ConversationState,
    available_notes: List[Dict[str, Any]],
    model: str
) -> Dict[str, Any]:
    """Analyze what the user wants, considering conversation history."""
    
    # Build context about what we already know
    known_info = []
    if conversation_state.subject:
        known_info.append(f"Subject: {conversation_state.subject}")
    if conversation_state.quantity:
        known_info.append(f"Quantity: {conversation_state.quantity}")
    if conversation_state.user_confirmed_generic:
        known_info.append("User confirmed generic flashcards")
    
    known_context = "\n".join(known_info) if known_info else "No information gathered yet"
    
    # Extract available subjects
    available_subjects = extract_subjects_from_notes(available_notes)
    
    analysis_prompt = f"""
Analyze this user message in the context of an ongoing flashcard generation conversation.

User message: "{prompt}"

What we already know:
{known_context}

Available subjects in user's notes: {available_subjects if available_subjects else "No notes uploaded"}

Extract from the NEW message:
1. Subject mentioned (if any) - only if explicitly stated
2. Quantity mentioned (if any) - look for numbers like "10", "fifteen", etc.
3. Confirmation of generic content - did user say "yes", "proceed", "go ahead", etc.?
4. Topic within subject (if any)

Respond ONLY with valid JSON:
{{
    "subject": "subject name or null",
    "quantity": number or null,
    "confirmed_generic": true or false,
    "topic": "specific topic or null"
}}
"""
    
    try:
        response = get_chat_completion([
            {"role": "system", "content": "You are a precise intent analyzer. Always respond with valid JSON only."},
            {"role": "user", "content": analysis_prompt}
        ], model=model)
        
        # Parse JSON response
        response_clean = response.strip()
        if "```json" in response_clean:
            response_clean = response_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in response_clean:
            response_clean = response_clean.split("```")[1].split("```")[0].strip()
        
        analysis = json.loads(response_clean)
        
        logger.info(f"Intent analysis: {analysis}")
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing intent: {str(e)}")
        # Fallback to basic parsing
        return {
            "subject": None,
            "quantity": None,
            "confirmed_generic": any(word in prompt.lower() for word in ["yes", "proceed", "go ahead", "sure", "ok"]),
            "topic": None
        }


# ============================================================================
# CONTEXTUAL PROMPT GENERATION
# ============================================================================

def generate_contextual_prompts(
    conversation_state: ConversationState,
    user_notes: List[Dict[str, Any]]
) -> List[str]:
    """
    Generate 3-4 prompts that adapt to conversation state.
    CRITICAL: Prompts must NEVER be the same as previous recommendations.
    """
    
    prompts = []
    
    # SCENARIO 1: Subject not yet specified
    if not conversation_state.subject:
        if conversation_state.has_notes:
            # Suggest specific subjects from their notes
            subjects = extract_subjects_from_notes(user_notes, limit=3)
            prompts = [f"Create flashcards for {subj}" for subj in subjects]
        else:
            # Generic subject suggestions
            prompts = [
                "Make me 10 biology flashcards",
                "Create chemistry study cards",
                "Generate 15 history flashcards"
            ]
    
    # SCENARIO 2: Subject specified, asking about quantity or generic confirmation
    elif conversation_state.subject:
        subject = conversation_state.subject
        
        if not conversation_state.has_notes and not conversation_state.user_confirmed_generic:
            # User being asked about generic content
            prompts = [
                "Yes, proceed with generic content",
                "Let me upload my notes first",
                f"Make 10 {subject} flashcards now"
            ]
        else:
            # Asking about details (quantity, topics, etc.)
            if conversation_state.has_notes:
                # Extract specific topics from their subject notes
                topics = extract_topics_from_subject(user_notes, subject, limit=3)
                prompts = [
                    f"Focus on {topics[0]}",
                    f"Create 15 cards covering {topics[1] if len(topics) > 1 else 'all topics'}",
                    f"Make flashcards for all {subject} topics"
                ]
            else:
                # Generic prompts for specified subject
                prompts = [
                    f"Make 10 {subject} flashcards",
                    f"Create 20 {subject} cards",
                    "Yes, that's perfect"
                ]
    
    # SCENARIO 3: Almost ready to generate - give action-oriented prompts
    elif conversation_state.has_enough_info_to_generate():
        prompts = [
            "Yes, generate them now",
            "Make it 15 cards instead",
            "Add more detail to each card"
        ]
    
    # Ensure we always return 3-4 unique prompts
    return prompts[:4] if prompts else ["Create flashcards", "Generate study materials", "Help me study"]


# ============================================================================
# SMART CLARIFICATION GENERATION
# ============================================================================

async def generate_smart_clarification(
    model: str,
    conversation_state: ConversationState,
    user_notes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate contextual clarification questions and recommended prompts.
    Key: Prompts must CHANGE based on conversation state and NEVER repeat.
    """
    
    # Determine what information is still missing
    missing_info = []
    if not conversation_state.subject:
        missing_info.append("subject")
    if not conversation_state.quantity:
        missing_info.append("quantity")
    
    # Generate clarification message based on what's missing
    if "subject" in missing_info:
        conversation_state.add_question_asked("subject")
        
        if conversation_state.has_notes:
            # User has notes - suggest subjects from their notes
            available_subjects = extract_subjects_from_notes(user_notes)
            message = f"I'd love to help! Which subject should I focus on: {', '.join(available_subjects[:3])}?"
        else:
            # No notes - ask for subject
            message = "I'd be happy to create flashcards for you! Which subject or topic should I focus on?"
    
    elif not conversation_state.has_notes and not conversation_state.user_confirmed_generic:
        conversation_state.add_question_asked("generic_confirmation")
        
        # User specified subject but has no notes
        message = f"I don't have any {conversation_state.subject} notes from you yet. I can create generic {conversation_state.subject} flashcards, but they'll be much more effective once you upload your class materials. Would you like me to proceed with generic content?"
    
    else:
        # Just need minor details - but don't ask if we're at max questions
        if conversation_state.should_ask_clarification():
            conversation_state.add_question_asked("quantity")
            message = f"Great! How many {conversation_state.subject} flashcards would you like? (I recommend 10-15 for focused study)"
        else:
            # Max questions reached - proceed with defaults
            message = f"I have what I need! Your {conversation_state.subject} flashcards are being generated now."
            conversation_state.ready_to_generate = True
    
    # Generate CONTEXT-AWARE recommended prompts
    recommended_prompts = generate_contextual_prompts(
        conversation_state=conversation_state,
        user_notes=user_notes
    )
    
    return {
        "message": sanitize_ai_response(message),
        "recommended_prompts": recommended_prompts
    }


# ============================================================================
# MAIN CONVERSATION PROCESSING
# ============================================================================

async def process_chat_message(
    user_message: str,
    conversation_state: ConversationState,
    user_notes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Main conversation processing with loop prevention.
    """
    
    # Update has_notes flag
    conversation_state.has_notes = len(user_notes) > 0
    
    # Determine which model to use
    is_first_message = conversation_state.turns_count == 0
    model = get_appropriate_model(
        conversation_stage="conversation",
        context={
            "is_first_message": is_first_message,
            "ready_to_generate": False,
            "validating_flashcard": False
        }
    )
    
    logger.info(f"Processing message (turn {conversation_state.turns_count + 1}) with model: {model}")
    
    # Analyze user intent
    intent_analysis = await analyze_user_intent(
        prompt=user_message,
        conversation_state=conversation_state,
        available_notes=user_notes,
        model=model
    )
    
    # Update conversation state
    conversation_state.update_from_user_message(
        message=user_message,
        extracted_info=intent_analysis
    )
    
    # Save state
    save_conversation_state(conversation_state)
    
    # Decide on action
    if conversation_state.has_enough_info_to_generate():
        # GENERATE FLASHCARDS
        conversation_state.ready_to_generate = True
        save_conversation_state(conversation_state)
        
        return {
            "action": "generate_flashcards",
            "message": sanitize_ai_response("I have everything I need! Your flashcards are being generated now. This may take a moment as I ensure each card is accurate and helpful."),
            "recommended_prompts": [],  # No prompts during generation
            "state": conversation_state
        }
    
    elif not conversation_state.should_ask_clarification():
        # Forced generation after max questions
        conversation_state.ready_to_generate = True
        save_conversation_state(conversation_state)
        
        subject_text = conversation_state.subject or "study"
        return {
            "action": "generate_flashcards",
            "message": sanitize_ai_response(f"I'll create flashcards based on what we've discussed. Your {subject_text} flashcards are being generated now!"),
            "recommended_prompts": [],
            "state": conversation_state
        }
    
    else:
        # ASK CLARIFYING QUESTION
        clarification = await generate_smart_clarification(
            model=model,
            conversation_state=conversation_state,
            user_notes=user_notes
        )
        
        save_conversation_state(conversation_state)
        
        return {
            "action": "clarify",
            "message": clarification["message"],
            "recommended_prompts": clarification["recommended_prompts"],
            "state": conversation_state
        }
