## Task: trace the current acquisition path

Work alone. The other planner does the same task from the same checkpoint. You
cannot see its trace until both traces are done. Do not look for it.

Read `src/venimapping_camera`, `src/venimapping_bringup`, the driver source,
and v1. Then write `{P}/{tool}/trace.md` with these sections:

1. Current path. Describe what exists today between the camera and any
   consumer: the gateway, the driver services and topics, the launch files,
   the parameters, and the threads. Cite each point.
2. Driver contract. Describe what the driver offers for acquisition: image
   publishing, stream start and stop, single frames and triggers, timestamps,
   frame identity, frame loss visibility, calibration, events, and connection
   handling. Cite the driver source.
3. Audit of v1. Write a table with the columns Claim, v1 section, Verdict, and
   Evidence. The verdict is Confirmed, Stale, or Wrong. Cover each claim in v1
   sections 2 and 3, and each other v1 claim about the code or the driver.
4. Unknowns. List what the code and the documents cannot answer. For each
   unknown, say if a camera check or Logan can answer it.
5. Design choices. List the design choices for get image and get image feed.
   Give each choice a short question. Do not take positions yet.

If an unknown blocks a design choice, you may write a camera request.
