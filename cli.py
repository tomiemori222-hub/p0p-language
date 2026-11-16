import sys
import os
import math

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
# 3. ИНТЕРПРЕТАТОР
# ==========================================
class ReturnSignal(Exception):
    def __init__(self, value): self.value = value
class BreakSignal(Exception): pass
class ContinueSignal(Exception): pass

class FunctionValue:
    def __init__(self, node, env): self.node, self.env = node, env

class Env:
    def __init__(self, parent=None): self.vars, self.consts, self.parent = {}, set(), parent
    def declare(self, name, value, is_const=False):
        self.vars[name] = value
        if is_const: self.consts.add(name)
    def get(self, name):
        if name in self.vars: return self.vars[name]
        if self.parent: return self.parent.get(name)
        raise NameError(f"переменная {name!r} не определена")
    def set(self, name, value):
        if name in self.vars:
            if name in self.consts: raise TypeError(f"нельзя менять константу {name!r}")
            self.vars[name] = value; return
        if self.parent and self.parent.contains(name):
            self.parent.set(name, value); return
        raise NameError(f"переменная {name!r} не определена")
    def contains(self, name): return name in self.vars or (self.parent is not None and self.parent.contains(name))

class Interpreter:
    def __init__(self):
        self.globals = Env()
        self.stack = []

    def run(self, program):
        for s in program: self.exec(s, self.globals)

    def exec_block(self, stmts, env):
        for s in stmts: self.exec(s, env)

    def exec(self, stmt, env):
        if isinstance(stmt, Import):
            # В монолитном файле импорты просто игнорируются (все встроено)
            pass
        elif isinstance(stmt, VarDecl):
            v = self.eval(stmt.value, env) if stmt.value is not None else None
            env.declare(stmt.name, v, stmt.is_const)
        elif isinstance(stmt, Assign): env.set(stmt.name, self.eval(stmt.value, env))
        elif isinstance(stmt, IndexAssign):
            t = self.eval(stmt.target, env); i = self.eval(stmt.index, env); t[i] = self.eval(stmt.value, env)
        elif isinstance(stmt, MemberAssign):
            obj = self.eval(stmt.obj, env)
            if not isinstance(obj, dict): raise TypeError("не объект")
            obj[stmt.name] = self.eval(stmt.value, env)
        elif isinstance(stmt, Say): print(self.to_str(self.eval(stmt.value, env), top=True))
        elif isinstance(stmt, Show): print(self.to_str(self.eval(stmt.value, env), top=True), end="")
        elif isinstance(stmt, Push): self.stack.append(self.eval(stmt.value, env))
        elif isinstance(stmt, ExprStmt): self.eval(stmt.expr, env)
        elif isinstance(stmt, FnDecl): env.declare(stmt.name, FunctionValue(stmt, env))
        elif isinstance(stmt, Return):
            v = self.eval(stmt.value, env) if stmt.value is not None else None
            raise ReturnSignal(v)
        elif isinstance(stmt, Break): raise BreakSignal()
        elif isinstance(stmt, Continue): raise ContinueSignal()
        elif isinstance(stmt, If):
            for cond, body in stmt.branches:
                if self.truthy(self.eval(cond, env)):
                    self.exec(body, Env(env)); return
            if stmt.else_body is not None: self.exec(stmt.else_body, Env(env))
        elif isinstance(stmt, While):
            while self.truthy(self.eval(stmt.cond, env)):
                try: self.exec(stmt.body, Env(env))
                except ContinueSignal: continue
                except BreakSignal: break
        elif isinstance(stmt, ForIn):
            for item in self.eval(stmt.iterable, env):
                le = Env(env); le.declare(stmt.var, item)
                try: self.exec(stmt.body, le)
                except ContinueSignal: continue
                except BreakSignal: break
        elif isinstance(stmt, Loop):
            while True:
                try: self.exec(stmt.body, Env(env))
                except ContinueSignal: continue
                except BreakSignal: break
        elif isinstance(stmt, Delete):
            t = self.eval(stmt.target, env)
            if stmt.index is not None:
                i = self.eval(stmt.index, env); del t[i]
            else:
                if stmt.name not in t: raise NameError("нет такого поля")
                del t[stmt.name]
        elif isinstance(stmt, Block):
            self.exec_block(stmt.stmts, Env(env))
        else:
            raise RuntimeError(f"Неизвестный узел: {type(stmt).__name__}")

    def truthy(self, v):
        if v is None or v is False: return False
        if v == 0 or v == "": return False
        if isinstance(v, (list, dict)) and len(v) == 0: return False
        return True

    def to_str(self, v, top=False):
        if v is True: return "true"
        if v is False: return "false"
        if v is None: return "nil"
        if isinstance(v, FunctionValue): return "<fn>"
        if isinstance(v, str): return v if top else f'"{v}"'
        if isinstance(v, list): return "[" + ", ".join(self.to_str(x) for x in v) + "]"
        if isinstance(v, dict): return "{" + ", ".join(f"{k}: {self.to_str(x)}" for k, x in v.items()) + "}"
        return str(v)

    def eval(self, expr, env):
        if isinstance(expr, Number): return expr.value
        if isinstance(expr, String): return expr.value
        if isinstance(expr, Bool): return expr.value
        if isinstance(expr, Nil): return None
        if isinstance(expr, ListLit): return [self.eval(x, env) for x in expr.items]
        if isinstance(expr, ObjectLit): return {k: self.eval(v, env) for k, v in expr.pairs}
        if isinstance(expr, FnLit):
            node = FnDecl("<fn>", expr.params, expr.body); return FunctionValue(node, env)
        if isinstance(expr, Var): return env.get(expr.name)
        if isinstance(expr, Member):
            obj = self.eval(expr.obj, env)
            if not isinstance(obj, dict): raise TypeError("не объект")
            if expr.name not in obj: raise NameError("поля не существует")
            return obj[expr.name]
        if isinstance(expr, BinOp): return self.binop(expr.op, expr.left, expr.right, env)
        if isinstance(expr, UnaryOp):
            v = self.eval(expr.operand, env)
            return -v if expr.op == "-" else (not self.truthy(v))
        if isinstance(expr, Index):
            t = self.eval(expr.target, env); i = self.eval(expr.index, env); return t[i]
        if isinstance(expr, Call): return self.call(expr.name, expr.args, env)
        raise RuntimeError(f"Неизвестное выражение: {type(expr).__name__}")

    def binop(self, op, l, r, env):
        if op == "and": return self.truthy(self.eval(l, env)) and self.truthy(self.eval(r, env))
        if op == "or": return self.truthy(self.eval(l, env)) or self.truthy(self.eval(r, env))
        a, b = self.eval(l, env), self.eval(r, env)
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/":
            if b == 0: raise ZeroDivisionError("деление на ноль")
            return a / b
        if op == "%": return a % b
        if op == "==": return a == b
        if op == "!=": return a != b
        if op == "<": return a < b
        if op == ">": return a > b
        if op == "<=": return a <= b
        if op == ">=": return a >= b
        raise RuntimeError(f"Неизвестный оператор {op}")

    def call_fnval(self, fnval, arg_exprs, env):
        fn = fnval.node
        if len(arg_exprs) != len(fn.params):
            raise TypeError(f"нужно {len(fn.params)} арг., передано {len(arg_exprs)}")
        vals = [self.eval(a, env) for a in arg_exprs]
        local = Env(fnval.env)
        for p, v in zip(fn.params, vals): local.declare(p, v)
        try: self.exec_block(fn.body.stmts, local)
        except ReturnSignal as r: return r.value
        return None

    def call(self, name, arg_exprs, env):
        if "." not in name and env.contains(name):
            v = env.get(name)
            if isinstance(v, FunctionValue): return self.call_fnval(v, arg_exprs, env)
        
        # ВСТРОЕННЫЕ ФУНКЦИИ
        if name == "ask": return input(self.to_str(self.eval(arg_exprs[0], env), top=True) if arg_exprs else "")
        if name == "num": 
            try: return int(self.eval(arg_exprs[0], env))
            except: return 0
        if name == "str": return self.to_str(self.eval(arg_exprs[0], env), top=True)
        if name == "type":
            v = self.eval(arg_exprs[0], env)
            if v is None: return "nil"
            if isinstance(v, bool): return "bool"
            if isinstance(v, (int, float)): return "number"
            if isinstance(v, str): return "string"
            if isinstance(v, list): return "list"
            if isinstance(v, dict): return "object"
            if isinstance(v, FunctionValue): return "function"
            return "unknown"
        if name == "append":
            xs = self.eval(arg_exprs[0], env); xs.append(self.eval(arg_exprs[1], env)); return None
        if name == "range": return list(range(int(self.eval(arg_exprs[0], env))))
        if name == "keys": return list(self.eval(arg_exprs[0], env).keys())
        if name == "values": return list(self.eval(arg_exprs[0], env).values())
        if name == "has": return self.eval(arg_exprs[1], env) in self.eval(arg_exprs[0], env)
        if name == "abs": return abs(self.eval(arg_exprs[0], env))
        if name == "min": return min(self.eval(arg_exprs[0], env))
        if name == "max": return max(self.eval(arg_exprs[0], env))
        if name == "sum": return sum(self.eval(arg_exprs[0], env))
        if name == "upper": return self.eval(arg_exprs[0], env).upper()
        if name == "lower": return self.eval(arg_exprs[0], env).lower()
        if name == "len": return len(self.eval(arg_exprs[0], env))
        if name == "pop":
            if not self.stack: raise IndexError("стек пуст")
            return self.stack.pop()
        if name == "pile": return len(self.stack)
        
        raise NameError(f"функция {name!r} не определена")

# ==========================================
# 4. ТОЧКА ВХОДА (CLI)
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("========================================")
        print(" p0P Language Interpreter (CLI)")
        print("========================================")
        print(" Использование: python cli.py <файл.p>")
        print("========================================")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Ошибка: Файл {file_path} не найден.")
        sys.exit(1)

    # Умное чтение файла (чтобы не крашилось на русских буквах в Windows)
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
        Interpreter().run(ast)
    except Exception as e:
        print(f"ОШИБКА: {e}")