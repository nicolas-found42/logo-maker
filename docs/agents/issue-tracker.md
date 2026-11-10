# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `nicolas-found42/logo-maker`:
[repository issues](https://github.com/nicolas-found42/logo-maker/issues). Use the `gh` CLI.

## Target and ticket operations

Before the first write in a session, run `gh repo view --json nameWithOwner` from this
clone and verify the target is `nicolas-found42/logo-maker`. Use
`--repo nicolas-found42/logo-maker` on writes so fork or directory defaults cannot
redirect them.

- Create: `gh issue create --repo nicolas-found42/logo-maker --title "..." --body-file /path/to/body.md`.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open --limit 100 --json number,title,labels`; add label filters as needed.
  Use `gh api --paginate repos/nicolas-found42/logo-maker/issues` when exhaustive discovery is required;
  exclude entries with a `pull_request` field from issue-only results.
- Edit: `gh issue edit <number> --repo nicolas-found42/logo-maker --body-file /path/to/body.md`.
- Comment: `gh issue comment <number> --repo nicolas-found42/logo-maker --body-file /path/to/comment.md`.
- Labels: `gh issue edit <number> --add-label "..." --remove-label "..."` with the explicit
  `--repo nicolas-found42/logo-maker` target.
  Read `triage-labels.md` for the role mapping and usage rules.
- Close: post the explanation as a comment, then run
  `gh issue close <number> --repo nicolas-found42/logo-maker`. Post the comment separately
  even when the issue is already closed.

Write multiline bodies to a temporary UTF-8 file and pass `--body-file`.

## Templates for agent submissions

Apply these rules when creating issues or creating/updating PR descriptions through
the CLI, a connector or the API, as well as through the browser.

- **Issues:** read `.github/ISSUE_TEMPLATE/bug-report.yml` or
  `.github/ISSUE_TEMPLATE/feature-request.yml` as appropriate. Build a Markdown body
  using the form's field labels as headings, answer every required field, and add
  applicable optional evidence. Explain unavailable information rather than inventing
  it. Preserve additional sections required by the originating skill, such as a spec
  or agent brief. Apply the intended labels explicitly, using the form defaults and
  `triage-labels.md`; a requested workflow may select a different canonical triage role.
- **PR descriptions:** use the installed `pr` skill and fill
  `.github/pull_request_template.md`, preserving its headings and required fields.
  The template supplies the repo-specific structure; the skill supplies the evidence,
  capture/attachment and saved-PR inspection workflow. Keep missing required evidence
  visible as an unresolved gap.

Before publishing, check the body against the current template: required sections
contain actual answers, placeholders are replaced, commands have observed results or
explicit reasons not run, and issue labels include exactly one triage role.
When updating an existing issue, preserve its established role unless the task calls
for a transition; when updating a PR body, preserve unrelated author content.

After publishing, read back the saved body and labels to catch omissions. For PRs,
also complete the `pr` skill's saved-page visual inspection before claiming the PR is
verified.

## Automated template validation

Before publishing, run the same validator used by the template-validation workflow:

```sh
python3 scripts/template_check.py --kind pr --body-file /path/to/pr-body.md
python3 scripts/template_check.py --kind bug --body-file /path/to/bug-body.md
python3 scripts/template_check.py --kind feature --body-file /path/to/feature-body.md
```

Use the form's field labels as level-three headings in issue bodies. Required issue
fields come from the checked-in form metadata. Keep required field labels as plain,
single-line scalars and `validations` in the existing two-line block layout; unsupported
metadata layouts fail validation rather than silently dropping requirements.

The PR template supplies required heading levels, table rows and Merge Danger fields.
Every response cell needs an answer; `N/A` or `not run` needs an explanation. `Gaps`
may say `None`. Before and After each require a distinct HTTPS image reference and
a caption identifying the revision and scenario. Comments, code samples of image
markup, local paths and placeholder answers do not satisfy these requirements.

The workflow revalidates current PR bodies on open/edit/reopen/synchronize/ready events
and publishes the commit status **`template/pr`** on the current PR head. It checks
current state again before publishing a result. The validator and templates are loaded
from the trusted base/default branch; contributor code is never executed by this job.

For opened/edited/reopened or relabeled issues, the workflow validates the current body
using its `bug` or `enhancement` category. Invalid open issues fail the run and move to
`needs-info`, preserving category, area and other supplementary labels. Valid issues
keep their existing labels; triage decides the next role after information arrives.
Issues stay open, and the workflow posts no comments.

Image references are checked structurally, without fetching their URLs. CI cannot
prove that images show the claimed result or that a written test result is truthful;
the `pr` skill's evidence capture and saved-page inspection remain required.

### Making the PR check required

After the workflow, validator and templates reach the default branch and `template/pr`
has run successfully, require **`template/pr`** in the `main` branch protection or
ruleset. Keep existing required checks when adding it. A workflow failure alone does
not prevent merging without this repository setting. GitHub has no issue-creation
status gate; issue validation runs after creation, including API-created issues.

On 2026-11-10, GitHub rejected both branch-protection and ruleset access for this private
repository with HTTP 403. Later that day, the owner authorized making the repository
public, which removed that restriction. Required-check enforcement is configured in
the repository settings; keep `template/pr` required when changing those settings.

## Parent issues and dependencies

Use native GitHub relationships:

- Create a child with `gh issue create --parent <parent>` and the explicit repo,
  title and body-file flags described above.
- Link an existing child:
  `gh issue edit <parent> --repo nicolas-found42/logo-maker --add-sub-issue <child>`.
- Add a blocker:
  `gh issue edit <child> --repo nicolas-found42/logo-maker --add-blocked-by <blocker>`.

Check the installed CLI's help before using these flags. If native relationships are
unavailable, use `Part of #<parent>` and `Blocked by: #<number>` at the top of the
child body, plus a child task list in the parent. Work is startable when all blockers
are closed; check the linked issues rather than inferring this from a label.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Skill requests

- “Publish to the issue tracker”: create a GitHub issue in this repository.
- “Fetch the relevant ticket”: read the issue body, labels, and comments.
- A bare `#<number>` can be an issue or a PR; inspect its type before selecting
  `gh issue` or `gh pr` commands.
