""" Bytecode representation and compilation. See opcodes.py for
details about bytecodes
"""

from nolang import opcodes

from rpython.rlib.rstring import StringBuilder


class BaseConstant(object):
    pass


class IntegerConstant(BaseConstant):
    def __init__(self, v):
        self._intval = v

    def wrap(self, space):
        return space.newint(self._intval)


class StringConstant(BaseConstant):
    def __init__(self, v):
        self._strval = v

    def wrap(self, space):
        return space.newtext(self._strval)


class InvalidStackDepth(Exception):
    pass


class UnknownGlobalName(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "<UnknownGlobalName %s>" % self.name


class Bytecode(object):
    def __init__(self, filename, source, varnames, module, constants, bytecode,
                 arglist, exception_blocks, lnotab):
        self.filename = filename
        self.source = source
        self.varnames = varnames
        self.module = module
        self._constants = constants
        self.constants = None
        self.bytecode = bytecode
        r = self.compute_stack_depth(bytecode)
        self.stack_depth, self.resume_stack_depth = r
        self.arglist = arglist
        self.exception_blocks = exception_blocks
        self.lnotab = lnotab

    def setup(self, space):
        self.constants = [None] * len(self._constants)
        for i, constant in enumerate(self._constants):
            self.constants[i] = constant.wrap(space)

    def repr(self, numbers=True):
        i = 0
        res = StringBuilder()
        bc = self.bytecode
        while i < len(bc):
            opcode = opcodes.opcodes[ord(bc[i])]
            c = i
            if opcode.numargs == 0:
                r = "  " + opcode.name
                i += 1
            elif opcode.numargs == 1:
                argval = (ord(bc[i + 1]) << 8) + ord(bc[i + 2])
                r = "  %s %d" % (opcode.name, argval)
                i += 3
            else:
                assert opcode.numargs == 2
                arg1 = (ord(bc[i + 1]) << 8) + ord(bc[i + 2])
                arg2 = (ord(bc[i + 3]) << 8) + ord(bc[i + 4])
                r = "  %s %d %d" % (opcode.name, arg1, arg2)
                i += 5
            if numbers:
                res.append("%3d" % c + r)
            else:
                res.append(r)
            res.append("\n")
        return res.build()

    @staticmethod
    def compute_stack_depth(bc):
        i = 0
        stack_depth = 0
        max_stack_depth = 0
        resume_stack_depth = 0
        max_resume_stack_depth = 0
        while i < len(bc):
            opcode = opcodes.opcodes[ord(bc[i])]
            if opcode.stack_effect == 255:
                var = (ord(bc[i + 1]) << 8) + ord(bc[i + 2])
                var2 = (ord(bc[i + 3]) << 8) + ord(bc[i + 4])
                stack_depth -= var + 2 * var2
            elif opcode.stack_effect == 254:
                var = (ord(bc[i + 1]) << 8) + ord(bc[i + 2])
                stack_depth -= var - 1
            else:
                stack_depth += opcode.stack_effect
            if ord(bc[i]) == opcodes.PUSH_RESUME_STACK:
                resume_stack_depth += 1
                max_resume_stack_depth = max(max_resume_stack_depth,
                                             resume_stack_depth)
            if ord(bc[i]) == opcodes.POP_RESUME_STACK:
                resume_stack_depth -= 1
            if opcode.numargs == 0:
                i += 1
            elif opcode.numargs == 1:
                i += 3
            else:
                assert opcode.numargs == 2
                i += 5
            max_stack_depth = max(max_stack_depth, stack_depth)
        if stack_depth != 0 or resume_stack_depth != 0:
            raise InvalidStackDepth()
        return max_stack_depth, max_resume_stack_depth


class UndeclaredVariable(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '<UndeclaredVariable %s>' % self.name


class ExceptionBlock(object):
    def __init__(self, types_w):
        self.types_w = types_w
        self.position = 0

    def match(self, space, w_exception):
        for w_type in self.types_w:
            if space.issubclass(space.type(w_exception), w_type):
                return True
        return False


class _BytecodeBuilder(object):
    def __init__(self, w_mod, arglist):
        self.vars = {}
        self.varnames = []
        self.builder = []
        self.constants = []  # XXX implement interning of integers, strings etc.
        self.exception_blocks = []
        self.w_mod = w_mod
        for var in arglist:
            self.register_variable(var.name, var.tp)
        self.arglist = arglist
        self.lnotab = []
        self.accumulator = []

    def add_constant(self, const):
        no = len(self.constants)
        self.constants.append(const)
        return no

    def add_int_constant(self, v):
        return self.add_constant(IntegerConstant(v))

    def add_str_constant(self, v):
        return self.add_constant(StringConstant(v))

    def get_variable(self, name):
        try:
            return opcodes.LOAD_VARIABLE, self.vars[name]
        except KeyError:
            pass
        try:
            return opcodes.LOAD_GLOBAL, self.w_mod.name2index[name]
        except KeyError:
            pass
        raise UndeclaredVariable(name)

    def register_variable(self, v, tp):
        no = len(self.vars)
        self.varnames.append(no)  # XXX should we rely on dicts being ordered?
        self.vars[v] = no
        assert len(self.vars) == len(self.varnames)
        return no

    def register_exception_setup(self, exc_names):
        types_w = []
        for name in exc_names:
            try:
                no = self.w_mod.name2index[name]
            except KeyError:
                raise UnknownGlobalName(name)
            types_w.append(self.w_mod.functions[no])
        self.exception_blocks.append(ExceptionBlock(types_w))
        return len(self.exception_blocks) - 1

    def emit(self, lineno, opcode, arg0=-1, arg1=-1):
        self.lnotab.append(lineno)
        self.builder.append(chr(opcode))
        if opcodes.opcodes[opcode].numargs == 0:
            assert arg0 == -1
        else:
            assert arg0 >= 0
        if opcodes.opcodes[opcode].numargs <= 1:
            assert arg1 == -1
        else:
            assert arg1 >= 0
        assert arg0 < 0x10000
        assert arg1 < 0x10000
        numargs = opcodes.opcodes[opcode].numargs
        if numargs > 0:
            self.builder.append(chr(arg0 >> 8))
            self.builder.append(chr(arg0 & 0xff))
            self.lnotab += [0] * 2
        if numargs > 1:
            self.builder.append(chr(arg1 >> 8))
            self.builder.append(chr(arg1 & 0xff))
            self.lnotab += [0] * 2
        assert numargs <= 2

    def get_position(self):
        return len(self.builder)

    def get_patch_position(self):
        return len(self.builder) - 2

    def patch_position(self, pos, target):
        assert target < 0x10000
        self.builder[pos] = chr(target >> 8)
        self.builder[pos + 1] = chr(target & 0xff)

    def _packlnotab(self, lnotab):
        return lnotab

    def build(self, filename, source):
        return Bytecode(filename, source, self.varnames, self.w_mod,
                        self.constants,
                        "".join(self.builder), self.arglist,
                        self.exception_blocks, self._packlnotab(self.lnotab))


def compile_bytecode(ast, source, w_mod, arglist=[], startlineno=0):
    """ Compile the bytecode from produced AST.
    """
    builder = _BytecodeBuilder(w_mod, arglist[:])
    ast.compile(builder)
    # hack to enable building for now
    builder.emit(ast.getendidx(), opcodes.LOAD_NONE)
    builder.emit(ast.getendidx(), opcodes.RETURN)
    return builder.build(w_mod.name, source)
