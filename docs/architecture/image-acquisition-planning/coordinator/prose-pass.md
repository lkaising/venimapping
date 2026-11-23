# Prose pass report

The pass turned `docs/architecture/image-acquisition-design-v2.md` from an integrated planning checkpoint into a standalone design. No issue was `Open` in `issues.md`. The notes in `issues.md` held no prose-pass instruction. The only unresolved decision there, `i30`, is the timestamp source. It is now L1 in section 15.

## Old-to-new section map

| Old section | New section | Change |
|---|---|---|
| Header, 1 Summary, "State of the design after round 5" | 1 Summary | Rewritten. The round recap and issue tallies are gone. An "Open items" list replaces them. |
| 1 Labels and citations | 2 Conventions | Shortened. The `facts`, `register`, `i`, `N`, and `M` ID forms are gone. |
| 2.1 to 2.6 Current state | 3 Current state | Merged with the repeated "What exists today" lists of old 6.1, 6.2, 7, and 8. `facts` shorthand is resolved to `driver:` and `ros:` citations. |
| 11 Camera findings | 4 Measured camera behavior | Now the primary home. It gains values that were repeated in old 5, 6, 7, and 8. It adds a derived-estimates table and a rule-to-measurement table. |
| 3 Requirements and working assumptions | 5 Requirements and working assumptions | The "What depends on it" column names topics and not register IDs. |
| 4.1 to 4.3 | 6 Architecture overview | The "Owner section" columns are gone. |
| 4.4 Decision register and amendment logs | Removed | Every rule is in full in its owning section (see the checks below). |
| 5 Data plane | 7 Data plane | The v1 references are gone. QoS, capacity, and slot rationale moved in from the old disagreement table. |
| 6.1 Control plane | 8 Control plane | The "What this section changes from v1" table is gone. The reasons moved into the owning rules. |
| 6.2 Error vocabulary | 9 Error vocabulary | The v1 diagnostics paragraph now states the engineering reason. |
| 7 Bring-up | 10 Bring-up | The "What exists today" list and the "Register" column are gone. |
| 8 Testing | 11 Testing | The "Old behavior" and "New behavior" columns became one "Guards against" column. |
| 8 Coverage of register entries | 11 Coverage by design rule | Rows use design rule names and not register IDs. |
| 9 Proposed source tree | 12 Proposed source tree | The "Owner" columns are gone. The CMake rules from old 9.3 and old 10 are one list under "CMake layout". |
| 10 Implementation sequence | 13 Implementation sequence | The "Owner section" column is gone. The CMake rules now point to section 12. |
| 10 "What is not in phase 1" | 14 Deferred scope | Expanded with the engineering reason for each deferral. |
| 12 Changes from v1 | Removed | Rationale moved into sections 5, 7, 8, 9, 10, 11, and 14. |
| 13 Decisions for Logan | 15 Decisions for Logan | The "Entries" lines became "Depends on" lines. L1 now holds the evidence and the two positions. |
| 14 Recorded disagreements | 15 "Empirical gates", L1, and owning sections | Settled disagreements are now rules with reasons. Unresolved ones stay as L1 and the executor gate. |

## Deliberate cuts and rewrites that could affect technical meaning

1. Register and amendment logs (old 4.4). Before the cut, each amendment was checked against its owning section. The checks covered the `receive_seq` formula, `close_admission` after a failed start and after an expiry, the `LeaseLink` rules, the join rule, the `start` return rule, the readback decides rule, the `FeedOptions::deadline` rule, the acceptance check, the `kWedged` clear rule, and the test seam. All appear in full in sections 6 to 9.
2. Decision table d1 to d29. Each decision appears in its owning section or in the deferred scope list. The `ic` contract IDs were removed from the prose and not replaced, because the contract text is in the owning sections.
3. Disagreement table (old 14). Rationale that existed only there moved as follows:
   1. Reader depth 2 and not 1, with the c1 and c3 depth 5 note: section 7, "VimbaX adapter and threads", reasons list.
   2. Default capacity 1 and not 2: section 7, "Source, subscription, and backpressure".
   3. One queue per subscription and not two fixed slots: the same place.
   4. Stop outside the deadline, and the rejected "reserve part of the deadline" rule: section 8, "Get image", "Deadline and stop".
   5. The one-shot latch and oldest-queued alternatives for freshness, and the reopen condition: section 8, "Get image", "Freshness" item 6.
   6. Settings file against service writes only: section 10, "Camera settings file".
   7. Executor split: section 6 "Threads" item 3 and section 15 "Empirical gates".
   8. Timestamp source: section 15, L1, with both positions and the evidence.
4. Changes from v1 (old 12) and the per-section v1 tables. Rationale moved as follows:
   1. No pixel copy and the 93.2 MB/s figure: section 7, "Frame and pixel ownership".
   2. String accessors that return a reference: section 7, same place.
   3. Idle subscription for the source lifetime, and the missing rclcpp rule against short-lived subscriptions: section 7, "Source, subscription, and backpressure".
   4. A RELIABLE reader does not make loss countable: section 3 "Frame loss visibility" and section 7.
   5. Match wait before start, because the VOLATILE publisher does not wait for a reader: section 8, "Start sequence" step 6.
   6. Why the last release stops the stream: section 8, "Leases and the stream lifecycle".
   7. Why the worker checks silence and a consumer does not: section 8, "Silence, outage, and reconnect".
   8. Why get image has no trigger in phase 1: section 8, "Get image" and section 14.
   9. A new error domain and not private diagnostics: section 9 opening.
   10. No `cyclonedds.xml`: section 10, "Host check" and section 14.
   11. Direct VmbC adapter deferred, with the exclusive-mode reason: section 14.
   12. A drain-then-take freshness scheme cannot see an in-flight frame: section 8, "Freshness" item 1.
5. Section 6.1 "Inputs from the code" keeps its numbering, because the rules cite "input 3", "input 4", "input 5", "input 8", "input 10", "input 11", and "input 12". Items that repeated section 3 now point to it where they were short.
6. Test tables. The old-behavior notes that named draft bugs became "Guards against" text. The text describes the real driver behavior or the real regression. Examples: the -18 wedge at Mono10, the rate write before the enable, the frames that arrive before the start reply, and the one-release rule for each link. The three long step lists and their "why the order is exact" notes are unchanged except that "with the old rule" became "a `start` that would...".
7. Bring-up checks. The bring-up test note "Old behavior ... New behavior" became "The test fails on the current files". The part B note about old behavior became "Failures that part B catches".
8. Camera measurements. These moved to section 4 and were removed from the rules that used them: the 79 ms and 3 to 5 frame start latency, the 34 ms and 16 ms intervals, the `buffer_count` 7 evidence, the 30.000001907348633 Hz read back, the 12674 s camera clock, the CLI call time, and the 110 ms start. The rules that need a number keep it only where it forms part of the rule, for example the 250 ms threshold, the 0.001 tolerance, and the 2000 ms first-frame limit.
9. Citations. `facts 1.x.y`, `X1`, `X3`, `A68`, and similar shorthand now cite `driver:` and `ros:` lines from `facts.md`. References to draft section files and draft line numbers are gone. The camera check records c1, c2, and c3 keep their names and are defined in section 4.
10. Additions that carry no new engineering claim. These are the "Derived estimates" table, the "Rules that rest on these measurements" table, the "Empirical gates" list, and the new reasons in section 14. The derived values come only from numbers in the old text, for example 30 ms plus 79 ms, and 25 calls at 2000 ms for the 50 s estimate.

## Unclear passages left intact

1. Start latency. The old text says the cold path takes "about 110 ms to the `stream_start` reply", with the first frame about 30 ms after the driver starts the call and the reply 79 ms later. The old bring-up note says the 2000 ms first-frame limit is "about 18 times the measured 110 ms from `stream_start` to the first frame". The two uses of 110 ms refer to different events. The new text keeps the first meaning (reply) in the derived estimates and says "start latency" in the bring-up note.
2. R7 says the cost to reverse is "Low above 200 ms". L6 asks about "less than about 200 ms". The text does not say what the cost is below 200 ms.
3. The `get_image` probe mode gives a warm limit of "under 67 ms". The text elsewhere gives a warm time of about one frame period, 33 ms. The 67 ms value is two periods, but the old text does not say so.
4. P11 and part A. Step 11 of part A stops the check if the camera does not take the written values. The note says the camera may return to its own defaults after a driver restart. The old text does not say whether a restart without a power cycle was measured.
5. The decision L1 option 3 needs "a new patch for L3". L3 lists four candidate patches, and none of them publishes both stamps. The old text does not name the patch.
6. The control plane inputs list item 11 and 12 pointed at the data-plane draft. Both now point at section 7. The old text gave no direct code citation for the `take` rule.
