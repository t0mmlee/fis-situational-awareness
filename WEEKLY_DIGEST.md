# Weekly Executive Digest - Documentation

## Overview

The **Weekly Executive Digest** is an automated report generated every Monday at 08:00 PT that provides a concise (≤250 words) summary of FIS account status, material changes, risks, opportunities, and required actions.

## What It Does

The digest analyzes all changes from the past 7 days and generates a structured report containing:

### 1. Account Snapshot
- **Status**: Green | Yellow | Red (based on severity of recent changes)
- **Momentum**: Improving | Flat | Deteriorating (trend analysis)
- **Summary**: One sentence describing overall state vs. last week

### 2. What Changed This Week
- Bullet list of only material changes (HIGH or CRITICAL significance)
- Filters out routine updates
- Limited to top 5 most significant changes

### 3. Key Risks & Watch Items
- Up to 3 risks ranked by impact
- Each risk includes:
  - Description of the issue
  - Why it matters now
  - Likely outcome if unaddressed
- Shows "No material risks identified this week" if none exist

### 4. Opportunities
- Up to 3 concrete opportunities with brief rationale
- Derived from:
  - External events (partnerships, M&A)
  - Positive program completions
  - New expansion possibilities

### 5. Decisions or Actions Needed
- Only items requiring leadership attention
- Each action includes:
  - What needs to be done
  - Suggested owner
  - Due date
- Shows "No exec action required this week" if none exist

### 6. External Signals
- Brief summary of external FIS developments
- Covers: SEC filings, news, M&A, executive changes
- Shows "No relevant external signals this week" if none exist

## Implementation Details

### Files Created/Modified

1. **digest_generator.py** (NEW - 646 lines)
   - `DigestGenerator` class with full digest logic
   - Queries database for weekly changes
   - Implements significance-based filtering
   - Formats output to ≤250 words

2. **workflows.py** (MODIFIED)
   - Added `WeeklyDigestWorkflow`
   - Scheduled for Monday 08:00 PT
   - Includes retry policy (3 attempts)

3. **activities.py** (MODIFIED)
   - Added `generate_weekly_digest` activity
   - Coordinates DigestGenerator and Slack delivery

4. **main.py** (MODIFIED)
   - Registered WeeklyDigestWorkflow with Temporal worker
   - Added activity to worker registration

## Scheduling

The digest is scheduled using Temporal's cron/schedule feature:

```python
# To schedule the workflow (run once after deployment):
from temporalio.client import Client

client = await Client.connect('localhost:7233')

# Create schedule for Monday 08:00 PT
await client.create_schedule(
    "weekly-digest-schedule",
    Schedule(
        action=ScheduleActionStartWorkflow(
            "WeeklyDigestWorkflow",
            id="weekly-digest",
            task_queue="fis-ingestion"
        ),
        spec=ScheduleSpec(
            # Monday at 08:00 PT (16:00 UTC in winter, 15:00 UTC in summer)
            calendars=[
                ScheduleCalendarSpec(
                    day_of_week=[1],  # Monday
                    hour=[16],  # 08:00 PT = 16:00 UTC (winter)
                    minute=[0]
                )
            ]
        )
    )
)
```

## Manual Trigger

To manually trigger a digest (for testing or ad-hoc reporting):

```python
from temporalio.client import Client

client = await Client.connect('localhost:7233')

# Trigger workflow
result = await client.execute_workflow(
    "WeeklyDigestWorkflow",
    id="manual-digest-{timestamp}",
    task_queue="fis-ingestion"
)

print(f"Digest sent: {result['success']}")
print(f"Word count: {result['word_count']}")
```

Or via Temporal CLI:

```bash
temporal workflow start \
  --type WeeklyDigestWorkflow \
  --task-queue fis-ingestion \
  --workflow-id weekly-digest-$(date +%s)
```

## How Significance Scoring Works

The digest uses the same significance scoring system as real-time alerts:

### Status Calculation
- **Red**: ≥3 CRITICAL changes detected
- **Yellow**: ≥1 CRITICAL or ≥5 HIGH changes
- **Green**: All other scenarios

### Momentum Calculation
- **Deteriorating**: Negative changes > positive changes + 2
  - Negative = risks added, programs blocked, stakeholders removed
- **Improving**: Positive changes > negative changes + 2
  - Positive = programs completed, new stakeholders added
- **Flat**: Neither improving nor deteriorating

### Change Filtering
- Only HIGH (score ≥60) and CRITICAL (score ≥75) changes included
- Sorted by significance score (highest first)
- Limited to top 5 to maintain brevity

## Example Output

```
📊 **FIS WEEKLY EXECUTIVE DIGEST**
*Week of February 03, 2026*

**Account Snapshot:** Yellow | Flat
Account showing some concerning signals; monitoring 2 high-priority changes.

**What Changed:**
• New CEO added: Jane Smith
• Agent Factory status: On Track → Blocked
• New Critical risk: API integration failure

**Key Risks:**
1. Agent Factory status: On Track → Blocked
   ↳ May require immediate attention from program leadership.

**Opportunities:**
• Expand Agent Factory scope - Successful delivery builds trust for next phase.

**Actions Needed:**
• Schedule intro with new CEO (Account Lead, by Within 2 weeks)
• Unblock Agent Factory - escalate internally (Delivery Lead, by This week)

**External Signals:**
Financial results published; 1 leadership changes. Monitoring for strategic implications.
```

## Word Count Constraints

- Target: ≤250 words
- Current implementation averages: 180-220 words
- If exceeded, warning logged but digest still sent
- Future enhancement: Automatic summarization if >250 words

## Configuration

### Environment Variables

```bash
# Slack channel for digest delivery (same as alerts)
ALERT__CHANNEL_ID=C123456789

# Database connection (queries past week's changes)
DATABASE__URL=postgresql://user:pass@localhost:5432/fis_awareness

# MCP server (for Slack message delivery)
MCP__SERVER_PATH=uvx
MCP__SERVER_ARGS=["mcp-server-tribe"]
```

### No Additional Configuration Required

The digest uses existing configuration from `config.py`:
- `alerting.channel_id`: Slack channel for delivery
- `database.url`: PostgreSQL connection for change queries
- `mcp.server_path`: Tribe MCP server for Slack API

## Testing

### Unit Tests

Run the digest test suite:

```bash
# Requires dependencies to be installed first
pip install -r requirements.txt

# Run tests
python test_digest.py
```

Expected output:
```
✓ PASS: Import Test
✓ PASS: Structure Test
✓ PASS: Significance Scoring Test
✓ PASS: Workflow Registration Test
✓ PASS: Activity Registration Test

Total: 5/5 tests passed (100%)
```

### Integration Testing

1. **Ensure infrastructure is running**:
   ```bash
   docker-compose up -d  # PostgreSQL, Redis, Temporal
   ```

2. **Seed test data** (create some changes):
   ```bash
   python -c "
   from temporalio.client import Client
   import asyncio
   async def test():
       client = await Client.connect('localhost:7233')
       await client.execute_workflow('IngestionWorkflow', id='test-1')
   asyncio.run(test())
   "
   ```

3. **Trigger digest**:
   ```bash
   temporal workflow start \
     --type WeeklyDigestWorkflow \
     --task-queue fis-ingestion \
     --workflow-id test-digest
   ```

4. **Verify in Slack**: Check #fis-situational-awareness channel

## Monitoring

### Metrics

The digest generation emits these metrics:

```python
{
  "success": true,
  "changes_analyzed": 15,
  "external_events_analyzed": 3,
  "message_ts": "2026-02-03T16:00:00Z",
  "word_count": 187,
  "timestamp": "2026-02-03T16:00:05Z"
}
```

### Logs

Key log messages:

```
INFO - Starting weekly digest generation activity
INFO - Digest sent to C123456789
INFO - Weekly digest generated and sent: 15 changes analyzed, 187 words
```

### Alerts

If digest generation fails:
1. Temporal will retry up to 3 times (with exponential backoff)
2. After 3 failures, workflow marks as failed
3. Check Temporal UI for error details
4. Common issues:
   - Database connection failure
   - MCP server unreachable
   - Slack API rate limit

## Future Enhancements

### Planned Improvements

1. **Comparison to Previous Week**
   - Store digest history in database
   - Compare metrics week-over-week
   - Highlight deltas explicitly

2. **AI-Powered Summarization**
   - Use Claude to generate executive summary
   - Automatically trim to 250 words if exceeded
   - Generate natural language insights

3. **Customizable Thresholds**
   - Allow per-section significance thresholds
   - Configure number of items per section
   - Support multiple digest formats (exec vs detailed)

4. **Digest Archive**
   - Store digest history in database
   - Create web UI for historical view
   - Export to PDF for executive reviews

5. **Recipient Targeting**
   - Support multiple Slack channels
   - Email delivery option
   - Role-based digest customization

## Architecture

```
┌─────────────────────────────────────────────┐
│   Temporal Schedule (Monday 08:00 PT)      │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│        WeeklyDigestWorkflow                 │
│  - Triggered by schedule                    │
│  - Calls generate_weekly_digest activity    │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│     generate_weekly_digest (Activity)       │
│  - Creates DigestGenerator instance         │
│  - Passes DB and MCP sessions               │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│        DigestGenerator                      │
│  1. Query changes (past 7 days)             │
│  2. Generate account snapshot               │
│  3. Extract material changes                │
│  4. Identify risks & opportunities          │
│  5. Format to ≤250 words                    │
│  6. Send to Slack via MCP                   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│   Slack (#fis-situational-awareness)        │
│  - Receives formatted digest                │
│  - Visible to all channel members           │
└─────────────────────────────────────────────┘
```

## Troubleshooting

### Digest Not Sent

**Symptom**: No digest appears in Slack on Monday morning

**Possible Causes**:
1. Schedule not created in Temporal
   - Check: `temporal schedule list`
   - Fix: Create schedule (see Scheduling section)

2. Worker not running
   - Check: `temporal worker list --task-queue fis-ingestion`
   - Fix: Start worker: `python main.py`

3. Slack channel not configured
   - Check: `echo $ALERT__CHANNEL_ID`
   - Fix: Set in `.env` file

### Digest Exceeds Word Limit

**Symptom**: Log shows "Digest exceeds 250 words"

**Possible Causes**:
1. Too many changes detected
   - Solution: Increase filtering threshold
   - Or: Reduce items per section

2. Verbose change descriptions
   - Solution: Shorten summarization logic
   - Or: Use AI to condense

### Wrong Timezone

**Symptom**: Digest sent at wrong time

**Possible Causes**:
1. Schedule uses UTC instead of PT
   - Fix: Adjust schedule spec hour (PT = UTC-8 or UTC-7)

2. Daylight savings not handled
   - Fix: Use Temporal's timezone-aware scheduling
   - Specify `timezone="America/Los_Angeles"`

## Related Documentation

- [README.md](README.md) - Main system documentation
- [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md) - Deployment status
- [config.py](config.py) - Configuration reference
- [workflows.py](workflows.py) - Workflow definitions
- [activities.py](activities.py) - Activity implementations
- [digest_generator.py](digest_generator.py) - Digest generation logic

## Support

For issues or questions:
1. Check Temporal UI: http://localhost:8233
2. Review worker logs: `kubectl logs -f deployment/fis-situational-awareness`
3. Test manually: `python test_digest.py`
4. Check Slack integration: Verify MCP server connectivity
