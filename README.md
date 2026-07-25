# cshape

A dependency-free C AST + printer for Python: build a tree and get C11
source back. No parsing, no dependencies beyond the standard library —
just `CType*` / `CValue*` / `CStmt*` nodes and a `render()` function that
turns them into text.

Originally the C backend's printer for the Modest compiler, split out
because it doesn't know anything about Modest — it only knows about C.

## Install

```sh
pip install cshape
```

## Example

```python
from cshape import *

func = CStmtDefFunc(
	id="add",
	type=CTypeFunction(
		params=[CField(id="a", type=CTypeIdentifier("int")),
		        CField(id="b", type=CTypeIdentifier("int"))],
		to=CTypeIdentifier("int"),
	),
	block=CStmtBlock([
		CStmtReturn(CValueAdd(CValueIdentifier("a"), CValueIdentifier("b"))),
	]),
)

print(render(func).strip())
```

```c
int add(int a, int b) {
	return a + b;
}
```

(`render()` returns the node's own leading blank lines too — `CStmtDefFunc`
starts with a blank line by default, so `.strip()` if you're printing a
single node standalone rather than concatenating several.)

## What it covers

- Types: named types, pointers, arrays, function types, structs/unions, enums
- Values: the full C11 expression grammar with correct operator precedence
  and parenthesization (including the extra parens GCC/Clang warn about for
  mixed bitwise/shift expressions)
- Statements: blocks, if/while, return, break/continue, inline asm, raw
  inserts
- Preprocessor: `#define`, `#undef`, `#include`, `#if`/`#elif`/`#else`/`#endif`
  regions
- Two brace styles (`legacy` — K&R-ish, `modern` — Allman-ish), configurable
  via `render(node, style=...)`
- A `.mark` field on every node: set it to any string and it shows up as a
  `/*mark*/` comment right before that node in the output — useful for
  tracing which part of your own compiler/generator produced which bit of C

## What it doesn't do

No parsing, no semantic analysis, no type checking. It's a printer, not a
compiler frontend — you build the tree, it hands you back text.

## License

MIT
