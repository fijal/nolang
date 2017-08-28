from nolang.error import AppError
from support import BaseTest


class TestDict(BaseTest):
    def test_empty_dict(self):
        w_res = self.interpret_expr('return {};')
        assert self.space.type(w_res) is self.space.builtin_dict['Dict']
        assert self.space.len(w_res) == 0

    def test_short_dict(self):
        w_res = self.interpret_expr('return {"a": "foo", 1: "bar"};')
        space = self.space
        assert space.len(w_res) == 2
        assert space.utf8_w(space.getitem(w_res, space.newtext('a'))) == "foo"
        assert space.utf8_w(space.getitem(w_res, space.newint(1))) == "bar"

    def test_trailing_comma(self):
        w_res = self.interpret_expr('return {"a": "foo", 1: "bar",};')
        space = self.space
        assert space.len(w_res) == 2
        assert space.utf8_w(space.getitem(w_res, space.newtext('a'))) == "foo"
        assert space.utf8_w(space.getitem(w_res, space.newint(1))) == "bar"

    def test_multiple_trailing_commas(self):
        self.assert_expr_parse_error('return {,};')
        self.assert_expr_parse_error('return {"a": "foo", 1: "bar",,};')
        self.assert_expr_parse_error('return {"a": "foo",, 1: "bar"};')
        self.assert_expr_parse_error('return {, "a": "foo", 1: "bar"};')

    def test_constructor(self):
        w_res = self.interpret_expr('return Dict({});')
        assert self.space.type(w_res) is self.space.builtin_dict['Dict']
        assert self.space.len(w_res) == 0
        w_res = self.interpret_expr('return Dict({"a": "foo", 1: "bar"});')
        space = self.space
        assert space.len(w_res) == 2
        assert space.utf8_w(space.getitem(w_res, space.newtext('a'))) == "foo"
        assert space.utf8_w(space.getitem(w_res, space.newint(1))) == "bar"

    def test_constructor_copies(self):
        w_res = self.interpret_expr('''
            var x, y;
            x = {0: "a", 1: "b"};
            y = Dict(x);
            y[2] = "c";
            return [len(x), len(y)];
        ''')
        [w_xl, w_yl] = self.space.listview(w_res)
        assert self.space.int_w(w_xl) == 2
        assert self.space.int_w(w_yl) == 3

    def test_len(self):
        w_res = self.interpret_expr('return len({});')
        assert self.space.int_w(w_res) == 0
        w_res = self.interpret_expr('return len({"a": "foo", 1: "bar"});')
        assert self.space.int_w(w_res) == 2

    def test_get(self):
        w_res = self.interpret_expr('return {"a": "foo"}.get("a", "dflt");')
        assert self.space.utf8_w(w_res) == "foo"
        w_res = self.interpret_expr('return {"a": "foo"}.get("b", "dflt");')
        assert self.space.utf8_w(w_res) == "dflt"
        w_res = self.interpret_expr('return {"a": "foo"}.get("b", default="dflt");')
        assert self.space.utf8_w(w_res) == "dflt"

    def test_get_no_default(self):
        w_res = self.interpret_expr('return {"a": "foo"}.get("a");')
        assert self.space.utf8_w(w_res) == "foo"
        w_res = self.interpret_expr('return {"a": "foo"}.get("b");')
        assert w_res is self.space.w_None

    def test_getitem(self):
        w_res = self.interpret_expr('''
            return {
                "a": "foo",
                1: "bar"
            }[1];
        ''')
        assert self.space.utf8_w(w_res) == "bar"

    def test_setitem(self):
        w_res = self.interpret_expr('''
            var x;
            x = {
                "a": "foo",
                1: "bar"
            };
            x["c"] = "baz";
            return x;
        ''')
        space = self.space
        assert self.space.len(w_res) == 3
        assert space.utf8_w(space.getitem(w_res, space.newtext("c"))) == "baz"

    def test_in(self):
        w_res = self.interpret_expr('return "a" in {"a": 0, "b": 1};')
        assert w_res is self.space.w_True
        w_res = self.interpret_expr('return "b" in {"a": 0, "b": 1};')
        assert w_res is self.space.w_True
        w_res = self.interpret_expr('return "c" in {"a": 0, "b": 1};')
        assert w_res is self.space.w_False

    def test_not_in(self):
        w_res = self.interpret_expr('return "c" not in {"a": 0, "b": 1};')
        assert w_res is self.space.w_True
        w_res = self.interpret_expr('return "a" not in {"a": 0, "b": 1};')
        assert w_res is self.space.w_False

    def test_getitem_missing(self):
        try:
            self.interpret_expr('return {"foo": "bar"}["baz"];')
        except AppError as ae:
            assert ae.match(self.space, self.space.w_keyerror)
            assert ae.w_exception.message == 'baz'
        else:
            raise Exception("Applevel KeyError not raised.")

    def test_execution_order(self):
        w_res = self.interpret('''
            def check(l, x) {
                l.append(x);
                return x;
            }

            def main() {
                var l;
                l = [];
                {check(l, 0): check(l, 1), check(l, 2): check(l, 3)};
                return l;
            }
        ''')
        w_ls = self.space.listview(w_res)
        assert [self.space.int_w(w) for w in w_ls] == [0, 1, 2, 3]

    def test_merge(self):
        w_res = self.interpret_expr('''
            var a, b, ab;
            a = {"a": "foo", 1: "bar"};
            b = {"b": "baz", 1: "rab"};
            ab = a.merge(b);
            return [a, b, ab];
        ''')
        space = self.space
        [w_a, w_b, w_ab] = space.listview(w_res)
        # a and b are unmodified
        assert space.len(w_a) == 2
        assert space.utf8_w(space.getitem(w_a, space.newtext("a"))) == "foo"
        assert space.utf8_w(space.getitem(w_a, space.newint(1))) == "bar"
        assert space.len(w_b) == 2
        assert space.utf8_w(space.getitem(w_b, space.newtext("b"))) == "baz"
        assert space.utf8_w(space.getitem(w_b, space.newint(1))) == "rab"
        # ab is the merged output
        assert space.len(w_ab) == 3
        assert space.utf8_w(space.getitem(w_ab, space.newtext("a"))) == "foo"
        assert space.utf8_w(space.getitem(w_ab, space.newtext("b"))) == "baz"
        assert space.utf8_w(space.getitem(w_ab, space.newint(1))) == "rab"

    def test_pop(self):
        w_res = self.interpret_expr('''
            var a;
            a = {"a": "foo", 1: "bar"};
            return [a.pop(1), a];
        ''')
        space = self.space
        [w_pval, w_a] = self.space.listview(w_res)
        assert space.utf8_w(w_pval) == "bar"
        assert space.len(w_a) == 1
        assert space.utf8_w(space.getitem(w_a, space.newtext("a"))) == "foo"

    def test_pop_missing(self):
        try:
            self.interpret_expr('{"a": "bar"}.pop("b");')
        except AppError as ae:
            assert ae.match(self.space, self.space.w_keyerror)
            assert ae.w_exception.message == 'b'
        else:
            raise Exception("Applevel KeyError not raised.")

    def test_keys(self):
        w_res = self.interpret_expr('return {"a": "foo", 1: "bar"}.keys();')
        [w_a, w_1] = self.space.listview(w_res)
        assert [self.space.utf8_w(w_a), self.space.int_w(w_1)] == ["a", 1]

    def test_values(self):
        w_res = self.interpret_expr('return {"a": "foo", 1: "bar"}.values();')
        values_w = self.space.listview(w_res)
        assert [self.space.utf8_w(w) for w in values_w] == ["foo", "bar"]
