"""Sentiment analysis tool using VADER for emotion detection."""

import logging
import time
from typing import Any

from src.tools.base_tool import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class SentimentAnalyzerTool(BaseTool):
    """Tool for analyzing emotional tone and sentiment in text."""

    def __init__(self, config: dict[str, Any]):
        """Initialize sentiment analyzer.

        Args:
            config: Tool configuration
        """
        super().__init__(config)
        self.analyzer = None
        self._init_vader()

    def _init_vader(self):
        """Initialize VADER sentiment analyzer."""
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self.analyzer = SentimentIntensityAnalyzer()
            logger.info("VADER sentiment analyzer initialized")
        except ImportError:
            logger.warning("vaderSentiment not installed, using mock analyzer")
            self.analyzer = None

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Analyze sentiment and emotion in text.

        Args:
            parameters: Dict with 'text' key

        Returns:
            ToolResult with emotion classification and scores
        """
        start_time = time.time()

        try:
            text = parameters.get("text", "")

            if not text:
                # Return neutral sentiment for empty text instead of error
                logger.warning("No text provided for sentiment analysis, returning neutral")
                elapsed_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.SUCCESS,
                    data={
                        "emotion": "neutral",
                        "confidence": 0.0,
                        "scores": {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0},
                        "is_negative": False,
                        "is_positive": False,
                        "text_length": 0,
                    },
                    execution_time_ms=elapsed_ms,
                )

            # Analyze sentiment
            if self.analyzer:
                scores = self.analyzer.polarity_scores(text)
            else:
                # Mock analyzer for testing
                scores = self._mock_sentiment(text)

            # Classify emotion based on scores and keywords
            emotion = self._classify_emotion(text, scores)

            # Determine confidence
            confidence = max(abs(scores["pos"]), abs(scores["neg"]), abs(scores["neu"]))

            result = {
                "emotion": emotion,
                "confidence": confidence,
                "scores": scores,
                "is_negative": scores["compound"] < -0.05,
                "is_positive": scores["compound"] > 0.05,
                "is_neutral": -0.05 <= scores["compound"] <= 0.05,
            }

            elapsed_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Sentiment analysis: emotion={emotion}, "
                f"compound={scores['compound']:.2f}, "
                f"confidence={confidence:.2f}"
            )

            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=result,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Sentiment analysis failed: {e}")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    def _classify_emotion(self, text: str, scores: dict[str, float]) -> str:
        """Classify emotion based on sentiment scores and keywords.

        Emotion categories:
        - neutral: No strong sentiment
        - positive: Happy, excited, grateful
        - distressed: Worried, anxious, overwhelmed
        - frustrated: Angry, annoyed, disappointed
        - excited: Enthusiastic, eager

        Args:
            text: Input text
            scores: VADER sentiment scores

        Returns:
            Emotion classification
        """
        text_lower = text.lower()
        compound = scores["compound"]

        # Check for distress keywords
        distress_keywords = [
            "worried",
            "anxious",
            "stressed",
            "overwhelmed",
            "scared",
            "afraid",
            "concerned",
            "nervous",
            "panicking",
            "help me",
            "don't know what to do",
            "struggling",
            "difficult",
        ]
        if any(keyword in text_lower for keyword in distress_keywords):
            return "distressed"

        # Check for frustration keywords
        frustration_keywords = [
            "frustrated",
            "annoyed",
            "angry",
            "irritated",
            "upset",
            "disappointed",
            "why won't",
            "this doesn't work",
            "stupid",
            "hate",
            "terrible",
            "awful",
            "ridiculous",
        ]
        if any(keyword in text_lower for keyword in frustration_keywords):
            return "frustrated"

        # Check for excitement keywords
        excitement_keywords = [
            "excited",
            "amazing",
            "awesome",
            "fantastic",
            "wonderful",
            "love",
            "can't wait",
            "thrilled",
            "eager",
            "brilliant",
            "excellent",
            "perfect",
        ]
        if any(keyword in text_lower for keyword in excitement_keywords):
            return "excited"

        # Use compound score for general classification
        if compound >= 0.5:
            return "positive"
        elif compound <= -0.5:
            return "frustrated"
        elif compound <= -0.05:
            # Mild negative could be distressed
            if scores["neg"] > 0.3:
                return "distressed"
            return "neutral"
        else:
            return "neutral"

    def _mock_sentiment(self, text: str) -> dict[str, float]:
        """Mock sentiment analysis for testing without VADER.

        Args:
            text: Input text

        Returns:
            Mock sentiment scores
        """
        text_lower = text.lower()

        # Simple keyword-based mock
        positive_words = ["good", "great", "happy", "love", "excellent", "amazing"]
        negative_words = ["bad", "terrible", "hate", "awful", "sad", "worried"]

        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        total = max(pos_count + neg_count, 1)
        pos_score = pos_count / total
        neg_score = neg_count / total
        neu_score = 1.0 - (pos_score + neg_score)

        compound = pos_score - neg_score

        return {
            "pos": pos_score,
            "neg": neg_score,
            "neu": neu_score,
            "compound": compound,
        }

    async def fallback(self, parameters: dict[str, Any], error: Exception) -> ToolResult:
        """Fallback to neutral sentiment on failure.

        Args:
            parameters: Original parameters
            error: Exception that caused failure

        Returns:
            ToolResult with neutral sentiment
        """
        logger.warning(f"Sentiment analysis fallback: {error}")

        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.SUCCESS,
            data={
                "emotion": "neutral",
                "confidence": 0.5,
                "scores": {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0},
                "is_negative": False,
                "is_positive": False,
                "is_neutral": True,
            },
            execution_time_ms=0,
            fallback_used=True,
        )
