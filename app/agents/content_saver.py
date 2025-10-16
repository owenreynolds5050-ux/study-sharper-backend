"""
Content Saver
Saves generated study materials to database
"""

from supabase import Client
from typing import Dict, Any, List
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ContentSaver:
    """Saves generated content to appropriate database tables"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        logger.info("Content Saver initialized")
    
    async def save_generated_content(
        self,
        user_id: str,
        content_type: str,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save generated study materials to database.
        
        Args:
            user_id: User ID
            content_type: Type of content (flashcard_generation, quiz_generation, etc.)
            content: Generated content data
            
        Returns:
            Dictionary with saved item IDs
        """
        try:
            if content_type == "flashcard_generation":
                return await self.save_flashcards(user_id, content)
            elif content_type == "quiz_generation":
                return await self.save_quiz(user_id, content)
            elif content_type == "exam_generation":
                return await self.save_exam(user_id, content)
            elif content_type == "summary_generation":
                return await self.save_summary(user_id, content)
            else:
                logger.warning(f"Unknown content type: {content_type}")
                return {"saved": False, "reason": "Unknown content type"}
        
        except Exception as e:
            logger.error(f"Failed to save content: {e}")
            return {"saved": False, "error": str(e)}
    
    async def save_flashcards(self, user_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save flashcards to database.
        
        Args:
            user_id: User ID
            content: Flashcard data (from orchestrator response)
            
        Returns:
            Dictionary with saved flashcard IDs
        """
        try:
            data = content["data"] if "data" in content and isinstance(content["data"], dict) else content
            flashcards = data.get("flashcards", [])
            metadata = data.get("metadata", {})

            if not flashcards:
                logger.warning("No flashcards found to save")
                return {"saved": False, "reason": "No flashcards generated"}

            set_title = metadata.get("set_title") or data.get("title") or "AI Generated Flashcards"
            description = metadata.get("set_description") or data.get("description")
            note_ids = metadata.get("note_ids") or data.get("note_ids") or []

            set_payload = {
                "user_id": user_id,
                "title": str(set_title)[:200],
                "description": description,
                "source_note_ids": note_ids,
                "ai_generated": True,
                "generation_status": "complete"
            }

            set_response = self.supabase.table("flashcard_sets").insert(set_payload).execute()

            if not set_response.data:
                logger.error("Failed to create flashcard set for user %s", user_id)
                return {"saved": False, "reason": "Failed to create flashcard set"}

            set_record = set_response.data[0]
            set_id = set_record["id"]

            saved_ids = []
            flashcard_records = []
            primary_note_id = note_ids[0] if isinstance(note_ids, list) and note_ids else None

            for index, card in enumerate(flashcards):
                flashcard_records.append({
                    "user_id": user_id,
                    "set_id": set_id,
                    "front": str(card.get("question", card.get("front", ""))),
                    "back": str(card.get("answer", card.get("back", ""))),
                    "explanation": card.get("explanation"),
                    "topic": card.get("topic"),
                    "difficulty": card.get("difficulty"),
                    "ai_generated": True,
                    "mastery_level": 0,
                    "times_reviewed": 0,
                    "times_correct": 0,
                    "times_incorrect": 0,
                    "failed_verification": False,
                    "verification_attempts": 0,
                    "position": index,
                    "source_note_id": primary_note_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                })

            if flashcard_records:
                response = self.supabase.table("flashcards").insert(flashcard_records).execute()
                if response.data:
                    saved_ids = [row["id"] for row in response.data]

            if saved_ids:
                self.supabase.table("flashcard_sets").update({
                    "total_cards": len(saved_ids),
                    "mastered_cards": 0,
                    "updated_at": datetime.now().isoformat()
                }).eq("id", set_id).execute()

            logger.info(f"Saved {len(saved_ids)} flashcards for user: {user_id}")
            return {
                "saved": bool(saved_ids),
                "count": len(saved_ids),
                "ids": saved_ids,
                "set": set_record,
                "type": "flashcards"
            }

        except Exception as e:
            logger.error(f"Failed to save flashcards: {e}")
            raise
    
    async def save_quiz(self, user_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save quiz to database.
        
        Args:
            user_id: User ID
            content: Quiz data
            
        Returns:
            Dictionary with saved quiz ID
        """
        try:
            quiz_data = content.get("quiz", {})
            
            # Create quiz entry
            quiz_response = self.supabase.table("quizzes").insert({
                "user_id": user_id,
                "title": quiz_data.get("title", "Generated Quiz"),
                "total_points": content.get("total_points", 0),
                "estimated_time_minutes": content.get("estimated_time_minutes", 0),
                "created_at": datetime.now().isoformat()
            }).execute()
            
            quiz_id = quiz_response.data[0]["id"]
            
            # Save questions
            question_ids = []
            for idx, question in enumerate(quiz_data.get("questions", [])):
                question_response = self.supabase.table("quiz_questions").insert({
                    "quiz_id": quiz_id,
                    "type": question["type"],
                    "question": question["question"],
                    "options": json.dumps(question.get("options", [])),
                    "correct_answer": json.dumps(question["correct_answer"]),
                    "explanation": question.get("explanation"),
                    "points": question.get("points", 1),
                    "order_index": idx
                }).execute()
                
                if question_response.data:
                    question_ids.append(question_response.data[0]["id"])
            
            logger.info(f"Saved quiz {quiz_id} with {len(question_ids)} questions for user: {user_id}")
            return {
                "saved": True,
                "quiz_id": quiz_id,
                "question_count": len(question_ids),
                "type": "quiz"
            }
        
        except Exception as e:
            logger.error(f"Failed to save quiz: {e}")
            raise
    
    async def save_exam(self, user_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save exam to database.
        
        Args:
            user_id: User ID
            content: Exam data
            
        Returns:
            Dictionary with saved exam ID
        """
        try:
            exam_data = content.get("exam", {})
            
            # Create exam entry
            exam_response = self.supabase.table("exams").insert({
                "user_id": user_id,
                "title": exam_data.get("title", "Generated Exam"),
                "duration_minutes": exam_data.get("duration_minutes", 60),
                "total_points": exam_data.get("total_points", 100),
                "sections": json.dumps(exam_data.get("sections", [])),
                "created_at": datetime.now().isoformat()
            }).execute()
            
            exam_id = exam_response.data[0]["id"]
            
            logger.info(f"Saved exam {exam_id} for user: {user_id}")
            return {
                "saved": True,
                "exam_id": exam_id,
                "type": "exam"
            }
        
        except Exception as e:
            logger.error(f"Failed to save exam: {e}")
            raise
    
    async def save_summary(self, user_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save summary to database.
        
        Args:
            user_id: User ID
            content: Summary data
            
        Returns:
            Dictionary with saved summary ID
        """
        try:
            summary_data = content.get("summary", {})
            
            # Create summary entry
            summary_response = self.supabase.table("summaries").insert({
                "user_id": user_id,
                "title": summary_data.get("title", "Generated Summary"),
                "content": json.dumps(summary_data),
                "source_note_ids": [],  # TODO: Track source notes
                "length_type": content.get("length", "medium"),
                "style_type": content.get("style", "bullet_points"),
                "word_count": content.get("word_count", 0),
                "created_at": datetime.now().isoformat()
            }).execute()
            
            summary_id = summary_response.data[0]["id"]
            
            logger.info(f"Saved summary {summary_id} for user: {user_id}")
            return {
                "saved": True,
                "summary_id": summary_id,
                "type": "summary"
            }
        
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            raise
    
    async def get_user_content(
        self,
        user_id: str,
        content_type: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieve user's generated content.
        
        Args:
            user_id: User ID
            content_type: Type of content to retrieve
            limit: Maximum number of items
            
        Returns:
            List of content items
        """
        try:
            table_map = {
                "flashcards": "flashcards",
                "quizzes": "quizzes",
                "exams": "exams",
                "summaries": "summaries"
            }
            
            table = table_map.get(content_type)
            if not table:
                logger.warning(f"Invalid content type: {content_type}")
                return []
            
            response = self.supabase.table(table).select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(limit).execute()
            
            logger.info(f"Retrieved {len(response.data)} {content_type} for user: {user_id}")
            return response.data
        
        except Exception as e:
            logger.error(f"Failed to get user content: {e}")
            return []
