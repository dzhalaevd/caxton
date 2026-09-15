# Spreadsheet composition plan

Status: implemented; non-normative rationale for the public contract in
[`ARCHITECTURE.md`](../../ARCHITECTURE.md).

This note defines an implementation plan for composing independently constructed
spreadsheet reports into one `SpreadsheetDocument`. It does not expand the public
compatibility contract by itself. The delivered contract remains the one documented in
[`ARCHITECTURE.md`](../../ARCHITECTURE.md); implementation of this plan must update that
file.

## Use case

An application builds several report sections independently and wants one workbook:

```python
class AllIssuesReportBuilder:
    """Build one workbook containing every non-empty issue report."""

    SECTIONS = (
        ("Параметры", ParamsCheckReportBuilder, "params_check"),
        ("Уязвимости", VulnerabilitiesReportBuilder, "vulnerabilities"),
        ("Секреты", SecretsReportBuilder, "secrets"),
    )

    @classmethod
    def build_document(
        cls,
        data: AllIssuesReportData,
    ) -> SpreadsheetDocument:
        sections = {}

        for title, builder, field_name in cls.SECTIONS:
            section_data = getattr(data, field_name)
            if section_data.rows:
                sections[title] = builder.build_document(section_data)

        if not sections:
            raise ValueError(
                "Нельзя сформировать пустой отчёт по несоответствиям",
            )

        return compose(
            sections,
            theme=REPORT_THEME,
            styles=REPORT_STYLES,
        )
```

Today the application must unpack every child document, allocate output worksheet
names, copy immutable worksheets with those names, reconcile workbook settings, and
construct a new spreadsheet. That repeats composition policy in callers.

The meaningful problem is not tuple concatenation. It is including named report
sections while preserving their local meaning and producing one valid semantic
document.

## Decision

Add one family-specific public operation:

```python
def compose(
    sections: Mapping[str, SpreadsheetDocument],
    *,
    metadata: Mapping[str, Any] | None = None,
    styles: StyleSheet | Mapping[str, Style] | None = None,
    theme: DocumentTheme | None = None,
    template: TemplateSpecification | None = None,
) -> SpreadsheetDocument:
    ...
```

The mapping key is the section identity and visible worksheet-name prefix. Mapping
insertion order is the section order. Each value is an independently constructed
spreadsheet document.

`compose()` returns an ordinary flat `SpreadsheetDocument`. It is an in-process
operation: no adapter is required, and it must not render, inspect an artifact, or read
row data.

Keep `spreadsheet(*worksheets)` unchanged as the leaf factory. Do not make it accept
nested documents. Construction from worksheets and composition of report sections are
different operations with different conflict semantics.

### Why this interface

- A complete section is one mapping entry instead of an `include(...)` wrapper.
- Section order and section identity are visible at the call site.
- The mapping gives the implementation enough context to allocate worksheet names and
  rebase section-local worksheet references.
- Workbook-level policy remains expressible through keyword arguments.
- There is no intermediate collection or public builder graph.
- One implementation owns naming, reference rebasing, settings reconciliation, and
  errors, giving callers leverage and maintainers locality.

## Scope and non-goals

The initial feature composes documents that may contain multiple worksheets and
section-local cross-worksheet references.

It does not provide fully isolated lexical scopes for every named entity. In the first
version:

- worksheet names are section-qualified;
- explicit section-local worksheet references are rebased;
- table names remain workbook-global;
- style names remain document-global after reconciliation;
- cross-section references are rejected;
- template-bearing child documents are rejected.

This is the smallest coherent feature that replaces the application's worksheet naming
loop without introducing a new hierarchical document model.

## Behavioral contract

### Section normalization

- `sections` must be a `Mapping`.
- Each key must be a non-empty string.
- Keys must be unique under `casefold()`. A custom mapping that exposes duplicate
  case-insensitive keys is invalid.
- Each value must be a `SpreadsheetDocument`.
- Process entries in mapping iteration order.
- A child document with zero worksheets contributes nothing.
- If no worksheets remain after structural flattening, raise `CaxtonValueError`.
- Preserve block, table, column, and `DataSource` identity unless a containing node must
  be replaced to rebase a semantic reference.
- Never iterate a source, probe it for emptiness, infer a row count, or alter its
  repeatability state.

`compose()` can detect an empty document structurally but cannot detect an empty table
without consuming data. Applications remain responsible for deciding whether a section
with an empty row source should be included. A section builder may instead return a
zero-worksheet document when its application contract defines that as empty.

### Output worksheet names

For every child worksheet, derive the semantic output name as:

```text
<section> - <child worksheet name>
```

For example:

```text
Параметры - Сводка
Параметры - Детали
Уязвимости - Сводка
```

Composition must not silently append numeric suffixes. Final names must be unique under
`casefold()`; otherwise raise `InvalidOperationError` with the contributing sections
and local worksheet names.

The first version does not sanitize or truncate names according to XLSX rules. Those
rules belong to the selected target. Existing validation and renderer diagnostics must
reject an unrepresentable final name before output is delivered. Applications that need
shorter names should choose shorter section or child worksheet names deliberately.

### Worksheet references

Within each child document, build a complete mapping from local worksheet name to final
worksheet name before rewriting any node.

Rebase every explicit section-local `sheet_ref()` used by:

- `CellReference`;
- `RangeReference`;
- chart `TableReference` values;
- formulas nested in `FormulaBinary` nodes;
- conditional-format rules;
- future spreadsheet nodes that contain one of the supported reference values.

An explicit sheet reference must resolve within the same child document. References
that do not resolve locally are rejected as `cross_section_reference`; the composer
must not guess that they target another section by comparing final display names.

Unqualified `col()` and `table_ref()` values remain unchanged. Their existing local or
workbook-global resolution rules apply after composition.

The implementation rewrites immutable semantic nodes and reuses each underlying
`TableData.source` by identity. It must use explicit visitors for the closed spreadsheet
block and formula hierarchies rather than generic recursive copying.

### Table names

Named tables remain workbook-global in the initial feature. Equal names in different
sections are not automatically qualified because table names are also semantic formula
and chart identities and may materialize as backend-native table names.

After composing sections, detect duplicate table names under `casefold()` and report
them through the existing structural validation. The error context should identify the
section and worksheet that contributed each duplicate.

Section builders that are intended for composition must therefore use globally stable
table names, for example `params_issues`, `vulnerability_issues`, and `secret_issues`.
True local table scopes are a separate future capability.

### Styles

Build the final `StyleSheet` as follows:

1. Merge named styles from child documents in section order.
2. Coalesce the same style name when its `Style` value is equal.
3. If child documents define different values under the same name, raise
   `InvalidOperationError` unless the outer `styles=` explicitly defines that name.
4. Overlay explicitly supplied outer styles last. An outer definition is an intentional
   resolution of a child conflict.

Do not inspect blocks to discover which definitions are in use. Unused named styles
follow the same rules as used styles. Style strings inside blocks do not need rewriting
because the final sheet has one reconciled definition per name.

### Theme

- If `theme=` is supplied, it is the final document theme.
- Otherwise treat `DocumentTheme()` as neutral.
- If no child has a non-default theme, use `DocumentTheme()`.
- If all non-default child themes are equal, inherit that theme.
- If non-default child themes differ, raise `InvalidOperationError` and require an
  explicit outer `theme=`.

Theme reconciliation is structural. It must not resolve styles or materialize backend
formats.

### Metadata

- If `metadata=` is supplied, it is the complete final metadata mapping.
- Otherwise merge child mappings by key in section order.
- Equal values under the same key coalesce.
- Different values under the same key raise `InvalidOperationError` and require
  explicit outer metadata.
- Do not deep-merge nested mappings; metadata remains opaque document intent.

### Templates

A child document with a non-`None` template is rejected with
`InvalidOperationError`. A template owns a workbook operation and is not a reusable
report section.

The composed document may receive one explicit outer `template=`. Existing template
inspection, placement, capability, and failure-atomicity rules then apply to the final
document before the target is touched.

## Error contract

Use existing stable public errors:

- `CaxtonTypeError` for an invalid `sections` mapping, key, or value type;
- `CaxtonValueError` for an empty key or a composition with no worksheets;
- `InvalidOperationError` for name, reference, settings, or template conflicts;
- existing aggregated `ValidationError` issues for global table-name conflicts and
  other problems in the final semantic document.

Every `InvalidOperationError` must contain a stable `reason` and relevant semantic
context. Initial reason values:

- `duplicate_section`, with the conflicting section names;
- `worksheet_name_conflict`, with sections and local worksheet names;
- `cross_section_reference`, with section, worksheet, and requested worksheet;
- `style_conflict`, with style and contributing sections;
- `theme_conflict`, with contributing sections;
- `metadata_conflict`, with key and contributing sections;
- `included_template`, with the section.

Do not expose private rename plans, visitors, or merge-state objects through errors or
return values.

## Architecture placement

The external seam is the new `caxton.compose` / `caxton.api.compose` operation.

Suggested dependency placement:

```text
caxton.api.compose
    -> caxton._internal.composition.spreadsheet
    -> caxton.core immutable models and errors
```

The public function performs only argument normalization and delegates. The private
implementation owns:

- section validation and ordering;
- worksheet output-name planning;
- section-local worksheet-reference resolution;
- immutable reference and container rewriting;
- style, theme, and metadata reconciliation;
- child-template rejection;
- construction of the final flat `SpreadsheetDocument`.

The operation must not move into Core. No composition behavior belongs in renderer
selection, layout, ingestion, or an XLSX adapter. `_internal` must not import `api`.

## Implementation sequence

### 1. Fix the public contract in tests

Add `tests/test_spreadsheet_composition.py` and test only through `caxton.compose`:

- mapping insertion order determines section order;
- every child worksheet receives its section prefix;
- multi-worksheet documents retain local worksheet order;
- zero-worksheet children contribute nothing;
- an empty final composition raises the focused error;
- section names are validated and compared under `casefold()`;
- invalid child types raise `CaxtonTypeError` with section context;
- output worksheet collisions fail without invented suffixes;
- section-local cross-worksheet formulas and charts resolve to final names;
- unresolved external worksheet references fail before source consumption;
- unqualified column and table references remain unchanged;
- duplicate table names remain visible to structural validation;
- styles, themes, metadata, and templates follow the rules above;
- original documents remain unchanged;
- source objects are preserved by identity;
- composition and structural validation perform zero source reads.

Use a sentinel one-shot `DataSource` whose first iteration is observable and whose
second iteration raises. The composition tests must prove it is untouched.

### 2. Add typing and facade coverage

Add a fixture under `tests/types` proving that:

- `Mapping[str, SpreadsheetDocument]` is accepted;
- `compose()` returns `SpreadsheetDocument`;
- worksheet values, optional documents, and non-string keys are rejected statically;
- existing workbook-setting keyword types are preserved.

Export `compose` from `caxton.api` and the short `caxton` facade. Update the public
compatibility snapshot deliberately.

### 3. Implement section and rename planning

Create a private immutable plan containing:

- ordered sections;
- child worksheet identities;
- local-to-final worksheet-name maps;
- final-name ownership used for collision diagnostics.

Complete and validate the plan before rewriting semantic nodes. Planning must not call
full document validation and must not inspect data sources.

### 4. Implement explicit immutable visitors

Add explicit visitors for spreadsheet blocks and formula/reference nodes. Rebuild only
the containers on a path to a renamed reference. Reuse all unaffected immutable nodes
and every source object.

Visitors are private internal seams. Do not add a public visitor protocol, registry, or
generic `transform()` hook for this use case.

### 5. Reconcile workbook settings and construct the result

Apply style, theme, metadata, and template rules only after section planning and
reference validation succeed. Construct one final `SpreadsheetDocument` and return it
without invoking validation or compilation implicitly.

### 6. Verify compilation and rendering

Render fresh composed documents through both bundled create-new adapters where behavior
is intended to be shared. Prove:

- final worksheet order and names;
- representative literal cell output;
- cross-worksheet formula targets;
- chart source ranges;
- exactly one consumption of each one-shot source during rendering.

Use a fresh semantic document for each renderer invocation. No renderer-specific
composition branch should be introduced.

### 7. Update documentation and examples

- Update `ARCHITECTURE.md` to make named spreadsheet composition a delivered capability
  and document its fail-closed conflicts.
- Add the `compose()` docstring and generated reference entry.
- Extend `example/reusable` with a composed report flow instead of adding one example
  file per section.
- Add a guide example showing the mapping interface and the distinction between an
  empty document and a table with zero rows.
- Keep the README quick start unchanged unless composition makes it clearer rather than
  longer.
- Add a Towncrier feature fragment.

### 8. Run proportional checks

Run focused tests first, then repository gates:

```bash
.venv/bin/pytest tests/test_spreadsheet_composition.py -q
.venv/bin/pytest tests/test_formulas.py tests/test_spreadsheet_blocks.py \
    tests/test_spreadsheet_compiler.py tests/test_semantic_model.py -q
uv run --no-sync tox run -e py314
uv run --no-sync tox run -e pre-commit
uv run --no-sync tox run -e build
uv run --no-sync tox run -e docs
```

## Compatibility and rollout

The change is additive:

- `spreadsheet(*worksheets)` is unchanged;
- direct `SpreadsheetDocument` construction is unchanged;
- compiler and renderer contracts remain unchanged;
- existing documents do not acquire new behavior unless passed to `compose()`.

Do not add `Worksheet.__or__`, `SpreadsheetDocument.__or__`, `Worksheet.into()`,
`include()`, or nested-document support in `spreadsheet()` as aliases. Multiple
equivalent interfaces would dilute the seam and make conflict behavior harder to evolve
consistently.

## Rejected alternatives

### `spreadsheet(*documents)`

Flattening documents shortens tuple handling but does not give the implementation a
section identity. It therefore cannot reproduce the required worksheet prefixes or
rebase section-local references safely. The caller still owns the central complexity.

### `include(document, namespace=..., sheet_prefix=...)`

An include descriptor can represent the behavior, but it adds one wrapper per section
and does not improve the common call site. The ordered mapping carries the same required
information with less interface.

### `worksheet_1 | worksheet_2`

The operator cannot express section identity, workbook settings, or conflict policy.
Its first application changes the result type from `Worksheet` to
`SpreadsheetDocument`, requiring a second operator implementation for chaining. Caxton
also uses `|` for formula OR.

### `worksheet_1.into(worksheet_2, worksheet_3)`

The receiver looks like the destination even though it is the first input. Caxton
already uses `into` for template placement, and the method would put a multi-node
operation on a semantic leaf.

### Silent name deduplication

Inventing suffixes such as `(2)` can invalidate references or change what they resolve
to. Composition must either perform a complete section-local rebase or fail with
semantic context.

### Full lexical scopes in the initial version

Making worksheet, table, style, and metadata identities all lexical would require a new
hierarchical semantic model and contextual compiler resolution. That can become a
future capability if globally named tables and reconciled styles prove too restrictive.
It is not required to remove the current application-owned worksheet loop.

## Future extension

If independently reusable reports frequently collide on table or style names, introduce
true section scopes in the semantic model. At that point:

- local table references would resolve within their section first;
- the compiler would allocate backend-valid physical table names;
- local style definitions could shadow root definitions;
- explicit cross-section references would need a section-qualified reference form;
- the testing interface would expose section identity separately from output worksheet
  names.

Do not simulate lexical scope with increasingly complex string prefixes in the initial
composer. Add it only with concrete examples and update `ARCHITECTURE.md` before making
it public.

## Completion criteria

The feature is complete when:

- callers can compose an ordered mapping of named spreadsheet reports with one public
  function;
- the original application no longer allocates or mutates worksheet names;
- section-local worksheet references remain correct after naming;
- global table/style conflicts fail with stable semantic context;
- composition and structural validation perform zero source reads;
- both bundled create-new renderers produce the expected workbook;
- typing, compatibility, architecture, examples, public documentation, and changelog
  agree with the delivered behavior;
- no operator, fluent alias, include descriptor, builder graph, registry, or
  renderer-specific policy is introduced.
