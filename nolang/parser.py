
import rply
from rpython.rlib.runicode import str_decode_utf_8, unicode_encode_utf_8, UNICHR

from nolang.lexer import TOKENS, ParseError
from nolang import astnodes as ast


def sr(p):
    return (p[0].getsrcpos()[0], p[-1].getsrcpos()[1])


class ParsingState(object):
    def __init__(self, filename, input):
        self.input = input
        self.filename = filename


def errorhandler(state, lookahead, msg="Parsing error"):
    sourcepos = lookahead.getsrcpos()
    idx = sourcepos[0]
    source = state.input
    last_nl = source.rfind("\n", 0, idx)
    lineno = source.count("\n", 0, idx)
    if last_nl < 0:
        last_nl = 0
        colno = idx - 1
    else:
        colno = idx - last_nl - 1
    next_nl = source.find("\n", idx)
    if next_nl < 0:
        next_nl = len(source)
    line = source[last_nl:next_nl]
    raise ParseError(msg, line, state.filename, lineno, colno - 1,
                     (sourcepos[1] - sourcepos[0]) + colno - 1)


def hex_to_utf8(s):
    uchr = UNICHR(int(s, 16))
    return unicode_encode_utf_8(uchr, len(uchr), 'strict')


def get_parser():
    pg = rply.ParserGenerator(TOKENS, precedence=[
        ('left', ['AND']),
        ('left', ['OR']),
        ('left', ['EQ', 'LT', 'GT', 'IN', 'NE', 'LE', 'GE']),
        ('left', ['PLUS', 'MINUS']),
        ('left', ['TRUEDIV', 'STAR']),
        ('left', ['DOT']),
        ('left', ['LEFT_PAREN']),
    ])
    pg.error(errorhandler)

    @pg.production('program : body')
    def program_body(state, p):
        element_list = p[0].get_element_list()
        for elem in element_list:
            if isinstance(elem, ast.VarDeclaration):
                raise errorhandler(state, elem,
                                   'var declarations in body disallowed')
        return ast.Program(element_list, srcpos=sr(element_list))

    @pg.production('body :')
    def body_empty(state, p):
        return ast.FunctionBody(None, None)

    @pg.production('body : body body_element')
    def body_body_element(state, p):
        return ast.FunctionBody(p[1], p[0])

    @pg.production('body_element : function')
    def body_function(state, p):
        return p[0]

    @pg.production('body_element : class_definition')
    def body_element_class_definition(state, p):
        return p[0]

    @pg.production('body_element : SEMICOLON')
    def body_element_semicolon(state, p):
        return None

    @pg.production('body_element : var_declaration')
    def body_element_var_decl(state, p):
        return p[0]

    @pg.production('body_element : IMPORT IDENTIFIER dot_identifier_list'
                   ' optional_import SEMICOLON')
    def body_element_import_statement(state, p):
        basename = p[1].getstr()
        if p[2] is None and p[3] is None:
            return ast.Import([basename], [], srcpos=sr(p))
        if p[3] is None:
            names = p[2].get_names()
            return ast.Import([basename] + names[:-1], [names[-1]], srcpos=sr(p))
        if p[2] is None:
            return ast.Import([basename], p[3].get_names(), srcpos=sr(p))
        return ast.Import([basename] + p[2].get_names(),
                          p[3].get_names(), srcpos=sr(p))

    @pg.production('optional_import :')
    def optional_import_empty(state, p):
        return None

    @pg.production('optional_import : '
                   'LEFT_CURLY_BRACE IDENTIFIER identifier_list '
                   'RIGHT_CURLY_BRACE')
    def optional_import_brace(state, p):
        return ast.IdentifierListPartial(p[1].getstr(), p[2])

    @pg.production('class_definition : CLASS IDENTIFIER LEFT_CURLY_BRACE body '
                   'RIGHT_CURLY_BRACE')
    def class_definition(state, p):
        return ast.ClassDefinition(p[1].getstr(), p[3], srcpos=sr(p))

    @pg.production('class_definition : CLASS IDENTIFIER LEFT_PAREN IDENTIFIER '
                   'RIGHT_PAREN LEFT_CURLY_BRACE body RIGHT_CURLY_BRACE')
    def class_definition_inheritance(state, p):
        return ast.ClassDefinition(p[1].getstr(), p[6], p[3].getstr(), srcpos=sr(p))

    @pg.production('function : DEF IDENTIFIER arglist LEFT_CURLY_BRACE'
                   ' function_body RIGHT_CURLY_BRACE')
    def function_function_body(state, p):
        lineno = p[0].getsourcepos().lineno
        return ast.Function(p[1].getstr(), p[2].get_args(),
                            p[4].get_element_list(), lineno, srcpos=sr(p))

    @pg.production('function_body :')
    def function_body_empty(state, p):
        return ast.FunctionBody(None, None)

    @pg.production('function_body : function_body statement')
    def function_body_statement(state, p):
        return ast.FunctionBody(p[1], p[0])

    @pg.production('statement : expression SEMICOLON')
    def statement_expression(state, p):
        return ast.Statement(p[0], srcpos=sr(p))

    @pg.production('statement : SEMICOLON')
    def staement_empty(state, p):
        return None

    @pg.production('statement : var_declaration')
    def statement_var_decl(state, p):
        return p[0]

    @pg.production('var_declaration : VAR IDENTIFIER type_decl var_decl SEMICOLON')
    def var_declaration_basic(state, p):
        vars = [ast.Var(p[1].getstr(), p[2], srcpos=sr([p[1], p[2]]))] + \
            p[3].get_vars()
        return ast.VarDeclaration(vars, srcpos=sr(p))

    @pg.production('var_decl : ')
    def var_decl_empty(state, p):
        return ast.VarDeclPartial(None, None, None, srcpos=(0, 0))

    @pg.production('var_decl : COMMA IDENTIFIER type_decl var_decl')
    def var_decl_identifier(state, p):
        return ast.VarDeclPartial(p[1].getstr(), p[2], p[3], srcpos=sr(p))

    @pg.production('arg_decl : ')
    def arg_decl_empty(state, p):
        return ast.ArgsPartial([])

    @pg.production('arg_decl : COMMA IDENTIFIER type_decl arg_decl')
    def arg_decl_identifier(state, p):
        arg = ast.Arg(p[1].getstr(), p[2], None, srcpos=sr([p[1], p[2]]))
        return ast.ArgsPartial([arg] + p[3].get_args())

    @pg.production('arg_decl : COMMA IDENTIFIER ASSIGN arg_default type_decl arg_decl')
    def arg_decl_default(state, p):
        arg = ast.Arg(p[1].getstr(), p[4], p[3], srcpos=sr([p[1], p[4]]))
        return ast.ArgsPartial([arg] + p[5].get_args())

    @pg.production('arg_default : INTEGER')
    def arg_default_integer(state, p):
        # XXX Add more kinds of default arg.
        return ast.Number(int(p[0].getstr()), srcpos=sr(p))

    @pg.production('type_decl : ')
    def type_decl_empty(state, p):
        return ast.NoTypeDecl(srcpos=(0, 0))

    @pg.production('type_decl : COLON IDENTIFIER')
    def type_decl_non_empty(state, p):
        return ast.BaseTypeDecl(p[1].getstr(), srcpos=sr([p[1]]))

    @pg.production('statement : IDENTIFIER ASSIGN expression SEMICOLON')
    def statement_identifier_assign_expr(state, p):
        return ast.Assignment(p[0].getstr(), p[2], srcpos=sr(p))

    @pg.production('statement : atom DOT IDENTIFIER ASSIGN expression SEMICOLON')
    def statement_setattr(state, p):
        return ast.Setattr(p[0], p[2].getstr(), p[4], srcpos=sr(p))

    @pg.production('statement : atom LEFT_SQUARE_BRACKET expression RIGHT_SQUARE_BRACKET'
                   ' ASSIGN expression SEMICOLON')
    def statement_setitem(state, p):
        return ast.Setitem(p[0], p[2], p[5], srcpos=sr(p))

    @pg.production('statement : RETURN expression SEMICOLON')
    def statement_return(state, p):
        return ast.Return(p[1], srcpos=sr(p))

    @pg.production('statement : WHILE expression LEFT_CURLY_BRACE function_body'
                   ' RIGHT_CURLY_BRACE')
    def statement_while_loop(state, p):
        return ast.While(p[1], p[3].get_element_list(), srcpos=sr(p))

    @pg.production('statement : IF expression LEFT_CURLY_BRACE function_body'
                   ' RIGHT_CURLY_BRACE')
    def statement_if_block(state, p):
        return ast.If(p[1], p[3].get_element_list(), srcpos=sr(p))

    @pg.production('statement : RAISE expression SEMICOLON')
    def statement_raise(state, p):
        return ast.Raise(p[1], srcpos=sr(p))

    @pg.production('statement : TRY LEFT_CURLY_BRACE function_body '
                   'RIGHT_CURLY_BRACE except_finally_clauses')
    def statement_try_except(state, p):
        if p[4] is None:
            errorhandler(state, p[0])
        lst = p[4].gather_list()
        return ast.TryExcept(p[2].get_element_list(), lst, srcpos=sr([p[0], lst[-1]]))

    @pg.production('except_finally_clauses : ')
    def except_finally_clases_empty(state, p):
        return None

    @pg.production('except_finally_clauses : EXCEPT IDENTIFIER LEFT_CURLY_BRACE'
                   ' function_body RIGHT_CURLY_BRACE except_finally_clauses')
    def except_finally_clauses_except(state, p):
        # We want the position information for the clause, not the list.
        return ast.ExceptClauseList([p[1].getstr()], None,
                                    p[3].get_element_list(), p[5],
                                    srcpos=sr(p[:-1]))

    @pg.production('except_finally_clauses : EXCEPT IDENTIFIER AS IDENTIFIER '
                   'LEFT_CURLY_BRACE function_body RIGHT_CURLY_BRACE '
                   'except_finally_clauses')
    def except_finally_clauses_except_as_identifier(state, p):
        # We want the position information for the clause, not the list.
        return ast.ExceptClauseList([p[1].getstr()], p[3].getstr(),
                                    p[5].get_element_list(), p[7],
                                    srcpos=sr(p[:-1]))

    @pg.production('except_finally_clauses : FINALLY LEFT_CURLY_BRACE '
                   'function_body RIGHT_CURLY_BRACE')
    def except_finally_clauses_finally(state, p):
        return ast.FinallyClause(p[2].get_element_list(), False, srcpos=sr(p))

    @pg.production('except_finally_clauses : ELSE LEFT_CURLY_BRACE '
                   'function_body RIGHT_CURLY_BRACE')
    def except_finally_clause_else(state, p):
        return ast.FinallyClause(p[2].get_element_list(), True, srcpos=sr(p))

    @pg.production('identifier_list : COMMA IDENTIFIER identifier_list')
    def identifier_list_arglist(state, p):
        return ast.IdentifierListPartial(p[1].getstr(), p[2])

    @pg.production('identifier_list :')
    def rest_of_identifier_list_empty(state, p):
        return None

    @pg.production('dot_identifier_list : DOT IDENTIFIER dot_identifier_list')
    def dot_identifier_list_arglist(state, p):
        return ast.IdentifierListPartial(p[1].getstr(), p[2])

    @pg.production('dot_identifier_list :')
    def rest_of_dot_identifier_list_empty(state, p):
        return None

    @pg.production('arglist : LEFT_PAREN RIGHT_PAREN')
    def arglist(state, p):
        return ast.ArgList([], srcpos=sr(p))

    @pg.production('arglist : LEFT_PAREN IDENTIFIER type_decl arg_decl RIGHT_PAREN')
    def arglist_non_empty(state, p):
        arg = ast.Arg(p[1].getstr(), p[2], None, srcpos=sr([p[1], p[2]]))
        return ast.ArgList([arg] + p[3].get_args(), srcpos=sr(p))

    @pg.production('arglist : LEFT_PAREN IDENTIFIER ASSIGN arg_default type_decl arg_decl RIGHT_PAREN')
    def arglist_non_empty_default(state, p):
        arg = ast.Arg(p[1].getstr(), p[4], p[3], srcpos=sr([p[1], p[4]]))
        return ast.ArgList([arg] + p[5].get_args(), srcpos=sr(p))

    @pg.production('expression : INTEGER')
    def expression_number(state, p):
        return ast.Number(int(p[0].getstr()), srcpos=sr(p))

    @pg.production('expression : ST_DQ_STRING stringcontent ST_ENDSTRING')
    @pg.production('expression : ST_SQ_STRING stringcontent ST_ENDSTRING')
    @pg.production('expression : ST_RAW_DQ_STRING rawstringcontent ST_ENDRAW')
    @pg.production('expression : ST_RAW_SQ_STRING rawstringcontent ST_ENDRAW')
    def expression_string(state, p):
        val = ''.join(p[1].get_strparts())
        str_decode_utf_8(val, len(val), 'strict', final=True)
        return ast.String(val, srcpos=sr(p))

    @pg.production('expression : ST_INTERP_STRING interpstr ST_ENDSTRING')
    def expression_interpstring(state, p):
        strings = p[1].get_strings()
        return ast.InterpString(strings, p[1].get_exprs(), srcpos=sr(p))

    @pg.production('expression : atom')
    def expression_atom(state, p):
        return p[0]

    @pg.production('expression : expression OR expression')
    def expression_or_expression(state, p):
        return ast.Or(p[0], p[2], srcpos=sr(p))

    @pg.production('expression : expression AND expression')
    def expression_and_expression(state, p):
        return ast.And(p[0], p[2], srcpos=sr(p))

    @pg.production('interpstr : stringcontent')
    def interpstr_start(state, p):
        val = ''.join(p[0].get_strparts())
        str_decode_utf_8(val, len(val), 'strict', final=True)
        return ast.InterpStringContents([val], [])

    @pg.production('interpstr : interpstr ST_INTERP expression RIGHT_CURLY_BRACE stringcontent')
    def interpstr_part(state, p):
        val = ''.join(p[4].get_strparts())
        str_decode_utf_8(val, len(val), 'strict', final=True)
        return ast.InterpStringContents(
            p[0].get_strings() + [val], p[0].get_exprs() + [p[2]])

    @pg.production('stringcontent : ')
    def string_empty(state, p):
        return ast.StringContent([])

    @pg.production('stringcontent : stringcontent ESC_QUOTE')
    def string_esc_quote(state, p):
        return ast.StringContent(p[0].get_strparts() + [p[1].getstr()[1]])

    @pg.production('stringcontent : stringcontent ESC_ESC')
    def string_esc_esc(state, p):
        return ast.StringContent(p[0].get_strparts() + ['\\'])

    @pg.production('stringcontent : stringcontent ESC_SIMPLE')
    def string_esc_simple(state, p):
        part = {
            'a': '\a',
            'b': '\b',
            'f': '\f',
            'n': '\n',
            'r': '\r',
            't': '\t',
            'v': '\v',
            '0': '\0',
            '$': '$',
        }[p[1].getstr()[1]]
        return ast.StringContent(p[0].get_strparts() + [part])

    @pg.production('stringcontent : stringcontent ESC_HEX_8')
    @pg.production('stringcontent : stringcontent ESC_HEX_16')
    def string_esc_hex_fixed(state, p):
        s = p[1].getstr()
        return ast.StringContent(p[0].get_strparts() + [hex_to_utf8(s[2:])])

    @pg.production('stringcontent : stringcontent ESC_HEX_ANY')
    def string_esc_hex_any(state, p):
        s = p[1].getstr()
        end = len(s) - 1
        assert end >= 0
        return ast.StringContent(p[0].get_strparts() + [hex_to_utf8(s[3:end])])

    @pg.production('stringcontent : stringcontent ESC_UNRECOGNISED')
    def string_esc_unrecognised(state, p):
        return ast.StringContent(p[0].get_strparts() + [p[1].getstr()])

    @pg.production('stringcontent : stringcontent CHAR')
    def string_char(state, p):
        return ast.StringContent(p[0].get_strparts() + [p[1].getstr()])

    @pg.production('rawstringcontent : ')
    def rawstring_empty(state, p):
        return ast.StringContent([])

    @pg.production('rawstringcontent : rawstringcontent RAW_ESC')
    @pg.production('rawstringcontent : rawstringcontent RAW_CHAR')
    def rawstring_char(state, p):
        return ast.StringContent(p[0].get_strparts() + [p[1].getstr()])

    @pg.production('atom : TRUE')
    def atom_true(state, p):
        return ast.TrueNode(srcpos=sr(p))

    @pg.production('atom : IDENTIFIER')
    def atom_identifier(state, p):
        return ast.Identifier(p[0].getstr(), srcpos=sr(p))

    @pg.production('atom : FALSE')
    def atom_false(state, p):
        return ast.FalseNode(srcpos=sr(p))

    @pg.production('atom : atom LEFT_PAREN arg_list RIGHT_PAREN')
    def atom_call(state, p):
        return ast.Call(p[0], p[2].get_arg_list(), p[2].get_named_arg_list(), srcpos=sr(p))

    @pg.production('atom : LEFT_PAREN expression RIGHT_PAREN')
    def atom_paren_expression_paren(state, p):
        return p[1]

    @pg.production('atom : atom DOT IDENTIFIER')
    def atom_dot_identifier(state, p):
        return ast.Getattr(p[0], p[2].getstr(), srcpos=sr(p))

    @pg.production('atom : LEFT_SQUARE_BRACKET expression_list RIGHT_SQUARE_BRACKET')
    def atom_list_literal(state, p):
        return ast.List(p[1].get_element_list(), srcpos=sr(p))

    @pg.production('atom : LEFT_CURLY_BRACE dict_pair_list RIGHT_CURLY_BRACE')
    def atom_dict_literal(state, p):
        return ast.Dict(p[1].get_element_list(), srcpos=sr(p))

    @pg.production('atom : atom LEFT_SQUARE_BRACKET expression RIGHT_SQUARE_BRACKET')
    def atom_getitem(state, p):
        return ast.Getitem(p[0], p[2], srcpos=sr(p))

    @pg.production('expression : expression PLUS expression')
    @pg.production('expression : expression MINUS expression')
    @pg.production('expression : expression STAR expression')
    @pg.production('expression : expression TRUEDIV expression')
    @pg.production('expression : expression LT expression')
    @pg.production('expression : expression GT expression')
    @pg.production('expression : expression LE expression')
    @pg.production('expression : expression GE expression')
    @pg.production('expression : expression EQ expression')
    @pg.production('expression : expression IN expression')
    @pg.production('expression : expression NE expression')
    def expression_binop_expression(state, p):
        return ast.BinOp(p[1].getstr(), p[0], p[2], sr([p[1]]), srcpos=sr(p))

    @pg.production('expression : expression NOT IN expression')
    def expression_not_in_expression(state, p):
        return ast.BinOp('not in', p[0], p[3], sr([p[1], p[2]]), srcpos=sr(p))

    @pg.production('expression_list : ')
    def expression_list_empty(state, p):
        return ast.ExpressionListPartial([])

    @pg.production('expression_list : expression expression_sublist')
    def expression_list_expression(state, p):
        return ast.ExpressionListPartial([p[0]] + p[1].get_element_list())

    @pg.production('expression_sublist : ')
    @pg.production('expression_sublist : COMMA')
    def expression_sublist_empty(state, p):
        return ast.ExpressionListPartial([])

    @pg.production('expression_sublist : COMMA expression expression_sublist')
    def expression_sublist_expression(state, p):
        return ast.ExpressionListPartial([p[1]] + p[2].get_element_list())

    @pg.production('named_arg : IDENTIFIER ASSIGN expression')
    def named_arg(state, p):
        return ast.NamedArg(p[0].getstr(), p[2], srcpos=sr(p))

    @pg.production('arg_list : ')
    def arg_list_empty(state, p):
        return ast.ArgListPartial([], [])

    @pg.production('arg_list : expression arg_sublist')
    def arg_list_expression(state, p):
        return ast.ArgListPartial([p[0]] + p[1].get_arg_list(), p[1].get_named_arg_list())

    @pg.production('arg_list : named_arg named_arg_sublist')
    def arg_list_named_arg(state, p):
        return ast.ArgListPartial(p[1].get_arg_list(), [p[0]] + p[1].get_named_arg_list())

    @pg.production('arg_sublist : ')
    @pg.production('arg_sublist : COMMA')
    def arg_sublist_empty(state, p):
        return ast.ArgListPartial([], [])

    @pg.production('arg_sublist : COMMA expression arg_sublist')
    def arg_sublist_expression(state, p):
        return ast.ArgListPartial([p[1]] + p[2].get_arg_list(), p[2].get_named_arg_list())

    @pg.production('arg_sublist : COMMA named_arg named_arg_sublist')
    def arg_sublist_named_args(state, p):
        return ast.ArgListPartial(p[2].get_arg_list(), [p[1]] + p[2].get_named_arg_list())

    @pg.production('named_arg_sublist : ')
    @pg.production('named_arg_sublist : COMMA')
    def named_arg_sublist_empty(state, p):
        return ast.ArgListPartial([], [])

    @pg.production('named_arg_sublist : COMMA named_arg named_arg_sublist')
    def named_arg_sublist_expression(state, p):
        return ast.ArgListPartial(p[2].get_arg_list(), [p[1]] + p[2].get_named_arg_list())

    @pg.production('dict_pair_list : ')
    def dict_pair_list_empty(state, p):
        return ast.ExpressionListPartial([])

    @pg.production('dict_pair_list : expression COLON expression dict_pair_sublist')
    def dict_pair_list_expression(state, p):
        return ast.ExpressionListPartial([p[0], p[2]] + p[3].get_element_list())

    @pg.production('dict_pair_sublist : ')
    @pg.production('dict_pair_sublist : COMMA')
    def dict_pair_sublist_empty(state, p):
        return ast.ExpressionListPartial([])

    @pg.production('dict_pair_sublist : COMMA expression COLON expression dict_pair_sublist')
    def dict_pair_sublist_expression(state, p):
        return ast.ExpressionListPartial([p[1], p[3]] + p[4].get_element_list())

    res = pg.build()
    if res.lr_table.sr_conflicts:
        raise Exception("shift reduce conflicts")
    return res
