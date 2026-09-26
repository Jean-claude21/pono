"""What the server tells agents (D-006): served, versioned, never frozen in a plugin.

Written in English: no agent client sends a language when it connects (003 FR-013).
"""

SERVER_VERSION = "4.0.0"

INSTRUCTIONS = """\
Pono is the control desk of projects built with agents. It reads each project's real state from its
providers and guards production. These tools give you the same view and the same gestures as the
Pono console, within the access the person granted you.

How to use them:
- Start with `list_projects`: every project, its state, the reason, and what needs a decision.
- `get_project` gives one project in full; `list_releases` explains why a change towards production
  is refused or waiting (each guard, with the file, the line and the operation); `read_journal`
  says who did what and when.
- Always report facts as Pono states them, with the time they were read. Never guess a state.

What you may do with an access "read and act": import a repository, ask for a reading, ask for a
release to be evaluated again once the author fixed it, protect a production branch, and ask for a
rollback.

The development runtime (when the project has one):
- `start_runtime` asks for it; the first time, Pono proposes the runtime's files on the development
  branch and a person merges that proposal. `get_runtime` says where it stands.
- `write_file` and `delete_file` change the running runtime at once; the person sees the screen
  update in seconds. Writes are saved to the development branch after a quiet minute, or with
  `save_changes`. Never production.
- After a write, call `read_runtime_errors` to see compilation and browser errors, with file and
  line; fix them before moving on.
- A path listed in `conflicts` changed on the branch meanwhile: read it, then write the version you
  want again.
- Opening the runtime in a browser is the person's gesture: give them `openUrl`.

What only a person does, in the Pono console, by design:
- approving a release for production: tell the person the change is waiting and give them the
  project's console link from `get_project`;
- running a rollback: `request_rollback` only asks; a person confirms it in the console.

Errors come back as stable codes (for example `release.not_ready`, `provider.unavailable`). Explain
them plainly; never retry a refused guard by other means.
"""

__all__ = ["INSTRUCTIONS", "SERVER_VERSION"]
