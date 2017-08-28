""" Class containing convinient shortcut for calling all things
on objects
"""

from nolang.error import AppError
from nolang.objects.root import W_None, W_Root
from nolang.objects.int import W_IntObject
from nolang.objects.bool import W_BoolObject
from nolang.objects.buffer import W_BufObject
from nolang.objects.dict import W_DictObject
from nolang.objects.list import W_ListObject
from nolang.objects.unicode import W_StrObject
from nolang.objects.usertype import W_UserType
from nolang.builtins.spec import wrap_builtin
from nolang.builtins.exception import W_Exception


class Space(object):
    def __init__(self):
        self.w_None = W_None()  # singleton
        self.w_True = W_BoolObject(True)
        self.w_False = W_BoolObject(False)
        self.w_NotImplemented = W_Root()

    def setup(self, interpreter):
        self.interpreter = interpreter

    def setup_builtins(self, builtins, coremod, non_builtins):
        self.builtins_w = []
        self.builtin_dict = {}
        for builtin in builtins:
            self.setup_builtin(wrap_builtin(self, builtin))
        self.coremod = coremod
        for non_builtin in non_builtins:
            wrap_builtin(self, non_builtin)
        self.w_exception = self.builtin_dict['Exception']
        self.w_indexerror = self.make_exception('IndexError')
        self.w_typeerror = self.make_exception('TypeError')
        self.w_argerror = self.make_exception('ArgumentError')
        self.w_attrerror = self.make_exception('AttributeError')
        self.w_keyerror = self.make_exception('KeyError')

    def setup_builtin(self, builtin):
        self.builtins_w.append(builtin)
        self.builtin_dict[builtin.name] = builtin
        return builtin

    def make_subclass(self, w_tp, name):
        return W_UserType(w_tp.allocate, name, [], w_tp, w_tp.default_alloc)

    def make_exception(self, name, parent=None):
        if parent is None:
            parent = self.w_exception
        return self.setup_builtin(self.make_subclass(parent, name))

    def setattr(self, w_obj, attrname, w_value):
        w_obj.setattr(self, attrname, w_value)

    def getattr(self, w_obj, attrname):
        w_res = w_obj.getattr(self, attrname)
        if w_res is self.w_NotImplemented:
            return self.getattr(self.type(w_obj), attrname).bind(self, w_obj)
        return w_res

    def setitem(self, w_obj, w_index, w_value):
        w_obj.setitem(self, w_index, w_value)

    def getitem(self, w_obj, w_index):
        return w_obj.getitem(self, w_index)

    def str(self, w_obj):
        return w_obj.str(self)

    def len(self, w_obj):
        return w_obj.len(self)

    def hash(self, w_obj):
        return w_obj.hash(self)

    def key_eq(self, w_one, w_two):
        return self.is_true(self.binop_eq(w_one, w_two))

    # object stuff, hacks so far
    def issubclass(self, w_left, w_right):
        return w_left.issubclass(w_right)

    def type(self, w_obj):
        # for builtin types we know exactly what type is it based on class
        return w_obj.gettype(self)

    # newfoo wrappers
    def newint(self, intval):
        return W_IntObject(intval)

    def newbool(self, boolval):
        if boolval:
            return self.w_True
        return self.w_False

    def newtext(self, utf8val):
        return W_StrObject(utf8val)

    def newbuf(self, charsval):
        return W_BufObject(charsval)

    def newlist(self, items_w):
        return W_ListObject(items_w)

    def newdict(self, items_w):
        return W_DictObject(self.key_eq, self.hash, items_w)

    # foo_w unwrappers
    def int_w(self, w_obj):
        return w_obj.int_w(self)

    def utf8_w(self, w_obj):
        return w_obj.utf8_w(self)

    def buffer_w(self, w_obj):
        return w_obj.buffer_w(self)

    def listview(self, w_obj):
        return w_obj.listview(self)

    def dictview(self, w_obj):
        return w_obj.dictview(self)

    # unary operations
    def is_true(self, w_obj):
        return w_obj.is_true(self)

    def unaryop_not(self, w_obj):
        return self.newbool(not self.is_true(w_obj))

    # binary operations
    def binop_lt(self, w_one, w_two):
        return w_one.lt(self, w_two)

    def binop_gt(self, w_one, w_two):
        # Implemented in terms of lt and eq.
        return self.newbool(not (
            self.is_true(self.binop_lt(w_one, w_two)) or
            self.is_true(self.binop_eq(w_one, w_two))))

    def binop_le(self, w_one, w_two):
        # Implemented in terms of lt and eq.
        return self.newbool(
            self.is_true(self.binop_lt(w_one, w_two)) or
            self.is_true(self.binop_eq(w_one, w_two)))

    def binop_ge(self, w_one, w_two):
        # Implemented in terms of lt and eq.
        return self.newbool(not self.is_true(self.binop_lt(w_one, w_two)))

    def binop_eq(self, w_one, w_two):
        w_res = w_one.eq(self, w_two)
        if w_res is not self.w_NotImplemented:
            return w_res
        w_res = w_two.eq(self, w_one)
        if w_res is not self.w_NotImplemented:
            return w_res
        return self.w_False

    def binop_ne(self, w_one, w_two):
        # Implemented in terms of lt and eq.
        return self.unaryop_not(self.binop_eq(w_one, w_two))

    def binop_in(self, w_one, w_two):
        return w_two.contains(self, w_one)

    def binop_add(self, w_one, w_two):
        return w_one.add(self, w_two)

    def binop_sub(self, w_one, w_two):
        return w_one.sub(self, w_two)

    def binop_mul(self, w_one, w_two):
        return w_one.mul(self, w_two)

    def binop_truediv(self, w_one, w_two):
        return w_one.truediv(self, w_two)

    # various calls
    def call_method(self, w_object, method_name, args, named_args):
        w_obj = w_object.getattr(self, method_name)
        return w_obj.call(self, self.interpreter, args, named_args)

    def call(self, w_object, args, named_args):
        return w_object.call(self, self.interpreter, args, named_args)

    # exceptions
    def apperr(self, w_type_error, msg):
        return AppError(W_Exception(w_type_error, msg))
