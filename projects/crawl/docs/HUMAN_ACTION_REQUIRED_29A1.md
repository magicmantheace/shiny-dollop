# Human Action Required — 29A.1

No download or account-gated action blocks the proof. Blender, MPFB, System
Assets, Unreal 5.8, and Mutable were discovered locally and validated.

One optional editor-only step remains because UE 5.8 protects the Mutable graph
source from Python:

## Complete the Mutable species switch graph

**Why:** the automation creates and verifies
`/Game/Underreach29A1/Characters/CO_UnderreachDescender29A1`, but cannot write
its protected graph. The proven live backend already reconstructs the same
renderer manifests directly; this step only completes the visual editor graph.

1. Open `CO_UnderreachDescender29A1` in Unreal Editor.
2. Add Object → Component → Skeletal Mesh nodes.
3. Add a `Species` enum/switch with `human` and `dwarf` values.
4. Connect `SK_UnderreachHuman` and `SK_UnderreachDwarf` to the switch.
5. Connect the switch to the component, then the component to the root Object.
6. Compile and save.
7. Run `scripts/run-underreach-character-validation.ps1 -SkipBlender`.

There is no cost, URL, or additional asset download for this step. The import
report records `manual_graph_required=true` until UE exposes this graph safely.
