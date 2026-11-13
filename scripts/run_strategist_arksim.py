"""Run a bounded ArkSim pilot against Strategist without touching the live DB.

Install ArkSim only in a throwaway environment; see the evaluation guide.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "docs/ai-knowledge/examples/strategist-arksim-scenarios.json"
USER_PROMPT = ROOT / "docs/ai-knowledge/examples/strategist-arksim-user-prompt.j2"
MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Make bounded live API calls")
    parser.add_argument("--scenarios", type=int, default=3)
    parser.add_argument("--scenario-id", help="Run only one named scenario")
    parser.add_argument("--min-replies", type=int, choices=(1, 2), default=1,
                        help="Require at least this many Strategist replies per conversation")
    args = parser.parse_args()
    selected = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    if not 1 <= args.scenarios <= len(selected["scenarios"]):
        parser.error(f"--scenarios must be between 1 and {len(selected['scenarios'])}")
    if args.scenario_id:
        selected["scenarios"] = [
            item for item in selected["scenarios"] if item["scenario_id"] == args.scenario_id
        ]
        if not selected["scenarios"]:
            parser.error("unknown scenario ID")
    else:
        selected["scenarios"] = selected["scenarios"][: args.scenarios]

    if not args.run:
        count = len(selected["scenarios"])
        print(f"Dry run: {count} scenarios; at most {count * 2} Strategist replies.")
        print("Pass --run to create a temporary test database and call the APIs.")
        return

    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        parser.error("OPENROUTER_API_KEY is required for the free simulator model")
    if not os.environ.get("GIGACHAT_API_TOKEN", "").strip():
        parser.error("GIGACHAT_API_TOKEN is required for the real Strategist")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
    proxy = os.environ.get("OPENROUTER_PROXY_URL", "").strip()
    if proxy:
        os.environ["HTTPS_PROXY"] = proxy
        bypass = os.environ.get("NO_PROXY", "")
        os.environ["NO_PROXY"] = ",".join(
            part for part in (bypass, "api.giga.chat", "ngw.devices.sberbank.ru", "db", "valkey") if part
        )
    sys.path.insert(0, str(ROOT))

    import django

    django.setup()
    from django.db import connections
    from django.db.models import Sum
    from django.test.utils import setup_databases, teardown_databases
    from asgiref.sync import sync_to_async

    from arksim.config import AgentConfig, CustomConfig
    from arksim.simulation_engine import SimulationInput, run_simulation

    from apps.strategist.models import AIMessage

    run_id = uuid.uuid4().hex[:10]
    database_name = f"test_strategist_eval_{run_id}"
    connections["default"].settings_dict["TEST"]["NAME"] = database_name
    output_dir = ROOT / "var/strategist-eval" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_file = output_dir / "scenarios.json"
    scenario_file.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")

    old_config = setup_databases(verbosity=0, interactive=False, keepdb=False)
    try:
        if connections["default"].settings_dict["NAME"] != database_name:
            raise RuntimeError("Evaluation database isolation failed")
        simulation = asyncio.run(
            run_simulation(
                SimulationInput(
                    agent_config=AgentConfig(
                        agent_type="custom",
                        agent_name="boostklient-strategist",
                        custom_config=CustomConfig(
                            module_path=str(ROOT / "scripts/strategist_arksim_agent.py"),
                            class_name="StrategistAgent",
                        ),
                    ),
                    scenario_file_path=str(scenario_file),
                    output_file_path=str(output_dir / "simulation.json"),
                    provider="openai",
                    model=MODEL,
                    num_conversations_per_scenario=1,
                    max_turns=2,
                    num_workers=1,
                    simulated_user_prompt_template=USER_PROMPT.read_text(encoding="utf-8"),
                )
            )
        )
        tokens = AIMessage.objects.filter(role=AIMessage.Role.ASSISTANT).aggregate(
            total=Sum("total_tokens")
        )["total"] or 0
        report = {
            "run_id": run_id,
            "simulator_model": MODEL,
            "conversations": len(simulation.conversations),
            "strategist_replies": sum(
                message.role == "assistant"
                for conversation in simulation.conversations
                for message in conversation.conversation_history
            ),
            "strategist_reported_tokens": tokens,
            "note": "Synthetic users, isolated test DB; model judging and factual review not yet performed.",
        }
        (output_dir / "summary.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Transcripts: {output_dir / 'simulation.json'}")
        if any(
            sum(message.role == "assistant" for message in conversation.conversation_history)
            < args.min_replies
            for conversation in simulation.conversations
        ):
            raise RuntimeError("At least one simulated user stopped before the required replies")
    finally:
        asyncio.run(sync_to_async(connections.close_all, thread_sensitive=True)())
        connections.close_all()
        teardown_databases(old_config, verbosity=0)


if __name__ == "__main__":
    main()
