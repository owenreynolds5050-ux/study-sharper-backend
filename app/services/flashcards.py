"""
Flashcard Generation Service
Generates AI-powered flashcards from note content using OpenRouter
"""

from typing import List, Dict, Any, Optional
from app.services.open_router import get_chat_completion
from app.services.embeddings import get_embedding_for_text
from datetime import datetime, timedelta
import json
import re


def generate_flashcards_from_text(
    text: str,
    note_title: str = "",
    num_cards: int = 10,
    difficulty: str = "medium"
) -> List[Dict[str, str]]:
    """
    Generate flashcards from text content using AI.
    
    Args:
        text: The content to generate flashcards from
        note_title: Optional title of the note for context
        num_cards: Number of flashcards to generate (default: 10)
        difficulty: Difficulty level - 'easy', 'medium', or 'hard' (default: 'medium')
    
    Returns:
        List of flashcard dictionaries with 'front', 'back', and optionally 'explanation'
    """
    
    # Build the AI prompt based on difficulty
    difficulty_instructions = {
        "easy": "Focus on basic definitions and simple recall questions. Keep answers concise.",
        "medium": "Mix of recall and comprehension questions. Include some application questions.",
        "hard": "Focus on analysis, synthesis, and application. Include challenging questions that require deeper understanding."
    }
    
    difficulty_instruction = difficulty_instructions.get(difficulty, difficulty_instructions["medium"])
    
    system_prompt = f"""You are an expert educational content creator specializing in flashcard generation for students.

Your task is to create {num_cards} high-quality flashcards from the provided study material.

DIFFICULTY LEVEL: {difficulty.upper()}
{difficulty_instruction}

FLASHCARD GUIDELINES:
1. FRONT (Question): Should be clear, specific, and testable
2. BACK (Answer): Should be accurate, complete, and student-friendly
3. EXPLANATION (Optional): Add context, mnemonics, or additional insights when helpful

QUESTION TYPES TO INCLUDE:
- Definition questions: "What is X?"
- Concept questions: "Explain how X works"
- Application questions: "When would you use X?"
- Comparison questions: "What's the difference between X and Y?"
- Process questions: "What are the steps in X?"

IMPORTANT RULES:
- Each card should focus on ONE concept or fact
- Avoid yes/no questions - make questions specific
- Use examples in explanations when helpful
- Keep questions clear and unambiguous
- Make sure answers are complete but concise

OUTPUT FORMAT:
Return ONLY a valid JSON array of flashcard objects. Each object must have these fields:
- "front": the question (string)
- "back": the answer (string)
- "explanation": additional context (string, can be empty)

Example format:
[
  {{
    "front": "What is photosynthesis?",
    "back": "The process by which plants convert light energy into chemical energy (glucose) using carbon dioxide and water.",
    "explanation": "Remember the equation: 6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂"
  }}
]

DO NOT include any text before or after the JSON array.
"""
    
    user_prompt = f"""Generate {num_cards} flashcards from this study material:

{"Title: " + note_title if note_title else ""}

Content:
{text}

Return only the JSON array of flashcards."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        # Get AI response
        response = get_chat_completion(messages, model="anthropic/claude-3.5-sonnet")
        
        # Parse the JSON response
        flashcards = parse_flashcard_response(response)
        
        # Validate and clean flashcards
        valid_flashcards = []
        for card in flashcards[:num_cards]:  # Limit to requested number
            if validate_flashcard(card):
                valid_flashcards.append({
                    "front": card.get("front", "").strip(),
                    "back": card.get("back", "").strip(),
                    "explanation": card.get("explanation", "").strip()
                })
        
        if not valid_flashcards:
            raise ValueError("No valid flashcards generated from AI response")
        
        return valid_flashcards
        
    except Exception as e:
        raise Exception(f"Failed to generate flashcards: {str(e)}")


def parse_flashcard_response(response: str) -> List[Dict[str, str]]:
    """
    Parse AI response to extract JSON array of flashcards.
    Handles various response formats and cleans the output.
    """
    try:
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Extract content between code blocks
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if match:
                response = match.group(1)
        
        # Parse JSON
        flashcards = json.loads(response)
        
        # Ensure it's a list
        if not isinstance(flashcards, list):
            raise ValueError("Response is not a JSON array")
        
        return flashcards
        
    except json.JSONDecodeError as e:
        # Try to find JSON array in the response
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        raise ValueError(f"Failed to parse flashcard JSON: {str(e)}")


def validate_flashcard(card: Dict[str, Any]) -> bool:
    """
    Validate that a flashcard has required fields and reasonable content.
    """
    if not isinstance(card, dict):
        return False
    
    # Must have front and back
    if "front" not in card or "back" not in card:
        return False
    
    front = str(card.get("front", "")).strip()
    back = str(card.get("back", "")).strip()
    
    # Must not be empty
    if not front or not back:
        return False
    
    # Reasonable length constraints
    if len(front) < 5 or len(back) < 5:
        return False
    
    if len(front) > 500 or len(back) > 1000:
        return False
    
    return True


def calculate_next_review_interval(mastery_level: int, was_correct: bool) -> int:
    """
    Calculate the next review interval in days based on spaced repetition algorithm.
    
    Args:
        mastery_level: Current mastery level (0-5)
        was_correct: Whether the user answered correctly
    
    Returns:
        Number of days until next review
    """
    if not was_correct:
        # Reset to level 1 if incorrect
        return 1
    
    # Spaced repetition intervals by mastery level
    intervals = {
        0: 0,   # Review immediately
        1: 1,   # Review in 1 day
        2: 3,   # Review in 3 days
        3: 7,   # Review in 1 week
        4: 14,  # Review in 2 weeks
        5: 30   # Review in 1 month
    }
    
    return intervals.get(mastery_level, 1)


def update_mastery_level(current_level: int, was_correct: bool) -> int:
    """
    Update mastery level based on review performance.
    
    Args:
        current_level: Current mastery level (0-5)
        was_correct: Whether the user answered correctly
    
    Returns:
        New mastery level (0-5)
    """
    if was_correct:
        # Increase mastery level, max at 5
        return min(current_level + 1, 5)
    else:
        # Reset to level 1 if incorrect
        return 1


# ============================================================================
# AUTO-SUGGESTED FLASHCARDS
# ============================================================================

async def generate_suggested_flashcards_for_user(user_id: str, supabase) -> List[Dict]:
    """
    Auto-generate suggested flashcard sets from user's recent notes.
    Groups notes by topic and creates cohesive flashcard sets.
    """
    try:
        # Get recent notes (last 7 days or last 10 notes)
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        notes_response = supabase.table("notes").select(
            "id, title, content, extracted_text, created_at"
        ).eq("user_id", user_id).gte(
            "created_at", seven_days_ago
        ).order("created_at", desc=True).limit(10).execute()
        
        if not notes_response.data or len(notes_response.data) == 0:
            return []
        
        notes = notes_response.data
        
        # Group notes by topic using AI
        grouped_notes = await group_notes_by_topic(notes)
        
        suggestions = []
        
        for topic_group in grouped_notes:
            # Check if we already have a suggestion for this topic recently
            existing = supabase.table("flashcard_sets").select("id").eq(
                "user_id", user_id
            ).eq("is_suggested", True).contains(
                "source_note_ids", topic_group["note_ids"]
            ).gte("suggestion_date", seven_days_ago).execute()
            
            if existing.data:
                # Reuse existing suggestion
                continue
            
            # Generate flashcards for this topic group
            combined_text = "\n\n".join([
                f"## {note['title']}\n\n{note.get('content') or note.get('extracted_text', '')}"
                for note in topic_group["notes"]
            ])
            
            if len(combined_text) > 8000:
                combined_text = combined_text[:8000] + "\n\n[Content truncated...]"
            
            flashcards = generate_flashcards_from_text(
                text=combined_text,
                note_title=topic_group["topic"],
                num_cards=10,
                difficulty="medium"
            )
            
            # Create suggested flashcard set
            set_data = {
                "user_id": user_id,
                "title": f"📚 Suggested: {topic_group['topic']}",
                "description": f"Auto-generated from your recent notes on {topic_group['topic']}",
                "source_note_ids": topic_group["note_ids"],
                "is_suggested": True,
                "is_accepted": None,
                "suggestion_date": datetime.now().isoformat(),
                "ai_generated": True
            }
            
            set_response = supabase.table("flashcard_sets").insert(set_data).execute()
            
            if set_response.data:
                flashcard_set = set_response.data[0]
                set_id = flashcard_set["id"]
                
                # Insert flashcards
                flashcard_records = []
                for i, card in enumerate(flashcards):
                    flashcard_records.append({
                        "user_id": user_id,
                        "set_id": set_id,
                        "front": card["front"],
                        "back": card["back"],
                        "explanation": card.get("explanation", ""),
                        "position": i,
                        "ai_generated": True
                    })
                
                supabase.table("flashcards").insert(flashcard_records).execute()
                
                suggestions.append(flashcard_set)
        
        return suggestions
        
    except Exception as e:
        print(f"Error generating suggestions: {str(e)}")
        return []


async def group_notes_by_topic(notes: List[Dict]) -> List[Dict]:
    """
    Group notes by topic using AI analysis.
    Returns list of topic groups with their associated notes.
    """
    if len(notes) == 0:
        return []
    
    # If only 1-2 notes, treat as single group
    if len(notes) <= 2:
        titles = [note.get("title", "Untitled") for note in notes]
        return [{
            "topic": " & ".join(titles),
            "notes": notes,
            "note_ids": [note["id"] for note in notes]
        }]
    
    # Use AI to identify topics
    note_summaries = "\n".join([
        f"{i+1}. {note.get('title', 'Untitled')}: {(note.get('content') or note.get('extracted_text', ''))[:200]}"
        for i, note in enumerate(notes)
    ])
    
    system_prompt = """You are an expert at identifying topics and themes in study materials.
Analyze the provided notes and group them by topic. Return a JSON array of topic groups.

Each group should have:
- "topic": A concise topic name (2-5 words)
- "note_indices": Array of note indices (1-based) that belong to this topic

Example output:
[
  {"topic": "Cell Biology", "note_indices": [1, 3, 5]},
  {"topic": "Organic Chemistry", "note_indices": [2, 4]}
]

Only return the JSON array, no other text."""
    
    user_prompt = f"Group these notes by topic:\n\n{note_summaries}"
    
    try:
        response = get_chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], model="anthropic/claude-3.5-sonnet")
        
        # Parse response
        groups_data = json.loads(response.strip())
        
        # Convert to our format
        topic_groups = []
        for group in groups_data:
            group_notes = [notes[i-1] for i in group["note_indices"] if 0 < i <= len(notes)]
            if group_notes:
                topic_groups.append({
                    "topic": group["topic"],
                    "notes": group_notes,
                    "note_ids": [note["id"] for note in group_notes]
                })
        
        return topic_groups
        
    except Exception as e:
        print(f"Error grouping notes: {str(e)}")
        # Fallback: treat all notes as one group
        return [{
            "topic": "Recent Study Materials",
            "notes": notes,
            "note_ids": [note["id"] for note in notes]
        }]


# ============================================================================
# AI CHATBOT FOR FLASHCARDS
# ============================================================================

async def process_flashcard_chat_request(
    user_id: str,
    message: str,
    context: Optional[Dict],
    supabase
) -> Dict:
    """
    Process AI chat request for flashcard generation.
    Uses RAG to find relevant notes and generates flashcards based on user's natural language request.
    """
    try:
        # Save user message to chat history
        supabase.table("flashcard_chat_history").insert({
            "user_id": user_id,
            "message": message,
            "role": "user",
            "context": context
        }).execute()
        
        # Get recent chat history for context (last 10 messages)
        history_response = supabase.table("flashcard_chat_history").select(
            "message, role"
        ).eq("user_id", user_id).order(
            "created_at", desc=True
        ).limit(10).execute()
        
        chat_history = list(reversed(history_response.data)) if history_response.data else []
        
        # Use RAG to find relevant notes based on user's message
        relevant_notes = await find_relevant_notes_for_flashcards(user_id, message, supabase)
        
        # Generate AI response
        ai_response = await generate_flashcard_chat_response(
            message=message,
            chat_history=chat_history,
            relevant_notes=relevant_notes
        )
        
        # Save assistant response to chat history
        supabase.table("flashcard_chat_history").insert({
            "user_id": user_id,
            "message": ai_response["message"],
            "role": "assistant",
            "context": ai_response.get("context")
        }).execute()
        
        return ai_response
        
    except Exception as e:
        raise Exception(f"Chat processing failed: {str(e)}")


async def find_relevant_notes_for_flashcards(user_id: str, query: str, supabase) -> List[Dict]:
    """
    Use RAG to find notes relevant to the user's flashcard request.
    """
    try:
        # Generate embedding for the query
        embedding_result = get_embedding_for_text(query)
        query_embedding = embedding_result["embedding"]
        
        # Search for similar notes
        response = supabase.rpc("search_similar_notes", {
            "query_embedding": query_embedding,
            "match_threshold": 0.5,
            "match_count": 5,
            "p_user_id": user_id
        }).execute()
        
        return response.data or []
        
    except Exception as e:
        print(f"Error finding relevant notes: {str(e)}")
        # Fallback: return recent notes
        recent = supabase.table("notes").select(
            "id, title, content, extracted_text"
        ).eq("user_id", user_id).order(
            "created_at", desc=True
        ).limit(5).execute()
        
        return recent.data or []


async def generate_flashcard_chat_response(
    message: str,
    chat_history: List[Dict],
    relevant_notes: List[Dict]
) -> Dict:
    """
    Generate AI response for flashcard chat with recommended prompts and actions.
    """
    # Build context from relevant notes
    notes_context = ""
    if relevant_notes:
        notes_context = "\n\nRelevant notes found:\n"
        for note in relevant_notes[:3]:
            title = note.get("title", "Untitled")
            content = (note.get("content") or note.get("extracted_text", ""))[:200]
            notes_context += f"- {title}: {content}...\n"
    
    system_prompt = f"""You are a helpful AI assistant specialized in creating study flashcards.

Your role:
1. Help users create effective flashcard sets from their notes
2. Suggest specific flashcard topics based on their study materials
3. Provide recommended prompts for flashcard generation

When responding:
- Be concise and actionable
- Suggest specific flashcard sets they can create
- Reference their actual notes when relevant
- Provide 2-3 recommended prompts they can use

Available notes context:{notes_context}

If the user asks to create flashcards, respond with a JSON object containing:
{{
  "message": "Your helpful response",
  "action": "generate_flashcards",
  "note_ids": ["id1", "id2"],
  "num_cards": 10,
  "difficulty": "medium",
  "set_title": "Suggested title"
}}

Otherwise, respond with:
{{
  "message": "Your helpful response",
  "recommended_prompts": [
    "Create flashcards about...",
    "Generate a quiz on...",
    "Make study cards for..."
  ]
}}"""
    
    # Build message history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent chat history (last 5 exchanges)
    for msg in chat_history[-10:]:
        messages.append({
            "role": msg["role"],
            "content": msg["message"]
        })
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    # Get AI response
    response_text = get_chat_completion(messages, model="anthropic/claude-3.5-sonnet")
    
    # Try to parse as JSON
    try:
        response_data = json.loads(response_text.strip())
        return response_data
    except:
        # If not JSON, return as plain message with default prompts
        return {
            "message": response_text,
            "recommended_prompts": [
                "Create flashcards from my recent biology notes",
                "Generate a quiz on my chemistry study materials",
                "Make flashcards about the topics I studied this week"
            ]
        }
