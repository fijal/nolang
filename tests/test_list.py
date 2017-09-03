from nolang.error import AppError
from support import BaseTest


class TestList(BaseTest):
    def test_empty_list(self):
        w_res = self.interpret_expr('return [];')
        assert self.space.type(w_res) is self.space.builtin_dict['List']
        assert self.space.len(w_res) == 0

    def test_short_list(self):
        w_res = self.interpret_expr('return ["foo", "bar"];')
        space = self.space
        assert space.len(w_res) == 2
        assert space.utf8_w(space.getitem(w_res, space.newint(0))) == "foo"
        assert space.utf8_w(space.getitem(w_res, space.newint(1))) == "bar"

    def test_trailing_comma(self):
        w_res = self.interpret_expr('return ["foo", "bar",];')
        space = self.space
        assert space.len(w_res) == 2
        assert space.utf8_w(space.getitem(w_res, space.newint(0))) == "foo"
        assert space.utf8_w(space.getitem(w_res, space.newint(1))) == "bar"

    def test_extra_commas(self):
        self.assert_expr_parse_error('return [,];')
        self.assert_expr_parse_error('return ["foo", "bar",,];')
        self.assert_expr_parse_error('return ["foo", , "bar"];')
        self.assert_expr_parse_error('return [, "foo", "bar"];')

    def test_constructor(self):
        w_res = self.interpret_expr('return List([]);')
        assert self.space.type(w_res) is self.space.builtin_dict['List']
        assert self.space.len(w_res) == 0
        w_res = self.interpret_expr('return List(["foo", "bar"]);')
        space = self.space
        assert space.len(w_res) == 2
        assert space.utf8_w(space.getitem(w_res, space.newint(0))) == "foo"
        assert space.utf8_w(space.getitem(w_res, space.newint(1))) == "bar"

    def test_constructor_copies(self):
        w_res = self.interpret_expr('''
            var x, y;
            x = [0, 1, 2];
            y = List(x);
            y.append(3)
            return [len(x), len(y)];
        ''')
        [w_xl, w_yl] = self.space.listview(w_res)
        assert self.space.int_w(w_xl) == 3
        assert self.space.int_w(w_yl) == 4

    def test_len(self):
        w_res = self.interpret_expr('return len([]);')
        assert self.space.int_w(w_res) == 0
        w_res = self.interpret_expr('return len(["foo", 2]);')
        assert self.space.int_w(w_res) == 2

    def test_getitem(self):
        w_res = self.interpret_expr('return ["foo", "bar"][0];')
        assert self.space.utf8_w(w_res) == "foo"

    def test_setitem(self):
        w_res = self.interpret_expr('''
            var x;
            x = ["foo"];
            x[0] = "bar";
            return x[0];
        ''')
        assert self.space.utf8_w(w_res) == "bar"

    def test_in(self):
        assert self.interpret_expr('return "a" in ["a", "b"];') is self.space.w_True
        assert self.interpret_expr('return "b" in ["a", "b"];') is self.space.w_True
        assert self.interpret_expr('return "c" in ["a", "b"];') is self.space.w_False

    def test_not_in(self):
        assert self.interpret_expr('return "c" not in ["a", "b"];') is self.space.w_True
        assert self.interpret_expr('return "a" not in ["a", "b"];') is self.space.w_False

    def test_append(self):
        w_res = self.interpret_expr('''
            var x;
            x = ["foo"];
            x.append("bar");
            return x;
        ''')
        space = self.space
        assert space.len(w_res) == 2
        assert space.utf8_w(space.getitem(w_res, space.newint(1))) == "bar"

    def test_extend(self):
        w_res = self.interpret_expr('''
            var x;
            x = ["a", "b"];
            x.extend(["c", "d"]);
            return x;
        ''')
        list_w = self.space.listview(w_res)
        assert [self.space.utf8_w(w) for w in list_w] == ["a", "b", "c", "d"]

    def test_extend_nonlist(self):
        try:
            self.interpret_expr('["a", "b"].extend("c");')
        except AppError as ae:
            assert ae.match(self.space, self.space.w_typeerror)
            assert ae.w_exception.message == 'expected list'
        else:
            raise Exception("Applevel TypeError not raised.")

    def test_method_call_on_wrong_obj(self):
        try:
            self.interpret_expr('''
            List.append(1, 2)
            ''')
        except AppError as ae:
            if not ae.match(self.space, self.space.w_typeerror):
                raise
            assert ae.w_exception.message == "Expected List object, got Int"
        else:
            raise Exception("did not raise")

    def test_getitem_out_of_range(self):
        try:
            self.interpret_expr('return ["foo", "bar"][2];')
        except AppError as ae:
            assert ae.match(self.space, self.space.w_indexerror)
            assert ae.w_exception.message == 'list index out of range'
        else:
            raise Exception("Applevel IndexError not raised.")

    def test_getitem_index_not_int(self):
        try:
            self.interpret_expr('return ["foo", "bar"]["zero"];')
        except AppError as ae:
            assert ae.match(self.space, self.space.w_typeerror)
            assert ae.w_exception.message == 'list index must be int'
        else:
            raise Exception("Applevel TypeError not raised.")

    def test_execution_order(self):
        w_res = self.interpret('''
            def check(l, x) {
                l.append(x);
                return x;
            }

            def main() {
                var l;
                l = [];
                [
                    check(l, 0),
                    check(l, 1)
                ];
                return l;
            }
        ''')
        [w_0, w_1] = self.space.listview(w_res)
        assert [self.space.int_w(w_0), self.space.int_w(w_1)] == [0, 1]
