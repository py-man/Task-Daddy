from __future__ import annotations

import secrets

import pytest
from httpx import AsyncClient

from conftest import login


@pytest.mark.anyio
async def test_task_ai_enhance_is_intent_aware_for_access_issues(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"AI Access {secrets.token_hex(4)}"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={
        "laneId": lane_id,
        "title": "User cannot login to dashboard (403 access denied)",
        "description": "A user is blocked after MFA. Needs access to billing project.",
        "type": "Bug",
      },
    )
  ).json()

  res = await client.post(f"/ai/task/{t['id']}/enhance", json={})
  assert res.status_code == 200
  data = res.json()
  assert data["intent"]["type"] == "access_issue"
  assert data["intent"]["confidence"] >= 0.55
  assert data["acceptanceCriteria"]
  assert any("Authorization" in x or "Authentication" in x for x in data["acceptanceCriteria"])
  assert data["priorityRecommendation"]["value"] in ("P0", "P1", "P2", "P3")
  assert data["qualityScore"]["overall"] >= 0.0
  assert isinstance(data["qualityScore"].get("reasonCodes"), list)
  assert "retrievalContext" in data
  assert "linkedRecords" in data["retrievalContext"]
  assert "suggestions" in data
  assert any("preview" in s for s in data["suggestions"])
  assert "Acceptance Criteria" in data["text"]
  audit = (await client.get(f"/audit?taskId={t['id']}")).json()
  assert any(ev["eventType"] == "ai.task.preview" for ev in audit)
  latest = next(ev for ev in audit if ev["eventType"] == "ai.task.preview")
  assert latest["payload"]["schemaVersion"] == "ai.task.enhance.v2"
  assert latest["payload"]["intent"] == "access_issue"


@pytest.mark.anyio
async def test_task_ai_enhance_differs_for_feature_request(client: AsyncClient) -> None:
  await login(client, "admin@taskdaddy.local", "admin1234")

  b = (await client.post("/boards", json={"name": f"AI Feature {secrets.token_hex(4)}"})).json()
  lanes = (await client.get(f"/boards/{b['id']}/lanes")).json()
  lane_id = lanes[0]["id"]
  t = (
    await client.post(
      f"/boards/{b['id']}/tasks",
      json={
        "laneId": lane_id,
        "title": "Add board color presets for team branding",
        "description": "Feature request from product for customizable light themes.",
        "type": "Feature",
      },
    )
  ).json()

  res = await client.post(f"/ai/task/{t['id']}/enhance", json={})
  assert res.status_code == 200
  data = res.json()
  assert data["intent"]["type"] == "feature_request"
  assert data["acceptanceCriteria"]
  assert not any("Authentication flow" in x for x in data["acceptanceCriteria"])
  assert data["implementationNotes"]
  assert data["definitionOfDone"]
