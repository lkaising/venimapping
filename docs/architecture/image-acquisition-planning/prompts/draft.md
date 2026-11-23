## Task: draft your sections of v2

Read `{P}/register.md`, `{P}/coordinator/facts.md`, both traces, v1, and the
code. Follow the register. Draft only the sections that the section owners
list gives to {tool}. Write each section to `{P}/{tool}/sections/<name>.md`.

Each section must contain these items:

- data-plane: the frame type and its fields, the frame source port, the
  bounded queue and its backpressure rules, the threading and memory model,
  and the adapter over the driver.
- control-plane: the stream lifecycle, the configuration order, the policy
  layer for get image and get image feed, and the handling of disconnects and
  silence.
- error-vocabulary: the error values, the layer that raises each one, and how
  callers react to each one.
- bring-up: the launch, parameter, and namespace changes in
  `venimapping_bringup`.
- testing: unit tests without ROS, tests with the driver, and short hardware
  checks. Each test must tell the old behavior from the new behavior.
- implementation-sequence: ordered steps. Each step must build and pass its
  checks alone. Each step names its files and its exit check.

Also write these files:

1. `{P}/{tool}/source-tree.md`. List each file that your sections add or
   change, with one line about its purpose. Use the existing package layout.
2. `{P}/{tool}/draft-notes.md`. List each place where you disagree with the
   register, with evidence. Follow the register in the sections anyway. Also
   list the interface details that the other planner must match.

Start each section with a level-2 heading in sentence case. Write for a reader
who knows C++ and ROS 2 but has not read the planning files. Cite the register
id where a decision applies.
