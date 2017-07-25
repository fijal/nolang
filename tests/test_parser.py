
from nolang.lexer import get_lexer
from nolang.parser import get_parser, ParsingState
from nolang import astnodes as ast

from tests.support import reformat_expr, reformat_code


class BaseTest(object):
    def setup_class(self):
        self.parser = get_parser()
        self.lexer = get_lexer()

class TestExpressionParser(BaseTest):
    def parse(self, expr):
        program = "def foo () { " + expr + "; }"
        ast = self.parser.parse(self.lexer.lex(program), ParsingState(program))
        return ast.elements[0].body[0].expr

    def test_add(self):
        assert self.parse('1 + 1') == ast.BinOp('+', ast.Number(1), ast.Number(1))

    def test_various_kinds_of_calls(self):
        r = self.parse('x(1, 2, 3)')
        assert r == ast.Call(ast.Identifier('x'), [ast.Number(1), ast.Number(2),
            ast.Number(3)])
        r = self.parse('(1)(2)')
        assert r == ast.Call(ast.Number(1), [ast.Number(2)])


class TestParseFunctionBody(BaseTest):
    def parse(self, body):
        program = reformat_expr(body)
        ast = self.parser.parse(self.lexer.lex(program), ParsingState(program))
        return ast.elements[0].body

    def test_var(self):
        r = self.parse('''
            var x;
            x = 3;
            x = x + 1;
            ''')
        assert r == [ast.VarDeclaration(['x']), ast.Assignment('x',
                 ast.Number(3)), ast.Assignment('x', ast.BinOp('+',
                    ast.Identifier('x'), ast.Number(1)))]

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
        assert r == [ast.VarDeclaration(['i', 's']),
                     ast.Assignment('i', ast.Number(0)),
                     ast.While(ast.BinOp('<', ast.Identifier('i'),
                        ast.Number(10)), [
                          ast.Assignment('i', ast.BinOp('+',
                            ast.Identifier('i'), ast.Number(1))),
                          ast.Assignment('s', ast.BinOp('+',
                            ast.Identifier('s'), ast.Identifier('i')))]),
                     ast.Return(ast.Identifier('s'))]

    def test_implicit_return(self):
        r = self.parse('''
            var i, s;
            i = 0;
            while i < 10 {
                i = i + 1;
                s = s + i;
            }
            s
            ''')
        assert r == [ast.VarDeclaration(['i', 's']),
                     ast.Assignment('i', ast.Number(0)),
                     ast.While(ast.BinOp('<', ast.Identifier('i'),
                        ast.Number(10)), [
                          ast.Assignment('i', ast.BinOp('+',
                            ast.Identifier('i'), ast.Number(1))),
                          ast.Assignment('s', ast.BinOp('+',
                            ast.Identifier('s'), ast.Identifier('i')))]),
                     ast.Return(ast.Identifier('s'))]


class TestFullProgram(BaseTest):

    def parse(self, code):
        program = reformat_code(code)
        return self.parser.parse(self.lexer.lex(program), ParsingState(program))

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
                ]),
            ast.Function('main', [], [])
            ])
        assert r == expected

    def test_function_declaration_args(self):
        r = self.parse('''
            def foo(a0, a1) {
            }
            ''')
        expected = ast.Program([
            ast.Function('foo', ['a0', 'a1'], [
                ])
            ])
        assert r == expected
