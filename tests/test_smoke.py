import unittest

from cshape import (
	CField, CStmtBlock, CStmtDefFunc, CStmtReturn, CTypeFunction, CTypeIdentifier,
	CValueAdd, CValueIdentifier, render,
)


class SmokeTest(unittest.TestCase):
	def test_render_function(self):
		func = CStmtDefFunc(
			id='add',
			type=CTypeFunction(
				params=[CField(id='a', type=CTypeIdentifier('int')),
				        CField(id='b', type=CTypeIdentifier('int'))],
				to=CTypeIdentifier('int'),
			),
			block=CStmtBlock([
				CStmtReturn(CValueAdd(CValueIdentifier('a'), CValueIdentifier('b'))),
			]),
		)

		self.assertEqual(
			render(func).strip(),
			'int add(int a, int b) {\n\treturn a + b;\n}',
		)

	def test_render_is_reentrant(self):
		# render() must not leak indent/style state between independent calls
		named = CTypeIdentifier('int')
		render(named, style='modern')
		self.assertEqual(render(named, style='legacy'), 'int')

	def test_mark_shows_up_as_comment(self):
		v = CValueIdentifier('x')
		v.mark = 'debug-note'
		self.assertIn('/*debug-note*/', render(v))


if __name__ == '__main__':
	unittest.main()
