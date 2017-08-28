
""" AST nodes and corresponding compile functions. The basic AstNode comes
with compile() interface that produces bytecode
"""

from nolang import opcodes
from nolang.function import W_Function
from nolang.objects.usertype import W_UserType
from nolang.bytecode import compile_bytecode
from nolang.compiler import compile_class

from rply.token import BaseBox


class NameAlreadyDefined(Exception):
    def __init__(self, name):
        self.name = name


class StoringIntoGlobal(Exception):
    def __init__(self, name):
        self.name = name


class AstNode(BaseBox):
    def __init__(self, srcpos=None):
        if srcpos is None:
            srcpos = (0, 0)  # This is NOT rpython
        self._startidx, self._endidx = srcpos

    def getsrcpos(self):
        return (self._startidx, self._endidx)

    def getstartidx(self):
        return self._startidx

    def getendidx(self):
        return self._endidx

    def compile(self, state):
        raise NotImplementedError("abstract base class")

    def add_missing_imports(self, space, w_mod, globals_w, importer):
        pass

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, ", ".join([
            "%s=%s" % (k, v) for k, v in self.__dict__.iteritems()
            if k != '_srcpos']))

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        to_compare = self.__dict__.copy()
        other = other.__dict__.copy()
        del to_compare['_startidx']
        del to_compare['_endidx']
        del other['_startidx']
        del other['_endidx']
        return to_compare == other

    def __ne__(self, other):
        return not self == other


class Number(AstNode):
    def __init__(self, value, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.value = value

    def getintvalue(self):
        # XXX Temporary hack to get an int value out of this when using it as a
        # default value.
        return self.value

    def compile(self, state):
        no = state.add_int_constant(self.value)
        state.emit(self.getstartidx(), opcodes.LOAD_CONSTANT, no)


class String(AstNode):
    def __init__(self, value, srcpos):
        AstNode.__init__(self, srcpos)
        self.value = value

    def compile(self, state):
        no = state.add_str_constant(self.value)
        state.emit(self.getstartidx(), opcodes.LOAD_CONSTANT, no)


class StringContent(AstNode):
    def __init__(self, strparts):
        self.strparts = strparts

    def get_strparts(self):
        return self.strparts


class InterpString(AstNode):
    def __init__(self, strings, exprs, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.strings = strings
        self.exprs = exprs

    def get_strings(self):
        return self.strings

    def get_exprs(self):
        return self.exprs

    def compile(self, state):
        for i in range(len(self.exprs)):
            no = state.add_str_constant(self.strings[i])
            state.emit(self.getstartidx(), opcodes.LOAD_CONSTANT, no)
            self.exprs[i].compile(state)
        no = state.add_str_constant(self.strings[-1])
        state.emit(self.getstartidx(), opcodes.LOAD_CONSTANT, no)
        state.emit(self.getstartidx(), opcodes.TEXT_BUILD, len(self.exprs) * 2 + 1)


class InterpStringContents(AstNode):
    def __init__(self, strings, exprs):
        self.strings = strings
        self.exprs = exprs

    def get_strings(self):
        return self.strings

    def get_exprs(self):
        return self.exprs


class List(AstNode):
    def __init__(self, items, srcpos):
        AstNode.__init__(self, srcpos)
        self.items = items

    def compile(self, state):
        for item in self.items:
            item.compile(state)
        state.emit(self.getstartidx(), opcodes.LIST_BUILD, len(self.items))


class Dict(AstNode):
    def __init__(self, items, srcpos):
        AstNode.__init__(self, srcpos)
        self.items = items

    def compile(self, state):
        for item in self.items:
            item.compile(state)
        state.emit(self.getstartidx(), opcodes.DICT_BUILD, len(self.items))


class UnaryOp(AstNode):
    def __init__(self, op, expr, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.op = op
        self.expr = expr

    def compile(self, state):
        self.expr.compile(state)
        if self.op == 'not':
            state.emit(self.getstartidx(), opcodes.NOT)
        else:
            assert False


class BinOp(AstNode):
    def __init__(self, op, left, right, oppos, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.op = op
        self.oppos = oppos
        self.left = left
        self.right = right

    def compile(self, state):
        self.left.compile(state)
        self.right.compile(state)
        if self.op == '+':
            state.emit(self.oppos[0], opcodes.ADD)
        elif self.op == '-':
            state.emit(self.oppos[0], opcodes.SUB)
        elif self.op == '//':
            state.emit(self.oppos[0], opcodes.TRUEDIV)
        elif self.op == '*':
            state.emit(self.oppos[0], opcodes.MUL)
        elif self.op == '<':
            state.emit(self.oppos[0], opcodes.LT)
        elif self.op == '>':
            state.emit(self.oppos[0], opcodes.GT)
        elif self.op == '>=':
            state.emit(self.oppos[0], opcodes.GE)
        elif self.op == '<=':
            state.emit(self.oppos[0], opcodes.LE)
        elif self.op == '==':
            state.emit(self.oppos[0], opcodes.EQ)
        elif self.op == '!=':
            state.emit(self.oppos[0], opcodes.NE)
        elif self.op == 'in':
            state.emit(self.oppos[0], opcodes.IN)
        elif self.op == 'not in':
            state.emit(self.oppos[0], opcodes.IN)
            state.emit(self.oppos[0], opcodes.NOT)
        else:
            assert False


class And(AstNode):
    def __init__(self, left, right, srcpos):
        AstNode.__init__(self, srcpos)
        self.left = left
        self.right = right

    def compile(self, state):
        self.left.compile(state)
        state.emit(self.left.getendidx(), opcodes.JUMP_IF_FALSE_NOPOP, 0)
        pos = state.get_patch_position()
        state.emit(self.right.getstartidx(), opcodes.DISCARD)
        self.right.compile(state)
        state.patch_position(pos, state.get_position())


class Or(AstNode):
    def __init__(self, left, right, srcpos):
        AstNode.__init__(self, srcpos)
        self.left = left
        self.right = right

    def compile(self, state):
        self.left.compile(state)
        state.emit(self.left.getendidx(), opcodes.JUMP_IF_TRUE_NOPOP, 0)
        pos = state.get_patch_position()
        state.emit(self.right.getstartidx(), opcodes.DISCARD)
        self.right.compile(state)
        state.patch_position(pos, state.get_position())


class TrueNode(AstNode):
    def compile(self, state):
        state.emit(self.getstartidx(), opcodes.LOAD_TRUE)


class FalseNode(AstNode):
    def compile(self, state):
        state.emit(self.getstartidx(), opcodes.LOAD_FALSE)


class Program(AstNode):
    def __init__(self, elements, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.elements = elements

    def get_element_list(self):
        return self.elements


class Function(AstNode):
    def __init__(self, name, arglist, body, lineno=None, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.name = name
        self.arglist = arglist
        self.body = body
        self.lineno = lineno

    def get_name(self):
        return self.name

    def add_name(self, mapping):
        if self.name in mapping:
            raise NameAlreadyDefined(self.name)
        mapping[self.name] = len(mapping)

    def compile(self, state):
        for item in self.body:
            item.compile(state)

    def add_global_symbols(self, space, globals_w, source, w_mod):
        w_g = W_Function(self.name, compile_bytecode(self, source,
                         w_mod, self.arglist, self.lineno))
        globals_w.append(w_g)


class ClassDefinition(AstNode):
    def __init__(self, name, body, parent=None, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.name = name
        self.body = body
        self.parent = parent

    def get_name(self):
        return self.name

    def add_name(self, mapping):
        if self.name in mapping:
            raise NameAlreadyDefined(self.name)
        mapping[self.name] = len(mapping)

    def get_element_list(self):
        return self.body.get_element_list()

    def add_global_symbols(self, space, globals_w, source, w_mod):
        force_names = None
        for item in self.body.get_element_list():
            if isinstance(item, VarDeclaration):
                if force_names is None:
                    force_names = []
                force_names.extend([x.name for x in item.vars])
        t = compile_class(space, source, self, w_mod, self.parent)
        alloc, class_elements_w, w_parent, default_alloc = t
        w_g = W_UserType(alloc, self.name, class_elements_w, w_parent,
                         default_alloc, force_names)
        globals_w.append(w_g)


class While(AstNode):
    def __init__(self, expr, block, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.expr = expr
        self.block = block

    def compile(self, state):
        jump_pos = state.get_position()
        self.expr.compile(state)
        state.emit(self.expr.getendidx(), opcodes.JUMP_IF_FALSE, 0)
        patch_pos = state.get_patch_position()
        for item in self.block:
            item.compile(state)
        state.emit(self.block[-1].getendidx(), opcodes.JUMP_ABSOLUTE, jump_pos)
        state.patch_position(patch_pos, state.get_position())


class If(AstNode):
    def __init__(self, expr, block, srcpos):
        AstNode.__init__(self, srcpos)
        self.expr = expr
        self.block = block

    def compile(self, state):
        self.expr.compile(state)
        state.emit(self.expr.getendidx(), opcodes.JUMP_IF_FALSE, 0)
        patch_pos = state.get_patch_position()
        for item in self.block:
            item.compile(state)
        state.patch_position(patch_pos, state.get_position())


class TryExcept(AstNode):
    def __init__(self, block, except_blocks, srcpos):
        AstNode.__init__(self, srcpos)
        self.block = block
        last_exc_block = except_blocks[-1]
        self.else_clause = None
        self.finally_clause = None
        if isinstance(last_exc_block, FinallyClause):
            if last_exc_block.is_else():
                self.else_clause = last_exc_block
            else:
                self.finally_clause = last_exc_block
            self.except_blocks = except_blocks[:-1]
        else:
            self.except_blocks = except_blocks

    def compile(self, state):
        """ A bit of complicated logic, but we want something like that:

        push_resume_stack <label1>
        try_block
        jump <label2>
        <label1>
        except blocks
        <label2>
        finally_block

        -or-

        push_resume_stack <label1>
        try_block
        jump <label2>
        <label1>
        except blocks
        jump <label3>
        <label2>
        else_block
        <label3>


        """
        state.emit(self.getstartidx(), opcodes.PUSH_RESUME_STACK, 0)
        pos = state.get_patch_position()
        for item in self.block:
            item.compile(state)
        if self.block:
            idx = self.block[-1].getendidx()
        else:
            idx = self.getstartidx()
        state.emit(idx, opcodes.POP_RESUME_STACK)
        state.emit(idx, opcodes.JUMP_ABSOLUTE, 0)
        jump_pos = state.get_patch_position()
        state.patch_position(pos, state.get_position())
        if self.else_clause is None:
            state.accumulator.append([jump_pos])
            for item in self.except_blocks:
                item.compile(state)
            for pos in state.accumulator[-1]:
                state.patch_position(pos, state.get_position())
            if self.finally_clause is not None:
                self.finally_clause.compile(state)
            state.emit(self.getendidx(), opcodes.RERAISE)
            state.accumulator.pop()
        else:
            assert self.finally_clause is None
            # no support for else and finally for now
            state.accumulator.append([])
            for item in self.except_blocks:
                item.compile(state)
            for pos in state.accumulator[-1]:
                state.patch_position(pos, state.get_position())
            state.emit(self.getendidx(), opcodes.RERAISE)
            state.accumulator.pop()
            state.emit(self.else_clause.getstartidx(), opcodes.JUMP_ABSOLUTE, 0)
            pos = state.get_patch_position()
            state.patch_position(jump_pos, state.get_position())
            self.else_clause.compile(state)
            state.patch_position(pos, state.get_position())


class Raise(AstNode):
    def __init__(self, expr, srcpos):
        AstNode.__init__(self, srcpos)
        self.expr = expr

    def compile(self, state):
        self.expr.compile(state)
        state.emit(self.expr.getstartidx(), opcodes.RAISE)


class Statement(AstNode):
    def __init__(self, expr, srcpos):
        AstNode.__init__(self, srcpos)
        self.expr = expr

    def compile(self, state):
        if self.expr:
            self.expr.compile(state)
            state.emit(self.expr.getstartidx(), opcodes.DISCARD)


class Getattr(AstNode):
    def __init__(self, lhand, identifier, srcpos):
        AstNode.__init__(self, srcpos)
        self.lhand = lhand
        self.identifier = identifier

    def compile(self, state):
        self.lhand.compile(state)
        no = state.add_str_constant(self.identifier)
        state.emit(self.lhand.getendidx(), opcodes.GETATTR, no)


class Setattr(AstNode):
    def __init__(self, lhand, identifier, rhand, srcpos):
        AstNode.__init__(self, srcpos)
        self.lhand = lhand
        self.identifier = identifier
        self.rhand = rhand

    def compile(self, state):
        self.lhand.compile(state)
        self.rhand.compile(state)
        no = state.add_str_constant(self.identifier)
        state.emit(self.rhand.getendidx(), opcodes.SETATTR, no)


class Getitem(AstNode):
    def __init__(self, lhand, expr, srcpos):
        AstNode.__init__(self, srcpos)
        self.lhand = lhand
        self.expr = expr

    def compile(self, state):
        self.lhand.compile(state)
        self.expr.compile(state)
        state.emit(self.lhand.getendidx(), opcodes.GETITEM)


class Setitem(AstNode):
    def __init__(self, lhand, expr, rhand, srcpos):
        AstNode.__init__(self, srcpos)
        self.lhand = lhand
        self.expr = expr
        self.rhand = rhand

    def compile(self, state):
        self.lhand.compile(state)
        self.expr.compile(state)
        self.rhand.compile(state)
        state.emit(self.rhand.getendidx(), opcodes.SETITEM)


class Arg(AstNode):
    def __init__(self, name, tp, default, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.name = name
        self.tp = tp
        self.default = default

    def compile(self, state):
        raise NotImplementedError("XXX")


class ArgsPartial(AstNode):
    def __init__(self, args):
        self.args = args

    def get_args(self):
        return self.args


class ArgList(AstNode):
    def __init__(self, arglist, srcpos):
        AstNode.__init__(self, srcpos)
        self.arglist = arglist

    def get_args(self):
        return self.arglist


class FunctionBody(AstNode):
    def __init__(self, elem, next):
        self.elem = elem
        self.next = next

    def get_element_list(self):
        count = 0
        cur = self
        while cur.next is not None:
            if cur.elem is not None:
                count += 1
            cur = cur.next
            assert isinstance(cur, FunctionBody)
        if cur.elem is not None:
            count += 1
        cur = self
        lst = [None] * count
        i = len(lst) - 1
        while cur.next is not None:
            if cur.elem is not None:
                lst[i] = cur.elem
                i -= 1
            cur = cur.next
            assert isinstance(cur, FunctionBody)
        if cur.elem is not None:
            lst[i] = cur.elem
        return lst


class VarDeclaration(AstNode):
    def __init__(self, vars, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.vars = vars

    def compile(self, state):
        for var in self.vars:
            state.register_variable(var.name, var.tp)

    def add_global_symbols(self, space, class_elements_w, source, w_mod):
        pass  # handled somewhere else


class Identifier(AstNode):
    def __init__(self, name, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.name = name

    def compile(self, state):
        op, no = state.get_variable(self.name)
        state.emit(self.getstartidx(), op, no)


class Assignment(AstNode):
    def __init__(self, varname, expr, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.varname = varname
        self.expr = expr

    def compile(self, state):
        self.expr.compile(state)
        op, varno = state.get_variable(self.varname)
        if op == opcodes.LOAD_GLOBAL:
            raise StoringIntoGlobal(self.varname)
        state.emit(self.expr.getstartidx(), opcodes.STORE, varno)


class NamedArg(AstNode):
    def __init__(self, argname, expr, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.argname = argname
        self.expr = expr

    def compile(self, state):
        self.expr.compile(state)
        no = state.add_str_constant(self.argname)
        state.emit(self.getstartidx(), opcodes.LOAD_CONSTANT, no)


class ArgListPartial(AstNode):
    def __init__(self, args, named_args):
        self.args = args
        self.named_args = named_args

    def get_arg_list(self):
        return self.args

    def get_named_arg_list(self):
        return self.named_args


class Call(AstNode):
    def __init__(self, expr, arglist, named_args, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.left_hand = expr
        self.arglist = arglist
        self.named_args = named_args

    def compile(self, state):
        self.left_hand.compile(state)
        for named_arg in self.named_args:
            named_arg.compile(state)
        for arg in self.arglist:
            arg.compile(state)
        state.emit(self.left_hand.getendidx(), opcodes.CALL, len(self.arglist), len(self.named_args))


class Return(AstNode):
    def __init__(self, expr, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.expr = expr

    def compile(self, state):
        self.expr.compile(state)
        state.emit(self.getstartidx(), opcodes.RETURN)


class ExpressionListPartial(AstNode):
    def __init__(self, elements):
        self.elements = elements

    def get_element_list(self):
        return self.elements


class VarDeclPartial(AstNode):
    def __init__(self, name, tp, next, srcpos):
        AstNode.__init__(self, srcpos)
        self.name = name
        self.tp = tp
        self.next = next

    def get_vars(self):
        i = 0
        cur = self
        while cur.next:
            cur = cur.next
            assert isinstance(cur, VarDeclPartial)
            i += 1
        vars = [None] * i
        i = 0
        cur = self
        while cur.next:
            vars[i] = Var(cur.name, cur.tp, srcpos=cur.getsrcpos())
            i += 1
            cur = cur.next
            assert isinstance(cur, VarDeclPartial)
        return vars


class Var(AstNode):
    def __init__(self, name, tp, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.name = name
        self.tp = tp


class BaseTypeDecl(AstNode):
    def __init__(self, name, srcpos):
        AstNode.__init__(self, srcpos)
        self.name = name


class NoTypeDecl(AstNode):
    pass


class ExceptClause(AstNode):
    def __init__(self, exception_names, varname, block, srcpos):
        AstNode.__init__(self, srcpos)
        self.exception_names = exception_names
        self.varname = varname
        self.block = block

    def compile(self, state):
        no = state.register_exception_setup(self.exception_names)
        state.emit(self.getstartidx(), opcodes.COMPARE_EXCEPTION, no, 0)
        pos = state.get_patch_position()
        if self.varname is not None:
            state.emit(self.getstartidx(), opcodes.PUSH_CURRENT_EXC)
            no = state.register_variable(self.varname, None)
            state.emit(self.getstartidx(), opcodes.STORE, no)
        for item in self.block:
            item.compile(state)
        idx = self.getendidx()
        state.emit(idx, opcodes.CLEAR_CURRENT_EXC)
        state.emit(idx, opcodes.JUMP_ABSOLUTE, 0)
        state.accumulator[-1].append(state.get_patch_position())
        state.patch_position(pos, state.get_position())


class BaseExcNode(AstNode):
    def gather_list(self):
        count = 1
        cur = self
        while cur.next is not None:
            cur = cur.next
            assert isinstance(cur, BaseExcNode)
            count += 1
        lst = [None] * count
        lst[0] = self.get_exc_clause()
        pos = 1
        cur = self
        while cur.next is not None:
            cur = cur.next
            assert isinstance(cur, BaseExcNode)
            lst[pos] = cur.get_exc_clause()
            pos += 1
        return lst


class ExceptClauseList(BaseExcNode):
    def __init__(self, exception_names, varname, block, next, srcpos):
        self.exception_names = exception_names
        self.varname = varname
        self.block = block
        self.next = next
        self.clause_srcpos = srcpos

    def get_exc_clause(self):
        return ExceptClause(
            self.exception_names, self.varname, self.block, self.clause_srcpos)


class FinallyClause(BaseExcNode):
    next = None

    def __init__(self, block, is_else, srcpos):
        AstNode.__init__(self, srcpos)
        self._is_else = is_else
        self.block = block

    def is_else(self):
        return self._is_else

    def compile(self, state):
        for item in self.block:
            item.compile(state)

    def get_exc_clause(self):
        return self


class Import(AstNode):
    def __init__(self, import_part, names, srcpos=None):
        AstNode.__init__(self, srcpos)
        self.import_part = import_part
        self.names = names

    def add_name(self, mapping):
        if not self.names:
            names = self.import_part
        else:
            names = self.names
        for name in names:
            if name in mapping:
                raise NameAlreadyDefined(name)
            mapping[name] = len(mapping)

    def add_missing_imports(self, space, w_mod, globals_w, importer):
        idx = globals_w.index(None)
        assert idx >= 0
        importer.import_names(space, self.import_part, self.names,
                              globals_w, idx)

    def add_global_symbols(self, space, globals_w, source, w_mod):
        if self.names is None:
            globals_w.append(None)
        else:
            globals_w.extend([None] * len(self.names))


class IdentifierListPartial(AstNode):
    def __init__(self, name, next, extra=None):
        self.name = name
        self.next = next
        self.extra = extra

    def get_names(self):
        count = 0
        cur = self
        while cur is not None:
            count += 1
            assert isinstance(cur, IdentifierListPartial)
            cur = cur.next
        lst = [None] * count
        i = 0
        cur = self
        while cur is not None:
            assert isinstance(cur, IdentifierListPartial)
            lst[i] = cur.name
            cur = cur.next
            i += 1
        return lst
