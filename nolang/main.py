
""" Execute:

nolang-c <program.no>
"""

import os
import sys

from nolang.interpreter import Interpreter
from nolang.parser import get_parser, ParsingState, ParseError
from nolang.compiler import compile_module
from nolang.builtins.defaults import default_builtins
from nolang.lexer import get_lexer
from nolang.frameobject import format_traceback
from nolang.importer import Importer
from nolang.objects.space import Space
from nolang.error import AppError


def dirname(p):
    """Returns the directory component of a pathname"""
    i = p.rfind(os.path.sep) + 1
    assert i >= 0
    head = p[:i]
    if head and head != os.path.sep * len(head):
        head = head.rstrip(os.path.sep)
    return head


def path_split(p):
    """Split a pathname.  Returns tuple "(head, tail)" where "tail" is
    everything after the final slash.  Either part may be empty."""
    i = p.rfind('/') + 1
    assert i >= 0
    head, tail = p[:i], p[i:]
    if head and head != '/' * len(head):
        head = head.rstrip('/')
    return head, tail


def main(argv):
    if len(argv) != 2:
        print __doc__
        return 1
    return run_code(argv[1])


parser = get_parser()
lexer = get_lexer()
space = Space()
space.setup_builtins(*default_builtins(space))


def format_parser_error(pe):
    print "Error parsing input file %s, line %d: %s" % (pe.filename, pe.lineno,
        pe.msg)
    print "  " + pe.line
    print "  " + " " * pe.start_colno + "^" * (pe.end_colno - pe.start_colno)


def parse_name(fname):
    name = path_split(fname)[-1]
    p = name.rfind(".")
    if p > 0:
        name = name[:p]
    name = name.replace(".", "_")  # explode?
    return "self." + name


def run_code(fname):
    interpreter = Interpreter()
    space.setup(interpreter)
    try:
        source = open(fname).read()
    except (OSError, IOError):
        print "Error reading file %s" % fname
        return 1
    # XXX error handling
    try:
        ast = parser.parse(lexer.lex(fname, source), ParsingState(fname,
                           source))
    except ParseError as pe:
        format_parser_error(pe)
        return 1
    importer = Importer(space, dirname(os.path.abspath(fname)), parser, lexer)
    dotted_name = parse_name(fname)
    w_mod = compile_module(space, fname, dotted_name, source, ast, importer)
    w_mod.setup(space)
    try:
        space.call_method(w_mod, 'main', [], [])
    except AppError as e:
        os.write(2, format_traceback(space, e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
