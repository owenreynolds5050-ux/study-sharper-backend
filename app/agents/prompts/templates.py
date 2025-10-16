"""
Prompt Templates for Task Agents
Hardcoded, optimized prompts for high-quality content generation
"""

from typing import Dict, Any, List, Optional


class PromptTemplates:
    """Hardcoded prompt templates for all task agents"""
    
    @staticmethod
    def flashcard_generation(
        content: str,
        count: int = 10,
        difficulty: str = "medium",
        topic: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate flashcards prompt"""
        
        difficulty_guidance = {
            "easy": "Focus on basic definitions and simple concepts. Keep questions straightforward.",
            "medium": "Mix of definitions, concepts, and application questions. Balance recall and understanding.",
            "hard": "Include complex scenarios, multi-step problems, and analytical questions.",
            "adaptive": "Mix difficulty levels based on content complexity."
        }
        
        topic_instruction = f"focused on {topic}" if topic else "covering the main concepts"
        
        return f"""You are an expert study material creator. Generate {count} high-quality flashcards {topic_instruction} from the following content.

Difficulty Level: {difficulty}
Guidance: {difficulty_guidance.get(difficulty, difficulty_guidance["medium"])}

Content to create flashcards from:
---
{content}
---

Requirements:
1. Create EXACTLY {count} flashcards
2. Each flashcard must have a clear question and concise answer
3. Questions should test understanding, not just memorization
4. Answers should be accurate and complete but concise (2-3 sentences max)
5. Cover different aspects of the content
6. Difficulty level: {difficulty}
7. Avoid yes/no questions - make them specific and testable

Respond in this EXACT JSON format:
{{
    "flashcards": [
        {{
            "question": "Clear, specific question",
            "answer": "Concise, accurate answer",
            "topic": "Subtopic category",
            "difficulty": "{difficulty}"
        }}
    ],
    "total_count": {count},
    "topics_covered": ["list", "of", "topics"]
}}

IMPORTANT: Return ONLY valid JSON, no additional text."""

    @staticmethod
    def quiz_generation(
        content: str,
        question_count: int = 10,
        difficulty: str = "medium",
        question_types: Optional[List[str]] = None
    ) -> str:
        """Generate quiz prompt"""
        
        if question_types is None:
            question_types = ["multiple_choice", "true_false", "short_answer"]
        
        return f"""You are an expert assessment creator. Generate a {question_count}-question quiz from the following content.

Content:
---
{content}
---

Requirements:
1. Create EXACTLY {question_count} questions
2. Question types to include: {", ".join(question_types)}
3. Difficulty: {difficulty}
4. Each question must be clear and unambiguous
5. All answers must be correct and verifiable from the content
6. Include explanations for correct answers
7. For multiple choice, provide 4 options with only one correct answer
8. For true/false, ensure statements are clearly true or false
9. For short answer, provide expected answer and acceptable alternatives

Respond in this EXACT JSON format:
{{
    "quiz": {{
        "title": "Quiz Title Based on Content",
        "questions": [
            {{
                "type": "multiple_choice",
                "question": "Question text",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A",
                "explanation": "Why this is correct",
                "points": 1
            }},
            {{
                "type": "true_false",
                "question": "Statement to evaluate",
                "correct_answer": true,
                "explanation": "Explanation",
                "points": 1
            }},
            {{
                "type": "short_answer",
                "question": "Question requiring brief answer",
                "correct_answer": "Expected answer",
                "acceptable_answers": ["answer1", "answer2"],
                "explanation": "Explanation",
                "points": 2
            }}
        ]
    }},
    "total_points": 15,
    "estimated_time_minutes": 20
}}

IMPORTANT: Return ONLY valid JSON, no additional text."""

    @staticmethod
    def exam_generation(
        content: str,
        duration_minutes: int = 60,
        difficulty: str = "medium",
        sections: Optional[List[str]] = None
    ) -> str:
        """Generate exam prompt"""
        
        if sections is None:
            sections = ["multiple_choice", "short_answer", "essay"]
        
        return f"""You are an expert exam creator. Generate a comprehensive {duration_minutes}-minute exam from the following content.

Content:
---
{content}
---

Requirements:
1. Create an exam suitable for {duration_minutes} minutes
2. Include these sections: {", ".join(sections)}
3. Difficulty level: {difficulty}
4. Questions should comprehensively assess understanding
5. Include point values and time estimates per section
6. Provide answer keys and grading rubrics
7. Total points should equal 100

Respond in this EXACT JSON format:
{{
    "exam": {{
        "title": "Exam Title",
        "duration_minutes": {duration_minutes},
        "total_points": 100,
        "sections": [
            {{
                "section_name": "Multiple Choice",
                "instructions": "Choose the best answer for each question",
                "time_estimate_minutes": 20,
                "questions": [
                    {{
                        "question": "Question text",
                        "options": ["A", "B", "C", "D"],
                        "correct_answer": "A",
                        "points": 2
                    }}
                ]
            }},
            {{
                "section_name": "Short Answer",
                "instructions": "Answer in 2-3 complete sentences",
                "time_estimate_minutes": 25,
                "questions": [
                    {{
                        "question": "Question",
                        "sample_answer": "Good answer example",
                        "rubric": "Grading criteria",
                        "points": 10
                    }}
                ]
            }},
            {{
                "section_name": "Essay",
                "instructions": "Write a detailed essay response",
                "time_estimate_minutes": 15,
                "questions": [
                    {{
                        "prompt": "Essay prompt",
                        "rubric": {{
                            "thesis": 5,
                            "evidence": 10,
                            "analysis": 10,
                            "organization": 5
                        }},
                        "points": 30
                    }}
                ]
            }}
        ]
    }}
}}

IMPORTANT: Return ONLY valid JSON, no additional text."""

    @staticmethod
    def summary_generation(
        content: str,
        length: str = "medium",
        style: str = "bullet_points",
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """Generate summary prompt"""
        
        length_guidance = {
            "short": "Very concise, 3-5 key points only",
            "medium": "Balanced summary, 8-12 main points with brief explanations",
            "long": "Comprehensive summary, detailed coverage of all major topics"
        }
        
        style_guidance = {
            "bullet_points": "Use bullet points with clear hierarchy",
            "paragraph": "Write in flowing paragraph form",
            "outline": "Create a structured outline with headings and subpoints"
        }
        
        focus_instruction = ""
        if focus_areas:
            focus_instruction = f"\nFocus especially on: {', '.join(focus_areas)}"
        
        return f"""You are an expert at creating study summaries. Summarize the following content.

Content:
---
{content}
---

Requirements:
1. Length: {length} - {length_guidance.get(length)}
2. Style: {style} - {style_guidance.get(style)}
3. Extract the most important information
4. Maintain accuracy and clarity{focus_instruction}
5. Use clear, concise language appropriate for students
6. Identify and define key terms
7. Organize information logically

Respond in this EXACT JSON format:
{{
    "summary": {{
        "title": "Summary Title",
        "main_points": [
            {{
                "point": "Key point",
                "details": "Supporting details",
                "importance": "high"
            }}
        ],
        "key_terms": [
            {{
                "term": "Term",
                "definition": "Definition"
            }}
        ]
    }},
    "word_count": 500,
    "estimated_reading_time_minutes": 5
}}

IMPORTANT: Return ONLY valid JSON, no additional text."""

    @staticmethod
    def chat_with_context(
        question: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """General chat with context prompt"""
        
        context_str = ""
        
        # Add notes context
        if context.get("notes") and context["notes"].get("notes"):
            notes_list = context["notes"]["notes"]
            if notes_list:
                notes_text = "\n".join([
                    f"- {note.get('title', 'Untitled')}: {note.get('content', '')[:200]}..."
                    for note in notes_list[:3]
                ])
                context_str += f"\n\nRelevant Notes:\n{notes_text}"
        
        # Add progress context
        if context.get("progress"):
            progress = context["progress"]
            context_str += f"\n\nUser Study Progress:\n"
            context_str += f"- Total cards studied: {progress.get('total_cards_studied', 0)}\n"
            context_str += f"- Accuracy: {progress.get('accuracy_percentage', 0)}%\n"
            context_str += f"- Note count: {progress.get('note_count', 0)}\n"
            context_str += f"- Study sessions: {progress.get('session_count', 0)}"
        
        # Add user profile context
        if context.get("profile"):
            profile = context["profile"]
            prefs = profile.get("preferences", {})
            if prefs:
                context_str += f"\n\nUser Preferences:\n"
                context_str += f"- Difficulty: {prefs.get('preferred_difficulty', 'adaptive')}\n"
                context_str += f"- Detail level: {prefs.get('preferred_detail_level', 'detailed')}"
        
        # Add conversation history
        history_str = ""
        if conversation_history:
            history_str = "\n\nPrevious Conversation:\n" + "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in conversation_history[-5:]  # Last 5 messages
            ])
        
        return f"""You are an AI study assistant helping a student. Answer their question using the provided context.

User Question: {question}{context_str}{history_str}

Instructions:
1. Answer the question accurately and helpfully
2. Use information from the context when relevant
3. If you reference notes, mention which note
4. Be conversational but informative
5. If you don't have enough information, say so and ask clarifying questions
6. Be encouraging and supportive
7. Provide actionable study advice when appropriate

Provide a direct, helpful response (plain text, not JSON)."""
