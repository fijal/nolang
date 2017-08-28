""" Main declaration of function
"""

from nolang.objects.root import W_Root
from nolang.frameobject import Frame


class FuncArg(object):
    def __init__(self, name, tp, default):
        self.name = name
        self.tp = tp
        self.default = default

    def __repr__(self):
        return "<FuncArg %s %s %s>" % (self.name, self.tp, self.default)


class _W_FunctionBase(W_Root):
    def argerr(self, space, msg):
        return space.apperr(space.w_argerror, msg)

    def prepare_args(self, space, arglist, args_w, namedargs_w):
        num_args = len(arglist)
        if len(args_w) + len(namedargs_w) > num_args:
            raise self.argerr(
                space, "Function %s got %d arguments, expected %d" % (
                    self.name, len(args_w) + len(namedargs_w), num_args))
        valdict = {}
        for i in range(num_args):
            name = arglist[i].name
            valdict[name] = None
        for i in range(min(len(args_w), num_args)):
            valdict[arglist[i].name] = args_w[i]
        for i in range(len(namedargs_w)):
            name, val = namedargs_w[i]
            if name not in valdict:
                raise self.argerr(
                    space, "Function %s got unexpected keyword argument '%s'" % (
                        self.name, name))
            if valdict[name] is not None:
                raise self.argerr(
                    space, "Function %s got multiple values for argument '%s'" % (
                        self.name, name))
            valdict[name] = val
        for i in range(num_args):
            name = arglist[i].name
            if valdict[name] is None:
                valdict[name] = arglist[i].default
        missing = 0
        argvals_w = [None] * num_args
        for i in range(num_args):
            name = arglist[i].name
            val = valdict[name]
            if val is None:
                missing += 1
            argvals_w[i] = valdict[name]
        if missing > 0:
            raise self.argerr(
                space, "Function %s got %d arguments, expected %d" % (
                    self.name, num_args - missing, num_args))
        return argvals_w


class W_Function(_W_FunctionBase):
    def __init__(self, name, bytecode):
        self.name = name
        self.bytecode = bytecode

    def setup(self, space):
        self.bytecode.setup(space)
        self.arglist = [None] * len(self.bytecode.arglist)
        for i in range(len(self.arglist)):
            default = None
            # XXX Temporary hack to get an int value (the only type of default
            # we support for now) out of the raw uncompiled AST object we have
            # here.
            astarg = self.bytecode.arglist[i]
            if astarg.default is not None:
                default = space.newint(astarg.default.getintvalue())
            self.arglist[i] = FuncArg(astarg.name, astarg.tp, default)

    def call(self, space, interpreter, args_w, namedargs_w):
        frame = Frame(self.bytecode, self.name)
        frame.populate_args(self.prepare_args(
            space, self.arglist, args_w, namedargs_w))
        return interpreter.interpret(space, self.bytecode, frame)

    def bind(self, space, w_obj):
        return W_BoundMethod(w_obj, self)


class W_BuiltinFunction(_W_FunctionBase):
    def __init__(self, name, callable, arglist):
        self.name = name
        self.arglist = arglist
        self.callable = callable

    def setup(self, space):
        pass

    def call(self, space, interpreter, args_w, namedargs_w):
        if self.arglist is None:
            if len(namedargs_w) > 0:
                raise self.argerr(
                    space, "Function %s does not support keyword arguments" % (
                        self.name,))
            return self.callable(space, args_w)
        return self.callable(space, self.prepare_args(
            space, self.arglist, args_w, namedargs_w))

    def bind(self, space, w_obj):
        return W_BoundMethod(w_obj, self)

    def __repr__(self):
        return "<BuiltinFunction %s/%d>" % (self.name, self.num_args)


class W_Property(W_Root):
    def __init__(self, name, getter, setter):
        self.name = name
        self.getter = getter
        self.setter = setter

    def bind(self, space, w_obj):
        return self.getter(w_obj, space)

    def setup(self, space):
        pass


class W_BoundMethod(W_Root):
    def __init__(self, w_self, w_function):
        self.w_self = w_self
        self.w_function = w_function

    def call(self, space, interpreter, args_w, namedargs_w):
        return space.call(self.w_function, [self.w_self] + args_w, namedargs_w)
