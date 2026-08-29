"""
Persistent per-merchant state for Ledgr's incremental demo-data flow.

Stores what st.session_state alone cannot survive: a browser refresh, a
server restart, or logging out and back in. Backed by a plain JSON file
per merchant -- consistent with this project's established position that
flat files are enough for a buildathon (see CLAUDE.md's persistence
discussion), not a new database dependency.

This module is NOT reconciliation logic. It only tracks:
  - which batch is next to reconcile
  - which record IDs have already been reconciled (so a batch is never
    processed twice)
  - the saved results of each real reconciliation run (for the cumulative
    dashboard and Recent Reconciliations table)
  - when the next batch becomes available (a persisted timestamp, checked
    on demand -- never a sleep, never a background poll)
  - whether the current "new batch available" notification has been seen

The actual matching/reconciling always goes through the real
engine.reconcile() -- this module only decides WHICH rows to hand it and
remembers WHAT it returned.
"""
import json
import os
from datetime import datetime, timedelta

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state")
os.makedirs(STATE_DIR, exist_ok=True)

BATCH2_DELAY_SECONDS = 45
TOTAL_BATCHES = 2


def _path(merchant_id):
    # merchant_id is one of our own hardcoded demo ids (see auth.py) --
    # never raw user input, so a plain filename join is fine here.
    return os.path.join(STATE_DIR, f"{merchant_id}.json")


def _default_state():
    return {
        "current_batch": 1,               # next batch to reconcile (1..3); > 3 = nothing left
        "processed_record_ids": [],       # every order_id/settlement_id ever reconciled
        "reconciliation_runs": [],        # saved run dicts, most-recent first
        "next_batch_available_at": None,  # ISO timestamp, or None
        "notification_batch": None,       # which batch the current notification concerns
        "notification_created": False,    # the "new data" event has fired once for this batch
        "notification_seen": True,        # False = bell should show an unread dot
        "notification_overlay_open": False,  # should the floating top-right card render now
        "cases": {},                      # case_id -> case dict; survives across batches/reruns
    }


def load_state(merchant_id):
    """Always returns a complete state dict -- missing file or missing
    keys (e.g. after this module gains a new field) both backfill to
    defaults rather than raising."""
    path = _path(merchant_id)
    if not os.path.exists(path):
        return _default_state()
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default_state()
    defaults = _default_state()
    for k, v in defaults.items():
        data.setdefault(k, v)
    return data


def save_state(merchant_id, state):
    with open(_path(merchant_id), "w") as f:
        json.dump(state, f, indent=2, default=str)


def reset_state(merchant_id):
    """Demo-only: wipe this merchant's reconciliation progress/history.
    Never touches the underlying source data (orders.csv etc.) -- that's
    shared demo data, not per-merchant state."""
    path = _path(merchant_id)
    if os.path.exists(path):
        os.remove(path)


def schedule_next_batch(state, completed_batch):
    """Call right after a batch's reconciliation run has been saved.
    Resets the full notification lifecycle for the newly-scheduled batch
    -- it hasn't been created/seen/opened yet, because it isn't even
    available yet (that's what next_batch_available_at is for)."""
    if completed_batch >= TOTAL_BATCHES:
        state["next_batch_available_at"] = None
        state["current_batch"] = TOTAL_BATCHES + 1  # sentinel: nothing left
        return
    delay = BATCH2_DELAY_SECONDS
    next_batch = completed_batch + 1
    state["current_batch"] = next_batch
    state["next_batch_available_at"] = (datetime.now() + timedelta(seconds=delay)).isoformat()
    state["notification_batch"] = next_batch
    state["notification_created"] = False
    state["notification_seen"] = False
    state["notification_overlay_open"] = False


def mark_notification_created(state):
    """Call the moment a scheduled batch's timer passes and its 'new
    data' event fires for the first time. Opens the overlay and flags it
    created so this can never fire -- and the overlay can never
    auto-reappear -- a second time for this same batch, even across a
    browser refresh (notification_created is persisted, not session
    state)."""
    state["notification_created"] = True
    state["notification_overlay_open"] = True


def dismiss_overlay(state):
    """'Later' / '×': hides the floating overlay without marking the
    notification read -- the bell keeps its red dot, and the overlay will
    not auto-reappear for this batch (it stays reachable via the bell)."""
    state["notification_overlay_open"] = False


def mark_notification_read(state):
    """Clicking 'Review & Reconcile' (from the overlay OR the bell
    panel): clears the bell's red dot and closes the overlay."""
    state["notification_seen"] = True
    state["notification_overlay_open"] = False


def upsert_case(state, case):
    """
    Insert or update one case by its case_id -- the single write path for
    the persistent case store. Called every time a batch is reconciled,
    for every non-clean record, whether or not the case already existed.

    Preserves created_at/history/resolution from any EXISTING case with
    the same id, so a re-evaluated "pending settlement" case (see
    pending_settlement_order_ids()) keeps its timeline instead of looking
    like a brand-new case, and a human's earlier decision is never
    silently overwritten by a fresh deterministic re-run unless the case
    genuinely moved to a resolved state on its own merits.
    """
    cases = state.setdefault("cases", {})
    cid = case["case_id"]
    now = datetime.now().isoformat()
    existing = cases.get(cid)
    event = case.pop("_event", "reconciled")

    if existing:
        case["created_at"] = existing.get("created_at", now)
        case["history"] = list(existing.get("history", []))
        if existing.get("resolution", {}).get("resolved") and not case.get("resolution"):
            case["resolution"] = existing["resolution"]
        case.setdefault("bookmarked", existing.get("bookmarked", False))
        case.setdefault("comment", existing.get("comment", ""))
    else:
        case["created_at"] = now
        case.setdefault("history", [])

    case.setdefault("resolution", {"resolved": False, "resolution_type": None,
                                    "resolved_at": None, "resolved_by": None, "comment": None})
    case.setdefault("bookmarked", False)
    case.setdefault("comment", "")
    case["updated_at"] = now
    case["history"].append({"at": now, "event": event})
    cases[cid] = case
    return case


def get_case(state, case_id):
    return state.get("cases", {}).get(case_id)


def list_cases(state, case_status=None, case_type=None):
    """All persisted cases, newest-updated first. Filter by our own
    lifecycle status (case_status) and/or case_type -- both plain string
    fields on each case dict, nothing derived or fabricated here."""
    cases = list(state.get("cases", {}).values())
    if case_status:
        cases = [c for c in cases if c.get("case_status") == case_status]
    if case_type:
        cases = [c for c in cases if c.get("case_type") == case_type]
    return sorted(cases, key=lambda c: c.get("updated_at", ""), reverse=True)


def pending_settlement_order_ids(state):
    """
    Order IDs still genuinely waiting on a settlement from an EARLIER
    batch -- Tier 0 (routine COD timing) OR a Tier-5 order-side unmatched
    exception (has a real identifier, e.g. bank_utr, but nothing in the
    feed carries it yet) that a human hasn't explicitly resolved. Both
    are "we haven't seen the settlement yet," just via different engine
    paths -- see CLAUDE.md's 'delayed settlement' note on why a COD order
    with a known bank_utr skips engine.py's Tier-0 pre-check entirely and
    lands as a hard exception instead of a soft pending state.

    The next sync re-includes these orders alongside the new batch's data
    so a late-arriving settlement updates the SAME case instead of
    creating a duplicate. This matches this project's own established
    "reconciliation always re-walks still-open records" philosophy
    (see CLAUDE.md's earlier sync-semantics note) -- a real settlement
    that never arrives just keeps re-appearing as the same exception,
    which is expected, not a bug.
    """
    return [c["order_id"] for c in state.get("cases", {}).values()
            if c.get("order_id")
            and c.get("case_type") in ("pending_settlement", "unmatched_order", "remittance_overdue")
            and not c.get("resolution", {}).get("resolved")]


def record_resolution(state, case_id, resolution_type, resolved_by="user", comment=None):
    """Accept Recommendation / Keep for Manual Review -- persists a real
    human decision onto an existing case, along with the comment that
    justified it (auto-filled from AI's own recommendation on accept,
    required and user-typed on manual review -- see app_new.py's ticket
    page for that rule). Returns None if the case doesn't exist (never
    fabricates one)."""
    case = state.get("cases", {}).get(case_id)
    if not case:
        return None
    now = datetime.now().isoformat()
    if comment is not None:
        case["comment"] = comment
    case["resolution"] = {"resolved": True, "resolution_type": resolution_type,
                           "resolved_at": now, "resolved_by": resolved_by,
                           "comment": comment}
    case["case_status"] = "resolved" if resolution_type == "accepted" else "manual_review"
    case["updated_at"] = now
    case.setdefault("history", []).append({"at": now, "event": f"user action: {resolution_type}"})
    return case


def set_comment(state, case_id, comment):
    """Save the case's working comment (not yet a resolution) -- e.g. the
    'Save Comment' button while still investigating. Returns None if the
    case doesn't exist."""
    case = state.get("cases", {}).get(case_id)
    if not case:
        return None
    now = datetime.now().isoformat()
    case["comment"] = comment
    case["updated_at"] = now
    case.setdefault("history", []).append({"at": now, "event": "comment saved"})
    return case


def toggle_bookmark(state, case_id):
    """Flip a case's bookmarked flag -- a plain per-case marker for quick
    reference later, independent of case_status/resolution (bookmarking a
    case never changes its lifecycle state). Returns the new value, or
    None if the case doesn't exist (never fabricates one)."""
    case = state.get("cases", {}).get(case_id)
    if not case:
        return None
    now = datetime.now().isoformat()
    case["bookmarked"] = not case.get("bookmarked", False)
    case["updated_at"] = now
    case.setdefault("history", []).append(
        {"at": now, "event": "bookmarked" if case["bookmarked"] else "bookmark removed"})
    return case["bookmarked"]


def batch_is_available(state):
    """
    Whether state['current_batch'] should be revealed to the UI yet.
    Batch 1 is always available immediately. Batch 2/3 need
    next_batch_available_at to have actually passed -- checked here,
    freshly, on whatever natural Streamlit rerun calls this. No sleep,
    no background thread, no periodic API polling.
    """
    if state["current_batch"] > TOTAL_BATCHES:
        return False
    if state["current_batch"] == 1:
        return True
    ts = state.get("next_batch_available_at")
    if not ts:
        return False
    return datetime.now() >= datetime.fromisoformat(ts)
