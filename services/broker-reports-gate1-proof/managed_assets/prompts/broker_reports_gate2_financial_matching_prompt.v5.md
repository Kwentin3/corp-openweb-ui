Make one semantic matching decision for one deterministically prepared
financial fragment.

Use the available type cards in the decision packet as the only authority for
financial meaning. Match the source fragment to exactly one available type and
bind only source value references listed for that type's roles. Return a typed
decision only when the meaning is uniquely supported and every required role
has one permitted binding. Otherwise return an unclassified financial
decision and retain the permitted source value references.

Technical source support, layout-only detection, and structural binding
ambiguity are resolved before this request. Do not reconsider those technical
decisions. Do not invent, calculate, aggregate, normalize, repair, or transform
source values.

Return exactly one JSON object allowed by the supplied strict response schema.
Do not add prose, confidence, provenance, audit metadata, or additional fields.

{{financial_semantic_decision_packet_json}}
