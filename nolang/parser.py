
import rply

from nolang.lexer import TOKENS
from nolang import astnodes as ast

class ParsingState(object):
    def __init__(self, input):
        self.input = input

class ParseError(Exception):
    def __init__(self, line, filename, lineno, start_colno, end_colno):
        self.line = line
        self.filename = filename
        self.lineno = lineno
        self.start_colno = start_colno
        self.end_colno = end_colno

    def __str__(self):
        # 6 comes from formatting of ParseError by pytest
        return (self.line + "\n" + " " * (self.start_colno - 6) +
                "^" * (self.end_colno - self.start_colno))

def errorhandler(state, lookahead):
    lines = state.input.splitlines()
    sourcepos = lookahead.getsourcepos()
    line = lines[sourcepos.lineno - 1]
    raise ParseError(line, '<input>', sourcepos.lineno, sourcepos.colno - 1,
                     len(lookahead.value) + sourcepos.colno - 1)

def get_parser():
    pg = rply.ParserGenerator(TOKENS, precedence=[
        ('left', ['AND']),
        ('left', ['OR']),
        ('left', ['EQ', 'LT']),
        ('left', ['PLUS', 'MINUS']),
        ('left', ['TRUEDIV', 'STAR']),
        ('left', ['DOT']),
        ('left', ['LEFT_PAREN']),
        ])
    pg.error(errorhandler)

    @pg.production('program : body')
    def program_body(state, p):
        return p[0]

    @pg.production('body :')
    def body_empty(state, p):
        return ast.Program([])

    @pg.production('body : body body_element')
    def body_body_element(state, p):
        p[0].get_element_list().append(p[1])
        return p[0]

    @pg.production('body_element : function')
    def body_function(state, p):
        return p[0]

    @pg.production('body_element : class_definition')
    def body_element_class_definition(state, p):
        return p[0]

    @pg.production('class_definition : CLASS IDENTIFIER LEFT_CURLY_BRACE body '
                   'RIGHT_CURLY_BRACE')
    def class_definition(state, p):
        return ast.ClassDefinition(p[1].getstr(), p[3])

    @pg.production('class_definition : CLASS IDENTIFIER LEFT_PAREN IDENTIFIER '
                   'RIGHT_PAREN LEFT_CURLY_BRACE body RIGHT_CURLY_BRACE')
    def class_definition_inheritance(state, p):
        return ast.ClassDefinition(p[1].getstr(), p[6], p[3].getstr())

    @pg.production('function : FUNCTION IDENTIFIER arglist LEFT_CURLY_BRACE'
                   ' function_body RIGHT_CURLY_BRACE')
    def function_function_body(state, p):
        return ast.Function(p[1].getstr(), p[2].get_names(),
                            p[4].get_element_list())

    @pg.production('function : FUNCTION IDENTIFIER arglist LEFT_CURLY_BRACE'
                   ' function_body expression RIGHT_CURLY_BRACE')
    def function_function_body_implicit_return(state, p):
        statements = p[4].get_element_list()
        statements.append(ast.Return(p[5]))
        return ast.Function(p[1].getstr(), p[2].get_names(), statements)

    @pg.production('function_body :')
    def function_body_empty(state, p):
        return ast.FunctionBody([])

    @pg.production('function_body : function_body statement')
    def function_body_statement(state, p):
        p[0].get_element_list().append(p[1])
        return p[0]

    @pg.production('statement : expression SEMICOLON')
    def statement_expression(state, p):
        return ast.Statement(p[0])

    @pg.production('statement : VAR IDENTIFIER var_decl SEMICOLON')
    def statement_var_decl(state, p):
        return ast.VarDeclaration([p[1].getstr()] + p[2].get_names())

    @pg.production('var_decl : ')
    def var_decl_empty(state, p):
        return ast.VarDeclPartial([])

    @pg.production('var_decl : COMMA IDENTIFIER var_decl')
    def var_decl_identifier(state, p):
        return ast.VarDeclPartial([p[1].getstr()] + p[2].get_names())

    @pg.production('statement : IDENTIFIER ASSIGN expression SEMICOLON')
    def statement_identifier_assign_expr(state, p):
        return ast.Assignment(p[0].getstr(), p[2])

    @pg.production('statement : atom DOT IDENTIFIER ASSIGN expression SEMICOLON')
    def statement_setattr(state, p):
        return ast.Setattr(p[0], p[2].getstr(), p[4])

    @pg.production('statement : RETURN expression SEMICOLON')
    def statement_return(state, p):
        return ast.Return(p[1])

    @pg.production('statement : WHILE expression LEFT_CURLY_BRACE function_body'
                   ' RIGHT_CURLY_BRACE')
    def statement_while_loop(state, p):
        return ast.While(p[1], p[3].get_element_list())

    @pg.production('statement : IF expression LEFT_CURLY_BRACE function_body'
                   ' RIGHT_CURLY_BRACE')
    def statement_if_block(state, p):
        return ast.If(p[1], p[3].get_element_list())

    @pg.production('statement : RAISE expression SEMICOLON')
    def statement_raise(state, p):
        return ast.Raise(p[1])

    @pg.production('statement : TRY LEFT_CURLY_BRACE function_body '
                   'RIGHT_CURLY_BRACE EXCEPT IDENTIFIER LEFT_CURLY_BRACE '
                   'function_body RIGHT_CURLY_BRACE')
    def statement_try_except(state, p):
        return ast.TryExcept(p[2].get_element_list(), [p[5].getstr()],
                             p[7].get_element_list(), None)

    @pg.production('arglist : LEFT_PAREN RIGHT_PAREN')
    def arglist(state, p):
        return ast.ArgList([])

    @pg.production('arglist : LEFT_PAREN IDENTIFIER var_decl RIGHT_PAREN')
    def arglist_non_empty(state, p):
        return ast.ArgList([p[1].getstr()] + p[2].get_names())

    @pg.production('expression : INTEGER')
    def expression_number(state, p):
        return ast.Number(int(p[0].getstr()))

    @pg.production('expression : STRING')
    def expression_string(state, p):
        # XXX validate valid utf8
        s = p[0].getstr()
        end = len(s) - 1
        assert end >= 0
        return ast.String(s[1:end])

    @pg.production('expression : atom')
    def expression_atom(state, p):
        return p[0]

    @pg.production('expression : expression OR expression')
    def expression_or_expression(state, p):
        return ast.Or(p[0], p[2])

    @pg.production('expression : expression AND expression')
    def expression_and_expression(state, p):
        return ast.And(p[0], p[2])

    @pg.production('atom : TRUE')
    def atom_true(state, p):
        return ast.TrueNode()

    @pg.production('atom : IDENTIFIER')
    def atom_identifier(state, p):
        return ast.Identifier(p[0].getstr())

    @pg.production('atom : FALSE')
    def atom_false(state, p):
        return ast.FalseNode()

    @pg.production('atom : atom LEFT_PAREN expression_list '
                   'RIGHT_PAREN')
    def atom_call(state, p):
        return ast.Call(p[0], p[2].get_element_list())

    @pg.production('atom : LEFT_PAREN expression RIGHT_PAREN')
    def atom_paren_expression_paren(state, p):
        return p[1]

    @pg.production('atom : atom DOT IDENTIFIER')
    def atom_dot_identifier(state, p):
        return ast.Getattr(p[0], p[2].getstr())

    @pg.production('expression : expression PLUS expression')
    @pg.production('expression : expression MINUS expression')
    @pg.production('expression : expression STAR expression')
    @pg.production('expression : expression TRUEDIV expression')
    @pg.production('expression : expression LT expression')
    @pg.production('expression : expression EQ expression')
    def expression_lt_expression(state, p):
        return ast.BinOp(p[1].getstr(), p[0], p[2])

    @pg.production('expression_list : ')
    def expression_list_empty(state, p):
        return ast.ExpressionListPartial([])

    @pg.production('expression_list : expression expression_sublist')
    def expression_list_expression(state, p):
        return ast.ExpressionListPartial([p[0]] + p[1].get_element_list())

    @pg.production('expression_sublist : ')
    def expression_sublist_empty(state, p):
        return ast.ExpressionListPartial([])

    @pg.production('expression_sublist : COMMA expression expression_sublist')
    def expression_sublist_expression(state, p):
        return ast.ExpressionListPartial([p[1]] + p[2].get_element_list())

    res = pg.build()
    if res.lr_table.sr_conflicts:
        raise Exception("shift reduce conflicts")
    return res
