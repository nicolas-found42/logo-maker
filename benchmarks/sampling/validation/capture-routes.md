# PR evidence routes

- Real direct five-call generic-edge reproduction ran against isolated baseline archive
  `38ba86b9ccff305cb453c46920824509ae989f76` and implementation `d9d61ae` with matching inputs.
- Baseline metadata initially failed because a `git archive` extraction has no `.git`.
  Retried with the pinned revision passed explicitly and `PYTHONPATH` selecting the isolated
  source. Both observed outputs are retained as text.
- Headless project `playwright-core` with installed Chrome rendered actual stdout as text
  and captured `/tmp/logo-maker-sampling-before.png` and `...-after.png`. No GUI terminal or
  full desktop was opened/captured. Both images were inspected for legibility and privacy.
- Installed `gh issue comment --help` advertises `--attach`; it uploaded both images while
  posting the authorized #5 progress/evidence comment. Saved body was read back and contains
  distinct durable GitHub attachment URLs. This first supported route succeeded; no new host
  or fallback storage was used.
- Before: `https://github.com/user-attachments/assets/46e83cc3-4b9b-48b7-ae48-ff95a3b35d7f`
- After: `https://github.com/user-attachments/assets/08897352-7bb6-4e98-8c1b-12c0e860af85`
- Saved PR browser inspection is recorded separately after publication; these attachments
  alone do not establish that the PR description rendered correctly.
