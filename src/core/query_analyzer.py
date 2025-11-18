"""Query analyzer for complexity detection and capability requirements."""

import logging
import re
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes queries to determine complexity and required capabilities."""

    def __init__(self, embeddings_provider=None):
        """Initialize query analyzer with optional embeddings provider for topic detection.

        Args:
            embeddings_provider: Optional EmbeddingsProvider instance for semantic analysis
        """
        self.embeddings_provider = embeddings_provider
        if self.embeddings_provider:
            logger.debug("QueryAnalyzer initialized with embeddings provider")
        else:
            logger.debug("QueryAnalyzer initialized without embeddings (topic shift detection disabled)")

    # Keywords for different query types
    WEB_SEARCH_KEYWORDS = [
        "current",
        "latest",
        "today",
        "recent",
        "news",
        "stock price",
        "what's the",
        "search for",
        "find information",
        "find",  # "find a sensor", "find me"
        "look up",
        "look online",  # "can you look online"
        "look for",  # "look for the part"
        "search online",
        "check online",  # "check online for me"
        "check",  # "check prices"
        "show me",  # "show me options"
        "get me",  # "get me prices"
        "where can i find",
        "where to buy",
        "update",
        "happening",
        "status",
        "price",
        "weather",
        "best",  # Product recommendations
        "recommend",  # Recommendations need current data
        "top",  # Top products/rankings
        "compare",  # Product comparisons
        "which",  # "which graphics card" etc
        "should i buy",  # Shopping advice
        "worth it",  # Product value questions
        "available",  # "what's available"
        "in stock",  # "is it in stock"
    ]

    # Implicit web search indicators (things that change frequently)
    WEB_SEARCH_IMPLICIT = [
        "cost",
        "price",
        "weather",
        "temperature",
        "forecast",
        "score",
        "result",
        "winner",
        "leader",
        "ranking",
        "exchange rate",
        "stock",
        "market",
        "trending",
    ]

    # Product/spec queries that need web verification
    WEB_SEARCH_SPECS = [
        "spec",
        "specification",
        "datasheet",
        "data sheet",
        "conflicting",
        "check sources",
        "fake spec",
        "verify",
        "at least two sources",
        "cross-check",
        "compare specs",
        "official spec",
        "manufacturer spec",
        "real spec",
    ]

    # Time-sensitive keywords that suggest current data needed
    TIME_SENSITIVE = [
        "now",
        "currently",
        "today",
        "this week",
        "this month",
        "this year",
        "2024",
        "2025",
        "2026",
        "recently",
        "just",
        "latest",
        "new",  # New releases/products
        "upcoming",  # Future events/products
        "announced",  # Recent announcements
    ]
    
    # Fresh information topics that always need web search
    FRESH_INFO_TOPICS = [
        "ai model",  # AI models evolve rapidly
        "llm",  # Language models
        "crypto",  # Cryptocurrency prices
        "bitcoin",
        "ethereum",
        "stock",  # Stock prices
        "news",  # News by definition
        "weather",  # Weather changes
        "sports",  # Sports scores
        "election",  # Political events
        "covid",  # Pandemic info
        "vaccine",  # Medical updates
        "release date",  # Product releases
        "announcement",  # Company/product announcements
    ]

    CODE_EXEC_KEYWORDS = [
        "calculate",
        "compute",
        "sum",
        "average",
        "analyze data",
        "plot",
        "graph",
        "chart",
        "statistics",
        "math",
        "range",
        "hours",
        "wh",
        "kwh",
        "watt",
        "miles",
        "km",
        "energy",
        "capacity",
        "pack",
        "battery",
        "date",
        "time",
        "day",
        "month",
        "year",
    ]

    # Date/time query patterns (should use code_exec, not web_search)
    DATE_TIME_PATTERNS = [
        r"\bdate\b",
        r"\btime\b",
        r"\btoday\b.*\bdate\b",
        r"\bdate\b.*\btoday\b",
        r"\bcurrent\b.*\bdate\b",
        r"\bwhat.*day.*is.*it\b",
        r"\bwhat.*time.*is.*it\b",
    ]

    # Math/calculation patterns that strongly suggest code execution
    CODE_EXEC_PATTERNS = [
        r"\d+\s*wh",  # watt-hours
        r"\d+\s*kwh",  # kilowatt-hours
        r"\d+\s*w\b",  # watts
        r"\d+\s*ah",  # amp-hours
        r"\d+\s*mah",  # milliamp-hours
        r"\d+\s*v\b",  # volts
        r"(\d+)\s*[sS]\s*(\d+)\s*[pP]",  # battery pack configuration (14S5P, 14s5p, 14S 5P)
        r"how many.*hours",
        r"what.*range",
        r"total.*capacity",
        r"total.*energy",
        r"\d+.*cell",  # cell calculations
        r"pack.*energy",
        r"pack.*capacity",
    ]

    MEMORY_KEYWORDS = [
        "my",
        "remember",
        "recall",
        "you told me",
        "i mentioned",
        "i said",
        "my preference",
        "my schedule",
        "my goal",
        "save this",
        "store",
        "keep track",
    ]

    # Patterns for storing new information (user telling Kai something to remember)
    MEMORY_STORE_PATTERNS = [
        r"\bremember\s+(that\s+)?my",
        r"\bremember\s+(that\s+)?i",
        r"\bkeep\s+track\s+of",
        r"\bsave\s+(this|that)",
        r"\bstore\s+(this|that)",
        r"\bdon't\s+forget",
        r"\bmy\s+\w+\s+is\b",  # "my name is", "my favorite is"
    ]

    # Patterns for retrieving stored information
    MEMORY_RETRIEVE_PATTERNS = [
        r"\bwhat\s+(is|was)\s+my",
        r"\bdo\s+you\s+remember\s+(my|what)",
        r"\bwhat\s+did\s+i\s+(say|tell|mention)",
        r"\brecall\s+(my|what)",
    ]

    COMPLEX_KEYWORDS = [
        "analyze",
        "compare",
        "evaluate",
        "explain how",
        "why does",
        "break down",
        "step by step",
        "in detail",
        "comprehensive",
        "pros and cons",
        "advantages and disadvantages",
    ]

    MULTI_HOP_KEYWORDS = [
        "first",
        "then",
        "after that",
        "next",
        "finally",
        "compare and contrast",
        "how does",
        "relationship between",
        "based on",
        "given that",
        "assuming",
        "if",
    ]

    REASONING_KEYWORDS = [
        "because",
        "therefore",
        "thus",
        "consequently",
        "as a result",
        "due to",
        "leads to",
        "causes",
        "implies",
        "suggests",
    ]

    # High-stakes indicators that need better models
    HIGH_STAKES_KEYWORDS = [
        "show your work",
        "show your steps",
        "explain reasoning",
        "justify",
        "prove",
        "verify",
        "double check",
        "are you sure",
        "critical",
        "important",
        "need to be sure",
        "must be accurate",
    ]

    def detect_topic_shift(
        self,
        current_query: str,
        previous_topic_embedding: Optional[list[float]] = None,
        similarity_threshold: float = 0.5,
    ) -> tuple[bool, Optional[list[float]]]:
        """Detect if query represents a topic shift from previous conversation.

        Uses semantic similarity between current query and previous topic embedding.
        If similarity < threshold, considers it a topic shift.

        Args:
            current_query: Current user query
            previous_topic_embedding: Embedding of previous topic (from conversation)
            similarity_threshold: Threshold below which is considered a shift (default 0.5)

        Returns:
            Tuple of (is_topic_shift, current_query_embedding)
        """
        if not self.embeddings_provider or not previous_topic_embedding:
            # No provider or no previous topic - can't detect shift
            current_embedding = self._generate_embedding(current_query)
            return False, current_embedding

        # Generate embedding for current query
        current_embedding = self._generate_embedding(current_query)

        if not current_embedding:
            return False, None

        # Calculate cosine similarity
        try:
            similarity = self._cosine_similarity(
                np.array(current_embedding), np.array(previous_topic_embedding)
            )

            is_shift = similarity < similarity_threshold

            # Classify the type of topic shift
            shift_type = None
            if is_shift:
                if similarity < 0.2:
                    shift_type = "major"  # Completely different topic
                elif similarity < 0.4:
                    shift_type = "moderate"  # Related but different
                else:
                    shift_type = "minor"  # Slightly different angle

            if is_shift:
                logger.info(
                    f"Topic shift detected ({shift_type}): similarity={similarity:.3f} < {similarity_threshold}"
                )
            else:
                logger.debug(f"Same topic (similarity: {similarity:.3f})")

            return is_shift, current_embedding
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return False, current_embedding

    def _generate_embedding(self, text: str) -> Optional[list[float]]:
        """Generate embedding for text using the configured provider.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if provider unavailable
        """
        if not self.embeddings_provider:
            return None

        try:
            embeddings = self.embeddings_provider.embed([text])
            return embeddings[0] if embeddings else None
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0.0 to 1.0)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def analyze(
        self, query_text: str, previous_topic_embedding: Optional[list[float]] = None
    ) -> dict[str, Any]:
        """Analyze query for complexity, capabilities, and topic shifts.

        Args:
            query_text: User query text
            previous_topic_embedding: Previous conversation topic embedding for shift detection

        Returns:
            Analysis dict with complexity, capabilities, complexity_score, topic_shift, etc.
        """
        text_lower = query_text.lower()

        # Detect topic shift
        topic_shift, current_embedding = self.detect_topic_shift(
            query_text, previous_topic_embedding
        )

        # Detect required capabilities
        capabilities = []

        if self._needs_web_search(text_lower):
            capabilities.append("web_search")

        if self._needs_code_execution(text_lower):
            capabilities.append("code_exec")

        if self._needs_memory_retrieval(text_lower):
            capabilities.append("rag")

        # Determine complexity and score
        complexity = self._determine_complexity(text_lower, capabilities)
        complexity_score = self._calculate_complexity_score(text_lower, capabilities)

        # Detect multi-hop reasoning
        requires_multi_hop = self._requires_multi_hop_reasoning(text_lower)

        # Detect memory operation type (store vs retrieve)
        memory_operation = (
            self._detect_memory_operation(text_lower) if "rag" in capabilities else None
        )

        # Determine routing
        routing = self._determine_routing(complexity, capabilities, complexity_score)

        return {
            "complexity_level": complexity,
            "complexity_score": complexity_score,  # 0.0-1.0 scale
            "required_capabilities": capabilities,
            "requires_multi_hop": requires_multi_hop,
            "routing_decision": routing,
            "confidence": 0.85,  # Placeholder confidence
            "topic_shift": topic_shift,
            "current_topic_embedding": current_embedding,
            "memory_operation": memory_operation,  # "store" | "retrieve" | None
        }

    def _needs_web_search(self, text: str) -> bool:
        """Check if query needs web search (explicit or implicit).

        Detects:
        - Explicit requests ("search for", "look up")
        - Time-sensitive queries ("latest", "current", "today")
        - Information likely to be outdated (prices, weather, news)
        - Factual questions about current events
        - Product specifications and datasheets
        - Conflicting information that needs verification

        Args:
            text: Lowercase query text

        Returns:
            True if web search would be beneficial
        """
        # Price queries explicitly need web search
        price_patterns = [
            r'\b(what\'?s|what is|whats) the (cost|price)',
            r'\bhow much (does|will|is|are|do)',
            r'\blet me know.*\b(price|cost)',
            r'\btell me.*\b(price|cost)',
            r'\bprice for',
            r'\bcost (of|for)',
        ]
        if any(re.search(pattern, text) for pattern in price_patterns):
            logger.debug("Price query detected - needs web search")
            return True
        
        # Date/time queries should use code_exec, not web_search
        if any(re.search(pattern, text) for pattern in self.DATE_TIME_PATTERNS):
            logger.debug("Date/time query detected - will use code_exec, not web_search")
            return False

        # Explicit web search requests
        if any(keyword in text for keyword in self.WEB_SEARCH_KEYWORDS):
            return True

        # Product specs and verification needs (CRITICAL for accuracy)
        if any(keyword in text for keyword in self.WEB_SEARCH_SPECS):
            logger.debug("Web search needed: spec/verification keywords detected")
            return True

        # Time-sensitive queries - likely need current data
        if any(keyword in text for keyword in self.TIME_SENSITIVE):
            return True

        # Fresh information topics that always need web search
        if any(topic in text for topic in self.FRESH_INFO_TOPICS):
            logger.debug(f"Web search needed: fresh info topic detected")
            return True

        # Implicit indicators - things that change frequently
        if any(keyword in text for keyword in self.WEB_SEARCH_IMPLICIT):
            return True

        # Check for questions about current events (recent years)
        if re.search(r"\b(202[4-9]|20[3-9]\d)\b", text):  # Recent years
            return True

        # Simple factual questions that don't need web search (well-known facts)
        simple_factual_patterns = [
            r"\bwhat is the (capital|president|currency|population) of\b",
            r"\bwho is the (president|king|queen|leader|ceo) of\b",
            r"\bwhen (is|was) .{0,30}(born|founded|created|invented)\b",
        ]
        if any(re.search(pattern, text) for pattern in simple_factual_patterns):
            logger.debug("Simple factual query - using fast path, no web search")
            return False

        # Factual "who/what/where/when" questions (likely need verification)
        factual_patterns = [
            r"\bwho is\b",
            r"\bwhat is\b",
            r"\bwhere is\b",
            r"\bwhen did\b",
            r"\bwhen was\b",
            r"\bhow many\b",
        ]
        if any(re.search(pattern, text) for pattern in factual_patterns):
            # But not personal questions
            if not any(word in text for word in ["my", "i am", "me", "i'm"]):
                return True

        return False

    def _needs_code_execution(self, text: str) -> bool:
        """Check if query needs code execution.

        Args:
            text: Lowercase query text

        Returns:
            True if code execution needed
        """
        # Exclude memory/conversation queries that aren't calculations
        memory_query_patterns = [
            r'\b(do you |did you )?(remember|recall)\b',
            r'\bwhat (did|were) (we|i|you)',
            r'\b(our|the) (conversation|discussion|chat)',
        ]
        if any(re.search(pattern, text) for pattern in memory_query_patterns):
            # Unless there are explicit numbers/calculations
            if not re.search(r'\d+\s*[\+\-\*\/x×÷]\s*\d+', text):
                logger.debug("Memory query detected - NOT using code_exec")
                return False
        
        # Exclude information/listing queries that aren't calculations
        info_query_patterns = [
            r'\b(what|which|list|show|tell me about)\s+(are|is)?\s+(the\s+)?(latest|newest|current|best|top)',
            r'\b(latest|newest|current)\s+(ai|models?|llm|news|update)',
        ]
        if any(re.search(pattern, text) for pattern in info_query_patterns):
            logger.debug("Information query detected - NOT using code_exec")
            return False
        
        # Exclude workout/exercise/fitness queries (not calculations)
        workout_patterns = [
            r'\b(workout|exercise|train|fitness|gym)\b',
            r'\b(muscle|chest|back|legs|arms|abs|shoulders|bicep|tricep)\b',
            r'\b(cardio|strength|endurance|flexibility)\b',
        ]
        if any(re.search(pattern, text) for pattern in workout_patterns):
            # Unless there are explicit calculations
            if not re.search(r'\d+\s*[\+\-\*\/x×÷]\s*\d+', text):
                logger.debug("Workout/fitness query detected - NOT using code_exec")
                return False
        
        # Exclude workout/exercise/fitness queries (not calculations)
        workout_patterns = [
            r'\b(workout|exercise|train|fitness|gym)\b',
            r'\b(muscle|chest|back|legs|arms|abs)\b',
            r'\b(cardio|strength|endurance|flexibility)\b',
        ]
        if any(re.search(pattern, text) for pattern in workout_patterns):
            # Unless there are explicit calculations
            if not re.search(r'\d+\s*[\+\-\*\/x×÷]\s*\d+', text):
                logger.debug("Workout/fitness query detected - NOT using code_exec")
                return False

        # Date/time queries should use code_exec to get current date/time
        if any(re.search(pattern, text) for pattern in self.DATE_TIME_PATTERNS):
            logger.debug("Date/time query detected - will use code_exec")
            return True

        # Explicit keywords
        if any(keyword in text for keyword in self.CODE_EXEC_KEYWORDS):
            return True

        # Check for numerical computations
        if re.search(r"\d+\s*[\+\-\*\/]\s*\d+", text):
            return True

        # Check for unit-based calculations (batteries, energy, etc.)
        for pattern in self.CODE_EXEC_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(f"Code execution needed: pattern '{pattern}' matched")
                return True

        return False

    def _needs_memory_retrieval(self, text: str) -> bool:
        """Check if query needs memory/RAG retrieval.

        Args:
            text: Lowercase query text

        Returns:
            True if memory retrieval needed
        """
        return any(keyword in text for keyword in self.MEMORY_KEYWORDS)

    def _detect_memory_operation(self, text: str) -> str | None:
        """Detect if this is a memory store or retrieve operation.

        Args:
            text: Lowercase query text

        Returns:
            "store" if user wants to save info, "retrieve" if asking for saved info, None otherwise
        """
        # Check for store patterns
        for pattern in self.MEMORY_STORE_PATTERNS:
            if re.search(pattern, text):
                return "store"

        # Check for retrieve patterns
        for pattern in self.MEMORY_RETRIEVE_PATTERNS:
            if re.search(pattern, text):
                return "retrieve"

        # Default heuristic: if has "my" it's probably storing, if asking question it's retrieving
        if re.search(r"\bmy\s+\w+\s+(is|are)", text):
            return "store"

        if re.search(r"\b(what|which|who)\b.*\bmy\b", text):
            return "retrieve"

        return None

    def _determine_complexity(self, text: str, capabilities: list[str]) -> str:
        """Determine query complexity level.

        Args:
            text: Lowercase query text
            capabilities: Required capabilities list

        Returns:
            Complexity: simple, moderate, or complex
        """
        # Complex if needs code execution or 3+ tools
        if "code_exec" in capabilities or len(capabilities) >= 3:
            return "complex"

        # Complex if has complex keywords
        if any(keyword in text for keyword in self.COMPLEX_KEYWORDS):
            return "complex"

        # Moderate if needs any tools
        if len(capabilities) > 0:
            return "moderate"

        # Moderate for longer queries (more than 20 words)
        if len(text.split()) > 20:
            return "moderate"

        # Default to simple
        return "simple"

    def _determine_routing(
        self, complexity: str, capabilities: list[str], complexity_score: float
    ) -> str:
        """Determine routing hint (actual model selection in orchestrator).

        Args:
            complexity: Complexity level
            capabilities: Required capabilities
            complexity_score: Numeric complexity score (0.0-1.0)

        Returns:
            Routing hint: 'local' or 'external' (orchestrator picks specific tier)
        """
        # Orchestrator now handles tier selection based on complexity_score
        # This method just provides a high-level hint

        # Simple queries use local
        if complexity_score < 0.3:
            return "local"

        # Everything else goes to external (orchestrator picks tier)
        return "external"

    def _calculate_complexity_score(self, text: str, capabilities: list[str]) -> float:
        """Calculate numeric complexity score (0.0-1.0).

        Args:
            text: Lowercase query text
            capabilities: Required capabilities

        Returns:
            Complexity score from 0.0 (simple) to 1.0 (very complex)
        """
        score = 0.0

        # Base score from capabilities
        score += len(capabilities) * 0.15

        # HIGH STAKES BOOST - user explicitly needs accuracy
        high_stakes_count = sum(1 for kw in self.HIGH_STAKES_KEYWORDS if kw in text)
        if high_stakes_count > 0:
            score += 0.25  # Significant boost for verification requests
            logger.debug(f"High-stakes query detected ({high_stakes_count} indicators)")

        # Spec/verification queries are inherently higher complexity
        spec_count = sum(1 for kw in self.WEB_SEARCH_SPECS if kw in text)
        if spec_count > 0:
            score += 0.2  # Boost for spec verification needs

        # Bonus for complex keywords
        complex_count = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in text)
        score += min(complex_count * 0.1, 0.3)

        # Bonus for multi-hop indicators
        multi_hop_count = sum(1 for kw in self.MULTI_HOP_KEYWORDS if kw in text)
        score += min(multi_hop_count * 0.15, 0.3)

        # Bonus for reasoning indicators
        reasoning_count = sum(1 for kw in self.REASONING_KEYWORDS if kw in text)
        score += min(reasoning_count * 0.1, 0.2)

        # Query length factor
        word_count = len(text.split())
        if word_count > 50:
            score += 0.2
        elif word_count > 30:
            score += 0.1

        # Number of questions (indicates multi-part query)
        question_count = text.count("?")
        if question_count > 1:
            score += 0.15

        # Clamp to 0.0-1.0 range
        return min(1.0, max(0.0, score))

    def _requires_multi_hop_reasoning(self, text: str) -> bool:
        """Check if query requires multi-hop reasoning.

        Multi-hop reasoning involves:
        - Sequential steps (first X, then Y)
        - Comparisons requiring multiple retrievals
        - Conditional logic

        Args:
            text: Lowercase query text

        Returns:
            True if multi-hop reasoning detected
        """
        # Check for multi-hop keywords
        if any(kw in text for kw in self.MULTI_HOP_KEYWORDS):
            return True

        # Multiple questions suggest multi-hop
        if text.count("?") > 1:
            return True

        # Comparison queries
        if "compare" in text or "versus" in text or "vs" in text:
            return True

        # Conditional queries
        if any(word in text for word in ["if", "when", "unless", "provided that"]):
            return True

        return False
