# Postmortem: All Builds Showing "Timed Out" Despite Succeeding

**Date:** 2026-04-03
**Severity:** Critical — users could never see build results
**Duration:** ~3 hours (from first deployment to fix)
**Fix commit:** f1a7448

## Summary

Every build triggered from the web UI appeared to "time out after 10 minutes", even though GitHub Actions completed them successfully in 44-100 seconds. Users were told their builds failed when they actually succeeded.

## Root Cause

**React stale closure in `setInterval`.**

```tsx
// handleBuild sets state:
const startTime = Date.now();
setBuildStartTime(startTime);  // async! not yet applied

// pollBuildStatus creates an interval:
const interval = setInterval(() => {
  const elapsed = Date.now() - buildStartTime;  // ← captured as 0
  if (elapsed > 600) {
    // IMMEDIATELY triggers because Date.now() - 0 = 1.7 trillion ms
    setBuildError("Build timed out");
  }
}, 5000);
```

`setBuildStartTime(startTime)` is asynchronous — React batches state updates. When `pollBuildStatus` was called on the next line, `buildStartTime` was still `0`. The `setInterval` callback captured this stale value in its closure and never saw the update.

Result: `Date.now() - 0` = a number in the billions, far exceeding the 600-second timeout threshold. The very first poll triggered the timeout.

## Why It Wasn't Caught Earlier

1. **Backend always worked** — `curl` tests against the Worker API showed correct results, masking the frontend issue.
2. **The error message was misleading** — "Status polling timed out after 10 minutes" implied a slow build, not an instant bug.
3. **Multiple red herrings** — GitHub API rate limits were occurring simultaneously, creating a plausible alternative explanation.
4. **The timer display also broke** — showed `0:00` forever (same stale closure), but we attributed this to the 5s poll interval rather than a fundamental bug.

## Fix

Use `useRef` instead of `useState` for values accessed inside `setInterval`:

```tsx
const buildStartTimeRef = useRef(0);

// In handleBuild:
buildStartTimeRef.current = Date.now();

// In setInterval:
const elapsed = Date.now() - buildStartTimeRef.current;  // always current
```

`useRef` values are mutable and not part of React's render cycle, so they're always current inside closures.

## Lessons Learned

1. **Any state read inside `setInterval`/`setTimeout` must use `useRef`**, not `useState`. This is a well-known React pitfall but easy to forget.
2. **When backend works but frontend doesn't, check closures first.** "Works in curl, broken in browser" is a strong signal.
3. **Test the full user flow end-to-end before deploying**, not just individual API endpoints.
4. **Don't trust the error message you wrote** — "timed out after 10 minutes" was happening on the first poll, not after 10 minutes.

## Prevention

- Add this to code review checklist: "Does any async callback (setInterval, setTimeout, Promise.then) reference React state? If yes, use useRef."
- Consider using a custom hook like `useLatestRef` that auto-syncs state to ref.
