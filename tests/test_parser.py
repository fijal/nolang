from nolang.lexer import get_lexer
from nolang.parser import get_parser, ParsingState, ParseError
from nolang import astnodes as ast

from tests.support import reformat_expr, reformat_code


class BaseTest(object):
    def setup_class(self):
        self.parser = get_parser()
        self.lexer = get_lexer()


class TestStringParser(BaseTest):
    def parse(self, expr):
        program = "def foo () { " + expr + "; }"
        ast = self.parser.parse(self.lexer.lex('test', program),
                                ParsingState('test', program))
        return ast.elements[0].body[0].expr.value

    def parse_bad(self, expr):
        try:
            value = self.parse(expr)
        except ParseError:
            pass
        except UnicodeDecodeError:
            pass
        except ValueError:
            pass
        else:
            raise Exception("Incorrectly parsed %r as %r." % (expr, value))

    def test_simple(self):
        assert self.parse('"foo"') == 'foo'

    def test_quote(self):
        assert self.parse(r'"foo\"bar"') == 'foo"bar'

    def test_quote_only(self):
        assert self.parse(r'"\""') == '"'

    def test_non_strings(self):
        self.parse_bad(r'"\"')
        self.parse_bad(r'"\\\"')

    def test_escaped_escapes(self):
        assert self.parse(r'"\\"') == '\\'
        assert self.parse(r'"\\\""') == '\\"'
        assert self.parse(r'"\\\"\\"') == '\\"\\'

    def test_simple_escapes(self):
        assert self.parse(r'"\a"') == '\a'
        assert self.parse(r'"\b"') == '\b'
        assert self.parse(r'"\f"') == '\f'
        assert self.parse(r'"\n"') == '\n'
        assert self.parse(r'"\r"') == '\r'
        assert self.parse(r'"\t"') == '\t'
        assert self.parse(r'"\v"') == '\v'
        assert self.parse(r'"\0"') == '\0'

    def test_unrecognised_escapes(self):
        assert self.parse(r'"\q"') == '\\q'
        assert self.parse(r'"\1"') == '\\1'

    def test_hex_escapes(self):
        assert self.parse(r'"\x20"') == ' '
        assert self.parse(r'"\xff"') == '\xc3\xbf'
        assert self.parse(r'"\u0020"') == ' '
        assert self.parse(r'"\u1020"') == '\xe1\x80\xa0'
        assert self.parse(r'"\uffff"') == '\xef\xbf\xbf'
        assert self.parse(r'"\u{0}"') == '\x00'
        assert self.parse(r'"\u{20}"') == ' '
        assert self.parse(r'"\u{000000020}"') == ' '
        assert self.parse(r'"\u{1020}"') == '\xe1\x80\xa0'
        assert self.parse(r'"\u{ffff}"') == '\xef\xbf\xbf'
        assert self.parse(r'"\u{10000}"') == '\xf0\x90\x80\x80'
        assert self.parse(r'"\u{102030}"') == '\xf4\x82\x80\xb0'
        assert self.parse(r'"\u{10ffff}"') == '\xf4\x8f\xbf\xbf'

    def test_bad_hex_excapes(self):
        self.parse_bad(r'"\xf"')
        self.parse_bad(r'"\xfq"')
        self.parse_bad(r'"\u000q"')
        self.parse_bad(r'"\u{}"')
        self.parse_bad(r'"\u{q}"')
        self.parse_bad(r'"\u{110000}"')

    def test_bad_utf8(self):
        self.parse_bad('"\xff"')
        self.parse_bad('"\xc0q"')
        self.parse_bad('"\xc0c0"')
        self.parse_bad('"\xdfq"')
        self.parse_bad('"\xe0q"')
        self.parse_bad('"\xe0\x80q"')
        self.parse_bad('"\xef\x80q"')
        self.parse_bad('"\xf0q"')
        self.parse_bad('"\xf0\x80q"')
        self.parse_bad('"\xf0\x80\x80q"')
        self.parse_bad('"\xf7\x80\x80q"')
        self.parse_bad('"\xf8"')

    def test_good_utf8(self):
        assert self.parse('"\x00"') == '\x00'
        assert self.parse('"\x7f"') == '\x7f'
        assert self.parse('"\xc2\x80"') == '\xc2\x80'
        assert self.parse('"\xc2\xbf"') == '\xc2\xbf'
        assert self.parse('"\xdf\xbf"') == '\xdf\xbf'
        assert self.parse('"\xe0\xbf\xbf"') == '\xe0\xbf\xbf'
        assert self.parse('"\xef\x80\x80"') == '\xef\x80\x80'
        assert self.parse('"\xf0\xbf\xbf\xbf"') == '\xf0\xbf\xbf\xbf'
        assert self.parse('"\xf4\x80\x80\xbf"') == '\xf4\x80\x80\xbf'


class TestExpressionParser(BaseTest):
    def parse(self, expr):
        program = "def foo () { " + expr + "; }"
        ast = self.parser.parse(self.lexer.lex('test', program),
                                ParsingState('test', program))
        return ast.elements[0].body[0].expr

    def test_add(self):
        assert self.parse('1 + 1') == ast.BinOp(
            '+', ast.Number(1), ast.Number(1), oppos=(15, 16))

    def test_various_kinds_of_calls(self):
        r = self.parse('x(1, 2, 3)')
        assert r == ast.Call(ast.Identifier('x'), [ast.Number(1), ast.Number(2),
            ast.Number(3)])
        r = self.parse('(1)(2)')
        assert r == ast.Call(ast.Number(1), [ast.Number(2)])


class TestParseFunctionBody(BaseTest):
    def parse(self, body):
        program = reformat_expr(body)
        ast = self.parser.parse(self.lexer.lex('test', program),
                                ParsingState('test', program))
        return ast.elements[0].body

    def test_var(self):
        r = self.parse('''
            var x;
            x = 3;
            x = x + 1;
            ''')
        assert r == [
            ast.VarDeclaration(['x']),
            ast.Assignment('x', ast.Number(3)),
            ast.Assignment('x', ast.BinOp('+', ast.Identifier('x'),
                                          ast.Number(1), oppos=(46, 47)))]

    def test_while_loop(self):
        r = self.parse('''
            var i, s;
            i = 0;
            while i < 10 {
                i = i + 1;
                s = s + i;
            }
            return s;
            ''')
        assert r == [
            ast.VarDeclaration(['i', 's']),
            ast.Assignment('i', ast.Number(0)),
            ast.While(
                ast.BinOp('<', ast.Identifier('i'), ast.Number(10), oppos=(51, 52)), [
                    ast.Assignment('i', ast.BinOp(
                        '+', ast.Identifier('i'), ast.Number(1), oppos=(72, 73))),
                    ast.Assignment('s', ast.BinOp(
                        '+', ast.Identifier('s'), ast.Identifier('i'), oppos=(91, 92)))]),
            ast.Return(ast.Identifier('s'))]


class TestFullProgram(BaseTest):

    def parse(self, code):
        program = reformat_code(code)
        return self.parser.parse(self.lexer.lex('test', program),
                                 ParsingState('test', program))

    def test_function_declaration(self):
        r = self.parse('''
            def foo() {
                var x;
            }

            def main() {
            }
            ''')
        expected = ast.Program([
            ast.Function('foo', [], [
                ast.VarDeclaration(['x'])
            ], lineno=1),
            ast.Function('main', [], [], lineno=4)
        ])
        assert r == expected

    def test_function_declaration_args(self):
        r = self.parse('''
            def foo(a0, a1) {
            }
            ''')
        expected = ast.Program([
            ast.Function('foo', ['a0', 'a1'], [
            ], lineno=1)
        ])
        assert r == expected

    def test_empty_try(self):
        try:
            self.parse('''
                def foo() {
                    try {
                    }
                }
            ''')
        except ParseError:
            pass
        else:
            raise Exception("DID NOT RAISE")

    def test_import_stuff(self):
        r = self.parse('''
            import foo
            import foo.bar
            import foo{a,b,c,d}
            import foo.bar{a,b,c};
            ''')
        expected = ast.Program([
            ast.Import(["foo"], []),
            ast.Import(["foo"], ["bar"]),
            ast.Import(["foo"], ["a", "b", "c", "d"]),
            ast.Import(["foo", "bar"], ["a", "b", 'c'])
        ])
        assert r == expected

    def test_ast_pos(self):
        program = self.parse('''
            def foo(n) {
                return n + 1;
            }

            def main() {
            }
            ''')
        assert program.getsrcpos() == (4, 67)
        [func_foo, func_main] = program.elements
        assert func_foo.getsrcpos() == (4, 44)
        assert func_main.getsrcpos() == (49, 67)
        [ret] = func_foo.body
        assert ret.getsrcpos() == (25, 38)
        binop = ret.expr
        assert binop.getsrcpos() == (32, 37)
        assert binop.left.getsrcpos() == (32, 33)
        assert binop.right.getsrcpos() == (36, 37)

    def test_ast_pos_except(self):
        program = self.parse('''
            def main() {
                try {
                    raise Exception("foo");
                } except A {
                    return 1;
                } except Exception {
                }
            }
            ''')
        [func_main] = program.elements
        assert func_main.getsrcpos() == (4, 154)
        [try_except] = func_main.body
        assert try_except.getsrcpos() == (25, 148)
        [except_A, except_Exception] = try_except.except_blocks
        assert except_A.getsrcpos() == (77, 119)
        assert except_Exception.getsrcpos() == (120, 148)
