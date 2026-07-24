import unittest

from cshape import (
	CField, CStmtBlock, CStmtDefFunc, CStmtReturn, CTypeFunc, CTypeNamed,
	CValueAdd, CValueNamed, render,
)


class SmokeTest(unittest.TestCase):
	def test_render_function(self):
		func = CStmtDefFunc(
			id_str='add',
			type=CTypeFunc(
				params=[CField(id_str='a', type=CTypeNamed('int')),
				        CField(id_str='b', type=CTypeNamed('int'))],
				to=CTypeNamed('int'),
			),
			block=CStmtBlock([
				CStmtReturn(CValueAdd(CValueNamed('a'), CValueNamed('b'))),
			]),
		)

		self.assertEqual(
			render(func).strip(),
			'int add(int a, int b) {\n\treturn a + b;\n}',
		)

	def test_render_is_reentrant(self):
		# render() must not leak indent/style state between independent calls
		named = CTypeNamed('int')
		render(named, style='modern')
		self.assertEqual(render(named, style='legacy'), 'int')

	def test_mark_shows_up_as_comment(self):
		v = CValueNamed('x')
		v.mark = 'debug-note'
		self.assertIn('/*debug-note*/', render(v))


if __name__ == '__main__':
	unittest.main()
