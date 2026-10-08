# Contributing

SurfaceReducer is intentionally strict about authority boundaries.

Contributions should preserve these invariants:

- reducer code does not perform the authoritative operation it observes;
- hooks emit only after owner state is durable;
- every terminal or qualified claim is evidence-bound;
- duplicate delivery is idempotent;
- old observations do not overwrite newer current state;
- unknown/missing state is explicit rather than inferred as success;
- agent harnesses may propose hooks but do not silently gain execution authority.

Please include tests for currentness, duplicate delivery, failure paths, and replay whenever adding a new reducer or adapter behavior.
