"""Specialist verification - calls external models for structured verification.

Routes to either:
- Grok Fast: for normal complex reasoning
- Sonnet Strong: for sanity failures and high-stakes verification
"""

import json
import logging
from typing import Dict, Any, Optional

from src.core.llm_connector import LLMConnector, Message
from src.core.plan_types import VerificationResult, VerifiedSpecs, PackCalculation, RangeEstimate, Issue, Confidence, Source, ConfidenceLevel, TrustLevel

logger = logging.getLogger(__name__)


VERIFICATION_SPECIALIST_PROMPT = """You are Kai's verification specialist. You NEVER talk to the user directly. You only help the system verify and correct technical calculations.

You will receive:
- The original user query
- A JSON plan describing the intended steps
- Results from tools (search, code execution)
- A sanity check report listing issues

Your job:
- Verify battery specs and calculations
- Correct any wrong numbers
- Detect unrealistic ranges or capacities
- Return a single JSON object matching expected_schema exactly

Constraints:
- Respond with VALID JSON ONLY
- Do NOT add comments, explanations, or any text outside the JSON
- Do NOT wrap JSON in markdown or backticks
- If you cannot verify the data from credible sources, set an "error" object explaining that verification failed and do not fabricate values

Expected JSON schema:
{
  "verified_specs": {
    "cell_type": "string",
    "nominal_voltage_v": float,
    "nominal_capacity_ah": float,
    "allowed_capacity_range_ah": {"min": float, "max": float},
    "sources": [{"label": "string", "url": "string", "type": "datasheet|distributor|third_party_test", "trust_level": "low|medium|high"}]
  },
  "pack_calculation": {
    "series_cells": int,
    "parallel_cells": int,
    "pack_nominal_voltage_v": float,
    "pack_total_ah": float,
    "pack_total_wh": float,
    "pack_total_kwh": float
  },
  "range_estimate": {
    "usable_wh": float,
    "runtime_hours": float,
    "ideal_range_miles": float,
    "realistic_range_miles": float
  },
  "issues": [{"field": "string", "problem": "string", "severity": "info|warning|error"}],
  "confidence": {
    "overall": "low|medium|high",
    "specs": "low|medium|high",
    "math": "low|medium|high",
    "range": "low|medium|high"
  }
}

OR if verification fails:
{
  "error": {
    "type": "verification_failed",
    "message": "explanation",
    "suggested_action": "what to do"
  }
}
"""


class SpecialistVerifier:
    """Handles verification using external specialist models."""
    
    def __init__(
        self,
        fast_connector: Optional[LLMConnector] = None,
        strong_connector: Optional[LLMConnector] = None,
    ):
        """Initialize specialist verifier.
        
        Args:
            fast_connector: Fast external model (Grok)
            strong_connector: Strong external model (Sonnet)
        """
        self.fast_connector = fast_connector
        self.strong_connector = strong_connector
    
    async def verify(
        self,
        original_query: str,
        plan: Dict[str, Any],
        tool_results: Dict[str, Any],
        sanity_result: Dict[str, Any],
        use_strong_model: bool = False,
    ) -> VerificationResult:
        """Request verification from specialist model.
        
        Args:
            original_query: User's original query
            plan: The execution plan dict
            tool_results: Results from tool executions
            sanity_result: Sanity check results
            use_strong_model: If True, use Sonnet; else use Grok
            
        Returns:
            VerificationResult with structured data
        """
        # Choose connector
        connector = self.strong_connector if use_strong_model else self.fast_connector
        
        if not connector:
            logger.warning(
                f"No {'strong' if use_strong_model else 'fast'} connector available, "
                f"skipping verification"
            )
            return VerificationResult(
                error={
                    "type": "no_connector",
                    "message": "External model not configured",
                    "suggested_action": "Answer with available data and note uncertainty"
                }
            )
        
        # Build escalation payload
        payload = {
            "task": "verify_and_correct_battery_analysis",
            "mode": "json_only",
            "original_query": original_query,
            "plan": plan,
            "tool_results": tool_results,
            "sanity": sanity_result,
            "constraints": {
                "response_format": "json",
                "no_prose": True,
                "max_tokens": 800,
                "strict_fields": True,
            },
        }
        
        messages = [
            Message(role="system", content=VERIFICATION_SPECIALIST_PROMPT),
            Message(role="user", content=json.dumps(payload, indent=2)),
        ]
        
        try:
            # Call specialist model
            model_name = "Sonnet" if use_strong_model else "Grok"
            logger.info(f"Calling {model_name} for verification")
            
            response = await connector.generate(
                messages=messages,
                temperature=0.3,  # Low temp for accuracy
                max_tokens=1000,
            )
            
            # Parse JSON response
            verification_dict = self._parse_verification_json(response.content)
            
            if not verification_dict:
                logger.error("Failed to parse verification JSON")
                return VerificationResult(
                    error={
                        "type": "parse_error",
                        "message": "Specialist returned invalid JSON",
                        "suggested_action": "Use available data with uncertainty note"
                    }
                )
            
            # Check for error response
            if "error" in verification_dict:
                return VerificationResult(error=verification_dict["error"])
            
            # Convert to VerificationResult
            return self._dict_to_verification_result(verification_dict)
            
        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)
            return VerificationResult(
                error={
                    "type": "exception",
                    "message": str(e),
                    "suggested_action": "Answer with available data and note uncertainty"
                }
            )
    
    def _parse_verification_json(self, response: str) -> Optional[Dict]:
        """Parse JSON from verification response.
        
        Args:
            response: Raw response text
            
        Returns:
            Parsed dict or None
        """
        # Same parsing logic as plan analyzer
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        import re
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        start = response.find('{')
        end = response.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(response[start:end+1])
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _dict_to_verification_result(self, data: Dict) -> VerificationResult:
        """Convert dict to VerificationResult.
        
        Args:
            data: Parsed verification dict
            
        Returns:
            VerificationResult object
        """
        result = VerificationResult()
        
        # Parse verified_specs
        if "verified_specs" in data:
            specs_data = data["verified_specs"]
            sources = []
            for src in specs_data.get("sources", []):
                try:
                    trust = TrustLevel(src.get("trust_level", "medium"))
                except ValueError:
                    trust = TrustLevel.MEDIUM
                
                sources.append(Source(
                    label=src.get("label", ""),
                    url=src.get("url", ""),
                    type=src.get("type", "other"),
                    trust_level=trust,
                ))
            
            result.verified_specs = VerifiedSpecs(
                cell_type=specs_data.get("cell_type", ""),
                nominal_voltage_v=float(specs_data.get("nominal_voltage_v", 0)),
                nominal_capacity_ah=float(specs_data.get("nominal_capacity_ah", 0)),
                allowed_capacity_range_ah=specs_data.get("allowed_capacity_range_ah", {}),
                sources=sources,
            )
        
        # Parse pack_calculation
        if "pack_calculation" in data:
            calc = data["pack_calculation"]
            result.pack_calculation = PackCalculation(
                series_cells=int(calc.get("series_cells", 0)),
                parallel_cells=int(calc.get("parallel_cells", 0)),
                pack_nominal_voltage_v=float(calc.get("pack_nominal_voltage_v", 0)),
                pack_total_ah=float(calc.get("pack_total_ah", 0)),
                pack_total_wh=float(calc.get("pack_total_wh", 0)),
                pack_total_kwh=float(calc.get("pack_total_kwh", 0)),
            )
        
        # Parse range_estimate
        if "range_estimate" in data:
            est = data["range_estimate"]
            result.range_estimate = RangeEstimate(
                usable_wh=float(est.get("usable_wh", 0)),
                runtime_hours=float(est.get("runtime_hours", 0)),
                ideal_range_miles=float(est.get("ideal_range_miles", 0)),
                realistic_range_miles=float(est.get("realistic_range_miles", 0)),
            )
        
        # Parse issues
        for issue_data in data.get("issues", []):
            result.issues.append(Issue(
                field=issue_data.get("field", ""),
                problem=issue_data.get("problem", ""),
                severity=issue_data.get("severity", "info"),
            ))
        
        # Parse confidence
        if "confidence" in data:
            conf = data["confidence"]
            try:
                overall = ConfidenceLevel(conf.get("overall", "medium"))
                specs = ConfidenceLevel(conf.get("specs", "medium"))
                math = ConfidenceLevel(conf.get("math", "medium"))
                range_conf = ConfidenceLevel(conf.get("range", "medium"))
            except ValueError:
                overall = specs = math = range_conf = ConfidenceLevel.MEDIUM
            
            result.confidence = Confidence(
                overall=overall,
                specs=specs,
                math=math,
                range=range_conf,
            )
        
        return result
