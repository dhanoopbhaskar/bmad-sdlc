# DEV Phase Map (Role Overlay)

DEV delta only. Base `phase-map.md` owns the action tables; `role-config.toml` owns ownership.

- DEV runs `build.atdd`, `build.ticket`, `build.auto`, `build.loop`, and `build.tests`. `build.review` and `build.done` are QA's; DEV supplies the change, QA decides.
- Pick ready tickets from the BMAD artifacts; never invent one. `build.auto` and `build.loop` record nothing until each ticket's `build.ticket` gate is set.
- A built-in `bmad-build` review can satisfy `build.review` when its findings were triaged; record which review ran.
- DEV hands off when `next_action.role_allowed` is false (`handoff-protocol.md` §Role transitions). Never write a foreign gate without a reason.
