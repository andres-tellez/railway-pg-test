"""
Safe prod promotion helper.

This script promotes specific commits to prod by cherry-picking onto origin/prod
inside an isolated git worktree. It avoids touching the caller's dirty working tree.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List


class GitCommandError(RuntimeError):
    pass


def run_git(args: List[str], cwd: Path | None = None, check: bool = True) -> str:
    cmd = ["git", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise GitCommandError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return (proc.stdout or "").strip()


def get_repo_root() -> Path:
    root = run_git(["rev-parse", "--show-toplevel"])
    return Path(root)


def ensure_commit_exists(sha: str, repo_root: Path) -> None:
    run_git(["cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo_root)


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass
class WorktreeContext:
    repo_root: Path
    worktree_path: Path
    branch_name: str


def create_worktree(
    repo_root: Path, base_ref: str, worktree_path: Path
) -> WorktreeContext:
    branch_name = f"promote-prod-{now_stamp()}"
    run_git(
        ["worktree", "add", str(worktree_path), "-b", branch_name, base_ref],
        cwd=repo_root,
    )
    return WorktreeContext(
        repo_root=repo_root,
        worktree_path=worktree_path,
        branch_name=branch_name,
    )


def cleanup_worktree(ctx: WorktreeContext) -> None:
    try:
        run_git(
            ["worktree", "remove", str(ctx.worktree_path), "--force"], cwd=ctx.repo_root
        )
    finally:
        # Local branch might already be gone in edge cases; ignore failure.
        run_git(["branch", "-D", ctx.branch_name], cwd=ctx.repo_root, check=False)
        shutil.rmtree(ctx.worktree_path, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cherry-pick specific commits onto origin/prod in an isolated worktree, "
            "optionally push to prod."
        )
    )
    parser.add_argument(
        "--commits",
        nargs="+",
        required=True,
        help="Commit SHA(s) to cherry-pick in order.",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/prod",
        help="Base ref to start promotion branch from (default: origin/prod).",
    )
    parser.add_argument(
        "--target-branch",
        default="prod",
        help="Remote target branch name (default: prod).",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Remote name to push to (default: origin).",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push the resulting HEAD to <remote>/<target-branch>.",
    )
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="Keep temporary worktree and branch after success (debugging).",
    )
    parser.add_argument(
        "--worktree-path",
        help="Optional explicit path for the temporary worktree.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation before push.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = get_repo_root()

    run_git(["fetch", args.remote, "--prune"], cwd=repo_root)
    for sha in args.commits:
        ensure_commit_exists(sha, repo_root)

    if args.worktree_path:
        worktree_path = Path(args.worktree_path).expanduser().resolve()
        if worktree_path.exists():
            print(f"ERROR: worktree path already exists: {worktree_path}")
            return 2
        os.makedirs(worktree_path.parent, exist_ok=True)
    else:
        tmp = tempfile.mkdtemp(prefix="prod-promote-", dir=str(repo_root.parent))
        worktree_path = Path(tmp).resolve()

    ctx = create_worktree(repo_root, args.base_ref, worktree_path)

    promotion_failed = False
    try:
        for sha in args.commits:
            print(f"Cherry-picking {sha} ...")
            run_git(["cherry-pick", sha], cwd=ctx.worktree_path)

        print("\nPromotion branch head:")
        print(run_git(["log", "--oneline", "-n", "5"], cwd=ctx.worktree_path))

        if args.push:
            if not args.yes:
                answer = (
                    input(f"\nPush HEAD to {args.remote}/{args.target_branch}? [y/N]: ")
                    .strip()
                    .lower()
                )
                if answer != "y":
                    print("Push aborted by user.")
                    return 0
            run_git(
                ["push", args.remote, f"HEAD:{args.target_branch}"],
                cwd=ctx.worktree_path,
            )
            print(f"\nPushed to {args.remote}/{args.target_branch}.")
        else:
            print("\nDry run complete. Re-run with --push to publish.")

    except GitCommandError as exc:
        promotion_failed = True
        print("\nERROR during promotion.\n")
        print(str(exc))
        print("\nWorktree left in place for manual conflict resolution:")
        print(f"  {ctx.worktree_path}")
        print("\nAfter resolving conflicts:")
        print("  git add <files>")
        print("  git cherry-pick --continue")
        print("  git push origin HEAD:prod")
        return 1

    if not args.keep_worktree and not promotion_failed:
        cleanup_worktree(ctx)
    elif not promotion_failed:
        print(f"\nKeeping worktree at: {ctx.worktree_path}")
        print(f"Temporary branch: {ctx.branch_name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
