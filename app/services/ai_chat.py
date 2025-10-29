"""
AI Chat Service - Centralized AI request processing with RAG
Handles validation, intent detection, and response generation for all chatbots
"""

from typing import List, Dict, Any, Optional
from app.services.open_router import get_chat_completion
from app.services.embeddings import get_embedding_for_text
import re
import json
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# SYSTEM PROMPTS
# ============================================================================

STUDY_SHARPER_SYSTEM_PROMPT = """
You are an AI study assistant for Study Sharper, helping high school and college students create effective study materials.

CORE GUIDELINES:
1. Be concise: Limit responses to 2-3 sentences maximum
2. Be helpful and encouraging with a friendly yet professional tone
3. Always be grammatically correct
4. NEVER output JSON, code blocks, or structured data formats - only natural conversational text
5. When user's request doesn't match available content, offer intelligent alternatives

RESPONSE STRUCTURE:
- Start with a direct answer or acknowledgment
- Provide actionable next steps or alternatives if needed
- Keep it brief and scannable

HANDLING MISMATCHES:
When a user requests content for Subject X but only has notes on Subject Y:

❌ BAD: "I don't see any biology notes in the available context. I can only see some history notes..."
✅ GOOD: "I don't see biology notes in your collection yet. Would you like me to create generic biology flashcards, or would you prefer flashcards from your Industrial Revolution notes?"

When user has NO notes at all:

✅ GOOD: "I don't see any notes uploaded yet. I can create generic flashcards on [topic], but they'll be much more personalized and helpful once you upload your class notes. Would you like to proceed with generic flashcards?"

CONVERSATION FLOW:
- If you need clarification, ask ONE focused follow-up question
- Once you have enough information, take action immediately
- Confirm what you're creating before generating it
- Never ask for information you already have from context

TONE EXAMPLES:
✅ "I found your economics notes! I'll create 15 flashcards covering supply and demand concepts."
✅ "I couldn't locate biology notes yet. Should I make flashcards from your chemistry materials instead?"
✅ "To create the best quiz for you, which topics should I focus on: photosynthesis, cell structure, or both?"

Remember: You're a study partner, not a robot. Be warm, clear, and genuinely helpful.
"""

# ============================================================================
# CONTENT MODERATION & VALIDATION
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
    """
    Check if request is appropriate and within app capabilities.
    
    Returns: {
        "valid": bool,
        "reason": str,
        "suggested_response": str
    }
    """
    prompt_lower = prompt.lower()
    
    # Check 1: Content moderation (inappropriate language, harmful requests)
    for keyword in INAPPROPRIATE_KEYWORDS:
        if keyword in prompt_lower:
            return {
                "valid": False,
                "reason": "inappropriate_content",
                "suggested_response": "I'm here to help with studying! Let's keep our conversation focused on academic topics. How can I assist with your study materials?"
            }
    
    # Check 2: Out of scope requests
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, prompt_lower):
            return {
                "valid": False,
                "reason": "out_of_scope",
                "suggested_response": "I'm designed to help you learn and create study tools like flashcards, quizzes, and summaries. I can't complete assignments for you, but I can help you prepare to do them yourself! What study materials would you like to create?"
            }
    
    # Check 3: Empty or too short
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
    """
    Use vector embeddings to find most relevant notes.
    
    Returns: List of notes with metadata (title, subject, folder, content, relevance_score)
    """
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


async def retrieve_relevant_file_chunks(
    user_id: str,
    query: str,
    supabase,
    top_k: int = 5,
    file_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Find the most relevant file chunks for a user query."""
    try:
        embedding_result = get_embedding_for_text(query)
        query_embedding = embedding_result["embedding"]

        params = {
            "query_embedding": query_embedding,
            "match_count": top_k,
            "p_user_id": user_id
        }

        if file_ids:
            params["p_file_ids"] = file_ids

        response = supabase.rpc("search_file_chunks", params).execute()

        chunks = response.data or []

        formatted = []
        for index, chunk in enumerate(chunks[:top_k]):
            chunk_text = chunk.get("text", "").strip()
            file_title = chunk.get("file_title") or chunk.get("title") or "Untitled"
            similarity = chunk.get("similarity") or chunk.get("score")
            formatted.append({
                "rank": index + 1,
                "file_id": chunk.get("file_id"),
                "chunk_id": chunk.get("chunk_id"),
                "file_title": file_title,
                "text": chunk_text,
                "similarity": similarity
            })

        if not formatted:
            return {
                "chunks": [],
                "system_message": "You have access to these relevant notes:\nNo relevant notes found."
            }

        message_lines = ["You have access to these relevant notes:"]
        for item in formatted:
            message_lines.append(f"[{item['rank']}] {item['file_title']}\n{item['text']}")

        system_message = "\n".join(message_lines)

        return {
            "chunks": formatted,
            "system_message": system_message
        }

    except Exception as error:
        logger.error(f"Error retrieving file chunks: {error}")
        return {
            "chunks": [],
            "system_message": "You have access to these relevant notes:\nNo relevant notes found."
        }


# ============================================================================
# INTENT DETECTION & SUBJECT EXTRACTION
# ============================================================================

async def analyze_user_intent(
    prompt: str,
    available_notes: List[Dict[str, Any]],
    chatbot_type: str
) -> Dict[str, Any]:
    """
    Detect what the user wants and extract key information.
    
    Returns: {
        "intent": str,
        "requested_subject": str | None,
        "requested_topic": str | None,
        "available_subjects": List[str],
        "has_matching_content": bool,
        "confidence": float,
        "needs_clarification": bool
    }
    """
    
    # Extract available subjects from notes
    available_subjects = list(set([
        n.get("subject", "General") 
        for n in available_notes 
        if n.get("subject")
    ]))
    
    # Build analysis prompt for LLM
    analysis_prompt = f"""
Analyze this user request and extract key information.

User request: "{prompt}"
Chatbot type: {chatbot_type}
Available subjects in user's notes: {available_subjects if available_subjects else "No notes uploaded yet"}

Extract:
1. Primary intent (what study tool they want: flashcards, quiz, summary, explanation, etc.)
2. Subject/topic mentioned (if any)
3. Specific topic within subject (if mentioned)
4. Confidence level (0.0-1.0)
5. Whether clarification is needed

Respond ONLY with valid JSON in this exact format:
{{
    "intent": "create_flashcards|generate_quiz|create_summary|get_explanation|unclear",
    "requested_subject": "subject name or null",
    "requested_topic": "specific topic or null",
    "confidence": 0.85,
    "needs_clarification": false
}}
"""
    
    try:
        response = get_chat_completion([
            {"role": "system", "content": "You are a precise intent analyzer. Always respond with valid JSON only."},
            {"role": "user", "content": analysis_prompt}
        ], model="anthropic/claude-3.5-haiku")
        
        # Parse JSON response
        analysis = json.loads(response.strip())
        
        # Check if we have matching content
        has_matching_content = False
        if analysis.get("requested_subject") and available_subjects:
            requested_lower = analysis["requested_subject"].lower()
            has_matching_content = any(
                subj.lower() == requested_lower or requested_lower in subj.lower()
                for subj in available_subjects
            )
        
        return {
            **analysis,
            "available_subjects": available_subjects,
            "has_matching_content": has_matching_content
        }
        
    except Exception as e:
        logger.error(f"Error analyzing intent: {str(e)}")
        # Fallback to basic analysis
        return {
            "intent": "unclear",
            "requested_subject": None,
            "requested_topic": None,
            "available_subjects": available_subjects,
            "has_matching_content": False,
            "confidence": 0.3,
            "needs_clarification": True
        }


# ============================================================================
# RECOMMENDED PROMPTS GENERATION
# ============================================================================

async def generate_recommended_prompts(
    user_notes: List[Dict[str, Any]],
    current_context: str,
    chatbot_type: str
) -> List[str]:
    """
    Generate 3-4 contextual prompt suggestions based on user's actual notes.
    """
    prompts = []
    
    if not user_notes:
        # No notes - suggest generic actions
        if chatbot_type == "flashcard_assistant":
            return [
                "Create flashcards for biology basics",
                "Make flashcards for algebra concepts",
                "Generate history flashcards"
            ]
        elif chatbot_type == "quiz_generator":
            return [
                "Create a practice quiz on science",
                "Generate a math quiz",
                "Make a history quiz"
            ]
        else:
            return [
                "Summarize key concepts",
                "Explain a topic to me",
                "Create study materials"
            ]
    
    # Extract recent subjects and topics
    subjects_with_titles = {}
    for note in user_notes[:10]:  # Look at top 10 most relevant
        subject = note.get("subject", "General")
        title = note.get("title", "")
        if subject not in subjects_with_titles:
            subjects_with_titles[subject] = []
        if title:
            subjects_with_titles[subject].append(title)
    
    # Generate contextual prompts
    for subject, titles in list(subjects_with_titles.items())[:3]:
        if chatbot_type == "flashcard_assistant":
            if titles:
                prompts.append(f"Create flashcards from my {subject} notes")
            else:
                prompts.append(f"Make flashcards for {subject}")
        elif chatbot_type == "quiz_generator":
            prompts.append(f"Generate a quiz on {subject}")
        else:
            prompts.append(f"Summarize my {subject} notes")
    
    # Add a general helpful prompt
    if len(prompts) < 4:
        prompts.append("Summarize all my recent notes")
    
    return prompts[:4]


# ============================================================================
# AI RESPONSE GENERATION
# ============================================================================

async def generate_ai_response(
    prompt: str,
    context: Dict[str, Any],
    chatbot_type: str
) -> Dict[str, Any]:
    """
    Generate natural language AI response with proper formatting.
    
    Args:
        prompt: User's input
        context: {
            "relevant_notes": List[Dict],
            "user_intent": Dict,
            "conversation_history": List[Dict],
            "system_prompt": str
        }
        chatbot_type: Type of chatbot
    
    Returns: {
        "natural_text": str,  # Pre-formatted natural language response
        "action": str,  # "flashcards_generated", "needs_clarification", etc.
        "generated_content": Optional[Dict]
    }
    """
    
    relevant_notes = context.get("relevant_notes", [])
    user_intent = context.get("user_intent", {})
    conversation_history = context.get("conversation_history", [])
    
    # Build context for AI
    notes_context = ""
    if relevant_notes:
        notes_context = "\n\nRelevant notes found:\n"
        for i, note in enumerate(relevant_notes[:5]):
            title = note.get("title", "Untitled")
            subject = note.get("subject", "General")
            content = note.get("content") or note.get("extracted_text", "")
            snippet = content[:300] + "..." if len(content) > 300 else content
            notes_context += f"{i+1}. {title} ({subject}): {snippet}\n"
    
    # Build conversation messages
    messages = [
        {"role": "system", "content": STUDY_SHARPER_SYSTEM_PROMPT + notes_context}
    ]
    
    # Add conversation history (last 5 exchanges)
    for msg in conversation_history[-10:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("message", msg.get("content", ""))
        })
    
    # Add current prompt
    messages.append({"role": "user", "content": prompt})
    
    try:
        # Generate response
        response_text = get_chat_completion(messages, model="anthropic/claude-3.5-sonnet")
        
        # Determine action taken
        action = "response_provided"
        if "?" in response_text:
            action = "needs_clarification"
        elif any(word in response_text.lower() for word in ["i'll create", "i'll generate", "i'll make", "creating", "generating"]):
            action = "content_generation_initiated"
        
        return {
            "natural_text": response_text.strip(),
            "action": action,
            "generated_content": None  # Will be populated by specific handlers
        }
        
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return {
            "natural_text": "I'm having trouble processing your request right now. Could you try rephrasing it or try again in a moment?",
            "action": "error",
            "generated_content": None
        }
