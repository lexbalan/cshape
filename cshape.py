

nl_symbol = "\n"
indent_symbol = "\t"
indent_level = 0



legacy_style = {
	'LINE_BREAK_BEFORE_STRUCT_BRACE': False,
	'LINE_BREAK_BEFORE_FUNC_BRACE': False,
	'LINE_BREAK_BEFORE_BLOCK_BRACE': False,
}

modern_style = {
	'LINE_BREAK_BEFORE_STRUCT_BRACE': True,
	'LINE_BREAK_BEFORE_FUNC_BRACE': True,
	'LINE_BREAK_BEFORE_BLOCK_BRACE': True,
}

styles = {
	'legacy': legacy_style,
	'modern': modern_style,
}


styleguide = legacy_style


def indent_up():
	global indent_level
	indent_level = indent_level + 1


def indent_down():
	global indent_level
	indent_level = indent_level - 1


def set_nl_symbol(x):
	global nl_symbol
	nl_symbol = x


def str_indent():
	global indent_level
	global indent_symbol
	return indent_symbol * indent_level


def str_nl_indent(nl=1):
	s = nl_symbol * nl
	if nl > 0:
		s += str_indent()
	return s


def render(node, style='legacy', indent='\t', newline='\n'):
	global indent_level, styleguide, nl_symbol, indent_symbol

	saved = (indent_level, styleguide, nl_symbol, indent_symbol)
	indent_level = 0
	styleguide = styles[style]
	nl_symbol = newline
	indent_symbol = indent

	try:
		# dispatch through the same wrapper each node type's parent would use
		# to print it, so mark/precedence handling is applied uniformly even
		# when rendering a node standalone (str(node) alone skips it — CType
		# doesn't even define __str__, only to_str())
		if isinstance(node, CType):
			return str_ctype(node)
		if isinstance(node, CValue):
			return str_cvalue(node)
		if isinstance(node, CStmt):
			return str_cstmt(node)
		return str_cdef(node)
	finally:
		indent_level, styleguide, nl_symbol, indent_symbol = saved


def wrap_if(x, cond):
	return "(%s)" % x if cond else x


def str_specs(specifiers):
	s = ''
	for opt in specifiers:
		s += opt + ' '
	return s


def with_space(s):
	if s != '':
		return ' ' + s
	return ''


def str_gcc_attributes(attributes):
	if attributes == None:
		return ''

	# Modest attribute -> GCC attribute
	gcc_attributes = {
		# attributes with no parameters
		'inline': 'always_inline',
		'noinline': 'noinline',
		'used': 'used',
		'unused': 'unused',
		'packed': 'packed',
		'deprecated': 'deprecated',  # can be with string parameter
		'weak': 'weak',

		# attributes with one parameter
		'section': 'section',
		'alignment': 'aligned',
		'optimize': 'optimize',
	}

	atts = []
	for anno_name in attributes:
		#print(":anno:" + anno_name)
		asset = attributes[anno_name]
		if anno_name in gcc_attributes:
			gcc_att_name = gcc_attributes[anno_name]

			att_arg = ""
			if asset != {}:
				att_arg = asset.asset
				if isinstance(att_arg, str):
					att_arg = '"%s"' % att_arg
				att_arg = '(' + str(att_arg) + ')'

			atts.append("%s%s" % (gcc_att_name, str(att_arg)))

	if atts != []:
		return "__attribute__((" + ", ".join(atts) + "))\n"

	return ""








class CField():
	def __init__(self, id, type, specifiers=None, nl=0):
		#assert(isinstance(type, CType))
		self.id = id
		self.type = type
		self.specifiers = specifiers if specifiers != None else []
		self.nl = nl



class CType():
	def __init__(self):
		self.mark = None
		pass

	def to_str(self, text=''):
		return "<type> " + text


class CTypeIdentifier(CType):
	def __init__(self, id, specifiers=None):
		assert(isinstance(id, str))
		super().__init__()
		self.id = id
		self.specifiers = specifiers if specifiers != None else []
		self.precedence = 0

	def to_str(self, text='', with_qualifiers=True):
		# "const int a"
		sstr = ''
		if with_qualifiers:
			# for: const, volatile, restrict
			sstr += str_specs(self.specifiers)
		return sstr + self.id + with_space(text)


class CTypePointer(CType):
	def __init__(self, to, specifiers=None):
		super().__init__()
		self.to = to
		self.specifiers = specifiers if specifiers != None else []
		self.precedence = 1

	def to_str(self, text='', with_qualifiers=True):
		# "*volatile p"
		sstr = '*'
		if with_qualifiers:
			sstr += str_specs(self.specifiers)
		sstr += text
		sstr = wrap_if(sstr, self.to.precedence > self.precedence)
		sstr = str_ctype(self.to, sstr)
		return sstr


class CTypeArray(CType):
	def __init__(self, item_type, size=None, specifiers=[]):
		super().__init__()
		item_type.specifiers = specifiers  # array specs is array item specs (!)
		self.item_type = item_type
		self.size = size
		self.specifiers = specifiers if specifiers != None else []
		self.precedence = 2

	def to_str(self, text='', with_qualifiers=True):
		text = text + '['
		if self.size != None:
			text += str_cvalue(self.size)
		text += ']'
		text = wrap_if(text, self.item_type.precedence > self.precedence)
		text = str_ctype(self.item_type, text)
		return text


class CTypeFunction(CType):
	def __init__(self, params, to, size=None, extra_args=False, specifiers=None):
		super().__init__()
		self.params = params
		self.to = to
		self.extra_args = extra_args
		self.specifiers = specifiers if specifiers != None else []
		self.precedence = 3

	def to_str(self, text='', with_qualifiers=True):
		params_text = ''
		i = 0
		params = self.params
		while i < len(params):
			param = params[i]
			p = str_ctype(param.type, text=param.id)
			if i > 0:
				params_text += ', ' + p
			else:
				params_text += p
			i = i + 1

		if self.extra_args:
			params_text += ', ...'

		if params_text == '':
			params_text = 'void'

		text = text + '(%s)' % params_text
		text = str_ctype(self.to, text)
		return text


class CTypeStruct(CType):
	def __init__(self, fields, tag, specifiers=None):
		super().__init__()
		self.fields = fields
		self.tag = tag
		self.specifiers = specifiers if specifiers != None else []
		self.precedence = 0

	def to_str(self, text='', with_qualifiers=True):
		nl_end = 0
		sstr = '%s' % (self.tag)
		if styleguide['LINE_BREAK_BEFORE_STRUCT_BRACE']:
			sstr += '\n'
		else:
			sstr += ' '
		sstr += '{'
		indent_up()
		i = 0
		nfields = len(self.fields)
		if nfields > 0:
			while i < nfields:
				field = self.fields[i]
				assert(isinstance(field, CField))
				if field.nl > 0:
					nl_end = 1

				if i > 0 and field.nl == 0:
					if self.fields[i-1].nl == 0:
						sstr += ' '

				sstr += str_nl_indent(field.nl)
				sstr += str_ctype(field.type, text=field.id) + ';'
				i = i + 1
		else:
			sstr += 'uint8_t __placeholder;'
		indent_down()
		sstr += str_nl_indent(nl_end) + '}' + with_space(text)
		return sstr




class CEnumItem():
	def __init__(self, id, value=None):
		assert(isinstance(id, str))
		assert(value == None or isinstance(value, CValue))
		self.id = id
		self.value = value
		self.nl = 1

	def __str__(self):
		sstr = self.id
		if self.value != None:
			sstr += ' = ' + str_cvalue(self.value)
		return sstr


class CTypeEnum(CType):
	def __init__(self, items, tag='', specifiers=None):
		super().__init__()
		self.items = items
		self.tag = tag
		self.specifiers = specifiers if specifiers != None else []
		self.precedence = 0

	def to_str(self, text='', with_qualifiers=True):
		nl_end = 0
		sstr = 'enum %s' % (self.tag)
		if styleguide['LINE_BREAK_BEFORE_STRUCT_BRACE']:
			sstr += '\n'
		else:
			sstr += ' '
		sstr += '{'
		indent_up()
		i = 0
		nitems = len(self.items)

		while i < nitems:
			item = self.items[i]
			assert(isinstance(item, CEnumItem))
			if item.nl > 0:
				nl_end = 1

			if i > 0 and item.nl == 0:
				if self.items[i-1].nl == 0:
					sstr += ' '

			sstr += str_nl_indent(item.nl)
			sstr += str(item)
			i = i + 1

		indent_down()
		sstr += str_nl_indent(nl_end) + '}' + with_space(text)
		return sstr




def str_ctype(t, text='', with_qualifiers=True):
	assert(t != None)
	assert(text != None)
	#assert(isinstance(t, dict))

	sstr = t.to_str(text, with_qualifiers=with_qualifiers)
	if t.mark:
		sstr = '/*%s*/' % t.mark + sstr
	return sstr









def print_list_items(_list, method):
	sstr = ''
	i = 0
	while i < len(_list):
		item = _list[i]
		if i > 0:
			sstr += ", "
		sstr += method(item)
		i += 1
	return sstr






valuePrecedenceMax = 15


class KV():
	def __init__(self, key, value, nl):
		self.key = key
		self.value = value
		self.nl = nl


class CValue():
	def __init__(self):
		self.mark = None


class CValueIdentifier(CValue):
	def __init__(self, id):
		super().__init__()
		self.id = id
		self.precedence = 15

	def __str__(self):
		return self.id




class CValueInteger(CValue):
	def __init__(self, number, as_hex=False, nsigns=0, suffix=''):
		super().__init__()
		assert(isinstance(number, int))
		assert(isinstance(as_hex, bool))
		self.precedence = 15
		self.number = number
		self.as_hex = as_hex
		self.nsigns = nsigns
		self.suffix = suffix

	def __str__(self):
		sstr = ''
		if self.as_hex:
			fmt = "0x%%0%dX" % self.nsigns
			sstr += (fmt % self.number)
		else:
			sstr += str(self.number)
		return sstr + self.suffix




def string_literal_prefix(width):
	if width > 16: return "U"
	if width > 8: return "u"
	return ""


class CValueString(CValue):
	def __init__(self, string, width):
		assert(isinstance(string, str))
		super().__init__()
		self.string = string
		self.width = width
		self.precedence = 15

	def __str__(self):
		return '%s"%s"' % (string_literal_prefix(self.width), self.string)


def code_to_char(cc):
	if cc < 0x20:
		if cc == 0x07: return "\\a"	# bell
		elif cc == 0x08: return "\\b"  # backspace
		elif cc == 0x09: return "\\t"  # horizontal tab
		elif cc == 0x0A: return "\\n"  # line feed
		elif cc == 0x0B: return "\\v"  # vertical tab
		elif cc == 0x0C: return "\\f"  # form feed
		elif cc == 0x0D: return "\\r"  # carriage return
		elif cc == 0x1B: return "\\e"  # escape
		else: return "\\x%X" % cc

	elif cc <= 0x7E :
		sym = chr(cc)
		if sym == '\\': return '\\\\'
		elif sym == '"': return '\\"'
		else: return sym

	elif cc != 0:
		return chr(cc)


class CValueChar(CValue):
	def __init__(self, cc, width=8):
		assert(isinstance(cc, int))
		super().__init__()
		self.char_code = cc
		self.width = width
		self.precedence = 15

	def __str__(self):
		return "%s'%s'" % (string_literal_prefix(self.width), code_to_char(self.char_code))



class CValueArray(CValue):
	def __init__(self, items):
		super().__init__()
		self.items = items
		self.precedence = 15

	def __str__(self):
		indent_up()
		s_items = '' #print_list_items(self.items, str_cvalue)

		i = 0
		while i < len(self.items):
			item = self.items[i]
			if i > 0:
				s_items += ","
				if item.nl == 0:
					s_items += " "
			s_items += str_nl_indent(item.nl)
			s_items += str_cvalue(item)
			i = i + 1
		indent_down()

		if s_items == '':
			s_items = '0'

		if len(self.items) > 0:
			nn = 1 if len(self.items) > 0 and self.items[0].nl > 0 else 0
			s_items += str_nl_indent(nn)

		return '{%s}' % s_items


class CValueStruct(CValue):
	def __init__(self, items):
		super().__init__()
		self.items = items
		self.precedence = 15

	def __str__(self):

		indent_up()

		s_items = ''
		i = 0
		item = None
		need_nl = 0
		while i < len(self.items):
			item = self.items[i]
			if i > 0:
				s_items += ","
				if item.nl == 0:
					s_items += " "
			s_items += str_nl_indent(item.nl)
			s_items += ".%s = %s" % (item.key, str_cvalue(item.value))
			i += 1

		indent_down()

		if item != None and item.nl > 0:
			need_nl = 1

		if s_items == '':
			s_items = '0'
		sstr = '{'
		sstr += s_items
		sstr += str_nl_indent(1 if len(self.items) > 0 and self.items[0].nl > 0 else 0)
		sstr += '}'
		return sstr





class CValueParen(CValue):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.precedence = 15

	def __str__(self):
		return '(%s)' % str_cvalue(self.value, ext_precedence=self.precedence)



class CValueCall(CValue):
	def __init__(self, left, args):
		assert(isinstance(left, CValue))
		assert(isinstance(args, list))
		super().__init__()
		self.left = left
		self.args = args
		self.precedence = 14

	def __str__(self):
		return '%s(%s)' % (str_cvalue(self.left, ext_precedence=self.precedence), print_list_items(self.args, str_cvalue))


class CValueFieldAccess(CValue):
	def __init__(self, left, field_id):
		assert(isinstance(field_id, str))
		assert(isinstance(left, CValue))
		super().__init__()
		self.left = left
		self.field_id = field_id
		self.precedence = 14

	def __str__(self):
		return '%s.%s' % (str_cvalue(self.left, ext_precedence=self.precedence), self.field_id)


class CValuePtrFieldAccess(CValue):
	def __init__(self, left, field_id):
		assert(isinstance(field_id, str))
		assert(isinstance(left, CValue))
		super().__init__()
		self.left = left
		self.field_id = field_id
		self.precedence = 14

	def __str__(self):
		return '%s->%s' % (str_cvalue(self.left, ext_precedence=self.precedence), self.field_id)


class CValueIndex(CValue):
	def __init__(self, left, index):
		assert(isinstance(left, CValue))
		assert(isinstance(index, CValue))
		super().__init__()
		self.left = left
		self.index = index
		self.precedence = 14

	def __str__(self):
		lstr = str_cvalue(self.left, ext_precedence=self.precedence)
		return '%s[%s]' % (lstr, str_cvalue(self.index))


class CValueCast(CValue):
	def __init__(self, type, value):
		assert(isinstance(type, CType))
		assert(isinstance(value, CValue))
		super().__init__()
		self.type = type
		self.value = value
		self.precedence = 13

	def __str__(self):
		vstr = str_cvalue(self.value, ext_precedence=self.precedence)
		return '(%s)%s' % (str_ctype(self.type, with_qualifiers=False), vstr)


class CValueReference(CValue):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.precedence = 13

	def __str__(self):
		return '&%s' % str_cvalue(self.value, ext_precedence=self.precedence)


class CValueDereference(CValue):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.precedence = 13

	def __str__(self):
		return '*%s' % str_cvalue(self.value, ext_precedence=self.precedence)


class CValueUnaryPlus(CValue):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.precedence = 13

	def __str__(self):
		return '+%s' % (str_cvalue(self.value, ext_precedence=self.precedence))


class CValueUnaryMinus(CValue):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.precedence = 13

	def __str__(self):
		return '-%s' % (str_cvalue(self.value, ext_precedence=self.precedence))


class CValueLogicalNot(CValue):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.precedence = 13

	def __str__(self):
		return '!%s' % (str_cvalue(self.value, ext_precedence=self.precedence))


class CValueBitwiseNot(CValue):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.precedence = 13

	def __str__(self):
		return '~%s' % (str_cvalue(self.value, ext_precedence=self.precedence))


class CValueSizeofValue(CValue):
	def __init__(self, ofvalue):
		assert(isinstance(ofvalue, CValue))
		super().__init__()
		self.ofvalue = ofvalue
		self.precedence = 13

	def __str__(self):
		return 'sizeof %s' % (str_cvalue(self.ofvalue))


class CValueSizeofType(CValue):
	def __init__(self, oftype):
		assert(isinstance(oftype, CType))
		super().__init__()
		self.oftype = oftype
		self.precedence = 13

	def __str__(self):
		return 'sizeof(%s)' % (str_ctype(self.oftype))


class CValueMul(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 12

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s * %s' % (lx, rx)


class CValueDiv(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 12

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s / %s' % (lx, rx)


class CValueMod(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 12

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s %% %s' % (lx, rx)


class CValueAdd(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 11

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s + %s' % (lx, rx)


class CValueSub(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 11

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s - %s' % (lx, rx)


class CValueShiftLeft(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 10

	def __str__(self):

		# -Wbitwise-op-parentheses supressing
		lprec = self.precedence
		if self.left.precedence == self.precedence + 1:
			lprec = valuePrecedenceMax
		rprec = self.precedence
		if self.right.precedence == self.precedence + 1:
			rprec = valuePrecedenceMax

		lx = str_cvalue(self.left, ext_precedence=lprec)
		rx = str_cvalue(self.right, ext_precedence=rprec)
		return '%s << %s' % (lx, rx)


class CValueShiftRight(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 10

	def __str__(self):

		# -Wbitwise-op-parentheses supressing
		lprec = self.precedence
		if self.left.precedence == self.precedence + 1:
			lprec = valuePrecedenceMax
		rprec = self.precedence
		if self.right.precedence == self.precedence + 1:
			rprec = valuePrecedenceMax

		lx = str_cvalue(self.left, ext_precedence=lprec)
		rx = str_cvalue(self.right, ext_precedence=rprec)
		return '%s >> %s' % (lx, rx)


class CValueLt(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 9

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s < %s' % (lx, rx)


class CValueGt(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 9

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s > %s' % (lx, rx)


class CValueLE(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 9

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s <= %s' % (lx, rx)


class CValueGE(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 9

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s >= %s' % (lx, rx)


class CValueEq(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 8

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s == %s' % (lx, rx)


class CValueNe(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 8

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s != %s' % (lx, rx)


# -Wbitwise-op-parentheses supressing
# компилятор си любит ругаться на безобидные логические выражения, и сдвиги,
# все дело в том что люди часто ошибаются и поэтому, на всякий случай, компилятор просит еще и скобки
def select_prio_plus(sp, xp, n=0):
	if xp > sp and xp <= sp + n:
		return valuePrecedenceMax
	return sp


class CValueBitwiseAnd(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 7

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s & %s' % (lx, rx)


class CValueBitwiseXor(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 6

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=select_prio_plus(self.precedence, self.left.precedence, n=1))
		rx = str_cvalue(self.right, ext_precedence=select_prio_plus(self.precedence, self.right.precedence, n=1))
		return '%s ^ %s' % (lx, rx)


class CValueBitwiseOr(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 5

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=select_prio_plus(self.precedence, self.left.precedence, n=2))
		rx = str_cvalue(self.right, ext_precedence=select_prio_plus(self.precedence, self.right.precedence, n=2))
		return '%s | %s' % (lx, rx)


class CValueLogicalAnd(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 4

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return '%s && %s' % (lx, rx)


class CValueLogicalOr(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 3

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=select_prio_plus(self.precedence, self.left.precedence, n=1))
		rx = str_cvalue(self.right, ext_precedence=select_prio_plus(self.precedence, self.right.precedence, n=1))
		return '%s || %s' % (lx, rx)



class CValueVaStart(CValue):
	def __init__(self, va_list, last_param):
		assert(isinstance(va_list, CValue))
		assert(isinstance(last_param, CValue))
		super().__init__()
		self.va_list = va_list
		self.last_param = last_param
		self.precedence = 14

	def __str__(self):
		return 'va_start(%s, %s)' % (str_cvalue(self.va_list), str_cvalue(self.last_param))


class CValueVaArg(CValue):
	def __init__(self, va_list, xtype):
		assert(isinstance(va_list, CValue))
		assert(isinstance(xtype, CType))
		super().__init__()
		self.va_list = va_list
		self.xtype = xtype
		self.precedence = 14

	def __str__(self):
		return 'va_arg(%s, %s)' % (str_cvalue(self.va_list), str_ctype(self.xtype))


class CValueVaEnd(CValue):
	def __init__(self, va_list):
		assert(isinstance(va_list, CValue))
		super().__init__()
		self.va_list = va_list
		self.precedence = 14

	def __str__(self):
		return 'va_end(%s)' % (str_cvalue(self.va_list))


class CValueVaCopy(CValue):
	def __init__(self, va_dst, va_src):
		assert(isinstance(va_dst, CValue))
		assert(isinstance(va_src, CValue))
		super().__init__()
		self.va_dst = va_dst
		self.va_src = va_src
		self.precedence = 14

	def __str__(self):
		return 'va_copy(%s, %s)' % (str_cvalue(self.va_dst), str_cvalue(self.va_src))


# string concat
class CValueStringConcat(CValue):
	def __init__(self, left, right):
		assert(isinstance(left, CValue))
		assert(isinstance(right, CValue))
		super().__init__()
		self.left = left
		self.right = right
		self.precedence = 15

	def __str__(self):
		lx = str_cvalue(self.left, ext_precedence=self.precedence)
		rx = str_cvalue(self.right, ext_precedence=self.precedence)
		return lx + ' ' + rx



def str_cvalue(v, ext_precedence=0):
	assert(isinstance(v, CValue))
	y = str(v)
	sstr = wrap_if(y, (v.precedence < ext_precedence) or v.mark and (v.precedence < valuePrecedenceMax))
	if v.mark != None:
		sstr = '/*%s*/' % v.mark + sstr
	return sstr





def str_cstmt(x):
	assert(x != None)
	sstr = ''
	#if x.comment != None:
	#	sstr += str_nl_indent(x.comment.nl)
	#	print_comment(x.comment)
	#sstr += str_nl_indent(x.nl)
	sstr += str(x)
	if x.mark != None:
		sstr = '/*%s*/' % x.mark + sstr
	return sstr


class CStmt():
	def __init__(self):
		self.comment = None
		self.nl = 1
		self.mark = None
		pass


class CStmtLineComment(CStmt):
	def __init__(self, lines):
		assert(isinstance(lines, list))
		super().__init__()
		self.lines = lines
		self.nl = 1

	def __str__(self):
		sstr = ''
		sstr += str_nl_indent(self.nl)
		n = len(self.lines)
		i = 0
		while i < n:
			line = self.lines[i]
			sstr += "//%s" % line
			i = i + 1
			if i < n:
				sstr += str_nl_indent()
		return sstr


class CStmtBlockComment(CStmt):
	def __init__(self, text):
		assert(isinstance(text, str))
		super().__init__()
		self.text = text
		self.nl = 1

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "/*%s*/" % self.text
		return sstr


class CStmtBlock(CStmt):
	def __init__(self, stmts):
		assert(isinstance(stmts, list))
		super().__init__()
		self.nl = 0
		self.stmts = stmts

	def __str__(self):
		sstr = ''
		sstr += "{"
		nl_end_e = 1
		indent_up()
		for stmt in self.stmts:
			sstr += str_cstmt(stmt)
		indent_down()
		sstr += str_nl_indent(nl=nl_end_e)
		sstr += "}"
		return sstr


class CStmtExpr(CStmt):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value
		self.nl = 1

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		return sstr + str_cvalue(self.value) + ';'


class CStmtAssignment(CStmt):
	def __init__(self, lvalue, rvalue):
		assert(isinstance(lvalue, CValue))
		assert(isinstance(rvalue, CValue))
		super().__init__()
		self.lvalue = lvalue
		self.rvalue = rvalue

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		return sstr + "%s = %s;" % (str_cvalue(self.lvalue), str_cvalue(self.rvalue))


class CStmtIncrement(CStmt):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value

	def __str__(self):
		return str_nl_indent(self.nl) + "++%s;" % str_cvalue(self.value)


class CStmtDecrement(CStmt):
	def __init__(self, value):
		assert(isinstance(value, CValue))
		super().__init__()
		self.value = value

	def __str__(self):
		return str_nl_indent(self.nl) + "--%s;" % str_cvalue(self.value)


class CStmtDeclType(CStmt):
	def __init__(self, type, attributes=None):
		assert(isinstance(type, CTypeIdentifier))
		super().__init__()
		self.type = type
		self.attributes = attributes

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += str_gcc_attributes(self.attributes)
		sstr += str_ctype(self.type) + ';'
		return sstr


class CStmtDefType(CStmt):
	def __init__(self, id, type, attributes=None):
		assert(isinstance(id, str))
		assert(isinstance(type, CType))
		super().__init__()
		self.id = id
		self.type = type
		self.attributes = attributes

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += str_gcc_attributes(self.attributes)
		sstr += 'typedef %s;' % self.type.to_str(text=self.id)
		return sstr



class CStmtDefVar(CStmt):
	def __init__(self, id, type, initializer=None, storage_class='', attributes=None):
		assert(isinstance(id, str))
		assert(isinstance(type, CType))
		if initializer != None:
			assert(isinstance(initializer, CValue))
		super().__init__()
		self.id = id
		self.type = type
		self.storage = storage_class
		self.initializer = initializer
		self.attributes = attributes

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += str_gcc_attributes(self.attributes)
		if self.storage not in (None, ''):
			sstr += self.storage + ' '
		#mass
		sstr += str_ctype(self.type, text=self.id)
		if self.initializer != None:
			sstr += ' = %s' % str_cvalue(self.initializer)
		return sstr + ';'



class CStmtDefFunc(CStmt):
	def __init__(self, id, type, block, storage_class='', attributes=None):
		assert(isinstance(id, str))
		assert(isinstance(type, CType))
		assert(isinstance(block, CStmtBlock))
		#if init_value != None:
		#	assert(isinstance(init_value, CValue))
		super().__init__()
		self.id = id
		self.type = type
		self.storage = storage_class
		self.block = block
		self.attributes = attributes
		self.nl = 2

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += str_gcc_attributes(self.attributes)
		if self.storage not in (None, ''):
			sstr += self.storage + ' '
		sstr += self.type.to_str(text=self.id)

		if styleguide['LINE_BREAK_BEFORE_FUNC_BRACE']:
			sstr += str_nl_indent()
		else:
			sstr += ' '

		sstr += str_cstmt(self.block)
		return sstr



class CStmtIf(CStmt):
	def __init__(self, condition, then_block, else_block):
		assert(isinstance(condition, CValue))
		assert(isinstance(then_block, CStmtBlock))
		if else_block:
			assert((isinstance(else_block, CStmtBlock) or isinstance(else_block, CStmtIf)))
		super().__init__()
		self.condition = condition
		self.then_block = then_block
		self.else_block = else_block

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "if (%s)" % str_cvalue(self.condition)
		if styleguide['LINE_BREAK_BEFORE_BLOCK_BRACE']:
			sstr += str_nl_indent()
		else:
			sstr += ' '
		sstr += str(self.then_block)
		if self.else_block != None:
			if styleguide['LINE_BREAK_BEFORE_BLOCK_BRACE']:
				sstr += str_nl_indent()
			else:
				sstr += ' '
			sstr += 'else'
			if isinstance(self.else_block, CStmtBlock) and styleguide['LINE_BREAK_BEFORE_BLOCK_BRACE']:
				sstr += str_nl_indent()
			else:
				sstr += ' '
			sstr += str(self.else_block)
		return sstr


class CStmtWhile(CStmt):
	def __init__(self, condition, block):
		assert(isinstance(condition, CValue))
		assert(isinstance(block, CStmtBlock))
		super().__init__()
		self.condition = condition
		self.block = block

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "while (%s)" % str_cvalue(self.condition)
		if styleguide['LINE_BREAK_BEFORE_BLOCK_BRACE']:
			sstr += str_nl_indent()
		else:
			sstr += ' '
		sstr += str(self.block)
		return sstr


class CStmtReturn(CStmt):
	def __init__(self, return_value):
		if return_value != None:
			assert(isinstance(return_value, CValue))
		super().__init__()
		self.return_value = return_value

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += 'return'
		if self.return_value != None:
			sstr += ' ' + str_cvalue(self.return_value)
		return sstr + ";"


class CStmtBreak(CStmt):
	def __init__(self):
		super().__init__()
		pass

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "break;"
		return sstr


class CStmtContinue(CStmt):
	def __init__(self):
		super().__init__()
		pass

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "continue;"
		return sstr


#__asm__ volatile (
#	"assembly code template"
#	: output operands /* optional */
#	: input operands /* optional */
#	: clobbered registers/memory /* optional */
#);

class CStmtInlineAsm(CStmt):
	def __init__(self, text, outputs, inputs, clobbers):
		super().__init__()
		assert(isinstance(text, str))
		self.text = text
		self.outputs = outputs
		self.inputs = inputs
		self.clobbers = clobbers


	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "__asm__ volatile ("
		sstr += '"%s" ' % self.text.replace('\n', '\\n\\\n')

		sstr += ":"
		items = ("%s (%s)" % (str(xx[0]), str(xx[1])) for xx in self.outputs)
		if len(self.outputs) > 0:
			sstr += " " + ", ".join(items)

		if self.outputs != []:
			sstr += " "
		sstr += ":"
		items = ("%s (%s)" % (str(xx[0]), str(xx[1])) for xx in self.inputs)
		if len(self.inputs) > 0:
			sstr += " " + ", ".join(items)

		if self.inputs != []:
			sstr += " "
		sstr += ":"
		items = (str(xx) for xx in self.clobbers)
		if len(self.clobbers) > 0:
			sstr += " " + ", ".join(items)

		sstr += ");"
		return sstr



class CRawText(CStmt):
	def __init__(self, text):
		super().__init__()
		self.text = text
		pass

	def __str__(self):
		return self.text


class CMacroDef():
	def __init__(self, id, text=None):
		assert(isinstance(id, str))
		if text:
			assert(isinstance(text, str))
		self.nl = 1  #!!! (because it is not CStmt...)
		super().__init__()
		self.id = id
		self.text = text
		self.mark = None

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "#define %s" % (self.id)
		if self.text:
			sstr += ' ' + self.text
		return sstr


class CMacroDefValue():
	def __init__(self, id, value):
		assert(isinstance(id, str))
		assert(isinstance(value, CValue))
		self.nl = 1  #!!! (because it is not CStmt...)
		super().__init__()
		self.id = id
		self.value = value
		self.mark = None

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		set_nl_symbol(" \\\n")
		sstr += "#define %s %s" % (self.id, str_cvalue(self.value, ext_precedence=valuePrecedenceMax))
		set_nl_symbol("\n")
		return sstr


class CMacroUndef():
	def __init__(self, text):
		assert(isinstance(text, str))
		self.nl = 1  #!!! (because it is not CStmt...)
		super().__init__()
		self.text = text
		self.mark = None

	def __str__(self):
		sstr = str_nl_indent(self.nl)
		sstr += "#undef %s" % (self.text)
		return sstr


class CInclude():
	def __init__(self, text, is_system):
		assert(isinstance(text, str))
		assert(isinstance(is_system, bool))
		self.nl = 1  #!!! (because it is not CStmt...)
		super().__init__()
		self.text = text
		self.is_system = is_system
		self.mark = None

	def __str__(self):
		#sstr = str_nl_indent(self.nl)
		if self.is_system:
			return "\n#include <%s>" % self.text
		return "\n#include \"%s\"" % self.text


def str_cdef(x):
	prefix = '/*%s*/' % x.mark if x.mark else ''
	return prefix + str(x)


# pairs = ("macro text", [<defs>])
class CConditionalRegion():
	def __init__(self, pairs, _else=None):
		self.pairs = pairs
		self._else = _else
		self.mark = None

	def __str__(self):
		sstr = ''
		directive = '#if'
		for pair in self.pairs:
#			if directive == '#if':
#				ss = pair[0].split('()')
#				print(ss)
			sstr += "\n%s %s" % (directive, pair[0])
#			if len(pair[1]) > 5:
#				sstr += "\n"
			for xd in pair[1]:
				#print(":" + str(xd))
				sstr += str_cdef(xd)
#			if len(pair[1]) > 5:
#				sstr += "\n"
			directive = '#elif'

		if self._else != None:
			sstr += '\n#else'
#			if len(self._else) > 5:
#				sstr += "\n"
			for xd in self._else:
				sstr += str_cdef(xd)
#			if len(self._else) > 5:
#				sstr += "\n"
		sstr += "\n#endif"
		#sstr = sstr.replace("#if defined", "#ifdef")
		#sstr = sstr.replace("#if !defined", "#ifndef")
		return sstr






