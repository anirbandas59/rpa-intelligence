import asyncio
import hashlib
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import UseCase, StageRun
from llm.manager import LLMManager
from prompts.assessment_prompts import ACTIVE_S1_SCORING_SYSTEM, ACTIVE_S1_SCORING_USER
from core.exceptions import LLMProviderError, AgentExecutionError

logger = logging.getLogger(__name__)


class AssessmentService:
    def __init__(self, db: AsyncSession, model: str = "claude-haiku-4-5"):
        self.db = db
        self.model = model
        # Initialize manager with specified model
        self.llm = LLMManager(provider_name="anthropic", model_name=model)

    def _parse_json_response(self, raw: str) -> dict:
        """Port Project 1's JSON parsing pipeline: strip fences, trim pre/postamble."""
        # Strip markdown fences
        if "```json" in raw:
            raw = raw.split("```json", 1)[1]
        if "```" in raw:
            raw = raw.split("```", 1)[0]

        # Find first '{' and last '}'
        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            raise LLMProviderError("No valid JSON object found in response")

        json_str = raw[start : end + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Failed to parse JSON: {e}")

    def _safe_defaults(self, parsed: dict) -> dict:
        """Apply safe defaults for missing fields."""
        scores = {
            "technical_feasibility": parsed.get("technical_feasibility", 0),
            "migration_effort": parsed.get("migration_effort", 0),
            "platform_suitability": parsed.get("platform_suitability", 0),
            "risk": parsed.get("risk", 0),
        }

        total = (
            scores["technical_feasibility"]
            + scores["migration_effort"]
            + scores["platform_suitability"]
            + scores["risk"]
        )

        # Derive decision from total if missing
        if "migration_decision" not in parsed:
            if total >= 75:
                decision = "QUICK_WIN"
            elif total >= 50:
                decision = "STRATEGIC"
            elif total >= 25:
                decision = "HOLD"
            else:
                decision = "DO_NOT_MIGRATE"
        else:
            decision = parsed["migration_decision"]

        return {
            **scores,
            "total_score": total,
            "migration_decision": decision,
            "confidence": parsed.get("confidence", "MEDIUM"),
            "analysis": parsed.get("analysis", ""),
            "blockers": parsed.get("blockers", []),
            "power_automate_fit": parsed.get("power_automate_fit", ""),
        }

    async def _score_single_use_case(self, use_case_data: dict) -> dict:
        """Score a single use-case asynchronously."""
        user_prompt = ACTIVE_S1_SCORING_USER.format(
            name=use_case_data.get("name", ""),
            description=use_case_data.get("description", ""),
            source_platform=use_case_data.get("source_platform", ""),
            install_status=use_case_data.get("install_status", ""),
        )

        try:
            raw_response = await self.llm.complete_async(
                prompt=user_prompt,
                system=ACTIVE_S1_SCORING_SYSTEM,
                max_tokens=1000,
                temperature=0.3,
            )

            parsed = self._parse_json_response(raw_response)
            result = self._safe_defaults(parsed)

            logger.info(f"Scored use-case: {use_case_data.get('name')} → {result['migration_decision']}")
            return result

        except Exception as e:
            logger.error(f"Error scoring use-case {use_case_data.get('name')}: {e}")
            raise AgentExecutionError(f"Failed to score use-case: {e}")

    async def run_assessment(self, use_case_id: str) -> StageRun:
        """Run S1 assessment for a single use-case. Creates StageRun, runs LLM call, updates result."""
        # Fetch use-case
        result = await self.db.execute(select(UseCase).where(UseCase.id == use_case_id))
        use_case = result.scalar_one_or_none()

        if not use_case:
            raise ValueError(f"UseCase {use_case_id} not found")

        # Compute inputs snapshot and hash
        inputs = {
            "name": use_case.name,
            "description": use_case.description,
            "source_platform": use_case.source_platform,
            "install_status": use_case.install_status,
            **use_case.s1_inputs,
        }

        inputs_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

        # Count existing runs
        count_result = await self.db.execute(
            select(StageRun).where(StageRun.use_case_id == use_case_id, StageRun.stage == "s1")
        )
        run_number = len(count_result.scalars().all()) + 1

        # Create StageRun with status=running
        stage_run = StageRun(
            use_case_id=use_case_id,
            stage="s1",
            run_number=run_number,
            inputs_snapshot=inputs,
            inputs_hash=inputs_hash,
            result={},
            model_used=self.model,
            status="running",
        )

        self.db.add(stage_run)
        await self.db.commit()
        await self.db.refresh(stage_run)

        logger.info(f"Created S1 StageRun {stage_run.id} for use-case {use_case_id}")

        try:
            # Run scoring
            assessment_result = await self._score_single_use_case(inputs)

            # Update StageRun
            stage_run.result = assessment_result
            stage_run.status = "complete"
            await self.db.commit()
            await self.db.refresh(stage_run)

            # Update use-case latest_run_id
            use_case.s1_latest_run_id = stage_run.id
            await self.db.commit()

            logger.info(f"Completed S1 StageRun {stage_run.id}")
            return stage_run

        except Exception as e:
            stage_run.status = "failed"
            stage_run.error_message = str(e)
            await self.db.commit()
            logger.error(f"Failed S1 StageRun {stage_run.id}: {e}")
            raise

    async def run_bulk_assessment(self, project_id: str, use_case_ids: list[str]) -> list[StageRun]:
        """Run assessments in parallel using asyncio.gather."""
        tasks = [self.run_assessment(uc_id) for uc_id in use_case_ids]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def generate_followup_questions(self, use_case_id: str) -> list[str]:
        """Generate follow-up questions for low-confidence assessments."""
        result = await self.db.execute(select(UseCase).where(UseCase.id == use_case_id))
        use_case = result.scalar_one_or_none()

        if not use_case or not use_case.s1_latest_run_id:
            return []

        run_result = await self.db.execute(select(StageRun).where(StageRun.id == use_case.s1_latest_run_id))
        stage_run = run_result.scalar_one_or_none()

        if not stage_run:
            return []

        assessment = stage_run.result

        if assessment.get("confidence") == "HIGH":
            return []

        from prompts.assessment_prompts import S1_FOLLOWUP_SYSTEM, S1_FOLLOWUP_USER

        user_prompt = S1_FOLLOWUP_USER.format(
            name=use_case.name,
            analysis=assessment.get("analysis", ""),
            blockers=json.dumps(assessment.get("blockers", [])),
            confidence=assessment.get("confidence", "MEDIUM"),
        )

        try:
            raw_response = await self.llm.complete_async(
                prompt=user_prompt,
                system=S1_FOLLOWUP_SYSTEM,
                max_tokens=500,
                temperature=0.3,
            )

            questions = self._parse_json_response(raw_response)
            if isinstance(questions, list):
                return questions
            return []

        except Exception as e:
            logger.error(f"Failed to generate follow-up questions: {e}")
            return []
