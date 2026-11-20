---
name: pr-review-then-approve
description: >-
  Reviews a GitHub pull request via gh, proposes review comments, then optionally
  submits APPROVE with user-supplied body text. Use when the user pastes a PR URL
  and wants a review first, then to approve with custom or proposed wording; or
  when they say "review then approve", "PR review and approve", or similar.
disable-model-invocation: true
---

# PR review then optional approve

End-to-end workflow: **fetch PR → review → stop → user decides → approve only on explicit instruction with user-controlled body.**

## Prerequisites

- Shell with **`gh`** authenticated for the PR’s host (e.g. set `GH_HOST` for `github.twdcgrid.net`).
- User rules apply: only create git commits when asked; **approving a PR mutates GitHub** — do it only in **Phase 3**.

## Phase 1 — Ingest the PR

1. From the user message, take the **PR URL** or `owner/repo` + number.
2. Set host if needed, for example:

   ` $env:GH_HOST='github.twdcgrid.net' ` (PowerShell) when the URL is on TWDC Grid.

3. Fetch at least:
   - `gh pr view <url|n> --repo <repo> --json number,title,state,url,author,isDraft,createdAt,mergedAt,commits,reviewRequests,reviews,statusCheckRollup`
   - `gh pr diff …` (or `gh api` if diff is huge — summarize by file and highlight risky hunks).
   - Optional: `gh api repos/{owner}/{repo}/pulls/{n}/comments` for inline threads.
4. If the PR is **merged/closed** or **draft**, say so and do not offer approve unless the user still wants a retrospective review only.

## Phase 2 — Review output (mandatory stop)

Produce a concise review for the user. Use this structure:

1. **Summary** — what the PR does in one or two sentences.
2. **Strengths** — bullet list when applicable.
3. **Risks / issues** — severity labels: Critical / Important / Minor / Question (or the user’s usual scale).
4. **Check status** — briefly note failing checks (CI, required reviews) if any.
5. **Proposed approval comment** — a short block of text suitable for GitHub’s approve box: positive summary + optional follow-ups (non-blocking). This is **only a draft**; the user may replace it entirely.

Then **stop and ask** exactly:

> Do you want to **approve** this PR on GitHub?  
> - Reply **`no`** / **`skip`** to leave it at the review only.  
> - Reply **`yes`** and paste the **exact comment body** you want on the approval (you can copy from “Proposed approval comment”, edit it, or write something new).  
> - Or reply **`yes, use proposed`** to approve with the proposed approval comment verbatim.

Do **not** run `gh pr review --approve` until Phase 3 conditions are met.

## Phase 3 — Approve (only after explicit yes + body)

Run only when **both** are true:

1. The user clearly approves going ahead (e.g. “yes”, “approve”, “yes use proposed”).
2. Either:
   - they pasted the **final** comment body for the approval, or
   - they said **use proposed** / **use the proposed comment** and the agent still has that exact text.

Command (adapt URL/repo/number):

```powershell
$env:GH_HOST='github.twdcgrid.net'   # if applicable
gh pr review <number-or-url> --repo owner/repo --approve --body @'
<paste user’s final approval comment verbatim>
'@
```

Use a here-string or file for multi-line bodies so quotes stay faithful.

After success, confirm: PR link, that review state is **APPROVED**, and one-line reminder that merge may still require green CI or other reviewers.

## Edge cases

- **Wrong host / auth errors**: say what failed; do not retry auth flows repeatedly; user fixes `gh auth`.
- **User approves without pasting body and does not say “use proposed”**: ask once for the exact comment or confirmation to use proposed.
- **Partial reuse**: user’s pasted text wins even if it only reuses part of the draft.
- **Enterprise**: respect existing user rules (e.g. Disney `github.twdcgrid.net`); never push or merge unless explicitly asked (this skill only approves when instructed).

## What not to do

- Do not approve without explicit post-review confirmation.
- Do not substitute paraphrased approval text for what the user pasted unless they asked for “proposed verbatim”.
- Do not request or store secrets; PR bodies stay in the chat or `gh` output only.
