""" Basic declaration of user type defined with class
"""

from nolang.objects.root import W_Root


class W_UserType(W_Root):
    def __init__(self, allocate, name, class_elements_w, w_parent,
                 default_alloc=True, force_names=None):
        self.name = name
        self.allocate = allocate
        self.class_elements_w = class_elements_w
        self.default_alloc = default_alloc
        if w_parent is not None:
            self._dict_w = w_parent._dict_w.copy()
        else:
            self._dict_w = {}
        for item in class_elements_w:
            self._dict_w[item.name] = item
        self.w_parent = w_parent
        if force_names is None:
            self.force_names = None
        else:
            self.force_names = {}
            for elem in force_names:
                self.force_names[elem] = None

    def setup(self, space):
        for item in self.class_elements_w:
            item.setup(space)

    def call(self, space, interpreter, args_w, namedargs_w):
        if self.allocate is None:
            raise Exception("cannot be called like that")
        w_obj = space.call(self.allocate, [self] + args_w, namedargs_w)
        if '__init__' in self._dict_w:
            space.call(self._dict_w['__init__'], [w_obj] + args_w, namedargs_w)
        elif self.default_alloc:
            if len(args_w) != 0:
                raise space.apperr(space.w_argerror, "Default constructor"
                    " expecting no arguments")
        return w_obj

    def getattr(self, space, attrname):
        return self._dict_w[attrname]

    def issubclass(self, w_type):
        cur = self
        while cur is not None:
            if cur is w_type:
                return True
            cur = cur.w_parent
        return False

    def __repr__(self):
        return "<UserType %s>" % (self.name,)
