"""
Chat Intelligence ML Layer
Learns from user interactions to improve chatbot responses over time.

This is separate from the Tanker Analytics ML (ml_pipeline.py).
This ML focuses on:
- User intent classification
- Question similarity detection
- Answer refinement
- Context understanding
"""
import psycopg2
from psycopg2 import extras
from psycopg2 import errors as psycopg2_errors
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import Counter
import difflib

# Try to import sklearn for future ML enhancements (optional)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
    POSTGRES_PORT, DATABASE_NAME
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatIntelligence:
    """
    Chat Intelligence ML System
    Learns from chat history to improve responses
    """
    
    def __init__(self):
        self.intent_keywords = {
            'fleet_stats': ['how many', 'total', 'count', 'statistics', 'stats', 'summary', 'overview'],
            'list_request': ['list', 'all', 'show all', 'give me all', 'every', 'all tankers', 'tanker ids', 'tanker id'],
            'tanker_summary': ['tanker', 'status', 'where', 'location', 'position', 'current', 'now'],
            'tanker_detail': ['detail', 'details', 'information', 'info', 'about'],
            'eta_inquiry': ['eta', 'arrival', 'arrive', 'when', 'time', 'reach', 'destination'],
            'delay_reason': ['delay', 'late', 'behind', 'slow', 'why', 'reason'],
            'trend_analysis': ['trend', 'pattern', 'analysis'],
            'general_help': ['help', 'how', 'what', 'explain', 'tell me', 'show']
        }
        
        self.topic_keywords = {
            'specific_tanker': ['tanker', 'truck', 'vehicle', 'id'],
            'fleet_overview': ['all', 'fleet', 'every', 'total', 'summary'],
            'historical_data': ['history', 'past', 'previous', 'record'],
            'prediction_request': ['predict', 'forecast', 'estimate', 'likely', 'probability', 'future']
        }
        
        # Cache for learned patterns (loaded from DB)
        self.learned_patterns = {}
        self.pattern_cache_loaded = False
        
    def get_db_connection(self):
        """Create and return a database connection"""
        try:
            conn = psycopg2.connect(
                dbname=DATABASE_NAME,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                host=POSTGRES_HOST,
                port=POSTGRES_PORT
            )
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    def ensure_chat_tables_exist(self):
        """Self-healing: Create chat tables if they don't exist"""
        conn = self.get_db_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Check if chat_history table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'chat_history'
                )
            """)
            chat_history_exists = cursor.fetchone()[0]
            
            if not chat_history_exists:
                logger.info("Creating chat_history table...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        chat_id SERIAL PRIMARY KEY,
                        user_message TEXT NOT NULL,
                        bot_response TEXT NOT NULL,
                        context VARCHAR(50) NOT NULL,
                        tanker_id VARCHAR(50),
                        intent VARCHAR(50),
                        topic VARCHAR(50),
                        confidence_score DECIMAL(5, 4),
                        response_metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_history_context ON chat_history(context);
                    CREATE INDEX IF NOT EXISTS idx_chat_history_tanker ON chat_history(tanker_id);
                    CREATE INDEX IF NOT EXISTS idx_chat_history_intent ON chat_history(intent);
                    CREATE INDEX IF NOT EXISTS idx_chat_history_created ON chat_history(created_at);
                """)
                logger.info("chat_history table created")
            
            # Check if chat_feedback table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'chat_feedback'
                )
            """)
            chat_feedback_exists = cursor.fetchone()[0]
            
            if not chat_feedback_exists:
                logger.info("Creating chat_feedback table...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_feedback (
                        feedback_id SERIAL PRIMARY KEY,
                        chat_id INTEGER REFERENCES chat_history(chat_id) ON DELETE CASCADE,
                        feedback_type VARCHAR(20) NOT NULL,
                        feedback_value INTEGER,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_feedback_chat_id ON chat_feedback(chat_id);
                """)
                logger.info("chat_feedback table created")
            
            # Check if chat_learning_patterns table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'chat_learning_patterns'
                )
            """)
            chat_patterns_exists = cursor.fetchone()[0]
            
            if not chat_patterns_exists:
                logger.info("Creating chat_learning_patterns table...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_learning_patterns (
                        pattern_id SERIAL PRIMARY KEY,
                        question_pattern TEXT NOT NULL,
                        intent VARCHAR(50) NOT NULL,
                        topic VARCHAR(50),
                        suggested_response_template TEXT,
                        usage_count INTEGER DEFAULT 1,
                        success_rate DECIMAL(5, 4),
                        last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_learning_patterns_intent ON chat_learning_patterns(intent);
                    CREATE INDEX IF NOT EXISTS idx_chat_learning_patterns_usage ON chat_learning_patterns(usage_count DESC);
                """)
                logger.info("chat_learning_patterns table created")
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.warning(f"Error ensuring chat tables exist: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False
    
    def normalize_question(self, question: str) -> str:
        """
        Normalize a question for pattern matching
        - Lowercase
        - Remove special characters
        - Remove extra spaces
        """
        normalized = question.lower().strip()
        # Remove special characters but keep spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def classify_intent(self, question: str) -> Tuple[str, float]:
        """
        Classify user intent from question
        Returns: (intent, confidence_score)
        
        Uses rule-based classification initially, can be enhanced with ML
        """
        question_lower = question.lower()
        scores = {}
        
        # Check against intent keywords
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in question_lower)
            if score > 0:
                scores[intent] = score / len(keywords)  # Normalize by keyword count
        
        # Check learned patterns
        if not self.pattern_cache_loaded:
            self._load_learned_patterns()
        
        # Find similar patterns
        normalized_q = self.normalize_question(question)
        for pattern, pattern_data in self.learned_patterns.items():
            similarity = difflib.SequenceMatcher(None, normalized_q, pattern).ratio()
            if similarity > 0.7:  # 70% similarity threshold
                pattern_intent = pattern_data.get('intent', 'general_help')
                pattern_score = similarity * pattern_data.get('success_rate', 0.5)
                if pattern_intent in scores:
                    scores[pattern_intent] = max(scores[pattern_intent], pattern_score)
                else:
                    scores[pattern_intent] = pattern_score
        
        if scores:
            # Get intent with highest score
            best_intent = max(scores.items(), key=lambda x: x[1])
            confidence = min(best_intent[1] * 2, 1.0)  # Scale to 0-1
            return best_intent[0], confidence
        
        # Default to general_help
        return 'general_help', 0.3
    
    def classify_topic(self, question: str, tanker_id: Optional[str] = None) -> str:
        """
        Classify question topic
        """
        question_lower = question.lower()
        
        # If tanker_id is present, likely specific_tanker
        if tanker_id:
            return 'specific_tanker'
        
        # Check topic keywords
        for topic, keywords in self.topic_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                return topic
        
        return 'general'
    
    def store_chat_interaction(
        self,
        user_message: str,
        bot_response: str,
        context: str,
        tanker_id: Optional[str] = None,
        intent: Optional[str] = None,
        topic: Optional[str] = None,
        confidence: Optional[float] = None,
        response_metadata: Optional[Dict] = None
    ) -> Optional[int]:
        """
        Store a chat interaction in the database
        Returns: chat_id if successful, None otherwise
        Self-healing: Creates tables if missing
        """
        # Ensure tables exist (self-healing)
        if not self.ensure_chat_tables_exist():
            logger.warning("Chat tables not available - chat learning disabled")
            return None
        
        conn = self.get_db_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Classify if not provided
            if intent is None or confidence is None:
                intent, confidence = self.classify_intent(user_message)
            
            if topic is None:
                topic = self.classify_topic(user_message, tanker_id)
            
            # Prepare metadata
            metadata_json = json.dumps(response_metadata or {})
            
            cursor.execute("""
                INSERT INTO chat_history 
                (user_message, bot_response, context, tanker_id, intent, topic, confidence_score, response_metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING chat_id
            """, (
                user_message,
                bot_response,
                context,
                tanker_id,
                intent,
                topic,
                confidence,
                metadata_json
            ))
            
            chat_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.debug(f"Stored chat interaction: chat_id={chat_id}, intent={intent}, confidence={confidence:.2f}")
            
            # Update learned patterns asynchronously (don't block)
            self._update_learned_patterns_async(user_message, intent, topic)
            
            return chat_id
            
        except psycopg2_errors.UndefinedTable as e:
            # Table missing - try to create and retry once
            logger.warning(f"Chat table missing: {e}. Attempting to create...")
            if conn:
                conn.rollback()
                conn.close()
            if self.ensure_chat_tables_exist():
                # Retry once after creating tables
                return self.store_chat_interaction(user_message, bot_response, context, tanker_id, intent, topic, confidence, response_metadata)
            return None
        except Exception as e:
            logger.warning(f"Error storing chat interaction (non-critical): {e}")
            if conn:
                conn.rollback()
                conn.close()
            return None
    
    def find_similar_questions(self, question: str, limit: int = 5) -> List[Dict]:
        """
        Find similar questions from chat history
        Returns list of similar questions with their responses
        Self-healing: Gracefully handles missing tables
        """
        # Ensure tables exist
        if not self.ensure_chat_tables_exist():
            return []  # Return empty if tables unavailable
        
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            normalized_q = self.normalize_question(question)
            
            # Get recent chat history
            cursor.execute("""
                SELECT chat_id, user_message, bot_response, intent, topic, confidence_score, created_at
                FROM chat_history
                WHERE created_at > NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC
                LIMIT 100
            """)
            
            history = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Calculate similarity scores
            similar_questions = []
            for record in history:
                hist_q = self.normalize_question(record['user_message'])
                similarity = difflib.SequenceMatcher(None, normalized_q, hist_q).ratio()
                
                if similarity > 0.5:  # 50% similarity threshold
                    similar_questions.append({
                        'chat_id': record['chat_id'],
                        'question': record['user_message'],
                        'response': record['bot_response'],
                        'similarity': similarity,
                        'intent': record['intent'],
                        'created_at': record['created_at'].isoformat() if record['created_at'] else None
                    })
            
            # Sort by similarity and return top N
            similar_questions.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_questions[:limit]
            
        except psycopg2_errors.UndefinedTable:
            # Table missing - graceful degradation
            if conn:
                conn.close()
            return []
        except Exception as e:
            logger.warning(f"Error finding similar questions (non-critical): {e}")
            if conn:
                conn.close()
            return []
    
    def get_improved_response_suggestions(self, question: str, intent: str) -> Optional[Dict]:
        """
        Get suggestions for improving response based on learned patterns
        Returns suggestions like: verbosity level, include ETA automatically, etc.
        """
        if not self.pattern_cache_loaded:
            self._load_learned_patterns()
        
        normalized_q = self.normalize_question(question)
        
        # Find matching pattern
        best_match = None
        best_similarity = 0
        
        for pattern, pattern_data in self.learned_patterns.items():
            if pattern_data.get('intent') == intent:
                similarity = difflib.SequenceMatcher(None, normalized_q, pattern).ratio()
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = pattern_data
        
        if best_match and best_similarity > 0.7:
            return {
                'suggested_template': best_match.get('suggested_response_template'),
                'confidence': best_similarity,
                'usage_count': best_match.get('usage_count', 1),
                'success_rate': best_match.get('success_rate', 0.5)
            }
        
        return None
    
    def record_feedback(
        self,
        chat_id: int,
        feedback_type: str,
        feedback_value: Optional[int] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Record feedback for a chat interaction
        feedback_type: 'explicit_helpful', 'explicit_not_helpful', 'implicit_followup', 'implicit_clarification'
        feedback_value: 1 for positive, 0 for negative (None for implicit)
        Self-healing: Creates tables if missing
        """
        # Ensure tables exist
        if not self.ensure_chat_tables_exist():
            return False  # Fail silently if tables unavailable
        
        conn = self.get_db_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO chat_feedback 
                (chat_id, feedback_type, feedback_value, notes)
                VALUES (%s, %s, %s, %s)
            """, (chat_id, feedback_type, feedback_value, notes))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Update learned patterns based on feedback
            self._update_pattern_success_rate_async(chat_id, feedback_type, feedback_value)
            
            return True
            
        except psycopg2_errors.UndefinedTable:
            # Table missing - graceful degradation
            if conn:
                conn.rollback()
                conn.close()
            return False
        except Exception as e:
            logger.warning(f"Error recording feedback (non-critical): {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False
    
    def _load_learned_patterns(self):
        """Load learned patterns from database into cache"""
        # Ensure tables exist
        if not self.ensure_chat_tables_exist():
            self.pattern_cache_loaded = True
            return
        
        conn = self.get_db_connection()
        if not conn:
            self.pattern_cache_loaded = True
            return
        
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            cursor.execute("""
                SELECT question_pattern, intent, topic, suggested_response_template, 
                       usage_count, success_rate
                FROM chat_learning_patterns
                WHERE usage_count >= 2
                ORDER BY success_rate DESC, usage_count DESC
                LIMIT 100
            """)
            
            patterns = cursor.fetchall()
            cursor.close()
            conn.close()
            
            self.learned_patterns = {}
            for pattern in patterns:
                self.learned_patterns[pattern['question_pattern']] = {
                    'intent': pattern['intent'],
                    'topic': pattern['topic'],
                    'suggested_response_template': pattern['suggested_response_template'],
                    'usage_count': pattern['usage_count'],
                    'success_rate': float(pattern['success_rate']) if pattern['success_rate'] else 0.5
                }
            
            self.pattern_cache_loaded = True
            logger.debug(f"Loaded {len(self.learned_patterns)} learned patterns")
            
        except psycopg2_errors.UndefinedTable:
            # Table missing - graceful degradation
            self.pattern_cache_loaded = True
            if conn:
                conn.close()
        except Exception as e:
            logger.warning(f"Error loading learned patterns (non-critical): {e}")
            self.pattern_cache_loaded = True
            if conn:
                conn.close()
    
    def _update_learned_patterns_async(self, question: str, intent: str, topic: str):
        """
        Update learned patterns asynchronously (non-blocking)
        This runs in background to avoid slowing down chat responses
        Self-healing: Creates tables if missing
        """
        try:
            # Ensure tables exist
            if not self.ensure_chat_tables_exist():
                return  # Fail silently if tables unavailable
            
            normalized_q = self.normalize_question(question)
            
            conn = self.get_db_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # Check if pattern exists
            cursor.execute("""
                SELECT pattern_id, usage_count, success_rate
                FROM chat_learning_patterns
                WHERE question_pattern = %s
            """, (normalized_q,))
            
            result = cursor.fetchone()
            
            if result:
                # Update existing pattern
                pattern_id, usage_count, success_rate = result
                new_usage_count = usage_count + 1
                cursor.execute("""
                    UPDATE chat_learning_patterns
                    SET usage_count = %s, last_used_at = CURRENT_TIMESTAMP
                    WHERE pattern_id = %s
                """, (new_usage_count, pattern_id))
            else:
                # Insert new pattern
                cursor.execute("""
                    INSERT INTO chat_learning_patterns
                    (question_pattern, intent, topic, usage_count)
                    VALUES (%s, %s, %s, 1)
                """, (normalized_q, intent, topic))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Reload cache
            self.pattern_cache_loaded = False
            
        except psycopg2_errors.UndefinedTable:
            # Table missing - graceful degradation
            if 'conn' in locals() and conn:
                conn.close()
        except Exception as e:
            logger.debug(f"Error updating learned patterns (non-critical): {e}")
            if 'conn' in locals() and conn:
                conn.close()
    
    def _update_pattern_success_rate_async(self, chat_id: int, feedback_type: str, feedback_value: Optional[int]):
        """
        Update pattern success rate based on feedback
        """
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            
            # Get the chat record
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT user_message, intent, topic
                FROM chat_history
                WHERE chat_id = %s
            """, (chat_id,))
            
            chat = cursor.fetchone()
            if not chat:
                cursor.close()
                conn.close()
                return
            
            normalized_q = self.normalize_question(chat['user_message'])
            
            # Find matching pattern
            cursor.execute("""
                SELECT pattern_id, usage_count, success_rate
                FROM chat_learning_patterns
                WHERE question_pattern = %s
            """, (normalized_q,))
            
            pattern = cursor.fetchone()
            
            if pattern:
                pattern_id, usage_count, current_success_rate = pattern
                
                # Calculate new success rate
                # For explicit feedback: 1 = helpful, 0 = not helpful
                # For implicit followup: assume negative (user needed clarification)
                if feedback_type.startswith('explicit'):
                    is_positive = feedback_value == 1
                else:
                    is_positive = False  # Implicit feedback (followup/clarification) is negative
                
                # Update success rate using moving average
                if current_success_rate is None:
                    current_success_rate = 0.5
                
                # Weighted average: more weight to recent feedback
                new_success_rate = (current_success_rate * 0.7) + (1.0 if is_positive else 0.0) * 0.3
                
                cursor.execute("""
                    UPDATE chat_learning_patterns
                    SET success_rate = %s
                    WHERE pattern_id = %s
                """, (new_success_rate, pattern_id))
                
                conn.commit()
            
            cursor.close()
            conn.close()
            
            # Reload cache
            self.pattern_cache_loaded = False
            
        except psycopg2_errors.UndefinedTable:
            # Table missing - graceful degradation
            if 'conn' in locals() and conn:
                conn.close()
        except Exception as e:
            logger.debug(f"Error updating pattern success rate (non-critical): {e}")
            if 'conn' in locals() and conn:
                conn.close()
    
    def get_followup_suggestions(self, question: str, intent: str, topic: str) -> List[str]:
        """
        Generate follow-up question suggestions based on intent and topic
        """
        suggestions = []
        
        if intent == 'tanker_status' and topic == 'specific_tanker':
            suggestions = [
                "What is the ETA?",
                "Show me the route",
                "What is the current speed?"
            ]
        elif intent == 'eta_inquiry':
            suggestions = [
                "Why might it be delayed?",
                "Show me the route details",
                "What is the current status?"
            ]
        elif intent == 'trend_analysis':
            suggestions = [
                "Show me delay patterns",
                "What are the most common routes?",
                "Which tankers are most efficient?"
            ]
        else:
            suggestions = [
                "Tell me more",
                "Show me related information",
                "What else can you help with?"
            ]
        
        return suggestions[:3]  # Return top 3


# Global instance
_chat_intelligence = None

def get_chat_intelligence() -> ChatIntelligence:
    """Get or create global ChatIntelligence instance"""
    global _chat_intelligence
    if _chat_intelligence is None:
        _chat_intelligence = ChatIntelligence()
    return _chat_intelligence

