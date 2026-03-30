# Prod Release Workflow (Conflict-Safe)

This workflow prevents "push to prod" surprises caused by branch drift and dirty
local worktrees.

## Why this exists

- `dev` and `prod` often diverge.
- Direct pushes to `prod` can fail or create unreviewed merges.
- Local uncommitted changes can interfere with branch switching.

## One-time policy

1. Protect `prod` in GitHub settings:
   - Require pull requests before merging
   - Disable direct push to `prod`
2. Promote to `prod` only from commits (SHA list), not from "whatever is on dev".

## Scripted promotion

Use `scripts/promote_to_prod.py` to cherry-pick onto `origin/prod` in an isolated
worktree (does not modify your current working tree).

### Dry run (recommended first)

```bash
python scripts/promote_to_prod.py --commits <sha1> <sha2>
```

### Push to prod

```bash
python scripts/promote_to_prod.py --commits <sha1> <sha2> --push --yes
```

What this does:

1. `git fetch origin --prune`
2. Creates temporary branch/worktree from `origin/prod`
3. Cherry-picks each commit in order
4. Pushes `HEAD:prod` (if `--push`)
5. Cleans up temporary worktree/branch on success

If a conflict occurs, the script keeps the temporary worktree so you can resolve
manually without risking your main working directory.

## Manual conflict resolution in temporary worktree

When the script prints a conflict path:

```bash
git add <resolved files>
git cherry-pick --continue
git push origin HEAD:prod
```

## Optional: keep worktree for inspection

```bash
python scripts/promote_to_prod.py --commits <sha> --keep-worktree
```
