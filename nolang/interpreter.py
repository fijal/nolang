""" This is the main interpreter file that contains bytecode
dispatch loop.
"""
from rpython.rlib.rstring import StringBuilder

from nolang import opcodes
from nolang.error import AppError
from nolang.builtins.exception import W_Exception


class InvalidOpcode(Exception):
    def __init__(self, opcode):
        self.opcode = opcode

    def __str__(self):
        try:
            return "<UnimplementedOpcode %s>" % opcodes.opcodes[self.opcode].name
        except IndexError:
            return "<InvalidOpcode %d>" % self.opcode


class UninitializedVariable(Exception):
    pass  # XXX add logic to present the error


class Interpreter(object):
    def __init__(self):
        self.topframeref = None

    def interpret(self, space, bytecode, frame):
        back = self.topframeref
        try:
            self.topframeref = frame
            return self._interpret(space, bytecode, frame)
        finally:
            self.topframeref = back

    def _interpret(self, space, bytecode, frame):
        index = 0
        # make annotator happy
        arg0 = 0
        arg1 = 0
        bc = bytecode.bytecode
        cur_exc = None
        while True:
            try:
                op = ord(bc[index])
                numargs = opcodes.opcodes[op].numargs
                if numargs >= 1:
                    arg0 = (ord(bc[index + 1]) << 8) + ord(bc[index + 2])
                if numargs >= 2:
                    arg1 = (ord(bc[index + 3]) << 8) + ord(bc[index + 4])

                if op == opcodes.LOAD_NONE:
                    frame.push(space.w_None)
                elif op == opcodes.LOAD_CONSTANT:
                    frame.push(bytecode.constants[arg0])
                elif op == opcodes.LOAD_VARIABLE:
                    self.load_variable(space, frame, index, arg0)
                elif op == opcodes.LOAD_GLOBAL:
                    self.load_global(space, frame, index, arg0)
                elif op == opcodes.LOAD_TRUE:
                    frame.push(space.w_True)
                elif op == opcodes.LOAD_FALSE:
                    frame.push(space.w_False)
                elif op == opcodes.DISCARD:
                    frame.pop()
                elif op == opcodes.ADD:
                    self.binop_add(space, frame)
                elif op == opcodes.SUB:
                    self.binop_sub(space, frame)
                elif op == opcodes.MUL:
                    self.binop_mul(space, frame)
                elif op == opcodes.TRUEDIV:
                    self.binop_truediv(space, frame)
                elif op == opcodes.LT:
                    self.binop_lt(space, frame)
                elif op == opcodes.GT:
                    self.binop_gt(space, frame)
                elif op == opcodes.LE:
                    self.binop_le(space, frame)
                elif op == opcodes.GE:
                    self.binop_ge(space, frame)
                elif op == opcodes.EQ:
                    self.binop_eq(space, frame)
                elif op == opcodes.NE:
                    self.binop_ne(space, frame)
                elif op == opcodes.IN:
                    self.binop_in(space, frame)
                elif op == opcodes.NOT:
                    self.unaryop_not(space, frame)
                elif op == opcodes.STORE:
                    frame.store_var(arg0)
                elif op == opcodes.SETATTR:
                    self.setattr(space, frame, bytecode, arg0)
                elif op == opcodes.GETATTR:
                    self.getattr(space, frame, bytecode, arg0)
                elif op == opcodes.SETITEM:
                    self.setitem(space, frame)
                elif op == opcodes.GETITEM:
                    self.getitem(space, frame)
                elif op == opcodes.PUSH_RESUME_STACK:
                    self.push_resume_stack(space, frame, bytecode, arg0)
                elif op == opcodes.POP_RESUME_STACK:
                    self.pop_resume_stack(frame)
                elif op == opcodes.RAISE:
                    w_exception = frame.pop()
                    if not isinstance(w_exception, W_Exception):
                        raise Exception("handle this correctly")
                    w_exception.frame = frame
                    raise AppError(w_exception)
                elif op == opcodes.COMPARE_EXCEPTION:
                    index = self.compare_exception(space, frame,
                               bytecode, arg0, arg1, cur_exc, index)
                    continue
                elif op == opcodes.RERAISE:
                    if cur_exc:
                        raise AppError(cur_exc)
                elif op == opcodes.PUSH_CURRENT_EXC:
                    frame.push(cur_exc)
                elif op == opcodes.JUMP_IF_FALSE:
                    if not space.is_true(frame.pop()):
                        index = arg0
                        continue
                elif op == opcodes.JUMP_IF_TRUE_NOPOP:
                    if space.is_true(frame.peek()):
                        index = arg0
                        continue
                elif op == opcodes.JUMP_IF_FALSE_NOPOP:
                    if not space.is_true(frame.peek()):
                        index = arg0
                        continue
                elif op == opcodes.JUMP_ABSOLUTE:
                    index = arg0
                    continue
                elif op == opcodes.CALL:
                    self.call(space, frame, index, arg0, arg1)
                elif op == opcodes.RETURN:
                    return frame.pop()
                elif op == opcodes.LIST_BUILD:
                    self.list_build(space, frame, bytecode, arg0)
                elif op == opcodes.DICT_BUILD:
                    self.dict_build(space, frame, bytecode, arg0)
                elif op == opcodes.TEXT_BUILD:
                    self.text_build(space, frame, bytecode, arg0)
                else:
                    raise InvalidOpcode(op)

                if numargs == 0:
                    index += 1
                elif numargs == 1:
                    index += 3
                else:
                    index += 5
            except AppError as ae:
                ae.record_position(frame, bytecode, index)
                res = self.handle_error(space, frame, ae.w_exception)
                if res:
                    cur_exc = ae.w_exception
                    frame.stack_depth = 0  # clear stack
                    index = res
                    continue
                raise ae  # reraise the error if not handled

    def handle_error(self, space, frame, w_exception):
        if frame.resume_stack_depth:
            frame.resume_stack_depth -= 1
            r = frame.resume_stack[frame.resume_stack_depth]
            return r
        return 0

    def compare_exception(self, space, frame, bytecode, arg0, arg1, cur_exc,
                          cur_pos):
        block = bytecode.exception_blocks[arg0]
        if block.match(space, cur_exc):
            return cur_pos + 5
        return arg1

    def load_variable(self, space, frame, bytecode_index, no):
        w_res = frame.locals_w[no]
        if w_res is None:
            raise UninitializedVariable()
        frame.push(w_res)

    def load_global(self, space, frame, bytecode_index, no):
        frame.push(frame.globals_w[no])

    def call(self, space, frame, bytecode_index, num_args, num_named):
        args = [None] * num_args
        for i in range(num_args - 1, -1, -1):
            args[i] = frame.pop()
        named_args = [(None, None)] * num_named
        for i in range(num_named - 1, -1, -1):
            named_args[i] = (space.utf8_w(frame.pop()), frame.pop())
        w_callable = frame.pop()
        frame.push(space.call(w_callable, args, named_args))

    def list_build(self, space, frame, bytecode, no):
        items = [None] * no
        for i in range(no - 1, -1, -1):
            items[i] = frame.pop()
        frame.push(space.newlist(items))

    def dict_build(self, space, frame, bytecode, no):
        no = no / 2
        items = [(None, None)] * no
        for i in range(no - 1, -1, -1):
            v = frame.pop()
            k = frame.pop()
            items[i] = (k, v)
        frame.push(space.newdict(items))

    def text_build(self, space, frame, bytecode, no):
        items = [None] * no
        for i in range(no - 1, -1, -1):
            items[i] = space.str(frame.pop())
        sb = StringBuilder()
        for item in items:
            sb.append(item)
        frame.push(space.newtext(sb.build()))

    def setattr(self, space, frame, bytecode, no):
        w_arg = frame.pop()
        w_lhand = frame.pop()
        space.setattr(w_lhand, space.utf8_w(bytecode.constants[no]), w_arg)

    def getattr(self, space, frame, bytecode, no):
        w_lhand = frame.pop()
        frame.push(space.getattr(w_lhand, space.utf8_w(bytecode.constants[no])))

    def setitem(self, space, frame):
        w_arg = frame.pop()
        w_idx = frame.pop()
        w_lhand = frame.pop()
        space.setitem(w_lhand, w_idx, w_arg)

    def getitem(self, space, frame):
        w_idx = frame.pop()
        w_lhand = frame.pop()
        frame.push(space.getitem(w_lhand, w_idx))

    def push_resume_stack(self, space, frame, bytecode, arg0):
        frame.resume_stack[frame.resume_stack_depth] = arg0
        frame.resume_stack_depth += 1

    def pop_resume_stack(self, frame):
        frame.resume_stack_depth -= 1

    def binop_lt(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_lt(w_left, w_right))

    def binop_gt(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_gt(w_left, w_right))

    def binop_le(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_le(w_left, w_right))

    def binop_ge(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_ge(w_left, w_right))

    def binop_eq(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_eq(w_left, w_right))

    def binop_ne(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_ne(w_left, w_right))

    def binop_in(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_in(w_left, w_right))

    def binop_add(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_add(w_left, w_right))

    def binop_sub(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_sub(w_left, w_right))

    def binop_mul(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_mul(w_left, w_right))

    def binop_truediv(self, space, frame):
        w_right = frame.pop()
        w_left = frame.pop()
        frame.push(space.binop_truediv(w_left, w_right))

    def unaryop_not(self, space, frame):
        w_obj = frame.pop()
        frame.push(space.unaryop_not(w_obj))
