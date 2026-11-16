import sys
import os
import random

# ==========================================
# 1. ЛЕКСЕР
# ==========================================
KEYWORDS = {
    "let", "var", "const", "if", "else", "while", "for", "in", "loop", 
    "break", "continue", "return", "say", "show", "push", "true", "false", 
    "nil", "and", "or", "not", "import", "delete", "fn"
}
PUNCT = set("(){}[],:;.")
OPS = set("+-*/%=<>!")

class Lexer:
    def __init__(self, src):
        self.src, self.pos, self.line, self.col = src, 0, 1, 1

    def advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line, self.col = self.line + 1, 1
        else:
            self.col += 1
        return ch

    def skip(self):
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch in " \t\r\n":
                self.advance()
            elif ch == "~":
                while self.pos < len(self.src) and self.src[self.pos] != "\n":
                    self.advance()
            else:
                break

    def tokenize(self):
        toks = []
        while True:
            self.skip()
            if self.pos >= len(self.src):
                toks.append(("EOF", None, self.line, self.col))
                return toks
            ch = self.src[self.pos]
            line, col = self.line, self.col
            
            if ch.isdigit():
                s = self.pos
                while self.pos < len(self.src) and (self.src[self.pos].isdigit() or self.src[self.pos] == "."):
                    self.advance()
                toks.append(("NUMBER", self.src[s:self.pos], line, col))
            elif ch in "\"'":
                q = self.advance()
                buf = []
                while self.pos < len(self.src) and self.src[self.pos] != q:
                    c = self.advance()
                    if c == "\\":
                        esc = self.advance()
                        buf.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(esc, esc))
                    else:
                        buf.append(c)
                self.advance()
                toks.append(("STRING", "".join(buf), line, col))
            elif ch.isalpha() or ch == "_":
                s = self.pos
                while self.pos < len(self.src) and (self.src[self.pos].isalnum() or self.src[self.pos] == "_"):
                    self.advance()
                w = self.src[s:self.pos]
                toks.append(("KW" if w in KEYWORDS else "IDENT", w, line, col))
            elif ch in PUNCT:
                self.advance()
                toks.append(("PUNCT", ch, line, col))
            elif ch in OPS:
                two = self.src[self.pos:self.pos + 2]
                if two in ("==", "!=", "<=", ">="):
                    self.advance(); self.advance()
                    toks.append(("OP", two, line, col))
                else:
                    self.advance()
                    toks.append(("OP", ch, line, col))
            else:
                raise SyntaxError(f"[Строка {line}, Колонка {col}] Неожиданный символ: {ch!r}")

# ==========================================
# 2. ПАРСЕР И AST
# ==========================================
class Node: pass
class Number(Node): 
    def __init__(self, v): self.value = v
class String(Node): 
    def __init__(self, v): self.value = v
class Bool(Node): 
    def __init__(self, v): self.value = v
class Nil(Node): pass
class ListLit(Node): 
    def __init__(self, items): self.items = items
class ObjectLit(Node): 
    def __init__(self, pairs): self.pairs = pairs
class Var(Node): 
    def __init__(self, n): self.name = n
class Member(Node): 
    def __init__(self, obj, name): self.obj, self.name = obj, name
class BinOp(Node): 
    def __init__(self, op, l, r): self.op, self.left, self.right = op, l, r
class UnaryOp(Node): 
    def __init__(self, op, v): self.op, self.operand = op, v
class Index(Node): 
    def __init__(self, t, i): self.target, self.index = t, i
class Call(Node): 
    def __init__(self, name, args): self.name, self.args = name, args
class FnLit(Node): 
    def __init__(self, p, b): self.params, self.body = p, b
class Assign(Node): 
    def __init__(self, n, v): self.name, self.value = n, v
class IndexAssign(Node): 
    def __init__(self, t, i, v): self.target, self.index, self.value = t, i, v
class MemberAssign(Node): 
    def __init__(self, obj, name, v): self.obj, self.name, self.value = obj, name, v
class VarDecl(Node): 
    def __init__(self, n, v, is_const=False): self.name, self.value, self.is_const = n, v, is_const
class If(Node): 
    def __init__(self, branches, else_body): self.branches, self.else_body = branches, else_body
class While(Node): 
    def __init__(self, c, b): self.cond, self.body = c, b
class ForIn(Node): 
    def __init__(self, v, it, b): self.var, self.iterable, self.body = v, it, b
class Loop(Node): 
    def __init__(self, b): self.body = b
class Break(Node): pass
class Continue(Node): pass
class Return(Node): 
    def __init__(self, v): self.value = v
class FnDecl(Node): 
    def __init__(self, n, p, b): self.name, self.params, self.body = n, p, b
class Say(Node): 
    def __init__(self, v): self.value = v
class Show(Node): 
    def __init__(self, v): self.value = v
class Push(Node): 
    def __init__(self, v): self.value = v
class ExprStmt(Node): 
    def __init__(self, e): self.expr = e
class Import(Node): 
    def __init__(self, name, specific): self.name, self.specific = name, specific
class Delete(Node): 
    def __init__(self, target, index=None, name=None): self.target, self.index, self.name = target, index, name
class Block(Node):
    def __init__(self, stmts): self.stmts = stmts

class Parser:
    def __init__(self, tokens): self.tokens, self.pos = tokens, 0
    def peek(self, k=0): return self.tokens[self.pos + k]
    def check(self, kind, value=None):
        t = self.peek()
        return t[0] == kind and (value is None or t[1] == value)
    def match(self, kind, value=None):
        if self.check(kind, value): return self.advance()
        return None
    def advance(self):
        t = self.tokens[self.pos]; self.pos += 1; return t
    def expect(self, kind, value=None):
        t = self.peek()
        if not self.check(kind, value):
            need = value if value else kind
            token_val = t[1] if t[1] is not None else "КОНЕЦ ФАЙЛА"
            raise SyntaxError(f"[Строка {t[2]}, Колонка {t[3]}] Ожидалось {need!r}, получено {token_val!r}")
        return self.advance()

    def parse(self):
        stmts = []
        while not self.check("EOF"):
            s = self.statement()
            if s is not None: stmts.append(s)
        return stmts

    def statement(self):
        if self.check("KW", "import"): return self.import_stmt()
        if self.check("KW", "fn"): return self.fn_decl()
        if self.check("KW", "var") or self.check("KW", "let") or self.check("KW", "const"): return self.var_decl()
        if self.check("KW", "if"): return self.if_stmt()
        if self.check("KW", "while"): return self.while_stmt()
        if self.check("KW", "for"): return self.for_stmt()
        if self.check("KW", "loop"): return self.loop_stmt()
        if self.check("KW", "break"):
            self.advance(); self.match("PUNCT", ";"); return Break()
        if self.check("KW", "continue"):
            self.advance(); self.match("PUNCT", ";"); return Continue()
        if self.check("KW", "return"):
            self.advance()
            v = None if self.check("PUNCT", ";") or self.check("PUNCT", "}") else self.expression()
            self.match("PUNCT", ";")
            return Return(v)
        if self.check("KW", "say"):
            self.advance(); v = self.expression(); self.match("PUNCT", ";"); return Say(v)
        if self.check("KW", "show"):
            self.advance(); v = self.expression(); self.match("PUNCT", ";"); return Show(v)
        if self.check("KW", "push"):
            self.advance(); v = self.expression(); self.match("PUNCT", ";"); return Push(v)
        if self.check("KW", "delete"):
            self.advance()
            expr = self.postfix()
            self.match("PUNCT", ";")
            if isinstance(expr, Index): return Delete(expr.target, index=expr.index)
            if isinstance(expr, Member): return Delete(expr.obj, name=expr.name)
            raise SyntaxError("delete: нужно xs[i] или p.name")
        return self.expr_stmt()

    def import_stmt(self):
        self.advance()
        name = self.expect("STRING")[1]
        specific = None
        if self.match("OP", "="):
            specific = []
            while True:
                parts = [self.expect("IDENT")[1]]
                while self.match("PUNCT", "."): parts.append(self.expect("IDENT")[1])
                specific.append(".".join(parts))
                if not self.match("PUNCT", ","): break
        self.match("PUNCT", ";")
        return Import(name, specific)

    def fn_decl(self):
        self.advance()
        name = self.expect("IDENT")[1]
        params, body = self.fn_params_and_body()
        return FnDecl(name, params, body)

    def fn_params_and_body(self):
        self.expect("PUNCT", "(")
        params = []
        if not self.check("PUNCT", ")"):
            params.append(self.expect("IDENT")[1])
            while self.match("PUNCT", ","): params.append(self.expect("IDENT")[1])
        self.expect("PUNCT", ")")
        return params, self.block()

    def var_decl(self):
        kw = self.advance()[1]
        name = self.expect("IDENT")[1]
        value = None
        if self.match("OP", "="): value = self.expression()
        self.match("PUNCT", ";")
        return VarDecl(name, value, is_const=(kw == "const"))

    def if_stmt(self):
        self.advance()
        branches = [(self.expression(), self.block())]
        else_body = None
        while self.check("KW", "else"):
            self.advance()
            if self.check("KW", "if"):
                self.advance()
                branches.append((self.expression(), self.block()))
            else:
                else_body = self.block()
                break
        return If(branches, else_body)

    def while_stmt(self):
        self.advance()
        cond = self.expression()
        return While(cond, self.block())

    def for_stmt(self):
        self.advance()
        var = self.expect("IDENT")[1]
        self.expect("KW", "in")
        it = self.expression()
        return ForIn(var, it, self.block())

    def loop_stmt(self):
        self.advance()
        return Loop(self.block())

    def block(self):
        self.expect("PUNCT", "{")
        stmts = []
        while not self.check("PUNCT", "}"):
            s = self.statement()
            if s is not None: stmts.append(s)
        self.expect("PUNCT", "}")
        return Block(stmts)

    def expr_stmt(self):
        expr = self.expression()
        if self.check("OP", "="):
            self.advance()
            value = self.expression()
            self.match("PUNCT", ";")
            if isinstance(expr, Var): return Assign(expr.name, value)
            if isinstance(expr, Index): return IndexAssign(expr.target, expr.index, value)
            if isinstance(expr, Member): return MemberAssign(expr.obj, expr.name, value)
            raise SyntaxError("нельзя присвоить в это выражение")
        self.match("PUNCT", ";")
        return ExprStmt(expr)

    def expression(self): return self.or_expr()
    def or_expr(self):
        left = self.and_expr()
        while self.check("KW", "or"):
            self.advance(); left = BinOp("or", left, self.and_expr())
        return left
    def and_expr(self):
        left = self.not_expr()
        while self.check("KW", "and"):
            self.advance(); left = BinOp("and", left, self.not_expr())
        return left
    def not_expr(self):
        if self.check("KW", "not"):
            self.advance(); return UnaryOp("not", self.not_expr())
        return self.comparison()
    def comparison(self):
        left = self.add_expr()
        while True:
            t = self.peek()
            if t[0] == "OP" and t[1] in ("==", "!=", "<", ">", "<=", ">="):
                self.advance(); left = BinOp(t[1], left, self.add_expr())
            else: return left
    def add_expr(self):
        left = self.mul_expr()
        while True:
            t = self.peek()
            if t[0] == "OP" and t[1] in ("+", "-"):
                self.advance(); left = BinOp(t[1], left, self.mul_expr())
            else: return left
    def mul_expr(self):
        left = self.unary()
        while True:
            t = self.peek()
            if t[0] == "OP" and t[1] in ("*", "/", "%"):
                self.advance(); left = BinOp(t[1], left, self.unary())
            else: return left
    def unary(self):
        t = self.peek()
        if t[0] == "OP" and t[1] == "-":
            self.advance(); return UnaryOp("-", self.unary())
        if t[0] == "OP" and t[1] == "!":
            self.advance(); return UnaryOp("not", self.unary())
        return self.postfix()
    def member_name(self, node):
        if isinstance(node, Member): return self.member_name(node.obj) + "." + node.name
        if isinstance(node, Var): return node.name
        raise SyntaxError("сложное выражение перед .")
    def postfix(self):
        expr = self.primary()
        while True:
            if self.check("PUNCT", "("):
                if isinstance(expr, Var): fname = expr.name
                elif isinstance(expr, Member): fname = self.member_name(expr)
                else: raise SyntaxError("нельзя вызвать")
                self.advance()
                args = []
                if not self.check("PUNCT", ")"):
                    args.append(self.expression())
                    while self.match("PUNCT", ","): args.append(self.expression())
                self.expect("PUNCT", ")")
                expr = Call(fname, args)
            elif self.check("PUNCT", "["):
                self.advance(); idx = self.expression(); self.expect("PUNCT", "]")
                expr = Index(expr, idx)
            elif self.check("PUNCT", "."):
                self.advance(); name = self.expect("IDENT")[1]
                expr = Member(expr, name)
            else: return expr
    def primary(self):
        t = self.peek()
        if t[0] == "NUMBER":
            self.advance()
            v = t[1]; return Number(float(v) if "." in v else int(v))
        if t[0] == "STRING": self.advance(); return String(t[1])
        if t[0] == "KW" and t[1] in ("true", "false"): self.advance(); return Bool(t[1] == "true")
        if t[0] == "KW" and t[1] == "nil": self.advance(); return Nil()
        if t[0] == "KW" and t[1] == "fn":
            self.advance(); params, body = self.fn_params_and_body(); return FnLit(params, body)
        if t[0] == "IDENT": self.advance(); return Var(t[1])
        if t[0] == "PUNCT" and t[1] == "(":
            self.advance(); e = self.expression(); self.expect("PUNCT", ")"); return e
        if t[0] == "PUNCT" and t[1] == "[":
            self.advance(); items = []
            if not self.check("PUNCT", "]"):
                items.append(self.expression())
                while self.match("PUNCT", ","):
                    if self.check("PUNCT", "]"): break
                    items.append(self.expression())
            self.expect("PUNCT", "]"); return ListLit(items)
        if t[0] == "PUNCT" and t[1] == "{":
            self.advance(); pairs = []
            if not self.check("PUNCT", "}"):
                while True:
                    kt = self.peek()
                    if kt[0] == "IDENT": self.advance(); key = kt[1]
                    elif kt[0] == "STRING": self.advance(); key = kt[1]
                    else: raise SyntaxError(f"Ожидался ключ объекта, получено: {kt[1]!r}")
                    self.expect("PUNCT", ":")
                    pairs.append((key, self.expression()))
                    if not self.match("PUNCT", ","): break
                    if self.check("PUNCT", "}"): break
            self.expect("PUNCT", "}"); return ObjectLit(pairs)
        token_val = t[1] if t[1] is not None else "КОНЕЦ ФАЙЛА"
        raise SyntaxError(f"[Строка {t[2]}, Колонка {t[3]}] Неожиданный токен: {token_val!r}")

# ==========================================
# 3. КОМПИЛЯТОР В DRINK (ПОЛНЫЙ)
# ==========================================
class DrinkCompiler:
    def __init__(self):
        self.vapor = ["§INITIATE_RITUAL§"]
        self.var_map = {}
        self.counter = 1
        self.lbl_counter = 1
        self.loop_stack = [] # Для break/continue

    def new_label(self):
        lbl = f"LBL_{self.lbl_counter}"
        self.lbl_counter += 1
        return lbl

    def compile(self, ast):
        for node in ast: 
            self.compile_node(node)
        self.vapor.append("§QUENCH_THIRST§")
        
        out = "========== LOGILOOM DRINK FILE v1.0 ==========\n"
        out += "[VAPOR_LAYER]\n" + "\n".join(self.vapor) + "\n\n"
        out += "[LIQUID_LAYER]\nSECURE_DATA_HASH_"
        out += "".join(random.choices("0123456789abcdef", k=32))
        return out

    def compile_node(self, node):
        if isinstance(node, Say):
            self.eval_expr(node.value)
            self.vapor.append("§EXHALE_VAPOR§")
            
        elif isinstance(node, Show):
            self.eval_expr(node.value)
            self.vapor.append("§SHOW_VAPOR§")

        elif isinstance(node, Push):
            self.eval_expr(node.value)
            self.vapor.append("§PUSH_STACK§")
            
        elif isinstance(node, VarDecl):
            obf = f"V{self.counter}_H2O"
            self.counter += 1
            if node.value: self.eval_expr(node.value)
            else: self.vapor.append("§DROP_POWDER::0§")
            self.vapor.append(f"§VESSEL::{obf}§")
            self.var_map[node.name] = obf
            
        elif isinstance(node, Assign):
            obf = self.var_map.get(node.name, node.name)
            self.eval_expr(node.value)
            self.vapor.append(f"§VESSEL::{obf}§")

        elif isinstance(node, IndexAssign):
            self.eval_expr(node.target)
            self.eval_expr(node.index)
            self.eval_expr(node.value)
            self.vapor.append("§INDEX_ASSIGN§")

        elif isinstance(node, MemberAssign):
            self.eval_expr(node.obj)
            self.vapor.append(f"§DROP_STRING::{node.name}§")
            self.eval_expr(node.value)
            self.vapor.append("§MEMBER_ASSIGN§")

        elif isinstance(node, Block):
            for s in node.stmts: 
                self.compile_node(s)
                
        elif isinstance(node, If):
            lbl_else = self.new_label()
            lbl_end = self.new_label()

            self.eval_expr(node.cond)
            self.vapor.append(f"§JUMP_IF_FALSE::{lbl_else}§")
            
            self.compile_node(node.then_br)
            self.vapor.append(f"§JUMP::{lbl_end}§")
            
            self.vapor.append(f"§LABEL::{lbl_else}§")
            if node.else_br: self.compile_node(node.else_br)
            
            self.vapor.append(f"§LABEL::{lbl_end}§")
            
        elif isinstance(node, While):
            lbl_start = self.new_label()
            lbl_end = self.new_label()
            
            self.loop_stack.append((lbl_start, lbl_end))
            self.vapor.append(f"§LABEL::{lbl_start}§")
            
            self.eval_expr(node.cond)
            self.vapor.append(f"§JUMP_IF_FALSE::{lbl_end}§")
            
            self.compile_node(node.body)
            self.vapor.append(f"§JUMP::{lbl_start}§")
            
            self.vapor.append(f"§LABEL::{lbl_end}§")
            self.loop_stack.pop()

        elif isinstance(node, Loop):
            lbl_start = self.new_label()
            lbl_end = self.new_label()
            
            self.loop_stack.append((lbl_start, lbl_end))
            self.vapor.append(f"§LABEL::{lbl_start}§")
            
            self.compile_node(node.body)
            self.vapor.append(f"§JUMP::{lbl_start}§")
            
            self.vapor.append(f"§LABEL::{lbl_end}§")
            self.loop_stack.pop()

        elif isinstance(node, Break):
            if self.loop_stack:
                _, lbl_end = self.loop_stack[-1]
                self.vapor.append(f"§JUMP::{lbl_end}§")

        elif isinstance(node, Continue):
            if self.loop_stack:
                lbl_start, _ = self.loop_stack[-1]
                self.vapor.append(f"§JUMP::{lbl_start}§")

        elif isinstance(node, FnDecl):
            lbl_end = self.new_label()
            self.vapor.append(f"§JUMP::{lbl_end}§")
            
            lbl_func = f"FUNC_{node.name}"
            self.vapor.append(f"§LABEL::{lbl_func}§")
            self.compile_node(node.body)
            self.vapor.append("§RETURN§")
            
            self.vapor.append(f"§LABEL::{lbl_end}§")
            
        elif isinstance(node, Return):
            if node.value: self.eval_expr(node.value)
            self.vapor.append("§RETURN§")

    def eval_expr(self, expr):
        if isinstance(expr, Number): 
            self.vapor.append(f"§DROP_POWDER::{expr.value}§")
        elif isinstance(expr, String): 
            self.vapor.append(f"§DROP_STRING::{expr.value}§")
        elif isinstance(expr, Bool):
            self.vapor.append(f"§DROP_POWDER::{1 if expr.value else 0}§")
        elif isinstance(expr, Var): 
            self.vapor.append(f"§SIP::{self.var_map.get(expr.name, expr.name)}§")
        elif isinstance(expr, BinOp):
            self.eval_expr(expr.left)
            self.eval_expr(expr.right)
            op = {
                "+": "FUSE", "-": "EVAPORATE", "*": "MULTIPLY", "/": "FILTER", 
                "==": "COMPARE_EQ", "!=": "COMPARE_NEQ", "<": "COMPARE_LT", ">": "COMPARE_GT",
                "and": "LOGIC_AND", "or": "LOGIC_OR"
            }
            self.vapor.append(f"§{op.get(expr.op, 'FUSE')}§")
        elif isinstance(expr, UnaryOp):
            self.eval_expr(expr.operand)
            if expr.op == "-": self.vapor.append("§NEGATE§")
            else: self.vapor.append("§NOT§")
        elif isinstance(expr, Index):
            self.eval_expr(expr.target)
            self.eval_expr(expr.index)
            self.vapor.append("§INDEX_GET§")
        elif isinstance(expr, Call):
            if expr.name == "ask": 
                if expr.args: self.eval_expr(expr.args[0])
                self.vapor.append("§SCAN_INPUT§")
            elif expr.name == "num":
                self.eval_expr(expr.args[0])
                self.vapor.append("§CONVERT_NUM§")
            elif expr.name == "str":
                self.eval_expr(expr.args[0])
                self.vapor.append("§CONVERT_STR§")
            else:
                for a in expr.args: self.eval_expr(a)
                self.vapor.append(f"§CALL::{expr.name}::{len(expr.args)}§")

# ==========================================
# 4. ТОЧКА ВХОДА
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("========================================")
        print(" p0P Compiler (to .drink)")
        print("========================================")
        print(" Использование: python compiler.py <файл.p>")
        print("========================================")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Ошибка: Файл {file_path} не найден.")
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as f: source = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="cp1251") as f: source = f.read()
        except:
            with open(file_path, "r", encoding="cp866") as f: source = f.read()

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        
        compiler = DrinkCompiler()
        drink_code = compiler.compile(ast)
        
        out_file = file_path.replace(".p", ".drink")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(drink_code)
            
        print(f"[УСПЕХ] Исходник скомпилирован в {out_file}")
        print(f"[INFO] Вы можете запустить его через DRE: drink_vm.exe {out_file}")
        
    except Exception as e:
        print(f"ОШИБКА КОМПИЛЯЦИИ: {e}")