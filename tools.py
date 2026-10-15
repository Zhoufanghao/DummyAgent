"""小型算术工具：严格解析AST，不使用eval或exec。"""
import ast
import json
import math
import operator

CALCULATOR = {"type": "function", "function": {
    "name": "calculator", "description": "计算有限数值的简单四则运算，可用括号和小整数幂。",
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "算术表达式，如(12+3)*4"}},
        "required": ["expression"], "additionalProperties": False}}}
TOOLS = [CALCULATOR]


def calculator(expression):
    if not isinstance(expression, str) or not 1 <= len(expression) <= 200:
        raise ValueError("expression必须为1—200字符的字符串")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.Div: operator.truediv}

    def compute(node, depth=0):
        if depth > 12:
            raise ValueError("表达式嵌套过深")
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = compute(node.operand, depth + 1) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            left, right = compute(node.left, depth + 1), compute(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) <= 8 and right == int(right):
                value = left ** int(right)
            elif type(node.op) in operations:
                value = operations[type(node.op)](left, right)
            else:
                raise ValueError("仅允许四则运算与绝对值不超过8的整数幂")
        else:
            raise ValueError("表达式包含不允许的语法")
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e15:
            raise ValueError("数值超出范围")
        return value

    return compute(ast.parse(expression, mode="eval").body)


def execute(tool_call):
    """验证模型生成的名称与参数；错误也作为观察结果返回。"""
    try:
        if len(tool_call.function.arguments) > 8192:
            raise ValueError("参数过长")
        arguments = json.loads(tool_call.function.arguments)
        if tool_call.function.name != "calculator":
            raise ValueError("未知工具")
        if not isinstance(arguments, dict) or set(arguments) != {"expression"}:
            raise ValueError("参数必须且只能包含expression")
        return {"ok": True, "value": calculator(arguments["expression"])}
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError, RecursionError) as error:
        return {"ok": False, "error": str(error)[:300]}
