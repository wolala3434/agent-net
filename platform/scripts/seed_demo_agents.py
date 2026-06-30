#!/usr/bin/env python3
"""
Seed the Registry with 3 demo agents (per implementation-plan.md Phase 5).

Usage:
    python scripts/seed_demo_agents.py --registry http://localhost:8000
"""

import argparse
import os
import sys

import httpx

# Agent base ports from environment
AGENT_BASE_PORT_1 = os.getenv("AGENT_PORT_1", "9121")
AGENT_BASE_PORT_2 = os.getenv("AGENT_PORT_2", "9122")
AGENT_BASE_PORT_3 = os.getenv("AGENT_PORT_3", "9123")

# Agent endpoint hostname (for non-local deployments)
AGENT_HOST = os.getenv("AGENT_HOST", "localhost")

# Agent IDs must match what the SDK runtime generates in build_adl_card():
#   provider_slug = provider.name.lower().replace(" ", "-")
#   name_slug = config.name.lower().replace(" ", "-")
#   agent_id = f"{provider_slug}.{name_slug}@{config.version}"
#
# For "Agent Internet Demo" provider:
#   "Credit Risk Analyst"  -> "agent-internet-demo.credit-risk-analyst@1.0.0"
#   "Supply Chain Expert"  -> "agent-internet-demo.supply-chain-expert@1.0.0"
#   "Echo Summarizer"      -> "agent-internet-demo.echo-summarizer@1.0.0"
DEMO_AGENTS = [
    {
        "agent": {
            "id": "agent-internet-demo.credit-risk-analyst@1.0.0",
            "name": "Credit Risk Analyst",
            "version": "1.0.0",
            "description": "金融风险建模与分析，评估企业信用和供应链风险",
            "provider": {"name": "Agent Internet Demo", "contact": "demo@agentinternet.io"},
            "capabilities": [
                {
                    "id": "credit-risk-assessment",
                    "name": "信用风险评估",
                    "description": "分析企业信用风险，评估关键财务指标和供应链风险因子",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "timeframe": {"type": "string"},
                        },
                        "required": ["company", "timeframe"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "risk_score": {"type": "number"},
                            "factors": {"type": "array"},
                        },
                        "required": ["risk_score", "factors"],
                    },
                    "domains": ["analysis.financial", "analysis.risk"],
                    "execution_type": "synchronous",
                    "estimated_cost": "medium",
                    "estimated_duration": "short",
                }
            ],
            "endpoints": {
                "task": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_1}/api/v1/task",
                "health": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_1}/api/v1/health",
                "a2a": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_1}/api/v1/a2a",
            },
            "pricing": {
                "model": "per_call",
                "currency": "USD",
                "unit_price": 0.50,
                "estimated_cost": "medium",
            },
            "authentication": {"type": "none"},
            "tags": {"language": "python", "domain": "finance"},
        }
    },
    {
        "agent": {
            "id": "agent-internet-demo.supply-chain-expert@1.0.0",
            "name": "Supply Chain Expert",
            "version": "1.0.0",
            "description": "供应链数据分析和行业洞察，评估原材料价格和供应风险",
            "provider": {"name": "Agent Internet Demo", "contact": "demo@agentinternet.io"},
            "capabilities": [
                {
                    "id": "supply-chain-analysis",
                    "name": "供应链分析",
                    "description": "分析企业供应链风险，评估关键原材料的价格和供应风险",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "timeframe": {"type": "string"},
                        },
                        "required": ["company", "timeframe"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "risk_score": {"type": "number"},
                            "factors": {"type": "array"},
                        },
                        "required": ["risk_score", "factors"],
                    },
                    "domains": ["supply-chain", "analysis.risk"],
                    "execution_type": "synchronous",
                    "estimated_cost": "medium",
                    "estimated_duration": "short",
                }
            ],
            "endpoints": {
                "task": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_2}/api/v1/task",
                "health": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_2}/api/v1/health",
                "a2a": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_2}/api/v1/a2a",
            },
            "pricing": {
                "model": "per_call",
                "currency": "USD",
                "unit_price": 0.50,
                "estimated_cost": "medium",
            },
            "authentication": {"type": "none"},
            "tags": {"language": "python", "domain": "supply-chain"},
        }
    },
    {
        "agent": {
            "id": "agent-internet-demo.echo-summarizer@1.0.0",
            "name": "Echo Summarizer",
            "version": "1.0.0",
            "description": "文本摘要服务 — 接收文本输入，返回简洁摘要。用于连通性测试和单Agent模式验证",
            "provider": {"name": "Agent Internet Demo", "contact": "demo@agentinternet.io"},
            "capabilities": [
                {
                    "id": "text-summarisation",
                    "name": "文本摘要",
                    "description": "回显输入内容，用于连通性测试和单 Agent 模式验证",
                    "input_schema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}},
                        "required": ["summary"],
                    },
                    "domains": ["nlp.summarization"],
                    "execution_type": "synchronous",
                    "estimated_cost": "low",
                    "estimated_duration": "short",
                }
            ],
            "endpoints": {
                "task": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_3}/api/v1/task",
                "health": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_3}/api/v1/health",
                "a2a": f"http://{AGENT_HOST}:{AGENT_BASE_PORT_3}/api/v1/a2a",
            },
            "pricing": {
                "model": "per_call",
                "currency": "USD",
                "unit_price": 0.01,
                "estimated_cost": "low",
            },
            "authentication": {"type": "none"},
            "tags": {"language": "python", "domain": "testing"},
        }
    },
]


def main():
    parser = argparse.ArgumentParser(description="Seed demo agents into Registry")
    parser.add_argument("--registry", default=os.getenv("REGISTRY_URL", "http://localhost:8000"), help="Registry URL")
    args = parser.parse_args()

    base_url = args.registry.rstrip("/")

    for agent_card in DEMO_AGENTS:
        agent_id = agent_card["agent"]["id"]
        print(f"Registering {agent_id} ...")

        try:
            resp = httpx.post(
                f"{base_url}/api/v1/agents/register",
                json=agent_card["agent"],
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                print(f"  ✓ {data.get('status')} — {data.get('agent_id')}")
                print(f"    trial: {data.get('trial_status')}, free_quota: {data.get('free_quota_remaining')}")
            elif resp.status_code == 409:
                print("  ⚠ already registered, skipping")
            else:
                print(f"  ✗ HTTP {resp.status_code}: {resp.text[:200]}")
        except httpx.ConnectError:
            print(f"  ✗ Cannot connect to Registry at {base_url}")
            print("    Make sure the Registry is running first.")
            sys.exit(1)

    print("\nDone. All demo agents registered.")


if __name__ == "__main__":
    main()
