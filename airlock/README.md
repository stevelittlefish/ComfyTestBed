# airlock/

The Captain's drop zone. Shove raw cargo in here and tell the ship's computer to
process it.

Typical use: dump freshly-exported ComfyUI workflow JSON files in here, then say
**"import the new workflows"**. The computer will:

1. Move each file to its proper home in `workflows/`.
2. Adjust it — swap the hardcoded prompt for `%PROMPT%` and the seed for `%SEED%`.
3. Verify the placeholder substitution still parses as JSON.

Then it's a real workflow and the harness can fly it.

**Everything in here except this README is git-ignored.** The airlock is a staging
area — part of the process of building the ship, not part of the ship. Nothing dumped
here gets committed; it only matters once it's been imported and moved somewhere real.

So don't leave anything precious floating in the airlock. It is, by design, one good
depressurisation away from the void.
