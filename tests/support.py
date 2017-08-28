import re

from nolang.parser import get_parser, ParsingState, ParseError
from nolang.lexer import get_lexer
from nolang.bytecode import compile_bytecode
from nolang.interpreter import Interpreter
from nolang.compiler import compile_module
from nolang.importer import Importer
from nolang.objects.space import Space
from nolang.builtins.defaults import default_builtins


def reformat_code(body):
    bodylines = body.split("\n")
    cut = 0
    while bodylines[cut].strip(" ") == '':
        cut += 1
    bodylines = bodylines[cut:]
    m = re.match(" *", bodylines[0])
    lgt = len(m.group(0))
    newlines = []
    for i, line in enumerate(bodylines):
        if line.strip(" ") == "":
            continue
        if line[:lgt] != " " * lgt:
            raise Exception("bad formatting, line: %d\n%s" % (i, line))
        newlines.append(" " * 4 + line[lgt:])
    return "\n".join(newlines)


def reformat_expr(code):
    return "def main () {\n" + reformat_code(code) + "\n}"


class BaseTest(object):
    def setup_class(self):
        self.parser = get_parser()
        self.lexer = get_lexer()
        self.space = Space()
        self.space.setup_builtins(*default_builtins(self.space))
        self.interpreter = Interpreter()
        self.space.setup(self.interpreter)

    def compile(self, body):
        program = reformat_expr(body)
        ast = self.parse(program)
        imp = Importer(self.space)
        w_mod = compile_module(self.space, '<test>', 'self.test', program, ast,
                               imp)
        return compile_bytecode(ast.elements[0], program, w_mod)

    def parse(self, program):
        return self.parser.parse(self.lexer.lex('<test>', program),
                                 ParsingState('<test>', program))

    def interpret_expr(self, code):
        return self.interpret(reformat_expr(code))

    def interpret(self, code, args=None):
        source = reformat_code(code)
        ast = self.parse(source)
        imp = Importer(self.space)
        w_mod = compile_module(self.space, 'test', 'self.test', source, ast,
                               imp)
        w_mod.setup(self.space)
        if args is not None:
            args_w = [self.space.newlist([self.space.newtext(x) for x in args])]
        else:
            args_w = []
        return self.space.call_method(w_mod, 'main', args_w, [])

    def assert_expr_parse_error(self, code):
        try:
            value = self.interpret_expr(code)
        except ParseError:
            pass
        else:
            raise Exception("Incorrectly parsed %r as %r." % (code, value))

    def assert_parse_error(self, code):
        try:
            value = self.interpret(code)
        except ParseError:
            pass
        else:
            raise Exception("Incorrectly parsed %r as %r." % (code, value))
