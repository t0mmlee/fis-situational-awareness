# FIS Situational Awareness System - Roadmap

This document outlines what needs to be done to complete the system per the original specification.

---

## ✅ Current Status (Implemented)

### Core Features Working
- ✅ **Data Ingestion** (Slack, Notion, External sources)
- ✅ **Change Detection** (additions, removals, modifications)
- ✅ **Significance Scoring** (0-100 scale with CRITICAL/HIGH/MEDIUM/LOW)
- ✅ **Real-Time Alerts** (Slack notifications for CRITICAL changes ≥75)
- ✅ **Weekly Executive Digest** (Monday 08:00 PT, ≤250 words)
- ✅ **Temporal Orchestration** (scheduled workflows, retry logic)
- ✅ **Database Persistence** (full audit trail in PostgreSQL)
- ✅ **Health Checks** (FastAPI endpoints for monitoring)
- ✅ **MCP Integration** (all internal APIs via Tribe MCP)

### Current Limitations
- ⚠️ **Batch Processing** (every 3 days, not continuous)
- ⚠️ **Regex Entity Extraction** (not AI-powered)
- ⚠️ **No Gmail Integration**
- ⚠️ **No Internal State Model** (no aggregated account health)
- ⚠️ **No Governance Tracking** (defined but not extracted)

---

## 🎯 Priority 1: Get It Running (Phase 1)

**Timeline:** 1-2 hours
**Status:** 🔴 BLOCKING

### Tasks

| Task | Effort | Status | Notes |
|------|--------|--------|-------|
| Install Python dependencies | 5 min | ⬜ Not started | `pip install -r requirements.txt` |
| Create .env configuration | 10 min | ⬜ Not started | Need Slack channel ID + Anthropic API key |
| Start infrastructure (Docker) | 10 min | ⬜ Not started | PostgreSQL, Redis, Temporal |
| Initialize database | 5 min | ⬜ Not started | Create tables via SQLAlchemy |
| Configure MCP server | 15 min | ⬜ Not started | Slack + Notion tokens |
| Run tests | 5 min | ⬜ Not started | Verify all imports work |
| Start application | 2 min | ⬜ Not started | `python main.py` |
| Trigger test ingestion | 5 min | ⬜ Not started | Verify end-to-end flow |

### Success Criteria
- [ ] Application starts without errors
- [ ] All tests pass (17/17)
- [ ] Temporal worker connected
- [ ] Test ingestion completes successfully
- [ ] Database contains ingested entities
- [ ] Slack alert sent for test change

### Documentation
- [GETTING_STARTED.md](GETTING_STARTED.md) - Complete setup guide
- Automated script: `./setup.sh`

---

## 🚀 Priority 2: Core Spec Gaps (Phase 2)

**Timeline:** 2-3 days
**Status:** 🟡 IMPORTANT

### 2.1 Upgrade to AI-Powered Entity Extraction

**Current:** Uses regex/keyword matching to extract entities
**Goal:** Use Claude API for intelligent extraction

**Why It Matters:**
- Current regex misses nuanced updates like "We're concerned about the timeline"
- Can't detect sentiment or implicit risks
- Can't understand meeting notes or email context

**Implementation:**

```python
# agents/base.py - Add AI extraction method
async def extract_entities_with_ai(self, text: str, source: str) -> List[Dict]:
    """Use Claude to extract structured entities from text."""
    prompt = f"""
    Analyze this {source} message and extract FIS-related entities:

    1. Stakeholders (name, role, company, sentiment)
    2. Programs (name, status, concerns, next steps)
    3. Risks (description, severity, category, owner)
    4. Timelines (milestone, target_date, status, dependencies)
    5. Governance (decision, decision_maker, rationale, date)

    Text: {text}

    Return as JSON array of entities.
    """

    response = await anthropic.messages.create(
        model=config.ai.model,
        max_tokens=config.ai.max_tokens,
        temperature=config.ai.temperature,
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.content[0].text)
```

**Files to Modify:**
- `agents/slack_agent.py` - Replace `_extract_*` methods
- `agents/notion_agent.py` - Replace regex patterns
- `agents/base.py` - Add `extract_entities_with_ai()` helper

**Effort:** 1 day
**Impact:** High - Much better entity extraction accuracy

---

### 2.2 Implement Continuous Monitoring

**Current:** Ingests every 3 days (batch mode)
**Goal:** Run continuously with real-time updates

**Why It Matters:**
- 3-day delay means critical issues not detected quickly
- Specification requires "continuously scan" and "run continuously"

**Implementation Options:**

**Option A: Change Schedule (Easy)**
```python
# Change from every 3 days to every hour
INGESTION__INTERVAL_DAYS=0.042  # ~1 hour (1/24 days)
```

**Option B: Streaming Mode (Better)**
```python
# workflows.py - Add streaming workflow
@workflow.defn
class StreamingIngestionWorkflow:
    """Continuously polls sources for new content."""

    @workflow.run
    async def run(self):
        while True:
            # Check each source for updates
            await workflow.execute_activity("slack_ingestion", ...)

            # Sleep for short interval
            await asyncio.sleep(timedelta(minutes=15))
```

**Option C: Event-Driven (Best)**
- Use Slack Events API webhooks
- Use Notion Webhooks (when available)
- Process changes as they occur

**Files to Modify:**
- `workflows.py` - Add streaming workflow
- `config.py` - Add polling interval setting
- `activities.py` - Support incremental ingestion

**Effort:** 2 days
**Impact:** High - Real-time awareness

---

### 2.3 Add Gmail Integration

**Current:** No Gmail agent exists
**Goal:** Monitor Gmail for FIS stakeholder communications

**Why It Matters:**
- Email often contains critical decisions and sentiment
- Specification explicitly requires Gmail monitoring

**Implementation:**

```python
# agents/gmail_agent.py (NEW FILE)
class GmailIngestionAgent(BaseIngestionAgent):
    """Ingests FIS-related emails via Tribe MCP."""

    async def ingest(self, since: Optional[datetime] = None):
        # Search for FIS-related emails
        emails = await self._search_gmail("from:@fisglobal.com OR subject:FIS")

        # Extract entities from email content
        entities = []
        for email in emails:
            # Use AI to extract stakeholders, decisions, sentiment
            extracted = await self.extract_entities_with_ai(
                text=email["body"],
                source="gmail"
            )
            entities.extend(extracted)

        return entities
```

**Prerequisites:**
- Add Gmail tools to MCP server
- Configure Gmail API access
- Add to workflows as 4th parallel ingestion

**Files to Create:**
- `agents/gmail_agent.py` (new)

**Files to Modify:**
- `workflows.py` - Add `gmail_ingestion` to parallel activities
- `activities.py` - Add `gmail_ingestion` activity
- `config.py` - Add Gmail configuration section

**Effort:** 1 day
**Impact:** Medium - Captures email-based decisions

---

### 2.4 Build Internal State Model

**Current:** Only stores entity snapshots, no aggregated state
**Goal:** Maintain continuous internal model of account health

**Why It Matters:**
- Can't answer "What's the current account health?"
- No momentum tracking over time
- No ownership gap detection

**Implementation:**

```python
# state_model.py (NEW FILE)
class AccountStateModel:
    """
    Maintains aggregated state of FIS account.

    Tracks:
    - Overall health score (0-100)
    - Momentum trend (improving/flat/deteriorating)
    - Open risks by severity
    - Unowned action items
    - Stakeholder engagement level
    - Program delivery status
    """

    def calculate_health_score(self, snapshots: List[EntitySnapshot]) -> int:
        """Calculate 0-100 health score based on current state."""
        # Count critical risks
        critical_risks = sum(1 for e in snapshots
                            if e.entity_type == "risk"
                            and e.entity_data.get("severity") == "Critical")

        # Count blocked programs
        blocked_programs = sum(1 for e in snapshots
                              if e.entity_type == "program"
                              and e.entity_data.get("status") == "Blocked")

        # Start at 100, deduct points
        score = 100
        score -= critical_risks * 20
        score -= blocked_programs * 15

        return max(0, score)

    def detect_ownership_gaps(self, snapshots: List[EntitySnapshot]) -> List[str]:
        """Find actions/risks without owners."""
        gaps = []
        for snapshot in snapshots:
            if snapshot.entity_type == "risk":
                if not snapshot.entity_data.get("owner"):
                    gaps.append(f"Risk has no owner: {snapshot.entity_data.get('description')}")
        return gaps
```

**Database Schema:**

```sql
CREATE TABLE account_state (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    health_score INTEGER NOT NULL,
    momentum VARCHAR(20) NOT NULL,  -- 'improving', 'flat', 'deteriorating'
    critical_risks INTEGER NOT NULL,
    open_risks INTEGER NOT NULL,
    blocked_programs INTEGER NOT NULL,
    stakeholder_engagement_score INTEGER,
    ownership_gaps TEXT[],
    metadata JSONB
);
```

**Files to Create:**
- `state_model.py` (new)
- `models.py` - Add `AccountState` model

**Files to Modify:**
- `activities.py` - Add `update_state_model` activity
- `workflows.py` - Call after change detection

**Effort:** 1 day
**Impact:** High - Enables querying current state

---

### 2.5 Extract Governance Entities

**Current:** Governance entity type defined but never populated
**Goal:** Extract strategic decisions from Slack/Notion/Gmail

**Why It Matters:**
- Governance decisions are critical for account momentum
- Need to track who decided what and why

**Implementation:**

Use AI extraction with specific prompts:

```python
async def _extract_governance(self, message: str) -> List[Dict]:
    """Extract governance decisions from text."""
    prompt = """
    Identify any strategic decisions in this text:
    - Decision made
    - Decision maker (name/role)
    - Rationale/context
    - Date decided
    - Impact on FIS programs

    Look for phrases like:
    - "We've decided to..."
    - "The team agreed..."
    - "Leadership approved..."
    - "Strategic direction..."

    Text: {message}
    """
    # Use Claude to extract
```

**Files to Modify:**
- `agents/slack_agent.py` - Add `_extract_governance()`
- `agents/notion_agent.py` - Add governance extraction
- `agents/gmail_agent.py` - Check for decision emails

**Effort:** 0.5 days
**Impact:** Medium - Better strategic tracking

---

## 🔧 Priority 3: Enhancements (Phase 3)

**Timeline:** 1-2 weeks
**Status:** 🟢 NICE TO HAVE

### 3.1 Multi-Channel Digest Delivery

**Goal:** Send digest to multiple channels/recipients

- Support multiple Slack channels
- Email delivery option (PDF attachment)
- Role-based customization (exec vs detailed)

**Effort:** 2 days
**Impact:** Medium

---

### 3.2 Digest History & Comparison

**Goal:** Compare week-over-week metrics

- Store digest history in database
- Highlight deltas from previous week
- Web UI for historical view
- Export to PDF

**Effort:** 2 days
**Impact:** Low

---

### 3.3 Advanced Change Analysis

**Goal:** Better change interpretation

- Use LLM to generate natural language summaries
- Detect patterns across multiple changes
- Predict future issues based on trends
- Correlation detection (e.g., "When X happens, Y usually follows")

**Effort:** 3 days
**Impact:** High

---

### 3.4 Stakeholder Sentiment Analysis

**Goal:** Track stakeholder engagement and sentiment

- Analyze Slack message sentiment
- Track response times and engagement
- Detect disengagement early
- Alert when key stakeholders go quiet

**Effort:** 2 days
**Impact:** High

---

### 3.5 Configurable Alert Rules

**Goal:** Flexible alerting beyond significance scores

```python
# Example rules engine
rules = [
    {
        "name": "CEO Departure",
        "condition": "entity_type == 'stakeholder' AND role == 'CEO' AND change_type == 'removed'",
        "action": "alert_immediate",
        "recipients": ["exec-sponsor", "account-lead"]
    },
    {
        "name": "Program Blocked",
        "condition": "entity_type == 'program' AND new_value.status == 'Blocked'",
        "action": "alert_within_1_hour",
        "recipients": ["delivery-lead"]
    }
]
```

**Effort:** 3 days
**Impact:** High

---

### 3.6 Integration with Jira/Linear

**Goal:** Auto-create tickets for risks and action items

- Create Jira ticket when critical risk detected
- Assign to appropriate owner
- Track resolution in external system
- Sync status back to FIS system

**Effort:** 2 days
**Impact:** Medium

---

### 3.7 Predictive Analytics

**Goal:** Forecast account issues before they happen

- Train model on historical change patterns
- Predict likelihood of program delays
- Identify early warning signals
- Recommend preventive actions

**Effort:** 1 week
**Impact:** High (future)

---

## 📊 Effort Summary

| Priority | Total Effort | Impact | Status |
|----------|-------------|---------|--------|
| P1: Get Running | 1-2 hours | CRITICAL | 🔴 Blocking |
| P2: Core Spec Gaps | 2-3 days | HIGH | 🟡 Important |
| P3: Enhancements | 1-2 weeks | MEDIUM | 🟢 Nice to have |

---

## 🎯 Recommended Sequence

### Week 1: Make It Work
1. ✅ Complete setup (Phase 1) - **1-2 hours**
2. Test end-to-end flow
3. Monitor first few ingestion runs
4. Tune significance thresholds

### Week 2: Core Spec Compliance
5. Implement AI-powered extraction - **1 day**
6. Add Gmail integration - **1 day**
7. Build internal state model - **1 day**
8. Add governance extraction - **0.5 days**

### Week 3: Operational Excellence
9. Switch to continuous monitoring - **2 days**
10. Tune and optimize based on real data
11. Document operational playbooks
12. Train team on system usage

### Weeks 4+: Enhancements
13. Pick from Priority 3 based on needs
14. Iterate based on user feedback

---

## 🚧 Known Limitations

### Current System Cannot:

1. **Understand Nuance**
   - Regex can't detect implicit risks
   - Can't understand sentiment or tone
   - Misses context from prior conversations

2. **Detect Inaction**
   - No tracking of "prolonged silence"
   - Can't detect disengagement
   - Doesn't flag unowned actions

3. **Reason Probabilistically**
   - No speculation when info incomplete
   - Can't infer missing context
   - No confidence levels

4. **Maintain Continuous State**
   - Forgets context between runs
   - No cumulative understanding
   - Can't answer "What's the account health?"

### These Are Addressed By:
- AI extraction (#2.1)
- Internal state model (#2.4)
- Continuous monitoring (#2.2)

---

## 💡 Future Vision

### Ultimate Goal: Autonomous Account Manager

The system should be able to:

1. **Detect** subtle changes humans miss
2. **Reason** about implications and patterns
3. **Predict** issues before they become critical
4. **Recommend** specific actions with rationale
5. **Learn** from outcomes to improve over time

### Example Scenario

```
🤖 FIS Agent: I've noticed concerning patterns:

1. John (Executive Sponsor) hasn't posted in #fis channel for 14 days
   - Historical pattern: His silence usually precedes scope reductions
   - Last time (Q3 2025): 12-day silence → budget cut announcement
   - Recommended action: Schedule 1:1 check-in within 48 hours

2. Agent Factory mentioned in 3 messages with negative sentiment
   - Risk indicators: "struggling", "behind schedule", "concerned"
   - Timeline: Demo scheduled in 2 weeks, but no prep mentions
   - Recommended action: Delivery lead to assess readiness

3. FIS CFO posted on LinkedIn about "AI cost optimization"
   - External signal: Budget pressure likely increasing
   - Correlation: Similar posts in Q2 2025 led to vendor reviews
   - Recommended action: Prepare ROI analysis proactively
```

This level of intelligence requires:
- AI-powered extraction ✅ (roadmap #2.1)
- Continuous monitoring ✅ (roadmap #2.2)
- State model ✅ (roadmap #2.4)
- Sentiment analysis ✅ (roadmap #3.4)
- Predictive analytics ✅ (roadmap #3.7)

---

## 📚 Resources

- [GETTING_STARTED.md](GETTING_STARTED.md) - Setup instructions
- [WEEKLY_DIGEST.md](WEEKLY_DIGEST.md) - Digest documentation
- [README.md](README.md) - System overview
- [Original Spec](https://claude.ai/code/session_01QXDvEBS3GwLShL2PXjzy1d) - User requirements

---

## 🤝 Contributing

To work on any roadmap item:

1. Create feature branch: `git checkout -b feature/ai-extraction`
2. Implement changes
3. Add tests
4. Update documentation
5. Create pull request
6. Update this roadmap with status

---

**Last Updated:** February 5, 2026
**Maintainer:** Claude Code Agent
