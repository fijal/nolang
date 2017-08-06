from rply import LexerGenerator
from rply.lexer import Lexer, LexerStream
from rply.token import Token as RplyToken
from rpython.rlib.runicode import str_decode_utf_8, unicode_encode_utf_8, UNICHR


class Token(RplyToken):
    def getsrcpos(self):
        return (self.source_pos.start, self.source_pos.end)


class SourceRange(object):
    def __init__(self, start, end, lineno, colno):
        self.start = start
        self.end = end
        self.lineno = lineno
        self.colno = colno

    def __repr__(self):
        return "SourceRange(start=%d, end=%d, lineno=%d, colno=%d)" % (
            self.start, self.end, self.lineno, self.colno)


class ParseError(Exception):
    def __init__(self, msg, line, filename, lineno, start_colno, end_colno):
        self.msg = msg
        self.line = line
        self.filename = filename
        self.lineno = lineno
        self.start_colno = start_colno
        self.end_colno = end_colno

    def __str__(self):
        # 6 comes from formatting of ParseError by pytest
        return (self.line + "\n" + " " * (self.start_colno - 6) +
                "^" * (self.end_colno - self.start_colno))


RULES = [
    ('INTEGER', r'\d+'),
    ('PLUS', r'\+'),
    ('MINUS', r'\-'),
    ('LT', r'\<'),
    ('STAR', r'\*'),
    ('DOT', r'\.'),
    ('TRUEDIV', r'\/\/'),
    ('EQ', r'=='),
    ('ASSIGN', r'='),
    ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ('LEFT_CURLY_BRACE', r'\{'),
    ('LEFT_PAREN', r'\('),
    ('RIGHT_PAREN', r'\)'),
    ('RIGHT_CURLY_BRACE', r'\}'),
    ('COMMA', r','),
    ('SEMICOLON', r';'),
    ('STRING', r'"'),
]

KEYWORDS = [
    'def',
    'class',
    'return',
    'var',
    'while',
    'if',
    'or',
    'and',
    'true',
    'false',
    'try',
    'except',
    'finally',
    'as',
    'raise',
    'import',
]

TOKENS = [x[0] for x in RULES] + [x.upper() for x in KEYWORDS]

KEYWORD_DICT = dict.fromkeys(KEYWORDS)


STRING_RULES = [
    ('ESC_QUOTE', r'\\"'),
    ('ESC_ESC', r'\\\\'),
    ('ESC_SIMPLE', r'\\[abfnrtv0]'),
    ('ESC_HEX_8', r'\\x[0-9a-fA-F]{2}'),
    ('ESC_HEX_16', r'\\u[0-9a-fA-F]{4}'),
    ('ESC_HEX_ANY', r'\\u\{[0-9a-fA-F]+\}'),
    ('ESC_UNRECOGNISED', r'\\[^abfnrtv0xu"\\]'),
    ('CHAR', r'[^"\\]'),
    ('CLOSING_QUOTE', r'"'),
]


class SRLexerStream(LexerStream):
    def __init__(self, lexer, filename, s, idx=0, lineno=1):
        self._filename = filename
        LexerStream.__init__(self, lexer, s)
        self.idx = idx
        self._lineno = lineno

    def _update_pos(self, match_start, match_end):
        lineno = self._lineno
        self.idx = match_end
        self._lineno += self.s.count("\n", match_start, match_end)
        last_nl = self.s.rfind("\n", 0, match_start)
        if last_nl < 0:
            colno = match_start + 1
        else:
            colno = match_start - last_nl
        return SourceRange(match_start, match_end, lineno, colno)

    def next(self):
        while True:
            if self.idx >= len(self.s):
                raise StopIteration
            for rule in self.lexer.ignore_rules:
                match = rule.matches(self.s, self.idx)
                if match:
                    self._update_pos(match.start, match.end)
                    break
            else:
                break

        for rule in self.lexer.rules:
            match = rule.matches(self.s, self.idx)
            if match:
                source_pos = self._update_pos(match.start, match.end)
                token = Token(
                    rule.name, self.s[match.start:match.end], source_pos
                )
                return token
        else:
            raise self.parse_error("unrecognized token")

    def parse_error(self, msg):
        last_nl = self.s.rfind("\n", 0, self.idx)
        if last_nl < 0:
            colno = self.idx - 1
        else:
            colno = self.idx - last_nl - 1
        return ParseError(msg,
                          self.s.splitlines()[self._lineno - 1],
                          self._filename, self._lineno, colno, colno + 1)


class StringLexer(Lexer):
    def lex(self, filename, s, idx, lineno):
        return SRLexerStream(self, filename, s, idx, lineno)


class StringLexerGenerator(LexerGenerator):
    def build(self):
        return StringLexer(self.rules, self.ignore_rules)


def get_string_lexer():
    lg = StringLexerGenerator()

    for name, rule in STRING_RULES:
        lg.add(name, rule)
    return lg.build()


def hex_to_utf8(s):
    uchr = UNICHR(int(s, 16))
    return unicode_encode_utf_8(uchr, len(uchr), 'strict')


class QuillLexerStream(SRLexerStream):
    _last_token = None

    def lex_string(self):
        parts = []
        length = 1
        for t in self.lexer.string_lexer.lex(self._filename, self.s, self.idx + 1, self._lineno):
            length += len(t.value)
            if t.name == 'CLOSING_QUOTE':
                break
            elif t.name == 'ESC_QUOTE':
                parts.append('"')
            elif t.name == 'ESC_ESC':
                parts.append('\\')
            elif t.name == 'ESC_SIMPLE':
                parts.append({
                    'a': '\a',
                    'b': '\b',
                    'f': '\f',
                    'n': '\n',
                    'r': '\r',
                    't': '\t',
                    'v': '\v',
                    '0': '\0',
                }[t.value[1]])
            elif t.name in ['ESC_HEX_8', 'ESC_HEX_16']:
                parts.append(hex_to_utf8(t.value[2:]))
            elif t.name == 'ESC_HEX_ANY':
                parts.append(hex_to_utf8(t.value[3:-1]))
            else:
                assert t.name in ['ESC_UNRECOGNISED', 'CHAR']
                parts.append(t.value)
        else:
            raise self.parse_error("unterminated string")

        val = ''.join(parts)
        str_decode_utf_8(val, len(val), 'strict', final=True)
        source_range = self._update_pos(self.idx, self.idx + length)
        return Token('STRING', val, source_range)

    def next(self):
        while True:
            if self.idx >= len(self.s):
                raise StopIteration
            assert len(self.lexer.ignore_rules) == 1
            whitespace_rule = self.lexer.ignore_rules[0]
            match = whitespace_rule.matches(self.s, self.idx)
            if match is not None:
                source_range = self._update_pos(match.start, match.end)
                if "\n" in self.s[match.start:match.end]:
                    if self._last_token.name not in \
                       ('RIGHT_CURLY_BRACE', 'RIGHT_PAREN', 'IDENTIFIER', 'INTEGER'):
                        continue
                    token = Token(
                        'SEMICOLON', self.s[match.start:match.end], source_range
                    )
                    self._last_token = token
                    return token
            else:
                break

        for rule in self.lexer.rules:
            match = rule.matches(self.s, self.idx)
            if match:
                if rule.name == 'STRING':
                    token = self.lex_string()
                    self._last_token = token
                    return token

                source_range = self._update_pos(match.start, match.end)
                val = self.s[match.start:match.end]
                if val in KEYWORD_DICT:
                    name = val.upper()
                else:
                    name = rule.name
                token = Token(name, val, source_range)
                self._last_token = token
                return token
        else:
            raise self.parse_error("unrecognized token")


class QuillLexer(Lexer):
    def __init__(self, rules, ignore_rules, string_lexer):
        self.string_lexer = string_lexer
        Lexer.__init__(self, rules, ignore_rules)

    def lex(self, filename, s):
        return QuillLexerStream(self, filename, s)


class QuillLexerGenerator(LexerGenerator):
    def build(self):
        return QuillLexer(self.rules, self.ignore_rules, get_string_lexer())


def get_lexer():
    lg = QuillLexerGenerator()

    for name, rule in RULES:
        lg.add(name, rule)
    lg.ignore('\s+')
    return lg.build()
