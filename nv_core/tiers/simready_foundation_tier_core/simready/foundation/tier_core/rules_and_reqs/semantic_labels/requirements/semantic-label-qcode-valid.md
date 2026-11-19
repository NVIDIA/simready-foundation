# semantic-label-qcode-valid

| Code     | SL.QCODE.001 |
|----------|--------------|
| Validator| {oav-validator-latest-link}`sl-qcode-001` |
| Compatibility | {compatibility}`nvidia-omniverse`  |
| Tags     | {tag}`correctness` |

## Summary

If the Wikidata ontology is used, Q-Codes must be well-formed (`Q` followed by one or more digits). Values should reference a real Wikidata entity, but the validator checks format only — it does not contact wikidata.org.

## Description

[**Wikidata**](https://wikidata.org) is an open, collaboratively edited knowledge base with over 115 million items covering objects, materials, brands, places, and concepts. It is the taxonomy NVIDIA uses for its Omniverse Asset libraries (instance name `wikidata_qcode`). Each item is identified by a stable, language-independent **Q-code** (for example, `Q1420` for "motor car"), which is what makes it well-suited as a labeling key: the code never changes even as the human-readable name is edited or translated.

Labeling with a Q-code rather than a free-text string buys you the rest of Wikidata's structure for free:

- **Multilingual lookup.** Every item carries labels, descriptions, and aliases in hundreds of languages, so a single Q-code resolves to the correct term whether your downstream consumer reads English, Japanese, German, or Hindi — no parallel translation tables to maintain.
- **Ontology / hierarchy.** Items are linked by typed properties such as *instance of* (`P31`) and *subclass of* (`P279`), forming a navigable class hierarchy. From a leaf label you can walk up to broader categories (e.g. `aluminium` → `metal` → `chemical substance`) to group, aggregate, or coarsen labels for training without re-annotating assets.
- **Rich descriptions and aliases.** Each item has a short disambiguating description plus a list of synonyms/aliases, which helps both humans and agents confirm that a code means what they intend (and distinguish, say, a `jaguar` the animal from the car brand).
- **Machine-queryable and linked.** The graph is queryable via the public SPARQL endpoint and items cross-reference external identifiers and Wikipedia articles, so labels can be enriched, validated, or joined against other datasets programmatically.

When using Wikidata Q-Codes for semantic labeling, the codes must follow the proper format (`Q` followed by one or more digits). They should reference a real Wikidata entity so the structure above is actually available to consumers, but the validator enforces only the format — it does not verify retrievability against wikidata.org (a USD validator should not depend on network access).

## Why is it required?

- Well-formed Q-codes resolve to a real Wikidata entity, keeping its multilingual labels and ontology available to consumers
- Maintains consistency with Wikidata ontology standards
- Enables proper ML training with consistent, machine-resolvable ground truth labels

## Examples

```usd
# Invalid: Malformed Q-Codes
def Mesh "InvalidLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    token[] semantics:labels:wikidata_qcode = [
        "Q",           # Too short
        "QABC",        # Contains letters
        "123",         # Missing Q prefix
        "Q-1"          # Contains invalid characters
    ]
}

# Valid: Properly formatted Q-Codes
def Mesh "ValidLabels" {
    uniform token[] apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    token[] semantics:labels:wikidata_qcode = [
        "Q1420",       # Valid Q-Code for "motor car"
        "Q11442",      # Valid Q-Code for "bicycle"
        "Q41176"       # Valid Q-Code for "building"
    ]
}
```

## How to comply

Use properly formatted Q-Codes that:
1. Start with capital "Q"
2. Follow with one or more digits (0-9)

The validator enforces the two rules above. As a convention (not validated here), each code should also reference a real, retrievable Wikidata entity.

## For More Information

- [Semantic Labels Capability](../capability-semantic_labels.md)
- [Semantic Label Capability Requirement](semantic-label-capability.md)
- [Semantic Label Deprecated Schema Requirement](semantic-label-deprecated-schema.md)
