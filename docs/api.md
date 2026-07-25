# cshape API

This document describes the current public API exposed by `cshape.py`.

`cshape` is a small dependency-free C AST builder and printer for Python. You construct nodes from three main families:

- `CType*` for C types
- `CValue*` for expressions and literals
- `CStmt*` for statements and definitions

Then render them with `render(node, ...)`.

## Rendering

```python
render(node, style='legacy', indent='\t', newline='\n')
```

- `node` can be a type node, value node, statement node, or top-level preprocessor node.
- `style` can be `legacy` or `modern`.
- `indent` controls one indentation unit.
- `newline` controls the newline sequence.

`render()` preserves mark comments and operator precedence handling. When rendering a standalone statement or definition, remember that some nodes intentionally include their own leading blank lines.

## Core Conventions

- Most nodes expose a `.mark` field. If set, it is emitted as a `/*mark*/` comment before that node.
- `CField` and many type/value/statement nodes use `id` for C identifiers.
- `specifiers` is used for C qualifiers and similar modifier tokens.
- `CStmtBlock` owns a list of nested statement nodes.

## Example

```python
from cshape import *

func = CStmtDefFunc(
	id="add",
	type=CTypeFunction(
		params=[
			CField(id="a", type=CTypeIdentifier("int")),
			CField(id="b", type=CTypeIdentifier("int")),
		],
		to=CTypeIdentifier("int"),
	),
	block=CStmtBlock([
		CStmtReturn(
			CValueAdd(
				CValueIdentifier("a"),
				CValueIdentifier("b"),
			)
		),
	]),
)

print(render(func).strip())
```

## Types

### `CField`

```python
CField(id, type, specifiers=None, nl=0)
```

- Field or parameter declaration fragment.
- `nl` controls blank-line behavior inside structs and similar grouped output.

### `CType`

Base class for type nodes.

### `CTypeIdentifier`

```python
CTypeIdentifier(id, specifiers=None)
```

- Named type such as `int`, `size_t`, or a typedef name.

### `CTypePointer`

```python
CTypePointer(to, specifiers=None)
```

- Pointer type.
- `to` is another `CType`.

### `CTypeArray`

```python
CTypeArray(item_type, size=None, specifiers=[])
```

- Array type.
- `item_type` is the element type.
- `size` is a `CValue` or `None`.

### `CTypeFunction`

```python
CTypeFunction(params, to, size=None, extra_args=False, specifiers=None)
```

- Function type.
- `params` is a list of `CField`.
- `to` is the return type.
- `extra_args=True` emits variadic `...`.
- `size` is currently unused by the implementation.

### `CTypeStruct`

```python
CTypeStruct(fields, tag, specifiers=None)
```

- Struct or union-like body printer, depending on the `tag` text you provide.
- `fields` is a list of `CField`.

### `CEnumItem`

```python
CEnumItem(id, value=None)
```

- Single enum item.
- `value` is a `CValue` or `None`.

### `CTypeEnum`

```python
CTypeEnum(items, tag='', specifiers=None)
```

- Enum type definition.
- `items` is a list of `CEnumItem`.

## Values and Expressions

### Base and literals

```python
CValue()
CValueIdentifier(id)
CValueInteger(number, as_hex=False, nsigns=0, suffix='')
CValueString(string, width)
CValueChar(cc, width=8)
CValueArray(items)
CValueStruct(items)
CValueParen(value)
```

- `CValueArray` prints array literals like `{1, 2}`.
- `CValueStruct` prints designated initializers; items are usually `KV(key, value, nl)` objects.
- `CValueParen` forces explicit parentheses.

### Access, calls, casts, unary

```python
CValueCall(left, args)
CValueFieldAccess(left, field_id)
CValuePtrFieldAccess(left, field_id)
CValueIndex(left, index)
CValueCast(type, value)
CValueReference(value)
CValueDereference(value)
CValueUnaryPlus(value)
CValueUnaryMinus(value)
CValueLogicalNot(value)
CValueBitwiseNot(value)
CValueSizeofValue(ofvalue)
CValueSizeofType(oftype)
```

### Binary arithmetic and comparisons

```python
CValueMul(left, right)
CValueDiv(left, right)
CValueMod(left, right)
CValueAdd(left, right)
CValueSub(left, right)
CValueShiftLeft(left, right)
CValueShiftRight(left, right)
CValueLt(left, right)
CValueGt(left, right)
CValueLE(left, right)
CValueGE(left, right)
CValueEq(left, right)
CValueNe(left, right)
```

### Bitwise and logical

```python
CValueBitwiseAnd(left, right)
CValueBitwiseXor(left, right)
CValueBitwiseOr(left, right)
CValueLogicalAnd(left, right)
CValueLogicalOr(left, right)
```

The printer includes extra precedence handling for some bitwise and shift combinations to keep GCC/Clang warnings quiet.

### Varargs and string concatenation

```python
CValueVaStart(va_list, last_param)
CValueVaArg(va_list, xtype)
CValueVaEnd(va_list)
CValueVaCopy(va_dst, va_src)
CValueStringConcat(left, right)
```

- `CValueStringConcat` prints adjacent string literals or tokens separated by a single space.

### Helper value container

```python
KV(key, value, nl)
```

- Small helper used by `CValueStruct` for designated initializer entries.

## Statements and Definitions

### Statement base and comments

```python
CStmt()
CStmtLineComment(lines)
CStmtBlockComment(text)
CStmtBlock(stmts)
```

### Expression-like statements

```python
CStmtExpr(value)
CStmtAssignment(lvalue, rvalue)
CStmtIncrement(value)
CStmtDecrement(value)
```

### Declarations and definitions

```python
CStmtDeclType(type, attributes=None)
CStmtDefType(id, type, attributes=None)
CStmtDefVar(id, type, initializer=None, storage_class='', attributes=None)
CStmtDefFunc(id, type, block, storage_class='', attributes=None)
```

- `CStmtDeclType` expects a `CTypeIdentifier`.
- `CStmtDefType` emits a `typedef`.
- `CStmtDefVar` emits a variable definition, optionally with initializer.
- `CStmtDefFunc` emits a full function definition with body.

### Control flow

```python
CStmtIf(condition, then_block, else_block)
CStmtWhile(condition, block)
CStmtReturn(return_value)
CStmtBreak()
CStmtContinue()
```

- `else_block` may be `None`, another `CStmtBlock`, or a nested `CStmtIf`.
- `return_value` may be `None` for plain `return;`.

### Inline asm and raw insertion

```python
CStmtInlineAsm(text, outputs, inputs, clobbers)
CRawText(text)
```

- `CRawText` inserts verbatim text into the output.

## Preprocessor and Top-Level Nodes

```python
CMacroDef(id, text=None)
CMacroDefValue(id, value)
CMacroUndef(text)
CInclude(text, is_system)
CConditionalRegion(pairs, _else=None)
```

- `CMacroDef` emits `#define NAME` or `#define NAME text`.
- `CMacroDefValue` emits a `#define` whose body is built from a `CValue`.
- `CInclude(text, is_system=True)` emits `<...>`; otherwise it emits `"..."`.
- `CConditionalRegion` builds `#if` / `#elif` / `#else` / `#endif` regions.
- `pairs` should be a sequence of `(condition_text, defs)` tuples, where `defs` is a list of top-level nodes.

## Attributes

Some declaration and definition nodes accept an `attributes` mapping consumed by the internal GCC attribute printer. Currently recognized keys include:

- `inline`
- `noinline`
- `used`
- `unused`
- `packed`
- `deprecated`
- `weak`
- `section`
- `alignment`
- `optimize`

These are emitted as GCC-style `__attribute__((...))` annotations.

## Notes

- The module is a printer, not a parser or type checker.
- State such as indentation and style is reset per `render()` call.
- Most constructors assert expected input node types rather than silently coercing values.